#!/usr/bin/env python3
"""Smoke test for research_mine_failure_cases.py"""

import sys, os, subprocess

def test_mine():
    result = subprocess.run(
        [sys.executable,
         'scripts/research_mine_failure_cases.py',
         '--error-threshold-m', '100'],
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert result.returncode == 0, f"Script failed: {result.stderr}"
    assert 'failure_cases_summary.json' in result.stdout
    json_path = 'experiments/results/research_failure_cases/failure_cases_summary.json'
    assert os.path.exists(json_path), f"JSON not found: {json_path}"

    import json
    with open(json_path) as f:
        data = json.load(f)
    assert 'total_failure_cases' in data
    assert data['experiments_scanned'] == 5
    assert data['total_failure_cases'] > 0

if __name__ == '__main__':
    test_mine()
    print("test_mine PASS")