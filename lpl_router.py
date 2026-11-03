"""Die drei Verlegeregeln: sequentiell, Rip-up and Reroute und Negotiated Congestion (PathFinder), dazu Kennzahlen und der unabhängige Prüfer."""

from collections import defaultdict, deque
from dataclasses import dataclass, field

import lpl_constants as C
from lpl_grid import FREE, Board
from lpl_rng import SplitMix64
from lpl_search import RouteState, route_net


@dataclass(frozen=True)
class Routing:
    method: str
    failed: tuple                 # Netze ohne vollständige, konfliktfreie Verlegung
    nodes: dict = field(default_factory=dict)   # Netz -> Knotenmenge (nur verlegte Netze)
    edges: dict = field(default_factory=dict)   # Netz -> Kanten (u, v)
    searches: int = 0             # Zahl der Suchläufe (Rechenaufwand, plattformunabhängig)
    iterations: int = 0           # Negotiated Congestion: Durchläufe; sonst 0
    converged: bool = True        # Negotiated Congestion: ohne Konflikt beendet


def _result(method: str, state: RouteState, order, failed, iterations: int = 0, converged: bool = True) -> Routing:
    kept = [n for n in order if n in state.nodes and n not in failed]
    return Routing(method, tuple(sorted(failed)), {n: frozenset(state.nodes[n]) for n in kept}, {n: tuple(state.edges[n]) for n in kept},
                   state.searches, iterations, converged)


def route_sequential(board: Board, order, via_cost: float) -> Routing:
    """Jedes Netz der Reihe nach auf dem kürzesten Weg durch freie Zellen; was nicht mehr durchkommt, bleibt unverlegt."""
    state = RouteState(board)
    failed = []
    for n in order:
        r = route_net(board, state, n, "hard", via_cost)
        if r is None:
            failed.append(n)
        else:
            state.commit(n, *r)
    return _result("Sequentiell", state, order, failed)


def _rip_victims(state: RouteState, net: int, nodes: set) -> list:
    """Netze, deren Knoten der neue Weg des Netzes `net` durchquert."""
    return sorted({state.own[v] for v in nodes if state.own[v] >= 0 and state.own[v] != net})


def route_rrr(board: Board, order, via_cost: float, actions_per_net: int = C.RRR_ACTIONS_PER_NET) -> Routing:
    """Rip-up and Reroute: erst sequentiell. Dann darf jedes unverlegte Netz gegen einen Zuschlag fremde Netze durchqueren; diese werden aufgerissen,
    der Weg wird festgelegt und die Opfer neu (hart) verlegt. Aktionsgrenze `actions_per_net` mal Netzzahl; am Ende gilt der beste Stand."""
    state = RouteState(board)
    pending = deque()
    for n in order:
        r = route_net(board, state, n, "hard", via_cost)
        if r is None:
            pending.append(n)
        else:
            state.commit(n, *r)
    best = (len(pending), state.snapshot(), list(pending))
    budget = actions_per_net * len(order)
    while pending and budget > 0:
        budget -= 1
        n = pending.popleft()
        r = route_net(board, state, n, "cross", via_cost)
        if r is None:
            continue
        nodes, edges = r
        victims = _rip_victims(state, n, nodes)
        for v in victims:
            for node in state.nodes[v]:
                state.hist[node] += 1.0
            state.rip(v)
        state.commit(n, nodes, edges)
        for v in victims:
            rr = route_net(board, state, v, "hard", via_cost)
            if rr is None:
                pending.append(v)
            else:
                state.commit(v, *rr)
        if len(pending) < best[0]:
            best = (len(pending), state.snapshot(), list(pending))
    state.restore(best[1])
    return _result("Rip-up and Reroute", state, order, best[2])


def _overused(state: RouteState) -> list:
    return [v for v in range(state.board.nodes) if state.occ[v] > 1]


def _largest_conflict_free_subset(state: RouteState, order) -> list:
    """Bei Nicht-Konvergenz: Netze mit den wenigsten überlasteten Knoten zuerst behalten, solange sie keinen bereits behaltenen Knoten teilen. Gibt die verworfenen Netze."""
    over = set(_overused(state))
    keep, used = set(), set()
    for n in sorted(state.nodes, key=lambda k: (len(state.nodes[k] & over), k)):
        if used.isdisjoint(state.nodes[n]):
            keep.add(n)
            used |= state.nodes[n]
    return [n for n in order if n not in keep]


