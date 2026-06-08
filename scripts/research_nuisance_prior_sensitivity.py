#!/usr/bin/env python3
"""
Nuisance Parameter Prior Sensitivity Study
==========================================
Sweeps CFO, drift, and time-offset prior widths to understand which
nuisance parameter most severely degrades position estimation.

Outputs:
  experiments/results/research_nuisance_prior/nuisance_prior_trials.csv
  experiments/results/research_nuisance_prior/nuisance_prior_summary.json

No paper claims are made from these results.
"""

import sys
import os
import csv
import json
import time
import argparse
from datetime import datetime, timedelta

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

LAT0_DEG = 40.0
LON0_DEG = -105.0
ALT0_KM = 1.5
CARRIER_FREQ_HZ = 1.6e9
NUM_PACKETS = 20
TOTAL_TIME_S = 600.0

TRUE_OFFSET_EN = np.array([100.0, 50.0])

B0_TRUE = 50.0
B1_TRUE = 0.1
DELTA_T_TRUE = 0.001

SIGMA_F = 1.0
SIGMA_TAU = 1e-3

ROI_HALF = 500.0
GRID_STEP = 20.0

DELTA_T_MIN = -0.01
DELTA_T_MAX = 0.01
DELTA_T_N = 21

TLE_LINE1 = "1 25544U 98067A   26155.53033517  .00012622  00000+0  28098-3 0  9994"
TLE_LINE2 = "2 25544  51.6416 246.6182 0006706 302.2584 122.9105 15.50040302433475"

# ------------------------------------------------------------------
# Configurations: (label, b0_prior_std, b1_prior_std, delta_t_prior_std)
# ------------------------------------------------------------------
# Format: (descriptive_label, b0_std_hz, b1_std_hz_per_s, delta_t_std_s)
QUICK_CONFIGS = [
    ('tight',    10.0,   0.01,  1e-4),
    ('nominal',  100.0,  1.0,   1e-3),
    ('loose',    500.0,  5.0,   5e-2),
]

FULL_CONFIGS = [
    # CFO prior sweep (b1, delta_t fixed at nominal)
    ('cfo_tight',    10.0,   1.0,   1e-3),
    ('cfo_nominal',  100.0,  1.0,   1e-3),
    ('cfo_loose',    500.0,  1.0,   1e-3),
    ('cfo_vloose',   1000.0, 1.0,   1e-3),
    # Drift prior sweep (b0, delta_t fixed at nominal)
    ('drift_tight',   100.0,  0.01,  1e-3),
    ('drift_nominal', 100.0,  1.0,   1e-3),
    ('drift_loose',   100.0,  5.0,   1e-3),
    ('drift_vloose',  100.0,  10.0,  1e-3),
    # Time offset prior sweep (b0, b1 fixed at nominal)
    ('tau_tight',    100.0,  1.0,   1e-4),
    ('tau_nominal',  100.0,  1.0,   1e-3),
    ('tau_loose',    100.0,  1.0,   5e-2),
    ('tau_vloose',   100.0,  1.0,   1e-1),
]


def build_enu_basis(lat_deg, lon_deg):
    lat = np.radians(lat_deg)
    lon = np.radians(lon_deg)
    basis = np.array([
        [-np.sin(lon),  np.cos(lon), 0.0],
        [-np.sin(lat)*np.cos(lon), -np.sin(lat)*np.sin(lon), np.cos(lat)],
        [np.cos(lat)*np.cos(lon),  np.cos(lat)*np.sin(lon),  np.sin(lat)]
    ])
    return basis.T


