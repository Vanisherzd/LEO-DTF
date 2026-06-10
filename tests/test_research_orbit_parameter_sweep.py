#!/usr/bin/env python3
"""
Test for LEO-DTF Orbit-Driven Parameter Sweep (C19)
"""

import json
import os
import subprocess
import sys
from pathlib import Path

def test_sweep_script():
    """Run the sweep script with --quick and verify outputs."""
    # Change to the LEO-DTF directory
    base_dir = Path(__file__).parent.parent
    script_path = base_dir / "scripts" / "research_orbit_parameter_sweep.py"
    
    # Run the script with --quick and --seed 42 for reproducibility
    result = subprocess.run(
        [sys.executable, str(script_path), "--quick", "--seed", "42"],
        cwd=base_dir,
        capture_output=True,
        text=True
    )
    
    # Check that the script ran successfully
    assert result.returncode == 0, f"Script failed with exit code {result.returncode}\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    
    # Define the output directory
    results_dir = base_dir / "experiments" / "results" / "research_orbit_parameter_sweep"
    json_path = results_dir / "orbit_parameter_sweep_summary.json"
    md_path = results_dir / "orbit_parameter_sweep_summary.md"
    csv_path = results_dir / "orbit_parameter_sweep_trials.csv"
    
    # Assert JSON, MD, and CSV exist
    assert json_path.exists(), f"JSON file not found at {json_path}"
    assert md_path.exists(), f"MD file not found at {md_path}"
    assert csv_path.exists(), f"CSV file not found at {csv_path}"
    
    # Load the JSON
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    # Define required top-level fields
    required_fields = [
        "metadata",
        "sweep_dimensions",
        "total_trials",
        "completed_trials",
        "best_config",
        "best_by_carrier",
        "best_by_offset",
        "best_by_duration",
        "best_by_seed",
        "stability_summary",
        "suspicious_flags",
        "claim_status",
        "conservative_interpretation",
        "recommended_next_action"
    ]
    
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"
    
    # Assert completed_trials > 0
    assert data["completed_trials"] > 0, f"Expected at least one completed trial, got {data['completed_trials']}"
    
    # Assert trial rows exist in CSV (we can check by reading the CSV and counting lines > 1)
    with open(csv_path, 'r') as f:
        lines = f.readlines()
    assert len(lines) > 1, f"CSV should have header and at least one data row, got {len(lines)} lines"
    
    # Assert best_config has dtoi
    assert "dtoi" in data["best_config"], "best_config must have dtoi field"
    assert isinstance(data["best_config"]["dtoi"], (int, float)), "dtoi must be numeric"
    
    # Assert suspicious_flags is a list
    assert isinstance(data["suspicious_flags"], list), "suspicious_flags must be a list"
    
    # Assert claim_status says diagnostic only / not OTA / no localization accuracy
    claim = data["claim_status"]
    assert claim["diagnostic_only_not_OTA"] == True, "claim_status.diagnostic_only_not_OTA must be True"
    assert claim["no_localization_accuracy_claim"] == True, "claim_status.no_localization_accuracy_claim must be True"
    assert claim["no_real_satellite_capture_claim"] == True, "claim_status.no_real_satellite_capture_claim must be True"
    assert claim["no_HIL_claim"] == True, "claim_status.no_HIL_claim must be True"
    
    # Assert conservative_interpretation mentions not OTA and not localization
    interp = data["conservative_interpretation"]
    interp_str = " ".join(interp).lower()
    assert "not ota" in interp_str or "does not create ota" in interp_str, "Conservative interpretation must mention not OTA"
    assert "not localization" in interp_str or "does not create localization" in interp_str, "Conservative interpretation must mention not localization"
    
    # Assert no DTOI=507 positive claim appears in MD
    with open(md_path, 'r') as f:
        md_content = f.read()
    assert "DTOI=507" not in md_content, "Markdown must not contain DTOI=507 as a positive claim"
    # Also check for any positive claim about 507
    assert "507" not in md_content or "old DTOI=507" in md_content or "resolved" in md_content, "Markdown must not positively claim DTOI=507"
    
    # Assert if differential_mode_confirmed field exists in CSV, it is true for orbit-driven trials
    # We can check the CSV for the differential_mode_confirmed column
    import csv
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        for row in rows:
            # The sweep script sets differential_mode_confirmed to True for all orbit_driven_fallback trials
            assert row["differential_mode_confirmed"] == "True", f"Expected differential_mode_confirmed to be True, got {row['differential_mode_confirmed']}"
    
    # Additionally, we can check that the sweep dimensions in metadata match the quick settings
    # But we can skip for brevity.

    print("All tests passed!")

if __name__ == "__main__":
    test_sweep_script()