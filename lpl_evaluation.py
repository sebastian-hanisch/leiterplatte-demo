"""Kennzahlen, Verdikt-Logik und Experimente über feste Instanzen. Verdikte sind reine Funktionen (Art, Text); die App ruft st.<Art>(Text)."""

from dataclasses import dataclass
from statistics import median

import lpl_constants as C
from lpl_grid import Board, build_board
from lpl_placement import check_placement, hpwl, net_hpwl, place
from lpl_rng import SplitMix64
from lpl_router import (
    Routing,
    check_feasible,
    net_order,
    route_negotiated,
    route_rrr,
    route_sequential,
    routing_cost,
    via_count,
    wirelength,
)
from lpl_scenario import Instance, make_instance


@dataclass(frozen=True)
class Settings:
    n_ic: int = C.DEFAULT_N_IC
    util: int = C.DEFAULT_UTIL
    pin_use: int = C.DEFAULT_PIN_USE
    placement: str = C.DEFAULT_PLACEMENT
    order: str = C.DEFAULT_ORDER
    via_cost: int = C.DEFAULT_VIA
    iterations: int = C.DEFAULT_ITER
    seed: int = C.DEFAULT_SEED


@dataclass(frozen=True)
class Analysis:
    settings: Settings
    inst: Instance
    poses: list
    board: Board
    net_hpwl: tuple          # HPWL je Netz
    hpwl: int
    order: tuple
    routings: dict           # Verfahren -> Routing
    metrics: dict            # Verfahren -> Kennzahlen (siehe `metrics_of`)
    violations: dict         # Verfahren -> Fehlermeldungen des unabhängigen Prüfers (leer = in Ordnung)


def metrics_of(board: Board, hp_nets: tuple, routing: Routing, via_cost: float) -> dict:
    """Kennzahlen einer Verlegung. Länge und Vias gelten nur für die verlegten Netze; `detour` = Länge / HPWL derselben Netze."""
    routed = sorted(routing.nodes)
    hp = sum(hp_nets[n] for n in routed)
    wl = wirelength(board, routing)
    return {
        "nets": len(board.pads),
        "routed": len(routed),
        "failed": len(routing.failed),
        "wirelength": wl,
        "vias": via_count(board, routing),
        "cost": routing_cost(board, routing, via_cost),
        "detour": (wl / hp) if hp else 0.0,
        "searches": routing.searches,
        "iterations": routing.iterations,
        "converged": routing.converged,
    }


def prepare(settings: Settings) -> tuple:
    """Instanz, Platzierung, Raster, HPWL je Netz und Netzreihenfolge."""
    inst = make_instance(settings.n_ic, settings.pin_use, settings.util, settings.seed)
    poses = place(inst, settings.placement, settings.seed)
    board = build_board(inst, poses)
    hp_nets = tuple(net_hpwl(inst, poses, net) for net in inst.nets)
    order = tuple(net_order(list(hp_nets), settings.order, settings.seed))
    return inst, poses, board, hp_nets, order


def analyse(settings: Settings) -> Analysis:
    """Platziert und verlegt mit allen drei Regeln; der unabhängige Prüfer läuft für jede Verlegung."""
    inst, poses, board, hp_nets, order = prepare(settings)
    v = float(settings.via_cost)
    routings = {
        C.METHODS[0]: route_sequential(board, list(order), v),
        C.METHODS[1]: route_rrr(board, list(order), v),
        C.METHODS[2]: route_negotiated(board, list(order), v, settings.iterations),
    }
    metrics = {m: metrics_of(board, hp_nets, r, v) for m, r in routings.items()}
    violations = {m: check_feasible(board, r) + (check_placement(inst, poses) if m == C.METHODS[0] else []) for m, r in routings.items()}
    return Analysis(settings, inst, poses, board, hp_nets, sum(hp_nets), order, routings, metrics, violations)


# ---------------------------------------------------------------- Experiment: Reihenfolge
def random_orders(n_nets: int, samples: int, seed: int) -> list:
    """`samples` Zufallsreihenfolgen der Netze, jede aus eigenem Strom."""
    out = []
    for s in range(samples):
        idx = list(range(n_nets))
        SplitMix64(seed * 1000003 + s * 7919 + 5).shuffle(idx)
        out.append(idx)
    return out


def order_spread(a: Analysis, samples: int = C.ORDER_SAMPLES) -> dict:
    """Sequentielles Verlegen derselben Platzierung in den vier Standardreihenfolgen und `samples` Zufallsreihenfolgen: Zahl unverlegter Netze je Lauf."""
    v = float(a.settings.via_cost)
    fixed = {}
    for kind in C.ORDERS[:3]:
        o = net_order(list(a.net_hpwl), kind, a.settings.seed)
        fixed[kind] = len(route_sequential(a.board, o, v).failed)
    rand = [len(route_sequential(a.board, o, v).failed) for o in random_orders(len(a.board.pads), samples, a.settings.seed)]
    return {"fixed": fixed, "random": rand}


