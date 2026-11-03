"""Platzierung: legale Lagen, Zufall, quadratische Platzierung mit Legalisierung und Simulated Annealing auf der Halbumfangs-Netzlänge (HPWL)."""

import math
from collections import defaultdict

import numpy as np

import lpl_constants as C
from lpl_rng import SplitMix64
from lpl_scenario import Instance, Pose, dims, pin_xy


class PlacementError(Exception):
    """Das Brett ist zu dicht: es gibt keine überlappungsfreie Lage für alle Bauteile."""


def fixed_poses(inst: Instance) -> list:
    """Lagen der Stecker: J1 am linken, J2 am rechten Rand, senkrecht mittig."""
    left, right = inst.comps[0], inst.comps[1]
    return [(0, (inst.height - left.h) // 2, 0), (inst.width - 1, (inst.height - right.h) // 2, 0)]


def is_legal(inst: Instance, poses: list, i: int, pose: Pose, others) -> bool:
    """Liegt Bauteil i in `pose` im Brett und mit mindestens GAP Abstand zu allen Bauteilen aus `others` (ohne i selbst)?"""
    x, y, rot = pose
    w, h = dims(inst.comps[i], rot)
    if x < 0 or y < 0 or x + w > inst.width or y + h > inst.height:
        return False
    for j in others:
        if j == i:
            continue
        ox, oy, orot = poses[j]
        ow, oh = dims(inst.comps[j], orot)
        if not (x + w + C.GAP <= ox or ox + ow + C.GAP <= x or y + h + C.GAP <= oy or oy + oh + C.GAP <= y):
            return False
    return True


def net_hpwl(inst: Instance, poses: list, net) -> int:
    """Halbumfang des Rechtecks um alle Pins eines Netzes."""
    xs, ys = [], []
    for ci, pi in net:
        x, y = pin_xy(inst.comps[ci], poses[ci], pi)
        xs.append(x)
        ys.append(y)
    return max(xs) - min(xs) + max(ys) - min(ys)


def hpwl(inst: Instance, poses: list) -> int:
    return sum(net_hpwl(inst, poses, net) for net in inst.nets)


def _nearest_legal(inst: Instance, poses: list, i: int, tx: float, ty: float, placed: list, rots=(0, 1)):
    """Nächste legale Lage (mit einer der Drehungen `rots`) zum Wunschpunkt (tx, ty) in wachsenden Ringen um die Mitte; None, wenn das ganze Brett nichts hergibt.
    Wunschpunkt und Rückgabe beziehen sich auf die linke obere Ecke des Bauteils in Drehung 0; bei Drehung 1 bleibt die Mitte erhalten."""
    fp = inst.comps[i]
    cx, cy = tx + fp.w / 2.0, ty + fp.h / 2.0
    for d in range(0, max(inst.width, inst.height)):
        best = None
        for rot in rots:
            w, h = dims(fp, rot)
            ox, oy = int(round(cx - w / 2.0)), int(round(cy - h / 2.0))
            for dx in range(-d, d + 1):
                for dy in range(-d, d + 1):
                    if max(abs(dx), abs(dy)) != d:
                        continue
                    x, y = ox + dx, oy + dy
                    if is_legal(inst, poses, i, (x, y, rot), placed):
                        dist = (x + w / 2.0 - cx) ** 2 + (y + h / 2.0 - cy) ** 2
                        if best is None or (dist, rot) < (best[0], best[3]):
                            best = (dist, x, y, rot)
        if best:
            return (best[1], best[2], best[3])
    return None


def _random_attempt(inst: Instance, rng: SplitMix64):
    """Ein Versuch: große Bauteile zuerst an zufällige legale Plätze (Drehung zufällig); bei Misserfolg nächste freie Lage zu einem Zufallspunkt. None bei Misserfolg."""
    poses = fixed_poses(inst) + [None] * (len(inst.comps) - 2)
    placed = [0, 1]
    for i in sorted(range(2, len(inst.comps)), key=lambda c: (-(inst.comps[c].w * inst.comps[c].h), c)):
        fp = inst.comps[i]
        chosen = None
        for _ in range(500):
            rot = rng.below(2)
            w, h = dims(fp, rot)
            pose = (rng.below(inst.width - w + 1), rng.below(inst.height - h + 1), rot)
            if is_legal(inst, poses, i, pose, placed):
                chosen = pose
                break
        if chosen is None:
            chosen = _nearest_legal(inst, poses, i, rng.below(inst.width), rng.below(inst.height), placed)
        if chosen is None:
            return None
        poses[i] = chosen
        placed.append(i)
    return poses


def random_placement(inst: Instance, rng: SplitMix64) -> list:
    """Zufällige legale Lage aller Bauteile; bis zu 30 Versuche aus demselben Zufallsstrom, dann PlacementError."""
    for _ in range(30):
        poses = _random_attempt(inst, rng)
        if poses is not None:
            return poses
    raise PlacementError("Kein Platz für alle Bauteile: Dichte verringern.")


def quadratic_weights(inst: Instance) -> dict:
    """Clique-Modell: je Netz mit k Pins verbindet jedes Bauteilpaar eine Feder der Stärke 1 / (k - 1); gleiche Paare summieren sich."""
    weights = defaultdict(float)
    for net in inst.nets:
        comps = sorted({ci for ci, _ in net})
        for a in range(len(comps)):
            for b in range(a + 1, len(comps)):
                weights[(comps[a], comps[b])] += 1.0 / (len(net) - 1)
    return weights


def quadratic_targets(inst: Instance, poses: list) -> dict:
    """Minimum der Summe w * Abstand² über die Bauteilmitten bei festen Steckern: ein lineares Gleichungssystem je Achse. Gibt {Bauteil: (cx, cy)}."""
    movable = list(range(2, len(inst.comps)))
    index = {c: k for k, c in enumerate(movable)}
    m = len(movable)
    a = np.zeros((m, m))
    bx = np.zeros(m)
    by = np.zeros(m)
    for (u, v), w in quadratic_weights(inst).items():
        for p, q in ((u, v), (v, u)):
            if p not in index:
                continue
            a[index[p], index[p]] += w
            if q in index:
                a[index[p], index[q]] -= w
            else:
                fp = inst.comps[q]
                bx[index[p]] += w * (poses[q][0] + fp.w / 2.0)
                by[index[p]] += w * (poses[q][1] + fp.h / 2.0)
    a += 1e-6 * np.eye(m)
    sx, sy = np.linalg.solve(a, bx), np.linalg.solve(a, by)
    return {c: (float(sx[index[c]]), float(sy[index[c]])) for c in movable}


def quadratic_placement(inst: Instance) -> list:
    """Quadratische Platzierung: Lösung des Gleichungssystems, danach große Bauteile zuerst auf die nächste legale Lage legen (Drehung 0)."""
    poses = fixed_poses(inst) + [None] * (len(inst.comps) - 2)
    targets = quadratic_targets(inst, poses)
    placed = [0, 1]
    for i in sorted(targets, key=lambda c: (-(inst.comps[c].w * inst.comps[c].h), c)):
        fp = inst.comps[i]
        cx, cy = targets[i]
        pose = _nearest_legal(inst, poses, i, cx - fp.w / 2.0, cy - fp.h / 2.0, placed)
        if pose is None:
            raise PlacementError("Kein Platz für alle Bauteile: Dichte verringern.")
        poses[i] = pose
        placed.append(i)
    return poses


def _comp_nets(inst: Instance) -> dict:
    out = defaultdict(list)
    for k, net in enumerate(inst.nets):
        for ci in sorted({ci for ci, _ in net}):
            out[ci].append(k)
    return out


def _propose(inst: Instance, poses: list, rng: SplitMix64, temp: float, t_start: float):
    """Ein Zugvorschlag: Drehen (15 %), Tauschen zweier Bauteile (15 %) oder Verschieben im Radius, der mit der Temperatur schrumpft.
    Gibt {Bauteil: neue Lage} oder None, wenn der Vorschlag nicht legal ist."""
    movable = len(inst.comps) - 2
    i = 2 + rng.below(movable)
    x, y, rot = poses[i]
    r = rng.random()
    if r < 0.15:
        new = {i: (x, y, 1 - rot)}
    elif r < 0.30:
        j = 2 + rng.below(movable)
        if j == i:
            return None
        new = {i: (poses[j][0], poses[j][1], rot), j: (x, y, poses[j][2])}
    else:
        radius = max(1, int(round((inst.width + inst.height) / 4 * min(1.0, temp / t_start * 3 + 0.05))))
        new = {i: (x + rng.randint(-radius, radius), y + rng.randint(-radius, radius), rot)}
    trial = list(poses)
    for c, pose in new.items():
        trial[c] = pose
    everyone = range(len(inst.comps))
    if all(is_legal(inst, trial, c, pose, everyone) for c, pose in new.items()):
        return new
    return None


def sa_placement(inst: Instance, rng: SplitMix64, moves: int = C.SA_MOVES) -> list:
    """Simulated Annealing auf der HPWL: geometrische Abkühlung, Delta nur über die Netze der bewegten Bauteile, am Ende die beste besuchte Lage."""
    poses = random_placement(inst, rng)
    by_comp = _comp_nets(inst)
    net_len = [net_hpwl(inst, poses, net) for net in inst.nets]
    current = sum(net_len)
    best = (current, list(poses))
    t_start, t_end = 0.6 * (inst.width + inst.height) / 4, 0.15
    for it in range(moves):
        temp = t_start * (t_end / t_start) ** (it / moves)
        new = _propose(inst, poses, rng, temp, t_start)
        if new is None:
            continue
        trial = list(poses)
        for c, pose in new.items():
            trial[c] = pose
        affected = sorted({k for c in new for k in by_comp[c]})
        changed = {k: net_hpwl(inst, trial, inst.nets[k]) for k in affected}
        delta = sum(changed[k] - net_len[k] for k in affected)
        if delta <= 0 or rng.random() < math.exp(-delta / temp):
            poses = trial
            for k, v in changed.items():
                net_len[k] = v
            current += delta
            if current < best[0]:
                best = (current, list(poses))
    return best[1]


def place(inst: Instance, method: str, seed: int) -> list:
    """Lagen aller Bauteile nach Verfahren; der Zufall kommt nur aus `seed`."""
    rng = SplitMix64(seed * 7919 + 13)
    if method == C.PLACEMENTS[0]:
        return random_placement(inst, rng)
    if method == C.PLACEMENTS[1]:
        return quadratic_placement(inst)
    if method == C.PLACEMENTS[2]:
        return sa_placement(inst, rng)
    raise ValueError(method)


def check_placement(inst: Instance, poses: list) -> list:
    """Unabhängiger Prüfer: Fehlermeldungen (leer = alles in Ordnung): alle im Brett, keine zwei Bauteile näher als GAP, Stecker an ihrem Platz."""
    errors = []
    if len(poses) != len(inst.comps):
        return ["falsche Zahl von Lagen"]
    if poses[:2] != fixed_poses(inst):
        errors.append("Stecker nicht am Rand")
    for i, (x, y, rot) in enumerate(poses):
        w, h = dims(inst.comps[i], rot)
        if x < 0 or y < 0 or x + w > inst.width or y + h > inst.height:
            errors.append(f"{inst.comps[i].name} liegt außerhalb des Bretts")
        for j in range(i):
            ox, oy, orot = poses[j]
            ow, oh = dims(inst.comps[j], orot)
            dx = max(ox - (x + w), x - (ox + ow))   # Lücke in x (negativ: überlappen)
            dy = max(oy - (y + h), y - (oy + oh))
            if max(dx, dy) < C.GAP:
                errors.append(f"{inst.comps[i].name} und {inst.comps[j].name} zu nah")
    return errors
