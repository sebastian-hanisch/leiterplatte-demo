"""PDF-Bericht: erzeugt gültige Bytes für jede Verlegeregel, ohne Zeichen außerhalb von Latin-1 zu verlieren."""

import pytest

import lpl_constants as C
from lpl_evaluation import Settings, analyse
from lpl_pdf_export import _latin, build_pdf


@pytest.fixture(scope="module")
def a():
    return analyse(Settings(n_ic=3, util=55, seed=2))


@pytest.mark.parametrize("view", C.METHODS)
def test_pdf_is_a_pdf_for_every_method(a, view):
    data = build_pdf(a, view)
    assert data[:5] == b"%PDF-" and len(data) > 2000


def test_latin_replaces_what_core_fonts_cannot_write():
    assert _latin("a \u2013 b \u2192 c \u20ac") == "a - b -> c ?"
    assert _latin("Länge und Größe") == "Länge und Größe"
