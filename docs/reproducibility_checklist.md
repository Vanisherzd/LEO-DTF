# LEO-DTF Reproducibility Checklist

## 1. Repository State

- **Branch:** `main`
- **Latest commit:** `194bb36` (paper: integrate preliminary results into manuscript draft)
- **Python:** 3.x (tested with `/opt/hermes/.venv/bin/python3`)
- **Dependencies:** installed via `uv pip install -e .` from repo root

## 2. Core Scripts

| Script | Purpose | Expected Output | Status |
|--------|---------|-----------------|--------|
| `scripts/run_smoke_test.py` | Quick pipeline smoke test | Terminal output with pass/fail | ✓ |
| `scripts/generate_synthetic_dataset.py` | Deterministic synthetic pass | `synthetic_pass_dataset.json`, `synthetic_pass_observations.csv` | ✓ |
| `scripts/run_monte_carlo_synthetic.py` | Monte Carlo diagnostic | `montecarlo_trials.csv`, `montecarlo_summary.json` | ✓ |
| `scripts/diagnose_crlb_sensitivity.py` | CRLB noise sweep | `crlb_sensitivity.csv`, `crlb_sensitivity_summary.json` | ✓ |
| `scripts/run_ambiguity_ablation.py` | Ambiguity/ablation study | `ambiguity_ablation_trials.csv`, `ambiguity_ablation_summary.json`, `ablation_summary.tex` | ✓ |
| `scripts/summarize_evaluation.py` | Aggregate summary | `evaluation_summary.md`, `evaluation_summary.json`, `evaluation_summary.tex` | ✓ |
| `scripts/make_paper_figures.py` | Paper figures from results | PDF figures in `paper/figures/` | ✓ |

## 3. Generated Artifacts

All under `experiments/results/`:

- `synthetic/` — deterministic synthetic pass dataset (JSON + CSV)
- `montecarlo/` — Monte Carlo trials (CSV + JSON summary)
- `crlb/` — CRLB sensitivity sweep (CSV + JSON summary)
- `ablation/` — ambiguity ablation study (CSV + JSON summary + LaTeX table)
- `evaluation_summary.json` / `.md` / `.tex` — aggregated summary

Tables and figures:
- `paper/tables/evaluation_summary.tex`
- `paper/tables/ablation_summary.tex`
- `paper/figures/dtf_concept.pdf` — from synthetic data
- `paper/figures/ablation_summary.pdf` — bar chart from ablation JSON
- `paper/figures/crlb_sensitivity.pdf` — log-log from CRLB CSV
- `paper/figures/posterior_heatmap_placeholder.pdf` — **toy Gaussian only**, not from estimator

## 4. Manuscript Scope

> **IMPORTANT:** All results in the current manuscript draft are **preliminary synthetic diagnostics**. The following are explicitly not claimed:

- No real satellite over-the-air (OTA) validation
- No meter-level localization accuracy
- No GNSS replacement capability
- No operational deployment

The trace-driven HIL plan (Section 6 of the paper) is **planned/documented only**. No IQ captures have been executed.

## 5. Reproduction Commands

```bash
# Minimal verification
python scripts/run_smoke_test.py
python scripts/run_ambiguity_ablation.py --trials 3 --seed 42
python scripts/summarize_evaluation.py
pytest -q

# Full pipeline (takes ~2 minutes)
python scripts/generate_synthetic_dataset.py
python scripts/run_monte_carlo_synthetic.py --trials 5
python scripts/diagnose_crlb_sensitivity.py
python scripts/run_ambiguity_ablation.py --trials 5 --seed 42
python scripts/summarize_evaluation.py
python scripts/make_paper_figures.py
python scripts/run_smoke_test.py
pytest -q
```

**Note:** `run_ambiguity_ablation.py` is deterministic only when `--seed 42` is specified. Without the seed, Python's hash randomization causes non-reproducible results.

## 6. Known Non-Final Components

| Component | Status |
|-----------|--------|
| Posterior heatmap figure | **Toy Gaussian placeholder only** — not from estimator output |
| LoRa / LR-FHSS feature extractors | Stubs — `src/leodtf/feature_extract_lora.py`, `src/leodtf/feature_extract_lrfhss.py` |
| IQ Doppler injector | Stub placeholder — `src/leodtf/iq_doppler_injector.py` |
| HIL validation | Docs written but no IQ capture executed |
| References | All `todo_*` entries in `refs.bib` — must be replaced with real citations |
| TLE/SGP4 errors | Not fully characterized in CRLB or posterior |
| Atmospheric multipath | Not modeled in observation noise |

## 7. Claim Safety Checklist

- [ ] No real satellite OTA validation claimed anywhere in the repo
- [ ] No meter-level localization accuracy claimed
- [ ] No GNSS replacement capability claimed
- [ ] LR1121 described as transmit-only; not claimed to receive LR-FHSS
- [ ] No PGRL, reinforcement learning, or semantic communication framework present
- [ ] HIL described as planned/trace-driven only
- [ ] All quantitative results labeled as preliminary synthetic diagnostics
- [ ] Toy heatmap clearly labeled as placeholder not from estimator
- [ ] Monte Carlo trial counts (≤10 default) described as preliminary
- [ ] CRLB vs MAP estimator caveat preserved in paper

## 8. Citation Debt

All citations are placeholders (`todo_*`). Before submission, real references must replace:
- `todo_ntn_iot` — 3GPP NTN IoT background
- `todo_sgp4` — Vallado SGP4 reference
- `todo_doppler_positioning` — prior LEO Doppler localization
- `todo_ntn_positioning` — NTN positioning survey
- `todo_oscillator_nuisance` — oscillator/CFO modeling
- `todo_lr1121` — LR1121 datasheet reference
- `todo_lora_phy` — LoRaWAN specification
- `todo_usrp_b210` — USRP B210 product overview

See `docs/bibliography_todo.md` for search guidance.