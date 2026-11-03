"""Leiterplatte: welche Verlegeregel bekommt alle Netze unter? - interaktive Fall-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Ein synthetisches Sensorboard (Stecker, ICs, Kondensatoren, Widerstände) wird platziert und auf einem Raster mit zwei Lagen verlegt: sequentiell, mit Rip-up and
Reroute und mit Negotiated Congestion; auf einem Mini-Brett prüft ein exakter Löser (CP-SAT) die Aussagen. Aufbau und Regeln: DEMO-PLAYBOOK.md (§2).

Lauffähig mit: streamlit run app.py
"""

import streamlit as st

import lpl_constants as C
import lpl_evaluation as ev
from lpl_evaluation import Settings, analyse
from lpl_layout import dunkles_design, kopf_css
from lpl_mini import HAND_EXAMPLE, heuristics, mini_board, random_mini, scan_all_orders
from lpl_presets import (
    bounds,
    choices,
    init_session_state_defaults,
    load_permalink_settings,
    randomize_seed,
    sidebar_presets,
    sync_query_params,
)
from lpl_router import Routing, check_feasible, routing_cost
from lpl_visualization import (
    build_board_figure,
    build_bestueck_figure,
    build_bestueck_methods_figure,
    build_methods_figure,
    build_order_figure,
    build_placement_figure,
    build_via_figure,
)

st.set_page_config(page_title="Leiterplatte – Sebastian Hanisch", layout="wide")


def de(x: float, digits: int = 1) -> str:
    """Zahl mit Dezimalkomma."""
    return f"{x:.{digits}f}".replace(".", ",")


@st.cache_data(show_spinner=False)
def _analysis(settings):
    return analyse(settings)


@st.cache_data(show_spinner=False)
def _spread(settings):
    return ev.order_spread(analyse(settings))


@st.cache_data(show_spinner=False)
def _placements(settings):
    return ev.placement_comparison(settings)


@st.cache_data(show_spinner=False)
def _vias(settings):
    return ev.via_comparison(settings)


@st.cache_data(show_spinner=False)
def _bestueckung(settings, k):
    return ev.bestueckung_for(_analysis(settings), k)


@st.cache_data(show_spinner=False)
def _mini(spec, via_cost, iterations):
    """Mini-Brett: alle Reihenfolgen, Rip-up, Negotiated Congestion und der exakte Löser (ortools erst hier importiert)."""
    from lpl_exact import solve_exact

    board = mini_board(spec)
    v = float(via_cost)
    rrr, pf = heuristics(board, v, iterations)
    return scan_all_orders(board, v), rrr, pf, solve_exact(board, v)


# Fester Kopf: nur der Titel bleibt beim Scrollen oben (Stylesheet in lpl_layout.py).
st.html(kopf_css(dunkles_design()))
with st.container(key="kopf"):
    st.title("🔌 Leiterplatte: welche Verlegeregel bekommt alle Netze unter?")
st.markdown(
    """
Ein **Sensorboard** (zwei Stecker, ICs, Kondensatoren, Widerstände) wird platziert und auf einem **Raster mit zwei Lagen** verlegt: jedes **Netz** muss seine Pads verbinden,
zwei Netze dürfen keine Zelle teilen, und ein **Via** wechselt die Lage. Jedes Netz für sich ist ein einfacher kürzester Weg, **zusammen** blockieren sich die Netze,
und die **Reihenfolge** entscheidet mit. Die Demo vergleicht drei Verlegeregeln (**sequentiell**, **Rip-up and Reroute**, **Negotiated Congestion**) und prüft die Aussagen
auf einem **Mini-Brett** mit einem **exakten Löser**.

Danach wird dieselbe Platine **bestückt**: ein Automat holt die Bauteile von Zuführplätzen und setzt sie; **welcher Typ auf welchen Platz** und **in welcher Reihenfolge** entscheiden über die Fahrstrecke.

Weiter unten: die **Kernfrage**, der Abschnitt **🏭 Bestückung** und die Expander **🔧 Wie wir das erreichen – vollständiger Methodenvergleich**, **📐 Mathematische Formulierung** und **🚧 Wo die Annahmen enden**.
"""
)

