# Archived prompt fixture

`original_prompt_requests.jsonl` contains the first eight input rows from each
baseline/steering condition for lottery reward 100 and ultimatum offer 30.
They were extracted from the repository's existing archived EDSL CSVs under
`SAE/data/raw/games/safe_risky/results_20251008_225522/` and
`SAE/data/raw/games/ultimatum/results_20251008_201139/`.

The 32 records preserve the original system/user messages, generation settings
and controller metadata. They contain no generated answers, new experimental
results, access credentials or full feature-label catalog. Tests use a clearly
marked synthetic runtime and block network connections. This small fixture lets
the tests run from a clean checkout without the private generated plan directory.
