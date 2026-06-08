#!/usr/bin/env python3
"""
Repository State Validator
==========================
Fast (default) checks: required files, scripts exist, conservative phrases present.
Full checks (+--full): run all evaluation scripts and pytest.

Usage:
    python scripts/validate_repo_state.py        # fast
    python scripts/validate_repo_state.py --full # comprehensive
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PYTHON = sys.executable
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"


def check_filesExist(required_files):
    """Verify required files exist."""
    missing = [f for f in required_files if not (ROOT / f).exists()]
    if missing:
        print(f"  {FAIL} Missing files: {missing}")
        return False
    print(f"  {PASS} All required files present")
    return True


def check_scriptsExist(required_scripts):
    """Verify required scripts exist."""
    missing = [s for s in required_scripts if not (ROOT / s).exists()]
    if missing:
        print(f"  {FAIL} Missing scripts: {missing}")
        return False
    print(f"  {PASS} All scripts present")
    return True


def check_conservativePhrases():
    """Check that conservative disclaimers exist in README or paper."""
    paths = [
        ROOT / "README.md",
        ROOT / "paper" / "sections" / "00_abstract.tex",
        ROOT / "paper" / "sections" / "08_limitations.tex",
    ]
    required = ["No real satellite", "GNSS replacement", "meter-level", "preliminary synthetic"]
    found = {phrase: False for phrase in required}
    for path in paths:
        if path.exists():
            content = path.read_text()
            for phrase in required:
                if phrase.lower() in content.lower():
                    found[phrase] = True
    missing = [p for p, f in found.items() if not f]
    if missing:
        print(f"  {FAIL} Missing conservative phrases: {missing}")
        return False
    print(f"  {PASS} Conservative disclaimers present in README/paper")
    return True


def run_script(name, args=None, timeout=60):
    """Run a script, return (rc, stdout)."""
    cmd = [PYTHON, str(ROOT / "scripts" / name)]
    if args:
        cmd.extend(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"


def run_quick_checks():
    """Run fast checks without executing scripts."""
    print("\n=== Quick Checks ===")
    ok = True

    print("Checking required files...")
    required_files = [
        "README.md",
        "paper/main.tex",
        "paper/sections/00_abstract.tex",
        "paper/sections/07_evaluation_plan.tex",
        "docs/reproducibility_checklist.md",
        "docs/supervisor_review_checklist.md",
    ]
    ok &= check_filesExist(required_files)

    print("Checking required scripts...")
    required_scripts = [
        "scripts/generate_synthetic_dataset.py",
        "scripts/run_monte_carlo_synthetic.py",
        "scripts/diagnose_crlb_sensitivity.py",
        "scripts/run_ambiguity_ablation.py",
        "scripts/summarize_evaluation.py",
        "scripts/make_paper_figures.py",
        "scripts/run_smoke_test.py",
        "scripts/validate_repo_state.py",
        "scripts/check_paper_sanity.py",
    ]
    ok &= check_scriptsExist(required_scripts)

    print("Checking conservative phrases...")
    ok &= check_conservativePhrases()

    print("Checking paper LaTeX structure...")
    rc, out, err = run_script("check_paper_sanity.py", timeout=30)
    status = PASS if rc == 0 else f"{FAIL} (rc={rc})"
    print(f"  {status} check_paper_sanity.py")
    if rc != 0:
        ok = False
        # Print first few lines of output for debugging
        for line in out.splitlines()[:5]:
            print(f"    {line}")

    return ok


def run_full_checks():
    """Run all evaluation scripts and tests."""
    print("\n=== Full Checks ===")
    ok = True

    tests = [
        ("generate_synthetic_dataset.py", [], 60),
        ("run_monte_carlo_synthetic.py", ["--trials", "5"], 60),
        ("diagnose_crlb_sensitivity.py", [], 60),
        ("run_ambiguity_ablation.py", ["--trials", "5", "--seed", "42"], 60),
        ("summarize_evaluation.py", [], 60),
        ("make_paper_figures.py", [], 60),
        ("run_smoke_test.py", [], 60),
    ]

    for name, args, timeout in tests:
        rc, out, err = run_script(name, args, timeout)
        status = PASS if rc == 0 else f"{FAIL} (rc={rc})"
        print(f"  {status} {name}")
        if rc != 0:
            ok = False
            print(f"    STDERR: {err[:200]}")

    print("Running pytest...")
    rc, out, err = run_script("-m", ["pytest", "tests/", "-q"], timeout=120)
    status = PASS if rc == 0 else f"{FAIL} (rc={rc})"
    print(f"  {status} pytest")
    if rc != 0:
        ok = False

    return ok


def main():
    parser = argparse.ArgumentParser(description="Validate LEO-DTF repo state")
    parser.add_argument("--full", action="store_true",
                        help="Run full evaluation pipeline (default: fast checks only)")
    args = parser.parse_args()

    print(f"LEO-DTF Repository Validator (full={args.full})")
    print(f"Repo root: {ROOT}")

    quick_ok = run_quick_checks()
    full_ok = run_full_checks() if args.full else True

    print()
    if quick_ok and full_ok:
        print(f"{PASS} Repository state valid")
        return 0
    else:
        print(f"{FAIL} Repository state issues detected")
        return 1


if __name__ == "__main__":
    sys.exit(main())