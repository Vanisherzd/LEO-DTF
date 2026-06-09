#!/usr/bin/env python3
"""
Test for research_synthesize_contribution.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

def run_script():
    """Run the synthesis script and return (exit_code, stdout, stderr)."""
    cmd = [sys.executable, "scripts/research_synthesize_contribution.py"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd="/tmp/LEO-DTF"
    )
    return result.returncode, result.stdout, result.stderr

def test_script_runs():
    """Test that the script runs successfully."""
    exit_code, stdout, stderr = run_script()
    assert exit_code == 0, f"Script failed with exit code {exit_code}. STDOUT: {stdout}, STDERR: {stderr}"
    # Check that output files are created
    output_json = Path("/tmp/LEO-DTF/experiments/results/research_contribution/contribution_synthesis.json")
    output_md = Path("/tmp/LEO-DTF/experiments/results/research_contribution/contribution_synthesis.md")
    assert output_json.exists(), f"JSON output not found at {output_json}"
    assert output_md.exists(), f"MD output not found at {output_md}"
    # Check JSON is valid and has required keys
    with open(output_json, 'r') as f:
        data = json.load(f)
    required_keys = [
        "recommended_core_contribution",
        "supported_claims",
        "unsupported_claims",
        "forbidden_claims",
        "nuisance_model_findings",
        "geometry_diversity_findings",
        "packet_budget_findings",
        "observability_threshold_findings",
        "next_experiments",
        "missing_inputs"
    ]
    for key in required_keys:
        assert key in data, f"Missing key '{key}' in synthesis JSON"
    # Check that the core contribution is as expected
    assert data["recommended_core_contribution"] == "Nuisance-aware Doppler-Time Observability Characterization for LEO IoT."
    # Check that each list is non-empty (optional)
    for key in required_keys[1:]:  # skip the core contribution string
        assert isinstance(data[key], list), f"Key '{key}' should be a list"
        assert len(data[key]) > 0, f"Key '{key}' should not be empty"
    print("All tests passed!")

if __name__ == "__main__":
    test_script_runs()