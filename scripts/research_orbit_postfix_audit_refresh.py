#!/usr/bin/env python3
"""
LEO-DTF Post-Fix Orbit Audit Refresh Script (C15)

This script runs the existing orbit audit scripts in sequence and aggregates
their results into a summary JSON and Markdown file.

It does not modify any existing scripts, only reads their outputs.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

def run_command(cmd):
    """Run a command and check its exit code."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        sys.exit(1)
    return result

def main():
    # Define the base directory
    base_dir = Path(__file__).parent.parent
    results_dir = base_dir / "experiments" / "results" / "research_orbit_postfix_refresh"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Define the steps to run
    steps = [
        {
            "name": "research_orbit_trace_dtoi_bridge",
            "cmd": [
                "uv", "run", "python",
                "scripts/research_orbit_trace_dtoi_bridge.py",
                "--quick", "--seed", "42"
            ],
            "output_json": base_dir / "experiments" / "results" / "research_orbit_trace_bridge" / "orbit_trace_bridge_summary.json"
        },
        {
            "name": "research_orbit_trace_scale_audit",
            "cmd": [
                "uv", "run", "python",
                "scripts/research_orbit_trace_scale_audit.py"
            ],
            "output_json": base_dir / "experiments" / "results" / "research_orbit_trace_audit" / "orbit_trace_scale_audit.json"
        },
        {
            "name": "research_orbit_differential_unit_check",
            "cmd": [
                "uv", "run", "python",
                "scripts/research_orbit_differential_unit_check.py"
            ],
            "output_json": base_dir / "experiments" / "results" / "research_orbit_unit_check" / "orbit_differential_unit_check.json"
        },
        {
            "name": "research_orbit_offset_source_audit",
            "cmd": [
                "uv", "run", "python",
                "scripts/research_orbit_offset_source_audit.py"
            ],
            "output_json": base_dir / "experiments" / "results" / "research_orbit_offset_source_audit" / "orbit_offset_source_audit.json"
        },
        {
            "name": "research_orbit_audit_reconciliation",
            "cmd": [
                "uv", "run", "python",
                "scripts/research_orbit_audit_reconciliation.py"
            ],
            "output_json": base_dir / "experiments" / "results" / "research_orbit_audit_reconciliation" / "orbit_audit_reconciliation.json"
        }
    ]

    executed_steps = []
    for step in steps:
        print(f"\n=== Running {step['name']} ===")
        run_command(step["cmd"])
        executed_steps.append(step["name"])
        # Verify the output JSON exists
        if not step["output_json"].exists():
            print(f"ERROR: Expected output JSON not found: {step['output_json']}")
            sys.exit(1)

    # Read the JSON files
    def read_json(path):
        with open(path, 'r') as f:
            return json.load(f)

    try:
        c10_data = read_json(steps[0]["output_json"])
        c10a_data = read_json(steps[1]["output_json"])
        c11_data = read_json(steps[2]["output_json"])
        c12_data = read_json(steps[3]["output_json"])
        c13_data = read_json(steps[4]["output_json"])
    except Exception as e:
        print(f"Error reading JSON files: {e}")
        sys.exit(1)

    # Extract required information
    # C10: best_config from the summary
    # In the bridge summary, the best_config is under summary.best_config
    c10_best_config = c10_data.get("summary", {}).get("best_config", {})

    # C10A: scale_flags from the suspicious_scale_flags
    c10a_scale_flags = c10a_data.get("suspicious_scale_flags", [])

    # C11: unit_summary - we'll take the offset_scaling_checks and carrier_scaling_checks
    c11_unit_summary = {
        "offset_scaling_checks": c11_data.get("offset_scaling_checks", []),
        "carrier_scaling_checks": c11_data.get("carrier_scaling_checks", [])
    }

    # C12: source_summary - we'll take the unit_distance_checks and maybe the metadata
    c12_source_summary = {
        "metadata": c12_data.get("metadata", {}),
        "unit_distance_checks": c12_data.get("unit_distance_checks", [])
    }

    # C13: reconciliation_summary - we'll take the entire c13_data or a summary
    c13_reconciliation_summary = {
        "input_availability": c13_data.get("input_availability", {}),
        "c10_summary": c13_data.get("c10_summary", {}),
        "c10a_scale_flags": c13_data.get("c10a_scale_flags", []),
        "c11_unit_summary": c13_data.get("c11_unit_summary", {}),
        "c12_source_summary": c13_data.get("c12_source_summary", {}),
        "reconciliation_notes": c13_data.get("reconciliation_notes", "")
    }

    # Previous issue status
    previous_issue_status = {
        "old_c10_dtoi_507_was_invalid_or_pre_fix": True,  # Based on background
        "c14_replaced_absolute_doppler_with_differential_doppler": True  # From background
    }

    # Postfix claim status
    postfix_claim_status = {
        "orbit_dtoi_after_c14": "diagnostic_only_not_OTA",
        "localization_accuracy": "not_claimed",
        "real_satellite_capture": "not_claimed"
    }

    # Conservative interpretation
    conservative_interpretation = [
        "Not OTA validation.",
        "Does not prove localization accuracy.",
        "C14 only fixes differential Doppler logic.",
        "Safe contribution remains nuisance-aware DTOI observability unless post-fix audits support more."
    ]

    # Determine postfix_claim_status details and recommended next action
    # Check if current best orbit DTOI is still >100
    orbit_best_dtoi = c10a_data.get("orbit_best_dtoi", 0)
    if orbit_best_dtoi > 100:
        postfix_scale_status = "still_suspicious"
    else:
        postfix_scale_status = "resolved"

    # Check C11 offset scaling: we need to see if all checks passed
    offset_checks = c11_data.get("offset_scaling_checks", [])
    all_offset_passed = all(check.get("passed", False) for check in offset_checks)
    # Also check if C10A high-scale flags disappear or reduce
    # We'll consider the flags as improved if the list is empty or doesn't contain the severe ones
    severe_flags = ["orbit_synthetic_gap_gt_100x", "dtoI_gt_100_requires_manual_unit_audit"]
    flags_improved = not any(flag in c10a_scale_flags for flag in severe_flags)

    if all_offset_passed and flags_improved:
        postfix_offset_scaling_status = "improved"
    elif not all_offset_passed:
        postfix_offset_scaling_status = "unresolved"
    else:
        postfix_offset_scaling_status = "unchanged"

    # Build the recommended next action based on the statuses
    recommended_actions = []
    if postfix_scale_status == "still_suspicious":
        recommended_actions.append("Perform manual unit audit of offset and carrier scaling in the orbit-driven signal generation.")
    if postfix_offset_scaling_status == "unresolved":
        recommended_actions.append("Investigate offset scaling failures in unit check.")
    if not recommended_actions:
        recommended_actions.append("Consider proceeding to next research phase with current diagnostic results.")

    recommended_next_action = " ".join(recommended_actions)

    # Assemble the final JSON
    output_json = {
        "executed_steps": executed_steps,
        "c10_postfix_best_config": c10_best_config,
        "c10a_postfix_scale_flags": c10a_scale_flags,
        "c11_postfix_unit_summary": c11_unit_summary,
        "c12_postfix_source_summary": c12_source_summary,
        "c13_postfix_reconciliation_summary": c13_reconciliation_summary,
        "previous_issue_status": previous_issue_status,
        "postfix_claim_status": postfix_claim_status,
        "conservative_interpretation": conservative_interpretation,
        "recommended_next_action": recommended_next_action
    }

    # Write the JSON file
    json_out = results_dir / "orbit_postfix_refresh_summary.json"
    with open(json_out, 'w') as f:
        json.dump(output_json, f, indent=2)
    print(f"JSON summary written to: {json_out}")

    # Write a simple Markdown file
    md_out = results_dir / "orbit_postfix_refresh_summary.md"
    with open(md_out, 'w') as f:
        f.write("# LEO-DTF Post-Fix Orbit Audit Refresh Summary (C15)\n\n")
        f.write(f"**Executed Steps:** {', '.join(executed_steps)}\n\n")
        f.write("## C10 Post-Fix Best Config\n")
        f.write(json.dumps(c10_best_config, indent=2) + "\n\n")
        f.write("## C10A Post-Fix Scale Flags\n")
        f.write(", ".join(c10a_scale_flags) + "\n\n")
        f.write("## C11 Post-Fix Unit Summary\n")
        f.write(json.dumps(c11_unit_summary, indent=2) + "\n\n")
        f.write("## C12 Post-Fix Source Summary\n")
        f.write(json.dumps(c12_source_summary, indent=2) + "\n\n")
        f.write("## C13 Post-Fix Reconciliation Summary\n")
        f.write(json.dumps(c13_reconciliation_summary, indent=2) + "\n\n")
        f.write("## Previous Issue Status\n")
        f.write(json.dumps(previous_issue_status, indent=2) + "\n\n")
        f.write("## Postfix Claim Status\n")
        f.write(json.dumps(postfix_claim_status, indent=2) + "\n\n")
        f.write("## Conservative Interpretation\n")
        for item in conservative_interpretation:
            f.write(f"- {item}\n")
        f.write("\n")
        f.write("## Recommended Next Action\n")
        f.write(f"{recommended_next_action}\n")
    print(f"Markdown summary written to: {md_out}")

if __name__ == "__main__":
    main()