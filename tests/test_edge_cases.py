"""Randfälle: Extremwerte der Regler, kleinste und größte Instanz, entartete Eingaben, ungültige Namen."""

import pytest

import lpl_constants as C
import lpl_placement as P
import lpl_router as R
from lpl_evaluation import Settings, analyse
from lpl_grid import Board
from lpl_mini import MiniSpec, mini_board
from lpl_scenario import make_instance

CORNERS = [
    dict(n_ic=C.N_IC_MIN, util=C.UTIL_MIN, pin_use=C.PIN_USE_MIN, via_cost=C.VIA_MIN, iterations=C.ITER_MIN),
    dict(n_ic=C.N_IC_MAX, util=C.UTIL_MAX, pin_use=C.PIN_USE_MAX, via_cost=C.VIA_MAX, iterations=C.ITER_MAX),
    dict(n_ic=C.N_IC_MIN, util=C.UTIL_MAX, pin_use=C.PIN_USE_MAX, via_cost=C.VIA_MAX, iterations=C.ITER_MIN),
    dict(n_ic=C.N_IC_MAX, util=C.UTIL_MIN, pin_use=C.PIN_USE_MIN, via_cost=C.VIA_MIN, iterations=C.ITER_MAX),
]


@pytest.mark.parametrize("corner", CORNERS)
@pytest.mark.parametrize("placement", C.PLACEMENTS)
def test_every_corner_of_the_controls_gives_a_clean_analysis(corner, placement):
    """Worst-Case am Reglermaximum: kein Hänger, kein Platzierungsfehler, der Prüfer meldet nichts."""
    a = analyse(Settings(placement=placement, seed=C.DEFAULT_SEED, **corner))
    assert all(v == [] for v in a.violations.values())
    assert all(m["routed"] + m["failed"] == m["nets"] for m in a.metrics.values())


@pytest.mark.parametrize("n_ic", [C.N_IC_MIN, C.N_IC_MAX])
@pytest.mark.parametrize("util", [C.UTIL_MIN, C.UTIL_MAX])
def test_the_placement_always_succeeds_at_the_extremes_over_many_seeds(n_ic, util):
    for seed in range(12):
        inst = make_instance(n_ic, C.PIN_USE_MAX, util, seed)
        for method in C.PLACEMENTS:
            assert P.check_placement(inst, P.place(inst, method, seed)) == []


def test_exactly_two_nets_and_a_single_net():
    two = mini_board(MiniSpec(3, 2, nets=(((0, 0), (2, 0)), ((0, 1), (2, 1))), blocks=()))
    r = R.route_negotiated(two, [0, 1], 4.0)
    assert r.failed == () and r.converged
    one = mini_board(MiniSpec(2, 1, nets=(((0, 0), (1, 0)),), blocks=()))
    for fn in (R.route_sequential, R.route_rrr, R.route_negotiated):
        r = fn(one, [0], 4.0)
        assert r.failed == () and R.wirelength(one, r) == 1


def test_no_nets_and_empty_order_are_defined():
    board = Board(2, 1, (-1, -1, -1, -1), ())
    for fn in (R.route_sequential, R.route_rrr, R.route_negotiated):
        r = fn(board, [], 4.0)
        assert r.failed == () and r.nodes == {} and R.wirelength(board, r) == 0 and R.check_feasible(board, r) == []


def test_a_net_with_both_pads_on_neighbouring_cells_costs_one_step():
    board = mini_board(MiniSpec(2, 2, nets=(((0, 0), (1, 0)),), blocks=()))
    r = R.route_sequential(board, [0], 4.0)
    assert R.routing_cost(board, r, 4.0) == 1.0


def test_iteration_limit_of_one_still_returns_a_feasible_result():
    a = analyse(Settings(iterations=1, seed=2, n_ic=3, util=70))
    assert a.metrics[C.METHODS[2]]["iterations"] == 1 and all(v == [] for v in a.violations.values())


def test_invalid_names_raise():
    inst = make_instance(3, 85, 60, 1)
    with pytest.raises(ValueError):
        P.place(inst, "nope", 1)
    with pytest.raises(ValueError):
        R.net_order([1, 2], "nope")


def test_bounds_are_inclusive_and_defaults_lie_inside():
    assert C.N_IC_MIN <= C.DEFAULT_N_IC <= C.N_IC_MAX and C.UTIL_MIN <= C.DEFAULT_UTIL <= C.UTIL_MAX
    assert C.PIN_USE_MIN <= C.DEFAULT_PIN_USE <= C.PIN_USE_MAX and C.VIA_MIN <= C.DEFAULT_VIA <= C.VIA_MAX
    assert C.ITER_MIN <= C.DEFAULT_ITER <= C.ITER_MAX
    assert make_instance(C.N_IC_MIN, C.PIN_USE_MIN, C.UTIL_MIN, 0).nets and make_instance(C.N_IC_MAX, C.PIN_USE_MAX, C.UTIL_MAX, 0).nets
