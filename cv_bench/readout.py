"""S2.1 — read a binary choice off the logits instead of off sampled text.

V5 measured why this matters: on the one legacy stack whose raw text survives, the
last-match regex that produced every published probe curve disagrees with the
recorded answer on 34–55% of trials whenever a rationale is present. A logit
readout has no parser and no sampling noise — at a fixed prompt the only
variation left is numerical.

    spec = TrialSpec(prompt=..., labels=("Safe", "Risky"), stem="My choice: ")
    out  = readout.score(spec)
    out.logit_diff     # positive label minus negative label
    out.valid_mass     # probability mass on any spelling of either label

Both tokenisations of every label are checked, with and without a leading space,
because which one a tokenizer produces depends on what precedes it. Per label the
probabilities of its variants are **summed** — that is the probability the answer
begins with that label — and `valid_mass` is the sum over both labels. The raw
per-label logit is the maximum over that label's variants, reported alongside.

`stem=None` selects the legacy EDSL format: no assistant stem is appended and the
first answer token is read where that format expects it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch


@dataclass
class TrialSpec:
    prompt: str
    labels: Tuple[str, str]           # (negative, positive)
    stem: Optional[str] = "My choice: "
    use_chat_template: bool = True
    system: Optional[str] = None

    @property
    def negative(self) -> str:
        return self.labels[0]

    @property
    def positive(self) -> str:
        return self.labels[1]


@dataclass
class ReadoutResult:
    logit: Dict[str, float]
    prob: Dict[str, float]            # renormalised over the two labels
    raw_prob: Dict[str, float]        # un-renormalised, summed over variants
    logit_diff: float
    valid_mass: float
    n_prompt_tokens: int
    token_ids: Dict[str, List[int]] = field(default_factory=dict)


class Readout:
    """A logit readout bound to one model and tokenizer."""

    def __init__(self, model, tokenizer, device: Optional[str] = None):
        self.model = model
        self.tok = tokenizer
        self.device = device or getattr(model, "device", "cpu")
        self._id_cache: Dict[Tuple[str, bool], List[int]] = {}

    # -- tokenisation ------------------------------------------------------
    def label_token_ids(self, label: str, after_space: bool = True,
                        case_variants: bool = True) -> List[int]:
        """First-token ids for a label: case variants, with and without a leading space.

        Four spellings by default — "Safe", " Safe", "safe", " safe" — because
        which one a model emits depends on the stem, and a stem ending in a space
        makes the leading-space spelling unreachable. Distinct ids only: a
        tokenizer that maps several spellings to one first token yields one id,
        which is correct and not an error.
        """
        key = (label, after_space, case_variants)
        if key in self._id_cache:
            return self._id_cache[key]
        forms = [label]
        if case_variants:
            forms += [label.lower(), label.upper(), label.capitalize()]
        variants = []
        for f in dict.fromkeys(forms):
            variants.append(f)
            if after_space:
                variants.append(" " + f)
        ids: List[int] = []
        for v in variants:
            enc = self.tok(v, add_special_tokens=False)["input_ids"]
            if enc:
                ids.append(enc[0])
        out = sorted(set(ids))
        self._id_cache[key] = out
        return out

    # -- prompt assembly ---------------------------------------------------
    def render(self, spec: TrialSpec) -> str:
        if spec.stem is None:
            # Legacy EDSL format: the prompt is fed as-is and the answer token is
            # read immediately after it.
            return spec.prompt
        if not spec.use_chat_template or self.tok.chat_template is None:
            return spec.prompt + "\n" + spec.stem
        msgs = []
        if spec.system:
            msgs.append({"role": "system", "content": spec.system})
        msgs.append({"role": "user", "content": spec.prompt})
        text = self.tok.apply_chat_template(msgs, tokenize=False,
                                            add_generation_prompt=True)
        return text + spec.stem

    # -- scoring -----------------------------------------------------------
    def assert_labels_distinguishable(self, spec: TrialSpec) -> None:
        """The two labels must differ at the token this readout actually scores.

        If their first-token id sets overlap, `logit_diff` is a difference of two
        identical quantities and is identically zero -- and so is every gradient
        taken through it. Nothing in the arithmetic complains: the readout returns
        a clean z = 0 for every prompt, which reads as "no effect" rather than
        "no measurement".

        The failure is easy to walk into. Labels "Option A" and "Option B" under a
        bare stem "Answer:" share their first token, "Option"; the part that
        differs is never scored. The fix is a stem that moves the scored position
        onto the differing part -- "Answer: Option" with labels "A" and "B".

        Reported by the Track B session on 22 Sept; the same check guards its
        gradient anchor (cv_bench/anchors/gradient.py).
        """
        if not spec.negative.strip() or not spec.positive.strip():
            raise ValueError(
                f"labels {spec.negative!r} and {spec.positive!r} have no first-token "
                f"ids worth scoring: a blank label tokenises to whitespace, which is "
                f"not the answer the readout is looking for.")
        neg = set(self.label_token_ids(spec.negative))
        pos = set(self.label_token_ids(spec.positive))
        if not neg or not pos or (neg & pos):
            shared = sorted(neg & pos)
            detail = (f"share first-token ids {shared} "
                      f"({[self.tok.decode([i]) for i in shared[:4]]!r})"
                      if shared else "have no first-token ids at all")
            raise ValueError(
                f"labels {spec.negative!r} and {spec.positive!r} {detail} under "
                f"stem {spec.stem!r}: the readout scores a position where the two "
                f"labels are identical, so logit_diff would be identically zero. "
                f"Move the scored position onto the part that differs, e.g. stem "
                f"'Answer: Option' with labels 'A' and 'B'.")

    def _from_logits(self, logits: torch.Tensor, spec: TrialSpec,
                     n_tokens: int) -> ReadoutResult:
        logits = logits.float()
        logprobs = torch.log_softmax(logits, dim=-1)
        probs = logprobs.exp()
        out_logit, out_raw, ids = {}, {}, {}
        for lab in (spec.negative, spec.positive):
            tid = self.label_token_ids(lab)
            ids[lab] = tid
            out_logit[lab] = float(logits[tid].max().item()) if tid else float("-inf")
            out_raw[lab] = float(probs[tid].sum().item()) if tid else 0.0
        mass = out_raw[spec.negative] + out_raw[spec.positive]
        if mass > 0:
            renorm = {k: v / mass for k, v in out_raw.items()}
        else:
            renorm = {k: float("nan") for k in out_raw}
        eps = 1e-30
        diff = float(np.log(out_raw[spec.positive] + eps)
                     - np.log(out_raw[spec.negative] + eps))
        return ReadoutResult(logit=out_logit, prob=renorm, raw_prob=out_raw,
                             logit_diff=diff, valid_mass=mass,
                             n_prompt_tokens=n_tokens, token_ids=ids)

    @torch.inference_mode()
    def score(self, spec: TrialSpec, intervention=None) -> ReadoutResult:
        self.assert_labels_distinguishable(spec)
        text = self.render(spec)
        enc = self.tok(text, return_tensors="pt").to(self.model.device)
        n = int(enc["input_ids"].shape[1])
        if intervention is None:
            out = self.model(**enc, use_cache=False)
        else:
            from .steer import SteeringHook
            with SteeringHook(self.model, intervention, prompt_len=n):
                out = self.model(**enc, use_cache=False)
        return self._from_logits(out.logits[0, -1, :], spec, n)

    @torch.inference_mode()
    def score_batch(self, specs: Sequence[TrialSpec], intervention=None,
                    batch_size: int = 8) -> List[ReadoutResult]:
        """Left-padded batching with explicit position_ids.

        Left padding shifts every real token's index, so without explicit
        `position_ids` the rotary embeddings are wrong and the batched logits do
        not match the unbatched ones. The plan requires agreement to 1e-2 before
        any batched result is trusted; `cv_bench/tests/test_readout.py` asserts it.
        """
        for spec in specs:
            self.assert_labels_distinguishable(spec)
        results: List[ReadoutResult] = []
        pad_id = self.tok.pad_token_id
        if pad_id is None:
            pad_id = self.tok.eos_token_id
        for i in range(0, len(specs), batch_size):
            chunk = list(specs[i:i + batch_size])
            texts = [self.render(s) for s in chunk]
            encs = [self.tok(t, add_special_tokens=True)["input_ids"] for t in texts]
            width = max(len(e) for e in encs)
            input_ids, attn, pos = [], [], []
            for e in encs:
                pad = width - len(e)
                input_ids.append([pad_id] * pad + e)
                attn.append([0] * pad + [1] * len(e))
                # real tokens numbered from 0; padding parked at 0 and masked out
                pos.append([0] * pad + list(range(len(e))))
            batch = dict(
                input_ids=torch.tensor(input_ids, device=self.model.device),
                attention_mask=torch.tensor(attn, device=self.model.device),
                position_ids=torch.tensor(pos, device=self.model.device),
            )
            if intervention is None:
                out = self.model(**batch, use_cache=False)
            else:
                from .steer import SteeringHook
                with SteeringHook(self.model, intervention, prompt_len=width):
                    out = self.model(**batch, use_cache=False)
            for j, s in enumerate(chunk):
                results.append(self._from_logits(out.logits[j, -1, :], s, len(encs[j])))
        return results

    # -- the checks the plan requires --------------------------------------
    def check_valid_mass(self, specs: Sequence[TrialSpec],
                         threshold: float = 0.98) -> dict:
        """Valid mass over baseline prompts. Below threshold, revise the stem."""
        vals = [self.score(s).valid_mass for s in specs]
        v = np.asarray(vals, dtype=float)
        return dict(n=len(vals), mean=float(v.mean()), min=float(v.min()),
                    median=float(np.median(v)), threshold=threshold,
                    passes=bool(v.min() >= threshold),
                    share_above=float((v >= threshold).mean()))

    def check_batch_agreement(self, specs: Sequence[TrialSpec],
                              tol: float = 1e-2, batch_size: int = 8) -> dict:
        single = [self.score(s).logit_diff for s in specs]
        batched = [r.logit_diff for r in self.score_batch(specs, batch_size=batch_size)]
        d = np.abs(np.asarray(single) - np.asarray(batched))
        return dict(n=len(specs), max_abs_diff=float(d.max()),
                    mean_abs_diff=float(d.mean()), tol=tol,
                    passes=bool(d.max() <= tol))
