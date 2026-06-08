#!/usr/bin/env python3
"""
Export Posterior Diagnostic Heatmap
====================================
Run the estimator once on a deterministic synthetic scenario and export
the posterior grid as JSON, CSV, and a PDF heatmap.

Outputs:
    experiments/results/posterior/posterior_grid.json
    experiments/results/posterior/posterior_grid.csv
    paper/figures/posterior_heatmap_diagnostic.pdf

This is a preliminary synthetic diagnostic only. No paper performance
claims are made from these outputs.
"""

import csv
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "experiments" / "results" / "posterior"
OUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / "src"))

# ------------------------------------------------------------------
# Fixed scenario — identical to run_monte_carlo_synthetic.py
# ------------------------------------------------------------------
LAT0_DEG = 40.0
LON0_DEG = -105.0
ALT0_KM = 1.5
CARRIER_FREQ_HZ = 1.6e9
NUM_PACKETS = 20
TOTAL_TIME_S = 600.0
TRUE_OFFSET_EN = np.array([100.0, 50.0])  # meters
B0_TRUE = 50.0   # Hz
B1_TRUE = 0.1    # Hz/s
DELTA_T_TRUE = 0.001  # seconds
SIGMA_F = 1.0    # Hz
SIGMA_TAU = 1e-3  # seconds
E_MIN, E_MAX = -200.0, 200.0
N_MIN, N_MAX = -200.0, 200.0
STEP_M = 20.0
DELTA_T_MIN = -0.01
DELTA_T_MAX = 0.01
DELTA_T_N = 21
B0_PRIOR = (0.0, 100.0)
B1_PRIOR = (0.0, 1.0)
DELTA_T_PRIOR = (0.0, 0.01)


def build_enu_basis(lat_deg, lon_deg):
    lat = np.radians(lat_deg)
    lon = np.radians(lon_deg)
    basis = np.array([
        [-np.sin(lon),  np.cos(lon), 0.0],
        [-np.sin(lat)*np.cos(lon), -np.sin(lat)*np.sin(lon), np.cos(lat)],
        [np.cos(lat)*np.cos(lon),  np.cos(lat)*np.sin(lon),  np.sin(lat)]
    ])
    return basis.T


