"""Bestückung: Kosten von Hand, Orakel durch Aufzählung, Ungarische Methode gegen Aufzählung, Prüfer, Randfälle."""

import itertools

import pytest

import lpl_bestueck as B
import lpl_constants as C
from lpl_rng import SplitMix64


def make_mini(seed, n=6, t=3, m=4):
    """Kleine Instanz aus Zufall: n Bestückorte, t Typen (jeder mindestens einmal), m Zuführplätze auf einer Reihe unter den Teilen."""
    rng = SplitMix64(seed)
    pos = tuple((float(rng.randint(0, 30)), float(rng.randint(0, 12))) for _ in range(n))
    types = tuple([i % t for i in range(t)] + [rng.below(t) for _ in range(n - t)])
    slots = tuple((4.0 + 6.0 * s, 16.0) for s in range(m))
    return B.FeederInstance(tuple(f"P{i}" for i in range(n)), pos, types, tuple(f"T{i}" for i in range(t)), slots, (0.0, 16.0))


@pytest.fixture
def hand():
    """Zwei Teile bei (10, 2) und (14, 2), Typ 0 und Typ 1, Plätze bei x = 6, 12, 18 auf y = 10, Ausgangsposition (0, 10)."""
    return B.FeederInstance(("A", "B"), ((10.0, 2.0), (14.0, 2.0)), (0, 1), ("T0", "T1"), ((6.0, 10.0), (12.0, 10.0), (18.0, 10.0)), (0.0, 10.0))


def test_distance_is_chebyshev():
    assert B.dist((0, 0), (3, -4)) == 4 and B.dist((1, 1), (1, 1)) == 0


def test_round_cost_by_hand(hand):
    # Typ 0 auf Platz 0 (x = 6), Typ 1 auf Platz 2 (x = 18): holen von links nach rechts 6 + 12 = 18, dann (18,10) -> (10,2): 8, -> (14,2): 4: Summe 30
    cost, end, _ = B.round_route(hand, (0, 2), (0, 1), hand.home)
    assert cost == 30.0 and end == (14.0, 2.0)
    # Gegenrichtung (erst x = 18, dann x = 6) kostet 18 + 12 + 12 = 42 und wird nicht gewählt
    assert B.total_cost(hand, (0, 2), (0, 1), 2) == 30.0 + B.dist((14.0, 2.0), hand.home)       # 44: Rückweg max(14, 8) = 14


def test_single_nozzle_cost_equals_the_plain_tour_formula(hand):
    assignment, seq = (0, 2), (1, 0)
    expected = 0.0
    prev = hand.home
    for j in seq:
        slot = hand.slots[assignment[hand.types[j]]]
        expected += B.dist(prev, slot) + B.dist(slot, hand.positions[j])
        prev = hand.positions[j]
    expected += B.dist(prev, hand.home)
    assert B.total_cost(hand, assignment, seq, 1) == pytest.approx(expected)


def _brute_round(fi, assignment, block, start):
    """Unabhängiger Rechenweg: alle Hol-Reihenfolgen und alle Setz-Reihenfolgen aufzählen (ohne die Geometrie der Geraden auszunutzen)."""
    best = None
    for picks in itertools.permutations(block):
        for places in itertools.permutations(block):
            cur, c = start, 0.0
            for j in picks:
                slot = fi.slots[assignment[fi.types[j]]]
                c += B.dist(cur, slot)
                cur = slot
            for j in places:
                c += B.dist(cur, fi.positions[j])
                cur = fi.positions[j]
            best = c if best is None else min(best, c)
    return best


@pytest.mark.parametrize("seed", range(40))
def test_round_cost_matches_full_enumeration_of_pick_and_place_orders(seed):
    fi = make_mini(seed, n=7, t=4, m=6)
    rng = SplitMix64(seed + 1000)
    assignment = tuple(rng_perm(rng, fi.n_slots)[: fi.n_types])
    k = 1 + seed % 3
    block = tuple(rng_perm(rng, fi.n)[:k])
    start = (float(rng.randint(0, 30)), float(rng.randint(0, 20)))
    assert B.round_route(fi, assignment, block, start)[0] == pytest.approx(_brute_round(fi, assignment, block, start))


def rng_perm(rng, n):
    items = list(range(n))
    rng.shuffle(items)
    return items


def test_hungarian_matches_enumeration_of_all_assignments():
    for seed in range(30):
        rng = SplitMix64(seed)
        t, m = 3 + seed % 2, 5
        cost = [[float(rng.randint(0, 20)) for _ in range(m)] for _ in range(t)]
        got = B.assign_by_matrix(cost)
        best = min(sum(cost[i][p[i]] for i in range(t)) for p in itertools.permutations(range(m), t))
        assert sum(cost[i][got[i]] for i in range(t)) == pytest.approx(best) and len(set(got)) == t


def test_for_a_fixed_sequence_the_single_nozzle_cost_is_linear_in_the_assignment():
    """Die Behauptung des Modells: bei k = 1 und fester Reihenfolge ist die Fahrt eine Summe von Einträgen einer Typ-Platz-Matrix plus dem Rückweg."""
    fi = make_mini(3, n=8, t=4, m=6)
    seq = tuple(rng_perm(SplitMix64(5), fi.n))
    matrix = [[0.0] * fi.n_slots for _ in range(fi.n_types)]
    prev = fi.home
    for j in seq:
        for s in range(fi.n_slots):
            matrix[fi.types[j]][s] += B.dist(prev, fi.slots[s]) + B.dist(fi.slots[s], fi.positions[j])
        prev = fi.positions[j]
    closing = B.dist(prev, fi.home)
    for assignment in itertools.permutations(range(fi.n_slots), fi.n_types):
        assert B.total_cost(fi, assignment, seq, 1) == pytest.approx(sum(matrix[t][assignment[t]] for t in range(fi.n_types)) + closing)
    best = min(itertools.permutations(range(fi.n_slots), fi.n_types), key=lambda a: B.total_cost(fi, a, seq, 1))
    assert B.total_cost(fi, B.assignment_given_sequence_k1(fi, seq), seq, 1) == pytest.approx(B.total_cost(fi, best, seq, 1))