# ---------------------------------------------------------------- Experiment: Verfahren über feste Instanzen
def method_row(settings: Settings) -> dict:
    """Eine Instanz: unverlegte Netze je Verfahren, dazu die beste von ORDER_SAMPLES Zufallsreihenfolgen (sequentiell)."""
    a = analyse(settings)
    spread = order_spread(a)
    return {
        "seed": settings.seed,
        "nets": len(a.inst.nets),
        "sequential": a.metrics[C.METHODS[0]]["failed"],
        "best_random_order": min(spread["random"]),
        "worst_random_order": max(spread["random"]),
        "rrr": a.metrics[C.METHODS[1]]["failed"],
        "negotiated": a.metrics[C.METHODS[2]]["failed"],
        "converged": a.metrics[C.METHODS[2]]["converged"],
        "iterations": a.metrics[C.METHODS[2]]["iterations"],
        "violations": sum(len(v) for v in a.violations.values()),
    }


def method_sweep(util: int, seeds=C.SWEEP_SEEDS, base: Settings = Settings()) -> list:
    return [method_row(Settings(base.n_ic, util, base.pin_use, base.placement, base.order, base.via_cost, base.iterations, s)) for s in seeds]


def summarize_methods(rows: list) -> dict:
    """Zahl der Instanzen, in denen das Verfahren alle Netze verlegt."""
    keys = {"sequential": "sequential", "best_random_order": "best_random_order", "rrr": "rrr", "negotiated": "negotiated"}
    return {name: sum(1 for r in rows if r[key] == 0) for name, key in keys.items()} | {"n": len(rows)}


# ---------------------------------------------------------------- Experiment: Platzierung
def placement_row(settings: Settings, method: str) -> dict:
    """Eine Platzierungsart bei sonst gleichen Einstellungen: HPWL und unverlegte Netze von Rip-up und Negotiated Congestion."""
    s = Settings(settings.n_ic, settings.util, settings.pin_use, method, settings.order, settings.via_cost, settings.iterations, settings.seed)
    a = analyse(s)
    return {
        "placement": method,
        "hpwl": a.hpwl,
        "sequential": a.metrics[C.METHODS[0]]["failed"],
        "rrr": a.metrics[C.METHODS[1]]["failed"],
        "negotiated": a.metrics[C.METHODS[2]]["failed"],
        "wirelength": a.metrics[C.METHODS[2]]["wirelength"],
        "converged": a.metrics[C.METHODS[2]]["converged"],
    }


def placement_comparison(settings: Settings) -> list:
    return [placement_row(settings, m) for m in C.PLACEMENTS]


# ---------------------------------------------------------------- Experiment: Via-Kosten
def via_comparison(settings: Settings, costs=(1, 4, 12, 30)) -> list:
    """Negotiated Congestion bei verschiedenen Via-Kosten auf derselben Platzierung."""
    inst, poses, board, hp_nets, order = prepare(settings)
    rows = []
    for c in costs:
        r = route_negotiated(board, list(order), float(c), settings.iterations)
        m = metrics_of(board, hp_nets, r, float(c))
        rows.append({"via_cost": c, "failed": m["failed"], "vias": m["vias"], "wirelength": m["wirelength"], "converged": m["converged"]})
    return rows


# ---------------------------------------------------------------- Rangfolge der Verfahren
def full_routing_rank(a: Analysis) -> list:
    """Verfahren geordnet nach unverlegten Netzen (aufsteigend), bei Gleichstand nach Kosten."""
    return sorted(a.metrics, key=lambda m: (a.metrics[m]["failed"], a.metrics[m]["cost"]))


# ---------------------------------------------------------------- Verdikte
def _g(x: float) -> str:
    """Zahl ohne überflüssige Nachkommastellen, mit Dezimalkomma."""
    return f"{x:g}".replace(".", ",")


def verdict_methods(metrics: dict) -> tuple[str, str]:
    """Kernergebnis der Verlegeregeln auf der gewählten Instanz."""
    s, r, p = (metrics[m] for m in C.METHODS)
    n = s["nets"]
    head = f"Von {n} Netzen bleiben sequentiell **{s['failed']}**, mit Rip-up **{r['failed']}** und mit Negotiated Congestion **{p['failed']}** unverlegt."
    if p["failed"] == 0 and s["failed"] > 0:
        return "success", head + " Verhandeln bringt hier alle Netze unter, die einfache Reihenfolge nicht."
    if p["failed"] == 0 and s["failed"] == 0:
        return "info", head + " Das Brett ist so locker, dass schon die einfache Reihenfolge alles unterbringt: hier gibt es nichts zu verhandeln."
    if not p["converged"]:
        return "warning", head + f" Negotiated Congestion hat nach {p['iterations']} Iterationen keinen konfliktfreien Stand erreicht; angezeigt wird die größte konfliktfreie Teilmenge."
    return "warning", head + " Auch Verhandeln schafft nicht alle Netze: das Brett ist zu dicht oder das Verfahren findet die Lösung nicht (es beweist keine Unlösbarkeit)."


