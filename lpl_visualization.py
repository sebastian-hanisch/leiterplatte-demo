"""Plotly-Abbildungen. Alle Achsen sind gesperrt (fixedrange), damit Touch-Geräte beim Scrollen nicht am Diagramm hängen bleiben."""

import plotly.graph_objects as go

import lpl_constants as C
from lpl_grid import NC_PAD, Board, cell_of
from lpl_scenario import dims


def lock_axes(fig):
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def _base(fig, height=360):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.3), plot_bgcolor="rgba(0,0,0,0)")
    return lock_axes(fig)


def _segments(board: Board, routing, layer: int):
    """x- und y-Listen aller Leiterbahnstücke einer Lage, durch None getrennt (eine Spur für alle)."""
    xs, ys = [], []
    for edges in routing.edges.values():
        for u, v in edges:
            xu, yu, lu = cell_of(board, u)
            xv, yv, lv = cell_of(board, v)
            if lu == lv == layer:
                xs += [xu + 0.5, xv + 0.5, None]
                ys += [yu + 0.5, yv + 0.5, None]
    return xs, ys


def _via_points(board: Board, routing):
    xs, ys = [], []
    for edges in routing.edges.values():
        for u, v in edges:
            if abs(u - v) == board.cells:
                x, y, _ = cell_of(board, u)
                xs.append(x + 0.5)
                ys.append(y + 0.5)
    return xs, ys


def _airwires(board: Board, routing, net_names):
    """Unverlegte Netze als gestrichelte Luftlinien vom ersten Pad zu allen anderen."""
    xs, ys, hover = [], [], []
    for k in routing.failed:
        pads = board.pads[k]
        x0, y0 = pads[0] % board.width + 0.5, pads[0] // board.width + 0.5
        for p in pads[1:]:
            xs += [x0, p % board.width + 0.5, None]
            ys += [y0, p // board.width + 0.5, None]
    return xs, ys


def _add_components(fig, inst, poses):
    for fp, pose in zip(inst.comps, poses):
        x, y, rot = pose
        w, h = dims(fp, rot)
        fig.add_shape(type="rect", x0=x - 0.1, x1=x + w + 0.1, y0=y - 0.1, y1=y + h + 0.1, line=dict(color="rgba(120,120,120,0.8)", width=1),
                      fillcolor=C.COLOR_BODY if fp.kind == "ic" else "rgba(150,150,150,0.12)", layer="below")
        fig.add_annotation(x=x + w / 2, y=y + h / 2, text=fp.name, showarrow=False, font=dict(size=9, color="rgba(90,90,90,0.9)"))


def build_board_figure(board: Board, routing, inst=None, poses=None, show_top=True, show_bottom=True, label_pads=False, height=520):
    """Brett von oben: Bauteile, Pads, Leiterbahnen beider Lagen (rot oben, blau unten), Vias und unverlegte Netze als Luftlinien."""
    fig = go.Figure()
    w, h = board.width, board.height
    fig.add_shape(type="rect", x0=0, x1=w, y0=0, y1=h, line=dict(color="rgba(80,80,80,0.9)", width=2), layer="below")
    if inst is not None:
        _add_components(fig, inst, poses)
    pad_x, pad_y, nc_x, nc_y, pad_text = [], [], [], [], []
    for cell in range(board.cells):
        f = board.fixed[cell]
        x, y = cell % w + 0.5, cell // w + 0.5
        if f >= 0:
            pad_x.append(x)
            pad_y.append(y)
            pad_text.append(str(f))
        elif f == NC_PAD:
            nc_x.append(x)
            nc_y.append(y)
    fig.add_trace(go.Scatter(x=pad_x, y=pad_y, mode="markers+text" if label_pads else "markers", marker=dict(size=7, color=C.COLOR_PAD, symbol="square"), name="Pad",
                             text=pad_text if label_pads else None, textposition="top center", textfont=dict(size=11), hoverinfo="skip"))
    if nc_x:
        fig.add_trace(go.Scatter(x=nc_x, y=nc_y, mode="markers", marker=dict(size=7, color="rgba(100,100,100,0.7)", symbol="x"), name="Pad ohne Netz", hoverinfo="skip"))
    for layer, color, name, flag in ((1, C.COLOR_BOTTOM, "Unterseite", show_bottom), (0, C.COLOR_TOP, "Oberseite", show_top)):
        if flag:
            xs, ys = _segments(board, routing, layer)
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=color, width=3), opacity=0.85, name=name, hoverinfo="skip"))
    vx, vy = _via_points(board, routing)
    if vx:
        fig.add_trace(go.Scatter(x=vx, y=vy, mode="markers", marker=dict(size=7, color="white", line=dict(color=C.COLOR_VIA, width=2)), name="Via", hoverinfo="skip"))
    ax, ay = _airwires(board, routing, None)
    if ax:
        fig.add_trace(go.Scatter(x=ax, y=ay, mode="lines", line=dict(color=C.COLOR_UNROUTED, width=2, dash="dot"), name="unverlegt (Luftlinie)", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[-1, w + 1], y=[-1, h + 1], mode="markers", marker=dict(opacity=0), showlegend=False, hoverinfo="skip"))
    fig.update_xaxes(visible=False, constrain="domain")
    fig.update_yaxes(visible=False, autorange="reversed", scaleanchor="x", scaleratio=1)
    fig.update_layout(height=height, margin=dict(l=5, r=5, t=5, b=5), legend=dict(orientation="h", y=-0.02), plot_bgcolor="rgba(0,0,0,0)")
    return lock_axes(fig)


