"""Konstanten: Regler-Grenzen, feste Annahmen, Farben und Presets."""

# --- Reglergrenzen (Komplexität am Maximum: Raster 2 * W * H Knoten, je Netz höchstens Pins - 1 Suchläufe) ----------------------------------
N_IC_MIN, N_IC_MAX, DEFAULT_N_IC = 2, 8, 6            # bei 8 ICs rund 45 mal 33 Zellen und etwa 28 Netze
UTIL_MIN, UTIL_MAX, DEFAULT_UTIL = 40, 75, 60         # Dichte in Prozent: Bauteilfläche samt Abstand / Brettfläche
PIN_USE_MIN, PIN_USE_MAX, DEFAULT_PIN_USE = 50, 100, 85  # Prozent der freien IC-Pins, die in einem Signalnetz hängen
VIA_MIN, VIA_MAX, DEFAULT_VIA = 1, 30, 4              # Zusatzkosten eines Vias in Zellenschritten
ITER_MIN, ITER_MAX, DEFAULT_ITER = 10, 100, 60        # Iterationsgrenze von Negotiated Congestion: O(Iterationen * Netze * N log N)
SEED_MAX, DEFAULT_SEED = 999999, 35

PLACEMENTS = ("Zufall", "Quadratisch", "Simulated Annealing")
ORDERS = ("Kurze Netze zuerst", "Lange Netze zuerst", "Reihenfolge der Netzliste", "Zufällig")
METHODS = ("Sequentiell", "Rip-up and Reroute", "Negotiated Congestion")
DEFAULT_PLACEMENT, DEFAULT_ORDER, DEFAULT_VIEW = PLACEMENTS[2], ORDERS[0], METHODS[2]

# --- feste Annahmen des Modells ------------------------------------------------------------------------------------------------------------
GAP = 2                    # Mindestabstand zwischen Bauteilen in Zellen
CONN_PINS = 6              # Pins je Stecker
IC_WIDTH = 4               # ICs: zwei Pinreihen im Abstand 3, Gehäuse dazwischen
IC_ROWS = (3, 4, 5, 6)     # Pins je Reihe
N_CLUSTERS = 2             # Signalnetze bleiben meist im Cluster
SA_MOVES = 20000           # Züge des Simulated Annealing (fest: gleiche Rechenzeit in jeder Instanz)
MARGIN = 8                 # erste Suche nur im Rechteck der Pins plus dieser Rand, danach auf dem ganzen Brett
RRR_ACTIONS_PER_NET = 3    # Aktionsgrenze von Rip-up and Reroute: so viele Aufreißvorgänge je Netz (12 lässt weniger Netze unverlegt, kostet aber fast das Dreifache an Suchläufen: README, Grenzen)
RRR_CROSS = 6.0            # Zuschlag, mit dem Rip-up eine fremde Zelle durchquert
PF_START, PF_GROWTH, PF_HISTORY = 0.6, 1.6, 0.5  # Negotiated Congestion: Start, Wachstum je Iteration und Verlaufsgewicht
ORDER_SAMPLES = 20         # Zufallsreihenfolgen im Kernfragen-Experiment
SWEEP_SEEDS = tuple(range(100000, 100020))  # feste Instanzen für alle Sweeps: nie ein einzelner Seed als Befund
SWEEP_UTILS = (50, 60, 70)

# --- Mini-Brett des Exakt-Tabs -------------------------------------------------------------------------------------------------------------
MINI_MAX_ORDERS = 720      # bis 6 Netze: alle Reihenfolgen aufzählbar
EXACT_TIME_LIMIT = 20.0    # Sekunden für CP-SAT
EXACT_WORKERS = 4

# --- Bestückung (Folgestück in derselben Demo) --------------------------------------------------------------------------------------------
BST_K_MIN, BST_K_MAX, BST_DEFAULT_K = 1, 4, 4      # Düsen am Kopf; je Runde k! Setzreihenfolgen, daher höchstens 4
BST_METHODS = ("Maschinenpraxis", "Erst Plätze, dann Reihenfolge", "Abwechselnd", "Gemeinsam")
BST_EXTRA_SLOTS = 4        # freie Zuführplätze über die Typenzahl hinaus
BST_PITCH = 3.0            # Abstand der Zuführplätze in Rasterzellen
BST_ROW_OFFSET = 3         # Zuführreihe liegt so viele Zellen unter dem Brett
BST_EVALS_PER_PART = 600   # Kostenauswertungen je Bestückort und Verfahren (gleich für alle Suchverfahren): O(Auswertungen * Runden * k!)

# --- Farben --------------------------------------------------------------------------------------------------------------------------------
COLOR_TOP = "#d6604d"
COLOR_BOTTOM = "#4393c3"
COLOR_VIA = "#222222"
COLOR_UNROUTED = "#e08214"
COLOR_BODY = "rgba(120,120,120,0.35)"
COLOR_PAD = "#b8860b"
COLOR_CHOSEN = "#2F6B65"
COLOR_OTHER = "rgba(150,150,150,0.55)"
COLOR_LINE = "#4c78a8"


def _preset(**kw):
    """Ein Preset nennt jeden Regler; was nicht abweicht, steht auf dem Standardwert."""
    base = dict(n_ic=DEFAULT_N_IC, util=DEFAULT_UTIL, pin_use=DEFAULT_PIN_USE, placement=DEFAULT_PLACEMENT, order=DEFAULT_ORDER, via=DEFAULT_VIA,
                iterations=DEFAULT_ITER, seed=DEFAULT_SEED)
    base.update(kw)
    return base


PRESETS = {
    "Standardfall (Voreinstellung)": _preset(),
    "Reihenfolge-Falle": _preset(order=ORDERS[1], seed=19),
    "Dichtes Brett": _preset(util=72, seed=2),
    "Zu dicht": _preset(util=72, seed=21),
    "Zufällige Platzierung": _preset(util=55, placement=PLACEMENTS[0], seed=4),
    "Lockeres Brett": _preset(n_ic=4, util=45, seed=8),
}
PRESET_HELP = {
    "Standardfall (Voreinstellung)": "Sensorboard mit 6 ICs bei 60 % Dichte, Simulated-Annealing-Platzierung, kurze Netze zuerst: sequentielles Verlegen lässt mehrere Netze unverlegt, Verhandeln bringt alle unter.",
    "Reihenfolge-Falle": "Die langen Netze werden zuerst verlegt: auf diesem Brett bleiben sequentiell 10 statt 3 Netze unverlegt; Verhandeln bringt trotzdem alle unter.",
    "Dichtes Brett": "72 % Dichte: wenig Platz zwischen den Bauteilen. Rip-up and Reroute lässt noch Netze offen, Negotiated Congestion bringt hier alle unter.",
    "Zu dicht": "72 % Dichte, mehr Netze: auch Negotiated Congestion konvergiert nicht. Ob das Brett wirklich unlösbar ist, weiß keines der Verfahren; nur der exakte Löser auf dem Mini-Brett kann es beweisen.",
    "Zufällige Platzierung": "Bauteile zufällig gesetzt statt optimiert: lange Netze, viel Gedränge. Zeigt, wie viel die Platzierung an der Verlegbarkeit ändert.",
    "Lockeres Brett": "4 ICs bei 45 % Dichte: Hier gibt es nichts zu verhandeln, schon die einfache Reihenfolge bringt alle Netze unter.",
}
