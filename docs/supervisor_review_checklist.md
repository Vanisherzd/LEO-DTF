# Supervisor Review Checklist for LEO-DTF

## 1. Paper Claim Safety

Reviewers should verify that **none** of the following claims appear in the current draft:

| Claim | Status |
|-------|--------|
| Real satellite OTA validation | **NOT claimed** — all results are synthetic/trace-driven |
| Meter-level localization accuracy | **NOT claimed** — explicitly stated as coarse localization |
| GNSS replacement | **NOT claimed** — complementary bounded-ROI use case only |
| LR1121 can receive LR-FHSS | **NOT claimed** — described as transmit-only packet source |
| PGRL / reinforcement learning | **NOT present** — no RL framework in this repo |
| HIL validation completed | **NOT claimed** — docs describe planned trace-driven approach |

---

## 2. Technical Model Review

Items to verify in the paper manuscript:

- [ ] **Doppler sign convention:** Doppler is defined as positive when satellite approaches (frequency above carrier) or the other way — must be consistent throughout Eq. (4) and the estimator.
- [ ] **Range-rate definition:** $\dot{\rho}(t) = \frac{(p_{sat} - p_{term}) \cdot v_{sat}}{\|p_{sat} - p_{term}\|}$ is clearly stated in Section 3 or 4.
- [ ] **Stationary terminal assumption:** The model assumes the ground terminal is stationary (no mobility model). Is this clearly stated?
- [ ] **CFO/drift/time offset model:** Section 3 or 4 explicitly defines $b_0$ (CFO), $b_1$ (drift), and $\Delta t$ (time offset) as nuisance parameters.
- [ ] **Delay observation availability:** The paper should note that delay/timestamp observations may not be available from low-cost IoT hardware.
- [ ] **Prior/regularization on nuisance:** Section 5 (Estimator) should describe weak priors or regularization on $b_0$, $b_1$, and $\Delta t$.
- [ ] **Bounded ROI assumption:** Section 3 or 4 should state that a bounded ROI is a precondition (e.g., 10×10 km known coverage area).

---

## 3. Evaluation Review

Items to verify before accepting the evaluation claims:

- [ ] **Synthetic dataset generation:** `scripts/generate_synthetic_dataset.py` is deterministic and produces the geometry used in all experiments.
- [ ] **Monte Carlo trial count:** Default is `--trials 10`. The paper explicitly describes this as preliminary (not statistically conclusive) and uses small-N language.
- [ ] **CRLB vs MAP caveat:** Section 7 (Evaluation) should note that the classical CRLB assumes unbiased estimation without priors on nuisance parameters, and the MAP estimator uses weak priors. These are not directly comparable.
- [ ] **Ambiguity ablation interpretation:** Section 7 describes the ablation as a qualitative diagnostic of estimator behavior, not as a benchmark. The paper uses language like "intended to verify qualitative behavior" rather than "outperforms."
- [ ] **Toy heatmap clearly labeled:** `paper/figures/posterior_heatmap_placeholder.pdf` is a deterministic toy Gaussian. Section 7 and the figure caption explicitly describe it as a conceptual placeholder, not an actual estimator posterior.
- [ ] **Figure captions:** All figure captions should include "synthetic diagnostic" or "preliminary."

---

## 4. Hardware-in-the-Loop Review

Items to verify in the HIL section (Section 6) and hardware docs:

- [ ] **LR1121/STM32 packet source:** Described as a characterized packet waveform source in transmit-only mode.
- [ ] **USRP B210 capture:** Described as receive-only wideband SDR capture. No transmit role claimed.
- [ ] **RF safety checklist:** `docs/hardware/rf_safety_checklist.md` exists and states no OTA transmission is authorized.
- [ ] **No real OTA validation yet:** The HIL section explicitly states that no IQ captures have been executed and no OTA validation is claimed.
- [ ] **Required artifacts for future HIL:** The trace-driven validation checklist documents what a future HIL run must produce.

---

## 5. Paper Readiness

Before this draft is submitted or presented:

- [ ] **Citation replacement:** All `todo_*` entries in `refs.bib` must be replaced with real, verified citations. The current `todo_*` entries use placeholder titles and unverified authors.
- [ ] **Figure captions finalized:** Current captions may need revision for clarity and consistency.
- [ ] **Limitations section preserved:** Section 8 correctly lists all known limitations including: bounded ROI, synthetic-only results, toy heatmap, TLE/SGP4 errors not modeled, atmospheric/multipath effects not modeled, feature extractor stubs, HIL not executed.
- [ ] **Reproducibility commands verified:** All commands in Section 7 (Reproduction Commands) and the README have been tested and pass.
- [ ] **No overclaiming in abstract/intro:** The abstract and introduction should be re-read carefully to ensure "preliminary synthetic diagnostics" language is preserved and no operational deployment claims appear.

---

## 6. Known Gaps

These are known and documented, but represent work still needed:

| Item | Status | Action Needed |
|------|--------|---------------|
| Real satellite OTA capture | Not done | Requires authorized hardware setup |
| IQ Doppler injector implementation | Stub | `src/leodtf/iq_doppler_injector.py` is a placeholder |
| LoRa/LR-FHSS feature extraction | Stub | Real algorithms needed for HIL |
| USRP B210 capture replay | Not done | Requires actual hardware and capture |
| Citation verification | Placeholder | Must replace `todo_*` with real refs |
| TLE/SGP4 error characterization | Not modeled | Ephemeris errors can bias estimates |
| Atmospheric delay | Not modeled | Relevant for real L-band deployments |