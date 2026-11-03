"""Jede Zahl aus dem README, nachgerechnet über dieselben Auswertungsfunktionen wie in der App und als Median bzw. Mittel über die festen Instanzen SWEEP_SEEDS.

Die Messreihen laufen einmal je Testlauf auf mehreren Prozessen (Instanzen sind unabhängig); die Zahlen sind ganzzahlig oder auf zwei Stellen gerundete Mittel."""

import os
import statistics
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import pytest

import lpl_constants as C
import lpl_evaluation as ev
from lpl_evaluation import Settings
from lpl_mini import mini_board, random_mini, scan_all_orders, heuristics

WORKERS = max(1, min(4, os.cpu_count() or 1))
SEEDS = C.SWEEP_SEEDS


@pytest.fixture(scope="module")
def sweeps():
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        methods = {u: list(ex.map(ev.method_row, [Settings(util=u, seed=s) for s in SEEDS])) for u in C.SWEEP_UTILS}
        place = list(ex.map(ev.placement_comparison, [Settings(util=60, seed=s) for s in SEEDS]))
        via = list(ex.map(ev.via_comparison, [Settings(util=60, seed=s) for s in SEEDS]))
    return {"methods": methods, "place": place, "via": via}


def _mean(rows, key):
    return sum(r[key] for r in rows) / len(rows)


# ---- Befund 1: welche Regel verlegt alles? -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("util,expected", [
    (50, {"sequential": 0, "best_random_order": 2, "rrr": 14, "negotiated": 17}),
    (60, {"sequential": 1, "best_random_order": 1, "rrr": 8, "negotiated": 17}),
    (70, {"sequential": 0, "best_random_order": 0, "rrr": 7, "negotiated": 12}),
])
def test_number_of_instances_with_every_net_routed(sweeps, util, expected):
    summary = ev.summarize_methods(sweeps["methods"][util])
    assert summary == {**expected, "n": 20}


@pytest.mark.parametrize("util,seq,rrr,pf", [(50, 2.80, 0.70, 0.25), (60, 2.90, 1.10, 0.20), (70, 3.05, 1.85, 1.30)])
def test_mean_unrouted_nets_per_instance(sweeps, util, seq, rrr, pf):
    rows = sweeps["methods"][util]
    assert _mean(rows, "sequential") == pytest.approx(seq, abs=0.005)
    assert _mean(rows, "rrr") == pytest.approx(rrr, abs=0.005)
    assert _mean(rows, "negotiated") == pytest.approx(pf, abs=0.005)


@pytest.mark.parametrize("util,converged", [(50, 17), (60, 17), (70, 12)])
def test_negotiated_congestion_converges_on_this_many_instances(sweeps, util, converged):
    assert sum(r["converged"] for r in sweeps["methods"][util]) == converged


def test_the_independent_checker_never_complains_in_the_sweeps(sweeps):
    assert all(r["violations"] == 0 for rows in sweeps["methods"].values() for r in rows)


def test_rip_up_never_leaves_more_nets_unrouted_than_the_sequential_start(sweeps):
    assert all(r["rrr"] <= r["sequential"] for rows in sweeps["methods"].values() for r in rows)


# ---- Befund 2: die Reihenfolge ------------------------------------------------------------------------------------------------------------

def test_order_alone_changes_the_number_of_unrouted_nets(sweeps):
    rows = sweeps["methods"][60]
    spread = [r["worst_random_order"] - r["best_random_order"] for r in rows]
    assert statistics.median(spread) == 5.0 and max(spread) == 8 and min(spread) >= 1
    assert sum(r["sequential"] > r["best_random_order"] for r in rows) == 9      # kurze zuerst ist schlechter als die beste von 20 Zufallsreihenfolgen


# ---- Befund 3: Platzierung ----------------------------------------------------------------------------------------------------------------

def test_placement_table_means(sweeps):
    by = defaultdict(list)
    for inst in sweeps["place"]:
        for r in inst:
            by[r["placement"]].append(r)
    expected = {
        "Zufall": (525, 4.70, 2.90, 0.45, 16),
        "Quadratisch": (346, 3.45, 1.95, 0.10, 18),
        "Simulated Annealing": (296, 2.90, 1.10, 0.20, 17),
    }
    for name, (hp, seq, rrr, pf, full) in expected.items():
        rows = by[name]
        assert round(_mean(rows, "hpwl")) == hp
        assert _mean(rows, "sequential") == pytest.approx(seq, abs=0.005)
        assert _mean(rows, "rrr") == pytest.approx(rrr, abs=0.005)
        assert _mean(rows, "negotiated") == pytest.approx(pf, abs=0.005)
        assert sum(r["negotiated"] == 0 for r in rows) == full


