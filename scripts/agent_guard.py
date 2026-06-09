#!/usr/bin/env python3
"""
Agent-safe research automation guard for LEO-DTF.
Prevents modification of forbidden files and ensures Python syntax correctness.
"""

import subprocess
import sys
import os
from pathlib import Path

# Forbidden paths (directories and files)
FORBIDDEN = [
    "paper/",
    "docs/",
    "README.md",
    "paper/refs.bib",
    ".github/workflows/",
    "experiments/results/",
]

# Allowed paths (we can modify these)
ALLOWED_PREFIXES = [
    "scripts/agent_guard.py",
    "scripts/research_autorun.py",
    "tests/test_agent_guard.py",
    "scripts/research_",
    "tests/test_research_",
]

def is_forbidden(path: str) -> bool:
    """Check if a path is forbidden."""
    # Normalize path
    path = os.path.normpath(path)
    # Check against forbidden prefixes
    for forbidden in FORBIDDEN:
        if path.startswith(forbidden.rstrip('/')):
            return True
    return False

def is_allowed(path: str) -> bool:
    """Check if a path is allowed to be modified."""
    # Normalize path
    path = os.path.normpath(path)
    # Check against allowed prefixes
    for allowed in ALLOWED_PREFIXES:
        if path.startswith(allowed.rstrip('/')):
            return True
    return False

def main():
    # Get git status --short
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"FAIL: git status failed: {e}")
        sys.exit(1)

    lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
    modified_or_added = []

    for line in lines:
        if not line:
            continue
        # Format: XY PATH (where X is staged, Y is unstaged)
        # We care about both staged and unstaged changes
        # Take the part after the first two characters and a space
        parts = line.split()
        if len(parts) < 2:
            continue
        # The path might have spaces, but in our case it's unlikely
        # We'll join everything after the first two tokens (status chars)
        # Actually, the format is: XY PATH, where XY are two chars and a space
        # So we can take from index 3 onward
        path = line[3:]
        modified_or_added.append(path)

    # Check each modified/added file
    forbidden_found = []
    for path in modified_or_added:
        if is_forbidden(path):
            forbidden_found.append(path)

    if forbidden_found:
        print("FAIL: Forbidden files modified:")
        for path in forbidden_found:
            print(f"  {path}")
        sys.exit(1)

    # Check Python syntax for all .py files in modified_or_added
    syntax_errors = []
    for path in modified_or_added:
        if path.endswith('.py'):
            # Only check if the file exists (it should)
            if not os.path.exists(path):
                continue
            try:
                subprocess.run(
                    [sys.executable, "-m", "py_compile", path],
                    capture_output=True,
                    check=True
                )
            except subprocess.CalledProcessError as e:
                syntax_errors.append(path)

    if syntax_errors:
        print("FAIL: Python syntax errors in:")
        for path in syntax_errors:
            print(f"  {path}")
        sys.exit(1)

    # If we get here, everything is safe
    print("SAFE")
    sys.exit(0)

if __name__ == "__main__":
    main()