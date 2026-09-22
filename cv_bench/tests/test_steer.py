

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
