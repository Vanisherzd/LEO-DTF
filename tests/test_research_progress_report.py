#!/usr/bin/env python3
"""Smoke test for research_generate_progress_report.py"""

import sys, os, subprocess

def test_report():
    result = subprocess.run(
        [sys.executable,
         'scripts/research_generate_progress_report.py'],
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert result.returncode == 0, f"Script failed: {result.stderr}"
    json_path = 'experiments/results/research_progress_report.json'
    assert os.path.exists(json_path), f"JSON not found: {json_path}"

    import json
    with open(json_path) as f:
        data = json.load(f)
    assert 'observations' in data
    assert 'recommended_next_experiments' in data
    assert 'disclaimer' in data

if __name__ == '__main__':
    test_report()
    print("test_report PASS")