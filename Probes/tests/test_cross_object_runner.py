"""The cross-object runner, driven end to end with a stub model and judge.

No GPU, no torch: `Probes.models` and `Probes.judge` are replaced before import.
The stub model returns one fixed activation per distinct prompt text, which is
what the real capture does, so any split that put a prompt on both sides would
show up as shared vectors.
"""
import sys
import types

import numpy as np
import pytest


class _Cfg:
    pass


def _install_stubs():
    from Probes import config

    models = types.ModuleType("Probes.models")

    class Wrapped:  # noqa: D401 - stub
        def __init__(self):
            self.cfg = config.LLAMA
            self._vec = {}
            self._rng = np.random.default_rng(0)

        def generate(self, prompt, **kw):
            seed = kw.get("seed", 0)
            # Persona-prefixed prompts produce higher "creativity" on average.
            base = 7.0 if prompt.startswith("You are a highly creative") else 4.0
            return types.SimpleNamespace(text=f"{base + (seed % 5) * 0.3:.2f}")

        def capture_activations(self, prompt, layer):
            if prompt not in self._vec:
                self._vec[prompt] = self._rng.normal(size=32).astype(np.float32)
            return self._vec[prompt].copy()

    models.Wrapped = Wrapped
    sys.modules["Probes.models"] = models

    judge = types.ModuleType("Probes.judge")

    def score_response(text, task=None, judge_name=None):
        return {"creativity_score": float(text)}

    judge.score_response = score_response
    sys.modules["Probes.judge"] = judge
    return Wrapped


@pytest.fixture
def runner():
    saved = {k: sys.modules.get(k) for k in ("Probes.models", "Probes.judge",
                                            "Probes.experiments.cross_object_llama",
                                            "Probes.experiments._common",
                                            "Probes.tasks.preference", "Probes.tasks.capability")}
    for k in saved:
        sys.modules.pop(k, None)
    Wrapped = _install_stubs()
    from Probes.experiments import cross_object_llama as mod
    yield mod, Wrapped
    for k, v in saved.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v


def test_pool_groups_rows_by_distinct_prompt(runner):
    mod, Wrapped = runner
    X, y, g = mod._generate_capability_labeled_pool(Wrapped(), "divergent_creativity", "brick", n_samples=40)
    assert X.shape == (40, 32) and len(y) == 40 and len(g) == 40
    assert set(g) == {0, 1}                        # plain and persona prompt
    for gid in (0, 1):
        rows = X[g == gid]
        assert np.all(rows == rows[0])             # one vector per prompt


def test_every_row_is_prompt_held_out(runner, tmp_path):
    mod, Wrapped = runner
    mod.run(Wrapped(), tmp_path)
    import json
    rows = [json.loads(l) for l in (tmp_path / "cross_object_llama" / "llama_cross_object.jsonl").open()]
    splits = {r["split_type"] for r in rows}
    assert splits == {"in_distribution", "cross_object"}
    for r in rows:
        assert r["prompt_held_out"] is True
        if r["split_type"] == "in_distribution":
            assert r["cv_scheme"] == "leave_one_prompt_out"
            assert r["n_distinct_prompts"] == 2 and r["n_runs"] == 2
            assert 0.0 <= r["label_ceiling"] <= 1.0
        else:
            assert r["n_distinct_prompts_train"] == 6 and r["n_distinct_prompts_test"] == 2


def test_prompt_variants_add_groups(runner):
    mod, Wrapped = runner
    X, y, g = mod._generate_capability_labeled_pool(
        Wrapped(), "divergent_creativity", "brick", n_samples=48,
        prompt_variants=["List uses for a brick.", "Name ways to use a brick.", "What can a brick do?"])
    assert set(g) == set(range(6))                 # 3 wordings x {plain, persona}
