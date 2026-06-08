#!/usr/bin/env python3
"""
Failure Case Mining Utility
============================
Scans all research result directories and aggregates failure cases.
Outputs a structured CSV and JSON summary of configs that failed or
performed poorly.

Failure criteria:
  - localization_error_m > threshold (default 100 m)
  - status != success
  - posterior_entropy > threshold (high ambiguity)
  - hpd_cells > threshold (posterior spread wide)

This utility supports honest negative reporting — finding the regimes
where LEO-DTF does NOT work well — without modifying paper claims.

Output:
  experiments/results/research_failure_cases/failure_cases.csv
  experiments/results/research_failure_cases/failure_cases_summary.json
"""

import sys
import os
import csv
import json
import argparse
from datetime import datetime

import numpy as np


DEFAULT_ERROR_THRESHOLD_M = 100.0
DEFAULT_ENTROPY_THRESHOLD = 5.0
DEFAULT_HPD_THRESHOLD = 500

EXPERIMENTS = {
    'research_roi_grid': {
        'csv': 'experiments/results/research_roi_grid/roi_grid_trials.csv',
        'summary': 'experiments/results/research_roi_grid/roi_grid_summary.json',
    },
    'research_duration_cadence': {
        'csv': 'experiments/results/research_duration_cadence/duration_cadence_trials.csv',
        'summary': 'experiments/results/research_duration_cadence/duration_cadence_summary.json',
    },
    'research_nuisance_prior': {
        'csv': 'experiments/results/research_nuisance_prior/nuisance_prior_trials.csv',
        'summary': 'experiments/results/research_nuisance_prior/nuisance_prior_summary.json',
    },
    'research_pass_geometry': {
        'csv': 'experiments/results/research_pass_geometry/pass_geometry_trials.csv',
        'summary': 'experiments/results/research_pass_geometry/pass_geometry_summary.json',
    },
    'research_posterior_coverage': {
        'csv': 'experiments/results/research_posterior_coverage/posterior_coverage_trials.csv',
        'summary': 'experiments/results/research_posterior_coverage/posterior_coverage_summary.json',
    },
}


def load_csv(csv_path):
    rows = []
    try:
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except (FileNotFoundError, csv.Error):
        pass
    return rows


