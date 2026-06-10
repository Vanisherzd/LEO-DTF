#!/usr/bin/env python3
"""
Test for LEO-DTF Next Experiment Roadmap Generator (C18)
"""

import json
import os
import subprocess
import sys
from pathlib import Path

def test_roadmap_script():
    """Run the roadmap script and verify outputs."""
    # Change to the LEO-DTF directory
    base_dir = Path(__file__).parent.parent
    script_path = base_dir / "scripts" / "research_next_experiment_roadmap.py"
    
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
    output_dir = results_dir / "research_next_experiment_roadmap"
    json_path = output_dir / "next_experiment_roadmap.json"
    md_path = output_dir / "next_experiment_roadmap.md"
    csv_path = output_dir / "next_experiment_roadmap.csv"
    
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
        "candidate_experiments",
        "priority_ranking",
        "recommended_sequence",
        "immediate_next_phase",
        "deferred_experiments",
        "blocked_experiments",
        "claim_de_risking_map",
        "ci_safety_notes",
        "missing_inputs"
    ]
    
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"
    
    # Assert candidate_experiments length >= 8
    assert len(data["candidate_experiments"]) >= 8, f"Expected at least 8 candidate experiments, got {len(data['candidate_experiments'])}"
    
    # Assert priority_ranking length >= 8
    assert len(data["priority_ranking"]) >= 8, f"Expected at least 8 priority ranked experiments, got {len(data['priority_ranking'])}"
    
    # Assert recommended_sequence length >= 5
    assert len(data["recommended_sequence"]) >= 5, f"Expected at least 5 recommended sequence items, got {len(data['recommended_sequence'])}"
    
    # Assert immediate_next_phase is non-empty
    assert data["immediate_next_phase"].strip() != "", "Immediate next phase must be non-empty"
    
    # Assert deferred_experiments includes SDR/OTA or real RF (we expect E6)
    deferred_ids = set(data["deferred_experiments"])
    assert "E6" in deferred_ids, f"Deferred experiments must include E6 (SDR capture), got {deferred_ids}"
    
    # Assert blocked_experiments includes HIL (we expect E7)
    blocked_ids = set(data["blocked_experiments"])
    assert "E7" in blocked_ids, f"Blocked experiments must include E7 (HIL validation), got {blocked_ids}"
    
    # Assert ci_safety_notes mention quick smoke tests or long experiments
    ci_notes_text = " ".join(data["ci_safety_notes"]).lower()
    assert ("quick smoke" in ci_notes_text) or ("long experiment" in ci_notes_text) or ("ci timeout" in ci_notes_text), \
        "CI safety notes must mention quick smoke tests or long experiments"
    
    # Assert MD contains "does not create OTA" or equivalent
    with open(md_path, 'r') as f:
        md_content = f.read()
    assert "does not create OTA" in md_content or "not create OTA" in md_content or "does not create OTA, HIL, or localization evidence" in md_content, \
        "Markdown must contain conservative warning about not creating OTA/HIL/localization evidence"
    
    # Assert every candidate has overall_priority_score
    for exp in data["candidate_experiments"]:
        assert "overall_priority_score" in exp, f"Candidate experiment {exp.get('id', 'unknown')} missing overall_priority_score"
        assert isinstance(exp["overall_priority_score"], (int, float)), f"Overall priority score must be numeric"
    
    # Additionally, we can check that the immediate_next_phase is either C19, C20, or C21 (as per our logic)
    assert data["immediate_next_phase"] in ["C19", "C20", "C21"], f"Immediate next phase must be C19, C20, or C21, got {data['immediate_next_phase']}"
    
    # And that the top experiment in priority_ranking is either E1 or E2 (as per the task's expectation for immediate next phase)
    top_exp_id = data["priority_ranking"][0]["id"]
    assert top_exp_id in ["E1", "E2"], f"Top priority experiment should be E1 or E2 for immediate next phase, got {top_exp_id}"
    
    # Additionally, we can check that the claim_de_risking_map has entries for each experiment
    for exp in data["candidate_experiments"]:
        assert exp["id"] in data["claim_de_risking_map"], f"Claim de-risking map missing entry for {exp['id']}"
    
    # If we got here, all tests passed.

if __name__ == "__main__":
    test_roadmap_script()
    print("All tests passed!")