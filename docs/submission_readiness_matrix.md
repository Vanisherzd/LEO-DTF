# Submission Readiness Matrix

This document tracks the readiness of the LEO-DTF manuscript for conference/journal
submission. Each row represents an area of the paper or repository. Status is
honest, not optimistic.

---

## Status Key

| Status | Meaning |
|--------|---------|
| **Done** | Working code or text exists in repo; no blocking issues |
| **Partial** | Exists but has gaps (placeholder text, missing validation, etc.) |
| **Not done** | Not yet started or blocked; claiming it in the manuscript would be a overclaim |
| **N/A** | Not applicable to this work's scope |

---

## Readiness Table

| Area | Current Status | Evidence in Repo | Remaining Work | Claim Risk if Over-Stated |
|------|---------------|-----------------|-----------------|---------------------------|
| **Core method** | **Done** | `src/leodtf/estimator_grid_map.py`, `observation_model.py`, `orbit_propagation.py` | None | Medium — mathematical claims must match code |
| **System model** | **Partial** | `paper/sections/03_system_model.tex` | Needs TLE/SGP4 notation tightened; confirm all equations are consistent with code | High — system model must match implementation |
| **DTF formulation** | **Done** | `paper/sections/04_doppler_time_fingerprint.tex` (with eq:fingerprint_distance) | None | Low |
| **Bayesian estimator** | **Done** | `paper/sections/05_bayesian_estimator.tex` (with eq:obs_vector, eq:nuisance_vec, eq:profile_score) | None | Low |
| **Synthetic dataset** | **Done** | `scripts/generate_synthetic_dataset.py`; `experiments/results/synthetic/` | None | Low — clearly labeled synthetic |
| **Monte Carlo evaluation** | **Done** | `scripts/run_monte_carlo_synthetic.py`; `experiments/results/monte_carlo_*.csv` | None | Low |
| **Ambiguity ablation** | **Done** | `scripts/run_ambiguity_ablation.py`; `paper/tables/ablation_summary.tex` | Must verify N=1 trial is sufficient for paper claim | Medium — ablation must reflect real behavior |
| **CRLB diagnostic** | **Done** | `scripts/diagnose_crlb_sensitivity.py`; `paper/figures/crlb_sensitivity.pdf` | CRLB is lower bound only, not achieved error | Low if framed as lower bound |
| **Posterior heatmap** | **Done** | `scripts/export_posterior_diagnostic.py`; `paper/figures/posterior_heatmap_diagnostic.pdf` | Caption must say "preliminary synthetic diagnostic" only | High if claimed as real-world performance |
| **HIL plan** | **Partial** | `paper/sections/06_trace_driven_hil.tex`; `docs/hardware/` | HIL not executed; IQ capture not done; placeholder injector in code | Very High if claimed as validated |
| **Hardware safety** | **Done** | `docs/hardware/rf_safety_checklist.md` | None | Low |
| **Real satellite OTA validation** | **Not done** | Explicitly absent | Would require live satellite pass and USRP B210 capture | Very High if claimed |
| **Meter-level localization** | **Not done** | Explicitly absent | Not the goal; only coarse ROI | Very High if claimed |
| **GNSS replacement** | **Not done** | Explicitly absent | Not the goal; complementary approach only | Very High if claimed |
| **LR-FHSS reception on LR1121** | **Not done** | LR1121 described as transmit-only | No receiver implemented | Very High if claimed |
| **Citation completeness** | **Partial** | 9 `todo_*` placeholders remain in `paper/refs.bib` | All must be replaced with verified peer-reviewed citations before submission | High — placeholder citations weaken credibility |
| **LaTeX compilation** | **Partial** | `paper/main.tex` structure verified by `check_paper_sanity.py`; no pdflatex in CI | Need TeX Live or equivalent to compile for submission; figures currently generated via matplotlib | Medium — compilation issues only discovered at final submission |
| **CI / automated checks** | **Done** | `.github/workflows/smoke.yml` with 3 validation steps + pytest | None; CI runs on every push | Low |
| **Claim safety** | **Done** | `docs/claim_audit_report.md`, `docs/supervisor_review_checklist.md`, `check_paper_sanity.py`, `validate_repo_state.py` | Manual review still needed before submission | Low — safeguards in place |
| **Reproducibility** | **Done** | `docs/reproducibility_checklist.md`, `docs/local_setup.md`; all scripts deterministic with --seed | None | Low |
| **Bibliography quality** | **Not done** | All 9 `todo_*` entries are placeholders | Must replace with verified citations from `docs/placeholder_citation_report.md` | High |

---

## High-Priority Blocking Items Before Submission

1. **Replace all 9 `todo_*` citations** (highest priority)
   - See `docs/placeholder_citation_report.md` for action list
   - At minimum: SGP4, NTN context, oscillator nuisance, Doppler localization
   - Unused refs (`todo_lora_phy`, `todo_lr1121`, `todo_usrp_b210`) can be removed if not needed

2. **Execute HIL or explicitly downgrade HIL claims**
   - Current: HIL section says "no real satellite OTA validation is claimed"
   - If HIL is executed: replace trace-driven design with results
   - If not: confirm every figure and table clearly says "synthetic diagnostic"

3. **Verify posterior heatmap caption language**
   - Must say "preliminary synthetic diagnostic"
   - Must not say "validated on real data" or "representative performance"

4. **Check system model vs. code consistency**
   - Verify the equations in Section 3 match the actual implementation in
     `src/leodtf/observation_model.py` and `estimator_grid_map.py`

---

## Low-Priority Items (Can Be Addressed Post-First Submission)

- Add TeX Live to CI for actual paper compilation
- Replace `posterior_heatmap_diagnostic.pdf` with higher-fidelity rendering
- Tighten system model notation for journal-style rigor
- Add SOTA comparison table (if needed for specific venue)

---

## Pre-Submission Checklist (Manual)

Run these before any submission:

```bash
# All automated checks must pass
python scripts/check_paper_sanity.py          # must print "PASS"
python scripts/validate_repo_state.py          # must print "PASS"
python scripts/list_placeholder_citations.py   # review output; confirm no todo_* used in final text
pytest -q                                     # must be 30/30 passed

# Manual review
# 1. Search for "validated" in paper/sections/ — must only appear in "not validated" context
# 2. Search for "real satellite" — must only appear in limitations/disclaimer context
# 3. Search for "meter-level" — must only appear in limitations/context
# 4. Search for "GNSS replacement" — must only appear as negative disclaimer
# 5. Confirm no LR-FHSS reception claimed on LR1121
# 6. Confirm all figures say "synthetic diagnostic" or "preliminary"
# 7. Verify all table/figure captions are conservative
# 8. Confirm paper/refs.bib has zero remaining todo_* entries
```

---

## Document History

| Date | Change |
|------|--------|
| 2026-06-08 | Initial version |