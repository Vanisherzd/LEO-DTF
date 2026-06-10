#!/usr/bin/env python3
"""
Test for the orbit differential unit check script.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

def test_unit_check_script_runs_and_produces_output():
    # Run the unit check script
    result = subprocess.run([
        "uv", "run", "python",
        "scripts/research_orbit_differential_unit_check.py"
    ], capture_output=True, text=True)
    # The script should run successfully
    assert result.returncode == 0, f"Unit check script failed: {result.stderr}"

    # Define output paths
    out_dir = Path("experiments/results/research_orbit_unit_check")
    json_path = out_dir / "orbit_differential_unit_check.json"
    csv_path = out_dir / "orbit_differential_unit_trials.csv"
    md_path = out_dir / "orbit_differential_unit_check.md"

    # Assert JSON, CSV, and MD exist
    assert json_path.exists(), f"JSON output not found at {json_path}"
    assert csv_path.exists(), f"CSV output not found at {csv_path}"
    assert md_path.exists(), f"MD output not found at {md_path}"

    # Load JSON
    with open(json_path, 'r') as f:
        audit = json.load(f)

    # Assert JSON has required fields
    assert "offset_scaling_checks" in audit
    assert "carrier_scaling_checks" in audit
    assert "unit_checks" in audit
    assert "differential_mode_assessment" in audit
    assert "suspicious_flags" in audit
    assert "pass_fail_summary" in audit
    assert "conservative_interpretation" in audit
    assert "recommended_next_action" in audit

    # Assert conservative_interpretation mentions not OTA and not localization accuracy
    conservative = audit["conservative_interpretation"]
    assert "not OTA" in conservative or "not OTA validation" in conservative
    assert "not a localization accuracy" in conservative or "does not prove localization accuracy" in conservative

    # Assert pass_fail_summary exists (string)
    assert isinstance(audit["pass_fail_summary"], str)

    # Additionally, we can check that the script printed the output paths
    assert "Unit check JSON written to" in result.stdout
    assert "Unit check CSV written to" in result.stdout
    assert "Unit check Markdown written to" in result.stdout

if __name__ == "__main__":
    test_unit_check_script_runs_and_produces_output()
    print("All tests passed.")
