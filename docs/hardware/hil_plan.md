# Hardware-in-the-Loop (HIL) Validation Plan for LEO-DTF

> **Status:** Design only. No HIL runs have been executed. No OTA validation claimed.

## 1. Objective

Validate the LEO-DTF observation extraction and posterior estimation pipeline
in a laboratory setting using commercial off-the-shelf (COTS) D2S hardware,
without requiring live satellite passes.  The HIL confirms that:

- IQ samples captured from a real transmitter contain extractable timing and
  frequency information.
- The Doppler/CFO/delay injection and offline processing pipeline produces
  consistent observation sequences.
- The grid posterior estimator returns correct MAP estimates and HPD regions
  when given known injected ground-truth parameters.

**What is not validated:**
- Real satellite Doppler extraction from over-the-air (OTA) links.
- Antenna radiation pattern and RF path effects.
- Outdoor timing synchronization quality.

## 2. Hardware Roles

| Component | Role | TX/RX | Notes |
|-----------|------|-------|-------|
| Semtech LR1121 + STM32 | Packet waveform source | TX only | LR-FHSS or LoRa mode; transmit-only, NOT a receiver |
| NI/USRP B210 | Wideband SDR capture | RX only | Captures IQ at 1--10 MS/s |
| Processing host | Offline analysis | N/A | Runs Python pipeline; no real-time requirement |

The LR1121 is explicitly used as a characterized packet source.  It does not
perform reception and is not used to implement the DTF estimator.  Designing
the LR1121 as a receiver would be a separate hardware configuration and is not
part of this HIL plan.

## 3. Signal Flow

```
[LR1121/STM32 TX]
       |  (RF cable or antenna in lab)
       v
  [USRP B210 IQ capture]
       |  (raw IQ file, SigMF format)
       v
  [Offline: Doppler/CFO/delay injection]
       |  (injected IQ or synthetic observation injection)
       v
  [Feature extraction: timing + frequency]
       |  (CSV: timestamp, frequency estimate per packet)
       v
  [LEO-DTF Estimator: posterior + MAP]
       |  (JSON: posterior grid, MAP, HPD region)
       v
  [Analysis: reproduce heatmap, check against injected ground truth]
```

## 4. Injection Model

Offline injection applies the following impairments to simulated or captured
IQ samples:

- **Doppler shift**: time-varying frequency shift $f_D(t) = -(f_c/c)\dot{\rho}(t)$ for a
  chosen satellite geometry (TLE + SGP4).
- **CFO $b_0$**: constant frequency offset in Hz.
- **Drift $b_1$**: linear frequency drift in Hz/s.
- **Propagation delay**: $\rho(t)/c$ for the chosen geometry.
- **Additive noise**: complex AWGN to achieve target SNR.

The injector is implemented in `src/leodtf/iq_doppler_injector.py` (placeholder).
The design above defines the intended API and signal model.

## 5. Validation Checklist

Before any HIL validation claim is made in the manuscript, the following must
be satisfied:

- [ ] At least 3 independent IQ capture runs with different injected geometries
      (varying elevation, azimuth, pass duration).
- [ ] In each run, the injected true position lies within the 95\% HPD region.
- [ ] In each run, MAP estimate error is less than the grid resolution.
- [ ] Analysis script (`analysis.py`) reproduces the posterior heatmap from
      `extracted_observations.csv` without manual intervention.
- [ ] Posterior entropy decreases with increasing SNR in synthetic baseline
      runs using the same geometry as the HIL captures.
- [ ] Metadata JSON for each run records all injected parameters for
      reproducibility.

## 6. Expected Artifacts

All artifacts stored under `data/hil_runs/{run_id}/`:

```
data/hil_runs/
  {run_id}/
    capture_IQ_{run_id}.sigmf-data     # Raw IQ (SigMF format)
    capture_IQ_{run_id}.sigmf-meta     # SigMF metadata header
    metadata.json                       # Injected params, hardware config
    extracted_observations.csv          # Per-packet: time, freq, timestamp
    posterior_result.json               # Grid posterior, MAP, HPD, ambiguity
    analysis.py                         # Script reproducing posterior
```

## 7. Not Claimed Here

- Real satellite OTA validation.  (Requires live passes; not in current plan.)
- Meter-level or centimeter-level localization accuracy.
- Operational deployment or field validation.
- LR1121 functioning as a receiver.

## 8. Relationship to Manuscript

Section~\ref{sec:hil} of `paper/main.tex` describes the trace-driven HIL plan
at the same level of ambition as this document.  This `hil_plan.md` provides
additional engineering detail.  Both documents must be updated to reflect any
actual HIL execution before stronger claims are made in the manuscript.