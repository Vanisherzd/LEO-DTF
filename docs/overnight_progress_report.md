# LEO-DTF Overnight Progress Report

Generated: 2026-06-08

## Commits Completed This Run (Phases 17–24)

| # | Hash | Message |
|---|------|---------|
| 17 | `75e6e46` | chore: remove Hermes-specific Python path assumptions |
| 18 | `60f38b1` | ci: add GitHub Actions smoke workflow |
| 19 | `9d569a2` | test: add deterministic reproducibility checks |
| 20 | `6f1f868` | docs: add local setup guide |
| 21 | `870f022` | paper: add LaTeX sanity checker and fix tab ref mismatch |
| 22 | `413a616` | docs: add claim audit report |
| 23 | `f056ceb` | paper: add placeholder citation report |
| 24 | (pending) | docs: add overnight progress report |

## Latest Git Log (top 20)

```
f056ceb paper: add placeholder citation report
413a616 docs: add claim audit report
870f022 paper: add LaTeX sanity checker and fix tab ref mismatch
6f1f868 docs: add local setup guide
9d569a2 test: add deterministic reproducibility checks
60f38b1 ci: add GitHub Actions smoke workflow
75e6e46 chore: remove Hermes-specific Python path assumptions
852f995 chore: ignore generated local artifacts
5919025 paper: polish manuscript language
616410a chore: add repository validation script
db42ac4 paper: mark placeholder citations and bibliography debt
8278829 docs: add supervisor review checklist
d9c5f49 test: add CLI artifact smoke tests
61e5229 docs: add reproducibility checklist
194bb36 paper: integrate preliminary results into manuscript draft
...
```

## Test Status

| Check | Result |
|-------|--------|
| `validate_repo_state.py` | PASS |
| `check_paper_sanity.py` | PASS |
| `pytest -q` | 26/26 passed |

## New Files Added This Run

| File | Phase |
|------|-------|
| `.github/workflows/smoke.yml` | 18 |
| `tests/test_reproducibility.py` | 19 |
| `docs/local_setup.md` | 20 |
| `scripts/check_paper_sanity.py` | 21 |
| `docs/claim_audit_report.md` | 22 |
| `scripts/list_placeholder_citations.py` | 23 |
| `docs/placeholder_citation_report.md` | 23 |
| `docs/overnight_progress_report.md` | 24 |

## New Tests Added This Run

- `tests/test_reproducibility.py`: 3 tests (deterministic RNG check, tex validity, different-seed variation)

Total test count: 26 (was 23 before this run)

## New Documentation

- `docs/local_setup.md` — Step-by-step guide for fresh clone to reproduce all artifacts
- `docs/claim_audit_report.md` — Claim safety audit with allowed/prohibited list, high-risk sections, manual review checklist
- `docs/placeholder_citation_report.md` — Table of 9 `todo_*` placeholders with suggested replacement actions
- `docs/overnight_progress_report.md` — This report
- `.github/workflows/smoke.yml` — GitHub Actions CI for smoke + validate + pytest

## New Scripts

- `scripts/check_paper_sanity.py` — LaTeX structural checker (no pdflatex required). Checks `\input{}`, `\includegraphics{}`, `\cite{}`, `\ref{}` validity. Disallows overclaim patterns outside disclaimer context.
- `scripts/list_placeholder_citations.py` — Parses `refs.bib` for `todo_*` keys and reports where each is used in sections.

## Bug Fixes This Run

1. Replaced hardcoded `/opt/hermes/.venv/bin/python3` with `sys.executable` in `validate_repo_state.py` and `test_cli_artifacts.py`
2. Fixed `\\ref{tab:ablation-summary}` → `\\ref{tab:ablation}` mismatch in `07_evaluation_plan.tex`
3. Updated `check_paper_sanity.py` to handle multi-line disclaimer context (e.g., "GNSS replacement are explicitly outside the scope" spans two lines)

## Known Issues

| Issue | Severity | Notes |
|-------|----------|-------|
| 9 placeholder citations (`todo_*`) in `paper/refs.bib` | High | Must be replaced with verified citations before submission |
| `todo_lora_phy`, `todo_lr1121`, `todo_usrp_b210` are defined but **unused** in any section | Medium | Should be removed or cited |
| Toy posterior heatmap (`paper/figures/posterior_heatmap_placeholder.pdf`) | Low | Marked as placeholder; needs real result when HIL/run executed |
| HIL not executed | Low | Trace-driven design only; no live satellite data |
| No real OTA validation | By design | Explicitly documented everywhere |
| No meter-level claim | By design | Coarse localization only |
| No GNSS replacement claim | By design | Explicitly outside scope |

## Recommended Next Commits (Priority Order)

1. **`paper: replace all todo_* citations with verified references`** — Highest priority before submission. See `docs/placeholder_citation_report.md` for the full list.

2. **`paper: add DTF model equations section`** — Current sections 04/05 are placeholders; need real mathematical formulation.

3. **`paper: add evaluation results when HIL executed`** — `paper/figures/posterior_heatmap_placeholder.pdf` needs to be replaced with real output.

4. **`test: add test for check_paper_sanity.py`** — Add a test that runs check_paper_sanity.py as a subprocess and asserts PASS.

5. **`paper: tighten system model section`** — Section 03 has TODOs; needs completion with proper notation.

6. **`chore: update pyproject.toml classifiers`** — Add proper classifiers: "Development Status :: 3 - Alpha", "Topic :: Scientific/Engineering", etc.

7. **`docs: update bibliography_todo.md`** — Mark items as done as citations are replaced.

8. **`paper: final abstract/introduction polish`** — After citations are replaced and evaluation results exist.

## Claim Safety Summary

All manuscripts and docs are guarded by:
- `scripts/validate_repo_state.py` (fast checks + check_paper_sanity.py integration)
- `scripts/check_paper_sanity.py` (LaTeX structural + overclaim pattern check)
- `paper/sections/08_limitations.tex` (14 explicit scope constraints)
- `docs/claim_audit_report.md` (full claim safety audit)
- `docs/supervisor_review_checklist.md` (human review gate)

No overclaim phrases appear in the repository outside of explicitly documented disclaimer contexts.