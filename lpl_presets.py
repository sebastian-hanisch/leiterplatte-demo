"""Permalink (Begrenzen), Presets und Zufalls-Seed-Button (Standardmuster aus dem Demo-Portfolio)."""

import random
from dataclasses import dataclass

import streamlit as st

import lpl_constants as C


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: type
    default: object
    lo: object = None          # Reglergrenzen; bei Auswahllisten die erste und die letzte Auswahl
    hi: object = None
    choices: tuple | None = None


SETTING_SPECS = {
    "n_ic_slider": SettingSpec("ic", int, C.DEFAULT_N_IC, C.N_IC_MIN, C.N_IC_MAX),
    "util_slider": SettingSpec("dichte", int, C.DEFAULT_UTIL, C.UTIL_MIN, C.UTIL_MAX),
    "pin_use_slider": SettingSpec("pins", int, C.DEFAULT_PIN_USE, C.PIN_USE_MIN, C.PIN_USE_MAX),
    "placement_select": SettingSpec("platz", str, C.DEFAULT_PLACEMENT, C.PLACEMENTS[0], C.PLACEMENTS[-1], C.PLACEMENTS),
    "order_select": SettingSpec("reihe", str, C.DEFAULT_ORDER, C.ORDERS[0], C.ORDERS[-1], C.ORDERS),
    "via_slider": SettingSpec("via", int, C.DEFAULT_VIA, C.VIA_MIN, C.VIA_MAX),
    "iter_slider": SettingSpec("iter", int, C.DEFAULT_ITER, C.ITER_MIN, C.ITER_MAX),
    "seed_input": SettingSpec("seed", int, C.DEFAULT_SEED, 0, C.SEED_MAX),
}
PRESET_KEYS = {
    "n_ic": "n_ic_slider", "util": "util_slider", "pin_use": "pin_use_slider", "placement": "placement_select",
    "order": "order_select", "via": "via_slider", "iterations": "iter_slider", "seed": "seed_input",
}


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def choices(state_key):
    return SETTING_SPECS[state_key].choices


def _clean(spec: SettingSpec, raw):
    """Wert aus der Adresszeile: auf die Reglergrenzen begrenzt, bei Auswahllisten nur gültige Einträge; sonst None."""
    try:
        value = spec.caster(raw)
    except (ValueError, TypeError):
        return None
    if spec.choices is not None:
        return value if value in spec.choices else None
    return min(spec.hi, max(spec.lo, value))


def load_permalink_settings():
    """Einmal je Sitzung: Werte aus der Adresszeile übernehmen, auf die Reglergrenzen begrenzt."""
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            value = _clean(spec, qp[spec.url_param])
            if value is not None:
                st.session_state[state_key] = value
    st.session_state["permalink_loaded"] = True


def sync_query_params(values):
    """`values`: {state_key: aktueller Wert}; die Adresszeile spiegelt die Konfiguration."""
    try:
        for state_key, value in values.items():
            st.query_params[SETTING_SPECS[state_key].url_param] = str(value)
    except Exception:
        pass


def apply_preset(name):
    for key, state_key in PRESET_KEYS.items():
        if key in C.PRESETS[name]:
            st.session_state[state_key] = C.PRESETS[name][key]


def aktives_preset():
    """Name des Presets, dessen Werte GENAU den aktuellen Einstellungen entsprechen, sonst None.

    Zustandslos: verglichen wird jeder Regler aus SETTING_SPECS (ein Preset ohne Eintrag für einen Regler meint dessen
    Standardwert) mit dem Session State. Ein später ergänzter Regler braucht nur seinen Eintrag in SETTING_SPECS,
    dann hebt auch seine Änderung die Markierung auf (tests/test_layout.py prüft das für jeden Regler)."""
    preset_key_of = {state_key: key for key, state_key in PRESET_KEYS.items()}
    for name, preset in C.PRESETS.items():
        if all(
            st.session_state.get(state_key, spec.default) == preset.get(preset_key_of.get(state_key), spec.default)
            for state_key, spec in SETTING_SPECS.items()
        ):
            return name
    return None


def sidebar_presets():
    """Schnellstart oben in der Seitenleiste; das aktive Preset ist hervorgehoben (`type="primary"`)."""
    if not C.PRESETS:
        return
    st.header("🎯 Schnellstart")
    st.caption("Ein Beispielszenario laden:")
    aktiv = aktives_preset()
    for name in C.PRESETS:
        st.button(
            name, width="stretch", on_click=apply_preset, args=(name,), help=C.PRESET_HELP.get(name, ""), key=f"preset_{name}",
            type="primary" if aktiv == name else "secondary",
        )


def randomize_seed():
    st.session_state["seed_input"] = random.randint(0, C.SEED_MAX)