st.caption("🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, um ein Szenario zu teilen.")

load_permalink_settings()
init_session_state_defaults()

with st.sidebar:
    sidebar_presets()  # Schnellstart oben, das aktive Preset ist hervorgehoben
    st.header("⚙️ Einstellungen")
    st.markdown("**Brett**")
    n_ic = st.slider("ICs", *bounds("n_ic_slider"), key="n_ic_slider", help="Wie viele ICs (je 6 bis 12 Pins) das Sensorboard trägt; dazu je IC ein Kondensator und mindestens zwei Widerstände.")
    util = st.slider("Dichte (%)", *bounds("util_slider"), key="util_slider", help="Bauteilfläche samt Mindestabstand geteilt durch die Brettfläche: je dichter, desto kleiner das Brett.")
    pin_use = st.slider("Pin-Nutzung (%)", *bounds("pin_use_slider"), key="pin_use_slider", help="Anteil der freien IC-Pins, die in einem Signalnetz hängen: mehr Netze, mehr Gedränge.")
    st.markdown("**Platzierung**")
    placement = st.selectbox("Platzierung", choices("placement_select"), key="placement_select",
                             help="Zufall: legale Zufallslagen. Quadratisch: Federmodell mit Gleichungssystem, danach Legalisierung. Simulated Annealing: Suche auf der Netzlänge.")
    st.markdown("**Verlegen**")
    order = st.selectbox("Netzreihenfolge", choices("order_select"), key="order_select", help="In welcher Reihenfolge die Netze versucht werden (nach der Halbumfangs-Länge der Netze).")
    via = st.slider("Via-Kosten", *bounds("via_slider"), key="via_slider", help="Zusatzkosten eines Lagenwechsels in Zellenschritten.")
    iterations = st.slider("Iterationsgrenze (Negotiated Congestion)", *bounds("iter_slider"), key="iter_slider",
                           help="Nach so vielen Durchläufen gibt Negotiated Congestion auf und zeigt die größte konfliktfreie Teilmenge.")
    seed = st.number_input("Zufalls-Seed der Instanz", *bounds("seed_input"), key="seed_input", step=1)
    st.button("🎲 Neue Instanz generieren", width="stretch", on_click=randomize_seed)

sync_query_params({
    "n_ic_slider": int(n_ic), "util_slider": int(util), "pin_use_slider": int(pin_use), "placement_select": placement, "order_select": order,
    "via_slider": int(via), "iter_slider": int(iterations), "seed_input": int(seed),
})

settings = Settings(int(n_ic), int(util), int(pin_use), placement, order, int(via), int(iterations), int(seed))
try:
    with st.spinner("Platziere und verlege …"):
        a = _analysis(settings)
except Exception as exc:  # PlacementError: Brett zu dicht für die Bauteile
    st.error(f"Diese Einstellung lässt sich nicht platzieren: {exc}")
    st.stop()

for method, errors in a.violations.items():
    if errors:
        st.error(f"Prüfer meldet Fehler bei „{method}“: {errors[0]}")

# --- Ergebnis ------------------------------------------------------------------------------------------------------------------------------

st.markdown("## 🎯 Ergebnis")
st.caption(f"Sensorboard mit {len(a.inst.comps)} Bauteilen und {len(a.inst.nets)} Netzen auf {a.inst.width} × {a.inst.height} Zellen, Netzlänge (HPWL) der Platzierung: {a.hpwl} Zellen.")
seq = a.metrics[C.METHODS[0]]
st.markdown("**Unverlegte Netze je Verlegeregel**")
cols = st.columns(3)
for col, method in zip(cols, C.METHODS):
    m = a.metrics[method]
    # Delta immer als „mein Wert minus Referenz“ (Referenz: sequentiell); die Farbe regelt delta_color="inverse" (Vorzeichen-Falle, DEMO-PLAYBOOK §2).
    if method == C.METHODS[0]:
        col.metric(method, f"{m['failed']} von {m['nets']}", delta="Referenz", delta_color="off")
    else:
        col.metric(method, f"{m['failed']} von {m['nets']}", delta=f"{m['failed'] - seq['failed']:+d} gegen sequentiell", delta_color="inverse")

