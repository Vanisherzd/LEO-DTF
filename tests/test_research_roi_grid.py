#!/usr/bin/env python3
"""
Smoke test for research_roi_grid_sensitivity.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_research_roi_grid_quick():
    import subprocess
    result = subprocess.run(
        [sys.executable,
         'scripts/research_roi_grid_sensitivity.py',
         '--quick', '--trials', '1', '--seed', '42'],
        capture_output=True, text=True, cwd=os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
    assert result.returncode == 0, f"Script failed: {result.stderr}"
    csv_path = 'experiments/results/research_roi_grid/roi_grid_trials.csv'
    json_path = 'experiments/results/research_roi_grid/roi_grid_summary.json'
    assert os.path.exists(csv_path), f"CSV not found: {csv_path}"
    assert os.path.exists(json_path), f"JSON not found: {json_path}"

    import json
    with open(json_path) as f:
        data = json.load(f)
    assert 'configs' in data
    assert len(data['configs']) == 2  # QUICK_CONFIGS has 2 entries
    for cfg in data['configs']:
        assert 'roi_half_width_m' in cfg
        assert 'grid_step_m' in cfg
        assert 'mean_error_m' in cfg
        assert 'grid_cell_count' in cfg

if __name__ == '__main__':
    test_research_roi_grid_quick()
    print("test_research_roi_grid_quick PASS")