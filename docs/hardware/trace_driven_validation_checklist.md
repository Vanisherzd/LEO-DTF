# Trace-Driven Validation Checklist

> **Status:** Design phase. No HIL runs have been executed.

This checklist documents the steps required to validate the LEO-DTF
observation extraction and posterior estimation pipeline using the
trace-driven HIL design.  It applies to each independent validation run.

## Prerequisites

- [ ] Hardware: LR1121/STM32 (packet source), USRP B210 (capture), cables,
        attenuators, processing host.
- [ ] Software: UHD driver installed for USRP B210; LEO-DTF repo installed
        on processing host.
- [ ] Safety: RF safety checklist reviewed; conducted/shielded setup confirmed
        before any power is applied.

## Pre-Run Setup

- [ ] Transmitter frequency and power configured and verified via spectrum
        analyzer or power meter.
- [ ] Attenuator chain loss measured and logged.
- [ ] USRP B210 connected (receive port only); transmit path physically
        disconnected or attenuated to ≤ 0 dBm at antenna.
- [ ] Clock source set (internal or external GPSDO if used).
- [ ] Metadata JSON created with capture parameters.
- [ ] Synthetic injection parameters defined (satellite geometry, nuisance
        values, noise levels) for offline injection or ground-truth comparison.

## Capture Execution

- [ ] Capture command executed and `capture_log.txt` saved.
- [ ] Duration, sample rate, and center frequency confirmed in log.
- [ ] Any UHD warnings or errors recorded in `capture_log.txt`.

## Post-Capture

- [ ] IQ file confirmed to exist with expected size.
- [ ] Serial log (`tx_log.csv`) from STM32 confirmed.
- [ ] Packet metadata (`packet_metadata.json`) saved.

## Observation Extraction

- [ ] Observation extraction script runs without error on captured IQ.
- [ ] `extracted_observations.csv` generated with columns:
        `time_s`, `frequency_hz`, `timestamp_unix`.
- [ ] Packet detection rate logged (detected / expected packets).

## Posterior Estimation

- [ ] Estimator runs on `extracted_observations.csv` using the same TLE
        and ROI configuration as the injection.
- [ ] `posterior_result.json` generated with MAP location, HPD region,
        posterior entropy, and ambiguity score.
- [ ] Injected true position falls within the 95\% HPD region.

## Analysis and Validation

- [ ] MAP estimate error computed against injected ground truth.
- [ ] Posterior entropy compared with equivalent synthetic run.
- [ ] HPD region size compared with CRLB prediction at the same noise level.
- [ ] Analysis script (`analysis.py`) reproduces posterior from CSV
        without manual intervention.

## Artifact Archiving

For each run, archive:
- [ ] `capture_metadata.json`
- [ ] `capture_log.txt`
- [ ] `iq_capture.cfile` (SigMF recommended)
- [ ] `tx_log.csv`
- [ ] `extracted_observations.csv`
- [ ] `posterior_result.json`
- [ ] `analysis.py` (version used for this run)

## Claims Review

Before publishing any results from this run:
- [ ] No statement claiming real satellite OTA validation is included.
- [ ] All results are clearly labeled as trace-driven HIL diagnostics.
- [ ] No meter-level localization accuracy is claimed.
- [ ] It is stated that results reflect the quality of the hardware
        characterization and injection pipeline, not operational deployment.

## Not Claimed

This validation checklist does not validate:
- Real satellite OTA extraction (requires live passes).
- Outdoor antenna radiation performance.
- Long-term oscillator stability over multiple passes.
- Operation at power levels above the laboratory exemption threshold.

## Relationship to Paper

Section~\ref{sec:hil} of the manuscript describes the trace-driven HIL plan
at the same level of ambition as this checklist.  Both must be updated to
reflect any actual HIL execution before stronger claims are made.