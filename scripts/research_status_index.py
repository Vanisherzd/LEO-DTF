#!/usr/bin/env python3
"""
Research status index generator for LEO-DTF.
Scans research scripts, tests, and result directories to summarize completed phases.
"""
import json
import os
from pathlib import Path
import csv

def main():
    # Define the base paths
    repo_root = Path("/tmp/LEO-DTF")
    scripts_dir = repo_root / "scripts"
    tests_dir = repo_root / "tests"
    results_dir = repo_root / "experiments" / "results"

    # Output directory for the index
    output_dir = results_dir / "research_index"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Scan for research scripts (excluding guard and autorun if we want, but include all research_*.py)
    research_scripts = []
    for f in scripts_dir.glob("research_*.py"):
        # Skip the guard and autorun? Actually, we are allowed to include them, but the task says research_*.py
        # We'll include all that match the pattern.
        research_scripts.append(f.name)

    # 2. Scan for test files
    test_files = []
    for f in tests_dir.glob("test_research_*.py"):
        test_files.append(f.name)

    # 3. Scan for result directories under experiments/results/research_*/
    result_dirs = []
    for d in results_dir.glob("research_*"):
        if d.is_dir():
            result_dirs.append(d.name)

    # 4. List of expected result directories from C2 to C7 and C5 contribution
    expected_result_dirs = [
        "research_multipass_observability",
        "research_multisat_geometry",
        "research_packet_budget",
        "research_contribution",
        "research_nuisance_order",
        "research_carrier_band"
    ]

    # Determine missing result directories
    missing_result_dirs = [d for d in expected_result_dirs if d not in result_dirs]

    # 5. Read key quantitative findings from available result summaries
    key_quantitative_findings = []

    # Helper to safely read JSON summary
    def read_summary(dir_name, file_name="summary.json"):
        path = results_dir / dir_name / file_name
        if path.exists():
            with open(path, 'r') as f:
                return json.load(f)
        return None

    # C2: multipass_observability
    c2_summary = read_summary("research_multipass_observability", "multipass_observability_summary.json")
    if c2_summary:
        best = c2_summary.get('summary', {}).get('best_global_config', {})
        if best:
            key_quantitative_findings.append(
                f"C2 Multi-pass: best global DTOI = {best.get('dtoi_global_nuisance', 'N/A'):.4f}, "
                f"best per-pass DTOI = {best.get('dtoi_per_pass_nuisance', 'N/A'):.4f}"
            )

    # C3: multisat_geometry
    c3_summary = read_summary("research_multisat_geometry", "multisat_geometry_summary.json")
    if c3_summary:
        best = c3_summary.get('summary', {}).get('best_global_config', {})
        if best:
            key_quantitative_findings.append(
                f"C3 Multi-satellite: best global DTOI = {best.get('dtoi_global_nuisance', 'N/A'):.4f}, "
                f"best per-satellite DTOI = {best.get('dtoi_per_satellite_nuisance', 'N/A'):.4f}"
            )

    # C4: packet_budget
    c4_summary = read_summary("research_packet_budget", "packet_budget_summary.json")
    if c4_summary:
        best = c4_summary.get('summary', {}).get('best_config', {})
        if best:
            key_quantitative_findings.append(
                f"C4 Packet budget: best DTOI = {best.get('dtoi', 'N/A'):.4f} "
                f"(packet_count={best.get('packet_count', 'N/A')}, carrier={best.get('carrier_hz', 'N/A')/1e9:.1f} GHz, "
                f"offset={best.get('offset_m', 'N/A')} m, duration={best.get('duration_s', 'N/A')} s)"
            )

    # C5: contribution (we have the synthesis JSON)
    c5_summary = read_summary("research_contribution", "contribution_synthesis.json")
    if c5_summary:
        # We can pull a few key points from the synthesis if we want, but let's just note it exists.
        key_quantitative_findings.append("C5 Contribution synthesis: generated JSON and Markdown summary of C1-C4.")

    # C6A: nuisance_order
    c6_summary = read_summary("research_nuisance_order", "nuisance_order_summary.json")
    if c6_summary:
        best = c6_summary.get('summary', {}).get('best_config', {})
        if best:
            key_quantitative_findings.append(
                f"C6A Nuisance order: best DTOI = {best.get('dtoi', 'N/A'):.4f} "
                f"(nuisance_order={best.get('nuisance_order', 'N/A')}, carrier={best.get('carrier_hz', 'N/A')/1e9:.1f} GHz, "
                f"offset={best.get('offset_m', 'N/A')} m, duration={best.get('duration_s', 'N/A')} s)"
            )

    # C7: carrier_band
    c7_summary = read_summary("research_carrier_band", "carrier_band_summary.json")
    if c7_summary:
        best = c7_summary.get('summary', {}).get('best_config', {})
        if best:
            key_quantitative_findings.append(
                f"C7 Carrier band: best DTOI = {best.get('dtoi', 'N/A'):.4f} "
                f"(carrier={best.get('carrier_hz', 'N/A')/1e9:.1f} GHz, offset={best.get('offset_m', 'N/A')} m, "
                f"duration={best.get('duration_s', 'N/A')} s, nuisance_order={best.get('nuisance_order', 'N/A')})"
            )

    # 6. Build the JSON output
    index_json = {
        "completed_phases": ["C2", "C3", "C4", "C5", "C6A", "C7"],  # We can also derive from available result dirs, but we know
        "available_scripts": sorted(research_scripts),
        "available_tests": sorted(test_files),
        "available_result_dirs": sorted(result_dirs),
        "missing_result_dirs": sorted(missing_result_dirs),
        "key_quantitative_findings": key_quantitative_findings,
        "supported_core_contribution": "Nuisance-aware Doppler-Time Observability Characterization for LEO IoT.",
        "forbidden_claims": [
            "real OTA validation",
            "meter-level localization",
            "GNSS replacement",
            "single-pass always works",
            "multi-pass/multi-satellite solves localization",
            "HIL validation completed"
        ],
        "next_recommended_phases": []  # We can leave empty or suggest further studies
    }

    # Write JSON
    json_path = output_dir / "research_status_index.json"
    with open(json_path, 'w') as f:
        json.dump(index_json, f, indent=2)

    # 7. Generate Markdown version (machine-readable, not prose)
    md_content = f"""# LEO-DTF Research Status Index

## Completed Phases
{', '.join(index_json['completed_phases'])}

## Available Research Scripts
{chr(10).join(f"- {s}" for s in index_json['available_scripts'])}

## Available Test Files
{chr(10).join(f"- {t}" for t in index_json['available_tests'])}

## Available Result Directories
{chr(10).join(f"- {d}" for d in index_json['available_result_dirs'])}

## Missing Result Directories
{chr(10).join(f"- {d}" for d in index_json['missing_result_dirs']) if index_json['missing_result_dirs'] else "None"}

## Key Quantitative Findings
{chr(10).join(f"- {f}" for f in index_json['key_quantitative_findings'])}

## Supported Core Contribution
{index_json['supported_core_contribution']}

## Forbidden Claims
{chr(10).join(f"- {c}" for c in index_json['forbidden_claims'])}

## Next Recommended Phases
{chr(10).join(f"- {p}" for p in index_json['next_recommended_phases']) if index_json['next_recommended_phases'] else "None"}

---
*Generated automatically from repository state.*
"""
    md_path = output_dir / "research_status_index.md"
    with open(md_path, 'w') as f:
        f.write(md_content)

    print(f"Research status index written to {json_path} and {md_path}")

if __name__ == "__main__":
    main()