#!/usr/bin/env python3
"""
Research automation runner for LEO-DTF.
Runs a set of research scripts and tests, then runs the agent guard.
"""

import subprocess
import sys
import os

def run_command(cmd, check=True):
    """Run a command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check
        )
        print(result.stdout)
        if result.stderr:
            print(f"STDERR: {result.stderr}")
        return result
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {' '.join(cmd)}")
        print(f"Exit code: {e.returncode}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        if check:
            sys.exit(e.returncode)
        return e

def main():
    # Change to the repository root
    repo_root = "/tmp/LEO-DTF"
    os.chdir(repo_root)

    # List of research scripts to run with --quick --seed 42
    research_scripts = [
        "scripts/research_multipass_observability.py",
        "scripts/research_multisat_geometry_observability.py",
        "scripts/research_packet_budget_threshold.py",
    ]

    # Run each research script
    for script in research_scripts:
        if not os.path.exists(script):
            print(f"WARNING: Research script not found: {script}")
            continue
        run_command([
            "uv", "run", "python", script,
            "--quick", "--seed", "42"
        ])

    # Run focused tests
    test_scripts = [
        "tests/test_research_multipass_observability.py",
        "tests/test_research_multisat_geometry_observability.py",
        "tests/test_research_packet_budget_threshold.py",
    ]

    for test_file in test_scripts:
        if not os.path.exists(test_file):
            print(f"WARNING: Test file not found: {test_file}")
            continue
        run_command([
            "uv", "run", "--extra", "test", "pytest", test_file, "-q"
        ])

    # Finally, run the agent guard
    print("\nRunning agent guard...")
    result = run_command([
        "uv", "run", "python", "scripts/agent_guard.py"
    ], check=False)
    # Exit with the same code as agent_guard
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()