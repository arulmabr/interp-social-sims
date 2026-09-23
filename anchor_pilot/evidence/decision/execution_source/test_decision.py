import numpy as np
import torch

from anchor_pilot.decision import sphere_vector, evaluate, train_vector
from anchor_pilot.decision_analysis import fit_shortcut, shortcut_design
from anchor_pilot.decision_plan import build_decision_rows, TARGETS
from anchor_pilot.cpt import probabilities
from anchor_pilot.modeling import load_stack, prepare_inputs
from scipy.special import expit


def test_frames_orders_and_frozen_economics_disjoint():
    rows=build_decision_rows();keys={}
    for split in ('discovery','selection','frozen'):
        subset=[r for r in rows if r['split']==split]
        keys[split]={(r['frame'],r['probability'],r['stake'],r['ratio']) for r in subset}
        for key in keys[split]:
            matching=[r for r in subset if (r['frame'],r['probability'],r['stake'],r['ratio'])==key]
            assert {r['risky_label'] for r in matching}=={'A','B'}
    assert not keys['frozen']&(keys['selection']|keys['discovery'])


def test_shortcut_recovers_frame_bias_temperature_and_label_on_unseen_economics():
    rows=build_decision_rows();train=[r for r in rows if r['split']=='selection'];test=[r for r in rows if r['split']=='frozen']
    b1=probabilities(train,TARGETS['combined']);b2=probabilities(test,TARGETS['combined']);theta=[.7,1.2,1.5,.4,-.6,.3,.5]
    target=expit(shortcut_design(train,b1)@theta);model=fit_shortcut(train,b1,target)
    assert model['converged']
    assert np.max(abs(expit(shortcut_design(test,b2)@model['parameters'])-expit(shortcut_design(test,b2)@theta)))<1e-4


def test_sparse_training_updates_only_vector_and_stays_in_span():
    model,tok,d,e,layers,_=load_stack(True);layer=layers[-1]
    rows=build_decision_rows()[:4];prepared=prepare_inputs(model,tok,rows);q=torch.linalg.qr(d[:,:3]).Q
    train_vector.scope='all';train_vector.name='test'
    before=[p.detach().clone() for p in model.parameters()]
    initial=torch.randn(32)
    vector,info=train_vector(model,prepared,prepared,np.array([.8,.2,.7,.3]),np.array([.8,.2,.7,.3]),layer,q,initial,31,2,4)
    assert abs(float(vector.norm())-16)<1e-5
    assert torch.allclose(vector,q@(q.T@vector),atol=2e-5)
    assert all(torch.equal(a,b) for a,b in zip(before,model.parameters()))
    assert not model.model.layers[layer]._forward_hooks
    result=evaluate(model,prepared,layer,vector,'all')
    assert all(r['norm']['max_relative_norm_error']<1e-5 for r in result)


def test_sphere_vector_is_differentiable_for_dense_and_sparse():
    for basis in (None,torch.linalg.qr(torch.randn(32,4)).Q):
        theta=torch.randn(32 if basis is None else 4,requires_grad=True)
        vector=sphere_vector(theta,basis,4.)
        (vector@torch.randn(32)).backward()
        assert abs(float(vector.detach().norm())-4)<1e-5
        assert theta.grad is not None and theta.grad.norm()>0
