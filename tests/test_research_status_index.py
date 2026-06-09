#!/usr/bin/env python3
"""
Test for research_status_index.py
"""
import subprocess
import sys
import os
from pathlib import Path
import json

def run_script(args=[]):
    """Run the script with given args and return (exit_code, stdout, stderr)."""
    cmd = [sys.executable, "scripts/research_status_index.py"] + args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd="/tmp/LEO-DTF"
    )
    return result.returncode, result.stdout, result.stderr

def test_index_generation():
    """Test that the script runs and generates the expected files."""
    exit_code, stdout, stderr = run_script([])
    assert exit_code == 0, f"Script failed with exit code {exit_code}. STDOUT: {stdout}, STDERR: {stderr}"
    # Check output files exist
    json_path = Path("/tmp/LEO-DTF/experiments/results/research_index/research_status_index.json")
    md_path = Path("/tmp/LEO-DTF/experiments/results/research_index/research_status_index.md")
    assert json_path.exists(), f"JSON file not found at {json_path}"
    assert md_path.exists(), f"MD file not found at {md_path}"
    # Check JSON is valid and has required keys
    with open(json_path, 'r') as f:
        data = json.load(f)
    required_keys = [
        "completed_phases",
        "available_scripts",
        "available_tests",
        "available_result_dirs",
        "missing_result_dirs",
        "key_quantitative_findings",
        "supported_core_contribution",
        "forbidden_claims",
        "next_recommended_phases"
    ]
    for key in required_keys:
        assert key in data, f"Missing key '{key}' in index JSON"
    # Check that the core contribution is as expected
    assert data["supported_core_contribution"] == "Nuisance-aware Doppler-Time Observability Characterization for LEO IoT."
    # Check that forbidden claims include the required ones
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
    # Check that available_scripts includes at least the two specified
    scripts_set = set(data["available_scripts"])
    assert "research_packet_budget_threshold.py" in scripts_set, "Missing research_packet_budget_threshold.py in available_scripts"
    assert "research_carrier_band_threshold.py" in scripts_set, "Missing research_carrier_band_threshold.py in available_scripts"
    # Check that available_tests includes at least the two specified
    tests_set = set(data["available_tests"])
    assert "test_research_packet_budget_threshold.py" in tests_set, "Missing test_research_packet_budget_threshold.py in available_tests"
    assert "test_research_carrier_band_threshold.py" in tests_set, "Missing test_research_carrier_band_threshold.py in available_tests"
    print("All tests passed!")

if __name__ == "__main__":
    test_index_generation()