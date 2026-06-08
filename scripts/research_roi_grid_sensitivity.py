#!/usr/bin/env python3
"""
ROI and Grid-Resolution Sensitivity Study
===========================================
Sweeps bounded ROI size and grid step to characterize estimator behavior
across a range of position-grid configurations.

Outputs:
  experiments/results/research_roi_grid/roi_grid_trials.csv
  experiments/results/research_roi_grid/roi_grid_summary.json

Metrics: mean/median/p90 error, posterior entropy, HPD cells, runtime.

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

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# ------------------------------------------------------------------
# Fixed scenario (same as run_monte_carlo_synthetic.py for consistency)
# ------------------------------------------------------------------
LAT0_DEG = 40.0
LON0_DEG = -105.0
ALT0_KM = 1.5
CARRIER_FREQ_HZ = 1.6e9
NUM_PACKETS = 20
TOTAL_TIME_S = 600.0

TRUE_OFFSET_EN = np.array([100.0, 50.0])   # meters

B0_TRUE = 50.0      # Hz
B1_TRUE = 0.1       # Hz/s
DELTA_T_TRUE = 0.001  # seconds

SIGMA_F = 1.0       # Hz
SIGMA_TAU = 1e-3    # seconds

# Time offset grid (fixed for all configs)
DELTA_T_MIN = -0.01
DELTA_T_MAX = 0.01
DELTA_T_N = 21

# Nuisance priors (fixed)
B0_PRIOR = (0.0, 100.0)
B1_PRIOR = (0.0, 1.0)
DELTA_T_PRIOR = (0.0, 0.01)

# Synthetic TLE (ISS)
TLE_LINE1 = "1 25544U 98067A   26155.53033517  .00012622  00000+0  28098-3 0  9994"
TLE_LINE2 = "2 25544  51.6416 246.6182 0006706 302.2584 122.9105 15.50040302433475"

# ------------------------------------------------------------------
# Configurations to sweep
# ------------------------------------------------------------------
QUICK_CONFIGS = [
    # (roi_half_width_m, step_m)  -- minimal set for smoke test
    (200.0, 20.0),
    (500.0, 50.0),
]

FULL_CONFIGS = [
    # (roi_half_width_m, step_m)
    (100.0, 10.0),
    (100.0, 20.0),
    (200.0, 10.0),
    (200.0, 20.0),
    (200.0, 50.0),
    (500.0, 20.0),
    (500.0, 50.0),
    (500.0, 100.0),
    (1000.0, 50.0),
    (1000.0, 100.0),
    (2000.0, 50.0),
    (2000.0, 100.0),
]


def build_enu_basis(lat_deg, lon_deg):
    """Compute ENU basis at a geodetic location (columns = E, N, Up in ECEF)."""
    lat = np.radians(lat_deg)
    lon = np.radians(lon_deg)
    basis = np.array([
        [-np.sin(lon),  np.cos(lon), 0.0],
        [-np.sin(lat)*np.cos(lon), -np.sin(lat)*np.sin(lon), np.cos(lat)],
        [np.cos(lat)*np.cos(lon),  np.cos(lat)*np.sin(lon),  np.sin(lat)]
    ])
    return basis.T   # 3x3, columns are E, N, Up


def run_trial(rng, times_s, sat_pos, sat_vel, ref_ecef, enu_basis, obs_model,
              position_grid_en, delta_t_grid):
    """
    Run a single estimator trial with the given position grid.
    Returns a dict of scalar results.
    """
    from leodtf.estimator_grid_map import estimate_grid_map, compute_hpd_region

    # True ground station in ECEF (km)
    true_offset_km = np.array([TRUE_OFFSET_EN[0], TRUE_OFFSET_EN[1], 0.0]) / 1000.0
    true_gs_ecef = ref_ecef + enu_basis @ true_offset_km

    # Generate observations using the observation model
    observed_freq = np.zeros(NUM_PACKETS)
    observed_tau = np.zeros(NUM_PACKETS)

    for i in range(NUM_PACKETS):
        sat_state = (sat_pos[i], sat_vel[i])
        doppler_hz, propagation_delay_s = obs_model.compute_expected_measurements(
            sat_state, times_s[i])

        noise_f = rng.normal(0.0, SIGMA_F)
        noise_tau = rng.normal(0.0, SIGMA_TAU)

        observed_freq[i] = doppler_hz + B0_TRUE + B1_TRUE * times_s[i] + noise_f
        observed_tau[i] = times_s[i] + DELTA_T_TRUE + propagation_delay_s + noise_tau

    # Run estimator
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
            b0_prior=B0_PRIOR,
            b1_prior=B1_PRIOR,
            delta_t_prior=DELTA_T_PRIOR,
        )

        # Error metrics
        error_e = float(map_pos_en[0] - TRUE_OFFSET_EN[0])
        error_n = float(map_pos_en[1] - TRUE_OFFSET_EN[1])
        error_mag = float(np.hypot(error_e, error_n))

        # Posterior entropy
        eps = 1e-10
        p = posterior + eps
        p = p / p.sum()
        entropy = float(-np.sum(p * np.log(p)))

        # HPD 95% region
        hpd_mask, hpd_mass = compute_hpd_region(posterior, position_grid_en, mass=0.95)

        return {
            'status': 'success',
            'error_e_m': error_e,
            'error_n_m': error_n,
            'error_mag_m': error_mag,
            'posterior_entropy': entropy,
            'hpd_n_cells': int(hpd_mask.sum()),
            'hpd_mass': float(hpd_mass),
        }
    except Exception as e:
        return {
            'status': f'error: {e}',
            'error_e_m': np.nan,
            'error_n_m': np.nan,
            'error_mag_m': np.nan,
            'posterior_entropy': np.nan,
            'hpd_n_cells': 0,
            'hpd_mass': np.nan,
        }


def run_config(roi_half_m, step_m, trials, rng, times_s, sat_pos, sat_vel,
               ref_ecef, enu_basis, obs_model, delta_t_grid):
    """Run all trials for one ROI/step configuration."""
    from leodtf.estimator_grid_map import build_position_grid

    e_min, e_max = -roi_half_m, roi_half_m
    n_min, n_max = -roi_half_m, roi_half_m

    position_grid_en = build_position_grid(e_min, e_max, n_min, n_max, step_m)

    results = []
    for _ in range(trials):
        r = run_trial(rng, times_s, sat_pos, sat_vel, ref_ecef, enu_basis,
                      obs_model, position_grid_en, delta_t_grid)
        results.append(r)

    errors = [r['error_mag_m'] for r in results if r['status'] == 'success']
    entropies = [r['posterior_entropy'] for r in results if r['status'] == 'success']
    hpd_n = [r['hpd_n_cells'] for r in results if r['status'] == 'success']

    def _mean(x):
        return float(np.mean(x)) if x else np.nan
    def _median(x):
        return float(np.median(x)) if x else np.nan
    def _p90(x):
        return float(np.percentile(x, 90)) if x else np.nan

    summary = {
        'roi_half_width_m': roi_half_m,
        'grid_step_m': step_m,
        'n_trials': len(results),
        'n_success': len(errors),
        'n_fail': len(results) - len(errors),
        'mean_error_m': _mean(errors),
        'median_error_m': _median(errors),
        'p90_error_m': _p90(errors),
        'max_error_m': float(np.max(errors)) if errors else np.nan,
        'posterior_entropy_mean': _mean(entropies),
        'hpd_cells_mean': _mean(hpd_n),
        'grid_cell_count': len(position_grid_en),
    }
    return results, summary


def main():
    parser = argparse.ArgumentParser(description='ROI and grid-resolution sensitivity')
    parser.add_argument('--trials', '-N', type=int, default=3,
                        help='Trials per config (default: 3)')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--quick', action='store_true',
                        help='Use minimal quick config set')
    parser.add_argument('--output-dir',
                        default='experiments/results/research_roi_grid',
                        help='Output directory')
    args = parser.parse_args()

    # Load modules
    try:
        from leodtf.orbit_propagation import propagate_orbit
        from leodtf.frame_transform import geodetic_to_ecef
        from leodtf.observation_model import ObservationModel
        print("✓ Modules imported")
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return 1

    # Build scenario
    ref_time = datetime(2026, 6, 4, 12, 0, 0)
    times_s = np.linspace(0, TOTAL_TIME_S, NUM_PACKETS)
    times_dt = [ref_time + timedelta(seconds=t) for t in times_s]

    sat_pos, sat_vel = propagate_orbit(TLE_LINE1, TLE_LINE2, times_dt)
    ref_ecef = np.array(geodetic_to_ecef(LAT0_DEG, LON0_DEG, ALT0_KM))
    enu_basis = build_enu_basis(LAT0_DEG, LON0_DEG)
    obs_model = ObservationModel(ref_ecef, carrier_freq_hz=CARRIER_FREQ_HZ)
    delta_t_grid = np.linspace(DELTA_T_MIN, DELTA_T_MAX, DELTA_T_N)

    configs = QUICK_CONFIGS if args.quick else FULL_CONFIGS

    rng = np.random.default_rng(args.seed)

    os.makedirs(args.output_dir, exist_ok=True)

    fieldnames = [
        'roi_half_m', 'step_m', 'trial',
        'status', 'error_e_m', 'error_n_m', 'error_mag_m',
        'posterior_entropy', 'hpd_n_cells', 'hpd_mass',
    ]

    csv_path = os.path.join(args.output_dir, 'roi_grid_trials.csv')
    summary_rows = []

    t0 = time.time()

    for roi_half, step in configs:
        results, cfg_summary = run_config(
            roi_half, step, args.trials, rng,
            times_s, sat_pos, sat_vel, ref_ecef, enu_basis, obs_model, delta_t_grid,
        )
        summary_rows.append(cfg_summary)

        with open(csv_path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if f.tell() == 0:
                writer.writeheader()
            for i, r in enumerate(results):
                row = {
                    'roi_half_m': roi_half, 'step_m': step, 'trial': i + 1,
                    'status': r['status'],
                    'error_e_m': r['error_e_m'],
                    'error_n_m': r['error_n_m'],
                    'error_mag_m': r['error_mag_m'],
                    'posterior_entropy': r['posterior_entropy'],
                    'hpd_n_cells': r['hpd_n_cells'],
                    'hpd_mass': r['hpd_mass'],
                }
                writer.writerow(row)

        print(f"  ROI={roi_half:5.0f}m  step={step:4.0f}m  "
              f"→ err={cfg_summary['mean_error_m']:.2f}m  "
              f"entropy={cfg_summary['posterior_entropy_mean']:.3f}  "
              f"cells={cfg_summary['hpd_cells_mean']:.0f}  "
              f"[{len(results)} trials]")

    elapsed = time.time() - t0

    summary_json = {
        'experiment': 'research_roi_grid_sensitivity',
        'generated': datetime.now().isoformat(),
        'elapsed_s': round(elapsed, 1),
        'trials_per_config': args.trials,
        'seed': args.seed,
        'configs': summary_rows,
    }

    json_path = os.path.join(args.output_dir, 'roi_grid_summary.json')
    with open(json_path, 'w') as f:
        json.dump(summary_json, f, indent=2)

    print(f"\nDone — {len(configs)} configs, {elapsed:.1f}s")
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())