def build_methods_figure(metrics: dict):
    """Unverlegte Netze je Verlegeregel."""
    names = list(metrics)
    failed = [metrics[m]["failed"] for m in names]
    fig = go.Figure(go.Bar(x=names, y=failed, marker_color=[C.COLOR_OTHER, C.COLOR_LINE, C.COLOR_CHOSEN], text=failed, textposition="outside",
                           hovertemplate="%{x}: %{y} unverlegt<extra></extra>"))
    fig.update_yaxes(title_text="unverlegte Netze", rangemode="tozero")
    return _base(fig, 300)


def build_order_figure(spread: dict, rrr_failed: int, negotiated_failed: int):
    """Häufigkeit der Zahl unverlegter Netze über die Zufallsreihenfolgen (sequentiell), dazu die Werte der beiden anderen Regeln als senkrechte Linien."""
    rand = spread["random"]
    top = max(rand + [rrr_failed, negotiated_failed])
    xs = list(range(0, top + 1))
    counts = [rand.count(x) for x in xs]
    height = max(counts) + 1
    fig = go.Figure(go.Bar(x=xs, y=counts, marker_color=C.COLOR_OTHER, name="sequentiell, zufällige Reihenfolge", hovertemplate="%{x} unverlegt: %{y} Reihenfolgen<extra></extra>"))
    for value, name, color, dash in ((rrr_failed, "Rip-up and Reroute", C.COLOR_LINE, "dash"), (negotiated_failed, "Negotiated Congestion", C.COLOR_CHOSEN, "solid")):
        fig.add_trace(go.Scatter(x=[value, value], y=[0, height], mode="lines", line=dict(color=color, width=4, dash=dash), name=name,
                                 hovertemplate=f"{name}: %{{x}} unverlegt<extra></extra>"))
    fig.update_xaxes(title_text="unverlegte Netze", dtick=1, range=[-0.5, top + 0.5])
    fig.update_yaxes(title_text="Zahl der Reihenfolgen", range=[0, height * 1.05], dtick=1 if height <= 8 else None)
    return _base(fig, 300)


def build_placement_figure(rows: list):
    """HPWL (Balken) und unverlegte Netze (Negotiated Congestion, Punkte, rechte Achse) je Platzierungsart."""
    names = [r["placement"] for r in rows]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=names, y=[r["hpwl"] for r in rows], marker_color=C.COLOR_OTHER, name="Netzlänge (HPWL)", yaxis="y"))
    fig.add_trace(go.Scatter(x=names, y=[r["negotiated"] for r in rows], mode="markers", marker=dict(size=14, color=C.COLOR_CHOSEN), name="unverlegt (Negotiated Congestion)", yaxis="y2"))
    fig.update_layout(yaxis=dict(title="HPWL (Zellen)", rangemode="tozero", fixedrange=True),
                      yaxis2=dict(title="unverlegte Netze", overlaying="y", side="right", rangemode="tozero", dtick=1, fixedrange=True))
    return _base(fig, 320)


def build_via_figure(rows: list):
    """Vias und Länge über den Via-Kosten."""
    xs = [r["via_cost"] for r in rows]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=[r["vias"] for r in rows], mode="lines+markers", line=dict(color=C.COLOR_LINE, width=3), name="Vias", yaxis="y"))
    fig.add_trace(go.Scatter(x=xs, y=[r["wirelength"] for r in rows], mode="lines+markers", line=dict(color=C.COLOR_CHOSEN, width=3, dash="dash"), name="Länge (Zellen)", yaxis="y2"))
    fig.update_layout(xaxis=dict(title="Via-Kosten", type="category"), yaxis=dict(title="Vias", rangemode="tozero", fixedrange=True),
                      yaxis2=dict(title="Länge", overlaying="y", side="right", rangemode="tozero", fixedrange=True))
    return _base(fig, 320)