def verdict_order(spread: dict, n_nets: int) -> tuple[str, str]:
    """Wie stark streut die Zahl unverlegter Netze allein durch die Reihenfolge?"""
    rand = spread["random"]
    lo, hi, med = min(rand), max(rand), median(rand)
    fixed = spread["fixed"]
    text = (f"Dieselbe Platzierung, dasselbe sequentielle Verlegen, nur die Reihenfolge der {n_nets} Netze ändert sich: bei {len(rand)} Zufallsreihenfolgen bleiben "
            f"**{lo} bis {hi}** Netze unverlegt (Median {_g(med)}). Kurze zuerst: {fixed[C.ORDERS[0]]}, lange zuerst: {fixed[C.ORDERS[1]]}, Netzliste: {fixed[C.ORDERS[2]]}.")
    if hi > lo:
        return "success", text + " Die Reihenfolge allein entscheidet also mit."
    return "info", text + " Auf diesem Brett ist die Reihenfolge ohne Wirkung (alle Läufe gleich)."


def verdict_placement(rows: list) -> tuple[str, str]:
    """Hängt die Verlegbarkeit an der Netzlänge? Vergleicht die Platzierung mit der kleinsten HPWL mit der mit den wenigsten unverlegten Netzen (Negotiated Congestion)."""
    shortest = min(rows, key=lambda r: (r["hpwl"], r["negotiated"]))
    easiest = min(rows, key=lambda r: (r["negotiated"], r["hpwl"]))
    body = "; ".join(f"{r['placement']}: HPWL {r['hpwl']}, unverlegt {r['negotiated']}" for r in rows)
    if shortest["negotiated"] > easiest["negotiated"]:
        return "warning", f"{body}. Die Platzierung mit der kleinsten Netzlänge ({shortest['placement']}) ist hier **nicht** die am besten verlegbare ({easiest['placement']})."
    return "info", f"{body}. Die Platzierung mit der kleinsten Netzlänge ({shortest['placement']}) lässt auch hier die wenigsten Netze unverlegt (Gleichstände eingeschlossen); das gilt für diese Instanz, nicht allgemein."


def verdict_via(rows: list) -> tuple[str, str]:
    """Via-Kosten: wie weit sinkt die Via-Zahl, was kostet es an Länge?"""
    first, last = rows[0], rows[-1]
    saved = first["vias"] - last["vias"]
    text = (f"Via-Kosten {first['via_cost']} → {last['via_cost']}: Vias {first['vias']} → {last['vias']}, Länge {first['wirelength']} → {last['wirelength']} Zellen; "
            f"unverlegt {first['failed']} → {last['failed']}.")
    if saved > 0:
        return "info", text + f" Teure Vias sparen {saved} Vias und verlängern die Leiterbahnen."
    return "info", text + " Teure Vias sparen hier keine Vias."


def verdict_exact(scan, rrr: Routing, pf: Routing, exact, n_nets: int) -> tuple[str, str]:
    """Mini-Brett: Aufzählung aller Reihenfolgen gegen Rip-up, Negotiated Congestion und den bewiesenen Optimalwert."""
    head = f"Sequentiell klappt in **{scan.successes} von {scan.n_orders}** Reihenfolgen."
    solved = [m.method for m in (rrr, pf) if not m.failed]
    heur = "Rip-up und Negotiated Congestion finden beide eine Lösung" if len(solved) == 2 else (
        f"Nur {solved[0]} findet eine Lösung" if solved else "Weder Rip-up noch Negotiated Congestion finden eine Lösung")
    if exact.status == "infeasible":
        if solved:
            return "error", f"{head} Der Löser beweist, dass es keine Verlegung gibt, und trotzdem meldet ein Verfahren Erfolg: Widerspruch, bitte melden."
        return "info", (f"{head} Der Löser **beweist: es gibt keine Verlegung** aller {n_nets} Netze auf diesem Brett. "
                        "Deshalb bleiben auch bei Rip-up und Negotiated Congestion Netze unverlegt; das ist hier kein Mangel des Verfahrens.")
    if exact.status == "unknown":
        return "warning", f"{head} Der Löser fand in der Zeitgrenze keine Lösung und konnte nichts beweisen."
    proof = "Optimum bewiesen" if exact.status == "optimal" else "beste gefundene Lösung, nicht bewiesen optimal"
    if scan.successes == 0 and exact.cost is not None:
        return "success", f"{head} Obwohl der Löser eine Lösung zeigt (Kosten {_g(exact.cost)}, {proof}): **keine Reihenfolge schafft es.** {heur}."
    return "info", f"{head} Der Löser: Kosten {_g(exact.cost)} ({proof}). {heur}."
