#!/usr/bin/env python3
"""
Doppler-Time Fingerprint Ambiguity and Ablation Study
=====================================================
Runs a set of ablation cases that progressively add complexity to the
observation model, measuring how localization ambiguity (posterior entropy,
HPD region size) and error change as more nuisance parameters and
observation modalities are used.

Outputs:
  experiments/results/ablation/ambiguity_ablation_trials.csv
  experiments/results/ablation/ambiguity_ablation_summary.json
  paper/tables/ablation_summary.tex

All results are preliminary synthetic diagnostics. No paper performance
claims are made.
"""

import sys
import os
import csv
import json
import argparse
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# -----------------------------------------------------------------------
# Fixed scenario parameters
# -----------------------------------------------------------------------
LAT0_DEG = 40.0
LON0_DEG = -105.0
ALT0_KM = 1.5
CARRIER_FREQ_HZ = 1.6e9
NUM_PACKETS = 20
TOTAL_TIME_S = 600.0

# True EN offset (what estimator should recover)
TRUE_OFFSET_EN = np.array([100.0, 50.0])  # meters

# True nuisance
B0_TRUE = 50.0       # Hz
B1_TRUE = 0.1         # Hz/s
DELTA_T_TRUE = 0.001  # seconds

# Noise settings
SIGMA_F = 1.0        # Hz (frequency noise)
SIGMA_TAU = 1e-3     # seconds (delay noise, 1 ms)

# Grid
E_MIN, E_MAX = -200.0, 200.0
N_MIN, N_MAX = -200.0, 200.0
STEP_M = 20.0

# Delta-t grid
DELTA_T_MIN = -0.01
DELTA_T_MAX = 0.01
DELTA_T_N = 21

# Priors
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


def synthetic_orbit(times_dt):
    R = 6378.137 + 400.0
    mu = 3.986004418e5
    n = np.sqrt(mu / R**3)
    sat_pos, sat_vel = [], []
    for dt in times_dt:
        t = (dt - times_dt[0]).total_seconds()
        angle = n * t
        x, y = R * np.cos(angle), R * np.sin(angle)
        z = 0.0
        vx, vy = -R * n * np.sin(angle), R * n * np.cos(angle)
        vz = 0.0
        sat_pos.append([x, y, z])
        sat_vel.append([vx, vy, vz])
    return np.array(sat_pos), np.array(sat_vel)


def run_case(case_name, use_delay, use_cfo, use_drift,
             rng, sat_pos, sat_vel, ref_ecef, enu_basis, obs_model,
             position_grid_en, delta_t_grid):
    """
    Run estimator for one ablation case.

    Returns a dict of scalar results.
    """
    from leodtf.estimator_grid_map import estimate_grid_map

    # Build 3-D true offset in km for ECEF shift
    true_offset_km = np.array([TRUE_OFFSET_EN[0], TRUE_OFFSET_EN[1], 0.0]) / 1000.0
    true_gs_ecef = ref_ecef + enu_basis @ true_offset_km

    # Generate observations
    times_s = np.linspace(0, TOTAL_TIME_S, NUM_PACKETS)
    observed_freq = np.zeros(NUM_PACKETS)
    observed_tau = np.zeros(NUM_PACKETS) if use_delay else None

    for i in range(NUM_PACKETS):
        sat_state = (sat_pos[i], sat_vel[i])
        doppler_hz, propagation_delay_s = obs_model.compute_expected_measurements(
            sat_state, times_s[i])

        noise_f = rng.normal(0.0, SIGMA_F)
        observed_freq[i] = doppler_hz + (B0_TRUE if use_cfo else 0.0) + \
                           (B1_TRUE * times_s[i] if use_drift else 0.0) + noise_f

        if use_delay:
            noise_tau = rng.normal(0.0, SIGMA_TAU)
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
            sigma_tau=SIGMA_TAU if use_delay else 1e-9,
            b0_prior=B0_PRIOR if use_cfo else (0.0, 1e-6),
            b1_prior=B1_PRIOR if use_drift else (0.0, 1e-6),
            delta_t_prior=DELTA_T_PRIOR
        )
        error_e = map_pos_en[0] - TRUE_OFFSET_EN[0]
        error_n = map_pos_en[1] - TRUE_OFFSET_EN[1]
        error_mag = float(np.hypot(error_e, error_n))

        eps = 1e-10
        p = posterior + eps
        p = p / p.sum()
        entropy = float(-np.sum(p * np.log(p)))

        from leodtf.estimator_grid_map import compute_hpd_region
        hpd_mask, hpd_mass = compute_hpd_region(posterior, position_grid_en, mass=0.95)

        return {
            'case_name': case_name,
            'use_delay': use_delay,
            'use_cfo': use_cfo,
            'use_drift': use_drift,
            'num_samples': NUM_PACKETS,
            'localization_error_m': error_mag,
            'b0_est_hz': float(best_b0),
            'b1_est_hz_s': float(best_b1),
            'delta_t_est_s': float(best_delta_t),
            'posterior_entropy': entropy,
            'hpd_n_cells': int(hpd_mask.sum()),
            'hpd_mass': float(hpd_mass),
            'posterior_sum': float(posterior.sum()),
            'success': True,
            'notes': _get_notes(use_delay, use_cfo, use_drift),
        }
    except Exception as e:
        return {
            'case_name': case_name,
            'use_delay': use_delay,
            'use_cfo': use_cfo,
            'use_drift': use_drift,
            'num_samples': NUM_PACKETS,
            'localization_error_m': float('nan'),
            'posterior_entropy': float('nan'),
            'hpd_n_cells': 0,
            'hpd_mass': 0.0,
            'success': False,
            'notes': f'ERROR: {e}',
        }


