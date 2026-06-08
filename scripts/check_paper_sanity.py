#!/usr/bin/env python3
"""
LaTeX / Paper Sanity Checker
============================
Perform structural checks on the paper LaTeX sources without requiring
pdflatex. Optionally attempt compilation if pdflatex is available.

Usage:
    python scripts/check_paper_sanity.py
    python scripts/check_paper_sanity.py --try-compile

Exit codes:
    0  all structural checks pass
    1  one or more checks failed
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PAPER = ROOT / "paper"
MAIN_TEX = PAPER / "main.tex"
REFS_BIB = PAPER / "refs.bib"
SECTIONS_DIR = PAPER / "sections"
FIGURES_DIR = PAPER / "figures"
TABLES_DIR = PAPER / "tables"

# Forbidden phrases — report only if NOT in a disclaimer context
# We look for negative/disclaimer usage and skip it
FORBIDDEN_PATTERNS = [
    re.compile(r"meter-level\s+accuracy\s+achieved", re.IGNORECASE),
    re.compile(r"real\s+satellite\s+ota\s+validation\s+claimed", re.IGNORECASE),
    re.compile(r"gnss\s+replacement\b(?!\s+is\s+not)", re.IGNORECASE),
    re.compile(r"outperforms\s+state-of-the-art", re.IGNORECASE),
    re.compile(r"lr1121.*receiver", re.IGNORECASE),
]

# Lines that contain explicit negations — safe disclaimers, not overclaims
DISCLAIMER_PATTERNS = [
    re.compile(r"not\s+.*\bgnss\s+replacement\b", re.IGNORECASE),
    re.compile(r"no\s+gnss\s+replacement", re.IGNORECASE),
    re.compile(r"no\s+real\s+satellite", re.IGNORECASE),
    re.compile(r"no\s+meter-level", re.IGNORECASE),
    re.compile(r"explicitly\s+outside\s+scope", re.IGNORECASE),
    re.compile(r"scope.*meter", re.IGNORECASE),
    re.compile(r"no\s+ota", re.IGNORECASE),
    re.compile(r"no\s+operational", re.IGNORECASE),
]


def log(msg):
    print(msg)


def is_disclaimer_context(content, lineno, window=3):
    """Return True if 'GNSS replacement' near scope-limiting language within window."""
    lines = content.splitlines()
    start = max(0, lineno - window)
    end = min(len(lines), lineno + window + 1)
    window_text = " ".join(lines[start:end]).lower()
    return any(pat.search(window_text) for pat in DISCLAIMER_PATTERNS)


def check_main_exists():
    if not MAIN_TEX.exists():
        return False, f"{MAIN_TEX} does not exist"
    return True, None


def find_input_files(content):
    """Find all \\input{} paths in .tex content."""
    return re.findall(r'\\input\{([^}]+)\}', content)


def find_includegraphics(content):
    """Find all \\includegraphics paths."""
    return re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}', content)


def find_cites(content):
    """Find all \\cite{...} keys."""
    return re.findall(r'\\cite[pt]?\{([^}]+)\}', content)


def find_refs(content):
    """Find all \\ref{...} labels."""
    return re.findall(r'\\ref\{([^}]+)\}', content)


def load_bib_keys():
    """Return set of citation keys in refs.bib."""
    if not REFS_BIB.exists():
        return set()
    return set(re.findall(r'@\w+\{([^,]+),', REFS_BIB.read_text()))


def resolve_input_path(input_path):
    """Resolve a \\input{} path to an existing file, trying .tex extension."""
    p = PAPER / input_path
    if p.exists():
        return p
    # Try adding .tex
    p_tex = PAPER / (input_path + ".tex")
    if p_tex.exists():
        return p_tex
    return p  # return original, mark as missing


def run_checks(args):
    failures = []
    warnings = []

    # --- 1. main.tex exists ---
    ok, err = check_main_exists()
    if not ok:
        failures.append(f"FAIL: {err}")
        return failures, warnings

    main_content = MAIN_TEX.read_text()

    # --- 2. All \\input paths exist ---
    for input_path in find_input_files(main_content):
        full = resolve_input_path(input_path)
        if not full.exists():
            failures.append(f"FAIL: \\input{{{input_path}}} → file not found: {full}")

    # --- 3. All \\includegraphics files exist ---
    for img_path in find_includegraphics(main_content):
        full = FIGURES_DIR / img_path
        if not full.exists():
            failures.append(f"FAIL: \\includegraphics{{{img_path}}} → file not found: {full}")

    # --- 4. All \\cite keys in refs.bib ---
    bib_keys = load_bib_keys()
    for section_file in SECTIONS_DIR.glob("*.tex"):
        content = section_file.read_text()
        for key in find_cites(content):
            if key not in bib_keys and not key.startswith("todo_"):
                failures.append(
                    f"FAIL: \\cite{{{key}}} in {section_file.name} → key not in {REFS_BIB}"
                )

    # --- 5. All \\ref labels have a definition ---
    all_labels = set()
    for tex_file in list(SECTIONS_DIR.glob("*.tex")) + [MAIN_TEX]:
        all_labels.update(re.findall(r'\\label\{([^}]+)\}', tex_file.read_text()))
    for table_file in TABLES_DIR.glob("*.tex"):
        all_labels.update(re.findall(r'\\label\{([^}]+)\}', table_file.read_text()))

    for section_file in SECTIONS_DIR.glob("*.tex"):
        content = section_file.read_text()
        for label in find_refs(content):
            if label not in all_labels:
                warnings.append(
                    f"WARN: \\ref{{{label}}} in {section_file.name} → label not defined "
                    f"(found labels: {sorted(all_labels)})"
                )

    # --- 6. Check for forbidden overclaim patterns (skip disclaimers) ---
    for section_file in SECTIONS_DIR.glob("*.tex"):
        content = section_file.read_text()
        lines = content.splitlines()
        for lineno, line in enumerate(lines):
            # Skip if this region is clearly a disclaimer
            if is_disclaimer_context(content, lineno, window=3):
                continue
            for pattern in FORBIDDEN_PATTERNS:
                if pattern.search(line):
                    failures.append(
                        f"FAIL: overclaim pattern '{pattern.pattern}' "
                        f"found in {section_file.name}: {line.strip()[:80]}"
                    )

    return failures, warnings


def try_compile():
    """Attempt pdflatex compilation if available."""
    result = subprocess.run(
        ["which", "pdflatex"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log("pdflatex not available; structural checks only.")
        return

    log("Attempting pdflatex compilation...")
    result = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "main.tex"],
        capture_output=True,
        text=True,
        cwd=PAPER,
        timeout=60,
    )
    if result.returncode == 0:
        log("pdflatex compilation succeeded.")
    else:
        log(f"pdflatex compilation had errors (exit {result.returncode}).")
        log("Check paper/main.log for details.")


def main():
    parser = argparse.ArgumentParser(description="Check paper LaTeX sanity")
    parser.add_argument(
        "--try-compile",
        action="store_true",
        help="Attempt pdflatex compilation if available",
    )
    args = parser.parse_args()

    failures, warnings = run_checks(args)

    for w in warnings:
        log(w)

    if failures:
        log("\n=== SANITY CHECK FAILURES ===")
        for f in failures:
            log(f)
        log("\nSanity check: FAIL")
        sys.exit(1)
    else:
        if warnings:
            log(f"\nSanity check: PASS ({len(warnings)} warning(s) above)")
        else:
            log("\nSanity check: PASS")

    if args.try_compile:
        try_compile()

    sys.exit(0)


if __name__ == "__main__":
    main()