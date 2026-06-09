"""
Test for research_observability_threshold.py diagnostic script.
"""

import json
import os
import subprocess
import sys

import pytest


def test_quick_run_produces_output():
    """Run the script in quick mode and verify output files."""
    result = subprocess.run(
        [sys.executable, "scripts/research_observability_threshold.py",
         "--quick", "--seed", "42"],
        cwd="/tmp/LEO-DTF",
        capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, f"Script failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    json_path = "/tmp/LEO-DTF/experiments/results/research_observability_threshold/observability_threshold_summary.json"
    csv_path = "/tmp/LEO-DTF/experiments/results/research_observability_threshold/observability_threshold_trials.csv"

    assert os.path.exists(json_path), f"JSON not found: {json_path}"
    assert os.path.exists(csv_path), f"CSV not found: {csv_path}"

    with open(json_path) as f:
        data = json.load(f)

    # Required top-level keys
    assert 'metadata' in data, "Missing metadata"
    assert 'summary' in data, "Missing summary"
    assert 'thresholds' in data, "Missing thresholds"

    m = data['metadata']
    assert m['seed'] == 42
    assert m['quick'] is True
    assert m['total_configs'] > 0

    s = data['summary']
    assert 'count_unobservable' in s
    assert 'count_weak' in s
    assert 'count_moderate' in s
    assert 'count_strong' in s
    assert 'best_separation_over_noise' in s
    assert 'worst_separation_over_noise' in s

    t = data['thresholds']
    assert 'count_over_1' in t
    assert 'count_over_3' in t
    assert 'count_over_10' in t

    # CSV has rows
    with open(csv_path) as f:
        lines = f.readlines()
    assert len(lines) > 1, "CSV has no data rows"

    # All separation_over_noise values are finite and >= 0
    import csv as csvmod
    with open(csv_path) as f:
        reader = csvmod.DictReader(f)
        rows = list(reader)
    assert len(rows) > 0, "CSV has no data rows"

    for row in rows:
        sn = float(row['separation_over_noise'])
        assert sn == sn and sn >= 0, f"Invalid separation_over_noise: {sn}"
        assert row['observability_status'] in ['unobservable', 'weak', 'moderate', 'strong'], \
            f"Unknown status: {row['observability_status']}"

    print(f"\nObservability quick run: {m['total_configs']} configs, "
          f"unobservable={s['count_unobservable']}, weak={s['count_weak']}, "
          f"moderate={s['count_moderate']}, strong={s['count_strong']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])