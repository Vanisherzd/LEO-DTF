#!/usr/bin/env python3
"""
C22: Geometry / station placement robustness diagnostic.

This script evaluates whether corrected orbit-driven DTOI remains informative
under multiple ground-placement proxy geometries. The current orbit bridge
parameterizes displacement by offset magnitude, so direction-dependent placement
is modeled as a conservative geometry proxy, not as real surveyed station geometry.

Diagnostic-only:
- not OTA validation
- not real station deployment validation
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


def finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def evenly_sample(items: list[Any], max_items: int | None) -> list[Any]:
    """Select an evenly spaced deterministic subset instead of prefix truncation."""
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


def classify(dtoi: float) -> str:
    if dtoi >= 3.0:
        return "strong"
    if dtoi >= 1.0:
        return "robust"
    if dtoi >= 0.5:
        return "weak"
    return "collapsed"


def geometry_factor(direction: str, geometry_class: str) -> float:
    """Conservative placement proxy factor.

    This is not a real surveyed-station transform. It approximates how different
    placement orientations might project onto an orbit-driven differential signal.
    """
    direction_factor = {
        "east": 1.00,
        "north": 0.92,
        "northeast": 0.96,
        "northwest": 0.88,
        "southwest": 0.84,
        "radial_proxy": 0.78,
    }[direction]
    class_factor = {
        "favorable": 1.00,
        "nominal": 0.90,
        "unfavorable": 0.72,
    }[geometry_class]
    return direction_factor * class_factor


def summarize_by(trials: list[dict[str, Any]], key: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for value in sorted({str(t[key]) for t in trials}):
        subset = [t for t in trials if str(t[key]) == value]
        out[value] = {
            "count": len(subset),
            "mean_geometry_adjusted_dtoi": mean_or_zero([float(t["geometry_adjusted_dtoi"]) for t in subset]),
            "min_geometry_adjusted_dtoi": min(float(t["geometry_adjusted_dtoi"]) for t in subset),
            "max_geometry_adjusted_dtoi": max(float(t["geometry_adjusted_dtoi"]) for t in subset),
            "fraction_robust": mean_or_zero([1.0 if t["robust_observable"] else 0.0 for t in subset]),
            "fraction_strong": mean_or_zero([1.0 if t["strong_observable"] else 0.0 for t in subset]),
            "mean_geometry_loss_fraction": mean_or_zero([float(t["geometry_loss_fraction"]) for t in subset]),
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Use quick diagnostic grid. Default unless --full is set.")
    parser.add_argument("--full", action="store_true", help="Use denser geometry diagnostic grid.")
    parser.add_argument("--max-trials", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.full:
        carriers_hz = [433e6, 868e6, 915e6, 2.4e9]
        offsets_m = [100, 500, 1000, 5000]
        durations_s = [300, 600, 1200, 1800]
        directions = ["east", "north", "northeast", "northwest", "southwest", "radial_proxy"]
        geometry_classes = ["favorable", "nominal", "unfavorable"]
    else:
        carriers_hz = [2.4e9]
        offsets_m = [100, 5000]
        durations_s = [300, 1800]
        directions = ["east", "north", "northeast", "southwest", "radial_proxy"]
        geometry_classes = ["favorable", "nominal", "unfavorable"]

    combos = [
        (carrier, offset, duration, direction, geometry_class)
        for carrier in carriers_hz
        for offset in offsets_m
        for duration in durations_s
        for direction in directions
        for geometry_class in geometry_classes
    ]
    combos = evenly_sample(combos, args.max_trials)

    out_dir = ROOT / "experiments" / "results" / "research_geometry_placement_robustness"
    out_dir.mkdir(parents=True, exist_ok=True)

    trials: list[dict[str, Any]] = []

    for i, (carrier_hz, offset_m, duration_s, direction, geometry_class) in enumerate(combos, 1):
        print(
            f"Trial {i}/{len(combos)}: carrier={carrier_hz/1e6:.3f} MHz, "
            f"offset={offset_m} m, duration={duration_s} s, "
            f"direction={direction}, geometry={geometry_class}"
        )

        result = run_experiment(
            trace_source="orbit_driven_fallback",
            carrier_hz=carrier_hz,
            offset_m=offset_m,
            duration_s=duration_s,
            seed=args.seed,
        )

        base_dtoi = float(result["dtoi"])
        naive_snr = float(result["naive_snr"])
        energy_removed = float(result["energy_removed_by_nuisance"])
        factor = geometry_factor(direction, geometry_class)
        geometry_adjusted_dtoi = base_dtoi * factor
        geometry_loss_fraction = 1.0 - geometry_adjusted_dtoi / max(base_dtoi, EPS)

        trials.append({
            "carrier_hz": carrier_hz,
            "offset_m": offset_m,
            "duration_s": duration_s,
            "seed": args.seed,
            "placement_direction": direction,
            "geometry_class": geometry_class,
            "geometry_factor": factor,
            "base_dtoi": base_dtoi,
            "geometry_adjusted_dtoi": geometry_adjusted_dtoi,
            "naive_snr": naive_snr,
            "energy_removed_by_nuisance": energy_removed,
            "geometry_loss_fraction": geometry_loss_fraction,
            "observability_class": classify(geometry_adjusted_dtoi),
            "robust_observable": geometry_adjusted_dtoi >= 1.0,
            "strong_observable": geometry_adjusted_dtoi >= 3.0,
            "differential_mode_confirmed": result.get("differential_mode_confirmed"),
            "fallback_used": result.get("fallback_used"),
        })

    if not trials:
        raise RuntimeError("No trials completed")

    base_values = [float(t["base_dtoi"]) for t in trials]
    adjusted_values = [float(t["geometry_adjusted_dtoi"]) for t in trials]
    loss_values = [float(t["geometry_loss_fraction"]) for t in trials]

    suspicious_flags: list[str] = []
    numeric_fields = ["base_dtoi", "geometry_adjusted_dtoi", "naive_snr", "energy_removed_by_nuisance", "geometry_loss_fraction"]
    if any(not finite(t[field]) for t in trials for field in numeric_fields):
        suspicious_flags.append("any_nan_or_inf")
    if any(float(t["geometry_adjusted_dtoi"]) < 0 for t in trials):
        suspicious_flags.append("any_negative_adjusted_dtoi")
    if any(t.get("differential_mode_confirmed") is not True for t in trials):
        suspicious_flags.append("any_missing_differential_mode")
    if any(float(t["geometry_adjusted_dtoi"]) > float(t["base_dtoi"]) * 1.05 for t in trials):
        suspicious_flags.append("any_adjusted_dtoi_gt_base_by_large_margin")
    if any(float(t["base_dtoi"]) > 100 for t in trials):
        suspicious_flags.append("any_base_dtoi_gt_100")

    robust_trials = [t for t in trials if t["robust_observable"]]
    collapsed_trials = [t for t in trials if t["observability_class"] == "collapsed"]

    aggregate_metrics = {
        "mean_base_dtoi": mean_or_zero(base_values),
        "mean_geometry_adjusted_dtoi": mean_or_zero(adjusted_values),
        "median_geometry_adjusted_dtoi": median_or_zero(adjusted_values),
        "median_geometry_loss_fraction": median_or_zero(loss_values),
        "max_geometry_loss_fraction": max(loss_values),
        "fraction_robust_observable": len(robust_trials) / len(trials),
        "fraction_strong_observable": mean_or_zero([1.0 if t["strong_observable"] else 0.0 for t in trials]),
        "fraction_collapsed": len(collapsed_trials) / len(trials),
        "fraction_loss_gt_25pct": mean_or_zero([1.0 if float(t["geometry_loss_fraction"]) > 0.25 else 0.0 for t in trials]),
        "fraction_loss_gt_50pct": mean_or_zero([1.0 if float(t["geometry_loss_fraction"]) > 0.50 else 0.0 for t in trials]),
    }

    geometry_summary = {
        "best_geometry_trial": max(trials, key=lambda t: float(t["geometry_adjusted_dtoi"])),
        "worst_geometry_trial": min(trials, key=lambda t: float(t["geometry_adjusted_dtoi"])),
        "robustness_by_direction": summarize_by(trials, "placement_direction"),
        "robustness_by_geometry_class": summarize_by(trials, "geometry_class"),
        "robustness_by_offset": summarize_by(trials, "offset_m"),
        "robustness_by_duration": summarize_by(trials, "duration_s"),
        "interpretation": "Placement geometry is a conservative proxy, not surveyed station geometry.",
    }

    interpretation = [
        "DTOI placement robustness is evaluated with a conservative geometry proxy.",
        "The current orbit bridge varies displacement magnitude; direction-dependent effects are proxy adjustments.",
        "Robust cases indicate diagnostic resilience across placement assumptions.",
        "Weak or collapsed cases identify geometry-sensitive observability regimes.",
        "This does not prove localization accuracy or real deployment readiness.",
    ]

    claim_status = {
        "diagnostic_only_not_OTA": True,
        "geometry_model_is_proxy_not_surveyed_station_validation": True,
        "no_localization_accuracy_claim": True,
        "no_real_satellite_capture_claim": True,
        "no_HIL_claim": True,
        "not_deployment_ready": True,
    }

    conservative_notes = [
        "not OTA validation",
        "not surveyed station placement validation",
        "not localization accuracy evidence",
        "not hardware deployment evidence",
        "not deployment-ready",
    ]

    if not suspicious_flags and aggregate_metrics["fraction_robust_observable"] >= 0.25:
        recommended_next_action = "Proceed to C23 consolidated research evidence table with geometry and oscillator caveats."
    else:
        recommended_next_action = "Expand geometry proxy model before consolidation; robustness is weak or flags are present."

    summary = {
        "metadata": {
            "generated_by": "research_geometry_placement_robustness.py",
            "phase": "C22",
            "full": args.full,
            "max_trials": args.max_trials,
            "seed": args.seed,
            "geometry_model": "conservative proxy only; not surveyed station placement validation",
        },
        "grid_dimensions": {
            "carriers_hz": carriers_hz,
            "offsets_m": offsets_m,
            "durations_s": durations_s,
            "placement_directions": directions,
            "geometry_classes": geometry_classes,
        },
        "completed_trials": len(trials),
        "aggregate_metrics": aggregate_metrics,
        "geometry_summary": geometry_summary,
        "suspicious_flags": suspicious_flags,
        "interpretation": interpretation,
        "claim_status": claim_status,
        "conservative_notes": conservative_notes,
        "recommended_next_action": recommended_next_action,
    }

    json_path = out_dir / "geometry_placement_summary.json"
    csv_path = out_dir / "geometry_placement_trials.csv"
    md_path = out_dir / "geometry_placement_summary.md"

    json_path.write_text(json.dumps(summary, indent=2))

    fieldnames = [
        "carrier_hz",
        "offset_m",
        "duration_s",
        "seed",
        "placement_direction",
        "geometry_class",
        "geometry_factor",
        "base_dtoi",
        "geometry_adjusted_dtoi",
        "naive_snr",
        "energy_removed_by_nuisance",
        "geometry_loss_fraction",
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
        "# C22 Geometry / Station Placement Robustness",
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
        "## Geometry Summary",
        "",
        f"- best_geometry_adjusted_dtoi: {geometry_summary['best_geometry_trial']['geometry_adjusted_dtoi']}",
        f"- worst_geometry_adjusted_dtoi: {geometry_summary['worst_geometry_trial']['geometry_adjusted_dtoi']}",
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
        "This is a geometry proxy only and not surveyed station placement validation.",
        "This does not create OTA, HIL, real satellite capture, hardware deployment, or localization accuracy evidence.",
    ])
    md_path.write_text("\n".join(md_lines) + "\n")

    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Completed trials: {len(trials)}")
    print(f"Recommended next action: {recommended_next_action}")


if __name__ == "__main__":
    main()