def load_json(json_path):
    try:
        with open(json_path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def is_failure(row, error_threshold, entropy_threshold, hpd_threshold):
    """Check if a trial/config counts as a failure case."""
    status = row.get('status', 'success')
    if status != 'success' and 'error' in str(status).lower():
        return True, 'estimator_error'

    # Error: try primary then mean variants
    err_raw = row.get('error_mag_m') or row.get('mean_error_m')
    if err_raw:
        try:
            err = float(err_raw)
            if err > error_threshold:
                return True, f'high_error_{err:.1f}m'
        except (ValueError, TypeError):
            pass

    # Entropy: try primary then mean variants
    ent_raw = row.get('posterior_entropy') or row.get('posterior_entropy_mean')
    if ent_raw:
        try:
            ent = float(ent_raw)
            if ent > entropy_threshold:
                return True, f'high_entropy_{ent:.2f}'
        except (ValueError, TypeError):
            pass

    # HPD cells: try multiple column variants
    hpd_raw = (row.get('hpd_n_cells') or row.get('hpd_cells_mean') or
               row.get('hpd_50_cells') or row.get('hpd_50_cells_mean'))
    if hpd_raw:
        try:
            hpd = float(hpd_raw)
            if hpd > hpd_threshold:
                return True, f'large_hpd_{int(hpd)}'
        except (ValueError, TypeError):
            pass

    return False, ''


def interpret_failure(reason):
    """Generate conservative interpretation without overclaiming."""
    if 'error' in reason.lower():
        return 'Estimator failed — possible numerical instability or insufficient observations.'
    elif 'high_error' in reason:
        return 'Localization error exceeds threshold — DTF fingerprint may be insufficiently discriminative in this regime.'
    elif 'high_entropy' in reason:
        return 'High posterior entropy indicates ambiguous/uninformative Doppler-time observations.'
    elif 'large_hpd' in reason:
        return 'Large HPD region suggests weak posterior concentration.'
    return 'Regime where LEO-DTF performance degrades — further investigation needed.'


def main():
    parser = argparse.ArgumentParser(description='Mine failure cases from research results')
    parser.add_argument('--error-threshold-m', type=float, default=DEFAULT_ERROR_THRESHOLD_M)
    parser.add_argument('--entropy-threshold', type=float, default=DEFAULT_ENTROPY_THRESHOLD)
    parser.add_argument('--hpd-threshold', type=int, default=DEFAULT_HPD_THRESHOLD)
    parser.add_argument('--output-dir', default='experiments/results/research_failure_cases')
    args = parser.parse_args()

    failure_rows = []
    summary_data = {}

    for exp_name, cfg in EXPERIMENTS.items():
        csv_path = cfg['csv']
        summary_path = cfg['summary']

        if not os.path.exists(csv_path):
            print(f"  [skip] {exp_name} — no CSV")
            continue

        rows = load_csv(csv_path)

        exp_failures = []
        for row in rows:
            is_fail, reason = is_failure(
                row, args.error_threshold_m,
                args.entropy_threshold, args.hpd_threshold)
            if is_fail:
                failure_rows.append({
                    'source_experiment': exp_name,
                    'config_id': (row.get('roi_half_m') or row.get('config_id') or
                                  row.get('duration_s') or row.get('cfo_prior_hz') or 'unknown'),
                    'reason': reason,
                    'error_m': row.get('error_mag_m') or row.get('mean_error_m', ''),
                    'entropy': row.get('posterior_entropy') or row.get('posterior_entropy_mean', ''),
                    'hpd_cells': (row.get('hpd_n_cells') or row.get('hpd_cells_mean') or
                                  row.get('hpd_50_cells') or row.get('hpd_50_cells_mean', '')),
                    'status': row.get('status', 'unknown'),
                    'suggested_interpretation': interpret_failure(reason),
                })
                exp_failures.append(failure_rows[-1])

        status = 'ok' if not exp_failures else f'{len(exp_failures)}_failures'
        print(f"  {exp_name}: {len(rows)} configs, {len(exp_failures)} failures [{status}]")
        summary_data[exp_name] = {
            'status': status,
            'total_configs': len(rows),
            'n_failures': len(exp_failures),
            'failure_rate': round(len(exp_failures) / len(rows), 3) if rows else 0,
        }

    os.makedirs(args.output_dir, exist_ok=True)

    csv_path = os.path.join(args.output_dir, 'failure_cases.csv')
    json_path = os.path.join(args.output_dir, 'failure_cases_summary.json')

    fieldnames = ['source_experiment', 'config_id', 'reason', 'error_m',
                  'entropy', 'hpd_cells', 'status', 'suggested_interpretation']

    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(failure_rows)

    total_failures = len(failure_rows)
    summary = {
        'experiment': 'research_failure_cases',
        'generated': datetime.now().isoformat(),
        'error_threshold_m': args.error_threshold_m,
        'entropy_threshold': args.entropy_threshold,
        'hpd_threshold': args.hpd_threshold,
        'total_failure_cases': total_failures,
        'experiments_scanned': len(EXPERIMENTS),
        'experiment_summary': summary_data,
        'key_finding': (
            f'{total_failures} failure cases across {len(EXPERIMENTS)} '
            'experiments (synthetic diagnostics only). '
            'High failure rate suggests the estimator is sensitive to configuration choices. '
            'Failure regimes should guide the Limitations section and future work directions.'
        ),
    }

    with open(json_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nTotal: {total_failures} failure cases across {len(EXPERIMENTS)} experiments")
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())