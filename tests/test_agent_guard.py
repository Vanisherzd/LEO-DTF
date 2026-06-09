#!/usr/bin/env python3
"""
Test for agent_guard.py
"""
import subprocess
import sys
import tempfile
import os
from pathlib import Path

def run_guard(args=[]):
    """Run agent_guard.py with given args and return (exit_code, stdout, stderr)."""
    cmd = [sys.executable, "scripts/agent_guard.py"] + args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd="/tmp/LEO-DTF"
    )
    return result.returncode, result.stdout, result.stderr

def test_clean_repo():
    """Test that a clean repo passes."""
    exit_code, stdout, stderr = run_guard()
    assert exit_code == 0, f"Expected exit code 0, got {exit_code}. STDOUT: {stdout}, STDERR: {stderr}"
    assert "SAFE" in stdout, f"Expected 'SAFE' in output, got: {stdout}"

def test_forbidden_path_detection(monkeypatch):
    """Test that forbidden paths are detected without actually modifying forbidden files."""
    # We'll test the guard function directly by importing it? 
    # Instead, we can simulate by creating a temporary forbidden file in a safe location
    # and then check if the guard would catch it by checking the logic.
    # Since we cannot modify paper/, we'll test the is_forbidden function.
    # Let's import the guard module and test its functions.
    sys.path.insert(0, "/tmp/LEO-DTF/scripts")
    from agent_guard import is_forbidden, is_allowed
    
    # Test forbidden paths
    assert is_forbidden("paper/somefile.pdf") == True
    assert is_forbidden("docs/guide.md") == True
    assert is_forbidden("README.md") == True
    assert is_forbidden("paper/refs.bib") == True
    assert is_forbidden(".github/workflows/ci.yml") == True
    assert is_forbidden("experiments/results/data.json") == True
    
    # Test allowed paths
    assert is_allowed("scripts/agent_guard.py") == True
    assert is_allowed("scripts/research_autorun.py") == True
    assert is_allowed("tests/test_agent_guard.py") == True
    assert is_allowed("scripts/research_multipass_observability.py") == True
    assert is_allowed("tests/test_research_multipass_observability.py") == True
    
    # Test edge cases
    assert is_forbidden("paper") == True  # without trailing slash
    assert is_forbidden("PAPER/") == False  # case-sensitive? We'll assume not, but our check is case-sensitive.
    # The actual check uses startswith with the exact string, so we'll keep as is.

def test_allowed_paths():
    """Test that allowed paths are permitted."""
    sys.path.insert(0, "/tmp/LEO-DTF/scripts")
    from agent_guard import is_allowed
    
    # These should be allowed
    assert is_allowed("scripts/research_new.py") == True
    assert is_allowed("tests/test_research_new.py") == True
    assert is_allowed("scripts/research_") == True  # prefix
    assert is_allowed("tests/test_research_") == True

if __name__ == "__main__":
    # Run tests
    test_clean_repo()
    test_forbidden_path_detection()
    test_allowed_paths()
    print("All tests passed!")