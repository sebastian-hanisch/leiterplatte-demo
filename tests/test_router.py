"""Suche, Zustand und die drei Verlegeregeln an Mini-Brettern mit Handrechnung (DEMO-PLAYBOOK §1b)."""

import dataclasses

import pytest

import lpl_constants as C
import lpl_router as R
from lpl_grid import cell_of
from lpl_mini import HAND_EXAMPLE, MiniSpec, mini_board
from lpl_search import RouteState, _enter_cost, route_net

VIA = 4.0


def _cost(board, routing, via=VIA):
    return R.routing_cost(board, routing, via)


def test_two_independent_rows_cost_three_each(two_rows):
    r = R.route_sequential(two_rows, [0, 1], VIA)
    assert r.failed == () and R.wirelength(two_rows, r) == 6 and R.via_count(two_rows, r) == 0
    assert _cost(two_rows, r) == 6.0 and R.check_feasible(two_rows, r) == []


def test_crossing_nets_share_the_cell_on_different_layers(crossing):
    for order in ([0, 1], [1, 0]):
        r = R.route_sequential(crossing, order, VIA)
        assert r.failed == () and R.wirelength(crossing, r) == 5 and R.via_count(crossing, r) == 0
        assert R.check_feasible(crossing, r) == []
        # die gemeinsame Zelle (1, 1) wird von beiden Netzen benutzt, aber auf verschiedenen Lagen
        assert {v % crossing.cells for v in r.nodes[0]} & {v % crossing.cells for v in r.nodes[1]} == {1 * 4 + 1} | set()
        assert len({v for n in r.nodes for v in r.nodes[n]}) == sum(len(r.nodes[n]) for n in r.nodes)


@pytest.mark.parametrize("via", [1.0, 4.0, 10.0])
def test_forced_via_costs_four_steps_plus_one_via_step(via_forced, via):
    r = R.route_sequential(via_forced, [0], via)
    assert r.failed == () and R.wirelength(via_forced, r) == 4 and R.via_count(via_forced, r) == 1
    assert _cost(via_forced, r, via) == 4 + 1 + via
    # das Via liegt bei x = 2: oben gesperrt ist x = 1, unten gesperrt ist x = 3
    via_edges = [(u, v) for u, v in r.edges[0] if abs(u - v) == via_forced.cells]
    assert [cell_of(via_forced, u)[0] for u, _ in via_edges] == [2]


def test_blocked_net_stays_unrouted_and_reports_it():
    board = mini_board(MiniSpec(3, 1, nets=(((0, 0), (2, 0)),), blocks=((1, 0),)))
    for fn in (R.route_sequential, R.route_rrr, R.route_negotiated):
        r = fn(board, [0], VIA)
        assert r.failed == (0,) and r.nodes == {}


def test_enter_cost_by_hand():
    assert _enter_cost("hard", 0, 0.0, 0.0, 6.0) == 1.0
    assert _enter_cost("hard", 1, 0.0, 0.0, 6.0) < 0                       # gesperrt
    assert _enter_cost("soft", 3, 0.5, 2.0, 6.0) == pytest.approx((1 + 0.5) * (1 + 2.0 * 3))   # 10,5
    assert _enter_cost("soft", 0, 0.0, 2.0, 6.0) == 1.0
    assert _enter_cost("cross", 0, 0.5, 0.0, 6.0) == 1.5
    assert _enter_cost("cross", 1, 0.5, 0.0, 6.0) == 1.5 + 6.0


def test_commit_and_rip_keep_the_occupancy_consistent(two_rows):
    state = RouteState(two_rows)
    nodes, edges = route_net(two_rows, state, 0, "hard", VIA)
    state.commit(0, nodes, edges)
    assert sum(state.occ) == len(nodes) and all(state.own[v] == 0 for v in nodes)
    snap = state.snapshot()
    state.rip(0)
    assert sum(state.occ) == 0 and state.nodes == {} and all(o == -1 for o in state.own)
    state.restore(snap)
    assert sum(state.occ) == len(nodes) and state.edges[0] == edges


def test_occupied_cells_are_blocked_in_hard_mode_and_allowed_in_cross_mode(crossing):
    state = RouteState(crossing)
    # Netz 1 senkrecht in Spalte 1 auf beiden Lagen unmöglich zu sperren: wir belegen die ganze Zeile 1 beider Lagen künstlich mit Netz 0
    row = {1 * 4 + x for x in range(4)} | {12 + 1 * 4 + x for x in range(4)}
    state.commit(0, set(row), [])
    assert route_net(crossing, state, 1, "hard", VIA) is None
    r = route_net(crossing, state, 1, "cross", VIA)
    assert r is not None and r[0] & row


