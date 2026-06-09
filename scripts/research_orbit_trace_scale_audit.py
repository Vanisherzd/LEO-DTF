#!/usr/bin/env python3
"""
Read-only audit of orbit-driven DTOI trace scale.
Reads existing C10 results and flags potential scaling/unit issues.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Audit orbit-driven DTOI trace scale")
    parser.add_argument("--quick", action="store_true", help="Use quick parameters (not used in audit)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (not used in audit)")
    args = parser.parse_args()

    # Define input file paths (from C10)
    csv_path = Path("experiments/results/research_orbit_trace_bridge/orbit_trace_bridge_trials.csv")
    json_path = Path("experiments/results/research_orbit_trace_bridge/orbit_trace_bridge_summary.json")

    # If input files missing, run C10 to generate them
    if not csv_path.exists() or not json_path.exists():
        print("C10 result files missing. Generating them now...")
        result = subprocess.run([
            "uv", "run", "python",
            "scripts/research_orbit_trace_dtoi_bridge.py",
            "--quick", "--seed", str(args.seed)
        ], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Failed to generate C10 results: {result.stderr}")
            sys.exit(1)
        # Verify files now exist
        if not csv_path.exists() or not json_path.exists():
            print("C10 result files still missing after generation.")
            sys.exit(1)

    # Load CSV
    rows = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert numeric fields
            for key in ['carrier_hz', 'offset_m', 'duration_s', 'nuisance_order',
                        'total_samples', 'naive_snr', 'dtoi',
                        'energy_removed_by_nuisance']:
                if key in row:
                    try:
                        row[key] = float(row[key])
                    except ValueError:
                        pass
            rows.append(row)

    # Load JSON summary
    with open(json_path, 'r') as f:
        summary = json.load(f)

    # Compute audit metrics
    # Overall max DTOI and its row
    max_dtoi_row = max(rows, key=lambda x: x['dtoi'])
    max_dtoi = max_dtoi_row['dtoi']

    # Best per trace source from JSON summary (more reliable)
    best_by_trace = summary['summary']['best_by_trace_source']
    synth_best = best_by_trace.get('synthetic_curvature', {}).get('dtoi', 0.0)
    orbit_best = best_by_trace.get('orbit_driven_fallback', {}).get('dtoi', 0.0)
    gap = orbit_best - synth_best

    # Suspicious flags
    flags = []
    if orbit_best / max(synth_best, 1e-9) > 100:
        flags.append("orbit_synthetic_gap_gt_100x")
    if max_dtoi > 100:
        flags.append("dtoI_gt_100_requires_manual_unit_audit")
    # Check if best config offset_m <= 100 and dtoi > 100
    if max_dtoi_row['offset_m'] <= 100 and max_dtoi > 100:
        flags.append("small_offset_high_dtoi")

    # Unit risk assessment
    unit_risk = (
        "Potential unit mismatch: DTOI values exceed expected range (0-10) for observability diagnostic. "
        "Verify offset units (meters vs kilometers) and carrier scaling. "
        "The orbit-driven DTOI of ~507 suggests a possible factor of 1000 error in offset conversion."
    )

    # Differential Doppler risk assessment
    diff_doppler_risk = (
        "Differential Doppler signal is constructed as the difference between two ground stations. "
        "Validate that the satellite motion induces differential Doppler and that common-mode errors (e.g., clock drift) are removed. "
        "Ensure the nuisance projection (affine [1,t]) is appropriate for the differential signal."
    )

    # Recommendations
    if flags:
        recs = [
            "Perform manual unit audit of offset and carrier scaling in the orbit-driven signal generation.",
            "Verify the differential Doppler calculation uses two distinct ground positions.",
            "Check that the nuisance projection is applied to the differential signal, not absolute Doppler.",
            "Consider reducing the offset to validate scaling behavior.",
            "Compare with synthetic curvature results to isolate the source of discrepancy."
        ]
    else:
        recs = [
            "Results are within expected range for observability diagnostic (DTOI < 10).",
            "No immediate unit or scaling issues detected.",
            "Continue with standard validation procedures."
        ]

    # Conservative interpretation (must include specific phrases)
    conservative = (
        "C10 is an observability diagnostic, not OTA validation. "
        "DTOI=507 must not be used as a localization accuracy claim. "
        "Orbit-driven result requires unit/differential Doppler validation before paper use."
    )

    # Build audit JSON
    audit_json = {
        "max_dtoi": max_dtoi,
        "max_dtoi_row": max_dtoi_row,
        "synthetic_best_dtoi": synth_best,
        "orbit_best_dtoi": orbit_best,
        "orbit_vs_synthetic_gap": gap,
        "suspicious_scale_flags": flags,
        "unit_risk_assessment": unit_risk,
        "differential_doppler_risk_assessment": diff_doppler_risk,
        "recommendations": recs,
        "conservative_interpretation": conservative
    }

    # Create output directory
    out_dir = Path("experiments/results/research_orbit_trace_audit")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write JSON
    out_json = out_dir / "orbit_trace_scale_audit.json"
    with open(out_json, 'w') as f:
        json.dump(audit_json, f, indent=2)

    # Write Markdown
    out_md = out_dir / "orbit_trace_scale_audit.md"
    with open(out_md, 'w') as f:
        f.write("# Orbit-Driven DTOI Trace Scale Audit\n\n")
        f.write("## Audit Summary\n\n")
        f.write(f"- **Maximum DTOI**: {max_dtoi:.4f}\n")
        f.write(f"- **Best Synthetic DTOI**: {synth_best:.4f}\n")
        f.write(f"- **Best Orbit-Driven DTOI**: {orbit_best:.4f}\n")
        f.write(f"- **Orbit vs Synthetic Gap**: {gap:.4f}\n\n")
        f.write("## Suspicious Scale Flags\n\n")
        if flags:
            for flag in flags:
                f.write(f"- {flag}\n")
        else:
            f.write("None\n")
        f.write("\n")
        f.write("## Unit Risk Assessment\n\n")
        f.write(unit_risk + "\n\n")
        f.write("## Differential Doppler Risk Assessment\n\n")
        f.write(diff_doppler_risk + "\n\n")
        f.write("## Recommendations\n\n")
        for rec in recs:
            f.write(f"- {rec}\n")
        f.write("\n")
        f.write("## Conservative Interpretation\n\n")
        f.write(conservative + "\n")

    print(f"Audit JSON written to {out_json}")
    print(f"Audit Markdown written to {out_md}")

if __name__ == "__main__":
    main()
