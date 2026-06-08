#!/usr/bin/env python3
"""Smoke test for debug_oracle_nuisance_baseline.py"""

import sys, os, subprocess

def test_oracle():
    result = subprocess.run(
        [sys.executable, 'scripts/debug_oracle_nuisance_baseline.py',
         '--trials', '1', '--seed', '42'],
        capture_output=True, text=True)
    assert result.returncode == 0, f"script failed: {result.stderr}"
    path = 'experiments/results/debug_oracle_nuisance/oracle_nuisance_baseline.json'
    assert os.path.exists(path), f"{path} not created"
    print("test_oracle PASS")
    return 0

if __name__ == '__main__':
    sys.exit(test_oracle() or 0)