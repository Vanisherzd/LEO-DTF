#!/usr/bin/env python3
"""Test suite for DTOI derivation script."""

import sys, os
import numpy as np

# Add scripts dir to path for direct script imports
_script_dir = os.path.join(os.path.dirname(__file__), '..', 'scripts')
sys.path.insert(0, _script_dir)

# Also add src for leodtf imports
_src_dir = os.path.join(os.path.dirname(__file__), '..', 'src')
sys.path.insert(0, _src_dir)


# ─── Import from script ──────────────────────────────────────────────────────
from research_dtoi_derivation import (
    project_out_nuisance,
    compute_dtoi,
)


def test_project_out_nuisance_linear():
    """Linear combinations of [1, t] should be fully removed."""
    t_rel = np.linspace(0, 600, 11)

    # Constant vector -> fully removed
    const = np.ones(11) * 5.0
    proj_const, energy = project_out_nuisance(const, t_rel)
    assert np.allclose(proj_const, 0.0, atol=1e-10), \
        f"Constant not fully removed: max={np.max(np.abs(proj_const))}"
    assert energy > 0.99, f"Constant energy_removed={energy} too low"

    # Linear vector -> fully removed
    linear = 2.0 * t_rel
    proj_lin, energy = project_out_nuisance(linear, t_rel)
    assert np.allclose(proj_lin, 0.0, atol=1e-10), \
        f"Linear not fully removed: max={np.max(np.abs(proj_lin))}"
    assert energy > 0.99, f"Linear energy_removed={energy} too low"

    # Affine (constant + linear) -> fully removed
    affine = 3.0 + 1.5 * t_rel
    proj_aff, energy = project_out_nuisance(affine, t_rel)
    assert np.allclose(proj_aff, 0.0, atol=1e-10), \
        f"Afine not fully removed: max={np.max(np.abs(proj_aff))}"

    # Sinusoidal (NOT in subspace) -> should remain
    sin_vec = np.sin(2 * np.pi * t_rel / 600)
    proj_sin, energy = project_out_nuisance(sin_vec, t_rel)
    assert np.max(np.abs(proj_sin)) > 0.01, "Sinusoidal should not be fully removed"
    assert energy < 0.5, f"Sinusoidal energy_removed={energy} too high"


def test_dtoi_symmetry():
    """DTOI should be symmetric: DTOI(i,j) = DTOI(j,i)."""
    np.random.seed(42)
    g_i = np.random.randn(11)
    g_j = np.random.randn(11)
    t_rel = np.linspace(0, 600, 11)

    dtoi_ij, _ = compute_dtoi(g_i, g_j, t_rel, 1.0)
    dtoi_ji, _ = compute_dtoi(g_j, g_i, t_rel, 1.0)
    assert np.isclose(dtoi_ij, dtoi_ji, rtol=1e-10), \
        f"DTOI not symmetric: {dtoi_ij} vs {dtoi_ji}"


def test_dtoi_nuisance_reduces():
    """DTOI <= naive separability (nuisance projection can only reduce)."""
    np.random.seed(42)
    g_i = np.random.randn(11)
    g_j = np.random.randn(11)
    t_rel = np.linspace(0, 600, 11)

    diff = g_i - g_j
    naive = np.sqrt(np.mean(diff**2))
    dtoi, energy_removed = compute_dtoi(g_i, g_j, t_rel, 1.0)
    assert dtoi <= naive * 1.0001, f"DTOI={dtoi} should be <= naive={naive}"


def test_script_outputs():
    """Verify DTOI derivation script produces expected outputs."""
    import json, csv

    base = 'experiments/results/research_dtoi'
    assert os.path.exists(f'{base}/dtoi_examples.csv'), "CSV missing"
    assert os.path.exists(f'{base}/dtoi_summary.json'), "JSON missing"
    assert os.path.exists(f'{base}/dtoi_derivation.md'), "MD missing"

    rows = []
    with open(f'{base}/dtoi_examples.csv') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 3, f"Expected 3 rows, got {len(rows)}"

    for r in rows:
        naive = float(r['naive_separation_over_noise'])
        dtoi = float(r['nuisance_projected_dtoi'])
        energy = float(r['percent_energy_removed_by_cfo_drift'])

        assert np.isfinite(naive)
        assert np.isfinite(dtoi)
        assert np.isfinite(energy)
        assert 0 <= energy <= 100
        assert dtoi <= naive * 1.01, f"DTOI={dtoi} > naive={naive}"

    with open(f'{base}/dtoi_summary.json') as f:
        summary = json.load(f)

    assert 'key_findings' in summary
    assert 'dtoi_interpretation' in summary
    assert 'dtoi_less_than_naive' in summary['key_findings']
    assert summary['key_findings']['dtoi_less_than_naive'] is True


def test_dtoi_finite():
    """DTOI should be finite and non-negative for all examples."""
    import csv

    base = 'experiments/results/research_dtoi'
    with open(f'{base}/dtoi_examples.csv') as f:
        rows = list(csv.DictReader(f))

    for r in rows:
        dtoi = float(r['nuisance_projected_dtoi'])
        assert not np.isnan(dtoi) and not np.isinf(dtoi), f"DTOI is NaN/Inf: {r}"
        assert dtoi >= 0, f"DTOI is negative: {r}"


if __name__ == '__main__':
    # Run from repo root
    os.chdir(os.path.join(os.path.dirname(__file__), '..'))
    test_project_out_nuisance_linear()
    print("PASS: test_project_out_nuisance_linear")
    test_dtoi_symmetry()
    print("PASS: test_dtoi_symmetry")
    test_dtoi_nuisance_reduces()
    print("PASS: test_dtoi_nuisance_reduces")
    test_script_outputs()
    print("PASS: test_script_outputs")
    test_dtoi_finite()
    print("PASS: test_dtoi_finite")
    print("\nAll DTOI tests passed.")