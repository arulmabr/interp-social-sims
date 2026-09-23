"""Standalone figures from saved pilot outputs; no GPU or new model queries."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .cpt import probabilities


def read(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    destination = args.run / 'figures'
    destination.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'savefig.facecolor': 'white'})
    refined = args.run / 'refinement'
    rows = read(refined / 'rows.json')
    truth = probabilities(rows, read(refined / 'report.json')['target'])
    conditions = [
        ('baseline', 'Base model'),
        ('lora_combined_original', 'Original combined LoRA'),
        ('lora_combined_refined', 'Refined combined LoRA'),
        ('mean_delta_common_norm', 'Raw mean shift, norm 1'),
        ('mean_delta_fitted_magnitude', 'Raw mean shift, fitted magnitude'),
        ('sae_k10_fitted_magnitude', 'Ten SAE features, fitted magnitude'),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(12, 9), sharex=True, sharey=True)
    colors = {'gain': '#28799f', 'loss': '#ce7942', 'mixed': '#6a5690'}
    for ax, (name, title) in zip(axes.flat, conditions):
        scores = read(refined / f'scores_{name}.json')
        observed = np.array([r['p_risky'] for r in scores])
        invalid = np.array([r['answer_mass'] < .95 for r in scores])
        for frame, color in colors.items():
            mask = np.array([r['frame'] == frame for r in rows])
            ax.scatter(truth[mask], observed[mask], s=13, alpha=.45, c=color, label=frame)
        ax.plot([0, 1], [0, 1], color='#555555', lw=.8, ls='--', zorder=0)
        rmse = np.sqrt(np.mean((truth-observed)**2))
        ax.set_title(f'{title}\nRMSE {rmse:.3f}; A/B mass <95%: {invalid.sum()}/{len(rows)}', fontsize=10)
        ax.set(xlim=(-.03, 1.03), ylim=(-.03, 1.03), xticks=[0, .5, 1], yticks=[0, .5, 1])
        ax.set_aspect('equal')
    for ax in axes[:, 0]:
        ax.set_ylabel('Model risky-choice probability | A or B')
    for ax in axes[-1]:
        ax.set_xlabel('Planted CPT risky-choice probability')
    axes[0, 0].legend(loc='upper left', fontsize=8, frameon=False)
    fig.suptitle('Fresh-grid recovery: weight-space training and residual replay', fontsize=15, y=.98)
    fig.text(.5, .012, '300 fresh prompts; both answer orders. Conditional probabilities require adequate A/B mass.\n'
             'The full adapter edits several layers and positions; residual replay edits the final position at layer 50.',
             ha='center', fontsize=9, color='#444444')
    fig.subplots_adjust(left=.075, right=.985, bottom=.12, top=.88, hspace=.42, wspace=.22)
    for ext in ('png', 'pdf'):
        fig.savefig(destination / f'fresh_grid_recovery.{ext}', dpi=180)
    plt.close(fig)

    report = read(args.run / 'report.json')
    names = ['reward_probe_l48', 'reward_probe_l50', 'feature_184', 'feature_4237',
             'feature_31935', 'feature_13142', 'feature_20117', 'feature_4992',
             'creativity_triple', 'sae_readout_highest_cosine', 'sae_readout_k10']
    labels = ['Reward probe, L48', 'Reward probe, L50', 'Feature 184', 'Feature 4237',
              'Feature 31935', 'Feature 13142', 'Feature 20117', 'Feature 4992',
              'Creativity triple', 'Highest positive cosine', 'Readout OMP, k=10']
    values = [report['directions'][name]['cosine_readout'] for name in names]
    fig, (left, right) = plt.subplots(1, 2, figsize=(12, 5.5), gridspec_kw={'width_ratios': [1.3, 1]})
    left.barh(labels[::-1], values[::-1], color='#28799f')
    left.axvline(0, color='#444444', lw=.7)
    left.set(xlabel='Cosine with discovery-mean readout gradient', xlim=(-.045, .35),
             title='Readout alignment')
    agents = list(report['footprints'])
    errors = [report['footprints'][name]['native']['10']['relative_error'] for name in agents]
    agents.append('combined_refined')
    errors.append(read(refined / 'report.json')['footprint']['native']['10']['relative_error'])
    right.barh([name.replace('_', ' ') for name in agents][::-1], errors[::-1], color='#6a5690')
    for i, value in enumerate(errors[::-1]):
        right.text(value-.025, i, f'{value:.3f}', va='center', ha='right', color='white')
    right.set(xlim=(0, 1), xlabel='Relative residual error (0 = exact)',
              title='Ten-feature approximation of LoRA mean shift')
    fig.text(.5, .02, 'Discovery-only geometry. Sparse approximation error does not test the capacity of the full SAE dictionary.',
             ha='center', fontsize=9, color='#444444')
    fig.tight_layout(rect=(0, .065, 1, 1))
    for ext in ('png', 'pdf'):
        fig.savefig(destination / f'dictionary_geometry.{ext}', dpi=180)
    plt.close(fig)
    print(destination)


if __name__ == '__main__':
    main()
