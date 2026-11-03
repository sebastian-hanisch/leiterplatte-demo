"""Instanz: Bauteile, Netzliste und Brettgröße (synthetisches Sensorboard). Alle Zufallsentscheidungen über SplitMix64."""

import math
from dataclasses import dataclass

import lpl_constants as C
from lpl_rng import SplitMix64


@dataclass(frozen=True)
class Footprint:
    """Bauteil im Grundzustand. Pins als (dx, dy) relativ zur linken oberen Ecke; Stecker sind fest am Brettrand."""

    name: str
    kind: str  # "conn" (Stecker), "ic" (Gehäuse sperrt die Oberseite) oder "pas" (Widerstand, Kondensator)
    w: int
    h: int
    pins: tuple
    fixed: bool = False


@dataclass(frozen=True)
class Instance:
    comps: tuple          # Footprint je Bauteil; 0 und 1 sind die festen Stecker links und rechts
    nets: tuple           # je Netz ein Tupel von (Bauteil, Pin)
    net_names: tuple
    width: int
    height: int


Pose = tuple  # (x, y, rot) mit rot 0 oder 1 (um 90 Grad gedreht)


def dims(fp: Footprint, rot: int) -> tuple[int, int]:
    """Breite und Höhe des Bauteils in der Drehung `rot`."""
    return (fp.w, fp.h) if rot == 0 else (fp.h, fp.w)


def pin_xy(fp: Footprint, pose: Pose, i: int) -> tuple[int, int]:
    """Brettkoordinate von Pin i; die Drehung bildet (dx, dy) auf (h - 1 - dy, dx) ab."""
    x, y, rot = pose
    dx, dy = fp.pins[i]
    if rot == 1:
        dx, dy = fp.h - 1 - dy, dx
    return x + dx, y + dy


def body_cells(fp: Footprint, pose: Pose) -> list[tuple[int, int]]:
    """Gehäuseinneres der ICs (Spalten zwischen den Pinreihen): nur die Oberseite ist dort gesperrt."""
    if fp.kind != "ic":
        return []
    x, y, rot = pose
    cells = []
    for ix in range(1, fp.w - 1):
        for iy in range(fp.h):
            dx, dy = (ix, iy) if rot == 0 else (fp.h - 1 - iy, ix)
            cells.append((x + dx, y + dy))
    return cells


def _components(rng: SplitMix64, n_ic: int) -> tuple[list, list, list, list]:
    """Stecker J1, J2, dann n_ic ICs, je IC ein Abblockkondensator, dann Pull-up-Widerstände. Gibt (Bauteile, IC-, Kondensator-, Widerstandsindizes)."""
    comps = []
    for name in ("J1", "J2"):
        comps.append(Footprint(name, "conn", 1, 2 * C.CONN_PINS - 1, tuple((0, 2 * r) for r in range(C.CONN_PINS)), fixed=True))
    ics, caps, pulls = [], [], []
    for i in range(n_ic):
        rows = rng.choice(C.IC_ROWS)
        pins = tuple((0, r) for r in range(rows)) + tuple((C.IC_WIDTH - 1, r) for r in range(rows))
        comps.append(Footprint(f"U{i + 1}", "ic", C.IC_WIDTH, rows, pins))
        ics.append(len(comps) - 1)
    for i in range(n_ic):
        comps.append(Footprint(f"C{i + 1}", "pas", 2, 1, ((0, 0), (1, 0))))
        caps.append(len(comps) - 1)
    for i in range(max(2, n_ic)):
        comps.append(Footprint(f"R{i + 1}", "pas", 2, 1, ((0, 0), (1, 0))))
        pulls.append(len(comps) - 1)
    return comps, ics, caps, pulls


