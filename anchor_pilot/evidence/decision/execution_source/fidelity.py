"""Prespecified original-magnitude replay to separate dose and dictionary loss."""
import argparse
import json
import time
from pathlib import Path

import torch

from .modeling import load_stack, prepare_inputs
from .pilot import evaluate
from .smoke import save_json, gpu_memory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path)
    parser.add_argument('--batch-size', type=int, default=8)
    args = parser.parse_args()
    torch.set_num_threads(8)
    if args.run is None:
        candidates = sorted(Path('/workspace/anchor_pilot/outputs').glob('pilot-*/selection_lock.json'))
        args.run = candidates[-1].parent
    report = json.loads((args.run / 'report.json').read_text())
    if report['status'] != 'gpu_execution_complete_analysis_pending':
        raise RuntimeError('The main run did not complete')
    rows = json.loads((args.run / 'rows.json').read_text())
    directions = torch.load(args.run / 'directions.pt', map_location='cpu', weights_only=True)
    start = time.monotonic()
    model, tokenizer, _, _, _, _ = load_stack(False)
    prepared = prepare_inputs(model, tokenizer, rows)
    added = []
    for agent, footprint in report['footprints'].items():
        specs = [(agent + '_mean_delta', footprint['mean_delta_norm'])]
        specs += [(agent + f'_sae_preference_k{k}', info['decoded_norm']) for k, info in footprint['native'].items()]
        for source, magnitude in specs:
            key = source + '_fitted_magnitude'
            entry = directions[source]
            print(f'Original-magnitude replay: {key}; norm={magnitude:.4f}', flush=True)
            records, _ = evaluate(model, prepared, args.batch_size, direction=entry['vector'],
                                  layer=entry['layer'], rho=magnitude)
            save_json(args.run / f'scores_{key}.json', records)
            report['directions'][key] = {**report['directions'][source], 'requested_norm': magnitude,
                                         'source_direction': source, 'scale_family': 'discovery_fitted_magnitude',
                                         'common_norm_comparison': False}
            added.append(key)
    report['condition_count'] += len(added)
    report['fidelity_replay'] = {'conditions': added, 'elapsed_seconds': time.monotonic() - start,
                                 'gpu_memory': gpu_memory(), 'dose_chosen_from': 'discovery footprint only'}
    save_json(args.run / 'report.json', report)


if __name__ == '__main__':
    main()
