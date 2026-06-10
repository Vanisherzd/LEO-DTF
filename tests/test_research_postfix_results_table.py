#!/usr/bin/env python3
"""
Test for LEO-DTF Post-Fix Research Results Table Generator (C16)
"""

import json
import os
import subprocess
import sys
from pathlib import Path

def test_results_table_script():
    """Run the results table script and verify outputs."""
    # Change to the LEO-DTF directory
    base_dir = Path(__file__).parent.parent
    script_path = base_dir / "scripts" / "research_postfix_results_table.py"
    
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
    results_dir = base_dir / "experiments" / "results"
    output_dir = results_dir / "research_postfix_results_table"
    json_path = output_dir / "postfix_results_table.json"
    md_path = output_dir / "postfix_results_table.md"
    csv_path = output_dir / "postfix_results_table.csv"
    
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
        "table_rows",
        "headline_findings",
        "resolved_issues",
        "remaining_risks",
        "safe_claims",
        "forbidden_claims",
        "missing_inputs",
        "recommended_next_experiments"
    ]
    
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"
    
    # Assert table_rows exists and is a list
    assert isinstance(data["table_rows"], list), "table_rows must be a list"
    # Assert at least 5 table rows exist
    assert len(data["table_rows"]) >= 5, f"Expected at least 5 table rows, got {len(data['table_rows'])}"
    
    # Assert safe_claims and forbidden_claims are lists
    assert isinstance(data["safe_claims"], list), "safe_claims must be a list"
    assert isinstance(data["forbidden_claims"], list), "forbidden_claims must be a list"
    
    # Assert forbidden_claims include the required items
    forbidden_set = set(data["forbidden_claims"])
    required_forbidden = {
        "Real OTA validation",
        "Real satellite capture completed",
        "Localization accuracy proven",
        "Meter-level localization",
        "GNSS replacement",
        "HIL validation completed"
    }
    for req in required_forbidden:
        assert req in forbidden_set, f"Forbidden claim missing: {req}"
    
    # Assert resolved_issues mentions DTOI=507 or inflated DTOI
    resolved_issues_str = " ".join(data["resolved_issues"]).lower()
    assert ("dtoi=507" in resolved_issues_str) or ("inflated" in resolved_issues_str), \
        "Resolved issues must mention DTOI=507 or inflated DTOI"
    
    # Assert conservative language exists in MD (we can check for phrases like "not OTA validation" or "diagnostic only")
    with open(md_path, 'r') as f:
        md_content = f.read()
    assert "Not OTA validation" in md_content or "diagnostic only" in md_content or "not OTA" in md_content, \
        "Markdown must contain conservative language (e.g., 'Not OTA validation' or 'diagnostic only')"
    
    # Additionally, we can check that the script produced the expected output files in the steps
    # But the above should be sufficient.

if __name__ == "__main__":
    test_results_table_script()
    print("All tests passed!")