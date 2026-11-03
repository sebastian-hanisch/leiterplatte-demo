"""PDF-Bericht der aktuellen Verlegung (fpdf2): Einstellungen, Kennzahlen aller drei Regeln und eine Zeichnung des Bretts.

Kernschriften kennen weder Gedankenstrich noch Euro: im Text nur Bindestrich."""

from fpdf import FPDF

import lpl_constants as C
from lpl_evaluation import Analysis
from lpl_grid import cell_of
from lpl_scenario import dims

_RED, _BLUE, _GREY, _ORANGE = (214, 96, 77), (67, 147, 195), (120, 120, 120), (224, 130, 20)


def _latin(text: str) -> str:
    """Kernschriften (Latin-1): alles andere ersetzen, damit fpdf2 nicht abbricht."""
    return text.replace("–", "-").replace("→", "->").encode("latin-1", "replace").decode("latin-1")


def _setting_rows(a: Analysis) -> list:
    s = a.settings
    return [
        ("ICs / Netze", f"{s.n_ic} / {len(a.inst.nets)}"),
        ("Dichte / Brett", f"{s.util} % / {a.inst.width} x {a.inst.height} Zellen"),
        ("Pin-Nutzung", f"{s.pin_use} %"),
        ("Platzierung (HPWL)", f"{s.placement} ({a.hpwl})"),
        ("Netzreihenfolge", s.order),
        ("Via-Kosten / Iterationsgrenze", f"{s.via_cost} / {s.iterations}"),
        ("Seed", str(s.seed)),
    ]


def _draw_board(pdf: FPDF, a: Analysis, routing, x0: float, y0: float, width: float) -> float:
    """Zeichnet das Brett mit Bauteilen und Leiterbahnen; gibt die Höhe zurück."""
    board = a.board
    scale = width / board.width
    pdf.set_draw_color(80, 80, 80)
    pdf.set_line_width(0.4)
    pdf.rect(x0, y0, board.width * scale, board.height * scale)
    pdf.set_line_width(0.15)
    pdf.set_draw_color(*_GREY)
    for fp, (x, y, rot) in zip(a.inst.comps, a.poses):
        w, h = dims(fp, rot)
        pdf.rect(x0 + x * scale, y0 + y * scale, w * scale, h * scale)
    pdf.set_line_width(0.35)
    for edges in routing.edges.values():
        for u, v in edges:
            xu, yu, lu = cell_of(board, u)
            xv, yv, lv = cell_of(board, v)
            if lu == lv:
                pdf.set_draw_color(*(_RED if lu == 0 else _BLUE))
                pdf.line(x0 + (xu + 0.5) * scale, y0 + (yu + 0.5) * scale, x0 + (xv + 0.5) * scale, y0 + (yv + 0.5) * scale)
            else:
                pdf.set_draw_color(0, 0, 0)
                pdf.ellipse(x0 + (xu + 0.5) * scale - 0.5, y0 + (yu + 0.5) * scale - 0.5, 1.0, 1.0)
    pdf.set_draw_color(*_ORANGE)
    pdf.set_dash_pattern(dash=0.8, gap=0.8)
    for k in routing.failed:
        pads = board.pads[k]
        px, py = pads[0] % board.width + 0.5, pads[0] // board.width + 0.5
        for p in pads[1:]:
            pdf.line(x0 + px * scale, y0 + py * scale, x0 + (p % board.width + 0.5) * scale, y0 + (p // board.width + 0.5) * scale)
    pdf.set_dash_pattern()
    return board.height * scale


def build_pdf(a: Analysis, view: str) -> bytes:
    """Bericht als PDF-Bytes. `view` ist die Verlegeregel, deren Brett gezeichnet wird."""
    pdf = FPDF(unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 8, _latin("Leiterplatte: Verlegebericht"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, _latin("Sebastian Hanisch - Operations Research und Machine Learning (synthetisches Sensorboard, Raster mit zwei Lagen)"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Einstellungen", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for name, value in _setting_rows(a):
        pdf.cell(60, 5, _latin(name))
        pdf.cell(0, 5, _latin(value), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Ergebnis je Verlegeregel", new_x="LMARGIN", new_y="NEXT")
    heads = ("Regel", "unverlegt", "Laenge", "Vias", "Umweg", "Suchlaeufe")
    widths = (58, 24, 24, 20, 24, 28)
    pdf.set_font("Helvetica", "B", 9)
    for h, w in zip(heads, widths):
        pdf.cell(w, 5, h)
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 9)
    for method, m in a.metrics.items():
        cells = (method, f"{m['failed']} von {m['nets']}", str(m["wirelength"]), str(m["vias"]), f"{m['detour']:.2f}".replace(".", ","), str(m["searches"]))
        for c, w in zip(cells, widths):
            pdf.cell(w, 5, _latin(c))
        pdf.ln(5)
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, _latin(f"Brett: {view}"), new_x="LMARGIN", new_y="NEXT")
    top = pdf.get_y() + 1
    height = _draw_board(pdf, a, a.routings[view], pdf.l_margin, top, 180.0)
    pdf.set_y(top + height + 2)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 4, _latin("Rot: Oberseite, blau: Unterseite, Kreis: Via, orange gestrichelt: unverlegtes Netz (Luftlinie)."), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
