# LEO-DTF: LEO Doppler-Time Fingerprint for Coarse Localization

This repository implements the LEO Doppler-Time Fingerprint (DTF) method for coarse localization and uplink state estimation of direct-to-satellite IoT devices.

The approach is model-driven, using TLE + SGP4 geometry, Doppler/range-rate models, and nuisance parameters (time offset, CFO, drift, noise) to produce a Bayesian posterior over position and time offset.

**Important Constraints:**
- No real satellite OTA validation claimed.
- No meter-level GNSS replacement claimed.
- Target is coarse localization inside a bounded ROI.
- HIL is trace-driven: LR1121/STM32 as packet source, USRP B210 for IQ capture, with offline injection of Doppler/CFO/delay/SNR.
- LR-FHSS on LR1121 is transmit-only; we do not design LR1121 as a receiver.

## Directory Structure

- `src/leodtf`: Core implementation (TLE loading, orbit propagation, observation model, estimator, etc.)
- `experiments`: Configuration and results for experiments.
- `scripts`: Utility scripts for running simulations and tests.
- `tests`: Unit tests.
- `docs`: Documentation, including hardware plans.
- `data`: TLE snapshots, synthetic data, and IQ seeds.

## Getting Started

1. Clone the repository.
2. Install dependencies (see `pyproject.toml`).
3. Run the smoke test: `python scripts/run_smoke_test.py`

## License

This project is licensed under the MIT License - see the LICENSE file for details.