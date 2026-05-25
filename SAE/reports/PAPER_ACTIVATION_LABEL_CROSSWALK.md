# Paper Activation Label Crosswalk

Generated from `data/processed/paper_activation_label_crosswalk.csv` and `data/processed/steering_feature_label_crosswalk.csv`.

The stable identifier for an SAE feature is `feature_index`. Historical
Goodfire activation logs in the paper-facing CSV often contain only the
hosted Goodfire natural-language label, not the feature index. Those rows
are preserved, but they are not treated as exact Neuronpedia mappings.

## Coverage

- Paper activation rows: 62,340
- Unique old Goodfire labels: 106
- Exact feature-index rows: 3,478
- Old-label-only rows: 58,862
- Exact old labels in the paper CSV: 5
- Exact feature indices in the paper CSV: 5
- Indexed steering/provenance features: 10

Rows with `mapping_status=exact_feature_index_match` have a recovered
`feature_index` from saved Goodfire controller metadata. Rows with
`mapping_status=old_label_only_no_feature_index` retain the old Goodfire
label and activation but should not be described as exact feature identity
matches to Neuronpedia.

A companion source audit is available at
`reports/PAPER_ACTIVATION_INDEX_SEARCH_AUDIT.md`. That audit searches
the release repo plus companion EDSL/Goodfire development checkouts and
keeps the same strict rule: no fuzzy label matching and no co-location
matching across separate notebook cells or JSONL records.
`reports/PAPER_ACTIVATION_GIT_HISTORY_AUDIT.md` extends the same
strict search across reachable git history.

## Exact Paper-CSV Matches

| Feature index | Old Goodfire label | Neuronpedia label |
| ---: | --- | --- |
| 184 | Willing to take risks or make sacrifices for a goal | sacrifice for or at |
| 4237 | Executing potentially risky operations that require caution | before activities or anything |
| 31935 | Altruistic and selfless behavior or intentions | sacrifice and empathy |
| 20117 | Descriptions of creative unconventional thinking, especially 'thinking outside the box' | creative and innovative thinking |
| 4992 | Professional innovation and creative problem-solving | creative in thinking |

## Steering-Provenance Features

The paper activation CSV does not contain every controller feature that was
used for steering. The broader steering crosswalk keeps those indexed
controller features as provenance.

| Feature index | Old Goodfire label | Neuronpedia label |
| ---: | --- | --- |
| 13142 | Enabling or empowering creative expression and exploration | creative acts and originality |
| 20117 | Descriptions of creative unconventional thinking, especially 'thinking outside the box' | creative and innovative thinking |
| 4992 | Professional innovation and creative problem-solving | creative in thinking |
| 184 | Willing to take risks or make sacrifices for a goal | sacrifice for or at |
| 4237 | Executing potentially risky operations that require caution | before activities or anything |
| 31935 | Altruistic and selfless behavior or intentions | sacrifice and empathy |

`13142` is present in saved creativity steering provenance but absent
from the supplied combined paper activation CSV. It is still included
in the steering crosswalk because it is a saved controller feature.

## Source Pattern

Neuronpedia feature descriptions are attached through:

`https://www.neuronpedia.org/api/feature/llama3.3-70b-it/50-resid-post-gf/<feature_index>`

Neuronpedia stores the released description under
`explanations[0].description`; the top-level `label` field may be empty.