view = st.radio("Verlegung anzeigen", C.METHODS, index=C.METHODS.index(C.DEFAULT_VIEW), horizontal=True, key="view_radio")
t1, t2 = st.columns(2)
show_top = t1.checkbox("Oberseite (rot)", value=True, key="show_top")
show_bottom = t2.checkbox("Unterseite (blau)", value=True, key="show_bottom")
shown = a.routings[view]
st.plotly_chart(build_board_figure(a.board, shown, a.inst, a.poses, show_top, show_bottom), width="stretch", key=f"board_{view}_{show_top}_{show_bottom}")
st.caption("Rot: Oberseite, blau: Unterseite, weißer Kreis: Via, orange gestrichelt: unverlegtes Netz (Luftlinie). Gehäuse der ICs sperren nur die Oberseite; Pads sind Durchsteckpads.")

rows = []
for method, m in a.metrics.items():
    rows.append({
        "Verlegeregel": method,
        "unverlegt": f"{m['failed']} von {m['nets']}",
        "Länge (Zellen)": m["wirelength"],
        "Vias": m["vias"],
        "Umweg (Länge / HPWL)": de(m["detour"], 2),
        "Suchläufe": m["searches"],
        "Iterationen": str(m["iterations"]) if method == C.METHODS[2] else "–",
        "konvergiert": ("ja" if m["converged"] else "nein") if method == C.METHODS[2] else "–",
    })
st.table(rows)
st.caption("Länge, Vias und Umweg zählen nur die verlegten Netze und sind zwischen Regeln nur vergleichbar, wenn gleich viele Netze verlegt sind (wer weniger Netze verlegt, hat kürzere Leiterbahnen).")
kind, text = ev.verdict_methods(a.metrics)
getattr(st, kind)(text)

if st.button("📄 PDF-Bericht erstellen", key="pdf_start"):
    from lpl_pdf_export import build_pdf

    st.session_state["pdf_done"] = (settings, view, build_pdf(a, view))
done = st.session_state.get("pdf_done")
if done and done[0] == settings and done[1] == view:
    st.download_button("⬇️ PDF herunterladen", data=done[2], file_name="leiterplatte-bericht.pdf", mime="application/pdf", key="pdf_download")

# --- Kernfrage -----------------------------------------------------------------------------------------------------------------------------

st.markdown("## ❓ Kernfrage: Entscheidet die Reihenfolge, ob alle Netze auf die Platine passen?")
with st.spinner("Verlege in vielen Reihenfolgen …"):
    spread = _spread(settings)
kind, text = ev.verdict_order(spread, len(a.inst.nets))
getattr(st, kind)(text)
st.plotly_chart(build_order_figure(spread, a.metrics[C.METHODS[1]]["failed"], a.metrics[C.METHODS[2]]["failed"]), width="stretch", key="order_chart")
st.caption("Balken: wie viele der Zufallsreihenfolgen wie viele Netze unverlegt lassen (sequentielles Verlegen, gleiche Platzierung). Linien: Rip-up und Negotiated Congestion auf derselben Platzierung.")

# --- Bestückung ----------------------------------------------------------------------------------------------------------------------------

