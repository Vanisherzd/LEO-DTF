#!/usr/bin/env python3
"""
Research Experiment Index
==========================
Builds a machine-readable index of all research experiments and their outputs.
Does not modify paper or docs.

Output:
  experiments/results/research_index.json
  experiments/results/research_index.md
"""

import sys, os, json
from datetime import datetime

EXPERIMENTS = [
    {
        'id': 'research_roi_grid',
        'script': 'scripts/research_roi_grid_sensitivity.py',
        'description': 'Sweeps bounded ROI size (100m-2000m) and grid step (10m-100m) for impact on localization error, posterior entropy, and HPD region.',
        'output_csv': 'experiments/results/research_roi_grid/roi_grid_trials.csv',
        'output_json': 'experiments/results/research_roi_grid/roi_grid_summary.json',
        'metrics': ['mean_error_m', 'median_error_m', 'p90_error_m', 'posterior_entropy_mean', 'hpd_cells_mean'],
        'quick_cmd': 'python scripts/research_roi_grid_sensitivity.py --quick --trials 1 --seed 42',
        'full_cmd': 'python scripts/research_roi_grid_sensitivity.py --trials 3 --seed 42',
    },
    {
        'id': 'research_duration_cadence',
        'script': 'scripts/research_duration_cadence_sensitivity.py',
        'description': 'Sweeps observation duration (60s-900s) and packet interval (5s-60s) for impact on estimator performance.',
        'output_csv': 'experiments/results/research_duration_cadence/duration_cadence_trials.csv',
        'output_json': 'experiments/results/research_duration_cadence/duration_cadence_summary.json',
        'metrics': ['num_samples', 'mean_error_m', 'posterior_entropy_mean', 'hpd_cells_mean', 'failure_rate'],
        'quick_cmd': 'python scripts/research_duration_cadence_sensitivity.py --quick --trials 1 --seed 42',
        'full_cmd': 'python scripts/research_duration_cadence_sensitivity.py --trials 3 --seed 42',
    },
    {
        'id': 'research_nuisance_prior',
        'script': 'scripts/research_nuisance_prior_sensitivity.py',
        'description': 'Sweeps CFO prior (10-1000Hz), drift prior (0.01-5Hz/s), and time offset prior (1e-4 to 5e-2s) for sensitivity analysis.',
        'output_csv': 'experiments/results/research_nuisance_prior/nuisance_prior_trials.csv',
        'output_json': 'experiments/results/research_nuisance_prior/nuisance_prior_summary.json',
        'metrics': ['mean_error_m', 'posterior_entropy_mean', 'hpd_cells_mean', 'cfo_prior_hz', 'drift_prior_hz_s'],
        'quick_cmd': 'python scripts/research_nuisance_prior_sensitivity.py --quick --trials 1 --seed 42',
        'full_cmd': 'python scripts/research_nuisance_prior_sensitivity.py --trials 3 --seed 42',
    },
    {
        'id': 'research_pass_geometry',
        'script': 'scripts/research_pass_geometry_sensitivity.py',
        'description': 'Sweeps satellite altitude (400-1200km) and inclination (30-97deg) using synthetic TLE generation to understand geometry impact.',
        'output_csv': 'experiments/results/research_pass_geometry/pass_geometry_trials.csv',
        'output_json': 'experiments/results/research_pass_geometry/pass_geometry_summary.json',
        'metrics': ['mean_error_m', 'posterior_entropy_mean', 'doppler_span_hz', 'max_elevation_deg'],
        'quick_cmd': 'python scripts/research_pass_geometry_sensitivity.py --quick --trials 1 --seed 42',
        'full_cmd': 'python scripts/research_pass_geometry_sensitivity.py --trials 3 --seed 42',
    },
    {
        'id': 'research_posterior_coverage',
        'script': 'scripts/research_posterior_coverage.py',
        'description': 'Checks HPD credible region coverage rates at 50/80/90/95 levels. Diagnostic only — not a calibration proof.',
        'output_csv': 'experiments/results/research_posterior_coverage/posterior_coverage_trials.csv',
        'output_json': 'experiments/results/research_posterior_coverage/posterior_coverage_summary.json',
        'metrics': ['coverage_50', 'coverage_80', 'coverage_90', 'coverage_95', 'mean_error_m', 'posterior_entropy_mean'],
        'quick_cmd': 'python scripts/research_posterior_coverage.py --quick --trials 3 --seed 42',
        'full_cmd': 'python scripts/research_posterior_coverage.py --trials 30 --seed 42',
    },
    {
        'id': 'research_failure_cases',
        'script': 'scripts/research_mine_failure_cases.py',
        'description': 'Aggregates failure cases from all experiments using configurable error/entropy/HPD thresholds.',
        'output_csv': 'experiments/results/research_failure_cases/failure_cases.csv',
        'output_json': 'experiments/results/research_failure_cases/failure_cases_summary.json',
        'metrics': ['total_failure_cases', 'failure_rate_per_experiment'],
        'quick_cmd': 'python scripts/research_mine_failure_cases.py --error-threshold-m 100',
        'full_cmd': 'python scripts/research_mine_failure_cases.py --error-threshold-m 100',
    },
]

def main():
    import os

    index_json = {
        'generated': datetime.now().isoformat(),
        'n_experiments': len(EXPERIMENTS),
        'experiments': [],
    }

    md_lines = [
        "# Research Experiment Index\n",
        f"*Generated: {datetime.now().isoformat()}*\n",
        f"**{len(EXPERIMENTS)} experiments**\n\n",
        "| ID | Script | Quick Command | Status |\n",
        "|---|--------|----------------|--------|\n",
    ]

    for exp in EXPERIMENTS:
        csv_exists = os.path.exists(exp['output_csv'])
        json_exists = os.path.exists(exp['output_json'])
        status = 'data-ready' if (csv_exists and json_exists) else 'not-yet-run'

        entry = {
            'id': exp['id'],
            'script': exp['script'],
            'description': exp['description'],
            'output_csv': exp['output_csv'],
            'output_json': exp['output_json'],
            'metrics': exp['metrics'],
            'quick_cmd': exp['quick_cmd'],
            'full_cmd': exp['full_cmd'],
            'status': status,
            'csv_exists': csv_exists,
            'json_exists': json_exists,
        }
        index_json['experiments'].append(entry)

        md_lines.append(
            f"| {exp['id']} | {exp['script']} | "
            f"`{exp['quick_cmd']}` | {status} |\n"
        )

    md_lines += [
        "\n## Experiment Details\n\n",
    ]
    for exp in EXPERIMENTS:
        md_lines.append(
            f"### {exp['id']}\n"
            f"- **Script**: `{exp['script']}`\n"
            f"- **Description**: {exp['description']}\n"
            f"- **Output CSV**: `{exp['output_csv']}`\n"
            f"- **Output JSON**: `{exp['output_json']}`\n"
            f"- **Metrics**: {', '.join(exp['metrics'])}\n"
            f"- **Quick**: `{exp['quick_cmd']}`\n"
            f"- **Full**: `{exp['full_cmd']}`\n\n"
        )

    out_json = 'experiments/results/research_index.json'
    out_md = 'experiments/results/research_index.md'

    with open(out_json, 'w') as f:
        json.dump(index_json, f, indent=2)

    with open(out_md, 'w') as f:
        f.writelines(md_lines)

    print(f"Index: {out_json}  ({len(EXPERIMENTS)} experiments)")
    print(f"Readme: {out_md}")
    return 0

if __name__ == '__main__':
    sys.exit(main())