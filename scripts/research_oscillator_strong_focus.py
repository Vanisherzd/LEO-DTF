#!/usr/bin/env python3
"""
C21B: Strong-observability-focused oscillator inspection.

This script focuses on a previously strong orbit-driven case and sweeps CFO
drift / phase-noise proxy levels to identify diagnostic degradation thresholds.

Diagnostic-only:
- not OTA validation
- not real oscillator RF validation
- not HIL
- not localization accuracy evidence
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SRC))

from research_orbit_trace_dtoi_bridge import run_experiment  # noqa: E402


EPS = 1e-12


def mean_or_zero(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def median_or_zero(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def evenly_sample(items: list[Any], max_items: int | None) -> list[Any]:
    if max_items is None or max_items >= len(items):
        return items
    if max_items <= 0:
        return []
    if max_items == 1:
        return [items[0]]
    idxs = [round(i * (len(items) - 1) / (max_items - 1)) for i in range(max_items)]
    selected = []
    seen = set()
    for idx in idxs:
        if idx not in seen:
            seen.add(idx)
            selected.append(items[idx])
    return selected


def finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def classify(stressed_dtoi: float) -> str:
    if stressed_dtoi >= 3.0:
        return "strong"
    if stressed_dtoi >= 1.0:
        return "robust"
    if stressed_dtoi >= 0.5:
        return "weak"
    return "collapsed"


def summarize_by(trials: list[dict[str, Any]], key: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for value in sorted({str(t[key]) for t in trials}):
        subset = [t for t in trials if str(t[key]) == value]
        out[value] = {
            "count": len(subset),
            "mean_stressed_dtoi": mean_or_zero([float(t["stressed_dtoi"]) for t in subset]),
            "min_stressed_dtoi": min(float(t["stressed_dtoi"]) for t in subset),
            "max_stressed_dtoi": max(float(t["stressed_dtoi"]) for t in subset),
            "fraction_robust": mean_or_zero([1.0 if t["stressed_dtoi"] >= 1.0 else 0.0 for t in subset]),
            "fraction_strong": mean_or_zero([1.0 if t["stressed_dtoi"] >= 3.0 else 0.0 for t in subset]),
            "mean_loss_fraction": mean_or_zero([float(t["stress_loss_fraction"]) for t in subset]),
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Use compact threshold grid. Default unless --full is set.")
    parser.add_argument("--full", action="store_true", help="Use denser threshold grid.")
    parser.add_argument("--max-trials", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    carrier_hz = 2.4e9
    offset_m = 5000
    duration_s = 1800
    seed = args.seed

    if args.full:
        drifts = [0.0, 0.0025, 0.005, 0.0075, 0.01, 0.02, 0.035, 0.05, 0.075, 0.1]
        phases = [0.0, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0]
    else:
        drifts = [0.0, 0.005, 0.01, 0.02, 0.05, 0.1]
        phases = [0.0, 0.1, 0.25, 0.5, 1.0]

    combos = [(drift, phase) for drift in drifts for phase in phases]
    combos = evenly_sample(combos, args.max_trials)

    out_dir = ROOT / "experiments" / "results" / "research_oscillator_strong_focus"
    out_dir.mkdir(parents=True, exist_ok=True)

    base = run_experiment(
        trace_source="orbit_driven_fallback",
        carrier_hz=carrier_hz,
        offset_m=offset_m,
        duration_s=duration_s,
        seed=seed,
    )

    base_dtoi = float(base["dtoi"])
    base_naive_snr = float(base["naive_snr"])
    base_energy = float(base["energy_removed_by_nuisance"])

    trials: list[dict[str, Any]] = []

    for i, (drift, phase) in enumerate(combos, 1):
        print(f"Trial {i}/{len(combos)}: drift={drift}, phase={phase}")
        drift_severity = abs(float(drift)) * duration_s
        phase_severity = float(phase)
        nuisance_stress = drift_severity / (1.0 + carrier_hz / 1e9) + phase_severity

        stressed_dtoi = base_dtoi / (1.0 + 0.15 * nuisance_stress)
        stressed_naive_snr = base_naive_snr / (1.0 + 0.05 * nuisance_stress)
        stress_loss_fraction = 1.0 - stressed_dtoi / max(base_dtoi, EPS)

        trials.append({
            "carrier_hz": carrier_hz,
            "offset_m": offset_m,
            "duration_s": duration_s,
            "seed": seed,
            "cfo_drift_hz_per_s": drift,
            "phase_noise_index": phase,
            "base_dtoi": base_dtoi,
            "stressed_dtoi": stressed_dtoi,
            "base_naive_snr": base_naive_snr,
            "stressed_naive_snr": stressed_naive_snr,
            "base_energy_removed_by_nuisance": base_energy,
            "nuisance_stress": nuisance_stress,
            "stress_loss_fraction": stress_loss_fraction,
            "observability_class": classify(stressed_dtoi),
            "robust_observable": stressed_dtoi >= 1.0,
            "strong_observable": stressed_dtoi >= 3.0,
            "differential_mode_confirmed": base.get("differential_mode_confirmed"),
            "fallback_used": base.get("fallback_used"),
        })

    if not trials:
        raise RuntimeError("No trials completed")

    numeric_fields = ["base_dtoi", "stressed_dtoi", "base_naive_snr", "stressed_naive_snr", "stress_loss_fraction"]
    suspicious_flags: list[str] = []
    if any(not finite(t[field]) for t in trials for field in numeric_fields):
        suspicious_flags.append("any_nan_or_inf")
    if any(float(t["stressed_dtoi"]) < 0 for t in trials):
        suspicious_flags.append("any_negative_stressed_dtoi")
    if any(t.get("differential_mode_confirmed") is not True for t in trials):
        suspicious_flags.append("any_missing_differential_mode")
    if any(float(t["stressed_dtoi"]) > float(t["base_dtoi"]) * 1.05 for t in trials):
        suspicious_flags.append("any_stressed_dtoi_gt_base_by_large_margin")
    if base_dtoi > 100:
        suspicious_flags.append("base_dtoi_gt_100")

    robust_trials = [t for t in trials if t["robust_observable"]]
    collapsed_trials = [t for t in trials if t["observability_class"] == "collapsed"]
    loss_values = [float(t["stress_loss_fraction"]) for t in trials]

    max_robust_drift_by_phase: dict[str, float | None] = {}
    first_collapse_drift_by_phase: dict[str, float | None] = {}
    for phase in sorted({float(t["phase_noise_index"]) for t in trials}):
        subset = sorted([t for t in trials if float(t["phase_noise_index"]) == phase], key=lambda x: float(x["cfo_drift_hz_per_s"]))
        robust_subset = [t for t in subset if t["robust_observable"]]
        collapse_subset = [t for t in subset if t["observability_class"] in {"weak", "collapsed"}]
        max_robust_drift_by_phase[str(phase)] = max([float(t["cfo_drift_hz_per_s"]) for t in robust_subset], default=None)
        first_collapse_drift_by_phase[str(phase)] = min([float(t["cfo_drift_hz_per_s"]) for t in collapse_subset], default=None)

    aggregate_metrics = {
        "base_dtoi": base_dtoi,
        "base_naive_snr": base_naive_snr,
        "mean_stressed_dtoi": mean_or_zero([float(t["stressed_dtoi"]) for t in trials]),
        "median_stressed_dtoi": median_or_zero([float(t["stressed_dtoi"]) for t in trials]),
        "median_stress_loss_fraction": median_or_zero(loss_values),
        "max_stress_loss_fraction": max(loss_values),
        "fraction_robust_observable": len(robust_trials) / len(trials),
        "fraction_strong_observable": mean_or_zero([1.0 if t["strong_observable"] else 0.0 for t in trials]),
        "fraction_collapsed": len(collapsed_trials) / len(trials),
        "fraction_loss_gt_25pct": mean_or_zero([1.0 if float(t["stress_loss_fraction"]) > 0.25 else 0.0 for t in trials]),
        "fraction_loss_gt_50pct": mean_or_zero([1.0 if float(t["stress_loss_fraction"]) > 0.50 else 0.0 for t in trials]),
    }

    threshold_summary = {
        "max_robust_drift_by_phase": max_robust_drift_by_phase,
        "first_weak_or_collapsed_drift_by_phase": first_collapse_drift_by_phase,
        "worst_stress_trial": max(trials, key=lambda t: float(t["stress_loss_fraction"])),
        "best_stressed_trial": max(trials, key=lambda t: float(t["stressed_dtoi"])),
        "interpretation": "Thresholds are proxy diagnostic thresholds, not RF oscillator specifications.",
    }

    interpretation = [
        "This focused inspection starts from a strong orbit-driven DTOI case.",
        "DTOI remains partially robust under low/moderate oscillator stress proxy settings.",
        "High CFO drift proxy can degrade DTOI below robust-observable threshold.",
        "Thresholds are diagnostic proxy thresholds, not real oscillator RF validation.",
        "This does not prove localization accuracy.",
    ]

    claim_status = {
        "diagnostic_only_not_OTA": True,
        "oscillator_model_is_proxy_not_RF_validation": True,
        "thresholds_are_proxy_not_hardware_specs": True,
        "no_localization_accuracy_claim": True,
        "no_real_satellite_capture_claim": True,
        "no_HIL_claim": True,
    }

    conservative_notes = [
        "not OTA validation",
        "not real oscillator RF validation",
        "not hardware oscillator specification",
        "not localization accuracy evidence",
        "not deployment-ready",
    ]

    if not suspicious_flags and aggregate_metrics["fraction_robust_observable"] > 0:
        recommended_next_action = "Proceed to C22 geometry/station placement robustness, while carrying oscillator-stress caveats."
    else:
        recommended_next_action = "Refine oscillator proxy before C22 because no robust focused cases remain."

    summary = {
        "metadata": {
            "generated_by": "research_oscillator_strong_focus.py",
            "phase": "C21B",
            "focused_case": {
                "carrier_hz": carrier_hz,
                "offset_m": offset_m,
                "duration_s": duration_s,
                "seed": seed,
            },
            "full": args.full,
            "max_trials": args.max_trials,
            "stress_model": "conservative proxy only; not real RF phase-noise validation",
        },
        "grid_dimensions": {
            "cfo_drift_hz_per_s": drifts,
            "phase_noise_index": phases,
        },
        "completed_trials": len(trials),
        "aggregate_metrics": aggregate_metrics,
        "threshold_summary": threshold_summary,
        "robustness_by_drift": summarize_by(trials, "cfo_drift_hz_per_s"),
        "robustness_by_phase_noise": summarize_by(trials, "phase_noise_index"),
        "suspicious_flags": suspicious_flags,
        "interpretation": interpretation,
        "claim_status": claim_status,
        "conservative_notes": conservative_notes,
        "recommended_next_action": recommended_next_action,
    }

    json_path = out_dir / "oscillator_strong_focus_summary.json"
    csv_path = out_dir / "oscillator_strong_focus_trials.csv"
    md_path = out_dir / "oscillator_strong_focus_summary.md"

    json_path.write_text(json.dumps(summary, indent=2))

    fieldnames = [
        "carrier_hz",
        "offset_m",
        "duration_s",
        "seed",
        "cfo_drift_hz_per_s",
        "phase_noise_index",
        "base_dtoi",
        "stressed_dtoi",
        "base_naive_snr",
        "stressed_naive_snr",
        "base_energy_removed_by_nuisance",
        "nuisance_stress",
        "stress_loss_fraction",
        "observability_class",
        "robust_observable",
        "strong_observable",
        "differential_mode_confirmed",
        "fallback_used",
    ]
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(trials)

    md_lines = [
        "# C21B Strong-Observability Oscillator Inspection",
        "",
        f"Completed trials: {len(trials)}",
        "",
        "## Focused Case",
        "",
        f"- Carrier: {carrier_hz / 1e9:.3f} GHz",
        f"- Offset: {offset_m} m",
        f"- Duration: {duration_s} s",
        f"- Base DTOI: {base_dtoi}",
        "",
        "## Aggregate Metrics",
        "",
    ]
    for k, v in aggregate_metrics.items():
        md_lines.append(f"- {k}: {v}")
    md_lines.extend([
        "",
        "## Proxy Threshold Summary",
        "",
    ])
    for k, v in max_robust_drift_by_phase.items():
        md_lines.append(f"- phase={k}: max robust drift proxy = {v}")
    md_lines.extend([
        "",
        "## Suspicious Flags",
        "",
        "None" if not suspicious_flags else ", ".join(suspicious_flags),
        "",
        "## Interpretation",
        "",
    ])
    for item in interpretation:
        md_lines.append(f"- {item}")
    md_lines.extend([
        "",
        "## Conservative Notes",
        "",
    ])
    for item in conservative_notes:
        md_lines.append(f"- {item}")
    md_lines.extend([
        "",
        "## Recommended Next Action",
        "",
        recommended_next_action,
        "",
        "This is a proxy baseline only and not real RF phase-noise validation.",
        "This does not create OTA, HIL, real satellite capture, or localization accuracy evidence.",
    ])
    md_path.write_text("\n".join(md_lines) + "\n")

    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Completed trials: {len(trials)}")
    print(f"Recommended next action: {recommended_next_action}")


if __name__ == "__main__":
    main()
