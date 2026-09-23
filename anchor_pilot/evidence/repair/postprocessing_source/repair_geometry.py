"""Descriptive heterogeneity of saved discovery LoRA residual changes."""
import argparse
import hashlib
import json
from pathlib import Path

import torch

from .smoke import save_json


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    args=p.parse_args();torch.set_num_threads(4)
    source=args.run/'footprint.pt';data=torch.load(source,map_location='cpu',weights_only=True)
    rows=json.loads((args.run/'calibration_rows.json').read_text())
    assert data['prompt_ids']==[r['id'] for r in rows]
    assert all(r['split']=='discovery' for r in rows)
    delta=data['delta_h'].double();mean=delta.mean(0);norms=delta.norm(dim=1)
    energy=delta.square().sum();mean_energy=len(rows)*mean.square().sum()
    cosine=delta@mean/(norms*mean.norm()).clamp_min(1e-12)
    groups={}
    for field in ('frame','risky_label'):
        grouped=[];captured=0
        for value in sorted({r[field] for r in rows}):
            mask=torch.tensor([r[field]==value for r in rows]);shift=delta[mask].mean(0)
            captured+=int(mask.sum())*float(shift.square().sum())
            grouped.append({'value':value,'n':int(mask.sum()),'mean_shift_norm':float(shift.norm()),
                'cosine_with_overall_mean':float(shift@mean/(shift.norm()*mean.norm()).clamp_min(1e-12))})
        groups[field]={'fraction_energy_in_group_means':captured/float(energy),'groups':grouped}
    result={'n':len(rows),'layer':50,'split':'discovery','mean_shift_norm':float(mean.norm()),
        'mean_per_prompt_shift_norm':float(norms.mean()),
        'fraction_shift_energy_in_constant_mean':float(mean_energy/energy),
        'constant_mean_relative_reconstruction_error':float(((delta-mean).square().sum()/energy).sqrt()),
        'per_prompt_cosine_with_mean_quantiles':{str(q):float(torch.quantile(cosine,q)) for q in (0.,.25,.5,.75,1.)},
        'groups':groups,'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scope':'Descriptive geometry of discovery residual changes; does not select interventions or prove a behavioral mechanism.'}
    save_json(args.run/'residual_heterogeneity.json',result)
    print(json.dumps({k:result[k] for k in ('n','mean_shift_norm','fraction_shift_energy_in_constant_mean','constant_mean_relative_reconstruction_error')}))


if __name__=='__main__':main()
