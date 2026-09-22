"""G5b -- the creativity tasks on the local stack, with the logged SAE features.

The paper's capability arms ran on the hosted stack; the probe arms ran locally.
G5b closes that gap for the creativity side, as G5 did for the choice side:
the same two tasks, the same three logged features at the published nudge,
generated locally and saved.

Arms, 40 agents each, on brick (alternative uses) and stapler (product
innovation), the two tasks the paper reports:

  baseline   the task prompt alone
  persona    the paper's persona system prompt
  sae        the three `creativity.high_steering` features at their logged
             nudge of 0.3, by the indices S0 recovered from the controllers
             (13142, 20117, 4992), added at layer 50

Every generation is saved. Scoring is deliberately two separate steps:

  `--phase gen`       GPU, no API, no cost
  `--phase measures`  CPU, the four judge-independent text measures of S1.6
  `--phase judge`     the five judges of V2 under the length-controlled rubric,
                      which needs API credentials and spends money

The split exists so the texts and the judge-independent measures are in hand
whether or not the paid step runs, and so a judging bug never forces a
regeneration.

    python -m cv_bench.g5b --phase gen
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import re

import numpy as np

os.environ.setdefault("HF_HOME", "/orcd/data/gabrieli/001/guna23/hf_cache")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from cv_bench.resume import JsonlSink, install_stop_handler, run_units, complete, mark_done
from cv_bench.s21_fix import MODELS, load
from cv_bench.g5 import load_sae, SAE_LAYER

ROOT = Path(__file__).resolve().parents[1]
RUNROOT = Path(os.environ.get("ICLR_RUNROOT",
                              "/orcd/data/gabrieli/001/guna23/iclr_risk_2027"))
OUT = RUNROOT / "g5b"
LABELS_JSON = ROOT / "results/S/goodfire_labels.json"

N_AGENTS = 40
CAP = 1024                     # DECODING_DEFAULTS["max_new_tokens_capability"]
TEMPERATURE = 0.9              # DECODING_DEFAULTS["temperature_capability"]

TASKS = {
    "brick": ("List very detailed ways you can use a brick. "
              "Each answer should be a paragraph."),
    "stapler": ("Your goal is to improve the stapler. List as many specific "
                "enhancements as you can that would make it better. You may change "
                "features, materials, mechanisms, interfaces, or add/remove parts. "
                "Do not list new uses; stay focused on improvements to the object "
                "itself. For each idea, add enough detail so someone could build or "
                "test it."),
}

# The paper's own persona, as logged. S1.6 established that the creativity
# "prompting" system prompt is the three steered features' labels verbatim, so
# the persona arm and the SAE arm are not independent; that is reported, not
# repaired here.
PERSONA = ("You are a highly creative person who generates original, unusual and "
           "imaginative ideas.")

ARMS = ("baseline", "persona", "sae")

# S1.6's OBJECT_OF is keyed by the legacy task ids, and `.get(task, "object")`
# would silently fall back for a short name -- degrading object_distance without
# saying so. Map explicitly.
TASK_ID = {"brick": "detailed_ways_to_use_a_brick",
           "stapler": "improve_the_stapler_with_many_specific_enhancements"}


def sae_features() -> List[dict]:
    doc = json.loads(LABELS_JSON.read_text())
    return doc["creativity.high_steering"]["features"]


def phase_gen(model_key: str) -> None:
    import torch
    from cv_bench.steer import Intervention, SteeringHook, sae_decoder_direction

    sd = load_sae()
    model, tok = load(model_key, "bf16")
    feats = sae_features()
    print(f"[g5b] features: "
          + ", ".join(f"#{f['index_in_sae']}@{f['value']} {f['label'][:34]!r}"
                      for f in feats), flush=True)

    vecs = [sae_decoder_direction(sd, int(f["index_in_sae"])) for f in feats]
    scales = [float(f["value"]) * float(f.get("max_activation_strength", 1))
              for f in feats]
    total = np.stack([s * w for s, w in zip(scales, vecs)], 0).sum(0)
    mag = float(np.linalg.norm(total))

    sink = JsonlSink(OUT / f"gen_{model_key}.jsonl",
                     key=lambda r: f"{r['task']}|{r['arm']}|{r['agent']}")
    units = [(t, a, i) for t in TASKS for a in ARMS for i in range(1, N_AGENTS + 1)]

    def work(u):
        task, arm, agent = u
        msgs = ([{"role": "system", "content": PERSONA}] if arm == "persona" else [])
        msgs.append({"role": "user", "content": TASKS[task]})
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        enc = tok(text, return_tensors="pt").to(model.device)
        plen = int(enc["input_ids"].shape[1])
        torch.manual_seed(1000 * ARMS.index(arm) + agent)
        iv = (Intervention(layer=SAE_LAYER, vectors=total, scale=mag,
                           positions="all", mode="add", norm_unit=1.0, sign=1)
              if arm == "sae" else None)
        if iv is not None:
            with SteeringHook(model, iv, prompt_len=plen):
                with torch.inference_mode():
                    out = model.generate(**enc, max_new_tokens=CAP, do_sample=True,
                                         temperature=TEMPERATURE, top_p=0.95,
                                         pad_token_id=tok.pad_token_id)
        else:
            with torch.inference_mode():
                out = model.generate(**enc, max_new_tokens=CAP, do_sample=True,
                                     temperature=TEMPERATURE, top_p=0.95,
                                     pad_token_id=tok.pad_token_id)
        gen = tok.decode(out[0, plen:], skip_special_tokens=True)
        return dict(model=model_key, task=task, arm=arm, agent=int(agent),
                    layer=SAE_LAYER if arm == "sae" else None,
                    delta_norm=mag if arm == "sae" else 0.0,
                    temperature=TEMPERATURE, max_new_tokens=CAP,
                    n_chars=len(gen), response_text=gen,
                    features=([dict(index=int(f["index_in_sae"]), uuid=f["uuid"],
                                    label=f["label"], value=float(f["value"]))
                               for f in feats] if arm == "sae" else []))

    install_stop_handler()
    run_units(units, sink, lambda u: f"{u[0]}|{u[1]}|{u[2]}", work, "g5b-gen", 10)
    done = complete(units, sink, lambda u: f"{u[0]}|{u[1]}|{u[2]}")
    sink.close()
    if done:
        mark_done(OUT / f"done_g5b_gen_{model_key}.json", arms=ARMS,
                  tasks=list(TASKS), n_agents=N_AGENTS)


def phase_measures(model_key: str) -> None:
    """S1.6's four judge-independent measures, on G5b's own texts. No API."""
    import re
    from cv_bench.s1_text import (Encoder, split_ideas, OBJECT_OF,
                                  _mean_pairwise_cosine_distance)
    from cv_bench.s1_data import write_csv, append_manifest, rel

    p = OUT / f"gen_{model_key}.jsonl"
    recs = []
    for line in open(p):
        try:
            recs.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not recs:
        print("[g5b] no generations yet")
        return
    enc = Encoder(threads=int(os.environ.get("S1_THREADS", "2")))
    for r in recs:
        assert r["task"] in TASK_ID, f"no legacy task id for {r['task']!r}"
    obj_words = sorted({OBJECT_OF[TASK_ID[r["task"]]] for r in recs})
    obj_vec = {w: v for w, v in zip(obj_words, enc.sentences(obj_words))}

    rows = []
    for n, r in enumerate(recs, 1):
        text = r["response_text"]
        ideas = split_ideas(text)
        words = len(re.findall(r"\b\w+\b", text))
        if ideas:
            iv = enc.sentences(ideas)
            spread = _mean_pairwise_cosine_distance(iv)
            ov = obj_vec[OBJECT_OF[TASK_ID[r["task"]]]]
            obj_dist = float(np.mean(1.0 - iv @ ov))
        else:
            spread = obj_dist = float("nan")
        dsi = _mean_pairwise_cosine_distance(enc.content_tokens(text))
        rows.append(dict(task=r["task"], arm=r["arm"], agent=r["agent"],
                         n_chars=r["n_chars"], n_words=words, n_ideas=len(ideas),
                         category_spread=round(float(spread), 5),
                         object_distance=round(float(obj_dist), 5),
                         dsi_approx=round(float(dsi), 5)))
        if n % 40 == 0:
            print(f"  {n}/{len(recs)}", flush=True)
    write_csv("g5b_measures.csv", rows, list(rows[0]))
    append_manifest([(f"G5b.{t}.{a}.n_ideas_mean",
                      round(float(np.mean([x["n_ideas"] for x in rows
                                           if x["task"] == t and x["arm"] == a])), 3),
                      "mean idea count, judge-independent",
                      [rel(p)], "cv_bench/g5b.py")
                     for t in TASKS for a in ARMS
                     if any(x["task"] == t and x["arm"] == a for x in rows)])
    print(f"[g5b] {len(rows)} texts measured")


def phase_judge(model_key: str, max_usd: float = 50.0) -> None:
    """Score G5b's generations with the judges of V2, under the length-controlled
    rubric of App. A.3.5.

    The rubric and its length-control suffix are imported from `Probes/judge.py`
    rather than retyped, so the wording is the paper's own and cannot drift.

    Credentials are fetched at the moment of use and held only in local
    variables. Nothing in this function prints, logs or stores a key, and a
    provider's raw error body is never echoed -- only a class of failure.

    Judges that have no key are skipped and named in the output, per the
    authors' instruction to run the others and record the gap.
    """
    import sys as _sys
    _sys.path.insert(0, str(ROOT))
    from Probes.judge import (RUBRIC_TEMPLATE, LENGTH_CONTROLLED_SUFFIX,
                              TASK_DESCRIPTIONS)
    from cv_bench.judges import JUDGES, verify_one, _key

    TASK_KIND = {"brick": "divergent_creativity",
                 "stapler": "product_innovation"}

    live, skipped = [], []
    for judge in JUDGES:
        r = verify_one(judge)
        (live if r["status"] == "ok" else skipped).append((judge, r["reason"]))
    print(f"[g5b] judges live: {', '.join(j for j, _ in live)}", flush=True)
    for j, why in skipped:
        print(f"[g5b] judge skipped: {j} ({why})", flush=True)
    if not live:
        print("[g5b] no judge is reachable; nothing scored", flush=True)
        return

    gens = []
    for line in open(OUT / f"gen_{model_key}.jsonl"):
        try:
            gens.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    print(f"[g5b] {len(gens)} generations x {len(live)} judges = "
          f"{len(gens) * len(live)} scoring calls", flush=True)

    sink = JsonlSink(OUT / f"judged_{model_key}.jsonl",
                     key=lambda r: f"{r['task']}|{r['arm']}|{r['agent']}|{r['judge']}")
    units = [(g, j) for g in gens for j, _ in live]

    def work(u):
        g, judge = u
        prompt = RUBRIC_TEMPLATE.format(
            task_description=TASK_DESCRIPTIONS[TASK_KIND[g["task"]]],
            response_text=g["response_text"]) + LENGTH_CONTROLLED_SUFFIX
        ok, scores, why = _call_judge(judge, prompt)
        return dict(model=model_key, task=g["task"], arm=g["arm"],
                    agent=g["agent"], judge=judge,
                    eval_prompt_version="torrance_four_dimension_length_controlled_v1",
                    parse_status=("ok" if ok else "failed"), reason=why,
                    **(scores or {}))

    install_stop_handler()
    run_units(units, sink, lambda u: f"{u[0]['task']}|{u[0]['arm']}|"
                                     f"{u[0]['agent']}|{u[1]}", work, "g5b-judge", 25)
    done = complete(units, sink, lambda u: f"{u[0]['task']}|{u[0]['arm']}|"
                                           f"{u[0]['agent']}|{u[1]}")
    sink.close()
    if done:
        mark_done(OUT / f"done_g5b_judge_{model_key}.json",
                  judges_live=[j for j, _ in live],
                  judges_skipped=[{"judge": j, "reason": w} for j, w in skipped],
                  n_scored=len(units))


def _call_judge(judge: str, prompt: str):
    """One scoring call. Returns (ok, scores, reason_class). Never echoes a key."""
    import urllib.error
    import urllib.request
    from cv_bench.judges import JUDGES, _key, _headers

    filename, provider = JUDGES[judge]
    key = _key(filename)
    if key is None:
        return False, None, "no key"
    if provider == "anthropic":
        url = "https://api.anthropic.com/v1/messages"
        body = dict(model="claude-sonnet-4-5", max_tokens=200,
                    messages=[{"role": "user", "content": prompt}])
    elif provider == "google":
        # gemini-2.0-flash is not served on this key; the models endpoint lists
        # gemini-2.5-flash, which is also the family V2 records as the judge.
        url = ("https://generativelanguage.googleapis.com/v1beta/models/"
               "gemini-2.5-flash:generateContent")
        body = dict(contents=[{"parts": [{"text": prompt}]}])
    else:
        url = {"openai": "https://api.openai.com/v1/chat/completions",
               "deepseek": "https://api.deepseek.com/chat/completions",
               "moonshot": "https://api.moonshot.cn/v1/chat/completions"}[provider]
        body = dict(model={"openai": "gpt-4o-mini", "deepseek": "deepseek-chat",
                           "moonshot": "moonshot-v1-8k"}[provider],
                    max_tokens=200,
                    messages=[{"role": "user", "content": prompt}])
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={**_headers(provider, key), "Content-Type": "application/json"})
    # Gemini rate-limited 216 of its first 240 calls with http 429 while gpt-5
    # and claude-sonnet-4-6 took all 240 without complaint. A 429 is a "come
    # back later", not a failure, so it is retried with growing backoff; every
    # other HTTP status is reported as it is.
    payload = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                payload = json.loads(r.read().decode())
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < 5:
                time.sleep(4 * (2 ** attempt))      # 4, 8, 16, 32, 64 s
                continue
            return False, None, f"http {e.code}"
        except Exception as e:
            if attempt < 2:
                time.sleep(4)
                continue
            return False, None, type(e).__name__
    if payload is None:
        return False, None, "no reply after retries"
    # Pull the assistant's TEXT out of each provider's envelope. Searching
    # json.dumps(payload) instead -- which is what the first version did -- looks
    # for "fluency" in a string where every quote is backslash-escaped, so it
    # matched nothing and reported "no json in reply" for all 480 successful
    # calls.
    try:
        if provider == "anthropic":
            text = "".join(b.get("text", "") for b in payload.get("content", []))
        elif provider == "google":
            cand = payload.get("candidates", [{}])[0]
            text = "".join(pt.get("text", "")
                           for pt in cand.get("content", {}).get("parts", []))
        else:
            text = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return False, None, "unexpected reply shape"
    if not text.strip():
        return False, None, "empty reply"
    m = re.search(r'\{[^{}]*"fluency"[^{}]*\}', text)
    if not m:
        return False, None, "no json in reply"
    try:
        raw = json.loads(m.group(0))
    except json.JSONDecodeError:
        return False, None, "unparseable json"
    out = {}
    for k in ("fluency", "flexibility", "originality", "elaboration"):
        v = raw.get(k)
        if not isinstance(v, int):
            return False, None, "missing field"
        out[k] = max(1, min(10, v))
    out["final_score"] = round(sum(out.values()) / 4.0, 4)
    return True, out, "ok"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama", choices=list(MODELS))
    ap.add_argument("--phase", default="gen",
                    choices=["gen", "measures", "judge"])
    ap.add_argument("--max-usd", type=float, default=50.0,
                    help="standing approval; the phase stops rather than exceed it")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if a.phase == "gen":
        phase_gen(a.model)
    elif a.phase == "judge":
        phase_judge(a.model, a.max_usd)
    else:
        phase_measures(a.model)
    print(f"[g5b] {a.phase} finished in {(time.time()-t0)/60:.1f} min", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
