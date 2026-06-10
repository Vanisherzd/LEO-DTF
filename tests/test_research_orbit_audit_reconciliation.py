#!/usr/bin/env python3
"""
Test for research_orbit_audit_reconciliation.py
"""
import subprocess
import sys
import os
from pathlib import Path
import json

def run_script(args=[]):
    """Run the script with given args and return (exit_code, stdout, stderr)."""
    cmd = [sys.executable, "scripts/research_orbit_audit_reconciliation.py"] + args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd="/tmp/LEO-DTF"
    )
    return result.returncode, result.stdout, result.stderr

def test_reconciliation_run():
    """Test the script runs successfully and produces expected output files."""
    exit_code, stdout, stderr = run_script([])
    assert exit_code == 0, f"Script failed with exit code {exit_code}. STDOUT: {stdout}, STDERR: {stderr}"

    # Check output files exist
    base_dir = Path("/tmp/LEO-DTF/experiments/results")
    json_path = base_dir / "research_orbit_audit_reconciliation" / "orbit_audit_reconciliation.json"
    md_path = base_dir / "research_orbit_audit_reconciliation" / "orbit_audit_reconciliation.md"
    assert json_path.exists(), f"JSON file not found at {json_path}"
    assert md_path.exists(), f"MD file not found at {md_path}"

    # Load JSON and check required fields
    with open(json_path, 'r') as f:
        data = json.load(f)

    # Check required top-level fields
    required_fields = [
        "input_availability",
        "c10_summary",
        "c10a_scale_flags",
        "c11_unit_check_summary",
        "c12_source_audit_summary",
        "contradiction_matrix",
        "likely_root_cause",
        "claim_status",
        "conservative_interpretation",
        "recommended_next_action"
    ]
    for field in required_fields:
        assert field in data, f"Missing field '{field}' in JSON"

    # Check claim_status for c10_orbit_dtoi_507
    assert data["claim_status"]["c10_orbit_dtoi_507"] == "not_claimable_pending_reconciliation", \
        f"Expected c10_orbit_dtoi_507 to be 'not_claimable_pending_reconciliation', got {data['claim_status']['c10_orbit_dtoi_507']}"

    # Before C14, the reconciliation was expected to contain contradictions.
    # After C14 fixed orbit-driven differential Doppler, an empty contradiction
    # matrix is a valid resolved state. The test should accept both, as long as
    # the JSON explicitly carries claim status and a next action.
    assert isinstance(data["contradiction_matrix"], list)

    # Check conservative_interpretation mentions not OTA and not localization accuracy
    cons_interp = data["conservative_interpretation"].lower()
    assert "ota" in cons_interp and "validation" in cons_interp, "Conservative interpretation should mention OTA validation"
    assert "localization" in cons_interp and "accuracy" in cons_interp, "Conservative interpretation should mention localization accuracy"

    # Check recommended_next_action is non-empty
    assert len(data["recommended_next_action"]) > 0, "recommended_next_action should be non-empty"

    print("All tests passed!")

if __name__ == "__main__":
    test_reconciliation_run()