st.markdown("## 🏭 Bestückung: wie setzt der Automat die Platine?")
st.markdown(
    "Die Bauteile dieser Platine (ohne die Stecker) werden von einem Portalautomaten gesetzt. Jeder Bauteiltyp liegt auf **einem Zuführplatz** einer Reihe unter dem Brett; der Kopf hat "
    "**k Düsen** und holt erst k Teile, setzt dann k Teile. Zwei Entscheidungen: **welcher Typ auf welchen Platz** und **in welcher Reihenfolge gesetzt wird**. "
    "Verglichen werden die **Maschinenpraxis** (häufigste Typen in die Mitte, nächstes Teil zuerst), **erst Plätze, dann Reihenfolge** (Ungarische Methode, danach nur die Reihenfolge), "
    "**abwechselnd** und **gemeinsam** (beides in einer Suche) bei gleichem Rechenbudget. Die Suche braucht einige Sekunden und läuft erst auf Klick."
)
bst_k = st.slider("Düsen am Kopf", C.BST_K_MIN, C.BST_K_MAX, C.BST_DEFAULT_K, key="bst_k",
                  help="Eine Düse: ein Teil holen, setzen. Mehr Düsen: erst k Teile holen, dann k setzen; je Runde werden alle k! Setzreihenfolgen geprüft.")
if st.button("Bestückung berechnen", key="bst_start"):
    st.session_state["bst_done"] = (settings, int(bst_k))
if st.session_state.get("bst_done") == (settings, int(bst_k)):
    with st.spinner("Suche Zuführplätze und Reihenfolge …"):
        bst = _bestueckung(settings, int(bst_k))
    if bst.violations:
        st.error(f"Prüfer meldet Fehler: {bst.violations[0]}")
    cols = st.columns(len(bst.plans))
    reference = bst.plans[0].cost
    for col, plan, gap in zip(cols, bst.plans, bst.gaps):
        # Delta immer als „mein Wert minus Referenz“ (Referenz: Maschinenpraxis); die Farbe regelt delta_color="inverse" (Vorzeichen-Falle, DEMO-PLAYBOOK §2).
        if plan is bst.plans[0]:
            col.metric(plan.method, f"{plan.cost:.1f}".replace(".", ","), delta="Referenz", delta_color="off")
        else:
            col.metric(plan.method, f"{plan.cost:.1f}".replace(".", ","), delta=f"{plan.cost - reference:+.1f}".replace(".", ",") + " gegen Praxis", delta_color="inverse")
    st.caption(f"Fahrstrecke des Kopfes in Rasterzellen (Tschebyscheff-Abstand), {bst.fi.n} Bestückorte, {bst.fi.n_types} Typen, {bst.fi.n_slots} Zuführplätze; Budget je Suchverfahren "
               f"{C.BST_EVALS_PER_PART * bst.fi.n} Kostenauswertungen.")
    kind, text = ev.verdict_bestueckung([p.cost for p in bst.plans], bst.k)
    getattr(st, kind)(text)
    st.plotly_chart(build_bestueck_methods_figure(bst.plans, bst.gaps), width="stretch", key="bst_methods_chart")
    bst_view = st.radio("Fahrt anzeigen", C.BST_METHODS, index=len(C.BST_METHODS) - 1, horizontal=True, key="bst_view")
    shown_plan = bst.plans[C.BST_METHODS.index(bst_view)]
    st.plotly_chart(build_bestueck_figure(bst.fi, shown_plan, bst.k, a.inst.width, a.inst.height), width="stretch", key=f"bst_route_{bst_view}")
    st.caption("Gestrichelt: der Kopf holt Teile an den Zuführplätzen, durchgezogen: er setzt sie. Die Zahl im Kreis ist der Platz in der Reihenfolge, die Farbe der Bauteiltyp. "
               "Gefüllte Quadrate: Zuführplätze mit ihrem Typ, offene: frei.")
    st.table([{"Zuführplatz": shown_plan.assignment[t] + 1, "Typ": bst.fi.type_names[t], "Teile": sum(1 for x in bst.fi.types if x == t)}
              for t in sorted(range(bst.fi.n_types), key=lambda t: shown_plan.assignment[t])])

st.markdown("---")

