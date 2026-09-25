"""The pilot bridge, whose one dangerous step is the outcome ordering."""
import pathlib
import numpy as np
import pytest

from cv_bench.anchors.pilot_bridge import _lottery, to_trial
from cv_bench.estimator import agents as A

ROW = {
    "frame": "gain", "template": "original", "probability": 0.18, "stake": 35.0,
    "reward": 13.3, "risky": [[13.3, 0.18], [0.0, 0.82]], "safe": [[35.0, 1.0]],
    "risky_label": "A", "dominant_option": "safe",
}


def test_amount_probability_order_is_not_swapped():
    lot = _lottery([[13.3, 0.18], [0.0, 0.82]])
    assert lot.ev == pytest.approx(13.3 * 0.18)
    assert lot.support == (0.0, 13.3)


def test_risky_label_a_means_the_gamble_is_printed_first():
    assert to_trial(ROW).fmt.option_order == 1
    assert to_trial({**ROW, "risky_label": "B"}).fmt.option_order == 0


def test_canonical_is_safe_then_risky():
    t = to_trial(ROW)
    assert t.canonical[0].is_sure and t.canonical[0].ev == pytest.approx(35.0)
    assert not t.canonical[1].is_sure


def test_dominance_maps_to_the_canonical_index():
    assert to_trial(ROW).dominant == 0
    assert to_trial({**ROW, "dominant_option": "risky"}).dominant == 1
    assert to_trial({**ROW, "dominant_option": None}).dominant is None


def test_the_trial_is_usable_by_the_estimator():
    t = to_trial(ROW)
    z = A.latent_z(t, A.AgentParams(tau=0.1186))
    assert np.isfinite(z)
    assert z < 0            # a 18% shot at 13.3 against a sure 35 is bad


def test_bias_direction_uses_the_peft_safe_layer_path():
    """Regression: `model.model.layers` fails on a PeftModel (B8, and before)."""
    src = pathlib.Path("cv_bench/anchors/bias_direction.py").read_text()
    assert "decoder_layers(model)" in src
    assert "model.model.layers[" not in src
