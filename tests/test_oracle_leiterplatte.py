"""Orakel-Tests leiterplatte-demo: andere Rechenwege als die der Demo (DEMO-PLAYBOOK §12, ORACLE-PLAYBOOK).

1. Ein Netz allein: Dijkstra der Demo gegen `networkx` (Kürzeste-Wege-Bibliothek) auf zufälligen Mini-Brettern mit Sperrzellen und Via-Kosten.
2. Mehrere Netze: der exakte Löser (CP-SAT) gegen Aufzählung und Heuristiken: kein Verfahren unterschreitet das bewiesene Optimum, wo der Löser
   „unlösbar“ beweist, meldet jedes Verfahren unverlegte Netze, und wo ein Verfahren alles verlegt, ist das Brett lösbar.
3. Der Löser gegen eine Handrechnung (Optimum des Handbeispiels 25) und gegen eine geschlossene Formel (zwei freie Zeilen)."""

import itertools

import pytest

import lpl_router as R
from lpl_grid import FREE
from lpl_mini import HAND_EXAMPLE, MiniSpec, mini_board, random_mini, scan_all_orders

nx = pytest.importorskip("networkx")


def _nx_cost(board, net, via):
    """Kosten des kürzesten Weges eines Netzes auf dem leeren Brett nach networkx: Betreten eines Knotens kostet 1, ein Via zusätzlich `via`."""
    g = nx.DiGraph()
    w, cells = board.width, board.cells
    allowed = lambda v: board.fixed[v] in (FREE, net)
    for u in range(board.nodes):
        layer, r = divmod(u, cells)
        y, x = divmod(r, w)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if 0 <= x + dx < w and 0 <= y + dy < board.height:
                v = layer * cells + (y + dy) * w + (x + dx)
                if allowed(u) and allowed(v):
                    g.add_edge(u, v, weight=1.0)
        v = u + cells if layer == 0 else u - cells
        if allowed(u) and allowed(v):
            g.add_edge(u, v, weight=1.0 + via)
    s, t = board.pads[net]
    for node in (s, s + cells):
        g.add_edge("S", node, weight=0.0)
    for node in (t, t + cells):
        g.add_edge(node, "T", weight=0.0)
    try:
        return nx.shortest_path_length(g, "S", "T", weight="weight")
    except nx.NetworkXNoPath:
        return None


@pytest.mark.parametrize("seed", range(40))
def test_single_net_cost_equals_networkx(seed):
    spec = random_mini(seed, width=7, height=5, n_nets=1, n_blocks=8)
    board = mini_board(spec)
    via = float(1 + seed % 9)
    expected = _nx_cost(board, 0, via)
    r = R.route_sequential(board, [0], via)
    if expected is None:
        assert r.failed == (0,)
    else:
        assert r.failed == () and R.routing_cost(board, r, via) == pytest.approx(expected)
        assert R.check_feasible(board, r) == []


def test_exact_solver_against_the_hand_values():
    pytest.importorskip("ortools")
    from lpl_exact import solve_exact

    free = mini_board(MiniSpec(4, 3, nets=(((0, 0), (3, 0)), ((0, 2), (3, 2))), blocks=()))
    e = solve_exact(free, 4.0)
    assert e.status == "optimal" and e.cost == pytest.approx(6.0)         # zwei Zeilen, je 3 Schritte
    hand = solve_exact(mini_board(HAND_EXAMPLE), 4.0)
    assert hand.status == "optimal" and hand.cost == pytest.approx(25.0)  # 20 Schritte und ein Via-Schritt zu 5
    assert R.check_feasible(mini_board(HAND_EXAMPLE), hand.routing) == []


def test_exact_solver_proves_infeasibility_when_a_pad_is_walled_in():
    pytest.importorskip("ortools")
    from lpl_exact import solve_exact

    walled = mini_board(MiniSpec(3, 1, nets=(((0, 0), (2, 0)),), blocks=((1, 0),)))
    assert solve_exact(walled, 4.0).status == "infeasible"


@pytest.mark.parametrize("seed", range(300000, 300016))
def test_heuristics_agree_with_the_exact_solver_on_small_boards(seed):
    pytest.importorskip("ortools")
    from lpl_exact import solve_exact

    spec = random_mini(seed, width=5, height=5, n_nets=4, n_blocks=1)
    board = mini_board(spec)
    via = 4.0
    exact = solve_exact(board, via)
    assert exact.status in ("optimal", "infeasible")
    scan = scan_all_orders(board, via)
    rrr = R.route_rrr(board, [0, 1, 2, 3], via)
    pf = R.route_negotiated(board, [0, 1, 2, 3], via)
    for r in (rrr, pf):
        assert R.check_feasible(board, r) == []
    if exact.status == "infeasible":
        assert scan.successes == 0 and rrr.failed and pf.failed
        return
    assert R.check_feasible(board, exact.routing) == []
    assert exact.cost == pytest.approx(R.routing_cost(board, exact.routing, via))
    if scan.successes:
        assert scan.best_cost >= exact.cost - 1e-9
    for r in (rrr, pf):
        if not r.failed:
            assert R.routing_cost(board, r, via) >= exact.cost - 1e-9


def test_some_small_board_is_solvable_but_defeats_every_net_order():
    """Der Kern der Demo auf Mini-Brettern, gezählt statt behauptet: es gibt lösbare Bretter, an denen keine Reihenfolge klappt, und andere, an denen nur manche klappen."""
    pytest.importorskip("ortools")
    from lpl_exact import solve_exact

    none_works, some_work = 0, 0
    for seed in range(300000, 300060):
        board = mini_board(random_mini(seed, width=6, height=5, n_nets=5, n_blocks=1))
        scan = scan_all_orders(board, 4.0)
        if scan.successes == 0:
            if solve_exact(board, 4.0).status in ("optimal", "feasible"):
                none_works += 1
        elif scan.successes < scan.n_orders:
            some_work += 1
    assert none_works >= 1 and some_work >= 1


def test_all_orders_count_matches_itertools():
    board = mini_board(random_mini(1, width=5, height=5, n_nets=4, n_blocks=0))
    assert scan_all_orders(board, 4.0).n_orders == len(list(itertools.permutations(range(4))))
