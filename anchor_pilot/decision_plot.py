"""Plot all frozen reward levels, both seeds and labels; never selects a method."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .cpt import probabilities


def main():
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);args=parser.parse_args();root=args.root
    read=lambda name:json.loads((root/name).read_text())
    rows=read('frozen_rows.json');plan=read('plan.json');lock=read('selection_lock.json')
    for template in ('original','transfer'):
        fig,axes=plt.subplots(2,3,figsize=(13,7),sharex=True,sharey=True)
        for j,target in enumerate(('combined','neutral')):
            choice=lock['choices'][target]['selected'];scope=choice['scope'];dose=choice['dose']
            series={'Planted CPT':probabilities(rows,plan['targets'][target]),
                    'Base':np.array([s['p_risky'] for s in read('frozen_scores_baseline.json')])}
            if target=='combined':series['LoRA']=np.array([s['p_risky'] for s in read('frozen_scores_lora.json')])
            for method,label in [('dense','Dense vector'),('sae10','10 SAE features')]:
                series[label]=np.array([[s['p_risky'] for s in read(f'frozen_scores_{target}_{method}_{scope}_seed{seed}_rho{dose:g}.json')] for seed in plan['seeds']])
            for i,frame in enumerate(('gain','loss','mixed')):
                ax=axes[j,i];ratios=sorted({r['ratio'] for r in rows if r['template']==template})
                colors={'Planted CPT':'#111111','Base':'#999999','LoRA':'#8b5cf6','Dense vector':'#1479b8','10 SAE features':'#d66a19'}
                for label,values in series.items():
                    ys=[];low=[];high=[]
                    for ratio in ratios:
                        ids=[i for i,r in enumerate(rows) if r['template']==template and r['frame']==frame and r['probability']==.42 and r['stake']==35 and r['ratio']==ratio]
                        if values.ndim==1:ys.append(float(values[ids].mean()))
                        else:
                            seeds=values[:,ids].mean(1);ys.append(float(seeds.mean()));low.append(float(seeds.min()));high.append(float(seeds.max()))
                    ax.plot(ratios,ys,label=label,color=colors[label],linewidth=2,linestyle='--' if label=='Base' else '-',marker='o',markersize=3)
                    if low:ax.fill_between(ratios,low,high,color=colors[label],alpha=.18)
                ax.axhline(.5,color='#cccccc',linewidth=.8);ax.grid(alpha=.15);ax.set_ylim(-.02,1.02)
                ax.set_title(f'{target.capitalize()} target · {frame}')
                if i==0:ax.set_ylabel('Risky-choice probability')
                if j==1:ax.set_xlabel('Risky-outcome magnitude / stake')
        handles,labels=axes[0,0].get_legend_handles_labels();fig.legend(handles,labels,ncol=5,loc='lower center',frameon=False)
        fig.suptitle(f'Fresh {template} wording · probability 0.42 · stake 35 tokens',fontsize=15)
        fig.text(.5,.92,'Both answer orders averaged; shaded ranges show the two steering-training seeds, not confidence intervals.',ha='center',fontsize=10)
        fig.tight_layout(rect=(0,.05,1,.9));fig.savefig(root/f'decision_curves_{template}.png',dpi=170);plt.close(fig)


if __name__=='__main__':main()
