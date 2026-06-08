#!/usr/bin/env python3
"""Smoke test for research_roi_grid_sensitivity.py"""

import sys, os, subprocess

def test_quick():
    result = subprocess.run(
        [sys.executable,
         'scripts/research_roi_grid_sensitivity.py',
         '--quick', '--trials', '1', '--seed', '42'],
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert result.returncode == 0, f"Script failed: {result.stderr}"
    assert 'roi_grid_summary.json' in result.stdout
    json_path = 'experiments/results/research_roi_grid/roi_grid_summary.json'
    assert os.path.exists(json_path), f"JSON not found: {json_path}"

    import json
    with open(json_path) as f:
        data = json.load(f)
    assert 'configs' in data
    assert data['n_success'] > 0
    # Check no NaN in mean metrics
    assert not (data.get('mean_error_m') != data.get('mean_error_m')), "mean_error_m is NaN"

if __name__ == '__main__':
    test_quick()
    print("test_quick PASS")