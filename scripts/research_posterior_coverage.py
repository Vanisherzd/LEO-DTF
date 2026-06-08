#!/usr/bin/env python3
"""
Posterior HPD Coverage Diagnostic
==================================
Checks whether the HPD credible regions have correct coverage:
does the true location fall inside the 50/80/90/95% HPD regions
at the expected rates?

Outputs:
  experiments/results/research_posterior_coverage/posterior_coverage_trials.csv
  experiments/results/research_posterior_coverage/posterior_coverage_summary.json

IMPORTANT: This is a calibration DIAGNOSTIC, not a proof of calibration.
Results are preliminary and depend on grid resolution, prior choices, and
synthetic noise model. Do not claim statistical calibration from this alone.

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


def run_trial(rng, times_s, sat_pos, sat_vel, ref_ecef, enu_basis, obs_model,
              position_grid_en, delta_t_grid):
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

        # Check HPD coverage at 4 levels
        hpd_masses = [0.50, 0.80, 0.90, 0.95]
        coverage = {}
        hpd_sizes = {}
        for mass in hpd_masses:
            hpd_mask, _ = compute_hpd_region(posterior, position_grid_en, mass=mass)
            hpd_size = int(hpd_mask.sum())
            hpd_sizes[f'hpd_{int(mass*100)}_cells'] = hpd_size

            # Check if true position is in HPD region
            # True position in grid: find nearest grid point to TRUE_OFFSET_EN
            diffs = position_grid_en - TRUE_OFFSET_EN  # [G, 2]
            dists = np.sqrt(diffs[:, 0]**2 + diffs[:, 1]**2)
            nearest_idx = int(np.argmin(dists))
            in_hpd = bool(hpd_mask[nearest_idx])
            coverage[f'coverage_{int(mass*100)}'] = in_hpd

        return {
            'status': 'success',
            'error_mag_m': error_mag,
            'posterior_entropy': entropy,
            **coverage,
            **hpd_sizes,
        }
    except Exception as e:
        return {
            'status': f'error: {e}',
            'error_mag_m': np.nan, 'posterior_entropy': np.nan,
            'coverage_50': False, 'coverage_80': False,
            'coverage_90': False, 'coverage_95': False,
            'hpd_50_cells': 0, 'hpd_80_cells': 0,
            'hpd_90_cells': 0, 'hpd_95_cells': 0,
        }


def main():
    parser = argparse.ArgumentParser(description='Posterior HPD coverage diagnostic')
    parser.add_argument('--trials', '-N', type=int, default=30)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--quick', action='store_true',
                        help='Use 3 trials only (smoke test)')
    parser.add_argument('--output-dir',
                        default='experiments/results/research_posterior_coverage')
    args = parser.parse_args()

    if args.quick:
        args.trials = 3

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

    rng = np.random.default_rng(args.seed)

    os.makedirs(args.output_dir, exist_ok=True)

    fieldnames = [
        'trial', 'status', 'error_mag_m', 'posterior_entropy',
        'coverage_50', 'coverage_80', 'coverage_90', 'coverage_95',
        'hpd_50_cells', 'hpd_80_cells', 'hpd_90_cells', 'hpd_95_cells',
    ]

    csv_path = os.path.join(args.output_dir, 'posterior_coverage_trials.csv')
    results = []

    t0 = time.time()

    for trial in range(1, args.trials + 1):
        r = run_trial(rng, times_s, sat_pos, sat_vel, ref_ecef, enu_basis,
                      obs_model, position_grid_en, delta_t_grid)
        r['trial'] = trial
        results.append(r)

        with open(csv_path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if f.tell() == 0:
                writer.writeheader()
            writer.writerow({k: r.get(k, '') for k in fieldnames})

        if trial % 10 == 0 or trial == 1:
            cov50 = r.get('coverage_50', False)
            print(f"  trial {trial:3d}/{args.trials}  "
                  f"err={r.get('error_mag_m', 0):.2f}m  "
                  f"cov50={cov50}")

    elapsed = time.time() - t0

    # Summarize coverage rates
    successes = [x for x in results if x['status'] == 'success']

    def cov_rate(key):
        if not successes:
            return np.nan
        return sum(1 for r in successes if r.get(key, False)) / len(successes)

    def mean(key):
        vals = [r[key] for r in successes if r.get(key) is not None and not np.isnan(r.get(key, np.nan))]
        return float(np.mean(vals)) if vals else np.nan

    summary = {
        'experiment': 'research_posterior_coverage',
        'generated': datetime.now().isoformat(),
        'elapsed_s': round(elapsed, 1),
        'n_trials': args.trials,
        'n_success': len(successes),
        'coverage_50': cov_rate('coverage_50'),
        'coverage_80': cov_rate('coverage_80'),
        'coverage_90': cov_rate('coverage_90'),
        'coverage_95': cov_rate('coverage_95'),
        'mean_error_m': mean('error_mag_m'),
        'posterior_entropy_mean': mean('posterior_entropy'),
        'hpd_50_cells_mean': mean('hpd_50_cells'),
        'hpd_80_cells_mean': mean('hpd_80_cells'),
        'hpd_90_cells_mean': mean('hpd_90_cells'),
        'hpd_95_cells_mean': mean('hpd_95_cells'),
        'calibration_note': (
            'Preliminary diagnostic only. Coverage rates computed on grid with '
            f'{ROI_HALF*2}m ROI and {GRID_STEP}m step over {args.trials} trials. '
            'Not a proof of statistical calibration. Requires more trials and '
            'varied ground-truth locations for meaningful calibration assessment.'
        ),
    }

    json_path = os.path.join(args.output_dir, 'posterior_coverage_summary.json')
    with open(json_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\n── Coverage Summary ({len(successes)}/{args.trials} trials) ──")
    for level in [50, 80, 90, 95]:
        rate = cov_rate(f'coverage_{level}')
        expected = level / 100.0
        print(f"  {level}% HPD: coverage={rate:.3f}  (expected={expected:.2f})")

    print(f"\nDone — {elapsed:.1f}s")
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())