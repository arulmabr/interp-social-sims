"""S2.2 — the steering hook, with explicit position semantics.

The legacy hook in `Probes/models.py` is ambiguous about what it touches: its
"last 20% with a ramp" logic reads as if it acts during generation, and it does
not, because at `seq_len == 1` its own index arithmetic yields zero positions.
That ambiguity is why the published appendix, the printed sketch and the code
disagree (`reports/STACK_AUDIT.md` §3). This module makes the choice explicit and
testable.

    Intervention(layer, vectors, scale, positions, mode)

* ``layer``      index into ``model.model.layers``
* ``vectors``    one direction ``(d,)`` or several ``(k, d)``; each is unit
                 normalised before use, so ``scale`` alone sets the magnitude
* ``scale``      **in units of the median residual-stream norm at that layer**,
                 measured over calibration prompts with the first token excluded
                 (`median_residual_norm`). A scale of 0.1 means "a tenth of a
                 typical hidden state", which is comparable across layers and
                 models; the legacy lambda was in raw units and is not.
* ``positions``  ``last`` | ``all_prompt`` | ``all`` | ``legacy_ramp``
* ``mode``       ``add`` (default) or ``clamp`` (secondary, for SAE features)

``legacy_ramp`` reproduces `Probes/models.py` exactly — the last 20% of *prompt*
positions with a 0.5 → 1.0 ramp, and nothing during cached decoding — so old
numbers can be regenerated. It is the only mode that is not a clean statement of
intent, and it is named so nobody picks it by accident.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import numpy as np
import torch

POSITION_MODES = ("last", "all_prompt", "all", "legacy_ramp")
INTERVENTION_MODES = ("add", "clamp")

LEGACY_LAST_FRACTION = 0.20
LEGACY_RAMP_LO = 0.5
LEGACY_RAMP_HI = 1.0


@dataclass
class Intervention:
    layer: int
    vectors: np.ndarray
    scale: float = 0.0
    positions: str = "last"
    mode: str = "add"
    norm_unit: Optional[float] = None
    sign: int = 1

    def __post_init__(self):
        if self.positions not in POSITION_MODES:
            raise ValueError(f"positions must be one of {POSITION_MODES}")
        if self.mode not in INTERVENTION_MODES:
            raise ValueError(f"mode must be one of {INTERVENTION_MODES}")
        v = np.asarray(self.vectors, dtype=np.float32)
        if v.ndim == 1:
            v = v[None, :]
        n = np.linalg.norm(v, axis=-1, keepdims=True)
        self.vectors = v / np.clip(n, 1e-12, None)

    @property
    def delta_norm(self) -> float:
        """Magnitude actually added, in residual-stream units."""
        return float(self.scale) * float(self.norm_unit if self.norm_unit else 1.0)

    def describe(self) -> dict:
        return dict(layer=self.layer, n_vectors=int(self.vectors.shape[0]),
                    scale=float(self.scale), positions=self.positions,
                    mode=self.mode, sign=int(self.sign),
                    norm_unit=self.norm_unit, delta_norm=self.delta_norm)


# ---------------------------------------------------------------------------
@torch.inference_mode()
def median_residual_norm(model, tokenizer, prompts: Sequence[str], layer: int,
                         skip_first_token: bool = True) -> float:
    """Median L2 norm of the residual stream entering `layer`, over prompts.

    The first token is excluded by default: on most decoder-only models its
    hidden state is an outlier by an order of magnitude, and including it would
    make `scale` mean something different at every layer.
    """
    norms: List[float] = []
    block = model.model.layers[layer]
    captured: List[torch.Tensor] = []

    def hook(_m, _inp, output):
        captured.append((output[0] if isinstance(output, tuple) else output).detach())
        return output

    h = block.register_forward_hook(hook)
    try:
        for p in prompts:
            captured.clear()
            enc = tokenizer(p, return_tensors="pt").to(model.device)
            model(**enc, use_cache=False)
            if not captured:
                continue
            hs = captured[0][0]
            if skip_first_token and hs.shape[0] > 1:
                hs = hs[1:]
            norms.extend(hs.float().norm(dim=-1).cpu().tolist())
    finally:
        h.remove()
    if not norms:
        raise RuntimeError("no activations captured")
    return float(np.median(norms))


# ---------------------------------------------------------------------------
class SteeringHook:
    """Install `intervention` on a model, as a context manager.

    ``prompt_len`` must be given so the hook can tell prompt positions from
    generated ones. During cached decoding each forward pass carries a single
    position, and the hook counts them.

    ``record`` keeps, per forward pass, the absolute positions it modified, which
    is what the position test asserts against.
    """

    def __init__(self, model, intervention: Intervention, prompt_len: int,
                 record: bool = False):
        self.model = model
        self.iv = intervention
        self.prompt_len = int(prompt_len)
        self.record = record
        self.modified: List[List[int]] = []
        self._handle = None
        self._seen = 0   # positions consumed so far

    # -- position policy ---------------------------------------------------
    def _targets(self, seq_len: int, offset: int) -> tuple:
        """(indices within this pass, per-index gain). Empty means untouched."""
        pos = self.iv.positions
        abs_first = offset
        idx: List[int] = []
        gain: List[float] = []
        if pos == "all":
            idx = list(range(seq_len))
            gain = [1.0] * seq_len
        elif pos == "all_prompt":
            idx = [i for i in range(seq_len) if abs_first + i < self.prompt_len]
            gain = [1.0] * len(idx)
        elif pos == "last":
            idx = [i for i in range(seq_len) if abs_first + i == self.prompt_len - 1]
            gain = [1.0] * len(idx)
        elif pos == "legacy_ramp":
            # Reproduces Probes/models.py: computed from THIS pass's seq_len, so a
            # cached decode step (seq_len == 1) yields n = 0 and touches nothing.
            start = max(1, seq_len - max(1, int(math.ceil(seq_len * LEGACY_LAST_FRACTION))))
            n = seq_len - start
            if n > 0:
                idx = list(range(start, seq_len))
                gain = list(np.linspace(LEGACY_RAMP_LO, LEGACY_RAMP_HI, n))
        return idx, gain

    # -- the hook ----------------------------------------------------------
    def _make_hook(self):
        v = torch.as_tensor(self.iv.vectors, dtype=torch.float32)
        amount = self.iv.delta_norm * float(np.sign(self.iv.sign) or 1)

        def hook(_module, _inp, output):
            is_tuple = isinstance(output, tuple)
            hidden = output[0] if is_tuple else output
            seq_len = hidden.shape[1]
            offset = self._seen
            self._seen += seq_len
            idx, gain = self._targets(seq_len, offset)
            if self.record:
                self.modified.append([offset + i for i in idx])
            if idx and amount != 0.0:
                vv = v.to(hidden.device, hidden.dtype)
                direction = vv.sum(0)              # several vectors add together
                g = torch.tensor(gain, device=hidden.device, dtype=hidden.dtype)
                add = (amount * g)[None, :, None] * direction[None, None, :]
                if self.iv.mode == "add":
                    hidden[:, idx, :] = hidden[:, idx, :] + add
                else:  # clamp: raise the projection onto the direction to at least `amount`
                    unit = direction / torch.clamp(direction.norm(), min=1e-12)
                    proj = (hidden[:, idx, :] * unit).sum(-1, keepdim=True)
                    target = (amount * g)[None, :, None]
                    deficit = torch.clamp(target - proj, min=0)
                    hidden[:, idx, :] = hidden[:, idx, :] + deficit * unit
            return (hidden,) + output[1:] if is_tuple else hidden

        return hook

    def __enter__(self) -> "SteeringHook":
        self._seen = 0
        self.modified = []
        block = self.model.model.layers[self.iv.layer]
        self._handle = block.register_forward_hook(self._make_hook())
        return self

    def __exit__(self, *exc):
        if self._handle is not None:
            self._handle.remove()
            self._handle = None
        return False


def sae_decoder_direction(state_dict, feature_index: int) -> np.ndarray:
    """Unit decoder column for one SAE feature.

    Goodfire's released SAEs store the decoder as ``decoder_linear.weight`` with
    shape (d_model, n_features), so a feature is a *column*. Loaded elsewhere with
    ``torch.load(..., weights_only=True)``: these files are pickles.
    """
    w = state_dict["decoder_linear.weight"]
    col = w[:, feature_index]
    col = col.float().cpu().numpy()
    return col / max(float(np.linalg.norm(col)), 1e-12)
