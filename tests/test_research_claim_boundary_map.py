#!/usr/bin/env python3
"""
Test for LEO-DTF Claim Boundary Map Generator (C17)
"""

import json
import os
import subprocess
import sys
from pathlib import Path

def test_claim_boundary_map_script():
    """Run the claim boundary map script and verify outputs."""
    # Change to the LEO-DTF directory
    base_dir = Path(__file__).parent.parent
    script_path = base_dir / "scripts" / "research_claim_boundary_map.py"
    
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
    output_dir = results_dir / "research_claim_boundary_map"
    json_path = output_dir / "claim_boundary_map.json"
    md_path = output_dir / "claim_boundary_map.md"
    csv_path = output_dir / "claim_boundary_map.csv"
    
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
        "evidence_sources",
        "safe_to_claim",
        "conditional_to_claim",
        "not_claimable",
        "forbidden_claims",
        "needs_next_experiment",
        "recommended_paper_framing",
        "red_team_warnings",
        "missing_inputs"
    ]
    
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"
    
    # Assert lengths as per requirements
    assert len(data["safe_to_claim"]) >= 5, f"Expected at least 5 safe_to_claim items, got {len(data['safe_to_claim'])}"
    assert len(data["conditional_to_claim"]) >= 3, f"Expected at least 3 conditional_to_claim items, got {len(data['conditional_to_claim'])}"
    assert len(data["not_claimable"]) >= 5, f"Expected at least 5 not_claimable items, got {len(data['not_claimable'])}"
    assert len(data["forbidden_claims"]) >= 6, f"Expected at least 6 forbidden_claims items, got {len(data['forbidden_claims'])}"
    assert len(data["needs_next_experiment"]) >= 5, f"Expected at least 5 needs_next_experiment items, got {len(data['needs_next_experiment'])}"
    
    # Assert forbidden_claims includes the required items (by checking the claim strings)
    forbidden_claims_text = " ".join([claim["claim"] for claim in data["forbidden_claims"]]).lower()
    required_forbidden_substrings = [
        "real ota validation",
        "real satellite capture",
        "gnss replacement",
        "meter-level localization",
        "hil validation"
    ]
    for req in required_forbidden_substrings:
        assert req in forbidden_claims_text, f"Forbidden claim missing: {req}"
    
    # Assert red_team_warnings includes not reuse old DTOI=507 or equivalent
    red_team_text = " ".join(data["red_team_warnings"]).lower()
    assert ("old dtoi=507" in red_team_text) or ("reuse old dtoi" in red_team_text) or ("dtoi=507" in red_team_text), \
        "Red team warnings must mention not reusing old DTOI=507"
    
    # Assert recommended_paper_framing includes observability characterization and not localization system
    framing_text = " ".join(data["recommended_paper_framing"]).lower()
    assert ("observability characterization" in framing_text) and ("not localization system" in framing_text), \
        "Recommended paper framing must include observability characterization and not localization system"
    
    # Additionally, we can check that the script produced the expected output files in the steps
    # But the above should be sufficient.

if __name__ == "__main__":
    test_claim_boundary_map_script()
    print("All tests passed!")