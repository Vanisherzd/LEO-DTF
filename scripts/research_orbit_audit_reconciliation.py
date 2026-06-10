#!/usr/bin/env python3
"""
Orbit audit reconciliation script for LEO-DTF.

This script reads the results from C10, C10A, C11, and C12 and produces a
reconciliation report.
"""

import json
import os
from pathlib import Path
import sys

# Add the src directory to the path so we can import leodtf modules if needed
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def load_json(path):
    """Load a JSON file."""
    with open(path, 'r') as f:
        return json.load(f)

def main():
    # Define input paths
    base_dir = Path("experiments/results")
    c10_path = base_dir / "research_orbit_trace_bridge" / "orbit_trace_bridge_summary.json"
    c10a_path = base_dir / "research_orbit_trace_audit" / "orbit_trace_scale_audit.json"
    c11_path = base_dir / "research_orbit_unit_check" / "orbit_differential_unit_check.json"
    c12_path = base_dir / "research_orbit_offset_source_audit" / "orbit_offset_source_audit.json"

    # Check if files exist
    missing = []
    for p in [c10_path, c10a_path, c11_path, c12_path]:
        if not p.exists():
            missing.append(str(p))
    
    if missing:
        print(f"ERROR: Missing input files: {missing}", file=sys.stderr)
        print("Please run the respective scripts to generate these files.", file=sys.stderr)
        sys.exit(1)

    # Load the JSON files
    c10 = load_json(c10_path)
    c10a = load_json(c10a_path)
    c11 = load_json(c11_path)
    c12 = load_json(c12_path)

    # Build the reconciliation JSON
    reconciliation = {
        "input_availability": {
            "c10": c10_path.exists(),
            "c10a": c10a_path.exists(),
            "c11": c11_path.exists(),
            "c12": c12_path.exists()
        },
        "c10_summary": {
            "max_dtoi": c10.get("summary", {}).get("best_config", {}).get("dtoi"),
            "best_config": c10.get("summary", {}).get("best_config"),
            "synthetic_vs_orbit_gap": c10.get("summary", {}).get("synthetic_vs_orbit_gap")
        },
        "c10a_scale_flags": c10a.get("suspicious_scale_flags", []),
        "c11_unit_check_summary": {
            "offset_scaling_checks": c11.get("offset_scaling_checks", []),
            "carrier_scaling_checks": c11.get("carrier_scaling_checks", [])
        },
        "c12_source_audit_summary": {
            "unit_distance_checks": c12.get("unit_distance_checks", []),
            "rms_scaling_checks": c12.get("rms_scaling_checks", []),
            "bug_likelihood": c12.get("bug_likelihood"),
            "likely_failure_location": c12.get("likely_failure_location"),
            "conservative_interpretation": c12.get("conservative_interpretation"),
            "recommended_next_action": c12.get("recommended_next_action")
        },
        "contradiction_matrix": [],
        "likely_root_cause": "",
        "claim_status": {},
        "conservative_interpretation": "",
        "recommended_next_action": ""
    }

    # Build contradiction matrix
    # 1. If C10A has high DTOI flags and C11 has offset scaling failure, C10 DTOI=507 must be marked not_claimable.
    if c10a.get("suspicious_scale_flags") and any(not check.get("passed", True) for check in c11.get("offset_scaling_checks", [])):
        reconciliation["contradiction_matrix"].append(
            "C10A high DTOI flags and C11 offset scaling failure both indicate C10 DTOI=507 is not claimable."
        )

    # 2. If C12 bug_likelihood is LOW_FOR_DIRECT_DIFFERENTIAL_CALCULATION while C11 says offset scaling failed, add contradiction:
    #    "C11 artifact-based scaling conflicts with C12 source-level direct calculation."
    if c12.get("bug_likelihood") == "LOW_FOR_DIRECT_DIFFERENTIAL_CALCULATION":
        # Check if any offset scaling check in C11 failed
        offset_checks = c11.get("offset_scaling_checks", [])
        if any(not check.get("passed", True) for check in offset_checks):
            reconciliation["contradiction_matrix"].append(
                "C11 artifact-based scaling conflicts with C12 source-level direct calculation."
            )

    # 3. likely_root_cause
    if c12.get("bug_likelihood") == "HIGH":
        reconciliation["likely_root_cause"] = "C12 reports HIGH bug likelihood in direct differential calculation."
    else:
        reconciliation["likely_root_cause"] = (
            "C11 artifact grouping/reading mismatch or mismatch between C10 artifacts and C12 direct calculation"
        )

    # 4. claim_status
    reconciliation["claim_status"] = {
        "c10_orbit_dtoi_507": "not_claimable_pending_reconciliation",
        "c10a_scale_audit": "valid_as_risk_flag",
        "c11_unit_check": "useful_but_conflicts_with_c12",
        "c12_source_audit": "useful_direct_check"
    }

    # 5. conservative_interpretation
    reconciliation["conservative_interpretation"] = (
        "This is not OTA validation. "
        "Does not prove localization accuracy. "
        "DTOI=507 must not be used in paper claims until C10/C11/C12 are reconciled. "
        "Current safe contribution remains nuisance-aware DTOI observability, mainly supported by C2–C9."
    )

    # 6. recommended_next_action
    reconciliation["recommended_next_action"] = (
        "Investigate the discrepancy between C11 artifact-based offset scaling failure and "
        "C12 source-level direct calculation passing. Focus on C11 artifact selection and grouping logic."
    )

    # Create output directory
    output_dir = base_dir / "research_orbit_audit_reconciliation"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write JSON
    json_path = output_dir / "orbit_audit_reconciliation.json"
    with open(json_path, 'w') as f:
        json.dump(reconciliation, f, indent=2)

    # Write Markdown
    md_path = output_dir / "orbit_audit_reconciliation.md"
    with open(md_path, 'w') as f:
        f.write("# Orbit Audit Reconciliation Report\n\n")
        f.write("## Input Availability\n")
        for key, val in reconciliation["input_availability"].items():
            f.write(f"- {key}: {'Available' if val else 'Missing'}\n")
        f.write("\n## C10 Summary\n")
        f.write(f"- Max DTOI: {reconciliation['c10_summary']['max_dtoi']}\n")
        f.write(f"- Best Config: {reconciliation['c10_summary']['best_config']}\n")
        f.write(f"- Synthetic vs Orbit Gap: {reconciliation['c10_summary']['synthetic_vs_orbit_gap']}\n")
        f.write("\n## C10A Scale Flags\n")
        for flag in reconciliation["c10a_scale_flags"]:
            f.write(f"- {flag}\n")
        f.write("\n## C11 Unit Check Summary\n")
        f.write(f"- Offset Scaling Checks: {len(reconciliation['c11_unit_check_summary']['offset_scaling_checks'])} checks\n")
        f.write(f"- Carrier Scaling Checks: {len(reconciliation['c11_unit_check_summary']['carrier_scaling_checks'])} checks\n")
        f.write("\n## C12 Source Audit Summary\n")
        f.write(f"- Unit Distance Checks: {len(reconciliation['c12_source_audit_summary']['unit_distance_checks'])} checks\n")
        f.write(f"- RMS Scaling Checks: {len(reconciliation['c12_source_audit_summary']['rms_scaling_checks'])} checks\n")
        f.write(f"- Bug Likelihood: {reconciliation['c12_source_audit_summary']['bug_likelihood']}\n")
        f.write(f"- Likely Failure Location: {reconciliation['c12_source_audit_summary']['likely_failure_location']}\n")
        f.write("\n## Contradiction Matrix\n")
        for contradiction in reconciliation["contradiction_matrix"]:
            f.write(f"- {contradiction}\n")
        f.write("\n## Likely Root Cause\n")
        f.write(f"{reconciliation['likely_root_cause']}\n")
        f.write("\n## Claim Status\n")
        for key, val in reconciliation["claim_status"].items():
            f.write(f"- {key}: {val}\n")
        f.write("\n## Conservative Interpretation\n")
        f.write(f"{reconciliation['conservative_interpretation']}\n")
        f.write("\n## Recommended Next Action\n")
        f.write(f"{reconciliation['recommended_next_action']}\n")

    print(f"Reconciliation report written to {json_path} and {md_path}")

if __name__ == "__main__":
    main()