"""S1.6 — judge-independent measures on the existing creativity texts.

    python -m cv_bench.s1_text

Four measures, none of which consults a judge:
  * idea count            — how many distinct proposals the response contains
  * category spread       — mean pairwise cosine distance among a response's ideas
  * object distance       — mean cosine distance between the object word and each idea
  * DSI-approx            — mean pairwise cosine distance among content-word token
                            embeddings, the operationalisation of Divergent Semantic
                            Integration (Johnson et al. 2022) approximated with a
                            small sentence encoder; labelled approximate throughout

Each is then correlated with each judge's score.

Encoder: sentence-transformers/all-MiniLM-L6-v2, already in the local Hugging Face
cache. 22M parameters, CPU, threads capped. The Ocsai scorer is a hosted service
and is recorded as unavailable offline.
"""
from __future__ import annotations

import collections
import csv
import json
import os
import re
from typing import Dict, List, Sequence

import numpy as np

from .s1_data import CREATIVITY, append_manifest, rel, spearman, write_csv

SCRIPT = "cv_bench/s1_text.py"
MULTI = "torrance_four_dimension_length_controlled_v1"
ENCODER = "sentence-transformers/all-MiniLM-L6-v2"

OBJECT_OF = {
    "detailed_ways_to_use_a_brick": "brick",
    "improve_the_stapler_with_many_specific_enhancements": "stapler",
}

STOP = set("""a an the and or but if then than that this these those of in on at to for with by from
as is are was were be been being it its it's he she they them his her their we you i not no nor so
such can could would should may might must will shall do does did done have has had having there
here what which who whom whose when where why how all any both each few more most other some only
own same too very just also into over under again further once about against between during before
after above below up down out off through""".split())


def _fmt(v):
    return "" if v is None or (isinstance(v, float) and not np.isfinite(v)) else round(float(v), 4)


# ---------------------------------------------------------------------------
# Idea segmentation
# ---------------------------------------------------------------------------
def split_ideas(text: str) -> List[str]:
    """Best-effort split of a response into the distinct proposals it contains.

    The open-SAE creativity prompt asked for a bracketed, comma-separated list of
    at most ten quoted items; the revised-prompting responses are free paragraphs.
    Both shapes are handled, and the fallback is sentence splitting.
    """
    t = (text or "").strip()
    if not t:
        return []
    m = re.search(r"\[(.*)\]", t, re.S)
    if m:
        inner = m.group(1)
        quoted = re.findall(r'"([^"]{3,})"', inner)
        if len(quoted) >= 2:
            return [q.strip() for q in quoted]
    numbered = re.split(r"(?m)^\s*(?:\d+[\.\)]|[-*•])\s+", t)
    numbered = [s.strip() for s in numbered if len(s.strip()) > 20]
    if len(numbered) >= 2:
        return numbered
    paras = [p.strip() for p in re.split(r"\n\s*\n", t) if len(p.strip()) > 20]
    if len(paras) >= 2:
        return paras
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", t) if len(s.strip()) > 20]
    return sents or [t]


