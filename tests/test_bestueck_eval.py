"""Bestückung in der Auswertung: Instanz aus der Platzierung, Prozentrechnung, Verdikte, Zeichnung."""

import pytest

import lpl_bestueck as B
import lpl_constants as C
import lpl_evaluation as ev
import lpl_visualization as V
from lpl_evaluation import Settings, analyse

SMALL = dict(n_ic=3, util=55)


@pytest.fixture(scope="module")
def small_analysis():
    return analyse(Settings(seed=2, **SMALL))


def test_percent_over_best_by_hand():
    assert ev.percent_over_best([110.0, 100.0, 100.0, 105.0]) == pytest.approx((10.0, 0.0, 0.0, 5.0))
    assert ev.percent_over_best([0.0, 0.0]) == (0.0, 0.0)                    # nichts zu fahren: nichts zu vergleichen


def test_feeder_instance_takes_every_part_but_the_connectors(small_analysis):
    a = small_analysis
    fi = B.make_feeder_instance(a.inst, a.poses)
    assert fi.n == len(a.inst.comps) - 2 and "J1" not in fi.names and "J2" not in fi.names
    assert set(fi.type_names) == {"Kondensator", "Widerstand"} | {n for n in fi.type_names if n.startswith("IC mit")}
    assert fi.n_slots == fi.n_types + C.BST_EXTRA_SLOTS
    # Zuführreihe mittig unter dem Brett im Abstand BST_PITCH, Ausgangsposition links davon
    assert fi.slots[0][1] == a.inst.height + C.BST_ROW_OFFSET and fi.home == (0.0, fi.slots[0][1])
    assert fi.slots[0][0] + fi.slots[-1][0] == pytest.approx(a.inst.width) and fi.slots[1][0] - fi.slots[0][0] == C.BST_PITCH


def test_part_positions_are_the_component_centres(small_analysis):
    a = small_analysis
    fi = B.make_feeder_instance(a.inst, a.poses)
    j = fi.names.index("R1")
    fp = next(f for f in a.inst.comps if f.name == "R1")
    pose = a.poses[a.inst.comps.index(fp)]
    w, h = (fp.w, fp.h) if pose[2] == 0 else (fp.h, fp.w)
    assert fi.positions[j] == (pose[0] + w / 2.0, pose[1] + h / 2.0)


@pytest.mark.parametrize("k", [1, 4])
def test_bestueckung_for_is_clean_and_names_the_shortest_trip(small_analysis, k):
    b = ev.bestueckung_for(small_analysis, k)
    assert b.violations == () and len(b.plans) == 4 and [p.method for p in b.plans] == list(C.BST_METHODS)
    assert min(b.gaps) == pytest.approx(0.0) and all(g >= 0 for g in b.gaps)
    assert b.plans[0].evaluations == 1 and all(p.evaluations >= B.budget_for(b.fi) for p in b.plans[1:])


def test_budget_is_the_same_for_every_search_method(small_analysis):
    b = ev.bestueckung_for(small_analysis, 2)
    budget = B.budget_for(b.fi)
    assert [p.evaluations for p in b.plans[1:]] == [budget + 1, b.plans[2].evaluations, budget + 1]
    assert budget <= b.plans[2].evaluations <= budget + b.fi.n_types * (b.fi.n_types + b.fi.n_slots) * 8      # Platzsuche zählt mit


def test_verdict_when_the_split_costs_something():
    kind, text = ev.verdict_bestueckung([112.0, 104.0, 102.0, 100.0], 4)
    assert kind == "success"
    assert "kürzeste Fahrt hat 100 Zellen" in text and "Kopf mit 4 Düsen" in text and "Maschinenpraxis fährt 12 % mehr" in text
    assert "„erst Plätze, dann Reihenfolge“ 4 %" in text and "abwechselnd 2 %, gemeinsam 0 %" in text


def test_verdict_when_the_split_is_enough_and_decimal_comma():
    kind, text = ev.verdict_bestueckung([107.5, 100.4, 100.2, 100.0], 1)
    assert kind == "info" and "Kopf mit 1 Düse)" in text and "7,5 %" in text and "0,4 %" in text
    assert "Die Trennung genügt hier" in text


def test_verdict_threshold_is_inclusive_at_one_percent():
    assert ev.verdict_bestueckung([120.0, 101.0, 100.0, 100.0], 2)[0] == "success"       # genau 1 %
    assert ev.verdict_bestueckung([120.0, 100.99, 100.0, 100.0], 2)[0] == "info"


def test_verdict_when_every_search_finds_the_same_trip():
    kind, text = ev.verdict_bestueckung([130.0, 100.0, 100.0, 100.0], 2)
    assert kind == "info" and "dieselbe Fahrt" in text


def test_plan_route_covers_every_part_once_and_starts_at_home(small_analysis):
    b = ev.bestueckung_for(small_analysis, 3)
    plan = b.plans[3]
    rounds = B.plan_route(b.fi, plan, 3)
    assert len(rounds) == -(-b.fi.n // 3)
    assert rounds[0][1][0] == b.fi.home
    placed = [p for _, pts in rounds for p in pts[3:]]
    assert sorted(placed) == sorted(b.fi.positions)


def test_figures_have_the_expected_traces(small_analysis):
    b = ev.bestueckung_for(small_analysis, 2)
    fig = V.build_bestueck_figure(b.fi, b.plans[1], 2, small_analysis.inst.width, small_analysis.inst.height)
    names = [t.name for t in fig.data]
    assert "holen" in names and "setzen" in names and "Start" in names and set(b.fi.type_names) <= set(names)
    assert V.build_bestueck_methods_figure(b.plans, b.gaps).data[0].y == tuple(round(p.cost, 1) for p in b.plans)
