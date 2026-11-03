"""Bestückung: Bauteile einer platzierten Platine automatisch setzen. Ein Portalautomat holt Teile von Zuführplätzen (eine Reihe unter der Platine) und setzt sie.

Entscheidungen: (1) welcher Bauteiltyp auf welchen Zuführplatz, (2) in welcher Reihenfolge gesetzt wird (bei einem Kopf mit k Düsen: erst k Teile holen, dann k setzen,
Reihenfolge = Folge der Runden). Fahrstrecke: Tschebyscheff-Abstand (beide Achsen fahren gleichzeitig), Einheit Rasterzelle."""

import itertools
import math
from dataclasses import dataclass

import lpl_constants as C
from lpl_rng import SplitMix64
from lpl_scenario import Instance, dims


@dataclass(frozen=True)
class FeederInstance:
    names: tuple       # Bauteilname je Bestückort (U1, C1, ...)
    positions: tuple   # (x, y) der Bauteilmitte je Bestückort
    types: tuple       # Typnummer je Bestückort
    type_names: tuple  # Name je Typ
    slots: tuple       # (x, y) der Zuführplätze
    home: tuple        # Ausgangsposition des Kopfes

    @property
    def n(self) -> int:
        return len(self.positions)

    @property
    def n_types(self) -> int:
        return len(self.type_names)

    @property
    def n_slots(self) -> int:
        return len(self.slots)


@dataclass(frozen=True)
class FeederPlan:
    method: str
    assignment: tuple   # Zuführplatz je Typ
    sequence: tuple     # Reihenfolge der Bestückorte
    cost: float
    evaluations: int    # Zahl der Kostenauswertungen (gleiches Budget für alle Suchverfahren)


