#!/usr/bin/env python3
"""
Monte Carlo synthetic trials for LEO-DTF estimator.
=====================================================
Runs N trials with randomized noise realizations over a fixed scenario.
Outputs per-trial results to a CSV file.

No paper claims are made from these results.  This is a development
diagnostic for characterizing estimator behavior under repeated sampling.
"""

import sys
import os
import csv
import argparse
import numpy as np
from datetime import datetime, timedelta

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ---------------------------------------------------------------------------
# Fixed scenario
# ---------------------------------------------------------------------------
LAT0_DEG = 40.0
LON0_DEG = -105.0
ALT0_KM = 1.5
CARRIER_FREQ_HZ = 1.6e9   # 1.6 GHz L-band
NUM_PACKETS = 20
TOTAL_TIME_S = 600.0

# True EN offset of the ground station (what the estimator should recover)
TRUE_OFFSET_EN = np.array([100.0, 50.0])   # meters

# True nuisance parameters
B0_TRUE = 50.0      # Hz
B1_TRUE = 0.1       # Hz/s
DELTA_T_TRUE = 0.001  # seconds

# Noise std used in the observation model
SIGMA_F = 1.0       # Hz
SIGMA_TAU = 1e-3    # seconds (1 ms)

# Estimation grid
E_MIN, E_MAX = -200.0, 200.0   # meters
N_MIN, N_MAX = -200.0, 200.0   # meters
STEP_M = 20.0                   # meters

# Time offset grid
DELTA_T_MIN = -0.01   # seconds
DELTA_T_MAX = 0.01    # seconds
DELTA_T_N = 21

# Priors (weak)
B0_PRIOR = (0.0, 100.0)        # mean, std Hz
B1_PRIOR = (0.0, 1.0)          # mean, std Hz/s
DELTA_T_PRIOR = (0.0, 0.01)     # mean, std seconds


def build_enu_basis(lat_deg, lon_deg):
    """Compute ENU basis vectors at a geodetic location."""
    lat = np.radians(lat_deg)
    lon = np.radians(lon_deg)
    basis = np.array([
        [-np.sin(lon),  np.cos(lon), 0.0],
        [-np.sin(lat)*np.cos(lon), -np.sin(lat)*np.sin(lon), np.cos(lat)],
        [np.cos(lat)*np.cos(lon),  np.cos(lat)*np.sin(lon),  np.sin(lat)]
    ])
    return basis.T   # columns are E, N, Up (3x3)


def run_single_trial(rng, times_s, sat_positions_ecef, sat_velocities_ecef,
                     ref_ecef, enu_basis, obs_model,
                     position_grid_en, delta_t_grid):
    """
    Generate one synthetic trial and run the estimator.

    Returns a dict of scalar results.
    """
    from leodtf.estimator_grid_map import estimate_grid_map

    # Build 3-D true offset in km for ECEF shift
    true_offset_km = np.array([TRUE_OFFSET_EN[0], TRUE_OFFSET_EN[1], 0.0]) / 1000.0
    true_gs_ecef = ref_ecef + enu_basis @ true_offset_km

    # Generate observations
    observed_freq = np.zeros(NUM_PACKETS)
    observed_tau = np.zeros(NUM_PACKETS)

    for i in range(NUM_PACKETS):
        sat_state = (sat_positions_ecef[i], sat_velocities_ecef[i])
        doppler_hz, propagation_delay_s = obs_model.compute_expected_measurements(
            sat_state, times_s[i])

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
        delta_t_prior=DELTA_T_PRIOR
    )

    # Compute error
    error_e = map_pos_en[0] - TRUE_OFFSET_EN[0]
    error_n = map_pos_en[1] - TRUE_OFFSET_EN[1]
    error_mag = np.hypot(error_e, error_n)

    # Posterior entropy
    eps = 1e-10
    p = posterior + eps
    p = p / p.sum()
    entropy = -np.sum(p * np.log(p))

    # HPD 95% region size
    from leodtf.estimator_grid_map import compute_hpd_region
    hpd_mask, hpd_mass = compute_hpd_region(posterior, position_grid_en, mass=0.95)

    return {
        'true_e_m': float(TRUE_OFFSET_EN[0]),
        'true_n_m': float(TRUE_OFFSET_EN[1]),
        'map_e_m': float(map_pos_en[0]),
        'map_n_m': float(map_pos_en[1]),
        'error_e_m': float(error_e),
        'error_n_m': float(error_n),
        'error_mag_m': float(error_mag),
        'b0_true_hz': B0_TRUE,
        'b1_true_hz_s': B1_TRUE,
        'delta_t_true_s': DELTA_T_TRUE,
        'b0_est_hz': float(best_b0),
        'b1_est_hz_s': float(best_b1),
        'delta_t_est_s': float(best_delta_t),
        'posterior_entropy': float(entropy),
        'hpd_n_cells': int(hpd_mask.sum()),
        'hpd_mass': float(hpd_mass),
        'posterior_sum': float(posterior.sum()),
        'sigma_f_hz': SIGMA_F,
        'sigma_tau_s': SIGMA_TAU,
        'grid_step_m': STEP_M,
    }