def run_export():
    from leodtf.tle_loader import parse_tle
    from leodtf.orbit_propagation import propagate_orbit
    from leodtf.frame_transform import geodetic_to_ecef
    from leodtf.observation_model import ObservationModel
    from leodtf.estimator_grid_map import build_position_grid, estimate_grid_map, compute_hpd_region

    # Ground station
    ref_ecef = geodetic_to_ecef(LAT0_DEG, LON0_DEG, ALT0_KM)
    enu_basis = build_enu_basis(LAT0_DEG, LON0_DEG)

    # Build position grid
    position_grid_en = build_position_grid(E_MIN, E_MAX, N_MIN, N_MAX, STEP_M)
    delta_t_grid = np.linspace(DELTA_T_MIN, DELTA_T_MAX, DELTA_T_N)

    # True station position
    true_offset_km = np.array([TRUE_OFFSET_EN[0], TRUE_OFFSET_EN[1], 0.0]) / 1000.0
    true_gs_ecef = ref_ecef + enu_basis @ true_offset_km

    # Use synthetic orbit (same fallback as sim_dataset_gen.py)
    # 400 km, 53 deg — valid TLE that SGP4 can parse
    SYNTH_TLE_LINE1 = "1 99999U 26001A   26155.50000000  .00010000  00000-0  10000-3 0  9994"
    SYNTH_TLE_LINE2 = "2 99999  53.0000 000.0000 0006706 000.0000 000.0000 15.50000000100000"

    # Propagate orbit
    t_start = datetime(2024, 5, 4, 12, 0, 0)
    times_utc = [t_start + timedelta(seconds=i * TOTAL_TIME_S / NUM_PACKETS) for i in range(NUM_PACKETS)]

    from leodtf.orbit_propagation import propagate_orbit
    sat_positions_ecef, sat_velocities_ecef = propagate_orbit(
        SYNTH_TLE_LINE1, SYNTH_TLE_LINE2, times_utc)
    times_s = np.arange(NUM_PACKETS) * (TOTAL_TIME_S / NUM_PACKETS)

    # Observation model
    obs_model = ObservationModel(
        ground_station_ecef=true_gs_ecef,
        carrier_freq_hz=CARRIER_FREQ_HZ,
    )

    # Generate observations at true position
    observed_freq = np.zeros(NUM_PACKETS)
    observed_tau = np.zeros(NUM_PACKETS)
    rng = np.random.default_rng(42)  # deterministic

    for i in range(NUM_PACKETS):
        sat_state = (sat_positions_ecef[i], sat_velocities_ecef[i])
        doppler_hz, propagation_delay_s = obs_model.compute_expected_measurements(sat_state, times_s[i])
        noise_f = rng.normal(0.0, SIGMA_F)
        noise_tau = rng.normal(0.0, SIGMA_TAU)
        observed_freq[i] = doppler_hz + B0_TRUE + B1_TRUE * times_s[i] + noise_f
        observed_tau[i] = times_s[i] + DELTA_T_TRUE + propagation_delay_s + noise_tau

    # Run estimator
    posterior, map_pos_en, best_b0, best_b1, best_delta_t = estimate_grid_map(
        position_grid_en=position_grid_en,
        delta_t_grid=delta_t_grid,
        ground_station_ecef=ref_ecef,
        enu_basis=enu_basis,
        satellite_positions_ecsf=sat_positions_ecef,
        satellite_velocities_ecsf=sat_velocities_ecef,
        nominal_times=times_s,
        observed_freq=observed_freq,
        observed_tau=observed_tau,
        carrier_freq_hz=CARRIER_FREQ_HZ,
        sigma_f=SIGMA_F,
        sigma_tau=SIGMA_TAU,
        b0_prior=B0_PRIOR,
        b1_prior=B1_PRIOR,
        delta_t_prior=DELTA_T_PRIOR,
    )

    # HPD region
    hpd_mask, hpd_mass = compute_hpd_region(posterior, position_grid_en, mass=0.95)

    # Posterior entropy
    eps = 1e-10
    p = posterior + eps
    p = p / p.sum()
    entropy = -np.sum(p * np.log(p))

    # Export JSON
    result = {
        "timestamp": datetime.now().isoformat(),
        "scenario": {
            "lat": LAT0_DEG, "lon": LON0_DEG, "alt_km": ALT0_KM,
            "true_offset_en_m": TRUE_OFFSET_EN.tolist(),
            "b0_true_hz": B0_TRUE,
            "b1_true_hz_s": B1_TRUE,
            "delta_t_true_s": DELTA_T_TRUE,
            "sigma_f_hz": SIGMA_F,
            "sigma_tau_s": SIGMA_TAU,
            "num_packets": NUM_PACKETS,
            "grid_e_m": (E_MIN, E_MAX, STEP_M),
            "grid_n_m": (N_MIN, N_MAX, STEP_M),
        },
        "results": {
            "map_e_m": float(map_pos_en[0]),
            "map_n_m": float(map_pos_en[1]),
            "error_e_m": float(map_pos_en[0] - TRUE_OFFSET_EN[0]),
            "error_n_m": float(map_pos_en[1] - TRUE_OFFSET_EN[1]),
            "error_mag_m": float(np.hypot(map_pos_en[0] - TRUE_OFFSET_EN[0], map_pos_en[1] - TRUE_OFFSET_EN[1])),
            "b0_est_hz": float(best_b0),
            "b1_est_hz_s": float(best_b1),
            "delta_t_est_s": float(best_delta_t),
            "posterior_entropy": float(entropy),
            "hpd_n_cells": int(hpd_mask.sum()),
            "hpd_mass": float(hpd_mass),
        },
    }

    json_path = OUT_DIR / "posterior_grid.json"
    with open(json_path, "w") as f:
        json.dump(result, f, indent=2)

    # Export CSV (grid + posterior probability)
    csv_path = OUT_DIR / "posterior_grid.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["e_m", "n_m", "posterior_prob", "in_hpd"])
        for i in range(len(posterior)):
            writer.writerow([
                position_grid_en[i, 0],
                position_grid_en[i, 1],
                float(posterior[i]),
                bool(hpd_mask[i]),
            ])

    print(f"Posterior JSON: {json_path}")
    print(f"Posterior CSV: {csv_path}")

    # Generate heatmap
    pdf_path = ROOT / "paper" / "figures" / "posterior_heatmap_diagnostic.pdf"
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors

        e_coords = np.arange(E_MIN, E_MAX + STEP_M, STEP_M)
        n_coords = np.arange(N_MIN, N_MAX + STEP_M, STEP_M)
        grid_e, grid_n = np.meshgrid(e_coords, n_coords, indexing="ij")

        # Reshape posterior to 2D grid
        p_grid = posterior.reshape(grid_e.shape)

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # Left: posterior heatmap
        ax = axes[0]
        vmax = p_grid.max()
        im = ax.pcolormesh(grid_e, grid_n, p_grid, cmap="YlOrRd", shading="auto", vmax=vmax)
        ax.scatter(TRUE_OFFSET_EN[0], TRUE_OFFSET_EN[1], c="lime", s=120, marker="*",
                   edgecolors="black", linewidths=1, label="True position", zorder=5)
        ax.scatter(map_pos_en[0], map_pos_en[1], c="cyan", s=100, marker="x",
                   linewidths=2, label=f"MAP ({map_pos_en[0]:.0f}, {map_pos_en[1]:.0f})", zorder=5)

        # Draw HPD contour
        hpd_grid = hpd_mask.reshape(grid_e.shape)
        ax.contour(grid_e, grid_n, hpd_grid.astype(float), levels=[0.5],
                   colors=["blue"], linewidths=[1.5], linestyles=["--"])

        ax.set_xlabel("Easting offset (m)")
        ax.set_ylabel("Northing offset (m)")
        ax.set_title("Posterior probability mass over grid")
        ax.legend(fontsize=8)
        ax.set_aspect("equal", adjustable="box")
        plt.colorbar(im, ax=ax, label="P(x_k | y)")

        # Right: log-posterior (score)
        ax2 = axes[1]
        log_p = np.log(posterior + 1e-12)
        log_grid = log_p.reshape(grid_e.shape)
        vmin_log = log_p.min()
        im2 = ax2.pcolormesh(grid_e, grid_n, log_grid, cmap="viridis", shading="auto")
        ax2.scatter(TRUE_OFFSET_EN[0], TRUE_OFFSET_EN[1], c="red", s=120, marker="*",
                    edgecolors="white", linewidths=1, label="True position", zorder=5)
        ax2.scatter(map_pos_en[0], map_pos_en[1], c="yellow", s=100, marker="x",
                    linewidths=2, label="MAP estimate", zorder=5)
        ax2.set_xlabel("Easting offset (m)")
        ax2.set_ylabel("Northing offset (m)")
        ax2.set_title("Log-posterior score")
        ax2.legend(fontsize=8)
        ax2.set_aspect("equal", adjustable="box")
        plt.colorbar(im2, ax=ax2, label="log P(x_k | y)")

        fig.suptitle(
            "LEO-DTF Posterior Diagnostic (preliminary synthetic)\n"
            f"MAP error: {np.hypot(map_pos_en[0] - TRUE_OFFSET_EN[0], map_pos_en[1] - TRUE_OFFSET_EN[1]):.1f} m  |  "
            f"Entropy: {entropy:.3f}  |  HPD@95%: {hpd_mask.sum()} cells",
            fontsize=9,
        )
        fig.tight_layout()
        fig.savefig(pdf_path, bbox_inches="tight")
        plt.close(fig)
        print(f"Posterior heatmap PDF: {pdf_path}")

    except Exception as e:
        print(f"WARNING: Could not generate PDF heatmap: {e}")
        print("PDF heatmap not generated — this is non-fatal.")

    return result


if __name__ == "__main__":
    result = run_export()
    print("\nDone. Posterior diagnostic exported.")