def test_the_hand_example_has_no_working_order_but_rip_up_and_negotiation_solve_it(hand_board):
    from lpl_mini import scan_all_orders

    scan = scan_all_orders(hand_board, VIA)
    assert (scan.n_orders, scan.successes, scan.best_cost) == (120, 0, None)
    order = list(range(5))
    for fn in (R.route_rrr, R.route_negotiated):
        r = fn(hand_board, order, VIA)
        assert r.failed == () and _cost(hand_board, r) == 25.0 and R.check_feasible(hand_board, r) == []


def test_negotiation_without_enough_iterations_reports_non_convergence_but_stays_feasible(hand_board):
    r = R.route_negotiated(hand_board, list(range(5)), VIA, 1)
    assert r.iterations == 1 and not r.converged and len(r.failed) >= 1
    assert R.check_feasible(hand_board, r) == []


def test_methods_are_deterministic(hand_board):
    a = R.route_negotiated(hand_board, list(range(5)), VIA)
    b = R.route_negotiated(hand_board, list(range(5)), VIA)
    assert a == b


def test_sequential_result_does_not_depend_on_net_numbering():
    spec = HAND_EXAMPLE
    flipped = MiniSpec(spec.width, spec.height, tuple(reversed(spec.nets)), spec.blocks)
    for order in ([0, 1, 2, 3, 4], [4, 3, 2, 1, 0], [2, 0, 4, 1, 3]):
        a = R.route_sequential(mini_board(spec), order, VIA)
        b = R.route_sequential(mini_board(flipped), [4 - k for k in order], VIA)
        assert len(a.failed) == len(b.failed)
        assert sorted(4 - k for k in b.failed) == list(a.failed)
        assert R.wirelength(mini_board(spec), a) == R.wirelength(mini_board(flipped), b)


def test_net_order_kinds():
    hp = [5, 1, 5, 3]
    assert R.net_order(hp, C.ORDERS[0]) == [1, 3, 0, 2]
    assert R.net_order(hp, C.ORDERS[1]) == [0, 2, 3, 1]
    assert R.net_order(hp, C.ORDERS[2]) == [0, 1, 2, 3]
    a, b = R.net_order(hp, C.ORDERS[3], 1), R.net_order(hp, C.ORDERS[3], 2)
    assert sorted(a) == [0, 1, 2, 3] and a == R.net_order(hp, C.ORDERS[3], 1) and a != b
    with pytest.raises(ValueError):
        R.net_order(hp, "nope")


# ---- Prüfer: jede Verletzung wird gefunden -------------------------------------------------------------------------------------------------

def _routed(two_rows):
    return R.route_sequential(two_rows, [0, 1], VIA)


def test_checker_finds_a_shared_node(two_rows):
    r = _routed(two_rows)
    shared = next(iter(r.nodes[0]))
    bad = dataclasses.replace(r, nodes={**r.nodes, 1: r.nodes[1] | {shared}})
    assert any("gehört den Netzen" in e or "gesperrt" in e for e in R.check_feasible(two_rows, bad))


def test_checker_finds_a_missing_connection(two_rows):
    r = _routed(two_rows)
    bad = dataclasses.replace(r, edges={**r.edges, 0: r.edges[0][1:]})
    assert any("nicht angeschlossen" in e or "nicht im Baum" in e for e in R.check_feasible(two_rows, bad))


def test_checker_finds_an_edge_between_non_neighbours(two_rows):
    r = _routed(two_rows)
    u, v = r.edges[0][0]
    bad = dataclasses.replace(r, edges={**r.edges, 0: ((u, v + 2),) + r.edges[0][1:]})
    assert any("keine Nachbarn" in e for e in R.check_feasible(two_rows, bad))


def test_checker_finds_a_foreign_pad_and_a_blocked_cell(two_rows, via_forced):
    r = _routed(two_rows)
    foreign = next(iter(two_rows.pads[1]))
    bad = dataclasses.replace(r, nodes={**r.nodes, 0: r.nodes[0] | {foreign}})
    assert any("gesperrt oder gehört einem fremden Pad" in e for e in R.check_feasible(two_rows, bad))
    rv = R.route_sequential(via_forced, [0], VIA)
    bad = dataclasses.replace(rv, nodes={0: rv.nodes[0] | {1}})            # (1, 0) oben ist gesperrt
    assert any("gesperrt" in e for e in R.check_feasible(via_forced, bad))


def test_checker_accepts_an_unrouted_net_and_does_not_count_it(two_rows):
    r = dataclasses.replace(_routed(two_rows), failed=(1,), nodes={0: _routed(two_rows).nodes[0]}, edges={0: _routed(two_rows).edges[0]})
    assert R.check_feasible(two_rows, r) == []
    assert R.wirelength(two_rows, r) == 3