def main():
    parser = argparse.ArgumentParser(description='Monte Carlo synthetic trials')
    parser.add_argument('--trials', '-N', type=int, default=100,
                        help='Number of Monte Carlo trials (default: 100)')
    parser.add_argument('--seed', type=int, default=42,
                        help='Numpy random seed (default: 42)')
    parser.add_argument('--output', '-o',
                        default='outputs/monte_carlo_synthetic.csv',
                        help='Output CSV path')
    args = parser.parse_args()

    # ---- Load modules ----
    try:
        from leodtf.tle_loader import parse_tle
        from leodtf.orbit_propagation import propagate_orbit
        from leodtf.frame_transform import geodetic_to_ecef
        from leodtf.observation_model import ObservationModel
        from leodtf.estimator_grid_map import build_position_grid
        print("✓ All modules imported")
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return 1

    # ---- Synthetic TLE (fallback orbit) ----
    line1 = "1 25544U 98067A   26155.53033517  .00012622  00000+0  28098-3 0  9994"
    line2 = "2 25544  51.6416 246.6182 0006706 302.2584 122.9105 15.50040302433475"

    # ---- Build scenario ----
    ref_time = datetime(2026, 6, 4, 12, 0, 0)
    times_s = np.linspace(0, TOTAL_TIME_S, NUM_PACKETS)
    times_dt = [ref_time + timedelta(seconds=t) for t in times_s]

    sat_pos, sat_vel = propagate_orbit(line1, line2, times_dt)
    ref_ecef = np.array(geodetic_to_ecef(LAT0_DEG, LON0_DEG, ALT0_KM))
    enu_basis = build_enu_basis(LAT0_DEG, LON0_DEG)

    obs_model = ObservationModel(ref_ecef, carrier_freq_hz=CARRIER_FREQ_HZ)

    position_grid_en = build_position_grid(E_MIN, E_MAX, N_MIN, N_MAX, STEP_M)
    delta_t_grid = np.linspace(DELTA_T_MIN, DELTA_T_MAX, DELTA_T_N)

    print(f"Position grid: {position_grid_en.shape[0]} points  "
          f"({E_MIN}–{E_MAX} m E, {N_MIN}–{N_MAX} m N, {STEP_M} m step)")
    print(f"Delta-t grid: {len(delta_t_grid)} points  "
          f"({DELTA_T_MIN*1e3:.1f}–{DELTA_T_MAX*1e3:.1f} ms)")
    print(f"True EN offset: {TRUE_OFFSET_EN[0]:.1f} E, {TRUE_OFFSET_EN[1]:.1f} N m")
    print(f"Noise: sigma_f={SIGMA_F} Hz, sigma_tau={SIGMA_TAU*1e3:.1f} ms")
    print(f"Trials: {args.trials}   seed={args.seed}")

    # ---- Run trials ----
    rng = np.random.default_rng(args.seed)

    os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)

    fieldnames = [
        'trial', 'seed',
        'true_e_m', 'true_n_m',
        'map_e_m', 'map_n_m',
        'error_e_m', 'error_n_m', 'error_mag_m',
        'b0_true_hz', 'b1_true_hz_s', 'delta_t_true_s',
        'b0_est_hz', 'b1_est_hz_s', 'delta_t_est_s',
        'posterior_entropy', 'hpd_n_cells', 'hpd_mass', 'posterior_sum',
        'sigma_f_hz', 'sigma_tau_s', 'grid_step_m',
    ]

    with open(args.output, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for trial in range(1, args.trials + 1):
            row = {'trial': trial, 'seed': args.seed}
            row.update(run_single_trial(
                rng, times_s, sat_pos, sat_vel,
                ref_ecef, enu_basis, obs_model,
                position_grid_en, delta_t_grid))
            writer.writerow(row)

            if trial % 20 == 0 or trial == 1:
                print(f"  trial {trial:4d} / {args.trials}   "
                      f"RMSE: {row['error_mag_m']:.2f} m   "
                      f"b0_est: {row['b0_est_hz']:.2f} Hz")

    # ---- Summary ----
    errors = []
    with open(args.output, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            errors.append(float(row['error_mag_m']))
    errors = np.array(errors)
    print(f"\n── Summary ({args.trials} trials, seed={args.seed}) ──")
    print(f"  error_mag mean : {np.mean(errors):.2f} m")
    print(f"  error_mag std  : {np.std(errors):.2f} m")
    print(f"  error_mag min  : {np.min(errors):.2f} m")
    print(f"  error_mag max  : {np.max(errors):.2f} m")

    print(f"\nCSV written: {args.output}")
    print("NOTE: Synthetic diagnostic only. No paper claims are made.")
    return 0


if __name__ == '__main__':
    sys.exit(main())