"""Presets und Permalink: Vollständigkeit, gültige Werte, Standard-Preset = Standardeinstellungen, Begrenzen der Adresszeilenwerte."""

import pytest

import lpl_constants as C
import lpl_evaluation as ev
import lpl_presets as P


def test_every_preset_has_help_and_all_keys():
    assert set(C.PRESETS) == set(C.PRESET_HELP)
    for name, preset in C.PRESETS.items():
        assert set(preset) == set(P.PRESET_KEYS), name
        assert C.PRESET_HELP[name]


def test_preset_values_are_inside_the_control_bounds():
    for name, preset in C.PRESETS.items():
        for key, state_key in P.PRESET_KEYS.items():
            spec = P.SETTING_SPECS[state_key]
            if spec.choices is not None:
                assert preset[key] in spec.choices, (name, key)
            else:
                assert spec.lo <= preset[key] <= spec.hi, (name, key)


def test_default_preset_equals_the_default_settings():
    preset = C.PRESETS["Standardfall (Voreinstellung)"]
    assert ev.Settings(preset["n_ic"], preset["util"], preset["pin_use"], preset["placement"], preset["order"], preset["via"], preset["iterations"], preset["seed"]) == ev.Settings()


def test_setting_specs_cover_every_preset_key_and_the_first_preset_is_the_default():
    assert set(P.PRESET_KEYS.values()) == set(P.SETTING_SPECS)
    assert next(iter(C.PRESETS)) == "Standardfall (Voreinstellung)"
    assert all(P.SETTING_SPECS[k].default == C.PRESETS["Standardfall (Voreinstellung)"][key] for key, k in P.PRESET_KEYS.items())


def test_presets_differ_from_each_other():
    values = [tuple(p.values()) for p in C.PRESETS.values()]
    assert len(set(values)) == len(values)


@pytest.mark.parametrize("state_key,raw,expected", [
    ("util_slider", "99", C.UTIL_MAX),          # über der Grenze: auf die Grenze begrenzt
    ("util_slider", "-5", C.UTIL_MIN),
    ("util_slider", "abc", None),               # kein Zahlenwert: ignoriert
    ("placement_select", "Zufall", "Zufall"),
    ("placement_select", "Unsinn", None),       # nicht in der Auswahlliste: ignoriert
    ("seed_input", "123", 123),
    ("seed_input", "9999999", C.SEED_MAX),
])
def test_permalink_values_are_clamped_or_ignored(state_key, raw, expected):
    assert P._clean(P.SETTING_SPECS[state_key], raw) == expected


def test_url_params_are_unique():
    params = [s.url_param for s in P.SETTING_SPECS.values()]
    assert len(params) == len(set(params))
