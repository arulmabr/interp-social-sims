import copy
import os
from collections import Counter
from pathlib import Path

import pytest
import torch

from paper_replication.common import load_plan,records,parse_answer,make_batches,batch_seed,ROOT
from paper_replication.runtime import edit_selected


def test_zero_edit_is_bitwise_identity():
    torch.manual_seed(13)
    h=torch.randn(8,16).to(torch.bfloat16);enc=torch.randn(3,16);bias=torch.randn(3);dec=torch.randn(16,3)
    result,before,after,norm=edit_selected(h,enc,bias,dec,torch.zeros(3))
    assert result is h and torch.equal(result,h)
    assert torch.equal(before,after)and not torch.count_nonzero(norm)


def test_dormant_feature_can_be_activated_and_updates_are_simultaneous():
    h=torch.zeros(2,4);enc=torch.eye(4)[:3];bias=torch.tensor([-2.,-.2,1.]);dec=torch.eye(4)[:,:3]
    result,before,after,norm=edit_selected(h,enc,bias,dec,torch.tensor([.5,.7,-2.]))
    assert torch.allclose(before,torch.tensor([[0.,0.,1.],[0.,0.,1.]]))
    assert torch.allclose(after,torch.tensor([[.5,.7,0.],[.5,.7,0.]]))
    # Full decode/reconstruct with residual correction has the same result.
    residual=h-before@dec.T
    assert torch.allclose(result,after@dec.T+residual)
    assert (norm>0).all()


@pytest.mark.parametrize('game,text,answer',[
    ('ultimatum','Accept\nI would reject a different offer.','Accept'),
    ('ultimatum','"Reject"\nAccepting would be worse.','Reject'),
    ('lottery','Risky Option\nExplanation','Risky Option'),
    ('lottery','{"answer":"Safe Option","comment":"Risky Option is less attractive"}','Safe Option'),
])
def test_parse_explicit_answer_without_reading_rationale(game,text,answer):
    result=parse_answer(game,text);assert result['valid']and result['answer']==answer


@pytest.mark.parametrize('text',['I might accept or reject.','Accept or Reject','I cannot answer.',''])
def test_invalid_answers_are_not_silently_counted_as_rejection(text):
    assert parse_answer('ultimatum',text)==dict(valid=False,answer=None,target=None)


def test_batches_keep_common_interventions_and_paired_random_seeds():
    rows=[dict(game='lottery',condition=c,value=10,agent_index=i,id=f'{c}{i}')for c in ['baseline','steering']for i in range(40)]
    batches=list(make_batches(rows,8))
    assert len(batches)==10
    assert sum(len(b)for b,_ in batches)==80
    assert all(len({r['condition']for r in b})==1 for b,_ in batches)
    assert [s for b,s in batches if b[0]['condition']=='baseline']==[s for b,s in batches if b[0]['condition']=='steering']
    assert len(set(s for b,s in batches))==5


def test_original_protocol_inputs():
    path=Path(os.environ.get('PAPER_REPLICATION_PLAN_PATH',ROOT/'outputs/original-games-v1'))
    if not path.exists():pytest.skip('Extracted original input plan not present')
    plan=load_plan(path);rows=records(path/'requests.jsonl')
    assert len(rows)==plan['request_count']==9040
    counts=Counter((r['game'],r['condition'],r['value'])for r in rows)
    assert len(counts)==226 and set(counts.values())=={40}
    lookup={(r['game'],r['condition'],r['value'],r['agent_index']):r for r in rows}
    for r in rows:
        assert r['generation']['temperature']==.5 and r['generation']['max_new_tokens']==1000
        if r['edits']:
            baseline=lookup[(r['game'],'baseline',r['value'],r['agent_index'])]
            assert r['system_prompt']==baseline['system_prompt']
            assert r['user_prompt']==baseline['user_prompt']
    assert set(e['feature_id']for r in rows for e in r['edits'])=={184,4237,31935}
    scheduled=[r for batch,_ in make_batches(rows,8)for r in batch]
    assert len(scheduled)==len(rows)and {r['id']for r in scheduled}=={r['id']for r in rows}
    early=Counter((r['game'],r['condition'])for r in scheduled[:160])
    assert early=={(g,c):40 for g in ('lottery','ultimatum')for c in ('baseline','steering')}
    # Input ordering cannot change scheduling or sampling seeds.
    assert [(b[0]['id'],s)for b,s in make_batches(rows,8)]==[(b[0]['id'],s)for b,s in make_batches(list(reversed(rows)),8)]


def test_full_run_resume_preserves_ids_and_smoke_gate(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from paper_replication.common import write,file_hash,digest
    from paper_replication.run import execute
    import paper_replication.runtime
    source=Path(os.environ.get('PAPER_REPLICATION_PLAN_PATH',ROOT/'outputs/original-games-v1'))
    if not source.exists():pytest.skip('Original input plan not present')
    all_rows=records(source/'requests.jsonl')
    selected=[r for r in all_rows if (r['game'],r['value'])in [('lottery',100),('ultimatum',30)]
              and r['condition']in ('baseline','steering')and r['agent_index']<8]
    plan_dir=tmp_path/'plan';plan_dir.mkdir()
    import json
    (plan_dir/'requests.jsonl').write_text(''.join(json.dumps(r)+'\n'for r in selected))
    p=dict(request_count=len(selected),batch_size=8,requests_sha256=file_hash(plan_dir/'requests.jsonl'))
    p['plan_hash']=digest(p);write(plan_dir/'plan.json',p)
    class FakeRuntime:
        metadata={'fake':True}
        def generate_batch(self,rows,seed,zero=False,**kwargs):
            out=[]
            for r in rows:
                active=bool(r['edits'])and not zero
                answer=('Risky Option'if active else'Safe Option')if r['game']=='lottery'else('Accept'if active else'Reject')
                out.append(dict(response=answer,generated_tokens=1,input_tokens=10,truncated=False,
                    seed=seed,batch_size=len(rows),batch_elapsed_seconds=.01,trace=dict(changed_positions=int(active),hook_calls=1)))
            return out
    monkeypatch.setattr(paper_replication.runtime,'PaperRuntime',FakeRuntime)
    args=SimpleNamespace(plan=str(plan_dir),output=str(tmp_path/'run'),resume=False,smoke_only=False,max_seconds=100)
    first=execute(args);assert first['status']=='time_limit'and first['completed']==0
    args.resume=True;args.max_seconds=1000
    final=execute(args);assert final['status']=='completed'and final['completed']==32
    output=records(tmp_path/'run/responses.jsonl')
    assert len({r['id']for r in output})==32
    assert all(r['first_attempt_parse']['valid']and r['repair']is None for r in output)
    again=execute(args);assert again==final
    assert len(records(tmp_path/'run/responses.jsonl'))==32
