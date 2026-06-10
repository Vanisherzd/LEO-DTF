#!/usr/bin/env python3
"""
C23: Consolidated research evidence table.

This script consolidates diagnostic evidence from C19-C22 into a single
machine-readable evidence table. It does not generate manuscript claims and
does not create OTA, HIL, RF, deployment, or localization-accuracy evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


SOURCES = [
    {
        "phase": "C19",
        "title": "Orbit-driven parameter sweep",
        "path": ROOT / "experiments/results/research_orbit_parameter_sweep/orbit_parameter_sweep_summary.json",
        "generator": ["scripts/research_orbit_parameter_sweep.py", "--quick", "--seed", "42"],
    },
    {
        "phase": "C20",
        "title": "DTOI baseline comparison",
        "path": ROOT / "experiments/results/research_baseline_comparison/baseline_comparison_summary.json",
        "generator": ["scripts/research_baseline_comparison.py", "--quick", "--seed", "42"],
    },
    {
        "phase": "C21",
        "title": "Oscillator/CFO sensitivity sweep",
        "path": ROOT / "experiments/results/research_oscillator_sensitivity/oscillator_sensitivity_summary.json",
        "generator": ["scripts/research_oscillator_sensitivity.py", "--quick", "--seed", "42", "--max-trials", "12"],
    },
    {
        "phase": "C21B",
        "title": "Strong-case oscillator threshold inspection",
        "path": ROOT / "experiments/results/research_oscillator_strong_focus/oscillator_strong_focus_summary.json",
        "generator": ["scripts/research_oscillator_strong_focus.py", "--quick", "--seed", "42", "--max-trials", "12"],
    },
    {
        "phase": "C22",
        "title": "Geometry placement robustness",
        "path": ROOT / "experiments/results/research_geometry_placement_robustness/geometry_placement_summary.json",
        "generator": ["scripts/research_geometry_placement_robustness.py", "--quick", "--seed", "42", "--max-trials", "16"],
    },
]


def run_generator(cmd: list[str]) -> None:
    full_cmd = [sys.executable, *cmd]
    result = subprocess.run(full_cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"Generator failed: {' '.join(cmd)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def suspicious_flags(data: dict[str, Any] | None) -> list[str]:
    if not data:
        return ["missing_source"]
    flags = data.get("suspicious_flags", [])
    if flags is None:
        return []
    return list(flags)


def mismatch_count(data: dict[str, Any]) -> int:
    cases = data.get("mismatch_cases", {})
    if not isinstance(cases, dict):
        return 0
    return sum(len(v) for v in cases.values() if isinstance(v, list))


def extract_key_metrics(phase: str, data: dict[str, Any] | None) -> dict[str, Any]:
    if data is None:
        return {}

    metrics: dict[str, Any] = {
        "completed_trials": data.get("completed_trials"),
        "recommended_next_action": data.get("recommended_next_action"),
        "suspicious_flags": suspicious_flags(data),
    }

    if phase == "C19":
        stability = data.get("stability_summary", {})
        best = data.get("best_config", {})
        metrics.update({
            "best_dtoi": best.get("dtoi"),
            "fraction_observable": stability.get("fraction_observable"),
            "fraction_dtoi_gt_1": stability.get("fraction_dtoi_gt_1"),
            "fraction_dtoi_gt_3": stability.get("fraction_dtoi_gt_3"),
        })
    elif phase == "C20":
        agg = data.get("aggregate_metrics", {})
        metrics.update({
            "mean_dtoi": agg.get("mean_dtoi"),
            "fraction_dtoi_strong_but_naive_not_top": agg.get("fraction_dtoi_strong_but_naive_not_top"),
            "fraction_naive_high_but_dtoi_weak": agg.get("fraction_naive_high_but_dtoi_weak"),
            "mismatch_count": mismatch_count(data),
        })
    elif phase == "C21":
        agg = data.get("aggregate_metrics", {})
        metrics.update({
            "mean_stressed_dtoi": agg.get("mean_stressed_dtoi"),
            "fraction_robust_observable": agg.get("fraction_robust_observable"),
            "fraction_loss_gt_25pct": agg.get("fraction_loss_gt_25pct"),
            "max_stress_loss_fraction": agg.get("max_stress_loss_fraction"),
        })
    elif phase == "C21B":
        agg = data.get("aggregate_metrics", {})
        threshold = data.get("threshold_summary", {})
        metrics.update({
            "base_dtoi": agg.get("base_dtoi"),
            "fraction_robust_observable": agg.get("fraction_robust_observable"),
            "fraction_collapsed": agg.get("fraction_collapsed"),
            "max_stress_loss_fraction": agg.get("max_stress_loss_fraction"),
            "threshold_interpretation": threshold.get("interpretation"),
        })
    elif phase == "C22":
        agg = data.get("aggregate_metrics", {})
        metrics.update({
            "mean_geometry_adjusted_dtoi": agg.get("mean_geometry_adjusted_dtoi"),
            "fraction_robust_observable": agg.get("fraction_robust_observable"),
            "fraction_collapsed": agg.get("fraction_collapsed"),
            "max_geometry_loss_fraction": agg.get("max_geometry_loss_fraction"),
        })

    return metrics


def claim_scope_for_phase(phase: str) -> str:
    scopes = {
        "C19": "orbit-driven DTOI robustness diagnostic",
        "C20": "DTOI-vs-baseline diagnostic comparison",
        "C21": "oscillator proxy sensitivity diagnostic",
        "C21B": "focused oscillator proxy threshold diagnostic",
        "C22": "geometry placement proxy robustness diagnostic",
    }
    return scopes[phase]


def conservative_limitations_for_phase(phase: str) -> list[str]:
    base = [
        "not OTA validation",
        "not HIL evidence",
        "not real satellite capture evidence",
        "not localization accuracy evidence",
        "not deployment-ready evidence",
    ]
    extra = {
        "C19": ["orbit-driven simulation/proxy only"],
        "C20": ["matched-filter statistic is a proxy baseline only"],
        "C21": ["oscillator model is a conservative proxy, not real RF phase-noise validation"],
        "C21B": ["thresholds are proxy diagnostic thresholds, not hardware oscillator specifications"],
        "C22": ["geometry model is a proxy, not surveyed station placement validation"],
    }
    return base + extra[phase]


def make_record(source: dict[str, Any], data: dict[str, Any] | None) -> dict[str, Any]:
    phase = source["phase"]
    status = "available" if data is not None else "missing"
    flags = suspicious_flags(data)
    key_metrics = extract_key_metrics(phase, data)
    return {
        "phase": phase,
        "title": source["title"],
        "status": status,
        "source_path": str(source["path"].relative_to(ROOT)),
        "claim_scope": claim_scope_for_phase(phase),
        "completed_trials": key_metrics.get("completed_trials"),
        "key_metrics": key_metrics,
        "suspicious_flags": flags,
        "conservative_limitations": conservative_limitations_for_phase(phase),
        "recommended_next_action": key_metrics.get("recommended_next_action"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate-missing", action="store_true", help="Run quick generators for missing inputs.")
    parser.add_argument("--require-all", action="store_true", help="Fail if any source summary is missing.")
    args = parser.parse_args()

    if args.generate_missing:
        for src in SOURCES:
            if not src["path"].exists():
                print(f"Generating missing source for {src['phase']}: {src['path']}")
                run_generator(src["generator"])

    records = []
    missing = []
    for src in SOURCES:
        data = load_json(src["path"])
        if data is None:
            missing.append(src["phase"])
        records.append(make_record(src, data))

    if args.require_all and missing:
        raise RuntimeError(f"Missing required evidence sources: {missing}")

    all_flags = [flag for rec in records for flag in rec["suspicious_flags"]]
    available_count = sum(1 for rec in records if rec["status"] == "available")

    safe_claims = [
        "DTOI is supported only as a nuisance-aware observability diagnostic.",
        "Orbit-driven differential Doppler evidence is simulation/proxy evidence only.",
        "DTOI shows mismatch cases against naive Doppler/SNR proxy baselines.",
        "Oscillator sensitivity evidence should be carried with proxy-stress caveats.",
        "Geometry robustness evidence should be carried with placement-proxy caveats.",
    ]

    forbidden_claims = [
        "OTA validation completed",
        "HIL validation completed",
        "real satellite capture validated",
        "localization accuracy proven",
        "meter-level localization proven",
        "deployment-ready system",
        "hardware oscillator specification derived",
        "surveyed station placement validated",
    ]

    overall_assessment = {
        "available_sources": available_count,
        "total_sources": len(SOURCES),
        "missing_sources": missing,
        "all_sources_available": available_count == len(SOURCES),
        "all_suspicious_flags_empty": len(all_flags) == 0,
        "ready_for_claim_table_sync": available_count == len(SOURCES) and len(all_flags) == 0,
        "diagnostic_only": True,
        "not_ota_not_hil_not_localization": True,
    }

    if overall_assessment["ready_for_claim_table_sync"]:
        recommended_next_action = (
            "Proceed to manual claim/evidence synchronization; keep all claims diagnostic-only."
        )
    else:
        recommended_next_action = (
            "Resolve missing evidence or suspicious flags before claim/evidence synchronization."
        )

    summary = {
        "metadata": {
            "generated_by": "research_consolidated_evidence_table.py",
            "phase": "C23",
            "source_phases": [src["phase"] for src in SOURCES],
            "generate_missing": args.generate_missing,
            "require_all": args.require_all,
        },
        "evidence_records": records,
        "overall_assessment": overall_assessment,
        "safe_claims": safe_claims,
        "forbidden_claims": forbidden_claims,
        "conservative_summary": [
            "This table consolidates diagnostic/proxy evidence only.",
            "It does not create manuscript-ready OTA, HIL, RF, deployment, or localization evidence.",
            "Any paper-side claim must remain bounded to nuisance-aware DTOI observability diagnostics.",
        ],
        "recommended_next_action": recommended_next_action,
    }

    out_dir = ROOT / "experiments" / "results" / "research_consolidated_evidence_table"
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "consolidated_evidence_table.json"
    csv_path = out_dir / "consolidated_evidence_table.csv"
    md_path = out_dir / "consolidated_evidence_table.md"

    json_path.write_text(json.dumps(summary, indent=2))

    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "phase",
                "title",
                "status",
                "completed_trials",
                "claim_scope",
                "suspicious_flags",
                "recommended_next_action",
            ],
        )
        writer.writeheader()
        for rec in records:
            writer.writerow({
                "phase": rec["phase"],
                "title": rec["title"],
                "status": rec["status"],
                "completed_trials": rec["completed_trials"],
                "claim_scope": rec["claim_scope"],
                "suspicious_flags": ";".join(rec["suspicious_flags"]),
                "recommended_next_action": rec["recommended_next_action"],
            })

    md_lines = [
        "# C23 Consolidated Research Evidence Table",
        "",
        "## Overall Assessment",
        "",
    ]
    for k, v in overall_assessment.items():
        md_lines.append(f"- {k}: {v}")

    md_lines.extend(["", "## Evidence Records", ""])
    for rec in records:
        md_lines.extend([
            f"### {rec['phase']} — {rec['title']}",
            "",
            f"- Status: {rec['status']}",
            f"- Completed trials: {rec['completed_trials']}",
            f"- Claim scope: {rec['claim_scope']}",
            f"- Suspicious flags: {rec['suspicious_flags'] or 'None'}",
            f"- Recommended next action: {rec['recommended_next_action']}",
            "",
        ])

    md_lines.extend(["## Safe Claims", ""])
    for item in safe_claims:
        md_lines.append(f"- {item}")

    md_lines.extend(["", "## Forbidden Claims", ""])
    for item in forbidden_claims:
        md_lines.append(f"- {item}")

    md_lines.extend(["", "## Conservative Summary", ""])
    for item in summary["conservative_summary"]:
        md_lines.append(f"- {item}")

    md_lines.extend([
        "",
        "## Recommended Next Action",
        "",
        recommended_next_action,
        "",
        "This is a diagnostic-only evidence table and does not create OTA, HIL, RF, deployment, or localization-accuracy evidence.",
    ])

    md_path.write_text("\n".join(md_lines) + "\n")

    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Available sources: {available_count}/{len(SOURCES)}")
    print(f"All suspicious flags empty: {len(all_flags) == 0}")
    print(f"Recommended next action: {recommended_next_action}")


if __name__ == "__main__":
    main()
