"""Build an immutable candidate/protocol package, without GPU or API calls."""
import argparse
import collections
import json
from pathlib import Path

from .catalog import QUERIES, import_catalog, search
from .common import MODEL, MODEL_REVISION, SAE, SAE_REVISION, LAYER, digest, file_hash, source_hashes, write
from .design import build_rows


def prepare(csv_path, output, candidates_per_construct=5, calibration_scope='user_content_prompt_max'):
    output = Path(output)
    if output.exists():
        raise FileExistsError('Choose a new plan directory; plans are immutable')
    if not 1 <= candidates_per_construct <= 20:
        raise ValueError('Candidate count must be between 1 and 20')
    if calibration_scope not in ('user_content_prompt_max', 'final_prompt_position'):
        raise ValueError('Unsupported calibration scope')
    output.mkdir(parents=True)
    audit = import_catalog(csv_path, output / 'catalog.sqlite')
    candidates = {k: search(output / 'catalog.sqlite', q, candidates_per_construct) for k, q in QUERIES.items()}
    if any(len(v) < candidates_per_construct for v in candidates.values()):
        raise ValueError('A construct has insufficient retrieval results')
    rows = build_rows()
    for split in ('smoke', 'discovery', 'selection', 'frozen'):
        write(output / f'{split}.json', [r for r in rows if r['split'] == split])
    write(output / 'candidates.json', candidates)
    protocol = {
        'schema': 3, 'model': MODEL, 'model_revision': MODEL_REVISION,
        'sae': SAE, 'sae_revision': SAE_REVISION, 'layer': LAYER,
        'csv_sha256': file_hash(csv_path), 'candidate_method': 'fixed_keyword_bm25',
        'queries': QUERIES, 'candidates_per_construct': candidates_per_construct,
        'precision': 'bf16', 'scope': 'last_token_each_forward_pass',
        'edit': 'relu-clipped additive latent edit; preserve residual reconstruction error',
        'dose_multipliers': [-1.0, -0.5, 0.5, 1.0],
        'calibration_scope': calibration_scope,
        'calibration': ('p95 of positive per-prompt maxima over user-content tokens on discovery prompts; excludes system and special tokens; zero coverage is excluded'
                        if calibration_scope == 'user_content_prompt_max' else
                        'p95 of positive activations at final prompt position on discovery prompts; zero coverage is excluded'),
        'calibration_interpretation': 'Reference feature units; calibration position and intervention position are recorded separately. Negative edits can be zero when the feature is inactive at the intervention site.',
        'random_control': 'fixed random residual unit vector, norm matched to each feature edit per token',
        'selection': 'discovery screen followed by selection split; frozen requires a locked selection file',
        'min_answer_mass': .9, 'max_new_tokens': 192,
        'scientific_status': 'bounded pilot; construct validity requires review; no psychological trait claim',
        'construct_tasks': {'risk': 'lottery', 'altruism': 'ultimatum_responder',
                            'fairness': 'ultimatum_responder', 'creativity': 'uses_and_improvements'},
        'ultimatum_reference': 'iclr2027/sections/appendix_sae.tex; SAE/examples/games/ultimatum.py',
        'ultimatum_design': 'Same neutral accept/reject prompts for altruism and fairness candidate families; discovery 100-token offers 10..90 step 5; selection 80-token stakes; frozen 120/200-token stakes; order and wording counterbalanced.',
        'ultimatum_metrics': {
            'altruism': 'Mean acceptance probability, also reported by offer and below/equal/above-equal strata. This alone does not identify altruism rather than self-interest or efficiency preferences.',
            'fairness': 'Mean rejection probability below equality minus mean rejection probability at equality; paired change from baseline; equal-weight stratum means, stratified scenario bootstrap. Above-equal acceptance curve is a secondary diagnostic.',
        },
        'creativity_scoring': 'external blinded ratings required; no automatic word-count quality proxy',
        'bootstrap_unit': 'economic scenario / object-task family, keeping wording and answer order together',
        'created_from_source': source_hashes(),
    }
    files = {p.name: file_hash(p) for p in sorted(output.glob('*.json'))}
    protocol['input_hashes'] = files
    protocol['plan_hash'] = digest(protocol)
    write(output / 'plan.json', protocol)
    summary = {'plan_hash': protocol['plan_hash'], 'catalog_rows': audit['rows'],
               'candidates': {k: [f['feature_id'] for f in v] for k, v in candidates.items()},
               'prompts_by_split': dict(collections.Counter(r['split'] for r in rows)),
               'new_model_runs': False}
    write(output / 'preparation_summary.json', summary)
    return summary


def load_plan(path):
    from .common import read
    path = Path(path)
    plan = read(path / 'plan.json')
    expected = plan.pop('plan_hash')
    if digest(plan) != expected:
        raise ValueError('Plan hash mismatch')
    plan['plan_hash'] = expected
    for filename, checksum in plan['input_hashes'].items():
        if file_hash(path / filename) != checksum:
            raise ValueError(f'Plan input changed: {filename}')
    return plan


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv', required=True); p.add_argument('--output', required=True)
    p.add_argument('--candidates', type=int, default=5)
    p.add_argument('--calibration-scope', choices=['user_content_prompt_max','final_prompt_position'], default='user_content_prompt_max')
    args = p.parse_args()
    print(json.dumps(prepare(args.csv, args.output, args.candidates, args.calibration_scope), indent=2))


if __name__ == '__main__':
    main()
