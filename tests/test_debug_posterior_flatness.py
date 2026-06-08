"""
Test for debug_posterior_flatness.py diagnostic script.
"""

import json
import os
import subprocess
import sys

import pytest


def test_script_runs_and_produces_output(tmp_path):
    """Script runs, JSON and CSV exist, have required keys."""
    result = subprocess.run(
        [sys.executable, "scripts/debug_posterior_flatness.py", "--seed", "42"],
        cwd="/tmp/LEO-DTF",
        capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, f"Script failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    json_path = "/tmp/LEO-DTF/experiments/results/debug_posterior_flatness/posterior_flatness_diagnostic.json"
    csv_path = "/tmp/LEO-DTF/experiments/results/debug_posterior_flatness/posterior_flatness_scores.csv"

    assert os.path.exists(json_path), f"JSON not found: {json_path}"
    assert os.path.exists(csv_path), f"CSV not found: {csv_path}"

    with open(json_path) as f:
        data = json.load(f)

    # Required keys
    required = [
        "score_dynamic_range", "posterior_entropy", "effective_sample_size",
        "max_prob", "uniform_prob", "max_prob_over_uniform",
        "true_rank", "true_prob", "map_prob", "map_error_m",
        "residual_at_true_cell", "residual_at_map_cell",
        "sigma_sweep",
    ]
    for k in required:
        assert k in data, f"Missing key: {k}"

    # Core metrics must be finite
    for k in ["score_dynamic_range", "posterior_entropy", "effective_sample_size",
              "max_prob_over_uniform", "true_rank"]:
        assert finite_and_valid(data[k]), f"Invalid {k}: {data[k]}"

    # Posterior sum approx 1
    assert 0.9 < data["posterior_sum"] < 1.1, f"posterior_sum={data['posterior_sum']} not near 1"

    # Residual metrics
    for cell in ["residual_at_true_cell", "residual_at_map_cell"]:
        r = data[cell]
        for k in ["residual_rms_hz", "residual_var_hz2", "residual_max_abs_hz", "reduced_chi2"]:
            assert k in r, f"Missing {k} in {cell}"
            assert finite_and_valid(r[k]), f"Invalid {k} in {cell}: {r[k]}"

        # Consistency: variance <= max_abs^2 + small tolerance (var <= max^2 for any dataset)
        assert r["residual_var_hz2"] <= r["residual_max_abs_hz"] ** 2 + 1e-6, \
            f"Inconsistent var={r['residual_var_hz2']} vs max^2={r['residual_max_abs_hz']**2}"

    # No NaN in CSV
    with open(csv_path) as f:
        lines = f.readlines()
    assert len(lines) > 1, "CSV is empty or has no data rows"
    for line in lines[1:]:  # skip header
        parts = line.strip().split(",")
        for p in parts[1:]:  # skip idx
            try:
                v = float(p)
                assert not (v != v), f"NaN in CSV line: {line}"
            except ValueError:
                pass  # prob may be scientific notation, that's fine

    print(f"\nFlatness diagnostic: score_dynamic_range={data['score_dynamic_range']:.4f}, "
          f"true_rank={data['true_rank']}, ESS={data['effective_sample_size']:.1f}, "
          f"trueRMS={data['residual_at_true_cell']['residual_rms_hz']:.4f}Hz, "
          f"reduced_chi2={data['residual_at_true_cell']['reduced_chi2']:.4f}")


def finite_and_valid(v):
    """Check a value is finite (not NaN or inf)."""
    try:
        return (v == v) and (v != float("inf")) and (v != float("-inf"))
    except (TypeError, ValueError):
        return False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])