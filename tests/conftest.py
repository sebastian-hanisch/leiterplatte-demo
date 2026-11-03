"""Gemeinsame Fixtures: Mini-Bretter, an denen jede Einheit von Hand geprüft wird (DEMO-PLAYBOOK §1b)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lpl_grid import BODY, FREE, Board  # noqa: E402
from lpl_mini import HAND_EXAMPLE, MiniSpec, mini_board  # noqa: E402


@pytest.fixture
def hand_board():
    """Das Handbeispiel (6 x 5, 5 Netze, 1 Sperrzelle)."""
    return mini_board(HAND_EXAMPLE)


@pytest.fixture
def two_rows():
    """4 x 3, zwei waagerechte Netze in Zeile 0 und Zeile 2. Handrechnung: je 3 Schritte, kein Via, Summe 6."""
    return mini_board(MiniSpec(4, 3, nets=(((0, 0), (3, 0)), ((0, 2), (3, 2))), blocks=()))


@pytest.fixture
def crossing():
    """4 x 3: Netz 0 waagerecht in Zeile 1 (3 Schritte), Netz 1 senkrecht in Spalte 1 (2 Schritte); eines muss die andere Lage nehmen, kein Via nötig (Pads sind Durchsteckpads). Summe 5."""
    return mini_board(MiniSpec(4, 3, nets=(((0, 1), (3, 1)), ((1, 0), (1, 2))), blocks=()))


@pytest.fixture
def via_forced():
    """5 x 1, Netz 0 von (0,0) nach (4,0); (1,0) ist oben gesperrt, (3,0) unten gesperrt. Handrechnung: 4 Schritte und 1 Via bei x = 2, Kosten 4 + (1 + Via-Kosten)."""
    cells = 5
    fixed = [FREE] * (2 * cells)
    fixed[1] = BODY               # Schicht 0, x = 1
    fixed[cells + 3] = BODY       # Schicht 1, x = 3
    fixed[0] = fixed[cells] = 0   # Pad Netz 0
    fixed[4] = fixed[cells + 4] = 0
    return Board(5, 1, tuple(fixed), ((0, 4),))
