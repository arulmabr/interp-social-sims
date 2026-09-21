"""G2 — the unsteered (lambda = 0) run on the paper's own checkpoints.

    python -m cv_bench.g2_lambda0 --model llama
    python -m cv_bench.g2_lambda0 --model qwen

P1 of `GATE_S0_RESPONSE.md`, with the author amendments of 22 Sept. The legacy
code path is *imported*, never edited: `Probes.models.Wrapped` does the loading and
the generation, `Probes.tasks.prompts` supplies the prompt strings verbatim, and
`Probes.config` supplies the grids, the sampling settings, N and the seeding. The
steering hook is simply never installed, which is what lambda = 0 means.

Three arms per model:

  a  ``legacy``   raw prompt strings, legacy sampling, legacy max_new_tokens (12),
                  legacy N. This is the legacy pipeline with the hook off.
  b  ``chat``     the model's chat template applied, nothing else changed.
  c  ``chat64``   chat template with max_new_tokens = 64. **A departure from the
                  legacy settings**, included because 12 tokens may truncate an
                  answer that begins with a rationale, and V5 showed the coding is
                  sensitive to exactly that.

Every raw generation is saved. Each is coded twice:

  * ``legacy_code``  the legacy rule — the **last** match of the two labels
    (`Probes/tasks/prompts.py`), which is what produced every published probe curve;
  * ``strict_code``  the **first stated** option, with ``no_answer`` and ``unclear``
    as their own categories, never forced into a choice.

The agreement between the two codings per arm is the number V5 says must exist
before any excess result or any "shift in choices" claim enters a patch.

Output: one JSONL per (model, arm, game) under the run directory, written after
every reward level so a preempted job resumes where it stopped.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HF_HOME", "/orcd/data/gabrieli/001/guna23/hf_cache")
RUNDIR = Path(os.environ.get(
    "G2_RUNDIR", "/orcd/data/gabrieli/001/guna23/iclr_risk_2027/g2_lambda0"))

sys.path.insert(0, str(ROOT))

ARMS = {
    # name      apply_chat_template   max_new_tokens   is_legacy
    "legacy": (False, None, True),
    "chat": (True, None, False),
    "chat64": (True, 64, False),
}

LOTTERY_LABELS = ("Risky", "Safe")
ULTIMATUM_LABELS = ("Accept", "Reject")


# ---------------------------------------------------------------------------
# Coding
# ---------------------------------------------------------------------------
def _matches(text: str, labels):
    pat = re.compile(r"\b(%s)\b" % "|".join(labels), re.IGNORECASE)
    return list(pat.finditer(text or ""))


def legacy_code(text: str, game: str):
    """The legacy rule: the LAST match wins. Mirrors Probes/tasks/prompts.py."""
    labels = LOTTERY_LABELS if game == "lottery" else ULTIMATUM_LABELS
    m = _matches(text, labels)
    if not m:
        return -1
    positive = "risky" if game == "lottery" else "accept"
    return 1 if m[-1].group(1).lower() == positive else 0


_JOIN = re.compile(r"\b(or|and|vs\.?|versus|between)\b", re.IGNORECASE)


def strict_code(text: str, game: str) -> str:
    """The first *stated* option, with no-answer and unclear kept separate.

    Categories: "risky"/"safe" (or "accept"/"reject"), "no_answer", "unclear".
    A response that merely restates the menu -- "Safe or Risky", "between Accept
    and Reject" -- is `unclear`, not a choice. Nothing is forced.
    """
    labels = LOTTERY_LABELS if game == "lottery" else ULTIMATUM_LABELS
    t = (text or "").strip()
    if not t:
        return "no_answer"
    m = _matches(t, labels)
    if not m:
        return "no_answer"
    first = m[0]
    # Two different labels close together, joined by or/and/vs -> a restatement.
    for nxt in m[1:]:
        if nxt.group(1).lower() == first.group(1).lower():
            continue
        gap = t[first.end():nxt.start()]
        if len(gap.split()) <= 3 and _JOIN.search(gap):
            return "unclear"
        break
    return first.group(1).lower()


def strict_to_choice(code: str, game: str):
    positive = "risky" if game == "lottery" else "accept"
    negative = "safe" if game == "lottery" else "reject"
    if code == positive:
        return 1
    if code == negative:
        return 0
    return -1


# ---------------------------------------------------------------------------
def build_prompt(raw: str, tokenizer, use_template: bool) -> str:
    if not use_template:
        return raw
    return tokenizer.apply_chat_template(
        [{"role": "user", "content": raw}], tokenize=False, add_generation_prompt=True)


def done_keys(path: Path) -> set:
    if not path.exists():
        return set()
    out = set()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            out.add((r["param_value"], r["agent_id"]))
    return out


def run_game(wrapped, cfg, prompts_mod, model_key: str, arm: str, game: str,
             out_path: Path) -> int:
    use_template, max_new, is_legacy = ARMS[arm]
    dec = cfg.DECODING_DEFAULTS
    if game == "lottery":
        params = (cfg.LOTTERY["reward_grid_tokens"] if model_key == "llama"
                  else cfg.LOTTERY["reward_grid_tokens_qwen"])
        prompt_fn = prompts_mod.lottery_prompt
        n_agents = cfg.LOTTERY["n_agents"]
        seed_base = cfg.SEED["psychometric_llama" if model_key == "llama"
                             else "psychometric_qwen"]
    else:
        params = (cfg.ULTIMATUM["offer_grid_tokens"] if model_key == "llama"
                  else cfg.ULTIMATUM["offer_grid_tokens_qwen"])
        prompt_fn = prompts_mod.ultimatum_prompt
        n_agents = cfg.ULTIMATUM["n_agents"]
        seed_base = cfg.SEED["psychometric_llama" if model_key == "llama"
                             else "psychometric_qwen"]

    mnt = max_new if max_new is not None else dec["max_new_tokens_choice"]
    already = done_keys(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_new = 0
    t0 = time.time()
    for param_idx, p in enumerate(params):
        raw = prompt_fn(p)
        prompt = build_prompt(raw, wrapped.tokenizer, use_template)
        rows = []
        for i in range(1, n_agents + 1):
            if (p, i) in already:
                continue
            seed = cfg.agent_seed(seed_base, param_idx, i)
            res = wrapped.generate(
                prompt,
                max_new_tokens=mnt,
                temperature=dec["temperature_choice"],
                top_p=dec["top_p"],
                seed=seed,
            )
            text = res.text
            sc = strict_code(text, game)
            rows.append(dict(
                model=model_key, arm=arm, game=game,
                param_value=p, agent_id=i, seed=seed,
                lambda_value=0.0,
                max_new_tokens=mnt, temperature=dec["temperature_choice"],
                top_p=dec["top_p"], chat_template=use_template,
                legacy_settings=is_legacy,
                raw_generation=text,
                legacy_code=legacy_code(text, game),
                strict_code=sc,
                strict_choice=strict_to_choice(sc, game),
            ))
        if rows:
            with open(out_path, "a") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")
            n_new += len(rows)
        el = time.time() - t0
        print(f"  [{arm}/{game}] level {param_idx + 1}/{len(params)} "
              f"(value {p}) +{len(rows)} rows, {n_new} new, {el / 60:.1f} min",
              flush=True)
    return n_new


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["llama", "qwen"], required=True)
    ap.add_argument("--arms", default="legacy,chat,chat64")
    ap.add_argument("--games", default="lottery,ultimatum")
    a = ap.parse_args()

    from Probes import config as cfg
    from Probes import models as legacy_models
    from Probes.tasks import prompts as prompts_mod

    mc = cfg.MODELS[a.model]
    print(f"G2  model={a.model}  hf_id={mc.hf_id}", flush=True)
    print(f"HF_HOME={os.environ['HF_HOME']}", flush=True)
    print(f"RUNDIR={RUNDIR}", flush=True)

    t0 = time.time()
    wrapped = legacy_models.load(a.model, dtype="bf16")   # the legacy loader
    print(f"loaded in {(time.time() - t0) / 60:.1f} min", flush=True)
    # lambda = 0: the hook is never installed. Assert it, so the arm is honest.
    assert wrapped._steering_handle is None, "a steering hook is installed"

    meta = dict(
        model_key=a.model, hf_id=mc.hf_id, dtype="bf16",
        hf_home=os.environ["HF_HOME"],
        slurm_job=os.environ.get("SLURM_JOB_ID"),
        node=os.environ.get("SLURMD_NODENAME"),
        arms={k: dict(chat_template=v[0], max_new_tokens=v[1], legacy_settings=v[2])
              for k, v in ARMS.items()},
        legacy_decoding=dict(cfg.DECODING_DEFAULTS),
        started=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    )
    RUNDIR.mkdir(parents=True, exist_ok=True)
    (RUNDIR / f"{a.model}_meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    total = 0
    for arm in a.arms.split(","):
        for game in a.games.split(","):
            out = RUNDIR / f"{a.model}_{arm}_{game}.jsonl"
            print(f"=== {a.model} / {arm} / {game} -> {out.name}", flush=True)
            total += run_game(wrapped, cfg, prompts_mod, a.model, arm, game, out)
    print(f"G2 DONE model={a.model} new_rows={total} "
          f"elapsed={(time.time() - t0) / 60:.1f} min", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