def dist(a, b) -> float:
    """Tschebyscheff-Abstand: beide Achsen fahren gleichzeitig."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def type_label(fp) -> str:
    return f"IC mit {len(fp.pins)} Pins" if fp.kind == "ic" else ("Kondensator" if fp.name.startswith("C") else "Widerstand")


def make_feeder_instance(inst: Instance, poses: list, extra_slots: int = C.BST_EXTRA_SLOTS) -> FeederInstance:
    """Bestückorte = alle Bauteile außer den Steckern (die setzt der Automat nicht); Typ = Gehäuseart. Zuführplätze mittig unter dem Brett im Abstand BST_PITCH."""
    names, positions, types, labels = [], [], [], {}
    for fp, pose in zip(inst.comps, poses):
        if fp.kind == "conn":
            continue
        w, h = dims(fp, pose[2])
        names.append(fp.name)
        positions.append((pose[0] + w / 2.0, pose[1] + h / 2.0))
        types.append(labels.setdefault(type_label(fp), len(labels)))
    n_slots = len(labels) + extra_slots
    slot_y = inst.height + C.BST_ROW_OFFSET
    x0 = (inst.width - C.BST_PITCH * (n_slots - 1)) / 2.0
    slots = tuple((x0 + C.BST_PITCH * k, float(slot_y)) for k in range(n_slots))
    return FeederInstance(tuple(names), tuple(positions), tuple(types), tuple(labels), slots, (0.0, float(slot_y)))


# ---------------------------------------------------------------- Kosten einer Runde und einer Folge
def round_route(fi: FeederInstance, assignment, block, start):
    """Beste Fahrt einer Runde ab `start`: alle Zuführplätze der Runde auf der Geraden anfahren (zwei Richtungen, ein Überstreichen von Ende zu Ende ist nie schlechter
    als ein innerer Einstieg) und danach die Teile der Runde in der besten der k! Reihenfolgen setzen. Gibt (Kosten, Endposition, Punktfolge)."""
    slot_xs = sorted({fi.slots[assignment[fi.types[j]]][0] for j in block})
    slot_y = fi.slots[0][1]
    best = None
    for first, last in ((slot_xs[0], slot_xs[-1]), (slot_xs[-1], slot_xs[0])):
        base = dist(start, (first, slot_y)) + abs(last - first)
        for perm in itertools.permutations(block):
            cur = (last, slot_y)
            c = base
            for j in perm:
                c += dist(cur, fi.positions[j])
                cur = fi.positions[j]
            if best is None or c < best[0] - 1e-12:
                best = (c, cur, (start, (first, slot_y), (last, slot_y)) + tuple(fi.positions[j] for j in perm), len(slot_xs))
    return best[0], best[1], best[2]


class RoundCache:
    """Merkt sich Rundenkosten je (Zuordnung, Runde, Startpunkt): bei Reihenfolge-Zügen bleiben die meisten Runden unverändert."""

    def __init__(self, fi: FeederInstance):
        self.fi = fi
        self.memo: dict = {}

    def cost(self, assignment: tuple, block: tuple, start: tuple):
        key = (assignment, block, start)
        hit = self.memo.get(key)
        if hit is None:
            c, end, _ = round_route(self.fi, assignment, block, start)
            hit = (c, end)
            self.memo[key] = hit
        return hit


def total_cost(fi: FeederInstance, assignment: tuple, sequence: tuple, k: int, cache: RoundCache | None = None) -> float:
    """Fahrstrecke der ganzen Bestückung: Runden nacheinander, am Ende zurück zur Ausgangsposition."""
    cache = cache or RoundCache(fi)
    cur = fi.home
    total = 0.0
    for i in range(0, len(sequence), k):
        c, cur = cache.cost(assignment, tuple(sequence[i:i + k]), cur)
        total += c
    return total + dist(cur, fi.home)


def plan_route(fi: FeederInstance, plan: FeederPlan, k: int) -> list:
    """Punktfolgen je Runde (Holen und Setzen) für die Zeichnung: [(Runde, Punktfolge, Zahl der Zuführplätze)]."""
    cur = fi.home
    out = []
    for r, i in enumerate(range(0, len(plan.sequence), k)):
        c, cur, pts = round_route(fi, plan.assignment, tuple(plan.sequence[i:i + k]), cur)
        out.append((r, pts))
    return out


# ---------------------------------------------------------------- Zuordnung
def frequency_assignment(fi: FeederInstance) -> tuple:
    """Maschinenpraxis: häufigste Typen auf die mittleren Plätze."""
    counts = [0] * fi.n_types
    for t in fi.types:
        counts[t] += 1
    order = sorted(range(fi.n_types), key=lambda t: (-counts[t], t))
    middle = sorted(range(fi.n_slots), key=lambda s: (abs(s - (fi.n_slots - 1) / 2.0), s))
    out = [0] * fi.n_types
    for rank, t in enumerate(order):
        out[t] = middle[rank]
    return tuple(out)


def assign_by_matrix(cost: list) -> tuple:
    """Kostenminimale Zuordnung der Zeilen (Typen) auf verschiedene Spalten (Plätze): Ungarische Methode."""
    from scipy.optimize import linear_sum_assignment

    rows, cols = linear_sum_assignment(cost)
    out = [0] * len(cost)
    for r, c in zip(rows, cols):
        out[r] = int(c)
    return tuple(out)


def centroid_assignment(fi: FeederInstance) -> tuple:
    """Zuordnung nach Schwerpunkten: Kosten Typ t auf Platz s = doppelte Abstandssumme von Platz s zu allen Bestückorten des Typs (Hin- und Rückweg)."""
    cost = [[0.0] * fi.n_slots for _ in range(fi.n_types)]
    for j, t in enumerate(fi.types):
        for s in range(fi.n_slots):
            cost[t][s] += 2 * dist(fi.positions[j], fi.slots[s])
    return assign_by_matrix(cost)


def assignment_given_sequence_k1(fi: FeederInstance, sequence: tuple) -> tuple:
    """Einzeldüse bei fester Reihenfolge: jeder Summand der Fahrt hängt von genau einem Platz ab, die Zuordnung ist ein lineares Problem (exakt)."""
    cost = [[0.0] * fi.n_slots for _ in range(fi.n_types)]
    prev = fi.home
    for j in sequence:
        for s in range(fi.n_slots):
            cost[fi.types[j]][s] += dist(prev, fi.slots[s]) + dist(fi.slots[s], fi.positions[j])
        prev = fi.positions[j]
    return assign_by_matrix(cost)


# ---------------------------------------------------------------- Reihenfolge
def greedy_rounds(fi: FeederInstance, assignment: tuple, k: int) -> tuple:
    """Konstruktion: Runde für Runde die jeweils nächsten Bestückorte (vom letzten gesetzten Teil aus) in dieselbe Runde nehmen."""
    left = list(range(fi.n))
    cur = fi.home
    out = []
    while left:
        group = []
        for _ in range(min(k, len(left))):
            ref = cur if not group else fi.positions[group[-1]]
            j = min(left, key=lambda q: (dist(ref, fi.positions[q]), q))
            group.append(j)
            left.remove(j)
        out += group
        cur = fi.positions[group[-1]]
    return tuple(out)


def swap_move(sequence: tuple, rng: SplitMix64) -> tuple | None:
    """Tauscht zwei Positionen der Reihenfolge."""
    i, j = rng.below(len(sequence)), rng.below(len(sequence))
    if i == j:
        return None
    s = list(sequence)
    s[i], s[j] = s[j], s[i]
    return tuple(s)


def metropolis(delta: float, temp: float, rng: SplitMix64) -> bool:
    return delta <= 0 or rng.random() < math.exp(-delta / temp)


def sequence_search(fi, assignment, sequence, k, iters, rng, cache, evals=None):
    """Simulated Annealing nur über die Reihenfolge (Zuordnung fest); gibt (beste Folge, Kosten)."""
    cur = total_cost(fi, assignment, sequence, k, cache)
    best = (cur, sequence)
    t0 = max(cur / fi.n * 0.25, 1e-9)
    t1 = t0 * 0.02
    for it in range(iters):
        temp = t0 * (t1 / t0) ** (it / max(1, iters))
        new = swap_move(sequence, rng)
        if new is None:
            continue
        c = total_cost(fi, assignment, new, k, cache)
        if metropolis(c - cur, temp, rng):
            sequence, cur = new, c
            if cur < best[0]:
                best = (cur, sequence)
    return best[1], best[0]


def slot_move(assignment: tuple, fi: FeederInstance, rng: SplitMix64) -> tuple | None:
    """Tauscht die Plätze zweier Typen oder setzt einen Typ auf einen freien Platz."""
    a = rng.below(fi.n_types)
    out = list(assignment)
    if rng.below(2) == 0:
        b = rng.below(fi.n_types)
        if a == b:
            return None
        out[a], out[b] = out[b], out[a]
    else:
        free = [s for s in range(fi.n_slots) if s not in assignment]
        if not free:
            return None
        out[a] = free[rng.below(len(free))]
    return tuple(out)


def slot_descent(fi, assignment, sequence, k, cache):
    """Platzwechsel (Tausch oder freier Platz), solange einer die Fahrt verkürzt. Gibt (Zuordnung, Kosten, Zahl der Auswertungen)."""
    cur = total_cost(fi, assignment, sequence, k, cache)
    evals = 1
    improved = True
    while improved:
        improved = False
        for a in range(fi.n_types):
            candidates = [("swap", b) for b in range(a + 1, fi.n_types)] + [("free", s) for s in range(fi.n_slots) if s not in assignment]
            for kind, b in candidates:
                trial = list(assignment)
                if kind == "swap":
                    trial[a], trial[b] = trial[b], trial[a]
                else:
                    trial[a] = b
                trial = tuple(trial)
                c = total_cost(fi, trial, sequence, k, cache)
                evals += 1
                if c < cur - 1e-9:
                    assignment, cur, improved = trial, c, True
    return assignment, cur, evals


# ---------------------------------------------------------------- Verfahren
def solve_naive(fi, k, budget, seed) -> FeederPlan:
    a = frequency_assignment(fi)
    s = greedy_rounds(fi, a, k)
    return FeederPlan(C.BST_METHODS[0], a, s, total_cost(fi, a, s, k), 1)


def solve_separated(fi, k, budget, seed) -> FeederPlan:
    """Erst die Plätze (Ungarische Methode nach Schwerpunkten), danach nur noch die Reihenfolge verbessern."""
    cache = RoundCache(fi)
    a = centroid_assignment(fi)
    s, c = sequence_search(fi, a, greedy_rounds(fi, a, k), k, budget, SplitMix64(seed * 31 + 1), cache)
    return FeederPlan(C.BST_METHODS[1], a, s, c, budget + 1)


def solve_alternating(fi, k, budget, seed) -> FeederPlan:
    """Reihenfolge verbessern, dann Plätze verbessern, dann wieder die Reihenfolge, bis das Budget verbraucht ist."""
    cache = RoundCache(fi)
    rng = SplitMix64(seed * 31 + 2)
    a = centroid_assignment(fi)
    first = max(1, budget // 3)
    s, c = sequence_search(fi, a, greedy_rounds(fi, a, k), k, first, rng, cache)
    used = first
    while used < budget:
        a, c, n = slot_descent(fi, a, s, k, cache)
        used += n
        step = min(max(1, budget // 6), budget - used)
        if step <= 0:
            break
        s, c = sequence_search(fi, a, s, k, step, rng, cache)
        used += step
    return FeederPlan(C.BST_METHODS[2], a, s, c, used)


def solve_joint(fi, k, budget, seed) -> FeederPlan:
    """Simulated Annealing über Plätze und Reihenfolge zugleich (Platzzüge in 15 % der Schritte)."""
    cache = RoundCache(fi)
    rng = SplitMix64(seed * 31 + 3)
    a = centroid_assignment(fi)
    s = greedy_rounds(fi, a, k)
    cur = total_cost(fi, a, s, k, cache)
    best = (cur, a, s)
    t0 = max(cur / fi.n * 0.25, 1e-9)
    t1 = t0 * 0.02
    for it in range(budget):
        temp = t0 * (t1 / t0) ** (it / max(1, budget))
        if rng.below(100) < 15:
            na = slot_move(a, fi, rng)
            if na is None:
                continue
            c = total_cost(fi, na, s, k, cache)
            if metropolis(c - cur, temp, rng):
                a, cur = na, c
        else:
            ns = swap_move(s, rng)
            if ns is None:
                continue
            c = total_cost(fi, a, ns, k, cache)
            if metropolis(c - cur, temp, rng):
                s, cur = ns, c
        if cur < best[0]:
            best = (cur, a, s)
    return FeederPlan(C.BST_METHODS[3], best[1], best[2], best[0], budget + 1)


SOLVERS = (solve_naive, solve_separated, solve_alternating, solve_joint)


def budget_for(fi: FeederInstance) -> int:
    """Gleiches Budget an Kostenauswertungen für alle Suchverfahren, proportional zur Zahl der Bestückorte."""
    return C.BST_EVALS_PER_PART * fi.n


def solve_all(fi: FeederInstance, k: int, seed: int) -> tuple:
    budget = budget_for(fi)
    return tuple(solver(fi, k, budget, seed) for solver in SOLVERS)


def check_plan(fi: FeederInstance, plan: FeederPlan, k: int) -> list:
    """Unabhängiger Prüfer: Fehlermeldungen (leer = zulässig). Jeder Typ auf genau einem Platz, Plätze verschieden, jeder Bestückort genau einmal,
    und die gemeldeten Kosten stimmen mit einer frischen Berechnung überein."""
    errors = []
    if len(plan.assignment) != fi.n_types or any(not 0 <= s < fi.n_slots for s in plan.assignment):
        errors.append("Zuordnung ungültig")
    elif len(set(plan.assignment)) != fi.n_types:
        errors.append("zwei Typen auf demselben Zuführplatz")
    if sorted(plan.sequence) != list(range(fi.n)):
        errors.append("Reihenfolge enthält nicht jeden Bestückort genau einmal")
    if not errors and abs(total_cost(fi, plan.assignment, plan.sequence, k) - plan.cost) > 1e-6:
        errors.append("gemeldete Kosten weichen von der Neuberechnung ab")
    return errors
