"""Export readout-alignment covariates and the actual selected decoder coefficients."""
import argparse
import csv
import json
from pathlib import Path
import torch


def write_csv(path,rows):
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);args=p.parse_args();root=args.root
    read=lambda n:json.loads((root/n).read_text());screen=read('causal_screen.json');lock=read('selection_lock.json')
    rows=[]
    for entry in screen:
        for target in ('combined','neutral'):
            rows.append({'feature':entry['feature'],'scope':entry['scope'],'sign':entry['sign'],'target':target,
                         'cosine_to_readout':entry['cosine_to_readout'],'discovery_ce':entry['target_ce'][target],
                         'discovery_teacher_rmse':entry['target_rmse'][target],
                         'min_answer_mass':min(s['answer_mass'] for s in entry['scores'])})
    write_csv(root/'feature_screen.csv',rows)
    coefficients=[]
    for target,choice in lock['choices'].items():
        scope=choice['selected']['scope'];dose=choice['selected']['dose']
        for seed in (31,73):
            info=lock['training'][f'{target}_sae10_{scope}_seed{seed}']
            for feature,coefficient in zip(info['features'],info['decoder_coefficients']):
                cosine=next(e['cosine_to_readout'] for e in screen if e['feature']==feature)
                coefficients.append({'target':target,'scope':scope,'dose':dose,'seed':seed,'feature':feature,
                                     'decoder_coefficient_at_selected_dose':coefficient*dose/16,'cosine_to_readout':cosine})
    write_csv(root/'selected_feature_coefficients.csv',coefficients)
    gradient=torch.load(root/'readout_gradient.pt',map_location='cpu',weights_only=True)
    vectors=torch.load(root/'locked_interventions.pt',map_location='cpu',weights_only=True);alignments=[]
    for name,item in vectors.items():
        v=item['vector']
        if v is not None:alignments.append({'condition':name,'norm':float(v.norm()),'scope':item['scope'],
                                           'cosine_to_readout':float(torch.dot(v,gradient)/(v.norm()*gradient.norm()))})
    write_csv(root/'direction_alignment.csv',alignments)
    print(json.dumps({'screen_rows':len(rows),'selected_coefficient_rows':len(coefficients),'directions':len(alignments)}))


if __name__=='__main__':main()
