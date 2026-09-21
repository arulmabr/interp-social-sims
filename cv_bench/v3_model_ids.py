"""V3 — which checkpoint each legacy stack names, in code and in its run records.

    python -m cv_bench.v3_model_ids

`FRIDAY_PLAN.md`: "If the legacy probe runs name `Llama-3.1-70B-Instruct`, stop and
tell the authors before anything else." This script answers that, and the open
question at the end of GATE_S0_RESPONSE §1 about the exact id of the Qwen arm.

Read-only. CPU only. No network: nothing here contacts the Hugging Face hub.
"""
from __future__ import annotations

import collections
import csv
import glob
import json
import os
import re
import subprocess
from typing import Dict, List

from .s1_data import BEHAVIOURAL, PROBE_JSON, ROOT, append_manifest, rel, write_csv

SCRIPT = "cv_bench/v3_model_ids.py"
csv.field_size_limit(10_000_000)

# The id that would force a stop, and the family it belongs to.
STOP_IDS = ("Llama-3.1-70B-Instruct", "meta-llama/Llama-3.1-70B-Instruct")

ID_RE = re.compile(r"(?:meta-llama|Qwen|Goodfire|mistralai|google|moonshotai|deepseek-ai)"
                   r"/[A-Za-z0-9._-]+")


def _git(*args) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL)
    except Exception:
        return ""


def scan_code() -> Dict[str, set]:
    """Every model id literal in tracked code, by file."""
    out: Dict[str, set] = collections.defaultdict(set)
    tracked = [f for f in _git("ls-files").splitlines()
               if f.endswith((".py", ".sh", ".json", ".toml", ".txt", ".cfg"))
               and not f.startswith(("cv_bench/", "results/"))]
    for f in tracked:
        p = ROOT / f
        try:
            text = p.read_text(errors="ignore")
        except Exception:
            continue
        for m in ID_RE.findall(text):
            out[f].add(m)
    return out


def scan_history() -> List[str]:
    """Any commit whose content ever mentioned a 3.1 70B."""
    hits = []
    for pat in ("Llama-3.1-70B", "Meta-Llama-3-70B", "Llama-3.2-70B"):
        log = _git("log", "--all", "-S", pat, "--oneline")
        for line in log.splitlines():
            hits.append(f"{pat}: {line}")
    return hits


