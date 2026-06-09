#!/usr/bin/env python3
"""
Test for the orbit trace scale audit script.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

def test_audit_script_runs_and_produces_output():
    # Run the audit script
    result = subprocess.run([
        "uv", "run", "python",
        "scripts/research_orbit_trace_scale_audit.py"
    ], capture_output=True, text=True)
    # The script should run successfully
    assert result.returncode == 0, f"Audit script failed: {result.stderr}"

    # Define output paths
    out_dir = Path("experiments/results/research_orbit_trace_audit")
    json_path = out_dir / "orbit_trace_scale_audit.json"
    md_path = out_dir / "orbit_trace_scale_audit.md"

    # Assert JSON and MD exist
    assert json_path.exists(), f"JSON output not found at {json_path}"
    assert md_path.exists(), f"MD output not found at {md_path}"

    # Load JSON
    with open(json_path, 'r') as f:
        audit = json.load(f)

    # Assert JSON has suspicious_scale_flags (list)
    assert "suspicious_scale_flags" in audit
    assert isinstance(audit["suspicious_scale_flags"], list)

    # Assert JSON has conservative_interpretation (string)
    assert "conservative_interpretation" in audit
    assert isinstance(audit["conservative_interpretation"], str)
    conservative = audit["conservative_interpretation"]
    # Assert it mentions not OTA and not localization accuracy
    assert "not OTA" in conservative or "not OTA validation" in conservative
    assert "not a localization accuracy" in conservative or "must not be used as a localization accuracy claim" in conservative

    # Assert if max_dtoi > 100 then suspicious_scale_flags is non-empty
    max_dtoi = audit["max_dtoi"]
    flags = audit["suspicious_scale_flags"]
    if max_dtoi > 100:
        assert len(flags) > 0, f"Expected suspicious flags when max_dtoi > 100, but got none. max_dtoi={max_dtoi}"

    # Additionally, we can check that the audit script printed the output paths
    assert "Audit JSON written to" in result.stdout
    assert "Audit Markdown written to" in result.stdout

if __name__ == "__main__":
    test_audit_script_runs_and_produces_output()
    print("All tests passed.")
