#!/usr/bin/env python3
"""
Test for research_claim_audit.py
"""
import subprocess
import sys
import os
from pathlib import Path
import json

def run_script(args=[]):
    """Run the script with given args and return (exit_code, stdout, stderr)."""
    cmd = [sys.executable, "scripts/research_claim_audit.py"] + args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd="/tmp/LEO-DTF"
    )
    return result.returncode, result.stdout, result.stderr

def test_claim_audit_generation():
    """Test that the script runs and generates the expected files."""
    exit_code, stdout, stderr = run_script([])
    assert exit_code == 0, f"Script failed with exit code {exit_code}. STDOUT: {stdout}, STDERR: {stderr}"
    # Check output files exist
    json_path = Path("/tmp/LEO-DTF/experiments/results/research_claim_audit/claim_audit.json")
    md_path = Path("/tmp/LEO-DTF/experiments/results/research_claim_audit/claim_audit.md")
    assert json_path.exists(), f"JSON file not found at {json_path}"
    assert md_path.exists(), f"MD file not found at {md_path}"
    # Check JSON is valid and has required keys
    with open(json_path, 'r') as f:
        data = json.load(f)
    required_keys = [
        "supported_claims",
        "conditional_claims",
        "unsupported_claims",
        "forbidden_claims",
        "evidence_map",
        "weakest_links",
        "strongest_results",
        "minimum_extra_experiments_before_paper",
        "recommended_positioning",
        "missing_inputs"
    ]
    for key in required_keys:
        assert key in data, f"Missing key '{key}' in audit JSON"
    # Check that the forbidden claims include the required ones
    forbidden = set(data["forbidden_claims"])
    required_forbidden = {
        "real OTA validation",
        "meter-level localization",
        "GNSS replacement",
        "single-pass always works",
        "multi-pass/multi-satellite solves localization",
        "HIL validation completed"
    }
    assert required_forbidden.issubset(forbidden), f"Forbidden claims missing some required: {required_forbidden - forbidden}"
    # Check that supported_claims includes at least the nuisance-aware DTOI / observability diagnostic
    supported_set = set(data["supported_claims"])
    assert any("nuisance-aware DTOI" in s or "observability diagnostic" in s for s in supported_set), \
        "Supported claims must include nuisance-aware DTOI as observability diagnostic"
    # Check that minimum_extra_experiments_before_paper has at least 4 items
    assert len(data["minimum_extra_experiments_before_paper"]) >= 4, \
        "Minimum extra experiments must have at least 4 items"
    print("All tests passed!")

if __name__ == "__main__":
    test_claim_audit_generation()