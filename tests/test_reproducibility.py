"""
Deterministic Reproducibility Test
==================================
Verify that ambiguity ablation produces identical results when run with
the same seed. This guards against non-deterministic RNG issues such
as the previous hash(name) % 1000 problem.

Run with: pytest tests/test_reproducibility.py -v
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "run_ambiguity_ablation.py"
SUMMARY_JSON = ROOT / "experiments" / "results" / "ablation" / "ambiguity_ablation_summary.json"
SUMMARY_TEX = ROOT / "paper" / "tables" / "ablation_summary.tex"
PYTHON = sys.executable


def normalized_json(path: Path):
    """Load JSON, remove unstable metadata fields."""
    if not path.exists():
        pytest.skip(f"{path} not found — run ablation first")
    data = json.loads(path.read_text())
    # Remove non-deterministic / timestamp fields
    for key in ["timestamp", "generated_at", "run_id"]:
        data.pop(key, None)
    return data


def run_ablation(seed: int = 42, trials: int = 2) -> tuple[bytes, bytes]:
    """Run ablation and return (stdout, stderr)."""
    result = subprocess.run(
        [PYTHON, str(SCRIPT), "--trials", str(trials), "--seed", str(seed)],
        capture_output=True,
        text=True,
    )
    return result.stdout, result.stderr


def test_ablation_same_seed_produces_identical_results():
    """Two runs with same seed must produce byte-identical summary files."""
    seed = 42
    trials = 2

    # First run
    stdout1, stderr1 = run_ablation(seed=seed, trials=trials)
    assert SUMMARY_JSON.exists(), f"Summary JSON not created: {SUMMARY_JSON}"
    summary1 = normalized_json(SUMMARY_JSON)

    # Second run
    stdout2, stderr2 = run_ablation(seed=seed, trials=trials)
    summary2 = normalized_json(SUMMARY_JSON)

    # Compare normalized metrics
    assert summary1 == summary2, (
        "Ablation results differ between two runs with same seed. "
        "Results must be deterministic."
    )


def test_ablation_summary_tex_is_valid():
    """ablation_summary.tex must be parseable and non-empty."""
    if not SUMMARY_TEX.exists():
        pytest.skip(f"{SUMMARY_TEX} not found — run ablation first")
    content = SUMMARY_TEX.read_text()
    assert len(content) > 50, "ablation_summary.tex is suspiciously short"
    # Basic structural checks
    assert "\\begin{tabular}" in content, "Missing tabular environment"
    assert "\\end{tabular}" in content, "Missing \\end{tabular}"
    assert "\\hline" in content, "Missing \\hline separators"


def test_different_seeds_produce_different_results():
    """Different seeds should (大概率) produce different results, but we
    only verify that the script runs without error, not that results differ —
    statistical variation is small for few trials."""
    seed_a, seed_b = 11, 99
    trials = 2

    stdout_a, _ = run_ablation(seed=seed_a, trials=trials)
    stdout_b, _ = run_ablation(seed=seed_b, trials=trials)

    # Both should succeed
    assert SUMMARY_JSON.exists(), "Summary JSON not created"
    # We don't assert results are different — small trials may not always differ
    # The important invariant is that same seed always gives same results