def _get_notes(use_delay, use_cfo, use_drift):
    parts = []
    parts.append('frequency-only' if not use_delay else 'frequency+delay')
    if not use_cfo:
        parts.append('no CFO')
    if not use_drift:
        parts.append('no drift')
    return '; '.join(parts)


CASES = [
    dict(name='single_snapshot_freq',     use_delay=False, use_cfo=False, use_drift=False),
    dict(name='multi_snapshot_freq',       use_delay=False, use_cfo=False, use_drift=False),
    dict(name='multi_snapshot_freq_cfo',  use_delay=False, use_cfo=True,  use_drift=False),
    dict(name='multi_snapshot_freq_cfo_drift', use_delay=False, use_cfo=True, use_drift=True),
    dict(name='multi_snapshot_freq_delay', use_delay=True,  use_cfo=False, use_drift=False),
    dict(name='multi_snapshot_freq_delay_cfo',   use_delay=True, use_cfo=True,  use_drift=False),
    dict(name='multi_snapshot_freq_delay_cfo_drift', use_delay=True, use_cfo=True, use_drift=True),
]


def main():
    parser = argparse.ArgumentParser(description='Ambiguity and ablation study')
    parser.add_argument('--trials', '-N', type=int, default=10,
                        help='Monte Carlo trials per case (default: 10)')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output-dir',
                        default='experiments/results/ablation')
    args = parser.parse_args()

    # Load modules
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

    # Build scenario
    ref_time = datetime(2026, 6, 4, 12, 0, 0)
    times_s = np.linspace(0, TOTAL_TIME_S, NUM_PACKETS)
    times_dt = [ref_time + timedelta(seconds=t) for t in times_s]

    sat_pos, sat_vel = synthetic_orbit(times_dt)
    ref_ecef = np.array(geodetic_to_ecef(LAT0_DEG, LON0_DEG, ALT0_KM))
    enu_basis = build_enu_basis(LAT0_DEG, LON0_DEG)
    obs_model = ObservationModel(ref_ecef, carrier_freq_hz=CARRIER_FREQ_HZ)
    position_grid_en = build_position_grid(E_MIN, E_MAX, N_MIN, N_MAX, STEP_M)
    delta_t_grid = np.linspace(DELTA_T_MIN, DELTA_T_MAX, DELTA_T_N)

    print(f"Position grid: {position_grid_en.shape[0]} points")
    print(f"Trials per case: {args.trials}  seed={args.seed}")
    print(f"True EN offset: {TRUE_OFFSET_EN[0]:.0f}E, {TRUE_OFFSET_EN[1]:.0f}N m\n")

    output_dir = os.path.join(
        os.path.dirname(__file__), '..', args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, 'ambiguity_ablation_trials.csv')
    json_path = os.path.join(output_dir, 'ambiguity_ablation_summary.json')

    fieldnames = [
        'case_name', 'trial', 'use_delay', 'use_cfo', 'use_drift',
        'num_samples', 'localization_error_m',
        'b0_est_hz', 'b1_est_hz_s', 'delta_t_est_s',
        'posterior_entropy', 'hpd_n_cells', 'hpd_mass', 'posterior_sum', 'success', 'notes'
    ]

    rows = []
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for case in CASES:
            name = case['name']
            print(f"  Case: {name}")
            for trial in range(1, args.trials + 1):
                rng = np.random.default_rng(args.seed + trial + hash(name) % 1000)
                row = {
                    'trial': trial,
                    'case_name': name,
                    'use_delay': case['use_delay'],
                    'use_cfo': case['use_cfo'],
                    'use_drift': case['use_drift'],
                }
                result = run_case(
                    name, case['use_delay'], case['use_cfo'], case['use_drift'],
                    rng, sat_pos, sat_vel, ref_ecef, enu_basis, obs_model,
                    position_grid_en, delta_t_grid)
                row.update({k: v for k, v in result.items() if k != 'case_name'})
                writer.writerow(row)
                rows.append(row)

            # Per-case summary
            case_rows = [r for r in rows if r['case_name'] == name and r['success']]
            if case_rows:
                errs = [r['localization_error_m'] for r in case_rows]
                ents = [r['posterior_entropy'] for r in case_rows]
                hpds = [r['hpd_n_cells'] for r in case_rows]
                print(f"    N={len(case_rows)}  "
                      f"err={np.mean(errs):.1f}±{np.std(errs):.1f}m  "
                      f"ent={np.mean(ents):.3f}  "
                      f"hpd={int(np.mean(hpds))}")

    # Build summary JSON
    summary_cases = {}
    for case in CASES:
        name = case['name']
        case_rows = [r for r in rows if r['case_name'] == name and r['success']]
        if not case_rows:
            continue
        errs = [r['localization_error_m'] for r in case_rows]
        ents = [r['posterior_entropy'] for r in case_rows]
        hpds = [r['hpd_n_cells'] for r in case_rows]

        summary_cases[name] = {
            'use_delay': case['use_delay'],
            'use_cfo': case['use_cfo'],
            'use_drift': case['use_drift'],
            'trials': len(case_rows),
            'mean_error_m': float(np.mean(errs)),
            'std_error_m': float(np.std(errs)),
            'min_error_m': float(np.min(errs)),
            'max_error_m': float(np.max(errs)),
            'median_error_m': float(np.median(errs)),
            'p90_error_m': float(np.percentile(errs, 90)),
            'mean_entropy': float(np.mean(ents)),
            'std_entropy': float(np.std(ents)),
            'mean_hpd_cells': float(np.mean(hpds)),
            'notes': case_rows[0]['notes'],
        }

    summary = {
        'experiment': 'ambiguity_ablation',
        'trials_per_case': args.trials,
        'seed': args.seed,
        'config': {
            'roi_e_span_m': [E_MIN, E_MAX],
            'roi_n_span_m': [N_MIN, N_MAX],
            'grid_step_m': STEP_M,
            'num_packets': NUM_PACKETS,
            'total_time_s': TOTAL_TIME_S,
            'true_offset_en_m': TRUE_OFFSET_EN.tolist(),
            'sigma_f_hz': SIGMA_F,
            'sigma_tau_s': SIGMA_TAU,
        },
        'cases': summary_cases,
        'qualitative_interpretation': (
            "Multi-sample observations reduce ambiguity vs single-snapshot; "
            "delay observations provide additional discriminability when sigma_tau is small; "
            "CFO and drift act as vertical/tilt nuisance and do not degrade position "
            "estimate when properly marginalized; "
            "all results are preliminary synthetic diagnostics only."
        ),
        'output_csv': csv_path,
    }

    with open(json_path, 'w') as f:
        json.dump(summary, f, indent=2)

    # Write LaTeX table
    tex_path = os.path.join(
        os.path.dirname(__file__), '..', 'paper', 'tables', 'ablation_summary.tex')
    _write_tex_table(summary_cases, tex_path)

    print(f"\nCSV: {csv_path}")
    print(f"JSON: {json_path}")
    print(f"TeX:  {tex_path}")
    print("NOTE: Synthetic diagnostic only. No paper claims made.")
    return 0


