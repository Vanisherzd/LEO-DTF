#!/usr/bin/env python3
"""
C3-lite: lightweight multi-satellite geometry DTOI observability study.

This is a deterministic synthetic DTOI diagnostic, not an orbit/TLE simulator.
It evaluates how multiple satellite-like curvature signatures improve
Doppler-time separability after projecting out CFO/drift nuisance [1, t].
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np


SIGMA_F_HZ = 1.0
VALID_STATUS = ("unobservable", "weak", "moderate", "strong")


def classify(dtoi: float) -> str:
    if dtoi < 1.0:
        return "unobservable"
    if dtoi < 3.0:
        return "weak"
    if dtoi < 10.0:
        return "moderate"
    return "strong"


def project_out_nuisance(diff: np.ndarray, t_rel: np.ndarray) -> tuple[np.ndarray, float]:
    """Remove affine nuisance [1, t] from a Doppler-difference vector."""
    diff = np.asarray(diff, dtype=float)
    t_rel = np.asarray(t_rel, dtype=float)

    design = np.column_stack([np.ones_like(t_rel), t_rel])
    coeff, *_ = np.linalg.lstsq(design, diff, rcond=None)
    projected = diff - design @ coeff

    total_energy = float(np.dot(diff, diff))
    kept_energy = float(np.dot(projected, projected))
    energy_removed = 0.0 if total_energy <= 0 else 1.0 - kept_energy / total_energy
    return projected, energy_removed


def dtoi_from_diff(diff: np.ndarray, t_rel: np.ndarray) -> tuple[float, float, float, np.ndarray]:
    """Return DTOI, naive SNR, energy removed, and projected residual."""
    projected, energy_removed = project_out_nuisance(diff, t_rel)
    dtoi = float(np.sqrt(np.mean(projected ** 2)) / SIGMA_F_HZ)
    naive_snr = float(np.sqrt(np.mean(np.asarray(diff) ** 2)) / SIGMA_F_HZ)
    return dtoi, naive_snr, energy_removed, projected


def satellite_shape(t_rel: np.ndarray, sat_idx: int, geometry: str) -> np.ndarray:
    """Synthetic nonlinear Doppler curvature signature for one satellite."""
    t = t_rel / max(float(t_rel[-1]), 1.0)

    if geometry == "similar_tracks":
        omega = 2.0 * np.pi * (1.0 + 0.02 * sat_idx)
        phase = 0.15 * sat_idx
        gain = 1.0 + 0.03 * sat_idx
    elif geometry == "diverse_tracks":
        omega = 2.0 * np.pi * (1.0 + 0.22 * sat_idx)
        phase = sat_idx * np.pi / 2.0
        gain = 1.0 + 0.28 * sat_idx
    else:
        raise ValueError(f"unknown geometry={geometry}")

    nonlinear = (
        np.sin(omega * t + phase)
        + 0.45 * np.cos(2.0 * omega * t + 0.4 * phase)
        + 0.25 * np.sin(0.5 * omega * t + 0.7 * phase)
        + 0.12 * (t - 0.5) ** 2
    )

    # Include affine terms so nuisance projection is exercised.
    nuisance = 8.0 + 0.015 * t_rel
    return nuisance + gain * nonlinear


def doppler_difference(
    carrier_hz: float,
    offset_m: float,
    t_rel: np.ndarray,
    sat_idx: int,
    geometry: str,
) -> np.ndarray:
    """Synthetic Doppler difference between reference and offset terminal."""
    carrier_scale = carrier_hz / 2.4e9
    offset_scale = offset_m / 1000.0

    # Calibrated for a lightweight diagnostic: high carrier + large offset +
    # diverse geometry can reach useful DTOI, while lower settings remain weak.
    amplitude_hz = 1.05 * carrier_scale * offset_scale

    return amplitude_hz * satellite_shape(t_rel, sat_idx, geometry)


def evaluate_config(num_satellites: int, carrier_hz: float, offset_m: float, geometry: str) -> dict:
    duration_s = 600.0
    packet_interval_s = 10.0
    t_rel = np.arange(0.0, duration_s + 1e-9, packet_interval_s)

    per_sat_dtoi = []
    per_sat_naive = []
    per_sat_removed = []
    per_sat_projected = []
    per_sat_diff = []
    per_sat_time = []

    for sat_idx in range(num_satellites):
        diff = doppler_difference(carrier_hz, offset_m, t_rel, sat_idx, geometry)
        dtoi, naive, removed, projected = dtoi_from_diff(diff, t_rel)

        per_sat_dtoi.append(dtoi)
        per_sat_naive.append(naive)
        per_sat_removed.append(removed)
        per_sat_projected.append(projected)
        per_sat_diff.append(diff)

        # Treat each satellite as a separate measurement block. A global
        # affine nuisance is fitted across the concatenated stream.
        per_sat_time.append(t_rel + sat_idx * (duration_s + 120.0))

    concat_diff = np.concatenate(per_sat_diff)
    concat_time = np.concatenate(per_sat_time)

    dtoi_global, naive_global, removed_global, _ = dtoi_from_diff(concat_diff, concat_time)

    concat_projected = np.concatenate(per_sat_projected)
    dtoi_per_sat = float(np.sqrt(np.mean(concat_projected ** 2)) / SIGMA_F_HZ)

    return {
        "num_satellites": num_satellites,
        "carrier_hz": carrier_hz,
        "offset_m": offset_m,
        "geometry": geometry,
        "total_samples": int(len(concat_diff)),
        "naive_snr": naive_global,
        "dtoi_global_nuisance": dtoi_global,
        "dtoi_per_satellite_nuisance": dtoi_per_sat,
        "gain_global_vs_single": np.nan,
        "gain_per_satellite_vs_single": np.nan,
        "energy_removed_global": removed_global,
        "energy_removed_per_satellite": float(np.mean(per_sat_removed)),
        "observability_status_global": classify(dtoi_global),
        "observability_status_per_satellite": classify(dtoi_per_sat),
        "per_satellite_dtoi": json.dumps([round(float(x), 6) for x in per_sat_dtoi]),
    }


def run(quick: bool, seed: int) -> None:
    np.random.seed(seed)

    if quick:
        num_satellites_list = [1, 2, 4]
        carrier_list = [915e6, 2.4e9]
        offset_list = [100.0, 1000.0]
        geometry_list = ["similar_tracks", "diverse_tracks"]
    else:
        num_satellites_list = [1, 2, 4, 8]
        carrier_list = [137e6, 433e6, 915e6, 1.6e9, 2.4e9]
        offset_list = [100.0, 500.0, 1000.0, 5000.0]
        geometry_list = ["similar_tracks", "diverse_tracks"]

    rows = []

    for geometry in geometry_list:
        for carrier_hz in carrier_list:
            for offset_m in offset_list:
                baseline = None
                for num_satellites in num_satellites_list:
                    row = evaluate_config(num_satellites, carrier_hz, offset_m, geometry)

                    if num_satellites == 1:
                        baseline = row

                    if baseline is not None:
                        base_global = float(baseline["dtoi_global_nuisance"])
                        base_per_sat = float(baseline["dtoi_per_satellite_nuisance"])
                        row["gain_global_vs_single"] = (
                            float(row["dtoi_global_nuisance"]) / base_global
                            if base_global > 0
                            else np.nan
                        )
                        row["gain_per_satellite_vs_single"] = (
                            float(row["dtoi_per_satellite_nuisance"]) / base_per_sat
                            if base_per_sat > 0
                            else np.nan
                        )

                    rows.append(row)

    outdir = Path("experiments/results/research_multisat_geometry")
    outdir.mkdir(parents=True, exist_ok=True)

    csv_path = outdir / "multisat_geometry_trials.csv"
    fieldnames = list(rows[0].keys())
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    def count_status(key: str, status: str) -> int:
        return sum(1 for row in rows if row[key] == status)

    best_global = max(rows, key=lambda row: float(row["dtoi_global_nuisance"]))
    best_per_sat = max(rows, key=lambda row: float(row["dtoi_per_satellite_nuisance"]))

    summary = {
        "metadata": {
            "quick": quick,
            "seed": seed,
            "sigma_f_hz": SIGMA_F_HZ,
            "total_rows": len(rows),
            "model": "deterministic synthetic multi-satellite curvature DTOI diagnostic",
        },
        "summary": {
            "count_global_unobservable": count_status("observability_status_global", "unobservable"),
            "count_global_weak": count_status("observability_status_global", "weak"),
            "count_global_moderate": count_status("observability_status_global", "moderate"),
            "count_global_strong": count_status("observability_status_global", "strong"),
            "count_per_satellite_unobservable": count_status(
                "observability_status_per_satellite", "unobservable"
            ),
            "count_per_satellite_weak": count_status("observability_status_per_satellite", "weak"),
            "count_per_satellite_moderate": count_status(
                "observability_status_per_satellite", "moderate"
            ),
            "count_per_satellite_strong": count_status("observability_status_per_satellite", "strong"),
            "best_global_config": best_global,
            "best_per_satellite_config": best_per_sat,
        },
        "key_findings": [
            "Multi-satellite geometry can improve DTOI when signatures are diverse.",
            "Per-satellite nuisance projection is more conservative than a shared global nuisance.",
            "Carrier frequency and spatial offset remain dominant observability drivers.",
            "This is a synthetic diagnostic only, not real satellite, TLE, estimator, or OTA validation.",
        ],
    }

    json_path = outdir / "multisat_geometry_summary.json"
    json_path.write_text(json.dumps(summary, indent=2))

    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")
    print(f"Rows: {len(rows)}")
    print(
        "Best global:",
        best_global["num_satellites"],
        best_global["carrier_hz"],
        best_global["offset_m"],
        best_global["geometry"],
        best_global["dtoi_global_nuisance"],
    )
    print(
        "Best per-satellite:",
        best_per_sat["num_satellites"],
        best_per_sat["carrier_hz"],
        best_per_sat["offset_m"],
        best_per_sat["geometry"],
        best_per_sat["dtoi_per_satellite_nuisance"],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    run(quick=args.quick, seed=args.seed)


if __name__ == "__main__":
    main()