def route_negotiated(board: Board, order, via_cost: float, iterations: int = C.DEFAULT_ITER) -> Routing:
    """Negotiated Congestion (PathFinder): alle Netze dürfen sich Zellen teilen, doch das Teilen kostet (1 + pf * Belegung), der Preis pf wächst je Iteration,
    und jede überlastete Zelle merkt sich ihre Überlastung im Verlauf. Nach der ersten Iteration werden nur Netze auf überlasteten Zellen neu verlegt."""
    state = RouteState(board)
    pf = C.PF_START
    todo = list(order)
    for it in range(1, iterations + 1):
        for n in todo:
            if n in state.nodes:
                state.rip(n)
            r = route_net(board, state, n, "soft", via_cost, pf=pf)
            if r is None:
                return _result("Negotiated Congestion", state, order, list(order), it, False)
            state.commit(n, *r)
        over = _overused(state)
        if not over:
            return _result("Negotiated Congestion", state, order, [], it, True)
        for v in over:
            state.hist[v] += C.PF_HISTORY * (state.occ[v] - 1)
        over_set = set(over)
        todo = [n for n in order if state.nodes[n] & over_set]
        pf *= C.PF_GROWTH
    failed = _largest_conflict_free_subset(state, order)
    return _result("Negotiated Congestion", state, order, failed, iterations, False)


def net_order(inst_nets_hpwl: list, kind: str, seed: int = 0) -> list:
    """Netzreihenfolge: kurze oder lange Netze (nach HPWL) zuerst, Reihenfolge der Netzliste, oder zufällig (aus `seed`)."""
    n = len(inst_nets_hpwl)
    idx = list(range(n))
    if kind == C.ORDERS[0]:
        return sorted(idx, key=lambda k: (inst_nets_hpwl[k], k))
    if kind == C.ORDERS[1]:
        return sorted(idx, key=lambda k: (-inst_nets_hpwl[k], k))
    if kind == C.ORDERS[2]:
        return idx
    if kind == C.ORDERS[3]:
        SplitMix64(seed * 104729 + 7).shuffle(idx)
        return idx
    raise ValueError(kind)


# ---------------------------------------------------------------- Kennzahlen und Prüfer
def wirelength(board: Board, routing: Routing) -> int:
    """In-Ebene-Schritte aller verlegten Netze."""
    return sum(1 for es in routing.edges.values() for u, v in es if abs(u - v) != board.cells)


def via_count(board: Board, routing: Routing) -> int:
    return sum(1 for es in routing.edges.values() for u, v in es if abs(u - v) == board.cells)


def routing_cost(board: Board, routing: Routing, via_cost: float) -> float:
    """Kosten wie in der Suche: je Schritt 1, je Via-Schritt 1 + via_cost."""
    return wirelength(board, routing) + via_count(board, routing) * (1.0 + via_cost)


def check_feasible(board: Board, routing: Routing) -> list:
    """Unabhängiger Prüfer: Fehlermeldungen (leer = zulässig). Jede Kante verbindet Nachbarn oder das Via derselben Zelle; kein Knoten gehört zwei Netzen;
    kein Knoten ist gesperrt oder Pad eines fremden Netzes; alle Pads jedes als verlegt gemeldeten Netzes hängen über die Kanten zusammen."""
    errors = []
    owner: dict = {}
    w, cells = board.width, board.cells
    for net, nodes in routing.nodes.items():
        for v in nodes:
            f = board.fixed[v]
            if f != FREE and f != net:
                errors.append(f"Netz {net}: Knoten {v} ist gesperrt oder gehört einem fremden Pad")
            if v in owner and owner[v] != net:
                errors.append(f"Knoten {v} gehört den Netzen {owner[v]} und {net}")
            owner[v] = net
        adjacency = defaultdict(set)
        for u, v in routing.edges[net]:
            via = abs(u - v) == cells
            same_layer = u // cells == v // cells
            neighbours = same_layer and ((abs(u - v) == 1 and u // w == v // w) or abs(u - v) == w)
            if not (via or neighbours):
                errors.append(f"Netz {net}: Kante {u}-{v} verbindet keine Nachbarn")
            if u not in nodes or v not in nodes:
                errors.append(f"Netz {net}: Kante {u}-{v} liegt nicht im Baum")
            adjacency[u].add(v)
            adjacency[v].add(u)
        pads = board.pads[net]
        seen, queue = {pads[0], pads[0] + cells}, deque([pads[0], pads[0] + cells])
        while queue:
            u = queue.popleft()
            nxt = set(adjacency[u])
            if board.fixed[u] == net:          # Durchsteckpad: die andere Lage ist ohne Via verbunden
                nxt.add(u + cells if u < cells else u - cells)
            for v in nxt:
                if v not in seen:
                    seen.add(v)
                    queue.append(v)
        for p in pads:
            if p not in seen and p + cells not in seen:
                errors.append(f"Netz {net}: Pad {p} ist nicht angeschlossen")
    return errors
