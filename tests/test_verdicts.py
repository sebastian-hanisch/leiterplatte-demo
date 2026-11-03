"""Verdikte an von Hand gesetzten Werten (DEMO-PLAYBOOK §12): jede Zahl im Text und jede Schwelle der Art steht hier."""

import lpl_constants as C
import lpl_evaluation as ev
from lpl_exact import ExactResult
from lpl_mini import OrderScan
from lpl_router import Routing

S, R, P = C.METHODS


def _metrics(seq, rrr, pf, n=20, converged=True, iterations=14):
    base = {"nets": n, "converged": True, "iterations": 0}
    return {S: dict(base, failed=seq), R: dict(base, failed=rrr), P: dict(base, failed=pf, converged=converged, iterations=iterations)}


def test_methods_negotiation_wins():
    kind, text = ev.verdict_methods(_metrics(5, 2, 0, n=22))
    assert kind == "success"
    assert "Von 22 Netzen" in text and "sequentiell **5**" in text and "Rip-up **2**" in text and "Negotiated Congestion **0**" in text and "alle Netze unter" in text


def test_methods_nothing_to_negotiate_on_a_loose_board():
    kind, text = ev.verdict_methods(_metrics(0, 0, 0))
    assert kind == "info" and "nichts zu verhandeln" in text


def test_methods_non_convergence_names_the_iteration_limit():
    kind, text = ev.verdict_methods(_metrics(7, 4, 2, converged=False, iterations=60))
    assert kind == "warning" and "nach 60 Iterationen" in text and "konfliktfreie Teilmenge der letzten Wege" in text and "Negotiated Congestion **2**" in text


def test_methods_failures_without_non_convergence_do_not_claim_unroutability():
    kind, text = ev.verdict_methods(_metrics(3, 2, 1, converged=True))
    assert kind == "warning" and "es beweist keine Unlösbarkeit" in text


def test_order_verdict_names_range_median_and_the_fixed_orders():
    spread = {"fixed": {C.ORDERS[0]: 4, C.ORDERS[1]: 9, C.ORDERS[2]: 6}, "random": [3, 5, 7, 12]}
    kind, text = ev.verdict_order(spread, 21)
    assert kind == "success"
    assert "der 21 Netze" in text and "bei 4 Zufallsreihenfolgen" in text and "**3 bis 12**" in text and "Median 6" in text
    assert "Kurze zuerst: 4, lange zuerst: 9, Netzliste: 6" in text


def test_order_verdict_uses_a_decimal_comma_and_handles_equal_runs():
    kind, text = ev.verdict_order({"fixed": {C.ORDERS[0]: 1, C.ORDERS[1]: 1, C.ORDERS[2]: 1}, "random": [1, 2]}, 10)
    assert "Median 1,5" in text
    kind, text = ev.verdict_order({"fixed": {C.ORDERS[0]: 0, C.ORDERS[1]: 0, C.ORDERS[2]: 0}, "random": [0, 0, 0]}, 10)
    assert kind == "info" and "keinen Unterschied" in text


def _prow(name, hpwl, neg):
    return {"placement": name, "hpwl": hpwl, "negotiated": neg}


def test_placement_verdict_when_the_shortest_nets_are_not_the_easiest_to_route():
    rows = [_prow("Zufall", 500, 1), _prow("Quadratisch", 300, 0), _prow("Simulated Annealing", 250, 1)]
    kind, text = ev.verdict_placement(rows)
    assert kind == "warning" and "Zufall: HPWL 500, unverlegt 1" in text
    assert "kleinsten Netzlänge (Simulated Annealing)" in text and "nicht** die am besten verlegbare (Quadratisch)" in text


def test_placement_verdict_when_they_agree_and_on_ties():
    rows = [_prow("Zufall", 500, 1), _prow("Quadratisch", 300, 0), _prow("Simulated Annealing", 250, 0)]
    kind, text = ev.verdict_placement(rows)
    assert kind == "info" and "(Simulated Annealing) lässt auch hier die wenigsten Netze unverlegt" in text and "nicht allgemein" in text
    tied = [_prow("Zufall", 500, 0), _prow("Quadratisch", 300, 0), _prow("Simulated Annealing", 250, 0)]
    assert ev.verdict_placement(tied)[0] == "info"


def test_via_verdict_reports_the_saved_vias_and_the_equal_case():
    rows = [{"via_cost": 1, "vias": 29, "wirelength": 624, "failed": 0}, {"via_cost": 30, "vias": 12, "wirelength": 690, "failed": 1}]
    kind, text = ev.verdict_via(rows)
    assert kind == "info" and "Via-Kosten 1 → 30" in text and "Vias 29 → 12" in text and "Länge 624 → 690" in text and "unverlegt 0 → 1" in text and "sparen 17 Vias" in text and "um +66 Zellen" in text and "nur grob vergleichbar" in text
    same = [dict(rows[0], vias=5), dict(rows[1], vias=5)]
    assert "sparen hier keine Vias" in ev.verdict_via(same)[1]


def _routing(failed, method="Rip-up and Reroute"):
    return Routing(method, tuple(range(failed)))


def test_exact_verdict_no_order_works_but_a_solution_exists():
    scan = OrderScan(120, 0, None, None)
    kind, text = ev.verdict_exact(scan, _routing(0), _routing(0, P), ExactResult("optimal", 25.0, None), 5)
    assert kind == "success"
    assert "**0 von 120**" in text and "Kosten 25, Optimum bewiesen" in text and "keine Reihenfolge schafft es" in text and "beide eine Lösung" in text


def test_exact_verdict_some_orders_work_and_heuristics_differ():
    scan = OrderScan(24, 10, 31.0, (0, 1, 2, 3))
    kind, text = ev.verdict_exact(scan, _routing(1), _routing(0, P), ExactResult("feasible", 30.5, None), 4)
    assert kind == "info" and "**10 von 24**" in text and "Kosten 30,5" in text and "nicht bewiesen optimal" in text and "Nur Negotiated Congestion" in text


def test_exact_verdict_infeasible_unknown_and_contradiction():
    scan = OrderScan(24, 0, None, None)
    kind, text = ev.verdict_exact(scan, _routing(1), _routing(2, P), ExactResult("infeasible", None, None), 4)
    assert kind == "info" and "beweist: es gibt keine Verlegung** aller 4 Netze" in text
    assert ev.verdict_exact(scan, _routing(1), _routing(2, P), ExactResult("unknown", None, None), 4)[0] == "warning"
    kind, text = ev.verdict_exact(scan, _routing(0), _routing(2, P), ExactResult("infeasible", None, None), 4)
    assert kind == "error" and "Widerspruch" in text
    none = ev.verdict_exact(OrderScan(24, 5, 9.0, (0, 1, 2, 3)), _routing(2), _routing(3, P), ExactResult("optimal", 9.0, None), 4)[1]
    assert "Weder Rip-up noch Negotiated Congestion" in none