def test_the_placement_with_the_shortest_nets_routes_as_well_as_the_best_one_on_every_instance(sweeps):
    for inst in sweeps["place"]:
        shortest = min(inst, key=lambda r: (r["hpwl"], r["negotiated"]))
        easiest = min(inst, key=lambda r: (r["negotiated"], r["hpwl"]))
        assert shortest["negotiated"] == easiest["negotiated"]


# ---- Befund 4: Via-Kosten -----------------------------------------------------------------------------------------------------------------

def test_via_cost_table(sweeps):
    expected = {1: (16.1, 511), 4: (12.7, 541), 12: (10.2, 541), 30: (9.4, 554)}
    for k, (cost, (vias, wl)) in enumerate(expected.items()):
        rows = [inst[k] for inst in sweeps["via"]]
        assert all(r["via_cost"] == cost for r in rows)
        assert _mean(rows, "vias") == pytest.approx(vias, abs=0.051)
        assert round(_mean(rows, "wirelength")) == wl


# ---- Befund 5: Mini-Bretter gegen den exakten Löser ---------------------------------------------------------------------------------------

MINI = {
    "6 x 5, 5 Netze, 1 Sperrzelle": ((6, 5, 5, 1), dict(infeasible=108, feasible=42, none_works=1, some_work=9, all_work=32, rrr_miss=2, pf_miss=0)),
    "5 x 5, 4 Netze, 1 Sperrzelle": ((5, 5, 4, 1), dict(infeasible=73, feasible=77, none_works=1, some_work=12, all_work=64, rrr_miss=1, pf_miss=0)),
    "6 x 6, 6 Netze, 0 Sperrzellen": ((6, 6, 6, 0), dict(infeasible=104, feasible=46, none_works=3, some_work=14, all_work=29, rrr_miss=0, pf_miss=0)),
}


def _mini_gaps(shape):
    """Abstand der besten bekannten Verlegung (beste Reihenfolge, Rip-up, Negotiated Congestion) zum bewiesenen Optimum, je lösbarem Brett."""
    from lpl_exact import solve_exact
    from lpl_router import routing_cost

    w, h, n, b = shape
    gaps = []
    for seed in range(300000, 300150):
        board = mini_board(random_mini(seed, w, h, n, b))
        e = solve_exact(board, 4.0)
        if e.status != "optimal":
            continue
        scan = scan_all_orders(board, 4.0)
        costs = [routing_cost(board, r, 4.0) for r in heuristics(board, 4.0) if not r.failed]
        if scan.best_cost is not None:
            costs.append(scan.best_cost)
        gaps.append(min(costs) / e.cost - 1)
    return gaps


def test_gap_to_the_optimum_on_the_mini_boards():
    pytest.importorskip("ortools")
    assert max(_mini_gaps((6, 5, 5, 1))) == pytest.approx(0.0, abs=1e-9)
    assert max(_mini_gaps((5, 5, 4, 1))) == pytest.approx(0.0, abs=1e-9)
    gaps = _mini_gaps((6, 6, 6, 0))
    assert len(gaps) == 46
    assert sum(gaps) / len(gaps) == pytest.approx(0.0038, abs=0.0005)
    assert max(gaps) == pytest.approx(0.135, abs=0.0005)


def _mini_counts(shape):
    from lpl_exact import solve_exact

    w, h, n, b = shape
    c = defaultdict(int)
    for seed in range(300000, 300150):
        board = mini_board(random_mini(seed, w, h, n, b))
        e = solve_exact(board, 4.0)
        assert e.status in ("optimal", "infeasible")
        if e.status == "infeasible":
            c["infeasible"] += 1
            continue
        c["feasible"] += 1
        scan = scan_all_orders(board, 4.0)
        c["none_works" if scan.successes == 0 else "all_work" if scan.successes == scan.n_orders else "some_work"] += 1
        rrr, pf = heuristics(board, 4.0)
        c["rrr_miss"] += bool(rrr.failed)
        c["pf_miss"] += bool(pf.failed)
    return dict(c)


@pytest.mark.parametrize("name", list(MINI))
def test_mini_boards_against_the_exact_solver(name):
    pytest.importorskip("ortools")
    shape, expected = MINI[name]
    counts = _mini_counts(shape)
    assert {k: counts.get(k, 0) for k in expected} == expected


