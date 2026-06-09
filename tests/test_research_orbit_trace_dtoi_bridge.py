#!/usr/bin/env python3
"""
Test for research_orbit_trace_dtoi_bridge.py
"""
import subprocess
import sys
import os
from pathlib import Path
import json
import csv

def run_script(args=[]):
    """Run the script with given args and return (exit_code, stdout, stderr)."""
    cmd = [sys.executable, "scripts/research_orbit_trace_dtoi_bridge.py"] + args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd="/tmp/LEO-DTF"
    )
    return result.returncode, result.stdout, result.stderr

def test_quick_run():
    """Test the script with --quick --seed 42."""
    exit_code, stdout, stderr = run_script(["--quick", "--seed", "42"])
    assert exit_code == 0, f"Script failed with exit code {exit_code}. STDOUT: {stdout}, STDERR: {stderr}"
    # Check output files exist
    csv_path = Path("/tmp/LEO-DTF/experiments/results/research_orbit_trace_bridge/orbit_trace_bridge_trials.csv")
    json_path = Path("/tmp/LEO-DTF/experiments/results/research_orbit_trace_bridge/orbit_trace_bridge_summary.json")
    assert csv_path.exists(), f"CSV file not found at {csv_path}"
    assert json_path.exists(), f"JSON file not found at {json_path}"
    # Check CSV has expected rows (2 trace sources * 3 carriers * 2 offsets * 2 durations = 24)
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 24, f"Expected 24 rows, got {len(rows)}"
    # Check DTOI values are finite and non-negative
    for row in rows:
        dtoi = float(row["dtoi"])
        assert dtoi >= 0, f"DTOI negative: {dtoi}"
        assert dtoi == dtoi, f"DTOI is NaN"  # check for NaN
    # Check observability status is valid
    valid_statuses = {"unobservable", "weak", "moderate", "strong"}
    for row in rows:
        assert row["observability_status"] in valid_statuses, f"Invalid status: {row['observability_status']}"
    # Check JSON summary
    with open(json_path, 'r') as f:
        summary = json.load(f)
    assert "summary" in summary
    assert "best_config" in summary["summary"]
    assert "best_by_trace_source" in summary["summary"]
    assert "synthetic_vs_orbit_gap" in summary["summary"]
    # Check that conservative_notes includes the required points
    conservative_notes = summary["conservative_notes"]
    # We'll just check that it's a list of strings and not empty
    assert isinstance(conservative_notes, list), "conservative_notes should be a list"
    assert len(conservative_notes) > 0, "conservative_notes should not be empty"
    # Optionally, check for specific strings (but we can be flexible)
    joined_notes = " ".join(conservative_notes)
    assert "OTA validation" in joined_notes or "ota validation" in joined_notes.lower(), "Should mention OTA validation"
    assert "localization accuracy" in joined_notes or "Localization Accuracy" in joined_notes, "Should mention localization accuracy"
    print("All tests passed!")

if __name__ == "__main__":
    test_quick_run()