# ---------------------------------------------------------------------------
# Encoder
# ---------------------------------------------------------------------------
class Encoder:
    def __init__(self, threads: int = 2):
        import torch
        from transformers import AutoModel, AutoTokenizer
        torch.set_num_threads(threads)
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(ENCODER)
        self.model = AutoModel.from_pretrained(ENCODER)
        self.model.eval()

    def sentences(self, texts: Sequence[str], batch: int = 64) -> np.ndarray:
        torch = self.torch
        out = []
        for i in range(0, len(texts), batch):
            chunk = [t[:2000] for t in texts[i:i + batch]]
            enc = self.tok(chunk, padding=True, truncation=True, max_length=256,
                           return_tensors="pt")
            with torch.no_grad():
                h = self.model(**enc).last_hidden_state
            mask = enc["attention_mask"].unsqueeze(-1).float()
            v = (h * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            v = torch.nn.functional.normalize(v, dim=-1)
            out.append(v.numpy())
        return np.concatenate(out) if out else np.zeros((0, 384), dtype=np.float32)

    def content_tokens(self, text: str, max_tokens: int = 220) -> np.ndarray:
        """Normalised contextual embeddings of the content-word tokens of one text."""
        torch = self.torch
        enc = self.tok(text[:4000], truncation=True, max_length=max_tokens,
                       return_tensors="pt")
        with torch.no_grad():
            h = self.model(**enc).last_hidden_state[0]
        ids = enc["input_ids"][0].tolist()
        toks = self.tok.convert_ids_to_tokens(ids)
        keep = [i for i, tk in enumerate(toks)
                if tk.isalpha() and len(tk) > 2 and tk.lower() not in STOP]
        if len(keep) < 4:
            return np.zeros((0, h.shape[-1]), dtype=np.float32)
        v = torch.nn.functional.normalize(h[keep], dim=-1)
        return v.numpy()


def _mean_pairwise_cosine_distance(v: np.ndarray) -> float:
    if v.shape[0] < 2:
        return float("nan")
    s = v @ v.T
    iu = np.triu_indices(v.shape[0], k=1)
    return float(1.0 - s[iu].mean())


# ---------------------------------------------------------------------------
def load_rows() -> List[dict]:
    out = []
    for r in csv.DictReader(open(CREATIVITY, newline="")):
        if r["eval_prompt_version"] != MULTI:
            continue
        try:
            y = float(r["final_score"])
        except (TypeError, ValueError):
            continue
        out.append(dict(
            resp=f"{r['source_file']}|{r['task']}|{r['condition']}|{r['subject_id']}",
            source_file=r["source_file"], task=r["task"], condition=r["condition"],
            subject_id=r["subject_id"], judge=r["evaluator_model"], score=y,
            text=r["response_text"] or "",
        ))
    return out


def main() -> int:
    rows = load_rows()
    # one record per unique response; judges are folded in afterwards
    texts: Dict[str, dict] = {}
    for r in rows:
        texts.setdefault(r["resp"], dict(resp=r["resp"], source_file=r["source_file"],
                                         task=r["task"], condition=r["condition"],
                                         subject_id=r["subject_id"], text=r["text"]))
    items = sorted(texts.values(), key=lambda d: d["resp"])
    print(f"unique responses: {len(items)}")

    enc = Encoder(threads=int(os.environ.get("S1_THREADS", "2")))
    obj_words = sorted({OBJECT_OF.get(i["task"], "object") for i in items})
    obj_vec = {w: v for w, v in zip(obj_words, enc.sentences(obj_words))}

    measures = []
    for n, it in enumerate(items, 1):
        ideas = split_ideas(it["text"])
        words = len(re.findall(r"\b\w+\b", it["text"]))
        if ideas:
            iv = enc.sentences(ideas)
            spread = _mean_pairwise_cosine_distance(iv)
            ov = obj_vec[OBJECT_OF.get(it["task"], "object")]
            obj_dist = float(np.mean(1.0 - iv @ ov))
        else:
            spread = obj_dist = float("nan")
        dsi = _mean_pairwise_cosine_distance(enc.content_tokens(it["text"]))
        measures.append(dict(
            resp=it["resp"], source_file=it["source_file"], task=it["task"],
            condition=it["condition"], subject_id=it["subject_id"],
            n_words=words, n_ideas=len(ideas),
            category_spread=_fmt(spread), object_distance=_fmt(obj_dist),
            dsi_approx=_fmt(dsi),
        ))
        if n % 200 == 0:
            print(f"  {n}/{len(items)}")
    write_csv("s1_6_text_measures.csv", measures)

    # correlate each measure with each judge, within the open-SAE slice and overall
    mby = {m["resp"]: m for m in measures}
    corr, manifest = [], []
    judges = sorted({r["judge"] for r in rows})
    # Pooling across tasks inflates a correlation whenever the tasks differ in
    # level -- the same trap the published 0.77 Spearman falls into (S1_5 section 4),
    # so every scope below is also computed within each task.
    scopes = [("all_datasets", lambda r: True),
              ("open_sae_creativity", lambda r: r["source_file"] == "open_sae_creativity")]
    for _t in sorted({i["task"] for i in items}):
        scopes.append((f"open_sae|task={_t[:26]}",
                       (lambda t: (lambda r: r["source_file"] == "open_sae_creativity"
                                   and r["task"] == t))(_t)))
    for scope, pred in scopes:
        for measure in ("n_ideas", "n_words", "category_spread", "object_distance", "dsi_approx"):
            for judge in judges + ["MEAN_of_5_judges"]:
                if judge == "MEAN_of_5_judges":
                    agg = collections.defaultdict(list)
                    for r in rows:
                        if pred(r):
                            agg[r["resp"]].append(r["score"])
                    pairs = [(mby[k][measure], float(np.mean(v))) for k, v in agg.items()
                             if mby.get(k) and mby[k][measure] != ""]
                else:
                    pairs = [(mby[r["resp"]][measure], r["score"]) for r in rows
                             if pred(r) and r["judge"] == judge
                             and mby.get(r["resp"]) and mby[r["resp"]][measure] != ""]
                if len(pairs) < 10:
                    continue
                xs = [float(a) for a, _ in pairs]
                ys = [b for _, b in pairs]
                rho = spearman(xs, ys)
                corr.append(dict(scope=scope, measure=measure, judge=judge, n=len(pairs),
                                 spearman=_fmt(rho)))
                if scope == "open_sae_creativity" and judge == "MEAN_of_5_judges":
                    manifest.append((
                        f"S1.6.open_sae.{measure}.vs_mean_judge", _fmt(rho), SCRIPT,
                        [rel(CREATIVITY)],
                        f"Spearman of a judge-independent text measure against the five-judge "
                        f"mean, n={len(pairs)} responses",
                    ))
    write_csv("s1_6_measure_judge_correlations.csv", corr)

    # condition means of each measure, open-SAE slice
    cond_rows = []
    for task in sorted({m["task"] for m in measures}):
        for cond in sorted({m["condition"] for m in measures if m["task"] == task}):
            sel = [m for m in measures if m["task"] == task and m["condition"] == cond
                   and m["source_file"] == "open_sae_creativity"]
            if not sel:
                continue
            rec = dict(task=task, condition=cond, n=len(sel))
            for k in ("n_ideas", "n_words", "category_spread", "object_distance", "dsi_approx"):
                v = [float(m[k]) for m in sel if m[k] != ""]
                rec[f"mean_{k}"] = _fmt(float(np.mean(v))) if v else ""
            cond_rows.append(rec)
    write_csv("s1_6_condition_means.csv", cond_rows)

    append_manifest(manifest + [(
        "S1.6.ocsai_scorer", "unavailable offline", SCRIPT,
        ["Revised Prompting/data/OCSAI_SOURCE.txt"],
        "the repository ships the OCSAI alternate-uses dataset used to build few-shot "
        "exemplars, not the Ocsai scoring model, which is a hosted service; recorded as "
        "unavailable per the plan's instruction",
    )])
    print(f"measures {len(measures)}; correlations {len(corr)}; condition means {len(cond_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