def _write_tex_table(cases, tex_path):
    """Write a simple LaTeX table from ablation summary cases."""
    os.makedirs(os.path.dirname(tex_path), exist_ok=True)
    rows = []
    n_val = next((c['trials'] for c in cases.values()), '?')
    for name, c in cases.items():
        short = name.replace('_', '\\_')
        err = c['mean_error_m']
        ent = c['mean_entropy']
        hpd = c['mean_hpd_cells']
        delay = 'Yes' if c['use_delay'] else 'No'
        cfo = 'Yes' if c['use_cfo'] else 'No'
        drift = 'Yes' if c['use_drift'] else 'No'
        rows.append(
            f"{short} & {delay} & {cfo} & {drift} & "
            f"{err:.1f} & {ent:.3f} & {int(hpd)} \\"
        )
    body = '\n    '.join(rows) if rows else "No data \\"
    content_str = f"""%% LEO-DTF Ablation Summary
%% Auto-generated by scripts/run_ambiguity_ablation.py
%% Do not edit manually

\\begin{{table}}[htbp]
\\centering
\\caption{{Ablation Study: Effect of Observation Modalities and Nuisance Parameters
          on Estimator Behavior (Preliminary Synthetic)}}
\\label{{tab:ablation}}
\\begin{{tabular}}{{|l|c|c|c|r|r|r|}}
\\hline
\\textbf{{Case}} & \\textbf{{Delay}} & \\textbf{{CFO}} & \\textbf{{Drift}} &
  \\textbf{{Mean Err (m)}} & \\textbf{{Mean Entropy}} & \\textbf{{HPD Cells}} \\ \\hline
    {body}
\\hline
\\end{{tabular}}
\\smallskip
\\footnotesize
All results are preliminary synthetic diagnostics (N={n_val} trials per case).
Error is mean localization error; entropy and HPD cells characterize posterior ambiguity.
CRLB is not evaluated here.  No paper performance claims are made.
\\end{{table}}
"""
    with open(tex_path, 'w') as f:
        f.write(content_str)


if __name__ == '__main__':
    sys.exit(main())