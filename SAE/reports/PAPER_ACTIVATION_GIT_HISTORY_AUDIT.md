# Paper Activation Git-History Audit

Generated from `data/processed/paper_activation_git_history_audit.csv`.

This audit searches reachable git history for exact mappings from
historical Goodfire labels to SAE `feature_index` values. The acceptance
rule is strict: the label and index must occur in the same serialized
controller/dictionary object, or in explicit prose of the form
`label (index N)`. Co-located labels and indices in a historical file are
recorded as rejected candidates.

## Scope

- Paper activation rows inspected: 62,340
- Unique old Goodfire labels inspected: 106
- Git roots searched: release_repo, edsl, edsl_goodfire
- Reachable commits searched: 11,664
- Reachable git objects enumerated: 74,493
- Historical text-like blob paths scanned: 23,267
- Exact mapping evidence rows: 264
- Unique old labels with exact feature indices: 5
- Unique exact feature indices: 5
- New exact old labels beyond the current crosswalk: 0

## Result

Git history did not recover any additional exact feature-index
mappings beyond the five already used in the paper activation
crosswalk.

| Old Goodfire label | Feature index | Evidence methods | Historical paths | Example commit |
| --- | ---: | --- | ---: | --- |
| Altruistic and selfless behavior or intentions | 31935 | csv_model_controller, ipynb_output_literal, ipynb_source_ast_dict | 19 | 46fe97f94791 |
| Descriptions of creative unconventional thinking, especially 'thinking outside the box' | 20117 | csv_model_controller, ipynb_output_literal, ipynb_source_ast_dict | 3 | 46fe97f94791 |
| Executing potentially risky operations that require caution | 4237 | csv_model_controller, ipynb_output_literal, ipynb_source_ast_dict, python_ast_dict | 109 | 126fe2ba153c |
| Professional innovation and creative problem-solving | 4992 | csv_model_controller, ipynb_output_literal, ipynb_source_ast_dict | 3 | 46fe97f94791 |
| Willing to take risks or make sacrifices for a goal | 184 | csv_model_controller, ipynb_output_literal, ipynb_source_ast_dict, python_ast_dict | 109 | 126fe2ba153c |

## Rejected Historical Co-Location

These historical blobs contain paper labels and index-like text but no
same-object label/index mapping. They are audit evidence for why nearby
matching is unsafe.

| Source file | Old labels in blob | Example labels | Example commit |
| --- | ---: | --- | --- |
| edsl/creativity_torrance_test.ipynb | 23 | Character decision-making and multi-step action sequences in narratives \| Connecting phrases and transitions when reformulating text \| Descriptions of comfortable outdoor living spaces and backyard amenities \| Descriptions of construction materials and building methods \| Descriptions of creative unconventional thinking, especially 'thinking outside the box' | f158b6b672d2 |
| edsl/old_notebooks/creativity_torrance_test.ipynb | 22 | Connecting phrases and transitions when reformulating text \| Descriptions of construction materials and building methods \| Descriptions of ergonomic grips and comfortable handling features \| Descriptions of mechanical components and how they interact \| Detailed technical explanations and specifications | 7f3c76f6f678 |
| edsl/Goodfire_cooperate_variant.ipynb | 8 | Descriptions of creative unconventional thinking, especially 'thinking outside the box' \| Explanatory text about complex ecological and social systems \| Game theory concepts involving cooperation versus competition \| Professional innovation and creative problem-solving \| Technical setup and configuration states in experimental procedures | f158b6b672d2 |
| edsl_goodfire/edsl_games/Goodfire_cooperate_variant.ipynb | 7 | Detailed character descriptions and intimate interactions in fiction \| Explanatory text about complex ecological and social systems \| Game theory concepts involving cooperation versus competition \| Technical setup and configuration states in experimental procedures \| The assistant is establishing its capabilities and boundaries | 4db80c9006df |
| edsl_goodfire/edsl_games/Goodfire_cooperate_variant.ipynb | 7 | Detailed character descriptions and intimate interactions in fiction \| Explanatory text about complex ecological and social systems \| Game theory concepts involving cooperation versus competition \| Technical setup and configuration states in experimental procedures \| The assistant is establishing its capabilities and boundaries | 2326da6b079e |
| edsl_goodfire/edsl_games/Goodfire_cooperate_variant.ipynb | 6 | Explanatory text about complex ecological and social systems \| Game theory concepts involving cooperation versus competition \| Technical setup and configuration states in experimental procedures \| The assistant is establishing its capabilities and boundaries \| The assistant is providing a list of options | 2326da6b079e |
| release_repo/data/processed/creativity/open_sae_response_only_frequency/open_sae_feature_activations.jsonl | 2 | Descriptions of creative unconventional thinking, especially 'thinking outside the box' \| Professional innovation and creative problem-solving |  |
| release_repo/data/processed/creativity/steering_provenance/steering_features.csv | 2 | Descriptions of creative unconventional thinking, especially 'thinking outside the box' \| Professional innovation and creative problem-solving |  |
| release_repo/docs/STEERING.md | 2 | Descriptions of creative unconventional thinking, especially 'thinking outside the box' \| Professional innovation and creative problem-solving |  |
| release_repo/data/processed/games/ultimatum/open_sae_full/open_sae_feature_activations.jsonl | 1 | Altruistic and selfless behavior or intentions |  |

## Counts

- Commits by root: {'edsl': 7108, 'edsl_goodfire': 4549, 'release_repo': 7}
- Text-like blob paths by root: {'edsl': 14781, 'edsl_goodfire': 7899, 'release_repo': 587}
- Audit rows by root: {'edsl': 24, 'edsl_goodfire': 17, 'release_repo': 233}
- Exact evidence rows by method: {'csv_model_controller': 229, 'ipynb_output_literal': 6, 'ipynb_source_ast_dict': 23, 'python_ast_dict': 6}
