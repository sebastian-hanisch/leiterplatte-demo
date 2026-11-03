"""Exakter Löser für Mini-Bretter mit 2-Pin-Netzen: knotendisjunkte Wege minimaler Kosten als Ganzzahlmodell (OR-Tools CP-SAT)."""

from dataclasses import dataclass

import lpl_constants as C
from lpl_grid import FREE, Board
from lpl_router import Routing


@dataclass(frozen=True)
class ExactResult:
    status: str            # "optimal", "feasible" (Zeitgrenze, Lösung ohne Beweis), "infeasible" (bewiesen unlösbar) oder "unknown" (Zeitgrenze ohne Lösung)
    cost: float | None     # Kosten der Lösung (Schritte + Via-Schritte zu 1 + via_cost)
    routing: Routing | None


def _arcs(board: Board, via_cost: float) -> list:
    """Alle gerichteten Bögen des Rasters mit Kosten: Schritt 1, Via 1 + via_cost."""
    w, cells = board.width, board.cells
    arcs = []
    for u in range(board.nodes):
        layer, r = divmod(u, cells)
        y, x = divmod(r, w)
        steps = []
        if x > 0:
            steps.append((u - 1, 1.0))
        if x < w - 1:
            steps.append((u + 1, 1.0))
        if y > 0:
            steps.append((u - w, 1.0))
        if y < board.height - 1:
            steps.append((u + w, 1.0))
        steps.append((u + cells if layer == 0 else u - cells, 1.0 + via_cost))
        arcs += [(u, v, c) for v, c in steps]
    return arcs


def solve_exact(board: Board, via_cost: float, time_limit: float = C.EXACT_TIME_LIMIT) -> ExactResult:
    """Kostenminimale knotendisjunkte Verlegung aller Netze. Je Netz fließt eine Einheit von einem Pad (beide Lagen erlaubt) zum anderen; jeder Knoten trägt höchstens ein Netz.
    Ganzzahlige Kosten (via_cost ganzzahlig) machen das Optimum eindeutig im Wert, nicht in der Lösung."""
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    cells = board.cells
    arcs = _arcs(board, via_cost)
    cost_scale = 1000
    usage: list = [[] for _ in range(board.nodes)]
    objective = []
    arc_vars: dict = {}
    for k, (s, t) in enumerate(board.pads):
        def allowed(v, k=k):
            return board.fixed[v] in (FREE, k)

        inflow = {v: [] for v in range(board.nodes)}
        outflow = {v: [] for v in range(board.nodes)}
        for idx, (u, v, c) in enumerate(arcs):
            if allowed(u) and allowed(v):
                b = model.NewBoolVar(f"a{k}_{idx}")
                arc_vars[(k, idx)] = b
                outflow[u].append(b)
                inflow[v].append(b)
                objective.append(int(round(c * cost_scale)) * b)
        start = {s: model.NewBoolVar(""), s + cells: model.NewBoolVar("")}
        goal = {t: model.NewBoolVar(""), t + cells: model.NewBoolVar("")}
        model.Add(sum(start.values()) == 1)
        model.Add(sum(goal.values()) == 1)
        for v in range(board.nodes):
            if not allowed(v):
                continue
            into = list(inflow[v]) + ([start[v]] if v in start else [])
            out = list(outflow[v]) + ([goal[v]] if v in goal else [])
            model.Add(sum(into) == sum(out))
            if into:
                usage[v].append(sum(into))
    for v in range(board.nodes):
        if len(usage[v]) > 1:
            model.Add(sum(usage[v]) <= 1)
    model.Minimize(sum(objective))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = C.EXACT_WORKERS
    solver.parameters.random_seed = 1
    status = solver.Solve(model)
    if status == cp_model.INFEASIBLE:
        return ExactResult("infeasible", None, None)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return ExactResult("unknown", None, None)
    nodes, edges = {}, {}
    for (k, idx), b in arc_vars.items():
        if solver.Value(b):
            u, v, _ = arcs[idx]
            edges.setdefault(k, []).append((u, v))
            nodes.setdefault(k, set()).update((u, v))
    for k, (s, t) in enumerate(board.pads):
        nodes.setdefault(k, set()).update((s, s + cells, t, t + cells))
        edges.setdefault(k, [])
    routing = Routing("Exakt (CP-SAT)", (), {k: frozenset(v) for k, v in nodes.items()}, {k: tuple(v) for k, v in edges.items()})
    return ExactResult("optimal" if status == cp_model.OPTIMAL else "feasible", solver.ObjectiveValue() / cost_scale, routing)
