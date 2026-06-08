#!/usr/bin/env python3
"""Smoke test for debug_coordinate_grid_consistency.py"""

import sys, os, subprocess

def test_debug_coordinate_grid():
    result = subprocess.run(
        [sys.executable,
         'scripts/debug_coordinate_grid_consistency.py',
         '--seed', '42'],
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert result.returncode == 0, f"Script failed:\n{result.stderr}"
    assert 'MAP error:' in result.stdout, f"Expected MAP error output, got:\n{result.stdout}"
    json_path = 'experiments/results/debug_coordinate_grid/coordinate_grid_diagnostic.json'
    assert os.path.exists(json_path), f"JSON not found: {json_path}"
    import json
    with open(json_path) as f:
        data = json.load(f)
    assert data['true_in_grid'] is True
    assert 'map_error_m' in data
    assert 'enu_roundtrip_error_m' in data
    print("test_debug_coordinate_grid PASS")

if __name__ == '__main__':
    test_debug_coordinate_grid()