#!/usr/bin/env python3
"""
Doppler-Time Observability Index (DTOI) Derivation
==================================================
Defines DTOI as a nuisance-aware separability score that projects out
CFO (b0) and drift (b1) before computing separability.

DTOI(i, j) = || P_perp (g_i - g_j) ||_2 / (sigma_f * sqrt(N))

where P_perp = I - A (A^T A)^(-1) A^T, A = [1, t]

Key insight:
- Naive separability overestimates localization power because b0/b1
  can absorb constant/linear differences in Doppler.
- DTOI removes the nuisance subspace before measuring separability.
- If DTOI is low but naive separability is high, CFO/drift explains the gap.

Outputs:
  experiments/results/research_dtoi/dtoi_derivation.md
  experiments/results/research_dtoi/dtoi_examples.csv
  experiments/results/research_dtoi/dtoi_summary.json
"""

import sys, os, csv, json, argparse
from datetime import datetime, timedelta
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

C_KM_S = 299792.458
SIGMA_F = 1.0
GS_LAT, GS_LON, GS_ALT = 40.0, -105.0, 0.0


def geodetic_to_ecef(lat, lon, alt_km):
    lat_r = np.radians(lat)
    lon_r = np.radians(lon)
    a, e2 = 6378.137, 2.668959e-3
    N = a / np.sqrt(1 - e2 * np.sin(lat_r)**2)
    x = (N + alt_km) * np.cos(lat_r) * np.cos(lon_r)
    y = (N + alt_km) * np.cos(lat_r) * np.sin(lon_r)
    z = (N * (1 - e2) + alt_km) * np.sin(lat_r)
    return np.array([x, y, z])


def enu_basis_from_geodetic(lat, lon):
    lat_r, lon_r = np.radians(lat), np.radians(lon)
    slat, clat = np.sin(lat_r), np.cos(lat_r)
    slon, clon = np.sin(lon_r), np.cos(lon_r)
    E = np.array([-slon, clon, 0.0])
    N_vec = np.array([-slat*clon, -slat*slon, clat])
    U = np.array([clat*clon, clat*slon, slat])
    return np.column_stack([E, N_vec, U])


def compute_doppler_timeseries(gs_ecef, sat_pos_km, sat_vel_km_s, carrier_hz):
    """Compute Doppler shift time series for ground station at gs_ecef (km)."""
    N = len(sat_pos_km)
    doppler = np.zeros(N)
    for i in range(N):
        los = sat_pos_km[i] - gs_ecef
        rng = np.linalg.norm(los)
        los_unit = los / rng
        range_rate = np.dot(sat_vel_km_s[i], los_unit)
        doppler[i] = -range_rate * carrier_hz / C_KM_S
    return doppler


def project_out_nuisance(diff_vector, t_rel):
    """
    Project out the [1, t] nuisance subspace from a difference vector.

    P_perp = I - A (A^T A)^(-1) A^T
    projected = P_perp @ diff_vector

    Returns projected vector and fraction of energy removed.
    """
    N = len(diff_vector)
    A = np.column_stack([np.ones(N), t_rel])  # [N, 2]

    # Projection matrix
    AT_A_inv = np.linalg.inv(A.T @ A)
    P_perp = np.eye(N) - A @ AT_A_inv @ A.T

    projected = P_perp @ diff_vector

    # Energy removed by projection
    total_energy = np.dot(diff_vector, diff_vector)
    projected_energy = np.dot(projected, projected)
    energy_removed = 1.0 - projected_energy / total_energy if total_energy > 0 else 0.0

    return projected, energy_removed


def compute_dtoi(g_i, g_j, t_rel, sigma_f):
    """
    Compute DTOI between two Doppler time series.

    DTOI = || P_perp (g_i - g_j) ||_2 / (sigma_f * sqrt(N))
    """
    diff = g_i - g_j
    projected, energy_removed = project_out_nuisance(diff, t_rel)

    rms_projected = np.sqrt(np.mean(projected**2))
    dtoi = rms_projected / sigma_f

    return dtoi, energy_removed


