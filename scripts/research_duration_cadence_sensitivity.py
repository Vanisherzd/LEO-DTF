#!/usr/bin/env python3
"""
Observation Duration and Cadence Sensitivity Study
===================================================
Sweeps satellite pass duration and packet interval to understand how
observation time and sampling frequency affect DTF discriminability.

Outputs:
  experiments/results/research_duration_cadence/duration_cadence_trials.csv
  experiments/results/research_duration_cadence/duration_cadence_summary.json

Metrics: num_samples, mean/median/p90 error, posterior entropy, HPD cells, runtime.

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

# ------------------------------------------------------------------
# Fixed scenario parameters
# ------------------------------------------------------------------
LAT0_DEG = 40.0
LON0_DEG = -105.0
ALT0_KM = 1.5
CARRIER_FREQ_HZ = 1.6e9

TRUE_OFFSET_EN = np.array([100.0, 50.0])

B0_TRUE = 50.0
B1_TRUE = 0.1
DELTA_T_TRUE = 0.001

SIGMA_F = 1.0
SIGMA_TAU = 1e-3

# Fixed grid (used for all configs to isolate duration/cadence effects)
ROI_HALF = 500.0
GRID_STEP = 20.0

# Time offset grid
DELTA_T_MIN = -0.01
DELTA_T_MAX = 0.01
DELTA_T_N = 21

B0_PRIOR = (0.0, 100.0)
B1_PRIOR = (0.0, 1.0)
DELTA_T_PRIOR = (0.0, 0.01)

TLE_LINE1 = "1 25544U 98067A   26155.53033517  .00012622  00000+0  28098-3 0  9994"
TLE_LINE2 = "2 25544  51.6416 246.6182 0006706 302.2584 122.9105 15.50040302433475"

# ------------------------------------------------------------------
# Configurations
# ------------------------------------------------------------------
QUICK_CONFIGS = [
    # (duration_s, packet_interval_s)
    (60, 10),
    (300, 30),
]

FULL_CONFIGS = [
    # (duration_s, packet_interval_s)
    (60,  60),   # 2 samples
    (60,  30),   # 3 samples
    (60,  10),   # 7 samples
    (120, 60),   # 3 samples
    (120, 30),   # 5 samples
    (120, 10),   # 13 samples
    (300, 60),   # 6 samples
    (300, 30),   # 11 samples
    (300, 10),   # 31 samples
    (600, 60),   # 11 samples
    (600, 30),   # 21 samples
    (600, 10),   # 61 samples
    (900, 60),   # 16 samples
    (900, 30),   # 31 samples
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
              position_grid_en, delta_t_grid):
    from leodtf.estimator_grid_map import estimate_grid_map, compute_hpd_region

    # True ground station in ECEF (km)
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
        posterior, map_pos_en, _, _, _ = estimate_grid_map(
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

        error_e = float(map_pos_en[0] - TRUE_OFFSET_EN[0])
        error_n = float(map_pos_en[1] - TRUE_OFFSET_EN[1])
        error_mag = float(np.hypot(error_e, error_n))

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
        }
    except Exception as e:
        return {
            'status': f'error: {e}',
            'error_e_m': np.nan,
            'error_n_m': np.nan,
            'error_mag_m': np.nan,
            'posterior_entropy': np.nan,
            'hpd_n_cells': 0,
        }


def run_config(duration_s, interval_s, trials, rng, ref_ecef, enu_basis, obs_model,
               position_grid_en, delta_t_grid):
    """Generate observations for this duration/interval, then run trials."""
    # Build full trajectory (use longest duration as upper bound)
    max_duration = 900
    max_times_s = np.linspace(0, max_duration, int(max_duration / 10) + 1)
    ref_time = datetime(2026, 6, 4, 12, 0, 0)
    max_times_dt = [ref_time + timedelta(seconds=t) for t in max_times_s]

    from leodtf.orbit_propagation import propagate_orbit
    from leodtf.frame_transform import geodetic_to_ecef

    sat_pos_full, sat_vel_full = propagate_orbit(TLE_LINE1, TLE_LINE2, max_times_dt)

    # Compute index into full trajectory for the requested duration
    valid_mask = max_times_s <= duration_s
    times_s = max_times_s[valid_mask]
    sat_pos = sat_pos_full[valid_mask]
    sat_vel = sat_vel_full[valid_mask]

    # Apply interval sampling
    if interval_s > 0:
        sampled_idx = np.arange(0, len(times_s), max(1, int(round(interval_s / 10))))
        times_s = times_s[sampled_idx]
        sat_pos = sat_pos[sampled_idx]
        sat_vel = sat_vel[sampled_idx]

    num_samples = len(times_s)

    results = []
    for _ in range(trials):
        r = run_trial(rng, times_s, sat_pos, sat_vel, ref_ecef, enu_basis,
                      obs_model, position_grid_en, delta_t_grid)
        r['num_samples'] = num_samples
        results.append(r)

    errors = [r['error_mag_m'] for r in results if r['status'] == 'success']
    entropies = [r['posterior_entropy'] for r in results if r['status'] == 'success']
    hpd_n = [r['hpd_n_cells'] for r in results if r['status'] == 'success']
    n_samples = [r['num_samples'] for r in results if r['status'] == 'success']

    def _mean(x): return float(np.mean(x)) if x else np.nan
    def _median(x): return float(np.median(x)) if x else np.nan
    def _p90(x): return float(np.percentile(x, 90)) if x else np.nan

    summary = {
        'duration_s': duration_s,
        'packet_interval_s': interval_s,
        'num_samples': int(np.mean(n_samples)) if n_samples else 0,
        'n_trials': len(results),
        'n_success': len(errors),
        'n_fail': len(results) - len(errors),
        'mean_error_m': _mean(errors),
        'median_error_m': _median(errors),
        'p90_error_m': _p90(errors),
        'posterior_entropy_mean': _mean(entropies),
        'hpd_cells_mean': _mean(hpd_n),
    }
    return results, summary


def main():
    parser = argparse.ArgumentParser(description='Duration and cadence sensitivity')
    parser.add_argument('--trials', '-N', type=int, default=3)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--output-dir',
                        default='experiments/results/research_duration_cadence')
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

    # Build base scenario
    ref_ecef = np.array(geodetic_to_ecef(LAT0_DEG, LON0_DEG, ALT0_KM))
    enu_basis = build_enu_basis(LAT0_DEG, LON0_DEG)
    obs_model = ObservationModel(ref_ecef, carrier_freq_hz=CARRIER_FREQ_HZ)
    delta_t_grid = np.linspace(DELTA_T_MIN, DELTA_T_MAX, DELTA_T_N)
    position_grid_en = build_position_grid(-ROI_HALF, ROI_HALF, -ROI_HALF, ROI_HALF, GRID_STEP)

    configs = QUICK_CONFIGS if args.quick else FULL_CONFIGS
    rng = np.random.default_rng(args.seed)

    os.makedirs(args.output_dir, exist_ok=True)

    fieldnames = [
        'duration_s', 'packet_interval_s', 'num_samples', 'trial',
        'status', 'error_e_m', 'error_n_m', 'error_mag_m',
        'posterior_entropy', 'hpd_n_cells',
    ]

    csv_path = os.path.join(args.output_dir, 'duration_cadence_trials.csv')
    summary_rows = []

    t0 = time.time()

    for duration, interval in configs:
        results, cfg_summary = run_config(
            duration, interval, args.trials, rng,
            ref_ecef, enu_basis, obs_model, position_grid_en, delta_t_grid,
        )
        summary_rows.append(cfg_summary)

        with open(csv_path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if f.tell() == 0:
                writer.writeheader()
            for i, r in enumerate(results):
                row = {
                    'duration_s': duration, 'packet_interval_s': interval,
                    'num_samples': r.get('num_samples', 0), 'trial': i + 1,
                    'status': r['status'],
                    'error_e_m': r['error_e_m'],
                    'error_n_m': r['error_n_m'],
                    'error_mag_m': r['error_mag_m'],
                    'posterior_entropy': r['posterior_entropy'],
                    'hpd_n_cells': r['hpd_n_cells'],
                }
                writer.writerow(row)

        print(f"  dur={duration:4d}s  int={interval:3d}s  "
              f"n={cfg_summary['num_samples']:2d}  "
              f"→ err={cfg_summary['mean_error_m']:.2f}m  "
              f"entropy={cfg_summary['posterior_entropy_mean']:.3f}  "
              f"cells={cfg_summary['hpd_cells_mean']:.0f}")

    elapsed = time.time() - t0

    summary_json = {
        'experiment': 'research_duration_cadence_sensitivity',
        'generated': datetime.now().isoformat(),
        'elapsed_s': round(elapsed, 1),
        'trials_per_config': args.trials,
        'seed': args.seed,
        'roi_half_m': ROI_HALF,
        'grid_step_m': GRID_STEP,
        'configs': summary_rows,
    }

    json_path = os.path.join(args.output_dir, 'duration_cadence_summary.json')
    with open(json_path, 'w') as f:
        json.dump(summary_json, f, indent=2)

    print(f"\nDone — {len(configs)} configs, {elapsed:.1f}s")
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())