def main() -> int:
    rows: List[dict] = []
    manifest = []

    # ---- Stack A, hosted Goodfire/EDSL, and Stack B, local vLLM -------------
    seen = collections.Counter()
    for r in csv.DictReader(open(BEHAVIOURAL, newline="")):
        seen[(r["model.inference_service"], r["model.model"], r["game"])] += 1
    for (svc, mid, game), n in sorted(seen.items()):
        stack = "A hosted Goodfire/EDSL" if svc == "goodfire" else "B local vLLM"
        rows.append(dict(
            stack=stack, arm=game, source="run record",
            where="cleaned/behavioral_games_combined.csv :: model.model",
            id_recorded=mid, n_rows=n,
            is_hf_id="yes", revision_pinned="no"))

    # creativity, hosted
    craw = ROOT / "SAE/data/raw/creativity/product_innovation_20251102_202650/baseline.csv"
    if craw.exists():
        row = next(csv.DictReader(open(craw, newline="")))
        rows.append(dict(
            stack="A hosted Goodfire/EDSL", arm="creativity", source="run record",
            where=f"{rel(craw)} :: model.model",
            id_recorded=row.get("model.model", ""), n_rows="",
            is_hf_id="yes", revision_pinned="no"))

    for p in sorted(glob.glob(str(ROOT / "Revised Prompting/runs_fp16/runs/*/run_manifest.json"))):
        j = json.load(open(p))
        rows.append(dict(
            stack="B local vLLM", arm=os.path.basename(os.path.dirname(p)),
            source="run record", where=f"{rel(p)} :: model",
            id_recorded=j.get("model", ""), n_rows=j.get("response_units", ""),
            is_hf_id="yes", revision_pinned="no"))

    # ---- Stack C, local HF probe -------------------------------------------
    import sys
    sys.path.insert(0, str(ROOT))
    from Probes import config

    for key, cfg in (("Llama", config.LLAMA), ("Qwen", config.QWEN)):
        rows.append(dict(
            stack=f"C local HF probe / {key}", arm="code", source="code",
            where="Probes/config.py :: ModelConfig.hf_id",
            id_recorded=cfg.hf_id, n_rows="", is_hf_id="yes", revision_pinned="no"))
        rows.append(dict(
            stack=f"C local HF probe / {key}", arm="code", source="code",
            where="Probes/config.py :: ModelConfig.name (display string)",
            id_recorded=cfg.name, n_rows="", is_hf_id="**no**", revision_pinned="no"))

    d = json.loads(PROBE_JSON.read_text())
    meta_names = collections.Counter()
    row_names = collections.Counter()
    for k, blob in d.items():
        mm = blob.get("metadata", {}).get("model")
        if mm:
            meta_names[mm] += 1
        for r in blob.get("per_agent_rows", []):
            row_names[r.get("model")] += 1
        for r in blob.get("data", []):
            if "model" in r:
                row_names[r["model"]] += 1
    for name, n in sorted(meta_names.items()):
        rows.append(dict(
            stack=f"C local HF probe / {'Llama' if 'Llama' in name else 'Qwen'}",
            arm="figure metadata", source="run record",
            where=f"{rel(PROBE_JSON)} :: metadata.model",
            id_recorded=name, n_rows=f"{n} figure keys",
            is_hf_id="**no** (display name)", revision_pinned="no"))
    for name, n in sorted(row_names.items()):
        if not name:
            continue
        rows.append(dict(
            stack=f"C local HF probe / {'Llama' if 'Llama' in name else 'Qwen'}",
            arm="per-row", source="run record",
            where=f"{rel(PROBE_JSON)} :: row.model",
            id_recorded=name, n_rows=n,
            is_hf_id="**no** (display name)", revision_pinned="no"))

    # ---- Stack D, local open-SAE reruns ------------------------------------
    sae_paths = set()
    for p in sorted(glob.glob(str(ROOT / "SAE/runs/*/open_sae_steering_metadata.json"))):
        j = json.load(open(p))
        rows.append(dict(
            stack="D local open-SAE", arm=os.path.basename(os.path.dirname(p)),
            source="run record", where=f"{rel(p)} :: model_id / sae_repo",
            id_recorded=f"{j.get('model_id')} + {j.get('sae_repo')}",
            n_rows=j.get("generated_response_units", ""),
            is_hf_id="yes",
            revision_pinned="SAE snapshot pinned in sae_path"))
        if j.get("sae_path"):
            sae_paths.add(j["sae_path"])

    write_csv("v3_model_ids.csv", rows)

    # ---- the stop condition -------------------------------------------------
    code = scan_code()
    all_code_ids = sorted({i for v in code.values() for i in v})
    stop_hits = [(f, i) for f, v in code.items() for i in v
                 if any(s in i for s in STOP_IDS)]
    record_hits = [r for r in rows if any(s in str(r["id_recorded"]) for s in STOP_IDS)]
    history = scan_history()

    # Any 3.1 at all, so the report can say what the matches actually are.
    # Bare names too: the repo's only 3.1 string is an un-prefixed SAE filename,
    # which the org/name regex above does not catch.
    any_31 = sorted({i for i in all_code_ids if "3.1" in i})
    bare_31 = []
    for f in sorted(code):
        for ln, line in enumerate((ROOT / f).read_text(errors="ignore").splitlines(), 1):
            for m in re.findall(r"[A-Za-z0-9._-]*Llama-3\.[12][A-Za-z0-9._-]*", line):
                bare_31.append(f"{f}:{ln}: {m}")

    manifest += [
        ("V3.stop_condition.legacy_probe_names_3_1_70B",
         bool(stop_hits or record_hits), SCRIPT,
         ["Probes/config.py", rel(PROBE_JSON)],
         "FRIDAY_PLAN V3 stop condition: does any legacy probe code or run record "
         "name Llama-3.1-70B-Instruct"),
        ("V3.code_model_ids", all_code_ids, SCRIPT, ["(tracked code)"],
         "every model id literal in tracked code outside cv_bench/ and results/"),
        ("V3.any_3_1_ids_in_code", any_31, SCRIPT, ["(tracked code)"],
         "org-prefixed model ids mentioning 3.1 anywhere in tracked code"),
        ("V3.bare_3_1_strings_in_code", sorted(set(bare_31)), SCRIPT, ["(tracked code)"],
         "every un-prefixed Llama-3.1 / 3.2 string literal in tracked code, "
         "file and line"),
        ("V3.history_hits_3_1_70B", history, SCRIPT, ["(git history, --all)"],
         "commits whose content ever added or removed a 3.1/3.2 70B id"),
        ("V3.probe_hf_id.llama", config.LLAMA.hf_id, SCRIPT, ["Probes/config.py"],
         "the only place a Hugging Face id is recorded for the Llama probe arm"),
        ("V3.probe_hf_id.qwen", config.QWEN.hf_id, SCRIPT, ["Probes/config.py"],
         "the only place a Hugging Face id is recorded for the Qwen probe arm"),
        ("V3.sae_snapshot_paths", sorted(sae_paths), SCRIPT,
         ["SAE/runs/*/open_sae_steering_metadata.json"],
         "the SAE checkpoint path recorded by the local open-SAE runs, including "
         "its Hugging Face snapshot revision"),
    ]
    append_manifest(manifest)

    print(f"rows: {len(rows)}")
    print(f"STOP CONDITION (legacy probe names 3.1-70B): {bool(stop_hits or record_hits)}")
    print(f"3.1 org-prefixed ids in code: {any_31}")
    print("bare 3.1 strings in code:")
    for h in sorted(set(bare_31)):
        print("   ", h)
    print(f"history hits: {history or 'none'}")
    print(f"SAE snapshot paths: {sorted(sae_paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
