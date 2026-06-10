#!/usr/bin/env python3
"""
C20: Baseline comparison for corrected orbit-driven DTOI.

This is a diagnostic-only comparison against:
- naive Doppler/SNR proxy
- simple matched-filter proxy

It does not use real RF, OTA, HIL, or localization ground truth.
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


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - pos) + xs[hi] * (pos - lo)


def grid_for_args(args: argparse.Namespace) -> tuple[list[float], list[int], list[int], list[int]]:
    if args.full:
        carriers_hz = [137e6, 433e6, 868e6, 915e6, 2.4e9]
        offsets_m = [100, 500, 1000, 5000]
        durations_s = [300, 600, 1200, 1800]
        seeds = [7, 42, 123]
    else:
        carriers_hz = [2.4e9]
        offsets_m = [100, 5000]
        durations_s = [300, 1800]
        seeds = [42]

    if args.seed is not None:
        seeds = [args.seed]

    return carriers_hz, offsets_m, durations_s, seeds


def trial_rank(dtoi: float, naive_snr: float, matched_filter_score: float) -> list[str]:
    scores = {
        "dtoi": dtoi,
        "naive_snr": naive_snr,
        "matched_filter_proxy": matched_filter_score,
    }
    return [name for name, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Run quick grid. This is the default unless --full is used.")
    parser.add_argument("--full", action="store_true", help="Run full comparison grid.")
    parser.add_argument("--max-trials", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    carriers_hz, offsets_m, durations_s, seeds = grid_for_args(args)

    combos: list[tuple[float, int, int, int]] = [
        (carrier, offset, duration, seed)
        for carrier in carriers_hz
        for offset in offsets_m
        for duration in durations_s
        for seed in seeds
    ]
    if args.max_trials is not None:
        combos = combos[: args.max_trials]

    out_dir = ROOT / "experiments" / "results" / "research_baseline_comparison"
    out_dir.mkdir(parents=True, exist_ok=True)

    trials: list[dict[str, Any]] = []
    missing_inputs: list[str] = []

    for i, (carrier_hz, offset_m, duration_s, seed) in enumerate(combos, 1):
        print(
            f"Trial {i}/{len(combos)}: carrier={carrier_hz/1e6:.3f} MHz, "
            f"offset={offset_m} m, duration={duration_s} s, seed={seed}"
        )
        result = run_experiment(
            trace_source="orbit_driven_fallback",
            carrier_hz=carrier_hz,
            offset_m=offset_m,
            duration_s=duration_s,
            seed=seed,
        )

        dtoi = float(result["dtoi"])
        naive_snr = float(result["naive_snr"])
        energy_removed = float(result["energy_removed_by_nuisance"])
        matched_filter_score = naive_snr / (1.0 + energy_removed)

        trial = {
            "carrier_hz": carrier_hz,
            "offset_m": offset_m,
            "duration_s": duration_s,
            "seed": seed,
            "trace_source": result.get("trace_source", "orbit_driven_fallback"),
            "dtoi": dtoi,
            "naive_snr": naive_snr,
            "naive_doppler_score": naive_snr,
            "matched_filter_score": matched_filter_score,
            "energy_removed_by_nuisance": energy_removed,
            "nuisance_penalty": energy_removed,
            "dtoi_to_naive_ratio": dtoi / max(naive_snr, EPS),
            "dtoi_to_matched_proxy_ratio": dtoi / max(matched_filter_score, EPS),
            "observability_status": result.get("observability_status", "unknown"),
            "offset_km_used": result.get("offset_km_used"),
            "differential_mode_confirmed": result.get("differential_mode_confirmed"),
            "fallback_used": result.get("fallback_used"),
        }
        trial["method_rank"] = trial_rank(dtoi, naive_snr, matched_filter_score)
        trials.append(trial)

    if not trials:
        raise RuntimeError("No trials completed")

    naive_values = [float(t["naive_snr"]) for t in trials]
    dtoi_values = [float(t["dtoi"]) for t in trials]
    matched_values = [float(t["matched_filter_score"]) for t in trials]
    energy_values = [float(t["energy_removed_by_nuisance"]) for t in trials]
    naive_q75 = percentile(naive_values, 0.75)

    mismatch_cases = {
        "naive_high_but_dtoi_weak": [
            t for t in trials if float(t["naive_snr"]) >= naive_q75 and float(t["dtoi"]) < 1.0
        ],
        "dtoi_observable_but_naive_not_top_quartile": [
            t for t in trials if float(t["dtoi"]) >= 1.0 and float(t["naive_snr"]) < naive_q75
        ],
        "energy_removed_high_but_dtoi_observable": [
            t for t in trials if float(t["energy_removed_by_nuisance"]) > 0.9 and float(t["dtoi"]) >= 1.0
        ],
    }

    rank_counts = {"dtoi": 0, "naive_snr": 0, "matched_filter_proxy": 0}
    for t in trials:
        rank_counts[t["method_rank"][0]] += 1

    aggregate_metrics = {
        "mean_dtoi": statistics.mean(dtoi_values),
        "mean_naive_snr": statistics.mean(naive_values),
        "mean_matched_filter_proxy": statistics.mean(matched_values),
        "median_dtoi_to_naive_ratio": statistics.median([float(t["dtoi_to_naive_ratio"]) for t in trials]),
        "median_dtoi_to_matched_proxy_ratio": statistics.median([float(t["dtoi_to_matched_proxy_ratio"]) for t in trials]),
        "fraction_dtoi_strong_but_naive_not_top": len(mismatch_cases["dtoi_observable_but_naive_not_top_quartile"]) / len(trials),
        "fraction_naive_high_but_dtoi_weak": len(mismatch_cases["naive_high_but_dtoi_weak"]) / len(trials),
        "fraction_energy_removed_gt_0_9": sum(1 for v in energy_values if v > 0.9) / len(trials),
    }

    best_dtoi_trial = max(trials, key=lambda t: float(t["dtoi"]))
    best_naive_snr_trial = max(trials, key=lambda t: float(t["naive_snr"]))
    best_matched_proxy_trial = max(trials, key=lambda t: float(t["matched_filter_score"]))

    interpretation = [
        "DTOI is a nuisance-aware diagnostic, not just raw Doppler magnitude.",
        "Naive SNR can be high even when nuisance projection removes most energy.",
        "Matched-filter proxy is only a proxy baseline, not a real RF receiver.",
        "This does not prove localization accuracy.",
    ]

    claim_status = {
        "diagnostic_only_not_OTA": True,
        "no_localization_accuracy_claim": True,
        "no_real_satellite_capture_claim": True,
        "no_HIL_claim": True,
        "matched_filter_is_proxy_not_real_receiver": True,
    }

    conservative_notes = [
        "not OTA validation",
        "not localization accuracy evidence",
        "not deployment-ready",
        "matched-filter statistic is a proxy baseline only",
    ]

    mismatch_count = sum(len(v) for v in mismatch_cases.values())
    if mismatch_count > 0:
        recommended_next_action = "Proceed to C21 oscillator/CFO sensitivity sweep; baseline mismatch cases are interpretable."
    else:
        recommended_next_action = "Expand baseline grid or add raw-signal baseline before making method-comparison claims."

    summary = {
        "metadata": {
            "generated_by": "research_baseline_comparison.py",
            "quick_default": not args.full,
            "full": args.full,
            "max_trials": args.max_trials,
            "seed": args.seed,
            "matched_filter_note": "matched_filter_score is a proxy baseline, not a real RF matched filter.",
        },
        "comparison_dimensions": {
            "carriers_hz": carriers_hz,
            "offsets_m": offsets_m,
            "durations_s": durations_s,
            "seeds": seeds,
        },
        "completed_trials": len(trials),
        "best_dtoi_trial": best_dtoi_trial,
        "best_naive_snr_trial": best_naive_snr_trial,
        "best_matched_proxy_trial": best_matched_proxy_trial,
        "aggregate_metrics": aggregate_metrics,
        "method_rank_summary": rank_counts,
        "mismatch_cases": mismatch_cases,
        "interpretation": interpretation,
        "claim_status": claim_status,
        "conservative_notes": conservative_notes,
        "recommended_next_action": recommended_next_action,
        "missing_inputs": missing_inputs,
    }

    json_path = out_dir / "baseline_comparison_summary.json"
    csv_path = out_dir / "baseline_comparison_trials.csv"
    md_path = out_dir / "baseline_comparison_summary.md"

    json_path.write_text(json.dumps(summary, indent=2))

    fieldnames = [
        "carrier_hz",
        "offset_m",
        "duration_s",
        "seed",
        "trace_source",
        "dtoi",
        "naive_snr",
        "naive_doppler_score",
        "matched_filter_score",
        "energy_removed_by_nuisance",
        "nuisance_penalty",
        "dtoi_to_naive_ratio",
        "dtoi_to_matched_proxy_ratio",
        "observability_status",
        "offset_km_used",
        "differential_mode_confirmed",
        "fallback_used",
        "method_rank",
    ]
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for t in trials:
            row = dict(t)
            row["method_rank"] = ">".join(t["method_rank"])
            writer.writerow(row)

    md_lines = [
        "# C20 Baseline Comparison",
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
        "## Method Rank Summary",
        "",
    ])
    for k, v in rank_counts.items():
        md_lines.append(f"- {k}: {v}")
    md_lines.extend([
        "",
        "## Mismatch Cases",
        "",
    ])
    for k, v in mismatch_cases.items():
        md_lines.append(f"- {k}: {len(v)}")
    md_lines.extend([
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
        "This comparison does not create OTA, HIL, real satellite capture, or localization accuracy evidence.",
        "The matched-filter statistic is a proxy baseline only.",
    ])
    md_path.write_text("\n".join(md_lines) + "\n")

    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Completed trials: {len(trials)}")
    print(f"Recommended next action: {recommended_next_action}")


if __name__ == "__main__":
    main()
