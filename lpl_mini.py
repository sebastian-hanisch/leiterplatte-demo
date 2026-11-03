"""Mini-Bretter für den Exakt-Tab: kleine Raster mit 2-Pin-Netzen, auf denen alle Reihenfolgen aufzählbar und CP-SAT ein bewiesenes Optimum liefert."""

import itertools
from dataclasses import dataclass

import lpl_constants as C
from lpl_grid import FREE, NC_PAD, Board
from lpl_rng import SplitMix64
from lpl_router import Routing, route_negotiated, route_rrr, route_sequential, routing_cost


@dataclass(frozen=True)
class MiniSpec:
    width: int
    height: int
    nets: tuple      # je Netz zwei Pads (x, y)
    blocks: tuple    # gesperrte Zellen (x, y), beide Lagen


# Handbeispiel (Brett 6 x 5, 5 Netze, 1 Sperrzelle): keine der 120 Reihenfolgen verlegt alles, das Optimum kostet 25 (Via-Kosten 4).
HAND_EXAMPLE = MiniSpec(
    6, 5,
    nets=(((3, 1), (4, 1)), ((0, 1), (5, 3)), ((2, 3), (0, 0)), ((5, 1), (5, 0)), ((2, 4), (3, 3))),
    blocks=((3, 4),),
)


def random_mini(seed: int, width: int = 6, height: int = 5, n_nets: int = 5, n_blocks: int = 1) -> MiniSpec:
    """Zufällige Pads und Sperrzellen auf verschiedenen Zellen."""
    cells = [(x, y) for x in range(width) for y in range(height)]
    SplitMix64(seed).shuffle(cells)
    nets = tuple((cells[2 * k], cells[2 * k + 1]) for k in range(n_nets))
    blocks = tuple(cells[2 * n_nets: 2 * n_nets + n_blocks])
    return MiniSpec(width, height, nets, blocks)


def mini_board(spec: MiniSpec) -> Board:
    """Raster des Mini-Bretts: Pads gehören ihrem Netz auf beiden Lagen, Sperrzellen sind für alle gesperrt."""
    w, h = spec.width, spec.height
    hw = w * h
    fixed = [FREE] * (2 * hw)
    for k, (a, b) in enumerate(spec.nets):
        for x, y in (a, b):
            fixed[y * w + x] = k
            fixed[hw + y * w + x] = k
    for x, y in spec.blocks:
        fixed[y * w + x] = NC_PAD
        fixed[hw + y * w + x] = NC_PAD
    pads = tuple((a[1] * w + a[0], b[1] * w + b[0]) for a, b in spec.nets)
    return Board(w, h, tuple(fixed), pads)


@dataclass(frozen=True)
class OrderScan:
    n_orders: int
    successes: int            # Reihenfolgen, in denen sequentielles Verlegen alles unterbringt
    best_cost: float | None   # Kosten der besten vollständigen Reihenfolge, sonst None
    best_order: tuple | None


def scan_all_orders(board: Board, via_cost: float) -> OrderScan:
    """Sequentielles Verlegen in jeder Reihenfolge der Netze (n! Läufe, n <= 6)."""
    n = len(board.pads)
    successes, best = 0, None
    for order in itertools.permutations(range(n)):
        r = route_sequential(board, list(order), via_cost)
        if not r.failed:
            successes += 1
            cost = routing_cost(board, r, via_cost)
            if best is None or cost < best[0]:
                best = (cost, order)
    return OrderScan(_factorial(n), successes, best[0] if best else None, best[1] if best else None)


def _factorial(n: int) -> int:
    out = 1
    for i in range(2, n + 1):
        out *= i
    return out


def heuristics(board: Board, via_cost: float, iterations: int = C.DEFAULT_ITER) -> tuple[Routing, Routing]:
    """Rip-up and Reroute und Negotiated Congestion auf dem Mini-Brett, Reihenfolge der Netzliste."""
    order = list(range(len(board.pads)))
    return route_rrr(board, order, via_cost), route_negotiated(board, order, via_cost, iterations)
