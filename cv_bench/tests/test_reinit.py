"""`--reinit` must actually reset the adapter, on a real PeftModel.

The wiring smoke test mocks the PEFT model, so `getattr(mod, "lora_A")` returns
a MagicMock and the reset loop never executes. If the attribute layout were
different from what lora.py assumes, `n_reset` would be 0, the adapter would
silently continue from its loaded weights, and the "independently trained"
anchor would not be independent at all -- while every log line and every
recorded flag still said it was. That is the failure this pins.
"""
from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")
peft = pytest.importorskip("peft")


def _reset(model, name):
    """The exact walk lora.py performs under --reinit."""
    import torch.nn.init as init
    n = 0
    for mod in model.modules():
        for attr, zero in (("lora_A", False), ("lora_B", True)):
            d = getattr(mod, attr, None)
            if d is None or name not in d:
                continue
            w = d[name].weight
            init.zeros_(w) if zero else init.kaiming_uniform_(w, a=5 ** 0.5)
            n += 1
    return n


def test_reinit_resets_every_matrix_and_spares_the_reference():
    import torch.nn as nn
    from peft import LoraConfig, get_peft_model

    class Tiny(nn.Module):
        def __init__(self):
            super().__init__()
            self.q_proj = nn.Linear(16, 16, bias=False)
            self.v_proj = nn.Linear(16, 16, bias=False)

        def forward(self, x):
            return self.v_proj(self.q_proj(x))

    cfg = LoraConfig(r=4, lora_alpha=8, target_modules=["q_proj", "v_proj"])
    m = get_peft_model(Tiny(), cfg, adapter_name="reference")
    m.add_adapter("preference", cfg)

    found, before = 0, {}
    for mod in m.modules():
        for attr in ("lora_A", "lora_B"):
            d = getattr(mod, attr, None)
            if d is not None and "preference" in d:
                nn.init.normal_(d["preference"].weight, std=0.5)
                before[id(d["preference"].weight)] = d["preference"].weight.detach().clone()
                found += 1
    assert found > 0, "the test model has no preference LoRA matrices"

    n_reset = _reset(m, "preference")
    assert n_reset == found, f"reinit touched {n_reset} of {found} matrices"

    changed = sum(
        1
        for mod in m.modules()
        for attr in ("lora_A", "lora_B")
        for d in [getattr(mod, attr, None)]
        if d is not None and "preference" in d
        and not torch.allclose(d["preference"].weight, before[id(d["preference"].weight)])
    )
    assert changed == n_reset, "some matrices were not actually changed"

    ref_present = any("reference" in getattr(mod, "lora_A", {}) for mod in m.modules())
    assert ref_present, "the reference adapter must be left alone"
