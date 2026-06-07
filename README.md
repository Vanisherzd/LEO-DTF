# LEO-DTF: LEO Doppler-Time Fingerprint for Coarse Localization

This repository implements the LEO Doppler-Time Fingerprint (DTF) method for
coarse localization and uplink state estimation of direct-to-satellite IoT
devices.

The approach is model-driven, using TLE + SGP4 geometry, Doppler/range-rate
observation models, and nuisance parameter estimation (time offset, CFO,
oscillator drift, noise) to produce a Bayesian posterior over position and
time offset within a bounded region of interest (ROI).

**Important Constraints:**
- No real satellite OTA validation claimed.
- No meter-level GNSS replacement claimed.
- Target is coarse localization inside a bounded ROI.
- HIL is trace-driven: LR1121/STM32 as packet source, USRP B210 for IQ capture,
  with offline injection of Doppler/CFO/delay/SNR.
- LR-FHSS on LR1121 is transmit-only; the repository does not design the
  LR1121 as a receiver.
- Research focus is Doppler-Time Fingerprint coarse localization and uplink
  state estimation.  This is not PGRL, reinforcement learning, or semantic
  communication.

## Directory Structure

- `src/leodtf`: Core implementation (TLE loading, orbit propagation,
  observation model, estimator, metrics, synthetic dataset generator)
- `experiments/results/`: Synthetic pass dataset and observation outputs
- `scripts/`: Utility scripts for running simulations, Monte Carlo trials,
  and synthetic dataset generation
- `tests/`: Unit tests
- `docs/`: Documentation, including hardware HIL plan
- `data/`: TLE snapshots, synthetic data, and IQ seeds
- `paper/`: LaTeX manuscript skeleton (see Manuscript section below)

## Getting Started

1. Clone the repository.
2. Install dependencies: `uv pip install -e .` (from repo root)
3. Run the smoke test: `python scripts/run_smoke_test.py`
4. Run the synthetic dataset generator:
   `python scripts/generate_synthetic_dataset.py`
5. Run Monte Carlo trials:
   `python scripts/run_monte_carlo_synthetic.py --trials 100`
6. Run CRLB sensitivity diagnostic:
   `python scripts/diagnose_crlb_sensitivity.py`
7. Run all tests: `pytest -q`

## Repository Scripts

| Script | Purpose |
|--------|---------|
| `scripts/run_smoke_test.py` | Smoke test — orbit propagation, CRLB, grid estimator demo |
| `scripts/generate_synthetic_dataset.py` | Generate reproducible synthetic pass dataset (JSON + CSV) |
| `scripts/run_monte_carlo_synthetic.py` | Monte Carlo trials with per-trial CSV output |
| `scripts/diagnose_crlb_sensitivity.py` | CRLB RMSE vs. timestamp noise sweep |
| `scripts/summarize_evaluation.py` | Summarize all evaluation outputs to Markdown/JSON/LaTeX table |

## Reproduce Preliminary Evaluation Artifacts

All outputs go under `experiments/results/`:

```bash
# 1. Generate synthetic pass dataset
python scripts/generate_synthetic_dataset.py
# Output: experiments/results/synthetic/synthetic_pass_dataset.json
#         experiments/results/synthetic/synthetic_pass_observations.csv

# 2. Run Monte Carlo trials (use --trials N for more trials)
python scripts/run_monte_carlo_synthetic.py --trials 5
# Output: experiments/results/montecarlo/montecarlo_trials.csv
#         experiments/results/montecarlo/montecarlo_summary.json

# 3. CRLB sensitivity diagnostic
python scripts/diagnose_crlb_sensitivity.py
# Output: experiments/results/crlb/crlb_sensitivity.csv
#         experiments/results/crlb/crlb_sensitivity_summary.json

# 4. Summarize all results into one report
python scripts/summarize_evaluation.py
# Output: experiments/results/evaluation_summary.md
#         experiments/results/evaluation_summary.json
#         paper/tables/evaluation_summary.tex

# 5. Run ambiguity and ablation study
python scripts/run_ambiguity_ablation.py --trials 5
# Output: experiments/results/ablation/ambiguity_ablation_trials.csv
#         experiments/results/ablation/ambiguity_ablation_summary.json
#         paper/tables/ablation_summary.tex
```

**Config files** (`experiments/configs/`) are currently documentation-first;
they record the experimental parameters but scripts do not yet consume them
directly.

All results are synthetic or trace-driven. No real satellite OTA validation
is performed or claimed.

## Manuscript

The LaTeX manuscript skeleton is in `paper/`.  It is a **working draft**;
no paper claims are made.  Current status:

- System model (Section~3) and estimator (Section~5) have been expanded to
  include full mathematical notation and implementation details.
- Evaluation (Section~7) references reproducible synthetic experiments and
  includes a trace-driven HIL plan.
- All quantitative results are preliminary and synthetic; no real satellite
  OTA data is used.
- No localization accuracy claims are made; all metrics are simulation diagnostics.
- The HIL section explicitly states that no OTA validation is claimed.

Manuscript structure:
```
paper/
  main.tex                   # IEEEtran conference style, includes all sections
  refs.bib                   # Placeholder references (to be replaced)
  sections/
    00_abstract.tex
    01_introduction.tex
    02_background.tex
    03_system_model.tex
    04_doppler_time_fingerprint.tex
    05_bayesian_estimator.tex
    06_trace_driven_hil.tex
    07_evaluation_plan.tex
    08_limitations.tex
    09_conclusion.tex
  figures/
  tables/
```

Compile (requires IEEEtran and a LaTeX distribution):
```bash
cd paper && pdflatex main.tex
```
Note: IEEEtran is not bundled with this repository; install via your LaTeX
distribution or from [CTAN](https://ctan.org/pkg/IEEEtran).

## License

This project is licensed under the MIT License - see the LICENSE file for details.