import pytest
import torch

from anchor_pilot.modeling import add_lora, load_stack, prepare_inputs
from anchor_pilot.repair_design import build_repair_rows, MODULES
from anchor_pilot.replay import capture_full, evaluate_batch, identity_gate, patch_full, projection, records, encoder_delta
from anchor_pilot.replay_plan import CONDITIONS, build_replay_rows


def fixture_stack():
    model,tok,decoder,encoder,layers,_=load_stack(True)
    add_lora(model,0,layers[-1],rank=2,target_modules=MODULES)
    g=torch.Generator().manual_seed(43)
    for name,p in model.named_parameters():
        if 'lora_B' in name:p.data.normal_(0,.07,generator=g)
    inputs=prepare_inputs(model,tok,build_repair_rows(True)[:2])
    inputs[1][0]['input_ids']=inputs[1][0]['input_ids'][:,-5:]
    return model,inputs,decoder,encoder,layers[-1]


def test_replay_identity_with_nonzero_adapter_and_left_padding():
    model,inputs,d,e,layer=fixture_stack()
    q={str(k):torch.linalg.qr(d[:,:k]).Q for k in (10,30)}
    scores,geometry=evaluate_batch(model,inputs,layer,d,e,torch.ones(32)*.03,q)
    assert set(scores)==set(CONDITIONS)
    assert identity_gate(scores)['passed']
    assert scores['baseline']!=scores['lora']
    assert max(abs(x['p_risky']-y['p_risky']) for x,y in zip(scores['raw_final_replace'],scores['lora']))>1e-6
    assert all(x>0 for x in geometry['raw_delta_norm_final'])
    assert len(model.model.layers[layer]._forward_hooks)==0


def test_mask_changes_only_selected_tokens_and_removes_hook_on_error():
    model,inputs,_,_,layer=fixture_stack()
    model.eval()
    with torch.no_grad(),capture_full(model,layer) as before:records(model,inputs)
    h=before[0];mask=torch.zeros(h.shape[:2],dtype=torch.bool);mask[0,-1]=True
    with torch.no_grad(),patch_full(model,layer,torch.ones(32),mask),capture_full(model,layer) as after:records(model,inputs)
    assert torch.equal(after[0][~mask],h[~mask])
    assert torch.allclose(after[0][mask],h[mask]+1)
    with pytest.raises(ValueError):
        with patch_full(model,layer,torch.zeros(2),mask):records(model,inputs)
    assert not model.model.layers[layer]._forward_hooks


def test_projection_matches_selected_decoder_least_squares():
    torch.manual_seed(8);d=torch.randn(12,4);x=torch.randn(3,2,12)
    q=torch.linalg.qr(d).Q;expected=(d@torch.linalg.lstsq(d,x.reshape(-1,12).T).solution).T.reshape_as(x)
    assert torch.allclose(projection(x,q),expected,atol=1e-6)


def test_encoder_difference_preserves_zero_delta_and_ignores_padding():
    torch.manual_seed(12);x=torch.randn(2,5,8);mask=torch.ones(2,5,dtype=torch.bool);mask[1,:2]=False
    d=torch.randn(8,10);e=(torch.randn(10,8),torch.randn(10))
    assert torch.count_nonzero(encoder_delta(x,x,mask,d,e))==0
    y=x+.1;result=encoder_delta(x,y,mask,d,e,chunk=3)
    expected=(torch.relu(y[mask]@e[0].T+e[1])-torch.relu(x[mask]@e[0].T+e[1]))@d.T
    assert torch.allclose(result[mask],expected,atol=1e-5)
    assert torch.count_nonzero(result[~mask])==0


def test_new_frozen_grid_is_balanced_and_disjoint():
    development,frozen=build_replay_rows()
    assert len(development)==36 and len(frozen)==540
    assert {r['frame'] for r in frozen}=={'gain','loss','mixed'}
    assert len({r['economic_id'] for r in frozen})==270
    assert not {r['text'] for r in frozen}&{r['text'] for r in build_repair_rows()}


@pytest.mark.skipif(torch.cuda.device_count()<2,reason='Needs two CUDA devices')
def test_bf16_partitioned_replay_is_exact():
    from anchor_pilot.modeling import install_partition_transfers
    model,inputs,d,e,layer=fixture_stack()
    model.to(device='cuda:0',dtype=torch.bfloat16)
    for block in model.model.layers[2:]:block.to('cuda:1')
    model.model.norm.to('cuda:1');model.lm_head.to('cuda:1')
    for name,param in model.named_parameters():
        if 'lora_' in name:param.data=param.data.float()
    install_partition_transfers(model)
    inputs=[({k:v.to('cuda:0') for k,v in item[0].items()},item[1],item[2]) for item in inputs]
    d=d.to('cuda:1');e=tuple(v.to('cuda:1') for v in e)
    q={str(k):torch.linalg.qr(d[:,:k]).Q for k in (10,30)}
    scores,_=evaluate_batch(model,inputs,layer,d,e,torch.ones(32,device='cuda:1')*.03,q)
    assert identity_gate(scores)['passed']
