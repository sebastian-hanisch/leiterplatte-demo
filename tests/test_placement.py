"""Platzierung: legale Lagen, HPWL gegen Handrechnung, quadratische Zielpunkte gegen die Formel, Simulated Annealing gegen seinen Start."""

import pytest

import lpl_constants as C
import lpl_placement as P
from lpl_rng import SplitMix64
from lpl_scenario import Footprint, Instance, make_instance

SEEDS = range(15)


def _two_part_instance():
    """Zwei Stecker (1 x 3) und ein Widerstand (2 x 1) auf einem 12 x 8 Brett; ein Netz verbindet je einen Pin der drei Bauteile."""
    conn = Footprint("J", "conn", 1, 3, ((0, 0), (0, 2)), fixed=True)
    res = Footprint("R", "pas", 2, 1, ((0, 0), (1, 0)))
    return Instance((conn, conn, res), (((0, 0), (1, 0), (2, 1)),), ("N",), 12, 8)


def test_hpwl_by_hand():
    inst = _two_part_instance()
    poses = [(0, 2, 0), (11, 3, 0), (5, 4, 0)]
    # Pins: J1 (0,2), J2 (11,3), R Pin 1 (6,4): x von 0 bis 11, y von 2 bis 4 -> 11 + 2 = 13
    assert P.net_hpwl(inst, poses, inst.nets[0]) == 13
    assert P.hpwl(inst, poses) == 13


def test_fixed_poses_are_centered_on_the_edges():
    inst = _two_part_instance()
    assert P.fixed_poses(inst) == [(0, 2, 0), (11, 2, 0)]     # (8 - 3) // 2 = 2


def test_is_legal_gap_is_inclusive_at_two_cells():
    inst = _two_part_instance()
    poses = [(0, 2, 0), (11, 2, 0), (3, 3, 0)]
    # Widerstand (2 x 1) bei x = 3: Lücke zum Stecker bei x = 0 ist 3 - 1 = 2, genau erlaubt; bei x = 2 nur 1, verboten
    assert P.is_legal(inst, poses, 2, (3, 3, 0), [0, 1])
    assert not P.is_legal(inst, poses, 2, (2, 3, 0), [0, 1])
    assert not P.is_legal(inst, poses, 2, (11, 3, 0), [0, 1])   # überlappt J2 und ragt hinaus
    assert not P.is_legal(inst, poses, 2, (-1, 3, 0), [0, 1])


def test_quadratic_targets_match_the_closed_form_for_one_free_part():
    inst = _two_part_instance()
    poses = [(0, 2, 0), (11, 3, 0), None]
    # ein bewegliches Bauteil, Feder 1 / (k - 1) = 1/2 zu jedem Stecker: Ziel = Mittel der Steckermitten (0,5 | 3,5) und (11,5 | 4,5)
    t = P.quadratic_targets(inst, poses)
    assert t[2][0] == pytest.approx(6.0, abs=1e-4) and t[2][1] == pytest.approx(4.0, abs=1e-4)


@pytest.mark.parametrize("method", C.PLACEMENTS)
@pytest.mark.parametrize("seed", SEEDS)
def test_every_method_gives_a_legal_placement(method, seed):
    inst = make_instance(C.DEFAULT_N_IC, C.DEFAULT_PIN_USE, C.UTIL_MAX, seed)
    poses = P.place(inst, method, seed)
    assert P.check_placement(inst, poses) == []


def test_the_checker_finds_overlap_distance_and_boundary_violations():
    inst = _two_part_instance()
    assert P.check_placement(inst, [(0, 2, 0), (11, 2, 0), (5, 4, 0)]) == []
    assert any("zu nah" in e for e in P.check_placement(inst, [(0, 2, 0), (11, 2, 0), (2, 3, 0)]))
    assert any("außerhalb" in e for e in P.check_placement(inst, [(0, 2, 0), (11, 2, 0), (11, 7, 0)]))
    assert any("Stecker" in e for e in P.check_placement(inst, [(0, 0, 0), (11, 2, 0), (5, 4, 0)]))


def test_sa_never_ends_worse_than_its_random_start_and_beats_it_on_average():
    gains = []
    for seed in SEEDS:
        inst = make_instance(C.DEFAULT_N_IC, C.DEFAULT_PIN_USE, C.DEFAULT_UTIL, seed)
        start = P.hpwl(inst, P.random_placement(inst, SplitMix64(seed * 7919 + 13)))
        final = P.hpwl(inst, P.place(inst, C.PLACEMENTS[2], seed))
        assert final <= start
        gains.append(start - final)
    assert sum(gains) / len(gains) > 100       # der Abstand ist groß; keine knappe Schwelle


def test_placement_methods_differ_on_at_least_one_instance():
    """Keine tote Spalte: jede Platzierungsart liefert auf mindestens einer Instanz eine andere HPWL als die Nachbarart."""
    differ = [0, 0]
    for seed in SEEDS:
        inst = make_instance(C.DEFAULT_N_IC, C.DEFAULT_PIN_USE, C.DEFAULT_UTIL, seed)
        h = [P.hpwl(inst, P.place(inst, m, seed)) for m in C.PLACEMENTS]
        differ[0] += h[0] != h[1]
        differ[1] += h[1] != h[2]
    assert all(v > 0 for v in differ)


def test_same_seed_same_placement():
    inst = make_instance(4, 85, 60, 3)
    assert P.place(inst, C.PLACEMENTS[2], 3) == P.place(inst, C.PLACEMENTS[2], 3)


def test_a_board_that_is_too_small_raises():
    parts = tuple(Footprint(f"R{i}", "pas", 2, 1, ((0, 0), (1, 0))) for i in range(30))
    conn = Footprint("J", "conn", 1, 3, ((0, 0),), fixed=True)
    inst = Instance((conn, conn) + parts, (), (), 12, 8)
    with pytest.raises(P.PlacementError):
        P.random_placement(inst, SplitMix64(1))


def test_every_accepted_move_proposal_is_legal():
    inst = make_instance(4, 85, 60, 2)
    poses = P.place(inst, C.PLACEMENTS[0], 2)
    rng = SplitMix64(4)
    accepted = 0
    for _ in range(300):
        new = P._propose(inst, poses, rng, 3.0, 5.0)
        if new:
            trial = list(poses)
            for c, pose in new.items():
                trial[c] = pose
            assert P.check_placement(inst, trial) == []
            accepted += 1
    assert accepted > 0
