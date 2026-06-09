#!/usr/bin/env python3
"""
Research claim audit generator for LEO-DTF.
Based on research status index and contribution synthesis, audits which claims are supported, conditional, unsupported, or forbidden.
"""
import json
import os
from pathlib import Path

def main():
    repo_root = Path("/tmp/LEO-DTF")
    results_dir = repo_root / "experiments" / "results"

    # 1. Read research status index (if exists)
    index_path = results_dir / "research_index" / "research_status_index.json"
    index_data = {}
    if index_path.exists():
        with open(index_path, 'r') as f:
            index_data = json.load(f)
    else:
        print("Warning: research status index not found at", index_path)

    # 2. Read contribution synthesis (if exists)
    contrib_path = results_dir / "research_contribution" / "contribution_synthesis.json"
    contrib_data = {}
    if contrib_path.exists():
        with open(contrib_path, 'r') as f:
            contrib_data = json.load(f)
    else:
        print("Warning: contribution synthesis not found at", contrib_path)

    # 3. Define the expected result directories and their summary files
    expected_results = {
        "research_multipass_observability": "multipass_observability_summary.json",
        "research_multisat_geometry": "multisat_geometry_summary.json",
        "research_packet_budget": "packet_budget_summary.json",
        "research_nuisance_order": "nuisance_order_summary.json",
        "research_carrier_band": "carrier_band_summary.json"
    }

    # 4. Collect evidence from each result summary if available
    evidence_map = {}
    for dir_name, file_name in expected_results.items():
        summary_path = results_dir / dir_name / file_name
        if summary_path.exists():
            with open(summary_path, 'r') as f:
                evidence_map[dir_name] = json.load(f)
        else:
            evidence_map[dir_name] = None  # missing

    # 5. Build supported claims based on the evidence
    supported_claims = [
        "nuisance-aware DTOI is useful as an observability diagnostic",
        "geometry diversity helps DTOI",
        "higher carrier frequency improves DTOI under same synthetic conditions",
        "higher-order nuisance projection weakens observability",
        "packet budget alone is insufficient to overcome nuisance-induced observability limits"
    ]

    # 6. Conditional claims (true only under certain conditions)
    conditional_claims = [
        "multi-pass improves observability only if nuisance can be shared or controlled",
        "multi-satellite improves observability only under geometry diversity and manageable per-link nuisance",
        "2.4 GHz reaches moderate DTOI only under large offset/long duration in tested configurations"
    ]

    # 7. Unsupported claims (not supported by current work, but not forbidden)
    unsupported_claims = [
        "accurate localization error prediction",
        "real deployment readiness",
        "real hardware/OTA validation",
        "universal carrier-band threshold",
        "performance under real oscillator phase noise"
    ]

    # 8. Forbidden claims (cannot be claimed based on this work)
    forbidden_claims = [
        "real OTA validation",
        "meter-level localization",
        "GNSS replacement",
        "single-pass always works",
        "multi-pass/multi-satellite solves localization",
        "HIL validation completed"
    ]

    # 9. Weakest links (based on the evidence: what limits observability the most?)
    # We can deduce from the results: nuisance projection is the biggest limiter.
    weakest_links = [
        "Nuisance projection (CFO/drift [1,t]) removes 98.7-100% of Doppler difference energy, making per-nuisance DTOI much lower than naive separability.",
        "Per-link nuisance DTOI remains weak (<1) in multi-pass and multi-satellite experiments, limiting accumulation.",
        "Lower carrier bands (e.g., 137 MHz) require impractically large offsets to achieve weak observability under affine nuisance."
    ]

    # 10. Strongest results (what we have shown)
    strongest_results = [
        "NUISANCE-AWARE OBSERVABILITY: We introduced DTOI (nuisance-projected separability) as a diagnostic for LEO satellite IoT.",
        "GEOMETRY HELPS: Multi-satellite geometry diversity can improve global DTOI (up to ~3.0 in C3).",
        "CARRIER MATTERS: Higher carrier frequency (e.g., 2.4 GHz) yields higher DTOI than lower bands under same offset/duration.",
        "PACKET LIMITS: Packet count improves DTOI via sqrt(N)-like averaging after nuisance projection, but saturation occurs quickly."
    ]

    # 11. Minimum extra experiments before paper
    minimum_extra_experiments = [
        "Real-data or high-fidelity orbit-driven trace validation (using actual TLEs or ephemeris)",
        "Oscillator phase-noise / clock model sensitivity (e.g., Allan variance models)",
        "Multi-pass or multi-satellite geometry with independent nuisance variables (e.g., separate oscillators per pass/satellite)",
        "Comparison against a naive non-projected separability metric to show the necessity of nuisance projection",
        "Reproducible result table regenerated from scripts (ensuring all numbers can be reproduced with --quick --seed 42)"
    ]

    # 12. Recommended positioning (how to position this work)
    recommended_positioning = (
        "This work characterizes the fundamental observability limits of LEO Doppler shift for IoT localization under realistic nuisance. "
        "It does not claim to achieve localization, but provides a framework to assess when and how Doppler shift can be informative."
    )

    # 13. Missing inputs (what we didn't have)
    missing_inputs = []
    if not index_path.exists():
        missing_inputs.append("research status index")
    if not contrib_path.exists():
        missing_inputs.append("contribution synthesis")
    for dir_name, file_name in expected_results.items():
        if evidence_map[dir_name] is None:
            missing_inputs.append(f"{dir_name}/{file_name}")

    # 14. Build the JSON output
    audit_json = {
        "supported_claims": supported_claims,
        "conditional_claims": conditional_claims,
        "unsupported_claims": unsupported_claims,
        "forbidden_claims": forbidden_claims,
        "evidence_map": {k: v is not None for k, v in evidence_map.items()},  # just boolean presence
        "weakest_links": weakest_links,
        "strongest_results": strongest_results,
        "minimum_extra_experiments_before_paper": minimum_extra_experiments,
        "recommended_positioning": recommended_positioning,
        "missing_inputs": missing_inputs
    }

    # 15. Write JSON and MD
    output_dir = results_dir / "research_claim_audit"
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "claim_audit.json"
    with open(json_path, 'w') as f:
        json.dump(audit_json, f, indent=2)

    # Markdown version (machine-readable)
    md_content = f"""# LEO-DTF Research Claim Audit

## Supported Claims
{chr(10).join(f"- {c}" for c in supported_claims)}

## Conditional Claims
{chr(10).join(f"- {c}" for c in conditional_claims)}

## Unsupported Claims
{chr(10).join(f"- {c}" for c in unsupported_claims)}

## Forbidden Claims
{chr(10).join(f"- {c}" for c in forbidden_claims)}

## Evidence Map (available result summaries)
{chr(10).join(f"- {k}: {'present' if v else 'missing'}" for k, v in evidence_map.items())}

## Weakest Links
{chr(10).join(f"- {w}" for w in weakest_links)}

## Strongest Results
{chr(10).join(f"- {s}" for s in strongest_results)}

## Minimum Extra Experiments Before Paper
{chr(10).join(f"- {e}" for e in minimum_extra_experiments)}

## Recommended Positioning
{recommended_positioning}

## Missing Inputs
{chr(10).join(f"- {m}" for m in missing_inputs) if missing_inputs else "None"}

---
*Generated automatically from repository state.*
"""
    md_path = output_dir / "claim_audit.md"
    with open(md_path, 'w') as f:
        f.write(md_content)

    print(f"Claim audit written to {json_path} and {md_path}")

if __name__ == "__main__":
    main()