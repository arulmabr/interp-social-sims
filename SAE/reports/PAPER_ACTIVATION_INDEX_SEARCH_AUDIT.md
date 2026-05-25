# Paper Activation Index Search Audit

Generated from `data/processed/paper_activation_index_search_audit.csv`.

This audit searched the public release repo plus companion EDSL/Goodfire
development checkouts for exact mappings from historical Goodfire labels
to SAE `feature_index` values. A mapping is accepted only when the old
Goodfire label and `index_in_sae` or `feature_index` occur in the same
serialized controller/dictionary object, or in an explicit prose
`label (index N)` source note. Co-located labels and index-like fields
in the same notebook or JSONL file are rejected.

## Scope

- Paper activation rows inspected: 62,340
- Unique old Goodfire labels inspected: 106
- Metadata roots searched: release_repo, edsl, edsl_goodfire
- Text/code files scanned: 18,521
- Candidate files with paper labels and index-like text: 697
- Exact mapping evidence rows: 1,276
- Unique old labels with exact feature indices: 5
- Unique exact feature indices: 5

## Result

The cross-repo search did not recover any additional exact feature-index
mappings beyond the five already used in the paper activation crosswalk.
The old activation logs mostly store only `activation.feature.label` and
`activation.activation`; they do not store the SAE index for each top
paragraph feature.

| Old Goodfire label | Feature index | Evidence methods | Source files |
| --- | ---: | --- | ---: |
| Altruistic and selfless behavior or intentions | 31935 | csv_model_controller, ipynb_source_ast_dict, prose_label_index_pattern | 37 |
| Descriptions of creative unconventional thinking, especially 'thinking outside the box' | 20117 | csv_model_controller, ipynb_output_literal, ipynb_source_ast_dict | 65 |
| Executing potentially risky operations that require caution | 4237 | csv_model_controller, ipynb_source_ast_dict, prose_label_index_pattern, python_ast_dict | 576 |
| Professional innovation and creative problem-solving | 4992 | csv_model_controller, ipynb_output_literal, ipynb_source_ast_dict, prose_label_index_pattern | 22 |
| Willing to take risks or make sacrifices for a goal | 184 | csv_model_controller, ipynb_source_ast_dict, prose_label_index_pattern, python_ast_dict | 576 |

## Rejected Co-Location

Several notebooks contain both old activation labels and controller
indices, but not in the same feature object. Those cases are kept as
`candidate_rejected_no_same_object_mapping` in the audit CSV and are not
used for Neuronpedia identity mapping.

Top rejected candidate files by old-label coverage:

| Source file | Old labels in file | Example labels |
| --- | ---: | --- |
| edsl/old_notebooks/creativity_torrance_test.ipynb | 22 | Connecting phrases and transitions when reformulating text | Descriptions of construction materials and building methods | Descriptions of ergonomic grips and comfortable handling features | Descriptions of mechanical components and how they interact | Detailed technical explanations and specifications |
| release_repo/data/processed/paper_activation_git_history_audit.csv | 18 | Altruistic and selfless behavior or intentions | Character decision-making and multi-step action sequences in narratives | Connecting phrases and transitions when reformulating text | Descriptions of comfortable outdoor living spaces and backyard amenities | Descriptions of construction materials and building methods |
| release_repo/reports/PAPER_ACTIVATION_GIT_HISTORY_AUDIT.md | 18 | Altruistic and selfless behavior or intentions | Character decision-making and multi-step action sequences in narratives | Connecting phrases and transitions when reformulating text | Descriptions of comfortable outdoor living spaces and backyard amenities | Descriptions of construction materials and building methods |
| edsl_goodfire/edsl_games/Goodfire_cooperate_variant.ipynb | 6 | Explanatory text about complex ecological and social systems | Game theory concepts involving cooperation versus competition | Technical setup and configuration states in experimental procedures | The assistant is establishing its capabilities and boundaries | The assistant is providing a list of options |
| release_repo/scripts/audit_paper_activation_git_history.py | 5 | Altruistic and selfless behavior or intentions | Descriptions of creative unconventional thinking, especially 'thinking outside the box' | Executing potentially risky operations that require caution | Professional innovation and creative problem-solving | Willing to take risks or make sacrifices for a goal |
| release_repo/tests/verify_release_artifacts.py | 5 | Altruistic and selfless behavior or intentions | Descriptions of creative unconventional thinking, especially 'thinking outside the box' | Executing potentially risky operations that require caution | Professional innovation and creative problem-solving | Willing to take risks or make sacrifices for a goal |
| edsl/creativity_experiment/creativity_gpt5_open_sae_share_20260523/open_sae_response_only_frequency/open_sae_feature_activations.jsonl | 2 | Descriptions of creative unconventional thinking, especially 'thinking outside the box' | Professional innovation and creative problem-solving |
| edsl/creativity_experiment/product_innovation_20251102_202650_goodfire_open_sae_40agent_features/open_sae_feature_activations.jsonl | 2 | Descriptions of creative unconventional thinking, especially 'thinking outside the box' | Professional innovation and creative problem-solving |
| edsl/creativity_experiment/product_innovation_20251102_202650_goodfire_open_sae_40agent_features_all_content_noncontrol/open_sae_feature_activations.jsonl | 2 | Descriptions of creative unconventional thinking, especially 'thinking outside the box' | Professional innovation and creative problem-solving |
| edsl/creativity_experiment/product_innovation_20251102_202650_goodfire_open_sae_40agent_features_response_only/open_sae_feature_activations.jsonl | 2 | Descriptions of creative unconventional thinking, especially 'thinking outside the box' | Professional innovation and creative problem-solving |
| edsl/creativity_experiment/product_innovation_20251102_202650_goodfire_open_sae_40agent_features_response_only_frequency/open_sae_feature_activations.jsonl | 2 | Descriptions of creative unconventional thinking, especially 'thinking outside the box' | Professional innovation and creative problem-solving |
| edsl/creativity_experiment/product_innovation_20251102_202650_goodfire_open_sae_40agent_features_user_prompt_noncontrol/open_sae_feature_activations.jsonl | 2 | Descriptions of creative unconventional thinking, especially 'thinking outside the box' | Professional innovation and creative problem-solving |

## Evidence Counts

- Audit rows by root: {'edsl': 1011, 'edsl_goodfire': 49, 'release_repo': 236}
- Exact evidence rows by method: {'csv_model_controller': 1251, 'ipynb_output_literal': 2, 'ipynb_source_ast_dict': 15, 'prose_label_index_pattern': 4, 'python_ast_dict': 4}

This is why `feature_index` remains blank for the old-label-only rows in
`data/processed/paper_activation_label_crosswalk.csv`: without the
index stored in the historical activation row or same-object metadata,
the old label alone is not a stable cross-system identifier.
