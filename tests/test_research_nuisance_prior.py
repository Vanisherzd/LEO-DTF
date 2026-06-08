#!/usr/bin/env python3
"""Smoke test for research_nuisance_prior_sensitivity.py"""

import sys, os, subprocess

def test_quick():
    result = subprocess.run(
        [sys.executable,
         'scripts/research_nuisance_prior_sensitivity.py',
         '--quick', '--trials', '1', '--seed', '42'],
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert result.returncode == 0, f"Script failed: {result.stderr}"
    json_path = 'experiments/results/research_nuisance_prior/nuisance_prior_summary.json'
    assert os.path.exists(json_path), f"JSON not found: {json_path}"

    import json
    with open(json_path) as f:
        data = json.load(f)
    assert 'configs' in data
    assert len(data['configs']) == 3  # QUICK_CONFIGS has 3 entries
    for cfg in data['configs']:
        assert 'label' in cfg
        assert 'mean_error_m' in cfg

if __name__ == '__main__':
    test_quick()
    print("test_quick PASS")