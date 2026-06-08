#!/usr/bin/env python3
"""Smoke test for research_pass_geometry_sensitivity.py"""

import sys, os, subprocess

def test_quick():
    result = subprocess.run(
        [sys.executable,
         'scripts/research_pass_geometry_sensitivity.py',
         '--quick', '--trials', '1', '--seed', '42'],
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert result.returncode == 0, f"Script failed: {result.stderr}"
    json_path = 'experiments/results/research_pass_geometry/pass_geometry_summary.json'
    assert os.path.exists(json_path), f"JSON not found: {json_path}"

    import json
    with open(json_path) as f:
        data = json.load(f)
    assert 'configs' in data
    assert len(data['configs']) == 2  # QUICK_CONFIGS has 2 entries

if __name__ == '__main__':
    test_quick()
    print("test_quick PASS")