#!/usr/bin/env python3
"""Smoke test for debug_forward_model_consistency.py"""

import sys, os, subprocess

def test_debug_forward_model():
    result = subprocess.run(
        [sys.executable,
         'scripts/debug_forward_model_consistency.py',
         '--seed', '42'],
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert result.returncode == 0, f"Script failed:\n{result.stderr}"
    assert 'Forward Model Consistency Check' in result.stdout
    json_path = 'experiments/results/debug_forward_model/forward_model_consistency.json'
    assert os.path.exists(json_path), f"JSON not found: {json_path}"
    import json
    with open(json_path) as f:
        data = json.load(f)
    assert 'doppler_diff_true_minus_center_mean_hz' in data
    assert 'geometry_nearly_identical' in data
    assert 'corr_pred_true_vs_center' in data
    print("test_debug_forward_model PASS")

if __name__ == '__main__':
    test_debug_forward_model()