#!/usr/bin/env python3
"""
Test for LEO-DTF Post-Fix Orbit Audit Refresh Script (C15)
"""

import json
import os
import subprocess
import sys
from pathlib import Path

def test_refresh_script():
    """Run the refresh script and verify outputs."""
    # Change to the LEO-DTF directory
    base_dir = Path(__file__).parent.parent
    script_path = base_dir / "scripts" / "research_orbit_postfix_audit_refresh.py"
    
    # Run the script
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=base_dir,
        capture_output=True,
        text=True
    )
    
    # Check that the script ran successfully
    assert result.returncode == 0, f"Script failed with exit code {result.returncode}\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    
    # Define the output directory
    results_dir = base_dir / "experiments" / "results" / "research_orbit_postfix_refresh"
    json_path = results_dir / "orbit_postfix_refresh_summary.json"
    md_path = results_dir / "orbit_postfix_refresh_summary.md"
    
    # Assert JSON and MD exist
    assert json_path.exists(), f"JSON file not found at {json_path}"
    assert md_path.exists(), f"MD file not found at {md_path}"
    
    # Load the JSON
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    # Define required fields
    required_fields = [
        "executed_steps",
        "c10_postfix_best_config",
        "c10a_postfix_scale_flags",
        "c11_postfix_unit_summary",
        "c12_postfix_source_summary",
        "c13_postfix_reconciliation_summary",
        "previous_issue_status",
        "postfix_claim_status",
        "conservative_interpretation",
        "recommended_next_action"
    ]
    
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"
    
    # Assert executed_steps length >= 5
    assert len(data["executed_steps"]) >= 5, f"Expected at least 5 executed steps, got {len(data['executed_steps'])}"
    
    # Assert postfix_claim_status values
    claim = data["postfix_claim_status"]
    assert claim["orbit_dtoi_after_c14"] == "diagnostic_only_not_OTA", \
        f"Expected orbit_dtoi_after_c14 to be 'diagnostic_only_not_OTA', got '{claim['orbit_dtoi_after_c14']}'"
    assert claim["localization_accuracy"] == "not_claimed", \
        f"Expected localization_accuracy to be 'not_claimed', got '{claim['localization_accuracy']}'"
    assert claim["real_satellite_capture"] == "not_claimed", \
        f"Expected real_satellite_capture to be 'not_claimed', got '{claim['real_satellite_capture']}'"
    
    # Assert conservative_interpretation mentions not OTA and not localization accuracy
    interp = data["conservative_interpretation"]
    assert any("Not OTA validation." in item for item in interp), \
        "Conservative interpretation must contain 'Not OTA validation.'"
    assert any("Does not prove localization accuracy." in item for item in interp), \
        "Conservative interpretation must contain 'Does not prove localization accuracy.'"
    
    # Assert recommended_next_action is non-empty
    assert data["recommended_next_action"].strip() != "", "Recommended next action must be non-empty"
    
    # Additionally, we can check that the script produced the expected output files in the steps
    # But the above should be sufficient.

if __name__ == "__main__":
    test_refresh_script()
    print("All tests passed!")