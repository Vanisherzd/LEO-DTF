#!/usr/bin/env python3
"""
ROI and Grid-Resolution Sensitivity Study
==========================================
Sweeps bounded ROI size and grid step to characterize estimator behavior
across a range of synthetic configurations.

Outputs:
  experiments/results/research_roi_grid/roi_grid_trials.csv
  experiments/results/research_roi_grid/roi_grid_summary.json
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

# Fixed scenario
LAT0_DEG = 40.0
LON0_DEG = -105.0
ALT0_KM = 1.5
CARRIER_FREQ_HZ = 1.6e9
NUM_PACKETS = 20
TOTAL_TIME_S = 600.0
TRUE_OFFSET_EN = np.array([100.0, 50.0])

# Nuisance truth
B0_TRUE = 50.0
B1_TRUE = 0.1
DELTA_T_TRUE = 0.001

# Noise model
SIGMA_F = 1.0
SIGMA_TAU = 1e-3

# Default grid settings
DELTA_T_MIN = -0.01
DELTA_T_MAX = 0.01
DELTA_T_N = 21
B0_PRIOR = (0.0, 100.0)
B1_PRIOR = (0.0, 1.0)
DELTA_T_PRIOR = (0.0, 0.01)

TLE_LINE1 = "1 25544U 98067A   26155.53033517  .00012622  00000+0  28098-3 0  9994"
TLE_LINE2 = "2 25544  51.6416 246.6182 0006706 302.2584 122.9105 15.50040302433475"


def build_enu_basis(lat_deg, lon_deg):
    lat = np.radians(lat_deg)
    lon = np.radians(lon_deg)
    basis = np.array([
        [-np.sin(lon),  np.cos(lon), 0.0],
        [-np.sin(lat)*np.cos(lon), -np.sin(lat)*np.sin(lon), np.cos(lat)],
        [np.cos(lat)*np.cos(lon),  np.cos(lat)*np.sin(lon),  np.sin(lat)]
    ])
    return basis.T


def run_trial(rng, roi_half_m, grid_step_m, times_s, sat_pos, sat_vel,
              ref_ecef, enu_basis, obs_model):
    from leodtf.estimator_grid_map import estimate_grid_map, compute_hpd_region, build_position_grid

    # Build position grid for this ROI config
    position_grid_en = build_position_grid(
        -roi_half_m, roi_half_m, -roi_half_m, roi_half_m, grid_step_m)
    delta_t_grid = np.linspace(DELTA_T_MIN, DELTA_T_MAX, DELTA_T_N)

    # True position
    true_offset_km = np.array([TRUE_OFFSET_EN[0], TRUE_OFFSET_EN[1], 0.0]) / 1000.0
    ref_true_ecef = ref_ecef + enu_basis @ true_offset_km

    # Generate observations
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
        posterior, map_pos_en, _, _, _ = estimate_grid_map(
            position_grid_en, delta_t_grid, ref_ecef, enu_basis,
            sat_pos, sat_vel, times_s,
            observed_freq, observed_tau,
            CARRIER_FREQ_HZ, SIGMA_F, SIGMA_TAU,
            b0_prior=B0_PRIOR, b1_prior=B1_PRIOR, delta_t_prior=DELTA_T_PRIOR,
        )

        error_e = float(map_pos_en[0] - TRUE_OFFSET_EN[0])
        error_n = float(map_pos_en[1] - TRUE_OFFSET_EN[1])
        error_mag = float(np.hypot(error_e, error_n))

        # Posterior entropy
        eps = 1e-10
        p = posterior + eps
        p = p / p.sum()
        entropy = float(-np.sum(p * np.log(p)))

        # HPD region
        hpd_mask, hpd_mass = compute_hpd_region(posterior, position_grid_en, mass=0.95)
        hpd_cells = int(hpd_mask.sum())

        return {
            'status': 'success',
            'error_e_m': error_e,
            'error_n_m': error_n,
            'error_mag_m': error_mag,
            'posterior_entropy': entropy,
            'hpd_n_cells': hpd_cells,
            'hpd_mass': hpd_mass,
        }
    except Exception as e:
        return {
            'status': f'error: {e}',
            'error_e_m': np.nan, 'error_n_m': np.nan,
            'error_mag_m': np.nan, 'posterior_entropy': np.nan,
            'hpd_n_cells': 0, 'hpd_mass': np.nan,
        }


def main():
    parser = argparse.ArgumentParser(description='ROI and grid-resolution sensitivity')
    parser.add_argument('--trials', '-N', type=int, default=3)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--quick', action='store_true',
                        help='Use 4 configs and 1 trial each (smoke test)')
    parser.add_argument('--output-dir', default='experiments/results/research_roi_grid')
    args = parser.parse_args()

    try:
        from leodtf.orbit_propagation import propagate_orbit
        from leodtf.frame_transform import geodetic_to_ecef
        from leodtf.observation_model import ObservationModel
        print("✓ Modules imported")
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return 1

    # ROI configs: (roi_half_m, grid_step_m)
    if args.quick:
        roi_configs = [
            (200.0, 20.0),
            (500.0, 50.0),
            (1000.0, 100.0),
            (2000.0, 100.0),
        ]
    else:
        roi_configs = [
            (100.0, 10.0), (100.0, 20.0),
            (200.0, 10.0), (200.0, 20.0), (200.0, 50.0),
            (500.0, 20.0), (500.0, 50.0), (500.0, 100.0),
            (1000.0, 50.0), (1000.0, 100.0),
            (2000.0, 100.0),
        ]

    # Pre-compute fixed satellite trajectory
    ref_time = datetime(2026, 6, 4, 12, 0, 0)
    times_s = np.linspace(0, TOTAL_TIME_S, NUM_PACKETS)
    times_dt = [ref_time + timedelta(seconds=t) for t in times_s]
    sat_pos, sat_vel = propagate_orbit(TLE_LINE1, TLE_LINE2, times_dt)
    ref_ecef = np.array(geodetic_to_ecef(LAT0_DEG, LON0_DEG, ALT0_KM))
    enu_basis = build_enu_basis(LAT0_DEG, LON0_DEG)
    obs_model = ObservationModel(ref_ecef, carrier_freq_hz=CARRIER_FREQ_HZ)

    os.makedirs(args.output_dir, exist_ok=True)

    all_results = []
    t0 = time.time()

    for roi_half, grid_step in roi_configs:
        rng = np.random.default_rng(args.seed)

        config_results = []
        for trial in range(1, args.trials + 1):
            r = run_trial(rng, roi_half, grid_step, times_s, sat_pos, sat_vel,
                          ref_ecef, enu_basis, obs_model)
            r['roi_half_m'] = roi_half
            r['step_m'] = grid_step
            r['trial'] = trial
            config_results.append(r)
            all_results.append(r)

        successes = [x for x in config_results if x['status'] == 'success']
        if successes:
            mean_err = float(np.mean([x['error_mag_m'] for x in successes]))
            print(f"  roi={roi_half:5.0f}m  step={grid_step:4.0f}m  "
                  f"err={mean_err:.1f}m  [{len(successes)}/{len(config_results)} ok]")
        else:
            print(f"  roi={roi_half:5.0f}m  step={grid_step:4.0f}m  [ALL FAILED]")

    elapsed = time.time() - t0

    # Write CSV
    csv_path = os.path.join(args.output_dir, 'roi_grid_trials.csv')
    fieldnames = ['roi_half_m', 'step_m', 'trial', 'status',
                  'error_e_m', 'error_n_m', 'error_mag_m',
                  'posterior_entropy', 'hpd_n_cells', 'hpd_mass']
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_results:
            writer.writerow({k: r.get(k, '') for k in fieldnames})

    # Write summary
    successes = [x for x in all_results if x['status'] == 'success']

    def agg(key):
        vals = [x[key] for x in successes if not np.isnan(x.get(key, np.nan))]
        if not vals:
            return np.nan
        return float(np.mean(vals))

    summary = {
        'experiment': 'research_roi_grid',
        'generated': datetime.now().isoformat(),
        'elapsed_s': round(elapsed, 1),
        'n_configs': len(roi_configs),
        'n_trials': args.trials,
        'n_success': len(successes),
        'configs': [
            {'roi_half_m': r[0], 'step_m': r[1]} for r in roi_configs
        ],
        'mean_error_m': agg('error_mag_m'),
        'median_error_m': float(np.median([x['error_mag_m'] for x in successes])) if successes else np.nan,
        'p90_error_m': float(np.percentile([x['error_mag_m'] for x in successes], 90)) if successes else np.nan,
        'posterior_entropy_mean': agg('posterior_entropy'),
        'hpd_cells_mean': agg('hpd_n_cells'),
        'runtime_s': round(elapsed, 1),
    }

    json_path = os.path.join(args.output_dir, 'roi_grid_summary.json')
    with open(json_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nDone — {elapsed:.1f}s  ({len(successes)}/{len(all_results)} configs ok)")
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())