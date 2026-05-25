# Approximate Neuronpedia Matches for Old Goodfire Labels

Generated from `data/processed/paper_activation_neuronpedia_approx_matches.csv`.

This table is intentionally approximate. It maps historical Goodfire
natural-language labels that lack recoverable SAE indices to current
Neuronpedia explanation-search candidates for the Goodfire Llama 3.3 70B
SAE source. These rows are semantic label suggestions, not feature
identity claims.

## Method

- Input labels: old Goodfire labels from
  `data/processed/paper_activation_label_crosswalk.csv` with
  `mapping_status=old_label_only_no_feature_index`.
- Search endpoint: `https://www.neuronpedia.org/api/explanation/search`.
- Search model/source: `llama3.3-70b-it` / `50-resid-post-gf`.
- Query: the old Goodfire label string.
- Ranking signal: Neuronpedia explanation-search cosine similarity.
- Stable feature identity remains unavailable unless a `feature_index` is
  recovered from historical metadata.

## Coverage

- Old-label-only Goodfire labels searched: 101
- Approximate candidate rows: 505
- Top-1 confidence buckets: {'high_semantic_similarity': 20, 'low_semantic_similarity': 22, 'medium_semantic_similarity': 59}
- Top-1 labels by paper source: {'lottery': 44, 'product_innovation_folder': 40, 'ultimatum': 36}

## Top-1 Candidate Examples

| Old Goodfire label | Candidate feature | Neuronpedia description | Similarity | Confidence |
| --- | ---: | --- | ---: | --- |
| German compound word components and suffixes | 45100 | German compound words | 0.860 | high_semantic_similarity |
| Non-Latin script characters and text fragments | 26932 | Non-Latin text components | 0.823 | high_semantic_similarity |
| Russian language grammatical connectors and word endings | 6919 | Russian word endings and grammatical suffixes | 0.815 | high_semantic_similarity |
| Common articles and prepositions in explanatory text | 33852 | common articles and prepositions | 0.810 | high_semantic_similarity |
| Descriptions of ergonomic grips and comfortable handling features | 36804 | ergonomic handle or grip | 0.794 | high_semantic_similarity |
| The assistant is asking questions or seeking clarification | 11078 | assistant asks questions | 0.778 | high_semantic_similarity |
| Step-by-step mathematical and logical reasoning | 31113 | step-by-step reasoning | 0.778 | high_semantic_similarity |
| Corrupted or malformed non-Latin text sequences | 5350 | garbled non-latin characters | 0.765 | high_semantic_similarity |
| Financial feasibility analysis and cost-benefit evaluation | 33459 | economic feasibility and costs | 0.763 | high_semantic_similarity |
| Chemical compound name subcomponents and IUPAC nomenclature patterns | 30342 | chemical nomenclature patterns | 0.745 | high_semantic_similarity |
| Modal constructions expressing possibilities and hypotheticals | 59418 | modal verbs for possibility | 0.735 | high_semantic_similarity |
| String literals and special characters in programming contexts | 12633 | special characters and programming terms | 0.733 | high_semantic_similarity |
| Structural delimiters and separators in formatted text | 54640 | structured text separators | 0.730 | high_semantic_similarity |
| Ensuring fairness and equal treatment | 52077 | equality and fairness | 0.723 | high_semantic_similarity |
| Aesthetic qualities and visual appearance | 14580 | qualities of look and design | 0.720 | high_semantic_similarity |
| Technical descriptions of physical components and their relationships | 5950 | technical components and their descriptions | 0.720 | high_semantic_similarity |
| Document structure and formatting syntax | 42 | HTML formatting and structure | 0.720 | high_semantic_similarity |
| Introducing potential risks or possibilities in explanatory contexts | 6786 | This introduces explanation or possibility | 0.717 | high_semantic_similarity |
| Syntactical patterns for value assignment in code | 11739 | assignments and code constructs | 0.710 | high_semantic_similarity |
| Descriptions of mechanical components and how they interact | 5950 | technical components and their descriptions | 0.702 | high_semantic_similarity |

## Interpretation Rule

Use `paper_activation_label_crosswalk.csv` for exact mappings. Use this
approximate table only for human-readable label replacement or appendix
triage. Do not use approximate candidates as evidence that the old
Goodfire activation row and the Neuronpedia feature are the same SAE
feature.