# --- Methodenvergleich ---------------------------------------------------------------------------------------------------------------------

with st.expander("🔧 Wie wir das erreichen – vollständiger Methodenvergleich"):
    tab_rules, tab_place, tab_via, tab_exact = st.tabs(["Die drei Verlegeregeln", "Platzierung", "Via-Kosten", "🧮 Exakt (OR-Tools)"])
    with tab_rules:
        st.plotly_chart(build_methods_figure(a.metrics), width="stretch", key="methods_chart")
        st.markdown(
            f"""
**Sequentiell.** Netz für Netz in der gewählten Reihenfolge: der kürzeste Weg durch alle noch freien Zellen (Dijkstra vom bisherigen Baum zum nächsten Pad). Was die früheren
Netze zugebaut haben, kommt nicht mehr durch; kein Netz wird je wieder angefasst.

**Rip-up and Reroute.** Erst sequentiell. Dann darf jedes unverlegte Netz gegen einen Zuschlag ({C.RRR_CROSS:g} Schritte je Zelle) **fremde Netze durchqueren**; diese werden aufgerissen,
das neue Netz wird festgelegt und die Opfer werden neu verlegt (jetzt um das neue Netz herum). Aufgerissene Zellen merken sich das, damit dieselbe Engstelle nicht immer
wieder geräumt wird. Aktionsgrenze: {C.RRR_ACTIONS_PER_NET} Aufreißvorgänge je Netz (ein größeres Budget verbessert Rip-up, kostet aber ein Vielfaches an Suchläufen); am Ende gilt der beste Stand.

**Negotiated Congestion (PathFinder).** Alle Netze dürfen sich zunächst Zellen **teilen**, das Teilen kostet aber: der Preis einer Zelle ist (1 + Verlauf) · (1 + Preis · Belegung).
Nach jedem Durchlauf steigt der Preis um den Faktor {C.PF_GROWTH:g}, überlastete Zellen erhöhen ihren Verlauf um {C.PF_HISTORY:g} je zusätzlichem Netz, und nur Netze auf überlasteten Zellen
werden neu verlegt. Ende: keine Zelle mehr doppelt belegt (konvergiert) oder die Iterationsgrenze ({a.settings.iterations}); dann bleibt die größte konfliktfreie Teilmenge der Netze.

Kein Verfahren ist vollständig: wenn eines Netze unverlegt lässt, heißt das nicht, dass es keine Lösung gibt. Nur der exakte Löser auf dem Mini-Brett kann Unlösbarkeit beweisen.
"""
        )
    with tab_place:
        st.markdown("Dieselbe Instanz mit den drei Platzierungsarten (sonst gleiche Einstellungen); verglichen werden die Netzlänge (HPWL) und die unverlegten Netze nach Negotiated Congestion.")
        if st.button("Platzierungen vergleichen", key="place_start"):
            st.session_state["place_done"] = settings
        if st.session_state.get("place_done") == settings:
            with st.spinner("Platziere und verlege dreimal …"):
                prow = _placements(settings)
            st.plotly_chart(build_placement_figure(prow), width="stretch", key="placement_chart")
            st.table([{"Platzierung": r["placement"], "HPWL": r["hpwl"], "unverlegt (sequentiell)": r["sequential"], "unverlegt (Rip-up)": r["rrr"],
                       "unverlegt (Negotiated Congestion)": r["negotiated"], "konvergiert": "ja" if r["converged"] else "nein"} for r in prow])
            kind, text = ev.verdict_placement(prow)
            getattr(st, kind)(text)
            st.caption("Eine Instanz ist keine Regel: die Messreihe über 20 feste Instanzen steht im README.")
    with tab_via:
        st.markdown("Negotiated Congestion auf derselben Platzierung bei Via-Kosten von 1, 4, 12 und 30 Zellenschritten.")
        if st.button("Via-Kosten vergleichen", key="via_start"):
            st.session_state["via_done"] = settings
        if st.session_state.get("via_done") == settings:
            with st.spinner("Verlege viermal …"):
                vrows = _vias(settings)
            st.plotly_chart(build_via_figure(vrows), width="stretch", key="via_chart")
            st.table([{"Via-Kosten": r["via_cost"], "Vias": r["vias"], "Länge (Zellen)": r["wirelength"], "unverlegt": r["failed"], "konvergiert": "ja" if r["converged"] else "nein"} for r in vrows])
            kind, text = ev.verdict_via(vrows)
            getattr(st, kind)(text)
    with tab_exact:
        # Der Tab ist selbstständig: eigener Button, Spinner und Ergebnis, gegen das aktuelle Szenario geprüft (DEMO-PLAYBOOK §2).
        st.markdown(
            "Auf einem **Mini-Brett** (5 bis 6 Netze, je zwei Pads) lässt sich alles nachprüfen: **alle Reihenfolgen** des sequentiellen Verlegens werden aufgezählt, "
            "und ein **exakter Löser** (OR-Tools CP-SAT, knotendisjunkte Wege kleinster Kosten) liefert eine Lösung oder beweist, dass es keine gibt. "
            "Die Via-Kosten und die Iterationsgrenze kommen aus der Seitenleiste."
        )
        mini_kind = st.selectbox("Mini-Brett", ("Handbeispiel (6 × 5, 5 Netze)", "Zufälliges Mini-Brett (Seed)"), key="mini_kind")
        if mini_kind.startswith("Hand"):
            spec = HAND_EXAMPLE
        else:
            mini_seed = st.number_input("Seed des Mini-Bretts", 0, C.SEED_MAX, value=300057, step=1, key="mini_seed")
            spec = random_mini(int(mini_seed))
        board_mini = mini_board(spec)
        st.plotly_chart(build_board_figure(board_mini, Routing("leer", ()), label_pads=True, height=340), width="stretch", key="mini_board_start")
        st.caption("Gold: Pads, beschriftet mit der Netznummer (jedes Netz hat zwei), graue Kreuze: gesperrte Zellen. Beim Zufalls-Seed 300057 (6 × 5, 5 Netze) klappt keine einzige Reihenfolge, obwohl der Löser eine Lösung findet.")
        if st.button("Alle Reihenfolgen aufzählen und exakt lösen", key="exact_start"):
            st.session_state["exact_done"] = (spec, settings.via_cost, settings.iterations)
        if st.session_state.get("exact_done") == (spec, settings.via_cost, settings.iterations):
            with st.spinner("Zähle Reihenfolgen auf und löse exakt …"):
                scan, rrr, pf, exact = _mini(spec, settings.via_cost, settings.iterations)
            kind, text = ev.verdict_exact(scan, rrr, pf, exact, len(spec.nets))
            getattr(st, kind)(text)
            v = float(settings.via_cost)
            st.table([
                {"Verfahren": "Sequentiell, beste Reihenfolge", "alle Netze verlegt": "ja" if scan.successes else "nein", "Kosten": de(scan.best_cost, 0) if scan.best_cost is not None else "–"},
                {"Verfahren": "Rip-up and Reroute", "alle Netze verlegt": "ja" if not rrr.failed else "nein", "Kosten": de(routing_cost(board_mini, rrr, v), 0) if not rrr.failed else "–"},
                {"Verfahren": "Negotiated Congestion", "alle Netze verlegt": "ja" if not pf.failed else "nein", "Kosten": de(routing_cost(board_mini, pf, v), 0) if not pf.failed else "–"},
                {"Verfahren": f"Exakt (CP-SAT, {exact.status})", "alle Netze verlegt": "ja" if exact.routing else "nein", "Kosten": de(exact.cost, 0) if exact.cost is not None else "–"},
            ])
            if exact.routing is not None:
                errs = check_feasible(board_mini, exact.routing)
                if errs:
                    st.error(f"Prüfer meldet Fehler in der exakten Lösung: {errs[0]}")
                st.plotly_chart(build_board_figure(board_mini, exact.routing, label_pads=True, height=340), width="stretch", key="mini_board_exact")
                st.caption("Lösung des exakten Lösers.")
            st.caption("Kosten: Schritte in der Ebene 1, Via-Schritt 1 plus Via-Kosten. Die Zeitgrenze des Lösers beträgt "
                       f"{C.EXACT_TIME_LIMIT:g} Sekunden; „feasible“ hieße: Lösung gefunden, Optimalität nicht bewiesen.")

