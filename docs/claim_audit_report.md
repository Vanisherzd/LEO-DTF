# LEO-DTF Claim Audit Report

This document tracks the safety of claims made in the LEO-DTF manuscript and
supporting documentation. It is intended for pre-submission human review.

---

## 1. Safe Claims Currently Allowed

The following claims are explicitly backed by working code in the repository
and conservative language in the manuscript:

| Claim | Backing | Location |
|-------|---------|----------|
| LEO-DTF formulates Doppler-time fingerprinting for bounded ROI | Synthetic pass generation + grid estimator in `src/leodtf/` | paper/sections/00-09 |
| Repo has synthetic pass dataset generation | `scripts/generate_synthetic_dataset.py` | experiments/results/ |
| Repo has Monte Carlo diagnostic with nuisance parameters | `scripts/run_monte_carlo_synthetic.py` | experiments/results/ |
| Repo has preliminary synthetic diagnostics | All evaluation scripts operate on synthetic data only | paper/sections/07_evaluation_plan.tex |
| Repo has trace-driven HIL plan | Hardware docs + no live satellite claimed | docs/hardware/ |
| No real satellite OTA validation | Every README + paper section explicitly states this | README.md, paper/ |
| LR1121 used as transmit-only | docs/hardware/lr1121_stm32_packet_source.md | docs/ |

---

## 2. Claims Explicitly NOT Allowed

The following claim categories are prohibited in all manuscript and
documentation files unless backed by verifiable evidence:

| Prohibited Claim | Reason |
|------------------|--------|
| Real satellite OTA validation | No live satellite experiments exist in this repo |
| Meter-level localization accuracy | Only coarse (ROI-scale) localization is supported |
| GNSS replacement | Explicitly outside scope; GNSS not used or compared |
| LR-FHSS reception on LR1121 | LR1121 is transmit-only; no receiver implemented |
| Operational deployment | No deployment; only synthetic trace-driven diagnostics |
| Outperforms state-of-the-art | No SOTA comparison performed |
| Real hardware validated | HIL is trace-driven only; no live validation |
| Semantic communication | This is not semantic communication research |
| PGRL / reinforcement learning | This is not PGRL; no RL components in this repo |

---

## 3. Paper Sections with Highest Claim Risk

| Section | Risk Reason |
|---------|-------------|
| `00_abstract.tex` | Highest traffic; first impression; tendency to over-claim |
| `01_introduction.tex` | Motivation claims; "outperforms" temptation |
| `04_doppler_time_fingerprint.tex` | May overstate accuracy without "preliminary synthetic" qualifier |
| `05_bayesian_estimator.tex` | Mathematical claims; prior assumptions may be overstated |
| `07_evaluation_plan.tex` | Highest risk: temptation to claim "validated" on synthetic data |
| `09_conclusion.tex` | Future work can slip into claimed achievements |

Sections `02_background.tex`, `03_system_model.tex`, `06_trace_driven_hil.tex`,
and `08_limitations.tex` are lower risk because they are explicitly
fact-stating or enumerating constraints.

---

## 4. Current Safeguards in Repository

| Safeguard | Location | What it does |
|-----------|----------|--------------|
| Conservative phrase checker | `scripts/validate_repo_state.py` | Fails fast if overclaim phrases appear |
| LaTeX sanity checker | `scripts/check_paper_sanity.py` | Checks for forbidden patterns in tex |
| Limitations section | `paper/sections/08_limitations.tex` | Lists 14 explicit scope constraints |
| Supervisor review checklist | `docs/supervisor_review_checklist.md` | Human review guide before submission |
| Reproducibility checklist | `docs/reproducibility_checklist.md` | Documents script inventory and claim safety |
| Claim audit report | this file | Tracks allowed/prohibited claims |
| Bibliography TODO | `docs/bibliography_todo.md` | Tracks unverified placeholder citations |
| HIL validation checklist | `docs/hardware/trace_driven_validation_checklist.md` | Pre-HIL safety gate |

---

## 5. Manual Review Checklist Before Submission

Run these checks manually before any submission:

- [ ] `python scripts/check_paper_sanity.py` — must PASS with zero FAILs
- [ ] `python scripts/validate_repo_state.py` — must PASS
- [ ] `pytest -q` — all 26 tests must pass
- [ ] Read `paper/sections/00_abstract.tex` aloud — no overclaim detected?
- [ ] Read `paper/sections/07_evaluation_plan.tex` — does "validated" appear?
  If yes, confirm it says "preliminary synthetic diagnostic" in same paragraph
- [ ] Search repo for "real satellite" — should only appear in limitations/contexts
- [ ] Search repo for "meter-level" — should only appear in limitations/contexts
- [ ] Search repo for "GNSS replacement" — should only appear as negative disclaimer
- [ ] Search repo for "outperforms" or "SOTA" — should not appear at all
- [ ] Verify all `todo_*` citations in `paper/refs.bib` are replaced with real refs
- [ ] Verify `docs/bibliography_todo.md` checklist is complete
- [ ] Verify HIL section mentions trace-driven and no live satellite
- [ ] Confirm no IQ capture files or large binary artifacts are in repo
- [ ] Confirm `docs/local_setup.md` reproduces all artifacts cleanly

---

## 6. Pattern Reference for Claim Detection

Use these patterns when searching the manuscript manually:

```bash
# High risk — should not appear outside limitations/disclaimer context
grep -i "real satellite" paper/sections/*.tex
grep -i "meter-level" paper/sections/*.tex
grep -i "gnss replacement" paper/sections/*.tex
grep -i "outperforms" paper/sections/*.tex
grep -i "SOTA" paper/sections/*.tex
grep -i "validated on" paper/sections/*.tex

# Low risk but verify
grep -i "operational" paper/sections/*.tex
grep -i "deployment" paper/sections/*.tex
```

---

## 7. HIL Claim Specifics

Hardware-in-the-loop (HIL) claims require special care:

- HIL in this repo = LR1121/STM32 packet source + USRP B210 IQ capture +
  offline injection of Doppler/CFO/delay/SNR
- This is trace-driven validation, NOT live satellite OTA validation
- The phrase "hardware-in-the-loop validated" may NOT be used
- Correct phrasing: "trace-driven HIL design is described; no live satellite
  over-the-air validation is claimed"

---

## 8. Revision History

| Date | Change |
|------|--------|
| (initial) | Created claim audit report |