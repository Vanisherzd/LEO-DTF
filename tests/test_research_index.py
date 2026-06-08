#!/usr/bin/env python3
"""Smoke test for research_build_experiment_index.py"""

import sys, os, subprocess

def test_index():
    result = subprocess.run(
        [sys.executable,
         'scripts/research_build_experiment_index.py'],
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert result.returncode == 0, f"Script failed: {result.stderr}"
    json_path = 'experiments/results/research_index.json'
    assert os.path.exists(json_path), f"JSON not found: {json_path}"

    import json
    with open(json_path) as f:
        data = json.load(f)
    assert data['n_experiments'] == 6
    assert len(data['experiments']) == 6
    ids = [e['id'] for e in data['experiments']]
    assert 'research_roi_grid' in ids
    assert 'research_posterior_coverage' in ids

if __name__ == '__main__':
    test_index()
    print("test_index PASS")