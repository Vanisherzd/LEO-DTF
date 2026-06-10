#!/usr/bin/env python3
"""
C21: Oscillator/CFO sensitivity sweep for corrected orbit-driven DTOI.

This is a conservative diagnostic proxy. It is not real RF phase-noise
validation, OTA validation, HIL, or localization accuracy evidence.
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


def grid_for_args(args: argparse.Namespace):
    if args.full:
        carriers_hz = [137e6, 433e6, 868e6, 915e6, 2.4e9]
        offsets_m = [100, 500, 1000, 5000]
        durations_s = [300, 600, 1200, 1800]
        seeds = [7, 42, 123]
        cfo_drift_hz_per_s = [0.0, 0.005, 0.01, 0.05, 0.1]
        phase_noise_index = [0.0, 0.1, 0.25, 0.5, 1.0]
    else:
        carriers_hz = [2.4e9]
        offsets_m = [100, 5000]
        durations_s = [300, 1800]
        seeds = [42]
        cfo_drift_hz_per_s = [0.0, 0.01, 0.05]
        phase_noise_index = [0.0, 0.25, 0.5]

    if args.seed is not None:
        seeds = [args.seed]

    return carriers_hz, offsets_m, durations_s, seeds, cfo_drift_hz_per_s, phase_noise_index


def mean_or_zero(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def median_or_zero(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def summarize_group(trials: list[dict[str, Any]], key: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    groups = sorted({str(t[key]) for t in trials})
    for group in groups:
        subset = [t for t in trials if str(t[key]) == group]
        out[group] = {
            "count": len(subset),
            "mean_stressed_dtoi": mean_or_zero([float(t["stressed_dtoi"]) for t in subset]),
            "fraction_robust_observable": mean_or_zero([1.0 if t["robust_observable"] else 0.0 for t in subset]),
            "fraction_strong_observable": mean_or_zero([1.0 if t["strong_observable"] else 0.0 for t in subset]),
            "mean_stress_loss_fraction": mean_or_zero([float(t["stress_loss_fraction"]) for t in subset]),
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Run quick grid. Default unless --full is set.")
    parser.add_argument("--full", action="store_true", help="Run full diagnostic grid.")
    parser.add_argument("--max-trials", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    carriers_hz, offsets_m, durations_s, seeds, drifts, phases = grid_for_args(args)

    combos = [
        (carrier, offset, duration, seed, drift, phase)
        for carrier in carriers_hz
        for offset in offsets_m
        for duration in durations_s
        for seed in seeds
        for drift in drifts
        for phase in phases
    ]
    if args.max_trials is not None:
        combos = combos[: args.max_trials]

    out_dir = ROOT / "experiments" / "results" / "research_oscillator_sensitivity"
    out_dir.mkdir(parents=True, exist_ok=True)

    trials: list[dict[str, Any]] = []

    for i, (carrier_hz, offset_m, duration_s, seed, drift, phase) in enumerate(combos, 1):
        print(
            f"Trial {i}/{len(combos)}: carrier={carrier_hz/1e6:.3f} MHz, "
            f"offset={offset_m} m, duration={duration_s} s, seed={seed}, "
            f"drift={drift}, phase={phase}"
        )
        result = run_experiment(
            trace_source="orbit_driven_fallback",
            carrier_hz=carrier_hz,
            offset_m=offset_m,
            duration_s=duration_s,
            seed=seed,
        )

        base_dtoi = float(result["dtoi"])
        base_naive_snr = float(result["naive_snr"])
        base_energy = float(result["energy_removed_by_nuisance"])

        drift_severity = abs(float(drift)) * float(duration_s)
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
            "robust_observable": stressed_dtoi >= 1.0,
            "strong_observable": stressed_dtoi >= 3.0,
            "differential_mode_confirmed": result.get("differential_mode_confirmed"),
            "fallback_used": result.get("fallback_used"),
        })

    if not trials:
        raise RuntimeError("No trials completed")

    base_dtoi_values = [float(t["base_dtoi"]) for t in trials]
    stressed_dtoi_values = [float(t["stressed_dtoi"]) for t in trials]
    loss_values = [float(t["stress_loss_fraction"]) for t in trials]

    aggregate_metrics = {
        "mean_base_dtoi": mean_or_zero(base_dtoi_values),
        "mean_stressed_dtoi": mean_or_zero(stressed_dtoi_values),
        "median_stress_loss_fraction": median_or_zero(loss_values),
        "max_stress_loss_fraction": max(loss_values),
        "fraction_robust_observable": mean_or_zero([1.0 if t["robust_observable"] else 0.0 for t in trials]),
        "fraction_strong_observable": mean_or_zero([1.0 if t["strong_observable"] else 0.0 for t in trials]),
        "fraction_loss_gt_25pct": mean_or_zero([1.0 if float(t["stress_loss_fraction"]) > 0.25 else 0.0 for t in trials]),
        "fraction_loss_gt_50pct": mean_or_zero([1.0 if float(t["stress_loss_fraction"]) > 0.50 else 0.0 for t in trials]),
    }

    suspicious_flags: list[str] = []
    numeric_fields = ["base_dtoi", "stressed_dtoi", "base_naive_snr", "stressed_naive_snr", "stress_loss_fraction"]
    if any(not finite(t[field]) for t in trials for field in numeric_fields):
        suspicious_flags.append("any_nan_or_inf")
    if any(float(t["stressed_dtoi"]) < 0 for t in trials):
        suspicious_flags.append("any_negative_stressed_dtoi")
    if any(t.get("differential_mode_confirmed") is not True for t in trials):
        suspicious_flags.append("any_missing_differential_mode")
    if any(float(t["stressed_dtoi"]) > float(t["base_dtoi"]) * 1.05 for t in trials):
        suspicious_flags.append("any_stressed_dtoi_gt_base_by_large_margin")
    if any(float(t["base_dtoi"]) > 100 for t in trials):
        suspicious_flags.append("any_base_dtoi_gt_100")

    best_base_trial = max(trials, key=lambda t: float(t["base_dtoi"]))
    best_stressed_trial = max(trials, key=lambda t: float(t["stressed_dtoi"]))
    worst_stress_loss_trial = max(trials, key=lambda t: float(t["stress_loss_fraction"]))

    interpretation = [
        "DTOI sensitivity is evaluated with a conservative oscillator stress proxy.",
        "This is not real RF phase-noise validation.",
        "Higher drift/phase-noise proxy generally reduces stressed DTOI.",
        "Robustness should be interpreted as diagnostic resilience, not localization accuracy.",
    ]

    claim_status = {
        "diagnostic_only_not_OTA": True,
        "oscillator_model_is_proxy_not_RF_validation": True,
        "no_localization_accuracy_claim": True,
        "no_real_satellite_capture_claim": True,
        "no_HIL_claim": True,
    }

    conservative_notes = [
        "not OTA validation",
        "not real oscillator RF validation",
        "not localization accuracy evidence",
        "not deployment-ready",
    ]

    if not suspicious_flags and aggregate_metrics["fraction_robust_observable"] >= 0.25:
        recommended_next_action = "Proceed to C22 geometry/station placement robustness; oscillator proxy robustness is interpretable."
    else:
        recommended_next_action = "Expand oscillator model before C22; current robustness is weak or flags are present."

    summary = {
        "metadata": {
            "generated_by": "research_oscillator_sensitivity.py",
            "quick_default": not args.full,
            "full": args.full,
            "max_trials": args.max_trials,
            "seed": args.seed,
            "stress_model": "conservative proxy only; not real RF phase-noise validation",
        },
        "grid_dimensions": {
            "carriers_hz": carriers_hz,
            "offsets_m": offsets_m,
            "durations_s": durations_s,
            "seeds": seeds,
            "cfo_drift_hz_per_s": drifts,
            "phase_noise_index": phases,
        },
        "completed_trials": len(trials),
        "best_base_trial": best_base_trial,
        "best_stressed_trial": best_stressed_trial,
        "worst_stress_loss_trial": worst_stress_loss_trial,
        "aggregate_metrics": aggregate_metrics,
        "robustness_by_drift": summarize_group(trials, "cfo_drift_hz_per_s"),
        "robustness_by_phase_noise": summarize_group(trials, "phase_noise_index"),
        "robustness_by_carrier": summarize_group(trials, "carrier_hz"),
        "sensitivity_summary": {
            "stress_model_is_proxy": True,
            "mean_loss_fraction": mean_or_zero(loss_values),
            "max_loss_fraction": max(loss_values),
            "robustness_interpretation": "diagnostic resilience only",
        },
        "suspicious_flags": suspicious_flags,
        "interpretation": interpretation,
        "claim_status": claim_status,
        "conservative_notes": conservative_notes,
        "recommended_next_action": recommended_next_action,
    }

    json_path = out_dir / "oscillator_sensitivity_summary.json"
    csv_path = out_dir / "oscillator_sensitivity_trials.csv"
    md_path = out_dir / "oscillator_sensitivity_summary.md"

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
        "# C21 Oscillator Sensitivity Sweep",
        "",
        f"Completed trials: {len(trials)}",
        "",
        "## Aggregate Metrics",
        "",
    ]
    for k, v in aggregate_metrics.items():
        md_lines.append(f"- {k}: {v}")

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
        "This oscillator stress model is a proxy and not real RF phase-noise validation.",
        "This sweep does not create OTA, HIL, real satellite capture, or localization accuracy evidence.",
    ])
    md_path.write_text("\n".join(md_lines) + "\n")

    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Completed trials: {len(trials)}")
    print(f"Recommended next action: {recommended_next_action}")


if __name__ == "__main__":
    main()
