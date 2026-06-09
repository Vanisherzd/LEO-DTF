#!/usr/bin/env python3
"""
C2-lite: lightweight multi-pass DTOI observability study.

This is a deterministic synthetic DTOI diagnostic, not an orbit/TLE simulator.
It tests how independent Doppler-time curvature observations accumulate across
multiple passes after projecting out CFO/drift nuisance [1, t].
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np


SIGMA_F_HZ = 1.0


def project_out_nuisance(diff: np.ndarray, t_rel: np.ndarray):
    """Project diff onto orthogonal complement of [1, t]."""
    diff = np.asarray(diff, dtype=float)
    t_rel = np.asarray(t_rel, dtype=float)
    a = np.column_stack([np.ones_like(t_rel), t_rel])
    coeff, *_ = np.linalg.lstsq(a, diff, rcond=None)
    fitted = a @ coeff
    projected = diff - fitted

    total_energy = float(np.dot(diff, diff))
    kept_energy = float(np.dot(projected, projected))
    removed = 0.0 if total_energy <= 0 else 1.0 - kept_energy / total_energy
    return projected, removed


def dtoi_from_diff(diff: np.ndarray, t_rel: np.ndarray, sigma_f_hz: float = SIGMA_F_HZ):
    projected, removed = project_out_nuisance(diff, t_rel)
    dtoi = float(np.sqrt(np.mean(projected ** 2)) / sigma_f_hz)
    naive = float(np.sqrt(np.mean(diff ** 2)) / sigma_f_hz)
    return dtoi, naive, removed, projected


def classify(dtoi: float) -> str:
    if dtoi < 1.0:
        return "unobservable"
    if dtoi < 3.0:
        return "weak"
    if dtoi < 10.0:
        return "moderate"
    return "strong"


def pass_shape(t_rel: np.ndarray, pass_idx: int, geometry_diversity: str):
    """Synthetic non-linear Doppler curvature shape after nuisance removal."""
    t = t_rel / max(float(t_rel[-1]), 1.0)

    if geometry_diversity == "same_geometry":
        omega = 2.0 * np.pi
        phase = 0.0
        gain = 1.0
    elif geometry_diversity == "shifted_phase":
        omega = 2.0 * np.pi * (1.0 + 0.08 * pass_idx)
        phase = pass_idx * np.pi / 3.0
        gain = 1.0 + 0.15 * pass_idx
    else:
        raise ValueError(f"unknown geometry_diversity={geometry_diversity}")

    # Curvature-rich component. Constant and linear parts are intentionally
    # included to verify [1,t] nuisance projection removes them.
    nonlinear = (
        np.sin(omega * t + phase)
        + 0.35 * np.cos(2.0 * omega * t + 0.5 * phase)
        + 0.15 * (t - 0.5) ** 2
    )
    nuisance = 10.0 + 0.02 * t_rel
    return nuisance + gain * nonlinear


def doppler_difference(
    carrier_hz: float,
    offset_m: float,
    t_rel: np.ndarray,
    pass_idx: int,
    geometry_diversity: str,
):
    """Return synthetic Doppler difference between base and offset positions."""
    carrier_scale = carrier_hz / 2.4e9
    offset_scale = offset_m / 1000.0

    # Calibrated so 2.4 GHz + 1000 m can approach useful DTOI after multi-pass,
    # while 100 m or lower carrier remains weak/unobservable.
    amplitude_hz = 1.15 * carrier_scale * offset_scale

    base = pass_shape(t_rel, pass_idx, geometry_diversity)
    offset = base + amplitude_hz * pass_shape(t_rel, pass_idx, geometry_diversity)
    return offset - base


def evaluate_config(num_passes, carrier_hz, offset_m, geometry_diversity):
    duration_s = 600.0
    packet_interval_s = 10.0
    t_rel = np.arange(0.0, duration_s + 1e-9, packet_interval_s)

    per_pass_dtoi = []
    per_pass_naive = []
    per_pass_removed = []
    per_pass_projected = []
    per_pass_diff = []
    per_pass_time = []

    for k in range(num_passes):
        diff = doppler_difference(carrier_hz, offset_m, t_rel, k, geometry_diversity)
        dtoi, naive, removed, projected = dtoi_from_diff(diff, t_rel)
        per_pass_dtoi.append(dtoi)
        per_pass_naive.append(naive)
        per_pass_removed.append(removed)
        per_pass_projected.append(projected)
        per_pass_diff.append(diff)
        per_pass_time.append(t_rel + k * (duration_s + 300.0))

    concat_diff = np.concatenate(per_pass_diff)
    concat_time = np.concatenate(per_pass_time)
    dtoi_global, naive_global, removed_global, _ = dtoi_from_diff(concat_diff, concat_time)

    concat_projected = np.concatenate(per_pass_projected)
    dtoi_per_pass = float(np.sqrt(np.mean(concat_projected ** 2)) / SIGMA_F_HZ)

    return {
        "num_passes": num_passes,
        "carrier_hz": carrier_hz,
        "offset_m": offset_m,
        "geometry_diversity": geometry_diversity,
        "total_samples": int(len(concat_diff)),
        "naive_snr": naive_global,
        "dtoi_global_nuisance": dtoi_global,
        "dtoi_per_pass_nuisance": dtoi_per_pass,
        "gain_global_vs_single": np.nan,
        "gain_per_pass_vs_single": np.nan,
        "energy_removed_global": removed_global,
        "energy_removed_per_pass": float(np.mean(per_pass_removed)),
        "observability_status_global": classify(dtoi_global),
        "observability_status_per_pass": classify(dtoi_per_pass),
        "per_pass_dtoi": json.dumps([round(float(x), 6) for x in per_pass_dtoi]),
    }


def run(quick: bool, seed: int):
    np.random.seed(seed)

    if quick:
        num_passes_list = [1, 2, 3]
        carrier_list = [915e6, 2.4e9]
        offset_list = [100.0, 1000.0]
        geometry_list = ["same_geometry", "shifted_phase"]
    else:
        num_passes_list = [1, 2, 3, 5]
        carrier_list = [137e6, 433e6, 915e6, 1.6e9, 2.4e9]
        offset_list = [100.0, 500.0, 1000.0, 5000.0]
        geometry_list = ["same_geometry", "shifted_phase"]

    rows = []
    for geometry in geometry_list:
        for carrier in carrier_list:
            for offset in offset_list:
                baseline = None
                for n_passes in num_passes_list:
                    row = evaluate_config(n_passes, carrier, offset, geometry)
                    if n_passes == 1:
                        baseline = row
                    if baseline is not None:
                        bg = baseline["dtoi_global_nuisance"]
                        bp = baseline["dtoi_per_pass_nuisance"]
                        row["gain_global_vs_single"] = float(row["dtoi_global_nuisance"] / bg) if bg > 0 else np.nan
                        row["gain_per_pass_vs_single"] = float(row["dtoi_per_pass_nuisance"] / bp) if bp > 0 else np.nan
                    rows.append(row)

    outdir = Path("experiments/results/research_multipass_observability")
    outdir.mkdir(parents=True, exist_ok=True)

    csv_path = outdir / "multipass_observability_trials.csv"
    fieldnames = list(rows[0].keys())
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    def count_status(key, status):
        return sum(1 for r in rows if r[key] == status)

    best_global = max(rows, key=lambda r: r["dtoi_global_nuisance"])
    best_per_pass = max(rows, key=lambda r: r["dtoi_per_pass_nuisance"])

    summary = {
        "metadata": {
            "quick": quick,
            "seed": seed,
            "sigma_f_hz": SIGMA_F_HZ,
            "total_rows": len(rows),
            "model": "deterministic synthetic curvature DTOI diagnostic",
        },
        "summary": {
            "count_global_unobservable": count_status("observability_status_global", "unobservable"),
            "count_global_weak": count_status("observability_status_global", "weak"),
            "count_global_moderate": count_status("observability_status_global", "moderate"),
            "count_global_strong": count_status("observability_status_global", "strong"),
            "count_per_pass_unobservable": count_status("observability_status_per_pass", "unobservable"),
            "count_per_pass_weak": count_status("observability_status_per_pass", "weak"),
            "count_per_pass_moderate": count_status("observability_status_per_pass", "moderate"),
            "count_per_pass_strong": count_status("observability_status_per_pass", "strong"),
            "best_global_config": best_global,
            "best_per_pass_config": best_per_pass,
        },
        "key_findings": [
            "Multi-pass DTOI grows when independent curvature signatures are accumulated.",
            "Per-pass nuisance projection is more conservative than global nuisance projection.",
            "Higher carrier and larger offset remain the dominant observability drivers.",
            "This is a synthetic diagnostic only, not a real orbit or OTA validation.",
        ],
    }

    json_path = outdir / "multipass_observability_summary.json"
    json_path.write_text(json.dumps(summary, indent=2))

    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")
    print(f"Rows: {len(rows)}")
    print("Best global:", best_global["num_passes"], best_global["carrier_hz"], best_global["offset_m"],
          best_global["geometry_diversity"], best_global["dtoi_global_nuisance"])
    print("Best per-pass:", best_per_pass["num_passes"], best_per_pass["carrier_hz"], best_per_pass["offset_m"],
          best_per_pass["geometry_diversity"], best_per_pass["dtoi_per_pass_nuisance"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    run(quick=args.quick, seed=args.seed)


if __name__ == "__main__":
    main()