def test_named_mini_boards():
    pytest.importorskip("ortools")
    for seed, shape in ((300057, (6, 5, 5, 1)), (300020, (5, 5, 4, 1)), (300020, (6, 6, 6, 0))):
        assert scan_all_orders(mini_board(random_mini(seed, *shape)), 4.0).successes == 0


# ---- Befund: Rip-up hängt an seiner Aktionsgrenze -----------------------------------------------------------------------------------------

def test_rip_up_budget_trade_off_on_six_fixed_instances():
    import lpl_router as R

    totals = {3: [0, 0], 12: [0, 0]}
    for seed in range(100000, 100006):
        inst, poses, board, hp, order = ev.prepare(Settings(util=70, seed=seed))
        for budget in totals:
            r = R.route_rrr(board, list(order), 4.0, budget)
            totals[budget][0] += len(r.failed)
            totals[budget][1] += r.searches
    assert totals == {3: [5, 4225], 12: [2, 12235]}


def test_negotiated_congestion_needs_fewer_searches_than_rip_up_in_the_standard_case():
    a = ev.analyse(Settings())
    assert (a.metrics[C.METHODS[2]]["searches"], a.metrics[C.METHODS[1]]["searches"]) == (550, 1130)


# ---- Presets: die Hilfetexte nennen Messwerte ---------------------------------------------------------------------------------------------

PRESET_RESULTS = {
    "Standardfall (Voreinstellung)": ((4, 1, 0), True),
    "Reihenfolge-Falle": ((10, 1, 0), True),
    "Dichtes Brett": ((3, 2, 0), True),
    "Zu dicht": ((7, 5, 3), False),
    "Zufällige Platzierung": ((5, 3, 0), True),
    "Lockeres Brett": ((0, 0, 0), True),
}


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_preset_results(name):
    p = C.PRESETS[name]
    a = ev.analyse(Settings(p["n_ic"], p["util"], p["pin_use"], p["placement"], p["order"], p["via"], p["iterations"], p["seed"]))
    failed = tuple(a.metrics[m]["failed"] for m in C.METHODS)
    (expected, converged) = PRESET_RESULTS[name]
    assert failed == expected and a.metrics[C.METHODS[2]]["converged"] == converged


def test_the_order_trap_preset_differs_from_short_first_on_the_same_board():
    p = C.PRESETS["Reihenfolge-Falle"]
    short = ev.analyse(Settings(p["n_ic"], p["util"], p["pin_use"], p["placement"], C.ORDERS[0], p["via"], p["iterations"], p["seed"]))
    assert short.metrics[C.METHODS[0]]["failed"] == 3


# ---- Befund 6: Bestückung -----------------------------------------------------------------------------------------------------------------

BST_EXPECTED = {
    1: ((7.41, 0.39, 0.09, 0.01), (0, 11, 15, 19)),
    2: ((12.48, 1.87, 1.12, 0.28), (0, 2, 8, 11)),
    3: ((15.65, 3.45, 1.57, 0.59), (0, 2, 5, 14)),
    4: ((18.77, 3.84, 1.70, 0.65), (0, 0, 5, 15)),
}


@pytest.fixture(scope="module")
def bestueck_sweeps():
    ks = sorted(BST_EXPECTED)
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        return {k: list(ex.map(ev.bestueck_row, [Settings(seed=s) for s in SEEDS], [k] * len(SEEDS))) for k in ks}


@pytest.mark.parametrize("k", sorted(BST_EXPECTED))
def test_bestueckung_gap_to_the_shortest_trip(bestueck_sweeps, k):
    rows = bestueck_sweeps[k]
    means, best_in = BST_EXPECTED[k]
    assert all(r["n"] == 18 and r["violations"] == 0 for r in rows)
    for i, expected in enumerate(means):
        assert sum(r["gaps"][i] for r in rows) / len(rows) == pytest.approx(expected, abs=0.0051)
    for i, expected in enumerate(best_in):
        assert sum(r["gaps"][i] < 1e-9 for r in rows) == expected


def test_bestueckung_extremes_named_in_the_readme(bestueck_sweeps):
    rows = bestueck_sweeps[4]
    assert max(r["gaps"][1] for r in rows) == pytest.approx(13.62, abs=0.0051)
    assert max(r["gaps"][0] for r in rows) == pytest.approx(35.73, abs=0.0051)
    # die Lücke der Trennung wächst mit der Düsenzahl (Mittel über 20 Instanzen)
    gaps = [sum(r["gaps"][1] for r in bestueck_sweeps[k]) / 20 for k in sorted(BST_EXPECTED)]
    assert gaps == sorted(gaps)
