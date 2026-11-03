"""SplitMix64: bekannte Werte (Referenzfolge nach Vigna) und die abgeleiteten Zufallsfunktionen."""

import lpl_rng


def test_first_outputs_for_seed_zero_match_the_reference():
    r = lpl_rng.SplitMix64(0)
    assert r.next() == 0xE220A8397B1DCDAF
    assert r.next() == 0x6E789E6AA1B965F4
    assert r.next() == 0x06C45D188009454F


def test_same_seed_same_stream_and_different_seed_differs():
    a, b, c = lpl_rng.SplitMix64(5), lpl_rng.SplitMix64(5), lpl_rng.SplitMix64(6)
    sa, sb, sc = [a.next() for _ in range(5)], [b.next() for _ in range(5)], [c.next() for _ in range(5)]
    assert sa == sb and sa != sc


def test_ranges_are_inclusive_and_cover_every_value():
    r = lpl_rng.SplitMix64(1)
    seen = {r.randint(-2, 2) for _ in range(500)}
    assert seen == {-2, -1, 0, 1, 2}
    assert all(0.0 <= r.random() < 1.0 for _ in range(500))
    assert all(0 <= r.below(7) < 7 for _ in range(500))


def test_shuffle_is_a_permutation_and_reproducible():
    items = list(range(20))
    a, b = items[:], items[:]
    lpl_rng.SplitMix64(9).shuffle(a)
    lpl_rng.SplitMix64(9).shuffle(b)
    assert a == b and sorted(a) == items and a != items


def test_weighted_respects_zero_weights_and_proportions():
    r = lpl_rng.SplitMix64(3)
    draws = [r.weighted(("a", "b", "c"), (6, 0, 3)) for _ in range(900)]
    assert "b" not in draws
    assert 550 < draws.count("a") < 750      # erwartet 600 von 900
