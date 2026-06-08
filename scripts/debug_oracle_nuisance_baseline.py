#!/usr/bin/env python3
"""
Oracle Nuisance Baseline Diagnostic
=====================================
Runs the estimator with nuisance parameters fixed to their true values.
If the oracle reduces the 111.8m error floor, the issue is nuisance fitting;
if not, the issue is fundamental identifiability/geometry.
"""

import sys, os, json, csv
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--trials', type=int, default=3)
    parser.add_argument('--output-dir', default='experiments/results/debug_oracle_nuisance')
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    rng = np.random.default_rng(args.seed)

    from leodtf.frame_transform import geodetic_to_ecef
    from leodtf.orbit_propagation import propagate_orbit
    from leodtf.observation_model import ObservationModel
    from leodtf.estimator_grid_map import estimate_grid_map, score_candidate

    # Standard scenario
    LAT0_DEG, LON0_DEG, ALT0_KM = 40.0, -105.0, 1.5
    TRUE_OFFSET_EN = np.array([100.0, 50.0])
    E_MIN, E_MAX = -200.0, 200.0
    N_MIN, N_MAX = -200.0, 200.0
    STEP_M = 20.0
    CARRIER_FREQ_HZ = 1.6e9
    B0_TRUE, B1_TRUE, DELTA_T_TRUE = 50.0, 0.1, 0.001
    SIGMA_F, SIGMA_TAU = 1.0, 1e-3
    NUM_PACKETS, TOTAL_TIME_S = 20, 600.0

    ref_ecef = np.array(geodetic_to_ecef(LAT0_DEG, LON0_DEG, ALT0_KM))
    lat_r, lon_r = np.radians(LAT0_DEG), np.radians(LON0_DEG)
    slat = np.sin(lat_r)
    clat = np.cos(lat_r)
    slon = np.sin(lon_r)
    clon = np.cos(lon_r)
    enu_basis = np.column_stack([
        np.array([-slon, clon, 0.0]),
        np.array([-slat*clon, -slat*slon, clat]),
        np.array([clat*clon, clat*slon, slat]),
    ])

    true_en = TRUE_OFFSET_EN.copy()
    e_vals = np.arange(E_MIN, E_MAX + STEP_M / 2, STEP_M)
    n_vals = np.arange(N_MIN, N_MAX + STEP_M / 2, STEP_M)
    position_grid_en = np.stack([
        np.repeat(e_vals, len(n_vals)),
        np.tile(n_vals, len(e_vals)),
    ], axis=1)
    delta_t_grid = np.linspace(-0.01, 0.01, 21)

    # Orbit
    ref_time = datetime(2026, 6, 4, 12, 0, 0)
    times_s = np.linspace(0, TOTAL_TIME_S, NUM_PACKETS)
    times_dt = [ref_time + timedelta(seconds=t) for t in times_s]
    line1 = "1 25544U 98067A   26155.53033517  .00012622  00000+0  28098-3 0  9994"
    line2 = "2 25544  51.6416 246.6182 0006706 302.2584 122.9105 15.50040302433475"
    sat_pos, sat_vel = propagate_orbit(line1, line2, times_dt)

    rows = []
    for trial in range(args.trials):
        r_trial = np.random.default_rng(args.seed + trial)

        # True position
        true_offset_km = np.array([true_en[0], true_en[1], 0.0]) / 1000.0
        true_gs_ecef = ref_ecef + enu_basis @ true_offset_km

        obs_true = ObservationModel(true_gs_ecef, carrier_freq_hz=CARRIER_FREQ_HZ)
        observed_freq = np.zeros(NUM_PACKETS)
        observed_tau = np.zeros(NUM_PACKETS)
        for i in range(NUM_PACKETS):
            d, p = obs_true.compute_expected_measurements((sat_pos[i], sat_vel[i]), times_s[i])
            observed_freq[i] = d + B0_TRUE + B1_TRUE * times_s[i] + r_trial.normal(0, SIGMA_F)
            observed_tau[i] = times_s[i] + DELTA_T_TRUE + p + r_trial.normal(0, SIGMA_TAU)

        # Normal estimator
        posterior, map_pos_en, best_b0, best_b1, best_dt = estimate_grid_map(
            position_grid_en=position_grid_en,
            delta_t_grid=delta_t_grid,
            ground_station_ecef=ref_ecef,
            enu_basis=enu_basis,
            satellite_positions_ecsf=sat_pos,
            satellite_velocities_ecsf=sat_vel,
            nominal_times=times_s,
            observed_freq=observed_freq,
            observed_tau=observed_tau,
            carrier_freq_hz=CARRIER_FREQ_HZ,
            sigma_f=SIGMA_F,
            sigma_tau=SIGMA_TAU,
            b0_prior=(0.0, 100.0), b1_prior=(0.0, 1.0), delta_t_prior=(0.0, 0.01),
        )

        # Oracle: score at true position with true nuisance
        oracle_score, _, _ = score_candidate(
            true_en, DELTA_T_TRUE, ref_ecef, enu_basis,
            sat_pos, sat_vel, times_s, observed_freq, observed_tau,
            CARRIER_FREQ_HZ, SIGMA_F, SIGMA_TAU,
            (B0_TRUE, 1e-6), (B1_TRUE, 1e-6), (DELTA_T_TRUE, 1e-6),
        )
        oracle_map_score, _, _ = score_candidate(
            true_en, DELTA_T_TRUE, ref_ecef, enu_basis,
            sat_pos, sat_vel, times_s, observed_freq, observed_tau,
            CARRIER_FREQ_HZ, SIGMA_F, SIGMA_TAU,
            (0.0, 100.0), (0.0, 1.0), (0.0, 0.01),
        )

        rows.append({
            'trial': trial,
            'normal_map_error_m': float(np.linalg.norm(map_pos_en - true_en)),
            'normal_map_east_m': float(map_pos_en[0]),
            'normal_map_north_m': float(map_pos_en[1]),
            'normal_b0': float(best_b0),
            'normal_b1': float(best_b1),
            'normal_delta_t': float(best_dt),
            'oracle_score': float(oracle_score),
            'oracle_map_score': float(oracle_map_score),
            'oracle_error_m': 0.0,  # at true position by definition
        })

    csv_path = os.path.join(args.output_dir, 'oracle_nuisance_trials.csv')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        'trials': args.trials,
        'normal_map_error_mean': float(np.mean([r['normal_map_error_m'] for r in rows])),
        'normal_map_error_std': float(np.std([r['normal_map_error_m'] for r in rows])),
        'oracle_score_mean': float(np.mean([r['oracle_score'] for r in rows])),
        'oracle_map_score_mean': float(np.mean([r['oracle_map_score'] for r in rows])),
        'interpretation': (
            'If oracle_score >> normal error: geometry/identifiability issue. '
            'If oracle_score << normal error: nuisance fitting issue. '
            'oracle_score ~ oracle_map_score: no nuisance fitting issue.'
        ),
    }
    json_path = os.path.join(args.output_dir, 'oracle_nuisance_baseline.json')
    with open(json_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"Oracle baseline: normal error={summary['normal_map_error_mean']:.2f}m, oracle_score={summary['oracle_score_mean']:.4f}")
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())