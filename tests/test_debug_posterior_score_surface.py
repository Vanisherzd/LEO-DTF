#!/usr/bin/env python3
"""Smoke test for debug_posterior_score_surface.py"""

import sys, os, subprocess

def test_debug_posterior_score():
    result = subprocess.run(
        [sys.executable,
         'scripts/debug_posterior_score_surface.py',
         '--seed', '42'],
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert result.returncode == 0, f"Script failed:\n{result.stderr}"
    assert 'Score at TRUE cell:' in result.stdout
    json_path = 'experiments/results/debug_posterior_score/posterior_score_surface.json'
    assert os.path.exists(json_path), f"JSON not found: {json_path}"
    import json
    with open(json_path) as f:
        data = json.load(f)
    assert 'map_error_m' in data
    assert 'posterior_sum' in data
    print("test_debug_posterior_score PASS")

if __name__ == '__main__':
    test_debug_posterior_score()