def run_trial(rng, times_s, sat_pos, sat_vel, ref_ecef, enu_basis, obs_model,
              position_grid_en, delta_t_grid, b0_prior, b1_prior, delta_t_prior):
    from leodtf.estimator_grid_map import estimate_grid_map, compute_hpd_region

    true_offset_km = np.array([TRUE_OFFSET_EN[0], TRUE_OFFSET_EN[1], 0.0]) / 1000.0
    ref_true_ecef = ref_ecef + enu_basis @ true_offset_km

    observed_freq = np.zeros(len(times_s))
    observed_tau = np.zeros(len(times_s))

    for i in range(len(times_s)):
        sat_state = (sat_pos[i], sat_vel[i])
        doppler_hz, propagation_delay_s = obs_model.compute_expected_measurements(
            sat_state, times_s[i])
        noise_f = rng.normal(0.0, SIGMA_F)
        noise_tau = rng.normal(0.0, SIGMA_TAU)
        observed_freq[i] = doppler_hz + B0_TRUE + B1_TRUE * times_s[i] + noise_f
        observed_tau[i] = times_s[i] + DELTA_T_TRUE + propagation_delay_s + noise_tau

    try:
        posterior, map_pos_en, best_b0, best_b1, best_delta_t = estimate_grid_map(
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
            b0_prior=b0_prior,
            b1_prior=b1_prior,
            delta_t_prior=delta_t_prior,
        )

        error_e = float(map_pos_en[0] - TRUE_OFFSET_EN[0])
        error_n = float(map_pos_en[1] - TRUE_OFFSET_EN[1])
        error_mag = float(np.hypot(error_e, error_n))

        fitted_cfo_err = float(best_b0 - B0_TRUE)
        fitted_drift_err = float(best_b1 - B1_TRUE)
        fitted_tau_err = float(best_delta_t - DELTA_T_TRUE)

        eps = 1e-10
        p = posterior + eps
        p = p / p.sum()
        entropy = float(-np.sum(p * np.log(p)))

        hpd_mask, hpd_mass = compute_hpd_region(posterior, position_grid_en, mass=0.95)

        return {
            'status': 'success',
            'error_e_m': error_e,
            'error_n_m': error_n,
            'error_mag_m': error_mag,
            'posterior_entropy': entropy,
            'hpd_n_cells': int(hpd_mask.sum()),
            'fitted_cfo_error_hz': fitted_cfo_err,
            'fitted_drift_error_hz_s': fitted_drift_err,
            'fitted_tau_error_s': fitted_tau_err,
        }
    except Exception as e:
        return {
            'status': f'error: {e}',
            'error_e_m': np.nan, 'error_n_m': np.nan,
            'error_mag_m': np.nan, 'posterior_entropy': np.nan,
            'hpd_n_cells': 0,
            'fitted_cfo_error_hz': np.nan,
            'fitted_drift_error_hz_s': np.nan,
            'fitted_tau_error_s': np.nan,
        }


def run_config(label, b0_std, b1_std, tau_std, trials, rng,
               times_s, sat_pos, sat_vel, ref_ecef, enu_basis, obs_model,
               position_grid_en, delta_t_grid):
    b0_prior = (0.0, b0_std)
    b1_prior = (0.0, b1_std)
    delta_t_prior = (0.0, tau_std)

    results = []
    for _ in range(trials):
        r = run_trial(rng, times_s, sat_pos, sat_vel, ref_ecef, enu_basis,
                      obs_model, position_grid_en, delta_t_grid,
                      b0_prior, b1_prior, delta_t_prior)
        results.append(r)

    errors = [r['error_mag_m'] for r in results if r['status'] == 'success']
    entropies = [r['posterior_entropy'] for r in results if r['status'] == 'success']
    hpd_n = [r['hpd_n_cells'] for r in results if r['status'] == 'success']
    cfo_errs = [r['fitted_cfo_error_hz'] for r in results if r['status'] == 'success']
    drift_errs = [r['fitted_drift_error_hz_s'] for r in results if r['status'] == 'success']
    tau_errs = [r['fitted_tau_error_s'] for r in results if r['status'] == 'success']

    def _m(x): return float(np.mean(x)) if x else np.nan

    summary = {
        'label': label,
        'b0_prior_std_hz': b0_std,
        'b1_prior_std_hz_s': b1_std,
        'delta_t_prior_std_s': tau_std,
        'n_trials': len(results),
        'n_success': len(errors),
        'n_fail': len(results) - len(errors),
        'mean_error_m': _m(errors),
        'median_error_m': float(np.median(errors)) if errors else np.nan,
        'p90_error_m': float(np.percentile(errors, 90)) if errors else np.nan,
        'posterior_entropy_mean': _m(entropies),
        'hpd_cells_mean': _m(hpd_n),
        'fitted_cfo_error_mean_hz': _m(cfo_errs),
        'fitted_drift_error_mean_hz_s': _m(drift_errs),
        'fitted_tau_error_mean_s': _m(tau_errs),
    }
    return results, summary