# --- Mathematische Formulierung ------------------------------------------------------------------------------------------------------------

with st.expander("📐 Mathematische Formulierung"):
    st.markdown("**Platzierung.** Bauteil $i$ liegt in Lage $(x_i, y_i, r_i)$, $r_i \\in \\{0, 1\\}$ (um 90 Grad gedreht), Bauteile haben mindestens den Abstand $g = 2$ Zellen. Ziel ist die Summe der Halbumfänge")
    st.latex(r"\mathrm{HPWL} = \sum_{k} \Big[\big(\max_{p \in N_k} x_p - \min_{p \in N_k} x_p\big) + \big(\max_{p \in N_k} y_p - \min_{p \in N_k} y_p\big)\Big]")
    st.markdown("**Verlegen.** Knoten $(x, y, l)$ mit Lage $l \\in \\{0, 1\\}$, Kanten zwischen Nachbarzellen derselben Lage (Kosten 1) und das Via $(x, y, 0) \\leftrightarrow (x, y, 1)$ (Kosten $1 + c_\\mathrm{via}$). Gesucht sind Bäume $T_k$, die alle Pads von Netz $k$ verbinden, mit")
    st.latex(r"T_k \cap T_{k'} = \emptyset \quad (k \neq k'), \qquad \text{zuerst } \max \#\{k \text{ verlegt}\}, \text{ dann } \min \sum_k \mathrm{Kosten}(T_k).")
    st.markdown("Das ist NP-schwer; die Verfahren sind Heuristiken.")
    st.markdown("**Negotiated Congestion.** Kosten eines Knotens $v$ in Durchlauf $t$ mit Preis $p_t$, Verlauf $h_v$ und Belegung $o_v$ (Zahl der Netze auf $v$ ohne das gerade verlegte):")
    st.latex(r"c_t(v) = (1 + h_v)\,(1 + p_t\, o_v), \qquad p_{t+1} = %s\, p_t, \qquad h_v \leftarrow h_v + %s\,(o_v - 1)\ \text{bei Überlast.}" % (f"{C.PF_GROWTH:g}", f"{C.PF_HISTORY:g}"))
    st.markdown("**Exakter Löser (Mini-Brett, 2-Pin-Netze).** Binärvariablen $x_{k,a} \\in \\{0,1\\}$ je Netz $k$ und Bogen $a$; Flusserhaltung je Netz und Knoten (eine Einheit vom ersten Pad zum zweiten, beide Lagen am Pad erlaubt) und höchstens ein Netz je Knoten:")
    st.latex(r"\min \sum_{k,a} c_a\, x_{k,a} \quad \text{u. d. N.} \quad \sum_{a \in \delta^{-}(v)} x_{k,a} - \sum_{a \in \delta^{+}(v)} x_{k,a} = b_k(v), \qquad \sum_{k} \sum_{a \in \delta^{-}(v)} x_{k,a} + [v \text{ ist Start}] \le 1.")
    st.markdown("**Bestückung.** Bestückorte $j = 1, \\dots, n$ mit Position $p_j$ und Typ $\\tau(j)$; Zuführplätze $s = 1, \\dots, m$ mit Position $q_s$ ($m \\ge$ Zahl der Typen). Gesucht: eine **injektive Zuordnung** $\\sigma$ der Typen auf Plätze und eine **Reihenfolge** $\\pi$ der Bestückorte, die in Runden zu je $k$ Teilen gesetzt werden. Abstand $d(a, b) = \\max(|a_x - b_x|, |a_y - b_y|)$. Für $k = 1$ ist die Fahrt")
    st.latex(r"\sum_{i=1}^{n} \Big[ d\big(p_{\pi(i-1)},\, q_{\sigma(\tau(\pi(i)))}\big) + d\big(q_{\sigma(\tau(\pi(i)))},\, p_{\pi(i)}\big) \Big] + d\big(p_{\pi(n)},\, \text{Start}\big), \qquad p_{\pi(0)} = \text{Start}.")
    st.markdown("Bei **fester Reihenfolge** hängt jeder Summand von genau einem Platz ab: die Zuordnung ist dann ein lineares Zuordnungsproblem (Ungarische Methode, exakt); bei fester Zuordnung ist die Reihenfolge ein asymmetrisches Rundreiseproblem. Bei $k > 1$ kommen die Einteilung in Runden und je Runde die Reihenfolge von Holen und Setzen hinzu (alle $k!$ Setzreihenfolgen werden geprüft, das Holen läuft die Zuführgerade von einem Ende zum anderen ab).")