def run_dtoi_trial(carrier_hz, duration_s, packet_interval_s, offset_m, direction, seed=42):
    """Compute naive separability vs DTOI for a configuration."""
    rng = np.random.default_rng(seed)

    # Ground stations
    gs_ecef_base = geodetic_to_ecef(GS_LAT, GS_LON, GS_ALT)
    enu_basis = enu_basis_from_geodetic(GS_LAT, GS_LON)

    if direction == 'east':
        offset_vec = np.array([offset_m, 0.0, 0.0])
    elif direction == 'north':
        offset_vec = np.array([0.0, offset_m, 0.0])
    else:
        offset_vec = np.array([offset_m, offset_m, 0.0])

    offset_ecef = enu_basis @ (offset_vec / 1000.0)
    gs_ecef_offset = gs_ecef_base + offset_ecef

    # Satellite trajectory
    from leodtf.orbit_propagation import propagate_orbit

    ref_time = datetime(2026, 6, 4, 12, 0, 0)
    num_packets = max(2, int(duration_s / packet_interval_s))
    times_s = np.linspace(0, duration_s, num_packets)
    times_dt = [ref_time + timedelta(seconds=t) for t in times_s]

    l1 = "1 25544U 98067A   26155.53033517  .00012622  00000+0  28098-3 0  9994"
    l2 = "2 25544  51.6416 246.6182 0006706 302.2584 122.9105 15.50040302433475"
    sat_pos, sat_vel = propagate_orbit(l1, l2, times_dt)

    # Doppler at each position
    doppler_base = compute_doppler_timeseries(gs_ecef_base, sat_pos, sat_vel, carrier_hz)
    doppler_offset = compute_doppler_timeseries(gs_ecef_offset, sat_pos, sat_vel, carrier_hz)

    t_rel = times_s - times_s[0]

    # Naive separation (RMS)
    diff = doppler_offset - doppler_base
    naive_rms = np.sqrt(np.mean(diff**2))
    naive_separation = naive_rms / SIGMA_F

    # Nuisance-projected separation (DTOI)
    dtoi, energy_removed = compute_dtoi(doppler_offset, doppler_base, t_rel, SIGMA_F)

    # Classification
    if dtoi < 1:
        status = 'unobservable'
    elif dtoi < 3:
        status = 'weak'
    elif dtoi < 10:
        status = 'moderate'
    else:
        status = 'strong'

    return dict(
        carrier_hz=carrier_hz,
        duration_s=duration_s,
        packet_interval_s=packet_interval_s,
        offset_m=offset_m,
        offset_direction=direction,
        num_samples=len(times_s),
        naive_separation_over_noise=naive_separation,
        nuisance_projected_dtoi=dtoi,
        percent_energy_removed_by_cfo_drift=energy_removed * 100,
        observability_class=status,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output-dir', default='experiments/results/research_dtoi')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Configurations matching Phase C1 examples
    configs = [
        (137e6, 600, 10, 100, 'east'),
        (915e6, 1800, 10, 1000, 'east'),
        (2.4e9, 1800, 10, 1000, 'east'),
    ]

    rows = []
    for carrier, dur, interval, offset, direction in configs:
        row = run_dtoi_trial(carrier, dur, interval, offset, direction, args.seed)
        rows.append(row)

    # CSV
    csv_path = os.path.join(args.output_dir, 'dtoi_examples.csv')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV: {csv_path} ({len(rows)} rows)")

    # Summary JSON
    summary = {
        'metadata': {
            'seed': args.seed,
            'sigma_f_hz': SIGMA_F,
        },
        'key_findings': {
            'dtoi_less_than_naive': all(
                r['nuisance_projected_dtoi'] <= r['naive_separation_over_noise'] * 1.01
                for r in rows
            ),
            'energy_removed_summary': {
                r['carrier_hz']: round(r['percent_energy_removed_by_cfo_drift'], 2)
                for r in rows
            },
            'most_informative_config': max(rows, key=lambda r: r['nuisance_projected_dtoi'])['carrier_hz'] / 1e6,
            'least_informative_config': min(rows, key=lambda r: r['nuisance_projected_dtoi'])['carrier_hz'] / 1e6,
        },
        'dtoi_interpretation': {
            'definition': 'DTOI = ||P_perp(g_i - g_j)||_2 / (sigma_f * sqrt(N))',
            'P_perp': 'Projects out [1, t] nuisance subspace (b0, b1)',
            'naive_separation': 'Raw RMS of Doppler difference / sigma_f (overestimates)',
            'dtoi': 'Nuisance-projected separability (conservative)',
            'energy_removed': 'Percent of Doppler difference energy absorbed by [1,t] subspace',
        }
    }

    json_path = os.path.join(args.output_dir, 'dtoi_summary.json')
    with open(json_path, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"JSON: {json_path}")

    # Markdown derivation
    md_path = os.path.join(args.output_dir, 'dtoi_derivation.md')
    with open(md_path, 'w') as f:
        f.write("# DTOI Derivation\n\n")
        f.write("## Motivation\n\n")
        f.write("Naive separability S_naive = ||f_D(t;x_i) - f_D(t;x_j)||_2 / (sigma_f sqrt(N))\n")
        f.write("overestimates localization power because CFO (b0) and drift (b1)\n")
        f.write("can absorb constant and linear differences in Doppler.\n\n")

        f.write("## Nuisance-Aware Separability\n\n")
        f.write("Define the nuisance subspace A = [1, t] for N samples:\n\n")
        f.write("```\n")
        f.write("A = [1, t_1; 1, t_2; ...; 1, t_N]\n")
        f.write("```\n\n")
        f.write("Projection matrix:\n\n")
        f.write("```\n")
        f.write("P_perp = I - A (A^T A)^(-1) A^T\n")
        f.write("```\n\n")
        f.write("DTOI(i, j) = || P_perp (g_i - g_j) ||_2 / (sigma_f sqrt(N))\n\n")

        f.write("## Interpretation\n\n")
        f.write("- If energy_removed is HIGH: CFO/drift explains most Doppler difference\n")
        f.write("  → naive separability is misleading\n")
        f.write("- If energy_removed is LOW: geometry is informative even after\n")
        f.write("  nuisance removal → DTOI ≈ naive separability\n\n")

        f.write("## Results\n\n")
        f.write("| Config | Naive S/N | DTOI | Energy Removed | Status |\n")
        f.write("|--------|-----------|------|---------------|--------|\n")
        for r in rows:
            f.write(f"| {r['carrier_hz']/1e6:.0f}MHz {r['duration_s']}s {r['offset_m']}m {r['offset_direction']} "
                    f"| {r['naive_separation_over_noise']:.4f} | {r['nuisance_projected_dtoi']:.4f} "
                    f"| {r['percent_energy_removed_by_cfo_drift']:.1f}% | {r['observability_class']} |\n")

    print(f"MD: {md_path}")

    # Print table
    print(f"\n{'Config':>30} {'Naive':>8} {'DTOI':>8} {'Removed%':>10} {'Status':>12}")
    print("-" * 75)
    for r in rows:
        cfg = f"{r['carrier_hz']/1e6:.0f}MHz {r['duration_s']}s {r['offset_m']}m {r['offset_direction']}"
        print(f"{cfg:>30} {r['naive_separation_over_noise']:>8.4f} {r['nuisance_projected_dtoi']:>8.4f} "
              f"{r['percent_energy_removed_by_cfo_drift']:>10.1f} {r['observability_class']:>12}")

    return 0


if __name__ == '__main__':
    sys.exit(main())