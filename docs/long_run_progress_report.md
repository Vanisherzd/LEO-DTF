# LEO-DTF Long-Run Progress Report (Phases 25–32)

Generated: 2026-06-08

## Starting Commit
`81c2f8d` — docs: add overnight progress report

## Ending Commit
_(this document — pending)_

---

## Commits Completed (Phases 25–32)

| Phase | Hash | Message |
|-------|------|---------|
| 25 | `0a4a002` | paper: clean placeholder citation usage |
| 26 | `c3824b9` | paper: strengthen Doppler-time fingerprint formulation |
| 27 | `5c518fd` | paper: strengthen Bayesian estimator formulation |
| 28 | `d059b98` | analysis: export real posterior diagnostic heatmap |
| 29 | `23fca37` | test: add repository validation script tests |
| 30 | `febd2c7` | ci: expand smoke workflow with paper sanity checks |
| 31 | `6c577db` | docs: add submission readiness matrix |
| 32 | _(this doc)_ | docs: add long-run progress report |

---

## New Files This Run

| File | Phase |
|------|-------|
| `scripts/export_posterior_diagnostic.py` | 28 |
| `tests/test_repo_validation_scripts.py` | 29 |
| `docs/submission_readiness_matrix.md` | 31 |
| `docs/long_run_progress_report.md` | 32 |

---

## Modified Files

| File | Phase | Change |
|------|-------|--------|
| `paper/sections/06_trace_driven_hil.tex` | 25 | Added `todo_lr1121`, `todo_lora_phy`, `todo_usrp_b210` citations |
| `paper/sections/04_doppler_time_fingerprint.tex` | 26 | Added eq:fingerprint_distance (Mahalanobis separability diagnostic) |
| `paper/sections/05_bayesian_estimator.tex` | 27 | Added Notation subsection, eq:obs_vector, eq:nuisance_vec, eq:profile_score |
| `paper/sections/07_evaluation_plan.tex` | 28 | Updated posterior heatmap description to reflect real diagnostic |
| `scripts/make_paper_figures.py` | 28 | Updated to use real posterior_grid.csv if available |
| `README.md` | 25, 28, 31 | Added new scripts, updated heatmap description, added submission matrix link |
| `.github/workflows/smoke.yml` | 30 | Added check_paper_sanity.py and list_placeholder_citations.py to CI |
| `docs/placeholder_citation_report.md` | 25 | Regenerated (all 9 todos now used) |

---

## Test Status (Final)

| Check | Result |
|-------|--------|
| `check_paper_sanity.py` | PASS |
| `validate_repo_state.py` (fast) | PASS |
| `pytest -q` | **30/30 passed** (was 26 before this run; +4 tests added) |

---

## Key Improvements in This Run

1. **All 9 placeholder citations now used** — `todo_lr1121`, `todo_lora_phy`, and `todo_usrp_b210` are cited in the HIL section where hardware is discussed.

2. **Paper math strengthened** — Section 4 (DTF) now has explicit Mahalanobis distance diagnostic (eq:fingerprint_distance). Section 5 (Estimator) now has Notation subsection with explicit observation vector and nuisance vector definitions, plus profile score equation.

3. **Real posterior diagnostic** — `export_posterior_diagnostic.py` runs the estimator on a deterministic synthetic scenario and exports the full posterior grid (JSON + CSV + heatmap PDF). `make_paper_figures.py` updated to use the real diagnostic when available.

4. **CI expanded** — GitHub Actions workflow now runs `check_paper_sanity.py` and `list_placeholder_citations.py` in addition to smoke test and pytest.

5. **New subprocess tests** — `tests/test_repo_validation_scripts.py` verifies all validation scripts pass without error.

6. **Submission readiness matrix** — Documents all 20+ paper areas with honest status, evidence, remaining work, and claim risk level.

---

## Known Issues

| Issue | Severity | Notes |
|-------|----------|-------|
| 9 `todo_*` placeholder citations remain | **High** | Must be replaced with verified peer-reviewed refs before submission |
| `todo_lora_phy`, `todo_lr1121`, `todo_usrp_b210` now used but still placeholder | Medium | Correctly cited in HIL section; need real refs |
| Posterior heatmap still labeled as synthetic diagnostic | Low | Correct — should never be claimed as real-world result |
| HIL not executed | By design | Trace-driven design only; clearly documented |
| No real OTA | By design | Explicitly documented everywhere |
| No meter-level claim | By design | Coarse localization only |
| No GNSS replacement claim | By design | Complementary approach only |

---

## Recommended Next Work (Priority Order)

1. **[Blocking] Replace all 9 `todo_*` citations** — Highest priority. See `docs/placeholder_citation_report.md` for action list. Priority: `todo_sgp4`, `todo_ntn_iot`, `todo_oscillator_nuisance`, `todo_doppler_localization`, `todo_ntn_positioning`.

2. **[High] Add posterior figure to paper evaluation section** — `paper/figures/posterior_heatmap_diagnostic.pdf` now exists; add a `\begin{figure}...\end{figure}` environment in Section 7 referencing it.

3. **[High] Final abstract/introduction polish** — After citations and real results are in place, tighten abstract to remove all "placeholder" language.

4. **[Medium] Add `\begin{figure}` for posterior heatmap** — Currently the heatmap is described in text but not rendered as a LaTeX figure in the evaluation section.

5. **[Medium] Update `docs/bibliography_todo.md`** — Mark items done as citations are replaced.

6. **[Low] Add TeX Live to CI** — Currently `check_paper_sanity.py` does structural checks only; a full `pdflatex` compilation would catch more issues.

7. **[Low] Consider higher-fidelity posterior rendering** — Current heatmap uses pcolormesh; could add HPD contour overlay for paper quality.

---

## Claim Safety Summary

The repository is well-guarded against overclaims:
- `check_paper_sanity.py` — LaTeX structural + overclaim pattern check
- `validate_repo_state.py` — fast mode runs check_paper_sanity.py automatically
- `docs/claim_audit_report.md` — full claim safety audit
- `docs/submission_readiness_matrix.md` — honest status for each paper area
- `paper/sections/08_limitations.tex` — 14 explicit scope constraints

No overclaim phrases appear in the repository outside explicitly documented disclaimer contexts.