"""Kürzeste-Wege-Suche eines Netzes: Mehrquellen-Dijkstra von dem schon verlegten Baum zum nächsten Pad, wiederholt, bis alle Pads verbunden sind.

Drei Kostenmodi für das Betreten eines Knotens v (Grundkosten 1, ein Via kostet zusätzlich `via_cost`):
  hard   belegte Knoten sind gesperrt (sequentielles Verlegen)
  cross  belegte Knoten sind erlaubt gegen einen Zuschlag `cross` (Rip-up: der Weg darf fremde Netze durchqueren, die danach aufgerissen werden)
  soft   Kosten (1 + Verlauf[v]) * (1 + pf * Belegung[v]) (Negotiated Congestion)"""

import heapq

import lpl_constants as C
from lpl_grid import FREE, Board


class RouteState:
    """Veränderlicher Zustand eines Verlegelaufs: Belegung je Knoten, Besitzer, Verlauf (Negotiated Congestion, Rip-up) und die Bäume der Netze."""

    def __init__(self, board: Board):
        self.board = board
        self.occ = [0] * board.nodes        # Zahl der Netze, die den Knoten benutzen
        self.own = [-1] * board.nodes       # letztes Netz auf dem Knoten (nur im harten Modus eindeutig)
        self.hist = [0.0] * board.nodes
        self.nodes: dict = {}               # Netz -> Menge seiner Knoten
        self.edges: dict = {}               # Netz -> Liste von Kanten (u, v)
        self.searches = 0

    def commit(self, net: int, nodes: set, edges: list) -> None:
        self.nodes[net] = nodes
        self.edges[net] = edges
        for v in nodes:
            self.occ[v] += 1
            self.own[v] = net

    def rip(self, net: int) -> None:
        for v in self.nodes.pop(net, ()):
            self.occ[v] -= 1
            if self.own[v] == net:
                self.own[v] = -1
        self.edges.pop(net, None)

    def snapshot(self) -> dict:
        return {k: (set(v), list(self.edges[k])) for k, v in self.nodes.items()}

    def restore(self, snap: dict) -> None:
        for net in list(self.nodes):
            self.rip(net)
        for net, (nodes, edges) in snap.items():
            self.commit(net, nodes, edges)


def _enter_cost(mode: str, occ: int, hist: float, pf: float, cross: float) -> float:
    """Kosten für das Betreten eines passierbaren Knotens; -1 heißt gesperrt."""
    if mode == "hard":
        return -1.0 if occ > 0 else 1.0
    if mode == "soft":
        return (1.0 + hist) * (1.0 + pf * occ)
    return 1.0 + hist + (cross if occ > 0 else 0.0)


def _nearest_target(board: Board, state: RouteState, net: int, sources, targets: set, mode: str, pf: float, cross: float, via_cost: float, box):
    """Dijkstra von allen Quellknoten zum nächsten Zielknoten innerhalb `box` = (xmin, xmax, ymin, ymax). Gibt (Zielknoten, Vorgänger) oder (None, None)."""
    w, cells = board.width, board.cells
    xmin, xmax, ymin, ymax = box
    fixed, occ, hist = board.fixed, state.occ, state.hist
    dist = {s: 0.0 for s in sources}
    prev: dict = {}
    heap = [(0.0, s) for s in sources]
    heapq.heapify(heap)
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        if u in targets:
            return u, prev
        layer = u // cells
        r = u - layer * cells
        y = r // w
        x = r - y * w
        steps = []
        if x > xmin:
            steps.append((u - 1, 0.0))
        if x < xmax:
            steps.append((u + 1, 0.0))
        if y > ymin:
            steps.append((u - w, 0.0))
        if y < ymax:
            steps.append((u + w, 0.0))
        steps.append((u + cells if layer == 0 else u - cells, via_cost))
        for v, extra in steps:
            f = fixed[v]
            if f != FREE and f != net:
                continue
            c = _enter_cost(mode, occ[v], hist[v], pf, cross)
            if c < 0:
                continue
            nd = d + c + extra
            if nd < dist.get(v, 1e18):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))
    return None, None


def _grow(board: Board, state: RouteState, net: int, mode: str, pf: float, cross: float, via_cost: float, box):
    """Baut den Baum des Netzes Pad für Pad: vom bisherigen Baum zum nächstgelegenen unverbundenen Pad. Gibt (Knotenmenge, Kanten) oder None."""
    cells = board.cells
    pads = board.pads[net]
    tree = {pads[0], pads[0] + cells}
    edges: list = []
    remaining = set(pads[1:])
    while remaining:
        targets = set()
        for p in remaining:
            targets.add(p)
            targets.add(p + cells)
        state.searches += 1
        hit, prev = _nearest_target(board, state, net, tree, targets, mode, pf, cross, via_cost, box)
        if hit is None:
            return None
        path, v = [], hit
        while v not in tree:
            path.append(v)
            edges.append((prev[v], v))
            v = prev[v]
        for v in path:
            tree.add(v)
            if board.fixed[v] == net:       # Durchsteckpad des eigenen Netzes: beide Lagen sind ohne Via verbunden
                tree.add(v + cells if v < cells else v - cells)
        remaining = {p for p in remaining if p not in tree and p + cells not in tree}
    return tree, edges


def route_net(board: Board, state: RouteState, net: int, mode: str, via_cost: float, pf: float = 0.0, cross: float = C.RRR_CROSS):
    """Verlegt ein Netz zuerst im Rechteck seiner Pads plus Rand, bei Misserfolg auf dem ganzen Brett. Gibt (Knotenmenge, Kanten) oder None."""
    w = board.width
    xs = [p % w for p in board.pads[net]]
    ys = [p // w for p in board.pads[net]]
    full = (0, board.width - 1, 0, board.height - 1)
    near = (max(0, min(xs) - C.MARGIN), min(board.width - 1, max(xs) + C.MARGIN), max(0, min(ys) - C.MARGIN), min(board.height - 1, max(ys) + C.MARGIN))
    result = _grow(board, state, net, mode, pf, cross, via_cost, near)
    if result is None and near != full:
        result = _grow(board, state, net, mode, pf, cross, via_cost, full)
    return result
