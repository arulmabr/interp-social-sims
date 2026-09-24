"""The offer-contrast directions must recover a planted offer signal.

No GPU. Activations are built whose only structure is a known direction scaled
by the log of the offer, on the real grid of 19 levels and at the real width of
8,192. Assertions are in multiples of the 1/sqrt(d) null, which is the unit the
panel itself reports, so they do not depend on a hand-picked cosine.
"""
import numpy as np

from cv_bench.g4u import NULL_D, RAND_SEEDS, directions

LABELLED = ("offer_probe", "diffmean", "pca1", "ridge_logn")
NULL = 1.0 / np.sqrt(NULL_D)


def _fixture(d=NULL_D, noise=0.10, seed=0):
    rng = np.random.default_rng(seed)
    offers = np.arange(10, 105, 5, dtype=float)      # the real grid, 19 levels
    planted = rng.normal(size=d)
    planted /= np.linalg.norm(planted)
    X = rng.normal(size=(offers.size, d)) * noise
    X += np.log(offers)[:, None] * planted[None, :]
    return X, offers, planted


def _multiples(v, planted):
    return abs(float(np.dot(v, planted))) / NULL


def test_every_offer_direction_finds_the_planted_direction():
    X, offers, planted = _fixture()
    dirs = directions(X, offers)
    assert dirs.pop("_offer_probe_acc") == 1.0
    for name in LABELLED:
        m = _multiples(dirs[name], planted)
        assert m > 10.0, (name, m)


def test_random_controls_sit_at_the_null():
    X, offers, planted = _fixture()
    dirs = directions(X, offers)
    for name in RAND_SEEDS:
        m = _multiples(dirs[name], planted)
        assert m < 3.0, (name, m)


def test_the_labelled_directions_beat_the_controls_by_an_order_of_magnitude():
    X, offers, planted = _fixture()
    dirs = directions(X, offers)
    dirs.pop("_offer_probe_acc")
    worst = min(_multiples(dirs[n], planted) for n in LABELLED)
    best_null = max(_multiples(dirs[n], planted) for n in RAND_SEEDS)
    assert worst > 5.0 * best_null, (worst, best_null)


def test_random_controls_are_reproducible():
    X, offers, _ = _fixture()
    a, b = directions(X, offers), directions(X, offers)
    for name in RAND_SEEDS:
        assert np.array_equal(a[name], b[name])


def test_every_direction_is_a_unit_vector():
    X, offers, _ = _fixture()
    dirs = directions(X, offers)
    dirs.pop("_offer_probe_acc")
    for name, v in dirs.items():
        assert abs(float(np.linalg.norm(v)) - 1.0) < 1e-6, name