def _signal_pool(rng: SplitMix64, comps: list, ics: list, used: set, pin_use_pct: int) -> dict:
    """Signalpins je Cluster: ICs wechselweise auf die Cluster verteilt, davon `pin_use_pct` Prozent der freien Pins; Stecker J1 gehört zu Cluster 0, J2 zum letzten."""
    pool = {c: [] for c in range(C.N_CLUSTERS)}
    for k, ci in enumerate(ics):
        free = [p for p in range(len(comps[ci].pins)) if (ci, p) not in used]
        rng.shuffle(free)
        for p in free[: (len(free) * pin_use_pct + 50) // 100]:
            pool[k % C.N_CLUSTERS].append((ci, p))
    for ci, cluster in ((0, 0), (1, C.N_CLUSTERS - 1)):
        for p in range(2, C.CONN_PINS):
            if rng.below(10) < 8:
                pool[cluster].append((ci, p))
    return pool


def _group_into_nets(rng: SplitMix64, pins: list) -> tuple[list, list]:
    """Teilt eine Pinliste in Netze von 2 bis 4 Pins (bevorzugt verschiedene Bauteile). Gibt (Netze, übrige einzelne Pins)."""
    pins = pins[:]
    rng.shuffle(pins)
    groups, rest = [], []
    while len(pins) >= 2:
        size = min(rng.weighted((2, 3, 4), (6, 3, 1)), len(pins))
        group = [pins.pop()]
        for _ in range(size - 1):
            other = [q for q in pins if q[0] not in {g[0] for g in group}]
            q = rng.choice(other) if other else pins[-1]
            pins.remove(q)
            group.append(q)
        groups.append(group)
    rest += pins
    return groups, rest


def board_size(comps, util_pct: int) -> tuple[int, int]:
    """Brettgröße aus der Dichte: Bauteilfläche samt Abstand geteilt durch die Brettfläche, Seitenverhältnis etwa 4 : 3."""
    area = sum((c.w + C.GAP) * (c.h + C.GAP) for c in comps)
    total = area * 100.0 / util_pct
    width = max(int(math.ceil(math.sqrt(total * 4 / 3))), 2 + max(c.w for c in comps))
    height = max(int(math.ceil(total / width)), max(c.h for c in comps) + 2)
    return width, height


def make_instance(n_ic: int, pin_use_pct: int, util_pct: int, seed: int) -> Instance:
    """Sensorboard: VCC und GND an allen Versorgungspins, Signalnetze mit 2 bis 4 Pins in Clustern, Pull-ups hängen an Signalnetzen und VCC."""
    rng = SplitMix64(seed)
    comps, ics, caps, pulls = _components(rng, n_ic)
    nets: dict[str, list] = {"VCC": [], "GND": []}
    used: set = set()

    def take(ci, pi, net):
        used.add((ci, pi))
        nets.setdefault(net, []).append((ci, pi))

    for ci in (0, 1):
        take(ci, 0, "VCC")
        take(ci, 1, "GND")
    for ci in ics:
        take(ci, 0, "VCC")
        take(ci, len(comps[ci].pins) - 1, "GND")
    for ci in caps:
        take(ci, 0, "VCC")
        take(ci, 1, "GND")
    pool = _signal_pool(rng, comps, ics, used, pin_use_pct)
    leftovers: list = []
    count = 0
    for cluster in range(C.N_CLUSTERS):
        groups, rest = _group_into_nets(rng, pool[cluster])
        leftovers += rest
        for group in groups:
            count += 1
            for ci, pi in group:
                take(ci, pi, f"S{count}")
    groups, _ = _group_into_nets(rng, leftovers)
    for group in groups:
        count += 1
        for ci, pi in group:
            take(ci, pi, f"S{count}")
    signal_names = sorted(k for k in nets if k.startswith("S"))
    for ci in pulls:
        take(ci, 1, "VCC")
        if signal_names:
            take(ci, 0, rng.choice(signal_names))
    names = [k for k in nets if len(nets[k]) >= 2]
    width, height = board_size(comps, util_pct)
    return Instance(tuple(comps), tuple(tuple(nets[k]) for k in names), tuple(names), width, height)
