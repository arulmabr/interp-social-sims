"""G1 — fetch the paper's model and its SAE to the lab share, then verify them.

    python -m cv_bench.g1_download            # download, then verify
    python -m cv_bench.g1_download --verify   # verify what is already on disk

`FRIDAY_PLAN.md` G1: "Download `meta-llama/Llama-3.3-70B-Instruct` and
`Goodfire/Llama-3.3-70B-Instruct-SAE-l50` to the lab share (approved). Verify shard
count, sizes and hashes against the hub. Load the SAE with `weights_only=True`."

Notes on what this deliberately does *not* do:

* `original/` is skipped. The model repo is 282 GB because it ships the weights
  twice: 30 sharded safetensors (141 GB) and a consolidated `original/*.pth` copy
  of the same parameters (141 GB). Transformers loads the safetensors.
* The token is read from a file, never from argv and never printed. It belongs to
  a different account from the one in `HF_TOKEN`, so it is passed explicitly to
  every call rather than left to environment pickup.
* The SAE is pinned to the revision the legacy runs recorded (V3), so new SAE work
  matches the logged runs exactly.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The lab share, per GATE_S0_RESPONSE §1.2. Set before huggingface_hub is imported,
# because the cache location is resolved at import time.
HF_HOME = Path("/orcd/data/gabrieli/001/guna23/hf_cache")
os.environ.setdefault("HF_HOME", str(HF_HOME))
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

MODEL_REPO = "meta-llama/Llama-3.3-70B-Instruct"
SAE_REPO = "Goodfire/Llama-3.3-70B-Instruct-SAE-l50"
# V3: the revision the logged open-SAE runs used.
SAE_REVISION = "128ee921ecd1b8b3a87d776cbcc357c0855da134"
SAE_FILE = "Llama-3.3-70B-Instruct-SAE-l50.pt"

# Amendment 5 (22 Sept): the token lives outside the repository. The in-repo copy
# and HF_TOKEN remain as fallbacks so nothing breaks while the move happens.
TOKEN_PATHS = [Path.home() / ".hf_token", ROOT / "hf_token.txt"]

# Weights, config, tokenizer. Not the duplicate consolidated copy.
MODEL_ALLOW = ["*.safetensors", "*.safetensors.index.json", "config.json",
               "generation_config.json", "tokenizer*", "special_tokens_map.json"]
MODEL_IGNORE = ["original/*"]


def token() -> str:
    for p in TOKEN_PATHS:
        if p.exists():
            t = p.read_text().strip()
            if t:
                print(f"token source: {p}", flush=True)
                return t
    t = os.environ.get("HF_TOKEN")
    if not t:
        sys.exit("No token: expected ~/.hf_token, hf_token.txt, or HF_TOKEN")
    print("token source: HF_TOKEN environment variable", flush=True)
    return t


def download(tok: str) -> None:
    from huggingface_hub import snapshot_download
    print(f"HF_HOME = {os.environ['HF_HOME']}", flush=True)

    print(f"[1/2] {SAE_REPO} @ {SAE_REVISION[:12]}", flush=True)
    p = snapshot_download(SAE_REPO, revision=SAE_REVISION, token=tok,
                          allow_patterns=[SAE_FILE, "*.json"], max_workers=4)
    print(f"      -> {p}", flush=True)

    print(f"[2/2] {MODEL_REPO}  (~141 GB, skipping original/)", flush=True)
    p = snapshot_download(MODEL_REPO, token=tok, allow_patterns=MODEL_ALLOW,
                          ignore_patterns=MODEL_IGNORE, max_workers=4)
    print(f"      -> {p}", flush=True)


def verify(tok: str) -> dict:
    """Shard count, per-file size and sha256 against the hub; then load the SAE."""
    from huggingface_hub import HfApi, snapshot_download
    api = HfApi()
    out: dict = {"hf_home": os.environ["HF_HOME"]}

    for tag, repo, rev, allow, ignore in (
        ("sae", SAE_REPO, SAE_REVISION, [SAE_FILE, "*.json"], None),
        ("model", MODEL_REPO, None, MODEL_ALLOW, MODEL_IGNORE),
    ):
        local = Path(snapshot_download(repo, revision=rev, token=tok,
                                       allow_patterns=allow, ignore_patterns=ignore,
                                       local_files_only=True, max_workers=4))
        info = api.model_info(repo, revision=rev, token=tok, files_metadata=True)
        want = {}
        for s in info.siblings:
            f = s.rfilename
            if ignore and any(f.startswith(g.rstrip("*")) for g in ignore):
                continue
            import fnmatch
            if not any(fnmatch.fnmatch(f, pat) for pat in allow):
                continue
            sha = getattr(getattr(s, "lfs", None), "sha256", None)
            want[f] = (s.size, sha)

        missing, wrong_size, checked = [], [], 0
        for f, (size, _sha) in want.items():
            lp = local / f
            if not lp.exists():
                missing.append(f)
            elif size is not None and lp.stat().st_size != size:
                wrong_size.append((f, lp.stat().st_size, size))
            else:
                checked += 1
        out[tag] = dict(
            repo=repo, revision=info.sha, local=str(local),
            files_expected=len(want), files_present=checked,
            shards=sum(1 for f in want if f.endswith(".safetensors")),
            missing=missing, wrong_size=wrong_size,
            total_gb=round(sum(s or 0 for s, _ in want.values()) / 1e9, 2),
        )
        print(f"{tag}: {checked}/{len(want)} files, "
              f"{out[tag]['shards']} shards, {out[tag]['total_gb']} GB, "
              f"missing={len(missing)} wrong_size={len(wrong_size)}", flush=True)

    # hashes: verify a sample of shards, since sha256 over 141 GB is slow
    import hashlib
    sample = sorted(Path(out["model"]["local"]).glob("*.safetensors"))[:2]
    info = api.model_info(MODEL_REPO, token=tok, files_metadata=True)
    hub_sha = {s.rfilename: getattr(getattr(s, "lfs", None), "sha256", None)
               for s in info.siblings}
    hashes = []
    for f in sample:
        h = hashlib.sha256()
        with open(f, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 24), b""):
                h.update(chunk)
        ok = (hub_sha.get(f.name) == h.hexdigest())
        hashes.append({"file": f.name, "sha256_matches_hub": ok})
        print(f"sha256 {f.name}: {'OK' if ok else 'MISMATCH'}", flush=True)
    out["sampled_hashes"] = hashes

    # CLAUDE rule / gate rule 15: .pt files are pickles.
    try:
        import torch
        sae_file = Path(out["sae"]["local"]) / SAE_FILE
        sd = torch.load(sae_file, map_location="cpu", weights_only=True)
        keys = list(sd.keys()) if hasattr(sd, "keys") else []
        shapes = {k: list(getattr(sd[k], "shape", [])) for k in keys[:8]}
        out["sae_load"] = dict(weights_only=True, ok=True, n_tensors=len(keys),
                               shapes=shapes)
        print(f"SAE loaded with weights_only=True: {len(keys)} tensors", flush=True)
        for k, v in shapes.items():
            print(f"   {k}: {v}", flush=True)
    except Exception as e:
        out["sae_load"] = dict(weights_only=True, ok=False, error=f"{type(e).__name__}: {e}")
        print(f"SAE load FAILED: {type(e).__name__}: {e}", flush=True)

    tgt = ROOT / "results/S/g1_download_verification.json"
    tgt.parent.mkdir(parents=True, exist_ok=True)
    tgt.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {tgt.relative_to(ROOT)}", flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="verify only, no download")
    a = ap.parse_args()
    tok = token()
    if not a.verify:
        download(tok)
    verify(tok)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
