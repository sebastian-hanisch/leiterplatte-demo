"""Instanzgenerator, Bauteile und Brettgröße: Handrechnung und Invarianten über viele Seeds."""

import pytest

import lpl_constants as C
from lpl_scenario import Footprint, body_cells, board_size, dims, make_instance, pin_xy

IC = Footprint("U", "ic", 4, 3, ((0, 0), (0, 1), (0, 2), (3, 0), (3, 1), (3, 2)))


def test_pin_positions_in_both_rotations_by_hand():
    assert [pin_xy(IC, (10, 5, 0), i) for i in (0, 2, 3)] == [(10, 5), (10, 7), (13, 5)]
    # gedreht: (dx, dy) -> (h - 1 - dy, dx) = (2 - dy, dx)
    assert [pin_xy(IC, (10, 5, 1), i) for i in (0, 2, 3)] == [(12, 5), (10, 5), (12, 8)]
    assert dims(IC, 0) == (4, 3) and dims(IC, 1) == (3, 4)


def test_body_cells_are_the_inner_columns_and_rotate_with_the_part():
    assert sorted(body_cells(IC, (10, 5, 0))) == [(11, 5), (11, 6), (11, 7), (12, 5), (12, 6), (12, 7)]
    # gedreht liegt das Gehäuse in den Zeilen y = 6 und 7 zwischen den Pinzeilen y = 5 und y = 8, x = 10..12
    assert sorted(body_cells(IC, (10, 5, 1))) == [(10, 6), (10, 7), (11, 6), (11, 7), (12, 6), (12, 7)]
    assert body_cells(Footprint("R", "pas", 2, 1, ((0, 0), (1, 0))), (0, 0, 0)) == []


def test_body_never_covers_a_pin():
    for rot in (0, 1):
        pins = {pin_xy(IC, (3, 4, rot), i) for i in range(len(IC.pins))}
        assert pins.isdisjoint(body_cells(IC, (3, 4, rot)))


def test_board_size_by_hand():
    # zwei Bauteile 4 x 3 und 2 x 1: gepolsterte Flächen 6 * 5 + 4 * 3 = 42
    comps = (Footprint("a", "ic", 4, 3, ()), Footprint("b", "pas", 2, 1, ()))
    assert board_size(comps, 100) == (8, 6)    # Breite ceil(sqrt(56)) = 8, Höhe ceil(42 / 8) = 6
    assert board_size(comps, 50) == (11, 8)    # Fläche 84: Breite ceil(sqrt(112)) = 11, Höhe ceil(84 / 11) = 8


@pytest.mark.parametrize("seed", range(40))
def test_instance_invariants(seed):
    inst = make_instance(C.DEFAULT_N_IC, C.DEFAULT_PIN_USE, C.DEFAULT_UTIL, seed)
    used = [pin for net in inst.nets for pin in net]
    assert len(used) == len(set(used)), "ein Pin hängt in zwei Netzen"
    assert all(len(net) >= 2 for net in inst.nets)
    assert all(0 <= ci < len(inst.comps) and 0 <= pi < len(inst.comps[ci].pins) for ci, pi in used)
    assert len(inst.net_names) == len(inst.nets) and len(set(inst.net_names)) == len(inst.nets)
    assert inst.comps[0].fixed and inst.comps[1].fixed and not any(c.fixed for c in inst.comps[2:])
    assert inst.net_names[:2] == ("VCC", "GND")
    assert len(inst.comps) == 2 + C.DEFAULT_N_IC + C.DEFAULT_N_IC + max(2, C.DEFAULT_N_IC)


def test_power_nets_collect_every_supply_pin():
    inst = make_instance(4, 85, 60, 11)
    by_name = dict(zip(inst.net_names, inst.nets))
    # VCC: 2 Stecker + 4 ICs + 4 Kondensatoren + 4 Pull-ups; GND: 2 Stecker + 4 ICs + 4 Kondensatoren
    assert len(by_name["VCC"]) == 2 + 4 + 4 + 4
    assert len(by_name["GND"]) == 2 + 4 + 4


def test_same_seed_same_instance_and_other_seed_differs():
    a = make_instance(6, 85, 60, 5)
    assert a == make_instance(6, 85, 60, 5)
    assert a != make_instance(6, 85, 60, 6)


def test_pin_use_changes_the_number_of_signal_pins():
    few = make_instance(6, 50, 60, 3)
    many = make_instance(6, 100, 60, 3)
    assert sum(len(n) for n in many.nets) > sum(len(n) for n in few.nets)


def test_smallest_instance_still_has_nets():
    inst = make_instance(C.N_IC_MIN, C.PIN_USE_MIN, C.UTIL_MAX, 0)
    assert len(inst.nets) >= 2