def main():
    parser = argparse.ArgumentParser(description='Nuisance prior sensitivity')
    parser.add_argument('--trials', '-N', type=int, default=3)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--output-dir',
                        default='experiments/results/research_nuisance_prior')
    args = parser.parse_args()

    try:
        from leodtf.orbit_propagation import propagate_orbit
        from leodtf.frame_transform import geodetic_to_ecef
        from leodtf.observation_model import ObservationModel
        from leodtf.estimator_grid_map import build_position_grid
        print("✓ Modules imported")
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return 1

    ref_time = datetime(2026, 6, 4, 12, 0, 0)
    times_s = np.linspace(0, TOTAL_TIME_S, NUM_PACKETS)
    times_dt = [ref_time + timedelta(seconds=t) for t in times_s]

    sat_pos, sat_vel = propagate_orbit(TLE_LINE1, TLE_LINE2, times_dt)
    ref_ecef = np.array(geodetic_to_ecef(LAT0_DEG, LON0_DEG, ALT0_KM))
    enu_basis = build_enu_basis(LAT0_DEG, LON0_DEG)
    obs_model = ObservationModel(ref_ecef, carrier_freq_hz=CARRIER_FREQ_HZ)
    delta_t_grid = np.linspace(DELTA_T_MIN, DELTA_T_MAX, DELTA_T_N)
    position_grid_en = build_position_grid(-ROI_HALF, ROI_HALF, -ROI_HALF, ROI_HALF, GRID_STEP)

    configs = QUICK_CONFIGS if args.quick else FULL_CONFIGS
    rng = np.random.default_rng(args.seed)

    os.makedirs(args.output_dir, exist_ok=True)

    fieldnames = [
        'label', 'b0_std', 'b1_std', 'tau_std', 'trial',
        'status', 'error_e_m', 'error_n_m', 'error_mag_m',
        'posterior_entropy', 'hpd_n_cells',
        'fitted_cfo_error_hz', 'fitted_drift_error_hz_s', 'fitted_tau_error_s',
    ]

    csv_path = os.path.join(args.output_dir, 'nuisance_prior_trials.csv')
    summary_rows = []

    t0 = time.time()

    for label, b0_std, b1_std, tau_std in configs:
        results, cfg_summary = run_config(
            label, b0_std, b1_std, tau_std, args.trials, rng,
            times_s, sat_pos, sat_vel, ref_ecef, enu_basis, obs_model,
            position_grid_en, delta_t_grid,
        )
        summary_rows.append(cfg_summary)

        with open(csv_path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if f.tell() == 0:
                writer.writeheader()
            for i, r in enumerate(results):
                row = {
                    'label': label, 'b0_std': b0_std,
                    'b1_std': b1_std, 'tau_std': tau_std,
                    'trial': i + 1,
                    'status': r['status'],
                    'error_e_m': r['error_e_m'],
                    'error_n_m': r['error_n_m'],
                    'error_mag_m': r['error_mag_m'],
                    'posterior_entropy': r['posterior_entropy'],
                    'hpd_n_cells': r['hpd_n_cells'],
                    'fitted_cfo_error_hz': r['fitted_cfo_error_hz'],
                    'fitted_drift_error_hz_s': r['fitted_drift_error_hz_s'],
                    'fitted_tau_error_s': r['fitted_tau_error_s'],
                }
                writer.writerow(row)

        print(f"  {label:15s}  b0={b0_std:6.1f}  b1={b1_std:5.2f}  tau={tau_std:.0e}  "
              f"→ err={cfg_summary['mean_error_m']:.2f}m  "
              f"entropy={cfg_summary['posterior_entropy_mean']:.3f}  "
              f"cells={cfg_summary['hpd_cells_mean']:.0f}")

    elapsed = time.time() - t0

    summary_json = {
        'experiment': 'research_nuisance_prior_sensitivity',
        'generated': datetime.now().isoformat(),
        'elapsed_s': round(elapsed, 1),
        'trials_per_config': args.trials,
        'seed': args.seed,
        'roi_half_m': ROI_HALF,
        'grid_step_m': GRID_STEP,
        'configs': summary_rows,
    }

    json_path = os.path.join(args.output_dir, 'nuisance_prior_summary.json')
    with open(json_path, 'w') as f:
        json.dump(summary_json, f, indent=2)

    print(f"\nDone — {len(configs)} configs, {elapsed:.1f}s")
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())