

def test_decoder_layers_sees_through_a_peft_wrapper():
    """The dose solver died on this: `model.model.layers` is right for a bare
    causal LM and wrong through a PeftModel, which puts the causal LM one level
    down. Both must resolve to the SAME list, because PEFT injects into those
    blocks in place."""
    from cv_bench.steer import decoder_layers

    blocks = ["b0", "b1", "b2"]

    class Inner:
        layers = blocks

    class Causal:
        model = Inner()

    class Peft:
        def __init__(self, inner):
            self.base_model = inner

        def get_base_model(self):
            return self.base_model

    bare = Causal()
    assert decoder_layers(bare) is blocks
    assert decoder_layers(Peft(bare)) is blocks


def test_measure_distinguishes_the_two_saturation_directions():
    """The first dose solver matched 2 of 12 because `switching_points`
    returning nothing was collapsed to NaN and read as 'dose too weak'. A ramp
    with no crossing saturates for opposite reasons, and the solver has to tell
    them apart or it walks the scale the wrong way."""
    import numpy as np
    from cv_bench.anchors.probe_vs_anchors import measure

    class T:
        family = "sure_gain"

        def __init__(self, x):
            self.param_dict = {"p": 0.5, "s": 50.0, "x": x}

    trials = [T(x) for x in (30, 80, 130, 180, 230)]
    always_risky = np.full(len(trials), 8.0)     # P ~ 1 everywhere
    always_safe = np.full(len(trials), -8.0)     # P ~ 0 everywhere

    sh, sat = measure(trials, always_risky, 210.0)
    assert np.isnan(sh) and sat == "risky"
    sh, sat = measure(trials, always_safe, 210.0)
    assert np.isnan(sh) and sat == "safe"

    crossing = np.array([-4.0, -2.0, 0.5, 3.0, 5.0])   # crosses between 80 and 130
    sh, sat = measure(trials, crossing, 210.0)
    assert sat is None and sh < 0
