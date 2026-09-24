"""B3.2 LoRA anchors (ICLR_PLAN.md B3.2, amendment A5).

Three adapters are trained on identical data, order and schedule:

  reference        theta0 = (alpha 0.88, gamma 0.61, lambda 2.25)
  preference       theta0 with alpha shifted by its minimum detectable change
  bias             theta0 plus an additive logit bias, matched on behavioural
                   effect size -- a weight-space negative control

A5 is the reason there are three and not two: the unmodified model is not a
prospect-theory agent, so "LoRA against base" would mix the known parameter
shift with the model becoming prospect-theoretic at all. **The anchors are the
contrasts against the reference adapter**, where the true difference is exact.

The loss is soft-label cross-entropy over the full vocabulary at the answer
token, with the synthetic agent's choice probabilities placed on the two option
tokens. The ground truth is therefore exact rather than sampled, and the
full-vocabulary normalisation is what keeps valid mass high: every other token
is pushed down at the same time.

Training prompts come from all frames but only from non-test reward levels and
templates; the test split cannot be reached from here at all, because the
generators refuse it.

No anchor is scored with the B2 decision rule until Gate B2 passes (author
item 6). This trains them and checks the cloning.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from functools import lru_cache
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

os.environ.setdefault("HF_HOME", "${HF_HOME}")

import numpy as np
import torch

from cv_bench.estimator import checkpoint as CK
from cv_bench.estimator.agents import (
    ALPHA0, GAMMA0, LAMBDA0, MDC, AgentParams, choice_prob, latent_z_packed, pack)
from cv_bench.tasks import core, risk, social

MODELS = {"llama70b": "meta-llama/Llama-3.3-70B-Instruct",
          "llama8b": "meta-llama/Llama-3.1-8B-Instruct"}
DEFAULT_OUT = Path("${ICLR_RUNROOT}/trackB/b3_lora")
STEM = "Answer:"

#: Provisional temperature for the dry run, until B2-cal returns the fitted one.
#: Not invented: the B2-cal baseline read measured z with SD 4.840 on the real
#: model against 1.690 for the synthetic base at TAU0 = 0.25, so 0.25 x
#: 1.690/4.840 puts the fallback agent on roughly the observed scale. It is a
#: scale match, not a fit, and is overridden by --tau once B2-cal lands.
PROVISIONAL_TAU = 0.0873

def _sha256(p: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


ADAPTERS = ("reference", "preference", "bias")


@lru_cache(maxsize=1)
def social_mdc_value() -> float:
    """The ultimatum MDC (BD55), computed once from the grid geometry."""
    from cv_bench.estimator.social_mdc import social_mdc
    return float(social_mdc()["mdc_beta_adv"])


def agent_for(name: str, tau: float, bias: float,
              pref_mdc_multiple: float = 1.0,
              domain: str = "risk") -> AgentParams:
    """The fallback agent behind each adapter.

    Risk uses Tversky-Kahneman and shifts alpha. Social uses the Fehr-Schmidt
    responder of BD54 and shifts `beta_adv`, the weight on being worse off than
    the proposer. The bias adapter is identical in both, a constant push on the
    latent, so the two negative controls are comparable.
    """
    if domain == "social":
        from cv_bench.estimator.agents import BETA0
        base = AgentParams(tau=tau, beta_adv=BETA0)
        if name == "reference":
            return base
        if name == "preference":
            return replace(base, beta_adv=BETA0 - pref_mdc_multiple * social_mdc_value())
        if name == "bias":
            return replace(base, action=bias)
        raise ValueError(f"unknown adapter {name!r}")
    base = AgentParams(alpha=ALPHA0, gamma=GAMMA0, lam=LAMBDA0, tau=tau)
    if name == "reference":
        return base
    if name == "preference":
        # The MDC itself is unchanged; a multiple > 1 adds a SECOND anchor further
        # from the detection limit so the anchor set brackets a range (author
        # decision, 22 Sept item 3).
        return replace(base, alpha=ALPHA0 + pref_mdc_multiple * MDC["alpha"])
    if name == "bias":
        return replace(base, action=bias)
    raise ValueError(f"unknown adapter {name!r}")


#: Label sets per domain. Social has no "legacy" set, so both of its sets are
#: used; that also gives the format family something to fit, since `par.label`
#: only fires on legacy labels and is inert on social trials.
LABEL_SETS = {"risk": ("legacy",), "social": ("accept_reject", "neutral")}


def _content(splits: Sequence[str], domain: str):
    if domain == "social":
        return list(social.generate_responder(splits=tuple(splits)))
    return list(risk.generate_risk(splits=tuple(splits)))


def _expand(content, domain: str, max_content: Optional[int]):
    if max_content:
        content = sorted(content, key=lambda t: t.content_id)[:max_content]
    out = list(core.expand_formats(content, response_formats=("mc",),
                                   label_sets=LABEL_SETS[domain]))
    return sorted(out, key=lambda t: t.trial_id)


def training_trials(splits: Sequence[str] = ("disc", "cal"),
                    max_content: Optional[int] = None,
                    domain: str = "risk") -> List[core.Trial]:
    """All frames, non-test levels and templates.

    The selection split is held out of training so the cloning check has
    prompts the adapter has not been fitted on.
    """
    return _expand(_content(splits, domain), domain, max_content)


def cloning_trials(max_content: Optional[int] = None,
                   domain: str = "risk") -> List[core.Trial]:
    return _expand(_content(("sel",), domain), domain, max_content)


def soft_targets(trials: Sequence[core.Trial], par: AgentParams) -> np.ndarray:
    """P(risky) for each trial under the agent. Exact, not sampled."""
    return choice_prob(latent_z_packed(pack(trials), par))


def load_base(model_key: str, four_bit: bool = False):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    mid = MODELS[model_key]
    tok = AutoTokenizer.from_pretrained(mid)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    kw = dict(device_map="auto", low_cpu_mem_usage=True)
    if four_bit:
        from transformers import BitsAndBytesConfig
        kw["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4")
    else:
        kw["torch_dtype"] = torch.bfloat16
    model = AutoModelForCausalLM.from_pretrained(mid, **kw)
    return model, tok


def attach_adapters(model, rank: int = 16):
    """One LoRA per anchor on a single loaded base, switched with set_adapter."""
    from peft import LoraConfig, get_peft_model
    cfg = LoraConfig(
        r=rank, lora_alpha=2 * rank, lora_dropout=0.0, bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    )
    peft_model = get_peft_model(model, cfg, adapter_name=ADAPTERS[0])
    for name in ADAPTERS[1:]:
        peft_model.add_adapter(name, cfg)
    return peft_model


def answer_token_ids(ro, trial: core.Trial) -> Tuple[List[int], List[int]]:
    spec = core.to_trial_spec(trial, stem=STEM)
    return ro.label_token_ids(spec.negative), ro.label_token_ids(spec.positive)


def soft_label_loss(logits: torch.Tensor, safe_ids: Sequence[int],
                    risky_ids: Sequence[int], p_risky: float) -> torch.Tensor:
    """Cross-entropy at the answer token against the agent's choice probability.

    The log-softmax is over the whole vocabulary, so probability mass on any
    token that is neither option is penalised; that is what keeps valid mass
    high without a separate term for it. Where a label tokenises to several
    first-token spellings, their probabilities are summed before the log, which
    matches how the readout builds z.
    """
    logprobs = torch.log_softmax(logits.float(), dim=-1)
    p_safe_model = torch.logsumexp(logprobs[safe_ids], dim=0)
    p_risky_model = torch.logsumexp(logprobs[risky_ids], dim=0)
    p = float(np.clip(p_risky, 1e-6, 1 - 1e-6))
    return -(p * p_risky_model + (1.0 - p) * p_safe_model)


def train_adapter(peft_model, tok, ro, name: str, trials: Sequence[core.Trial],
                  targets: np.ndarray, steps: int, lr: float, seed: int,
                  accum: int, out: Path, log_every: int = 25,
                  clone_every: int = 0, clone_trials: Optional[Sequence] = None,
                  clone_agent: Optional[AgentParams] = None,
                  train_probe: Optional[Sequence] = None) -> Dict[str, object]:
    """Train one adapter. Identical order and schedule for every adapter (A5)."""
    peft_model.set_adapter(name)
    params = [p for n, p in peft_model.named_parameters()
              if p.requires_grad and name in n]
    if not params:
        params = [p for p in peft_model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=lr)
    # Cosine decay to zero. With a constant learning rate the loss went flat
    # near 0.30 by step 600 while the calibration slope kept swinging between
    # 0.77 and 0.91 -- the adapter was orbiting a solution rather than settling
    # on one, so whether it "passed" depended on which step the probe landed.
    # This is a schedule change, not a change to the objective.
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(steps, 1))

    ck_path = out / f"ckpt_train_{name}.pt"
    start = 0
    if ck_path.exists():
        try:
            state = torch.load(ck_path, map_location="cpu")
            opt.load_state_dict(state["opt"])
            from peft import set_peft_model_state_dict
            set_peft_model_state_dict(peft_model, state["adapter"], adapter_name=name)
            start = int(state["step"])
            print(f"  resuming {name} at step {start}", flush=True)
        except Exception as exc:                     # a bad checkpoint restarts
            print(f"  checkpoint for {name} unusable ({exc}); starting over", flush=True)

    # The same permutation for every adapter: A5 requires identical data order.
    order = np.random.default_rng(seed).permutation(len(trials))
    losses: List[float] = []
    trace: List[Dict[str, object]] = []
    best: Dict[str, object] = {"score": float("inf"), "step": None,
                               "chk": None, "state": None}
    peft_model.train()
    for step in range(start, steps):
        opt.zero_grad(set_to_none=True)
        total = 0.0
        for k in range(accum):
            idx = int(order[(step * accum + k) % len(order)])
            trial = trials[idx]
            spec = core.to_trial_spec(trial, stem=STEM)
            enc = tok(ro.render(spec), return_tensors="pt").to(peft_model.device)
            out_logits = peft_model(**enc, use_cache=False).logits[0, -1, :]
            safe_ids, risky_ids = answer_token_ids(ro, trial)
            if not safe_ids or not risky_ids:
                continue
            loss = soft_label_loss(out_logits, safe_ids, risky_ids,
                                   float(targets[idx])) / accum
            loss.backward()
            total += float(loss.item())
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        opt.step()
        sched.step()
        losses.append(total)
        if (step + 1) % log_every == 0:
            recent = float(np.mean(losses[-log_every:]))
            print(f"  {name} step {step+1}/{steps} loss {recent:.4f}", flush=True)
            CK.heartbeat(out / "heartbeat.json", stage=f"train:{name}",
                         done=step + 1, total=steps, loss=recent)
            from peft import get_peft_model_state_dict
            torch.save({"step": step + 1, "opt": opt.state_dict(),
                        "adapter": get_peft_model_state_dict(
                            peft_model, adapter_name=name)}, ck_path)
        # A cloning check partway through turns one run into a curve: the
        # question is not "did 300 steps work" but "how does the calibration
        # slope move with training", and guessing a step count one run at a
        # time is how the last two attempts were spent.
        if clone_every and clone_trials is not None and (step + 1) % clone_every == 0:
            peft_model.eval()

            def probe(ts):
                with torch.inference_mode():
                    zs = np.array([ro.score(core.to_trial_spec(t, stem=core.stem_for(t))).logit_diff
                                   for t in ts])
                za = latent_z_packed(pack(list(ts)), clone_agent)
                return cloning_check(zs, za), float(zs.std())

            held, held_sd = probe(clone_trials)
            row = {"step": step + 1, "heldout": held, "heldout_z_sd": held_sd}
            msg = (f"  {name} @ {step+1}: held-out r={held['correlation']:.4f} "
                   f"slope={held['slope']:.4f} z_sd={held_sd:.3f}")
            if train_probe is not None:
                # Author item 4: the train-set slope is what separates a
                # generalisation failure from an objective that cannot reach
                # the target scale at all. Train ~1 with held-out < 0.9 is
                # generalisation; both below 0.9 indicts the loss.
                tr, tr_sd = probe(train_probe)
                row["train"] = tr
                row["train_z_sd"] = tr_sd
                msg += f" | train r={tr['correlation']:.4f} slope={tr['slope']:.4f}"
                # The verdict is only meaningful once training has converged.
                # Early on both slopes are low simply because the adapter is
                # under-trained, and calling that "objective suspect" at step
                # 250 reads as a conclusion when it is a starting point.
                gap = tr["slope"] - held["slope"]
                if step + 1 >= steps:
                    msg += ("  -> generalisation gap" if gap > 0.1
                            else "  -> objective suspect" if tr["slope"] < 0.9
                            else "  -> clones")
                else:
                    msg += f"  (train-heldout gap {gap:+.3f}; verdict at step {steps})"
            trace.append(row)
            # Keep the best checkpoint by held-out slope, as item 4 directs.
            # "Best" is closest to 1.0 among probes that clear both criteria;
            # if none clears, the closest to 1.0 overall, so the final report
            # says what the recipe can actually reach.
            from peft import get_peft_model_state_dict
            score = abs(held["slope"] - 1.0) + (0.0 if held["PASS"] else 10.0)
            if score < best["score"]:
                best.update(score=score, step=step + 1, chk=held,
                            state={k: v.detach().cpu().clone() for k, v in
                                   get_peft_model_state_dict(
                                       peft_model, adapter_name=name).items()})
                msg += "  [best so far]"
            print(msg, flush=True)
            peft_model.train()

    peft_model.eval()
    # Restore the selected checkpoint so everything downstream -- the cloning
    # check, the saved adapter, the contrasts -- uses the same weights.
    if best["state"] is not None:
        from peft import set_peft_model_state_dict
        set_peft_model_state_dict(peft_model, best["state"], adapter_name=name)
        print(f"  {name}: selected step {best['step']} "
              f"(held-out slope {best['chk']['slope']:.4f})", flush=True)
    return {"adapter": name, "steps": steps, "trace": trace,
            "selected_step": best["step"],
            "selected_heldout": best["chk"],
            "final_loss": float(np.mean(losses[-25:])) if losses else float("nan")}


@torch.inference_mode()
def read_adapter(peft_model, ro, name: str, trials: Sequence[core.Trial],
                 out: Path) -> np.ndarray:
    """Unbatched z under one adapter (amendment item 5a), resumable."""
    peft_model.set_adapter(name)
    key = CK.items_key([t.trial_id for t in trials])
    part = CK.Partial(out / f"ckpt_read_{name}.npz", len(trials), chunk=50, key=key)
    for i in range(part.n_done, len(trials)):
        res = ro.score(core.to_trial_spec(trials[i], stem=STEM))
        part.append(res.logit_diff)
        if i % 50 == 0:
            CK.heartbeat(out / "heartbeat.json", stage=f"read:{name}",
                         done=i + 1, total=len(trials))
    part.flush()
    return part.column(0)


def cloning_check(z_model: np.ndarray, z_agent: np.ndarray) -> Dict[str, float]:
    """Correlation >= 0.95 and calibration slope in 0.9-1.1 (B3.2).

    The slope regresses the model's z on the agent's z: a clone should track the
    target one-for-one, not merely rank the trials the same way.
    """
    ok = np.isfinite(z_model) & np.isfinite(z_agent)
    if ok.sum() < 10:
        return {"n": int(ok.sum()), "correlation": float("nan"),
                "slope": float("nan"), "PASS": False}
    x, y = z_agent[ok], z_model[ok]
    r = float(np.corrcoef(x, y)[0, 1])
    slope, intercept = np.polyfit(x, y, 1)
    return {"n": int(ok.sum()), "correlation": r, "slope": float(slope),
            "intercept": float(intercept),
            "PASS": bool(r >= 0.95 and 0.9 <= slope <= 1.1)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="llama8b", choices=list(MODELS))
    ap.add_argument("--domain", default="risk", choices=("risk", "social"),
                    help="risk is the lottery (B3.2); social is the ultimatum "
                         "responder with the Fehr-Schmidt agent (B7, BD54)")
    ap.add_argument("--tau", type=float, default=PROVISIONAL_TAU,
                    help="temperature of the fallback agent; B2-cal supplies the real one")
    ap.add_argument("--bias", type=float, default=0.6,
                    help="additive logit bias for the negative-control adapter")
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--steps", type=int, default=400)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--accum", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-content", type=int, default=None)
    ap.add_argument("--clone-content", type=int, default=60)
    ap.add_argument("--clone-every", type=int, default=0,
                    help="run a cloning probe every N steps, to see the slope trajectory")
    ap.add_argument("--clone-probe", type=int, default=60,
                    help="how many selection-split prompts the mid-training probe uses")
    ap.add_argument("--adapters-from", type=Path, default=None,
                    help="load adapter_<name>.pt from this run instead of training. "
                         "Used to re-probe cloning on more rows without retraining "
                         "(BD47: n=240 was the binding constraint, not the adapters).")
    ap.add_argument("--preference-mdc-multiple", type=float, default=1.0,
                    help="the shifted adapter is alpha0 + this many MDC. 1.0 is the "
                         "original anchor at the detection limit; 3.0 is the second "
                         "anchor. The MDC itself never changes.")
    ap.add_argument("--reinit", action="store_true",
                    help="reset the retrained adapter to a fresh LoRA initialisation "
                         "first, so it is trained INDEPENDENTLY rather than continuing "
                         "from loaded weights or from the reference adapter.")
    ap.add_argument("--retrain", default="",
                    help="comma-separated adapters to retrain; the rest are "
                         "loaded from --adapters-from unchanged")
    ap.add_argument("--init-from-reference", action="store_true",
                    help="start the retrained adapter from the REFERENCE adapter's "
                         "weights instead of from scratch. The loss is unchanged; "
                         "only the initialisation is. Two independently initialised "
                         "adapters carry independent cloning residuals that add in "
                         "quadrature, and that sum is the floor the planted shift has "
                         "to clear (BD47). Sharing an initialisation correlates them.")
    ap.add_argument("--four-bit", action="store_true",
                    help="fallback if bf16 does not fit; recorded as a deviation")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(args.seed)
    retrain = [s for s in args.retrain.split(",") if s]

    train = training_trials(max_content=args.max_content, domain=args.domain)
    clone = cloning_trials(max_content=args.clone_content, domain=args.domain)
    print(f"{len(train)} training rows (disc+cal, "
          f"{'/'.join(LABEL_SETS[args.domain])} labels), "
          f"{len(clone)} selection-split rows for the cloning check", flush=True)

    # Everything that can fail on a typo is built BEFORE the 640-second
    # model load, so a wiring mistake costs seconds rather than a GPU hour.

    results: Dict[str, object] = {
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": MODELS[args.model], "rank": args.rank, "steps": args.steps,
        "lr": args.lr, "accum": args.accum, "seed": args.seed,
        "tau": args.tau, "tau_is_provisional": args.tau == PROVISIONAL_TAU,
        "bias": args.bias, "four_bit": bool(args.four_bit),
        "n_train_rows": len(train), "n_clone_rows": len(clone),
        "theta0": {"alpha": ALPHA0, "gamma": GAMMA0, "lambda": LAMBDA0},
        "adapters": {}, "cloning": {}, "contrasts": {},
        "retrained": retrain, "init_from_reference": bool(args.init_from_reference),
        "reinit": bool(args.reinit),
        "preference_mdc_multiple": float(args.preference_mdc_multiple),
    }

    agents = {n: agent_for(n, args.tau, args.bias, args.preference_mdc_multiple,
                           domain=args.domain)
              for n in ADAPTERS}
    targets = {n: soft_targets(train, p) for n, p in agents.items()}

    t0 = datetime.now(timezone.utc)
    model, tok = load_base(args.model, four_bit=args.four_bit)
    peft_model = attach_adapters(model, rank=args.rank)
    from cv_bench.readout import Readout
    ro = Readout(peft_model, tok)
    trainable = sum(p.numel() for p in peft_model.parameters() if p.requires_grad)
    print(f"loaded in {(datetime.now(timezone.utc)-t0).total_seconds():.0f}s; "
          f"{trainable/1e6:.1f}M trainable LoRA params; "
          f"4bit={args.four_bit}", flush=True)

    for n in ADAPTERS:
        # recorded for every adapter, not only the retrained ones: a paired
        # adapter and an independently initialised one carry different contrast
        # noise floors, so which it was must never have to be inferred.
        results["adapters"][n] = {"params": agents[n].as_dict(),
                                  "target_mean_p_risky": float(targets[n].mean()),
                                  "init_from_reference": False}

    if args.adapters_from is not None:
        # Re-probe an existing run's adapters. Nothing is trained, so the
        # adapters are bit-identical to the ones that produced the first result
        # and only the number of clone rows changes.
        from peft import set_peft_model_state_dict
        results["adapters_from"] = str(args.adapters_from)
        for name in ADAPTERS:
            src = args.adapters_from / f"adapter_{name}.pt"
            sd = torch.load(src, map_location="cpu")
            peft_model.set_adapter(name)
            set_peft_model_state_dict(peft_model, sd, adapter_name=name)
            results["adapters"][name]["loaded_from"] = src.name
            results["adapters"][name]["sha256"] = _sha256(src)
            print(f"loaded adapter {name} from {src.name} "
                  f"({len(sd)} tensors)", flush=True)
        for name in retrain:
            from peft import get_peft_model_state_dict
            if args.init_from_reference and name != "reference":
                ref_sd = get_peft_model_state_dict(peft_model, adapter_name="reference")
                peft_model.set_adapter(name)
                set_peft_model_state_dict(peft_model, ref_sd, adapter_name=name)
                print(f"--- retraining {name}, initialised FROM REFERENCE "
                      f"({len(ref_sd)} tensors copied) ---", flush=True)
            elif args.reinit:
                import torch.nn.init as _init
                n_reset = 0
                for mod in peft_model.modules():
                    for attr, zero in (("lora_A", False), ("lora_B", True)):
                        d_ = getattr(mod, attr, None)
                        if d_ is None or name not in d_:
                            continue
                        w = d_[name].weight
                        if zero:
                            _init.zeros_(w)
                        else:
                            _init.kaiming_uniform_(w, a=5 ** 0.5)
                        n_reset += 1
                print(f"--- retraining {name} INDEPENDENTLY, fresh LoRA init "
                      f"({n_reset} matrices reset) ---", flush=True)
            else:
                print(f"--- retraining {name} from its loaded weights ---", flush=True)
            info = train_adapter(peft_model, tok, ro, name, train, targets[name],
                                 args.steps, args.lr, args.seed, args.accum, args.out,
                                 clone_every=args.clone_every,
                                 clone_trials=clone[:args.clone_probe],
                                 clone_agent=agents[name],
                                 train_probe=train[:args.clone_probe])
            results["adapters"][name].update(info)
            results["adapters"][name]["init_from_reference"] = bool(
                args.init_from_reference and name != "reference")
            torch.save(get_peft_model_state_dict(peft_model, adapter_name=name),
                       args.out / f"adapter_{name}.pt")
    else:
        for name in ADAPTERS:
            print(f"--- training {name} ---", flush=True)
            info = train_adapter(peft_model, tok, ro, name, train, targets[name],
                                 args.steps, args.lr, args.seed, args.accum, args.out,
                                 clone_every=args.clone_every,
                                 clone_trials=clone[:args.clone_probe],
                                 clone_agent=agents[name],
                                 train_probe=train[:args.clone_probe])
            results["adapters"][name].update(info)
            from peft import get_peft_model_state_dict
            torch.save(get_peft_model_state_dict(peft_model, adapter_name=name),
                       args.out / f"adapter_{name}.pt")

    z_clone_agent = {n: latent_z_packed(pack(clone), agents[n]) for n in ADAPTERS}
    z_clone_model = {}
    for name in ADAPTERS:
        z_clone_model[name] = read_adapter(peft_model, ro, name, clone, args.out)
        chk = cloning_check(z_clone_model[name], z_clone_agent[name])
        results["cloning"][name] = chk
        # BD47: the effective n depends on how much of the cloning residual is
        # shared within a content item, which cannot be recovered from the
        # model-side reads alone. Persist both sides, the residual and the
        # content id so the intraclass correlation is computable afterwards.
        _zm, _za = z_clone_model[name], z_clone_agent[name]
        _ok = np.isfinite(_zm) & np.isfinite(_za)
        _res = np.full_like(_zm, np.nan, dtype=float)
        if _ok.sum() >= 2:
            _b, _c = np.polyfit(_za[_ok], _zm[_ok], 1)
            _res[_ok] = _zm[_ok] - (_b * _za[_ok] + _c)
        np.savez(args.out / f"residuals_{name}.npz",
                 z_model=_zm, z_agent=_za, residual=_res,
                 content_id=np.array([str(t.content_id) for t in clone]),
                 trial_id=np.array([str(t.trial_id) for t in clone]))
        print(f"cloning {name}: r={chk['correlation']:.4f} "
              f"slope={chk['slope']:.4f} {'PASS' if chk['PASS'] else 'FAIL'}", flush=True)

    # The anchors are the contrasts against the reference adapter (A5).
    for name in ("preference", "bias"):
        d_model = z_clone_model[name] - z_clone_model["reference"]
        d_agent = z_clone_agent[name] - z_clone_agent["reference"]
        ok = np.isfinite(d_model) & np.isfinite(d_agent)
        results["contrasts"][f"{name}_minus_reference"] = {
            "model_mean_dz": float(np.mean(d_model[ok])),
            "agent_mean_dz": float(np.mean(d_agent[ok])),
            "correlation": float(np.corrcoef(d_agent[ok], d_model[ok])[0, 1])
            if ok.sum() > 10 else float("nan"),
            "recovery_ratio": float(np.mean(d_model[ok]) / np.mean(d_agent[ok]))
            if abs(np.mean(d_agent[ok])) > 1e-9 else float("nan"),
        }

    results["all_cloning_pass"] = all(v["PASS"] for v in results["cloning"].values())
    (args.out / "b3_lora.json").write_text(
        json.dumps(results, indent=2, sort_keys=True, default=float) + "\n")
    print("\n" + json.dumps({k: v for k, v in results.items() if k != "adapters"},
                            indent=2, sort_keys=True, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
