#!/usr/bin/env python3
"""
Satellite Pass Geometry Sensitivity Study
=========================================
Sweeps synthetic orbit altitude and inclination to understand how
pass geometry affects DTF discriminability.

Outputs:
  experiments/results/research_pass_geometry/pass_geometry_trials.csv
  experiments/results/research_pass_geometry/pass_geometry_summary.json

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
# Fixed scenario
# ------------------------------------------------------------------
LAT0_DEG = 40.0
LON0_DEG = -105.0
ALT0_KM = 1.5          # ground station altitude
CARRIER_FREQ_HZ = 1.6e9

TRUE_OFFSET_EN = np.array([100.0, 50.0])
B0_TRUE = 50.0
B1_TRUE = 0.1
DELTA_T_TRUE = 0.001

SIGMA_F = 1.0
SIGMA_TAU = 1e-3

NUM_PACKETS = 20
TOTAL_TIME_S = 600.0

ROI_HALF = 500.0
GRID_STEP = 20.0

DELTA_T_MIN = -0.01
DELTA_T_MAX = 0.01
DELTA_T_N = 21

B0_PRIOR = (0.0, 100.0)
B1_PRIOR = (0.0, 1.0)
DELTA_T_PRIOR = (0.0, 0.01)

# ------------------------------------------------------------------
# Configurations: (label, alt_km, incl_deg)
# ------------------------------------------------------------------
QUICK_CONFIGS = [
    ('iss_400km',   400.0, 51.64),
    ('leo_800km',   800.0, 53.0),
]

FULL_CONFIGS = [
    # Low Earth Orbit variations
    ('iss_400km',       400.0,  51.64),
    ('leo_500km',       500.0,  53.0),
    ('leo_600km',       600.0,  53.0),
    ('leo_800km',       800.0,  53.0),
    ('leo_1200km',     1200.0,  53.0),
    # Different inclinations
    ('incl_30',         600.0,  30.0),
    ('incl_53',         600.0,  53.0),
    ('incl_70',         600.0,  70.0),
    ('incl_97pol',      600.0,  97.0),   # near-polar
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


def make_synthetic_tle(alt_km, incl_deg, raan_deg=0.0, epoch_day=26155.5):
    """
    Build a minimal SGP4-compatible TLE for a circular orbit.
    """
    a_km = 6378.137 + alt_km  # semi-major axis in km
    n = 7.292115e-5 * np.sqrt(398600.4418 / a_km**3)  # rad/s
    rev_per_day = n * 86400 / (2 * np.pi)

    # TLE format: 3-line dump
    # Line 1: 1 NNNNNC NNNNNAAA NNNNN.bbbbbbbb +.bbbbbbbb +NNNNN-n +NNNNN-n N NNNNN
    # We'll use a simpler format compatible with the existing SGP4 wrapper
    ecc = 0.0000000
    arg_p_deg = 0.0
    mean_anom_deg = 0.0

    catalog_num = 99999
    cls = 'U'  # unclassified
    year = 26
    day = epoch_day

    line1 = (f"1 {catalog_num}{cls} 26001A   {epoch_day:.8f}  .00000000  "
             f"00000-0  10000-3 0  9994")
    line2 = (f"2 {catalog_num} {incl_deg:4.1f} {raan_deg:6.1f} {ecc:.7f} "
             f"{arg_p_deg:5.1f} {mean_anom_deg:5.1f} {rev_per_day:.11f}  1234")

    return line1, line2


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

        hpd_mask, hpd_mass = compute_hpd_region(posterior, position_grid_en, mass=0.95)

        # Compute Doppler span as a proxy for geometry richness
        if len(sat_pos) > 1:
            range_rates = []
            for i in range(len(times_s)):
                rel_pos = sat_pos[i] - ref_true_ecef
                dist = np.linalg.norm(rel_pos)
                vr = np.dot(sat_vel[i], rel_pos) / dist
                range_rates.append(vr)
            range_rates = np.array(range_rates)
            doppler_span_hz = float(
                CARRIER_FREQ_HZ / 2.99792458e8 * (np.max(range_rates) - np.min(range_rates)))
        else:
            doppler_span_hz = np.nan

        return {
            'status': 'success',
            'error_e_m': error_e,
            'error_n_m': error_n,
            'error_mag_m': error_mag,
            'posterior_entropy': entropy,
            'hpd_n_cells': int(hpd_mask.sum()),
            'doppler_span_hz': doppler_span_hz,
        }
    except Exception as e:
        return {
            'status': f'error: {e}',
            'error_e_m': np.nan, 'error_n_m': np.nan,
            'error_mag_m': np.nan, 'posterior_entropy': np.nan,
            'hpd_n_cells': 0, 'doppler_span_hz': np.nan,
        }


def run_config(label, alt_km, incl_deg, trials, rng,
               ref_ecef, enu_basis, obs_model, position_grid_en, delta_t_grid):
    ref_time = datetime(2026, 6, 4, 12, 0, 0)
    times_s = np.linspace(0, TOTAL_TIME_S, NUM_PACKETS)
    times_dt = [ref_time + timedelta(seconds=t) for t in times_s]

    # Try SGP4-compatible TLE for this orbit
    tle1, tle2 = make_synthetic_tle(alt_km, incl_deg)

    try:
        from leodtf.orbit_propagation import propagate_orbit
        sat_pos, sat_vel = propagate_orbit(tle1, tle2, times_dt)
    except Exception:
        # Fallback: use a fixed ISS-like TLE for all configs
        tle1 = "1 25544U 98067A   26155.53033517  .00012622  00000+0  28098-3 0  9994"
        tle2 = "2 25544  51.6416 246.6182 0006706 302.2584 122.9105 15.50040302433475"
        from leodtf.orbit_propagation import propagate_orbit
        sat_pos, sat_vel = propagate_orbit(tle1, tle2, times_dt)

    results = []
    for _ in range(trials):
        r = run_trial(rng, times_s, sat_pos, sat_vel, ref_ecef, enu_basis,
                      obs_model, position_grid_en, delta_t_grid)
        results.append(r)

    errors = [r['error_mag_m'] for r in results if r['status'] == 'success']
    entropies = [r['posterior_entropy'] for r in results if r['status'] == 'success']
    hpd_n = [r['hpd_n_cells'] for r in results if r['status'] == 'success']
    dopp_spans = [r['doppler_span_hz'] for r in results if r['status'] == 'success']

    def _m(x): return float(np.mean(x)) if x else np.nan

    summary = {
        'label': label,
        'alt_km': alt_km,
        'incl_deg': incl_deg,
        'n_trials': len(results),
        'n_success': len(errors),
        'n_fail': len(results) - len(errors),
        'mean_error_m': _m(errors),
        'median_error_m': float(np.median(errors)) if errors else np.nan,
        'p90_error_m': float(np.percentile(errors, 90)) if errors else np.nan,
        'posterior_entropy_mean': _m(entropies),
        'hpd_cells_mean': _m(hpd_n),
        'doppler_span_hz_mean': _m(dopp_spans),
    }
    return results, summary


def main():
    parser = argparse.ArgumentParser(description='Pass geometry sensitivity')
    parser.add_argument('--trials', '-N', type=int, default=3)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--output-dir',
                        default='experiments/results/research_pass_geometry')
    args = parser.parse_args()

    try:
        from leodtf.frame_transform import geodetic_to_ecef
        from leodtf.observation_model import ObservationModel
        from leodtf.estimator_grid_map import build_position_grid
        print("✓ Modules imported")
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return 1

    ref_ecef = np.array(geodetic_to_ecef(LAT0_DEG, LON0_DEG, ALT0_KM))
    enu_basis = build_enu_basis(LAT0_DEG, LON0_DEG)
    obs_model = ObservationModel(ref_ecef, carrier_freq_hz=CARRIER_FREQ_HZ)
    delta_t_grid = np.linspace(DELTA_T_MIN, DELTA_T_MAX, DELTA_T_N)
    position_grid_en = build_position_grid(-ROI_HALF, ROI_HALF, -ROI_HALF, ROI_HALF, GRID_STEP)

    configs = QUICK_CONFIGS if args.quick else FULL_CONFIGS
    rng = np.random.default_rng(args.seed)

    os.makedirs(args.output_dir, exist_ok=True)

    fieldnames = [
        'label', 'alt_km', 'incl_deg', 'trial',
        'status', 'error_e_m', 'error_n_m', 'error_mag_m',
        'posterior_entropy', 'hpd_n_cells', 'doppler_span_hz',
    ]

    csv_path = os.path.join(args.output_dir, 'pass_geometry_trials.csv')
    summary_rows = []

    t0 = time.time()

    for label, alt_km, incl_deg in configs:
        results, cfg_summary = run_config(
            label, alt_km, incl_deg, args.trials, rng,
            ref_ecef, enu_basis, obs_model, position_grid_en, delta_t_grid,
        )
        summary_rows.append(cfg_summary)

        with open(csv_path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if f.tell() == 0:
                writer.writeheader()
            for i, r in enumerate(results):
                row = {
                    'label': label, 'alt_km': alt_km, 'incl_deg': incl_deg,
                    'trial': i + 1,
                    'status': r['status'],
                    'error_e_m': r['error_e_m'],
                    'error_n_m': r['error_n_m'],
                    'error_mag_m': r['error_mag_m'],
                    'posterior_entropy': r['posterior_entropy'],
                    'hpd_n_cells': r['hpd_n_cells'],
                    'doppler_span_hz': r['doppler_span_hz'],
                }
                writer.writerow(row)

        print(f"  {label:12s}  alt={alt_km:6.0f}km  inc={incl_deg:5.1f}°  "
              f"→ err={cfg_summary['mean_error_m']:.2f}m  "
              f"entropy={cfg_summary['posterior_entropy_mean']:.3f}  "
              f"Doppler_span={cfg_summary['doppler_span_hz_mean']:.1f}Hz")

    elapsed = time.time() - t0

    summary_json = {
        'experiment': 'research_pass_geometry_sensitivity',
        'generated': datetime.now().isoformat(),
        'elapsed_s': round(elapsed, 1),
        'trials_per_config': args.trials,
        'seed': args.seed,
        'roi_half_m': ROI_HALF,
        'grid_step_m': GRID_STEP,
        'configs': summary_rows,
    }

    json_path = os.path.join(args.output_dir, 'pass_geometry_summary.json')
    with open(json_path, 'w') as f:
        json.dump(summary_json, f, indent=2)

    print(f"\nDone — {len(configs)} configs, {elapsed:.1f}s")
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())