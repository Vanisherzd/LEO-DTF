"""
Repository Validation Script Tests
===================================
Verify that the validation and sanity-check scripts run without error.
Each test runs a script as a subprocess and asserts exit code 0.

Run with: pytest tests/test_repo_validation_scripts.py -v
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PYTHON = sys.executable


def run(script_name, args=None, timeout=60):
    """Run a script and return (returncode, stdout, stderr)."""
    cmd = [PYTHON, str(ROOT / "scripts" / script_name)]
    if args:
        cmd.extend(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.returncode, result.stdout, result.stderr


def test_check_paper_sanity():
    """check_paper_sanity.py must pass with exit 0."""
    rc, out, err = run("check_paper_sanity.py")
    assert rc == 0, (
        f"check_paper_sanity.py failed (rc={rc}).\n"
        f"STDOUT:\n{out}\n\nSTDERR:\n{err}"
    )


def test_validate_repo_state_fast():
    """validate_repo_state.py (fast mode) must pass with exit 0."""
    rc, out, err = run("validate_repo_state.py")
    assert rc == 0, (
        f"validate_repo_state.py failed (rc={rc}).\n"
        f"STDOUT:\n{out}\n\nSTDERR:\n{err}"
    )


def test_list_placeholder_citations():
    """list_placeholder_citations.py must run without error."""
    rc, out, err = run("list_placeholder_citations.py")
    assert rc == 0, (
        f"list_placeholder_citations.py failed (rc={rc}).\n"
        f"STDOUT:\n{out}\n\nSTDERR:\n{err}"
    )


def test_export_posterior_diagnostic_if_available():
    """export_posterior_diagnostic.py must run without error if it exists."""
    script = ROOT / "scripts" / "export_posterior_diagnostic.py"
    if not script.exists():
        # Script is optional (only exists after Phase 28)
        return

    rc, out, err = run("export_posterior_diagnostic.py", timeout=120)
    assert rc == 0, (
        f"export_posterior_diagnostic.py failed (rc={rc}).\n"
        f"STDOUT:\n{out}\n\nSTDERR:\n{err}"
    )
    # Verify output was produced
    json_path = ROOT / "experiments" / "results" / "posterior" / "posterior_grid.json"
    csv_path = ROOT / "experiments" / "results" / "posterior" / "posterior_grid.csv"
    assert json_path.exists(), f"Expected output not found: {json_path}"
    assert csv_path.exists(), f"Expected output not found: {csv_path}"