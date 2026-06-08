#!/usr/bin/env python3
"""Smoke test for research_posterior_coverage.py"""

import sys, os, subprocess

def test_quick():
    result = subprocess.run(
        [sys.executable,
         'scripts/research_posterior_coverage.py',
         '--quick', '--trials', '3', '--seed', '42'],
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert result.returncode == 0, f"Script failed: {result.stderr}"
    json_path = 'experiments/results/research_posterior_coverage/posterior_coverage_summary.json'
    assert os.path.exists(json_path), f"JSON not found: {json_path}"

    import json
    with open(json_path) as f:
        data = json.load(f)
    assert 'coverage_50' in data
    assert 'calibration_note' in data
    assert data['n_trials'] == 3
    assert 'coverage_95' in data

if __name__ == '__main__':
    test_quick()
    print("test_quick PASS")