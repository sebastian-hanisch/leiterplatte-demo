"""Dasselbe Szenario mit gleichem Seed ergibt in zwei Prozessen mit verschiedener Hash-Randomisierung dasselbe (DEMO-PLAYBOOK §1d)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = (
    "import lpl_evaluation as ev; a = ev.analyse(ev.Settings(n_ic=3, util=60, seed=5));"
    "print(a.hpwl, [(m, sorted(a.routings[m].failed), v['wirelength'], v['vias']) for m, v in a.metrics.items()]);"
    "b = ev.bestueckung_for(a, 2); print([(p.assignment, p.sequence, p.cost) for p in b.plans])"
)


def _run(hash_seed):
    env = {"PYTHONHASHSEED": str(hash_seed), "SYSTEMROOT": r"C:\Windows", "PATH": ""}
    out = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, r'{ROOT}'); {SCRIPT}"], capture_output=True, text=True, env=env, check=True)
    return out.stdout


def test_two_processes_with_different_hash_seeds_agree():
    assert _run(1) == _run(2)
