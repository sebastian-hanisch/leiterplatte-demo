"""Auswertung: Kennzahlen gegen Handrechnung, Invarianten der Analyse und die Experimente."""

import pytest

import lpl_constants as C
import lpl_evaluation as ev
import lpl_router as R
from lpl_evaluation import Settings, analyse
from lpl_grid import build_board
from lpl_placement import net_hpwl

SMALL = dict(n_ic=3, util=55)
SEEDS = range(8)


def test_metrics_by_hand_on_two_free_rows(two_rows):
    r = R.route_sequential(two_rows, [0, 1], 4.0)
    m = ev.metrics_of(two_rows, (3, 3), r, 4.0)
    assert (m["nets"], m["routed"], m["failed"], m["wirelength"], m["vias"], m["cost"]) == (2, 2, 0, 6, 0, 6.0)
    assert m["detour"] == pytest.approx(1.0) and m["converged"] and m["iterations"] == 0


def test_metrics_count_only_routed_nets_for_the_detour(two_rows):
    r = R.route_sequential(two_rows, [0], 4.0)         # Netz 1 nicht versucht -> nicht in nodes
    m = ev.metrics_of(two_rows, (3, 6), r, 4.0)
    assert m["routed"] == 1 and m["wirelength"] == 3 and m["detour"] == pytest.approx(1.0)


def test_random_orders_are_permutations_and_streams_differ():
    orders = ev.random_orders(8, 5, 3)
    assert all(sorted(o) == list(range(8)) for o in orders)
    assert len({tuple(o) for o in orders}) == 5
    assert orders == ev.random_orders(8, 5, 3) and orders != ev.random_orders(8, 5, 4)


@pytest.mark.parametrize("seed", SEEDS)
def test_analysis_invariants(seed):
    a = analyse(Settings(seed=seed, **SMALL))
    n = len(a.inst.nets)
    for method, m in a.metrics.items():
        assert m["routed"] + m["failed"] == n and m["failed"] == len(a.routings[method].failed)
        assert set(a.routings[method].nodes) | set(a.routings[method].failed) == set(range(n))
    assert all(v == [] for v in a.violations.values())
    assert a.hpwl == sum(a.net_hpwl) and sorted(a.order) == list(range(n))
    # Rip-up beginnt beim sequentiellen Ergebnis und gibt den besten Stand zurück: nie mehr unverlegte Netze
    assert a.metrics[C.METHODS[1]]["failed"] <= a.metrics[C.METHODS[0]]["failed"]


def test_the_three_methods_differ_on_at_least_one_instance():
    """Keine tote Spalte: sequentiell, Rip-up und Negotiated Congestion liefern auf dichten Brettern verschiedene Ergebnisse (Seeds 22 und 21 der Presets)."""
    rows = [analyse(Settings(util=72, seed=s)).metrics for s in (22, 21)]
    seq, rrr, pf = ([r[m]["failed"] for r in rows] for m in C.METHODS)
    assert seq != rrr
    assert rrr != pf


def test_order_spread_matches_an_independent_recomputation():
    a = analyse(Settings(seed=2, **SMALL))
    spread = ev.order_spread(a, samples=6)
    assert len(spread["random"]) == 6 and set(spread["fixed"]) == set(C.ORDERS[:3])
    inst_board = a.board
    for kind, failed in spread["fixed"].items():
        order = R.net_order(list(a.net_hpwl), kind, a.settings.seed)
        assert failed == len(R.route_sequential(inst_board, order, float(a.settings.via_cost)).failed)
    for order, failed in zip(ev.random_orders(len(a.board.pads), 6, a.settings.seed), spread["random"]):
        assert failed == len(R.route_sequential(inst_board, order, float(a.settings.via_cost)).failed)


def test_the_order_changes_the_result_on_some_instance():
    spreads = [ev.order_spread(analyse(Settings(seed=s, **SMALL)), samples=6)["random"] for s in range(6)]
    assert any(max(s) > min(s) for s in spreads)


def test_method_row_and_summary_by_hand():
    rows = [
        {"sequential": 0, "best_random_order": 0, "rrr": 0, "negotiated": 0},
        {"sequential": 3, "best_random_order": 1, "rrr": 0, "negotiated": 0},
        {"sequential": 2, "best_random_order": 2, "rrr": 1, "negotiated": 0},
    ]
    assert ev.summarize_methods(rows) == {"sequential": 1, "best_random_order": 1, "rrr": 2, "negotiated": 3, "n": 3}


def test_method_sweep_uses_the_given_fixed_seeds_and_a_clean_checker():
    rows = ev.method_sweep(55, seeds=(100000, 100001), base=Settings(n_ic=3))
    assert [r["seed"] for r in rows] == [100000, 100001]
    assert all(r["violations"] == 0 and r["best_random_order"] <= r["worst_random_order"] for r in rows)


def test_placement_comparison_covers_every_method_once():
    rows = ev.placement_comparison(Settings(seed=3, **SMALL))
    assert [r["placement"] for r in rows] == list(C.PLACEMENTS)
    assert rows[0]["hpwl"] > rows[2]["hpwl"]          # Zufall deutlich länger als Simulated Annealing


def test_via_costs_reduce_the_number_of_vias_on_average():
    firsts, lasts = 0, 0
    for s in range(4):
        rows = ev.via_comparison(Settings(seed=s, **SMALL), costs=(1, 30))
        firsts += rows[0]["vias"]
        lasts += rows[1]["vias"]
    assert firsts > lasts


def test_prepare_places_everything_inside_a_board_of_the_requested_density():
    s = Settings(seed=1, **SMALL)
    inst, poses, board, hp, order = ev.prepare(s)
    area = sum((c.w + C.GAP) * (c.h + C.GAP) for c in inst.comps)
    assert 0.55 * 0.85 <= area / (inst.width * inst.height) <= 0.55 * 1.15   # Aufrundung der Seiten
    assert board == build_board(inst, poses) and hp == tuple(net_hpwl(inst, poses, n) for n in inst.nets)


def test_full_routing_rank_orders_by_failures_then_cost():
    a = analyse(Settings(seed=2, **SMALL))
    rank = ev.full_routing_rank(a)
    keys = [(a.metrics[m]["failed"], a.metrics[m]["cost"]) for m in rank]
    assert keys == sorted(keys)