# --- Grenzen -------------------------------------------------------------------------------------------------------------------------------

with st.expander("🚧 Wo die Annahmen enden"):
    st.markdown(
        f"""
- **Kein reales Layout.** Die Instanzen sind synthetisch (Zufallsnetzliste mit zwei Steckern, ICs, Kondensatoren, Widerständen); es gibt keine Impedanz, keinen Takt, keine EMV, keine Wärme, keine
  Entwurfsregeln jenseits von Zellenabstand und Via-Kosten, keine Leiterbahnbreiten, keine Innenlagen und keine Versorgungsflächen. VCC und GND sind gewöhnliche Netze.
- **Das Raster ist die Entwurfsregel.** Eine Leiterbahn belegt je Zelle genau eine Zelle, Nachbarbahnen dürfen sich berühren; Pads sind Durchsteckpads auf beiden Lagen, Gehäuse von ICs sperren nur die Oberseite.
- **Heuristiken beweisen nichts.** Bleibt ein Netz unverlegt, kann es an der Regel oder am Brett liegen. Nur der exakte Löser kann Unlösbarkeit beweisen, und der nur auf Mini-Brettern mit 2-Pin-Netzen.
- **Die Platzierung ist kein Layouter.** Drei einfache Verfahren auf der Netzlänge (HPWL); keine Platzierung nach Verlegbarkeit, kein Ausrichten von Bauteilgruppen, keine Randbedingungen an Abstände zu Kanten.
- **Reihenfolge-Aussagen gelten für diese Netzreihenfolgen.** Gemessen wird sequentielles Verlegen im kürzesten Weg; andere Regeln (zum Beispiel „engste Netze zuerst“) sind nicht untersucht.
- **Bestückung ist ein Spielzeugmodell.** Ein Bestückort je Bauteil (ohne Stecker), ein Typ je Gehäuseart (ICs nach Pinzahl, Kondensator, Widerstand), ein Zuführplatz je Typ; keine Beschleunigung, keine Düsenwechsel, keine Teilehöhen, keine Bandbreiten, keine Zweiseitenbestückung, kein Nutzen mit mehreren Platinen. Die Zahlen sind Fahrstrecken in Rasterzellen, keine Maschinenzeiten; „kürzeste gefundene Fahrt“ ist keine bewiesene Untergrenze.
- **Rechenzeit.** Nicht gemessen, nur die Zahl der Suchläufe; Rip-up ist auf {C.RRR_ACTIONS_PER_NET} Aufreißvorgänge je Netz begrenzt, Negotiated Congestion auf die Iterationsgrenze der Seitenleiste.
"""
    )

st.markdown("---")
st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). "
    "Mehr zu den Demos: [Interaktive Demos](https://sebastianhanisch.net/demos.html)."
)
