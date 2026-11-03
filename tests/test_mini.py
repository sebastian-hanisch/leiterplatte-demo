"""Mini-Bretter: Erzeugung, Raster und Aufzählung aller Reihenfolgen."""

import lpl_mini as M
from lpl_grid import FREE, NC_PAD


def test_random_mini_uses_distinct_cells_and_is_reproducible():
    spec = M.random_mini(7)
    cells = [c for net in spec.nets for c in net] + list(spec.blocks)
    assert len(cells) == len(set(cells)) == 2 * 5 + 1
    assert all(0 <= x < spec.width and 0 <= y < spec.height for x, y in cells)
    assert spec == M.random_mini(7) and spec != M.random_mini(8)


def test_mini_board_marks_pads_on_both_layers_and_blocks_for_everyone():
    spec = M.MiniSpec(3, 2, nets=(((0, 0), (2, 1)),), blocks=((1, 0),))
    b = M.mini_board(spec)
    assert b.pads == ((0, 5),) and b.cells == 6
    for layer in (0, 1):
        assert b.fixed[layer * 6 + 0] == 0 and b.fixed[layer * 6 + 5] == 0       # Pads des Netzes 0
        assert b.fixed[layer * 6 + 1] == NC_PAD                                   # Sperrzelle
        assert b.fixed[layer * 6 + 2] == FREE


def test_scan_counts_every_order_by_hand_on_two_independent_nets():
    spec = M.MiniSpec(4, 3, nets=(((0, 0), (3, 0)), ((0, 2), (3, 2))), blocks=())
    scan = M.scan_all_orders(M.mini_board(spec), 4.0)
    assert (scan.n_orders, scan.successes, scan.best_cost) == (2, 2, 6.0)


def test_the_hand_example_is_a_board_where_no_order_works():
    scan = M.scan_all_orders(M.mini_board(M.HAND_EXAMPLE), 4.0)
    assert (scan.n_orders, scan.successes, scan.best_cost, scan.best_order) == (120, 0, None, None)


def test_there_are_boards_where_only_some_orders_work():
    counts = [M.scan_all_orders(M.mini_board(M.random_mini(s, 5, 5, 4, 1)), 4.0) for s in range(40)]
    assert any(0 < c.successes < c.n_orders for c in counts)
    assert any(c.successes == c.n_orders for c in counts)


def test_heuristics_wrapper_returns_both_methods():
    rrr, pf = M.heuristics(M.mini_board(M.HAND_EXAMPLE), 4.0)
    assert (rrr.method, pf.method) == ("Rip-up and Reroute", "Negotiated Congestion") and not rrr.failed and not pf.failed
