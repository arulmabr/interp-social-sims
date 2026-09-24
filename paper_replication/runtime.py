"""Batched generation with explicit simultaneous additive SAE interventions."""
import time
from contextlib import contextmanager

from label_pilot.runtime import Runtime
from label_pilot.common import LAYER


def edit_selected(hidden,encoder,bias,decoder,deltas):
    import torch
    x=hidden.float()
    before=torch.relu(x@encoder.T+bias)
    after=torch.clamp(before+deltas,min=0)
    displacement=(after-before)@decoder.T
    if not torch.count_nonzero(deltas):
        updated=hidden
    else:
        updated=(x+displacement).to(hidden.dtype)
    norm=(updated.float()-x).norm(dim=-1)
    return updated,before,after,norm


class PaperRuntime(Runtime):
    def __init__(self):
        super().__init__([184,4237,31935])
        self.tokenizer.padding_side='left'
        if self.tokenizer.pad_token_id is None:self.tokenizer.pad_token_id=self.tokenizer.eos_token_id
        self.metadata.update(generation_top_k=0,tokenizer_padding_side='left',sampling=True,
            generation_eos_token_ids=self.model.generation_config.eos_token_id,
            local_strength_units='raw released-SAE activation units; hosted scaling equivalence not established')

    @contextmanager
    def batch_intervention(self,edits,batch_size,zero=False):
        from accelerate.utils.operations import send_to_device
        torch=self.torch
        deltas=torch.zeros(len(self.features),device=self.device,dtype=torch.float32)
        for edit in edits:deltas[self.features.index(edit['feature_id'])]+=0 if zero else edit['delta']
        stats={}
        if not edits:
            yield stats
            return
        active=torch.ones(batch_size,device=self.device,dtype=torch.bool)
        eos=self.model.generation_config.eos_token_id
        eos=[eos]if isinstance(eos,int)else eos
        counts=torch.zeros(batch_size,device=self.device,dtype=torch.int64)
        changed=counts.clone();norm_sum=torch.zeros(batch_size,device=self.device)
        sums=torch.zeros(batch_size,len(self.features),device=self.device)
        after_sums=sums.clone();maxes=sums.clone();after_maxes=sums.clone()
        call_count=0
        def pre_hook(_module,args,kwargs):
            nonlocal active,call_count
            ids=kwargs.get('input_ids')
            if call_count and ids is not None:
                # This helper uses the transport verified during Runtime setup,
                # including host staging if direct GPU peer copies are faulty.
                last_ids=send_to_device(ids[:,-1],self.device)
                ended=torch.zeros(batch_size,device=self.device,dtype=torch.bool)
                for token in eos:ended|=last_ids==token
                active &= ~ended
        def hook(_module,_args,output):
            nonlocal call_count,counts,changed,norm_sum,sums,after_sums,maxes,after_maxes
            hidden=output[0]if isinstance(output,tuple)else output
            updated,before,after,norm=edit_selected(hidden[:,-1,:],self.encoder,self.bias,self.decoder,deltas)
            counts+=active;changed+=(norm>0)&active;norm_sum+=norm*active
            sums+=before*active[:,None];after_sums+=after*active[:,None]
            maxes=self.torch.maximum(maxes,before*active[:,None]);after_maxes=self.torch.maximum(after_maxes,after*active[:,None])
            call_count+=1
            if zero:return output
            result=hidden.clone();result[:,-1,:]=updated
            return (result,*output[1:])if isinstance(output,tuple)else result
        pre=self.model.register_forward_pre_hook(pre_hook,with_kwargs=True)
        handle=self.model.model.layers[LAYER].register_forward_hook(hook)
        try:yield stats
        finally:
            handle.remove();pre.remove()
            denom=counts.clamp(min=1)[:,None]
            arrays=[x.detach().cpu().tolist()for x in (counts,changed,norm_sum/counts.clamp(min=1),sums/denom,after_sums/denom,maxes,after_maxes)]
            stats['rows']=[dict(hook_calls=arrays[0][i],changed_positions=arrays[1][i],realized_norm_mean=arrays[2][i],
                features=[dict(feature_id=f,before_mean=arrays[3][i][j],after_mean=arrays[4][i][j],before_max=arrays[5][i][j],after_max=arrays[6][i][j])
                          for j,f in enumerate(self.features)if any(e['feature_id']==f for e in edits)])for i in range(batch_size)]

    def generate_batch(self,rows,seed,zero=False,max_new_tokens=None,repair_responses=None):
        if not rows:return []
        config=rows[0]['generation'];edits=rows[0]['edits']
        if any(r['generation']!=config or r['edits']!=edits for r in rows):
            raise ValueError('Batch must have common generation and intervention settings')
        texts=[]
        for i,row in enumerate(rows):
            messages=[dict(role='system',content=row['system_prompt']),dict(role='user',content=row['user_prompt'])]
            if repair_responses is not None:
                options='Safe Option or Risky Option'if row['game']=='lottery'else'Accept or Reject'
                messages += [dict(role='assistant',content=repair_responses[i]),dict(role='user',content=
                    f'Your previous response did not provide a valid choice on the first line. Start with exactly one of: {options}. You may explain your choice on the next line.')]
            texts.append(self.tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True))
        encoded=self.tokenizer(texts,return_tensors='pt',padding=True,add_special_tokens=False)
        inputs={k:v.to(self.model.get_input_embeddings().weight.device)for k,v in encoded.items()}
        self.torch.manual_seed(seed);self.torch.cuda.manual_seed_all(seed)
        started=time.monotonic()
        with self.torch.inference_mode(),self.batch_intervention(edits,len(rows),zero) as trace:
            generated=self.model.generate(**inputs,do_sample=True,temperature=config['temperature'],top_p=config['top_p'],top_k=0,
                max_new_tokens=max_new_tokens or config['max_new_tokens'],pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.model.generation_config.eos_token_id,use_cache=True)
        suffixes=generated[:,inputs['input_ids'].shape[1]:].detach().cpu().tolist()
        elapsed=time.monotonic()-started
        eos=self.model.generation_config.eos_token_id;eos={eos}if isinstance(eos,int)else set(eos)
        out=[]
        for i,ids in enumerate(suffixes):
            end=next((j+1 for j,t in enumerate(ids)if t in eos),len(ids));tokens=ids[:end]
            out.append(dict(response=self.tokenizer.decode(tokens,skip_special_tokens=True),generated_tokens=len(tokens),
                input_tokens=int(encoded['attention_mask'][i].sum()),truncated=bool(tokens and tokens[-1]not in eos),
                seed=seed,batch_size=len(rows),batch_elapsed_seconds=elapsed,
                trace=trace.get('rows',[{}for _ in rows])[i]))
        return out
