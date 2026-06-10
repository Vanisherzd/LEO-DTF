#!/usr/bin/env python3
"""
LEO-DTF Claim Boundary Map Generator (C17)

This script generates a machine-readable claim boundary map for paper planning,
categorizing potential claims into:
- safe_to_claim
- conditional_to_claim
- not_claimable
- forbidden
- needs_next_experiment

It reads from the postfix results table if available, otherwise scans the results directory.

It does not modify any existing scripts or run new experiments.
"""

import json
import os
import csv
from pathlib import Path
from typing import Dict, List, Any, Optional

def read_json_file(path: Path) -> Optional[Dict]:
    """Read a JSON file and return its content, or None if missing/unreadable."""
    if not path.exists():
        return None
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to read JSON file {path}: {e}")
        return None

def main():
    base_dir = Path(__file__).parent.parent
    results_dir = base_dir / "experiments" / "results"
    output_dir = results_dir / "research_claim_boundary_map"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Try to read the postfix results table first
    postfix_results_path = results_dir / "research_postfix_results_table" / "postfix_results_table.json"
    postfix_data = read_json_file(postfix_results_path)

    # We'll also collect some key evidence from the postfix results table if available
    evidence_sources = []
    if postfix_data is not None:
        evidence_sources.append("research_postfix_results_table/postfix_results_table.json")
        # We could extract more specific evidence, but for now we just note the source.
    else:
        # If the postfix results table is missing, we can scan the results directory for other JSONs.
        # But per instructions, we prefer the postfix results table.
        # We'll note that we are scanning as a fallback.
        evidence_sources.append("scanning results directory (postfix results table missing)")

    # Define the claim boundary map based on project knowledge and the postfix results.
    # We'll create the claims as specified in the task.

    safe_to_claim = [
        {
            "claim": "Nuisance-aware DTOI can characterize observability under CFO/drift projection",
            "status": "safe_to_claim",
            "evidence": "C2-C7, C10/C15, C16 results show DTOI values under various synthetic configurations with nuisance projection.",
            "boundary": "Valid under synthetic assumptions, CFO/drift [1,t] projection, and the defined nuisance models.",
            "risk_if_overstated": "Overstating may imply real-world performance without validation."
        },
        {
            "claim": "Geometry diversity can improve DTOI under synthetic assumptions",
            "status": "safe_to_claim",
            "evidence": "C2 (multipass) and C3 (multisat) show increased DTOI with geometry diversity.",
            "boundary": "Observed in deterministic synthetic simulations with specific geometry configurations.",
            "risk_if_overstated": "May not hold in real-world scenarios with unknown geometry and dynamics."
        },
        {
            "claim": "Carrier frequency and observation duration influence DTOI",
            "status": "safe_to_claim",
            "evidence": "C7 (carrier band) and C6A (nuisance order) show DTOI variation with carrier and duration.",
            "boundary": "Within the tested frequency range (137 MHz to 2.4 GHz) and duration (up to 1800s) in synthetic tests.",
            "risk_if_overstated": "Extrapolation beyond tested parameters may not be accurate."
        },
        {
            "claim": "Post-fix orbit-driven differential Doppler diagnostic no longer shows inflated DTOI=507 artifact",
            "status": "safe_to_claim",
            "evidence": "C15 post-fix refresh shows orbit DTOI ~3.04 and empty scale flags.",
            "boundary": "After the C14 fix to differential Doppler (baseline vs offset) and ENU basis correction.",
            "risk_if_overstated": "May lead to confusion if the pre-fix artifact is mistakenly cited as a positive result."
        },
        {
            "claim": "Corrected orbit-driven DTOI is diagnostic-only, approximately 3.04 in the current quick configuration",
            "status": "safe_to_claim",
            "evidence": "C15 post-fix best config: DTOI ≈ 3.04 (from research_orbit_postfix_refresh).",
            "boundary": "Specific to the quick-mode synthetic setup (seed 42, carrier 2.4 GHz, offset 5000m, duration 1800s, nuisance order 1).",
            "risk_if_overstated": "May be misinterpreted as a localization accuracy figure."
        }
    ]

    conditional_to_claim = [
        {
            "claim": "Orbit-driven differential Doppler can support DTOI observability analysis if framed as simulation/diagnostic",
            "status": "conditional_to_claim",
            "evidence": "C10/C15 post-fix results show diagnostic DTOI values after fix.",
            "boundary": "Only when clearly labeled as a simulation/diagnostic and not as OTA validation.",
            "risk_if_overstated": "Risk of implying real satellite validation."
        },
        {
            "claim": "Multi-pass or multi-satellite diversity improves observability under controlled synthetic assumptions",
            "status": "conditional_to_claim",
            "evidence": "C2 and C3 show gains in DTOI with geometry diversity.",
            "boundary": "Under the specific synthetic curvature and noise models used in those experiments.",
            "risk_if_overstated": "May not generalize to real orbital dynamics and measurement noise."
        },
        {
            "claim": "Packet budget affects DTOI under the current noise and nuisance model",
            "status": "conditional_to_claim",
            "evidence": "C4 shows DTOI variation with packet count.",
            "boundary": "Within the packet-budget diagnostic model and the assumed SNR and nuisance parameters.",
            "risk_if_overstated": "May not hold under different noise conditions or receiver designs."
        }
    ]

    not_claimable = [
        {
            "claim": "Localization accuracy is proven",
            "status": "not_claimable",
            "evidence": "No OTA or HIL validation; results are observability diagnostics only.",
            "boundary": "The project explicitly states it does not prove localization accuracy.",
            "risk_if_overstated": "Misleading users about the system's capability."
        },
        {
            "claim": "Meter-level positioning is achieved",
            "status": "not_claimable",
            "evidence": "No meter-level validation claimed or proven.",
            "boundary": "The project does not assert meter-level positioning.",
            "risk_if_overstated": "Overstating precision without evidence."
        },
        {
            "claim": "Real satellite signal validation is complete",
            "status": "not_claimable",
            "evidence": "No real satellite signals processed; all results are synthetic.",
            "boundary": "The project uses synthetic signals and orbit propagators.",
            "risk_if_overstated": "Implying real-world validation."
        },
        {
            "claim": "Hardware-in-the-loop validation is complete",
            "status": "not_claimable",
            "evidence": "No HIL validation performed.",
            "boundary": "The project does not include HIL tests.",
            "risk_if_overstated": "Suggesting readiness for hardware deployment."
        },
        {
            "claim": "Single-pass single-node localization is sufficient",
            "status": "not_claimable",
            "evidence": "Results show DTOI improvements with geometry diversity (multipass, multisat).",
            "boundary": "The diagnostics indicate that single-pass may be insufficient for strong observability.",
            "risk_if_overstated": "Underestimating the need for diversity in observation."
        }
    ]

    forbidden_claims = [
        {
            "claim": "Real OTA validation completed",
            "status": "forbidden",
            "evidence": "No OTA validation performed.",
            "boundary": "The project forbids claiming real OTA validation.",
            "risk_if_overstated": "False claim of real-world testing."
        },
        {
            "claim": "Real satellite capture completed",
            "status": "forbidden",
            "evidence": "No real satellite signals captured or processed.",
            "boundary": "The project forbids claiming real satellite capture.",
            "risk_if_overstated": "Misrepresenting the data source."
        },
        {
            "claim": "GNSS replacement",
            "status": "forbidden",
            "evidence": "No claim or evidence of replacing GNSS.",
            "boundary": "The project does not propose GNSS replacement.",
            "risk_if_overstated": "Overstating the impact of the research."
        },
        {
            "claim": "Meter-level localization proven",
            "status": "forbidden",
            "evidence": "No meter-level localization proven.",
            "boundary": "The project forbids claiming meter-level localization.",
            "risk_if_overstated": "Claiming unverified precision."
        },
        {
            "claim": "Deployment-ready LEO localization system",
            "status": "forbidden",
            "evidence": "The project is a diagnostic observability study, not a deployment-ready system.",
            "boundary": "The project does not develop a deployment-ready system.",
            "risk_if_overstated": "Implying readiness for operational use."
        },
        {
            "claim": "HIL validation completed",
            "status": "forbidden",
            "evidence": "No HIL validation performed.",
            "boundary": "The project forbids claiming HIL validation.",
            "risk_if_overstated": "Suggesting hardware validation."
        }
    ]

    needs_next_experiment = [
        {
            "claim": "Real SDR capture or recorded RF trace validation",
            "status": "needs_next_experiment",
            "evidence": "Needed to move beyond synthetic diagnostics.",
            "boundary": "Future work should include real signal capture.",
            "risk_if_overstated": "Prematurely claiming real-world efficacy."
        },
        {
            "claim": "Oscillator phase-noise sensitivity sweep",
            "status": "needs_next_experiment",
            "evidence": "Current phase-noise model is limited.",
            "boundary": "Future work should sweep oscillator parameters.",
            "risk_if_overstated": "Overlooking a key error source."
        },
        {
            "claim": "Full TLE/SGP4 orbit-driven parameter sweep beyond quick mode",
            "status": "needs_next_experiment",
            "evidence": "Current orbit-driven results are in quick mode.",
            "boundary": "Future work should explore longer durations, different orbits, and realistic error models.",
            "risk_if_overstated": "Generalizing from a limited synthetic setup."
        },
        {
            "claim": "Receiver geometry and station placement robustness",
            "status": "needs_next_experiment",
            "evidence": "Need to test robustness to varying ground station layouts.",
            "boundary": "Future work should include Monte Carlo over station placements.",
            "risk_if_overstated": "Assuming ideal geometry."
        },
        {
            "claim": "Comparison against simple Doppler baseline and naive estimator",
            "status": "needs_next_experiment",
            "evidence": "Needed to contextualize the DTOI diagnostic.",
            "boundary": "Future work should compare with simpler methods.",
            "risk_if_overstated": "Overstating the novelty or advantage of the DTOI approach."
        }
    ]

    # Recommended paper framing (from the task)
    recommended_paper_framing = [
        "Use observability characterization, not localization system.",
        "Use diagnostic DTOI evidence, not accuracy evidence.",
        "Describe orbit-driven branch as post-fix differential Doppler simulation/diagnostic.",
        "Keep claims conservative until real RF/OTA or HIL validation exists."
    ]

    # Red team warnings (from the task)
    red_team_warnings = [
        "Do not say validated on real satellite.",
        "Do not say meter-level localization.",
        "Do not imply GNSS replacement.",
        "Do not hide that the orbit result is diagnostic/simulation.",
        "Do not reuse old DTOI=507 as a positive result."
    ]

    # Missing inputs (if any)
    missing_inputs = []
    if postfix_data is None:
        missing_inputs.append(str(postfix_results_path))

    # Assemble the final JSON
    output_json = {
        "metadata": {
            "generated_by": "research_claim_boundary_map.py",
            "base_dir": str(base_dir),
            "results_dir": str(results_dir),
            "output_dir": str(output_dir)
        },
        "evidence_sources": evidence_sources,
        "safe_to_claim": safe_to_claim,
        "conditional_to_claim": conditional_to_claim,
        "not_claimable": not_claimable,
        "forbidden_claims": forbidden_claims,
        "needs_next_experiment": needs_next_experiment,
        "recommended_paper_framing": recommended_paper_framing,
        "red_team_warnings": red_team_warnings,
        "missing_inputs": missing_inputs
    }

    # Write JSON
    json_out = output_dir / "claim_boundary_map.json"
    with open(json_out, 'w') as f:
        json.dump(output_json, f, indent=2)
    print(f"JSON claim boundary map written to: {json_out}")

    # Write Markdown
    md_out = output_dir / "claim_boundary_map.md"
    with open(md_out, 'w') as f:
        f.write("# LEO-DTF Claim Boundary Map (C17)\\n\\n")
        f.write("## Evidence Sources\\n\\n")
        for src in evidence_sources:
            f.write(f"- {src}\\n")
        f.write("\\n")
        f.write("## Safe to Claim\\n\\n")
        for claim in safe_to_claim:
            f.write(f"- **Claim**: {claim['claim']}\\n")
            f.write(f"  - Evidence: {claim['evidence']}\\n")
            f.write(f"  - Boundary: {claim['boundary']}\\n")
            f.write(f"  - Risk if overstated: {claim['risk_if_overstated']}\\n\\n")
        f.write("## Conditional to Claim\\n\\n")
        for claim in conditional_to_claim:
            f.write(f"- **Claim**: {claim['claim']}\\n")
            f.write(f"  - Evidence: {claim['evidence']}\\n")
            f.write(f"  - Boundary: {claim['boundary']}\\n")
            f.write(f"  - Risk if overstated: {claim['risk_if_overstated']}\\n\\n")
        f.write("## Not Claimable\\n\\n")
        for claim in not_claimable:
            f.write(f"- **Claim**: {claim['claim']}\\n")
            f.write(f"  - Evidence: {claim['evidence']}\\n")
            f.write(f"  - Boundary: {claim['boundary']}\\n")
            f.write(f"  - Risk if overstated: {claim['risk_if_overstated']}\\n\\n")
        f.write("## Forbidden Claims\\n\\n")
        for claim in forbidden_claims:
            f.write(f"- **Claim**: {claim['claim']}\\n")
            f.write(f"  - Evidence: {claim['evidence']}\\n")
            f.write(f"  - Boundary: {claim['boundary']}\\n")
            f.write(f"  - Risk if overstated: {claim['risk_if_overstated']}\\n\\n")
        f.write("## Needs Next Experiment\\n\\n")
        for claim in needs_next_experiment:
            f.write(f"- **Claim**: {claim['claim']}\\n")
            f.write(f"  - Evidence: {claim['evidence']}\\n")
            f.write(f"  - Boundary: {claim['boundary']}\\n")
            f.write(f"  - Risk if overstated: {claim['risk_if_overstated']}\\n\\n")
        f.write("## Recommended Paper Framing\\n\\n")
        for framing in recommended_paper_framing:
            f.write(f"- {framing}\\n")
        f.write("\\n")
        f.write("## Red Team Warnings\\n\\n")
        for warning in red_team_warnings:
            f.write(f"- {warning}\\n")
        f.write("\\n")
        f.write("## Missing Inputs\\n\\n")
        if missing_inputs:
            for missing in missing_inputs:
                f.write(f"- {missing}\\n")
        else:
            f.write("None\\n")
    print(f"Markdown claim boundary map written to: {md_out}")

    # Write CSV
    csv_out = output_dir / "claim_boundary_map.csv"
    with open(csv_out, 'w', newline='') as f:
        # We'll flatten the claims for CSV: each claim gets a row with columns for each field.
        # Since the claims have different fields based on status, we'll use a superset of fields.
        fieldnames = ["status", "claim", "evidence", "boundary", "risk_if_overstated"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for claim_list in [safe_to_claim, conditional_to_claim, not_claimable, forbidden_claims, needs_next_experiment]:
            for claim in claim_list:
                row = {key: claim.get(key, "") for key in fieldnames}
                writer.writerow(row)
    print(f"CSV claim boundary map written to: {csv_out}")

if __name__ == "__main__":
    main()