@pytest.mark.parametrize("k,joint_hits", [(1, 10), (2, 8)])
def test_methods_against_the_enumeration_of_all_assignments_and_sequences(k, joint_hits):
    hits = [0, 0, 0, 0]
    for seed in range(10):
        fi = make_mini(seed)
        cache = B.RoundCache(fi)
        optimum = min(B.total_cost(fi, a, s, k, cache) for a in itertools.permutations(range(fi.n_slots), fi.n_types) for s in itertools.permutations(range(fi.n)))
        plans = B.solve_all(fi, k, seed)
        assert all(p.cost >= optimum - 1e-9 for p in plans)             # kein Verfahren unterschreitet das Optimum
        assert all(B.check_plan(fi, p, k) == [] for p in plans)
        for i, p in enumerate(plans):
            hits[i] += p.cost <= optimum + 1e-9
    assert hits[3] == joint_hits                                         # gemeinsames Annealing trifft das Optimum auf (fast) allen Mini-Instanzen
    assert max(hits[:3]) <= hits[3] and hits[0] == 0                    # die anderen Verfahren seltener oder gleich oft; die Maschinenpraxis nie


def test_search_never_returns_something_worse_than_its_start():
    fi = make_mini(4, n=10, t=4, m=7)
    cache = B.RoundCache(fi)
    a = B.centroid_assignment(fi)
    start = B.greedy_rounds(fi, a, 2)
    seq, cost = B.sequence_search(fi, a, start, 2, 800, SplitMix64(1), cache)
    assert cost <= B.total_cost(fi, a, start, 2, cache) + 1e-9 and sorted(seq) == list(range(fi.n))
    a2, c2, evals = B.slot_descent(fi, a, seq, 2, cache)
    assert c2 <= cost + 1e-9 and evals >= 1 and len(set(a2)) == fi.n_types


def test_frequency_assignment_puts_the_most_frequent_type_in_the_middle():
    fi = B.FeederInstance(tuple("abcdef"), ((0, 0),) * 6, (0, 0, 0, 1, 1, 2), ("A", "B", "C"), tuple((float(s), 5.0) for s in range(5)), (0.0, 5.0))
    a = B.frequency_assignment(fi)
    assert a[0] == 2 and {a[1], a[2]} == {1, 3} and len(set(a)) == 3        # Typ A (3 Teile) auf die Mitte, B und C daneben


def test_greedy_rounds_is_a_permutation_with_nearest_first():
    fi = B.FeederInstance(tuple("abcd"), ((1.0, 1.0), (30.0, 1.0), (2.0, 1.0), (31.0, 1.0)), (0, 0, 0, 0), ("T",), ((5.0, 9.0), (6.0, 9.0)), (0.0, 9.0))
    seq = B.greedy_rounds(fi, (0,), 2)
    assert sorted(seq) == [0, 1, 2, 3] and set(seq[:2]) == {0, 2}          # erst die beiden nahen Teile, dann die fernen


def test_mirroring_the_board_leaves_the_cost_unchanged():
    fi = make_mini(7, n=8, t=4, m=6)
    width = 40.0
    mirrored = B.FeederInstance(fi.names, tuple((width - x, y) for x, y in fi.positions), fi.types, fi.type_names, tuple((width - x, y) for x, y in fi.slots), (width - fi.home[0], fi.home[1]))
    a, seq = (1, 0, 3, 2), tuple(range(8))
    for k in (1, 2, 3):
        assert B.total_cost(fi, a, seq, k) == pytest.approx(B.total_cost(mirrored, a, seq, k))


def test_check_plan_finds_each_violation(hand):
    good = B.FeederPlan("x", (0, 2), (0, 1), B.total_cost(hand, (0, 2), (0, 1), 2), 1)
    assert B.check_plan(hand, good, 2) == []
    import dataclasses

    assert any("demselben Zuführplatz" in e for e in B.check_plan(hand, dataclasses.replace(good, assignment=(1, 1)), 2))
    assert any("Zuordnung ungültig" in e for e in B.check_plan(hand, dataclasses.replace(good, assignment=(0, 9)), 2))
    assert any("genau einmal" in e for e in B.check_plan(hand, dataclasses.replace(good, sequence=(0, 0)), 2))
    assert any("Kosten" in e for e in B.check_plan(hand, dataclasses.replace(good, cost=1.0), 2))


def test_methods_are_deterministic_and_differ_on_some_instance():
    fi = make_mini(2, n=12, t=5, m=8)
    a = B.solve_all(fi, 3, 7)
    assert a == B.solve_all(fi, 3, 7)
    differing = [0, 0, 0]
    for seed in range(6):
        fi = make_mini(seed, n=10, t=4, m=7)
        costs = [p.cost for p in B.solve_all(fi, 4, seed)]
        for i in range(3):
            differing[i] += abs(costs[i] - costs[i + 1]) > 1e-9
    assert all(v > 0 for v in differing)                                  # keine tote Spalte: jedes Verfahren weicht vom Nachbarn ab


@pytest.mark.parametrize("n,k", [(1, 1), (2, 4), (3, 4), (5, 3), (4, 4)])
def test_tiny_instances_and_partial_last_round(n, k):
    fi = make_mini(n, n=max(n, 1), t=1, m=3)
    plans = B.solve_all(fi, k, 1)
    assert all(B.check_plan(fi, p, k) == [] for p in plans)
