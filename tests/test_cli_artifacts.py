"""
CLI Artifact Smoke Tests
=========================
Verify that key scripts produce their expected output files.
Each test runs a script and checks that expected artifacts appear.
Tests are idempotent — they don't fail if artifacts already exist.

Run with: pytest -q
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "scripts"

# All scripts use the project's venv python
PYTHON = sys.executable


def run(script_name, args=None):
    """Run a script and return (returncode, stdout, stderr)."""
    cmd = [PYTHON, str(SCRIPTS / script_name)]
    if args:
        cmd.extend(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return result.returncode, result.stdout, result.stderr


def test_generate_synthetic_dataset():
    """Generate synthetic pass dataset."""
    rc, out, err = run("generate_synthetic_dataset.py")
    assert rc == 0, f"generate_synthetic_dataset.py failed:\n{err}"

    base = ROOT / "experiments" / "results" / "synthetic"
    assert (base / "synthetic_pass_dataset.json").exists(), \
        "synthetic_pass_dataset.json not found"
    assert (base / "synthetic_pass_observations.csv").exists(), \
        "synthetic_pass_observations.csv not found"


def test_run_ambiguity_ablation():
    """Run ambiguity/ablation study (1 trial, seed=42)."""
    rc, out, err = run("run_ambiguity_ablation.py", ["--trials", "1", "--seed", "42"])
    assert rc == 0, f"run_ambiguity_ablation.py failed:\n{err}"

    base = ROOT / "experiments" / "results" / "ablation"
    assert (base / "ambiguity_ablation_trials.csv").exists(), \
        "ambiguity_ablation_trials.csv not found"
    assert (base / "ambiguity_ablation_summary.json").exists(), \
        "ambiguity_ablation_summary.json not found"
    assert (ROOT / "paper" / "tables" / "ablation_summary.tex").exists(), \
        "ablation_summary.tex not found"


def test_summarize_evaluation():
    """Summarize evaluation outputs."""
    rc, out, err = run("summarize_evaluation.py")
    assert rc == 0, f"summarize_evaluation.py failed:\n{err}"

    base = ROOT / "experiments" / "results"
    assert (base / "evaluation_summary.json").exists(), \
        "evaluation_summary.json not found"
    assert (ROOT / "paper" / "tables" / "evaluation_summary.tex").exists(), \
        "evaluation_summary.tex not found"


def test_make_paper_figures():
    """Generate paper figures from results."""
    rc, out, err = run("make_paper_figures.py")
    assert rc == 0, f"make_paper_figures.py failed:\n{err}"

    fig_dir = ROOT / "paper" / "figures"
    assert (fig_dir / "dtf_concept.pdf").exists(), \
        "dtf_concept.pdf not found"
    assert (fig_dir / "ablation_summary.pdf").exists(), \
        "ablation_summary.pdf not found"
    assert (fig_dir / "crlb_sensitivity.pdf").exists(), \
        "crlb_sensitivity.pdf not found"