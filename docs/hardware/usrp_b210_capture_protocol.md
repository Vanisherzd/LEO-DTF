# USRP B210 Capture Protocol

> **Status:** Design only. No captures have been performed.

## Hardware Role

The NI/USRP B210 functions as a **receive-only wideband SDR capture device**
in the LEO-DTF HIL validation plan.  It does not transmit.  Its role is to
digitize RF signals and pass IQ samples to the processing host for offline
analysis.

**Important:** The USRP B210 is used in receive-only mode.  It is not part
of the transmit chain and must not be connected to an antenna without
ensuring compliance with applicable regulations.

## Required Capture Metadata

Every IQ capture must be accompanied by a metadata JSON file (recommended
naming: `capture_metadata.json`) recording at minimum:

| Field | Description | Example |
|-------|-------------|---------|
| `sample_rate_hz` | ADC sample rate | 10e6 |
| `center_freq_hz` | Tuned center frequency | 2.437e9 |
| `gain_rx_db` | RX gain setting (dB) | 30.0 |
| `clock_source` | Clock reference | 'internal' |
| `time_source` | Time sync source | 'none' |
| `antenna` | Antenna port used | 'RX2' |
| `duration_s` | Capture duration (s) | 600.0 |
| `num_samples` | Total IQ samples captured | 6000000 |
| `format` | IQ format | 'cf32' |
| `capture_file` | Path to raw IQ file | 'iq_capture.cfile' |
| `timestamp_utc` | Capture start (ISO 8601) | '2026-06-07T12:00:00Z' |
| `operator` | Person running capture | 'researcher' |
| `device_serial` | USRP serial number | 'ENX1234ABC' |

## Suggested File Structure

```
data/hil_runs/{run_id}/
  capture_metadata.json       # All metadata above
  capture_log.txt             # Stdout/stderr from capture command
  iq_capture.cfile            # Raw IQ (complex float32, binary)
  extracted_observations.csv  # Post-processed: timestamp, freq, SNR
  posterior_result.json       # Estimator output: MAP, HPD, entropy
  analysis.py                 # Reproducible script to go from IQ → posterior
```

## Capture Command Placeholder

Example capture command using UHD (adjust frequencies, gains, and durations
before use):

```bash
# Example ONLY — do not run without configuring frequency/power
uhd_rx_cfile \
  --args="addr=0x1234" \
  --freq=2.437e9 \
  --rate=10e6 \
  --gain=30 \
  --duration=600 \
  --output-file=iq_capture.cfile \
  --capture-clock=internal \
  --antenna=RX2
```

## Post-Capture Analysis Flow

After the IQ capture:

1. **Frequency correction** — Estimate and remove DC offset and any
   static CFO using a known tone or preamble in the capture.

2. **Packet detection** — Locate LR1121/STM32 packet starts in the IQ
   stream using energy detection or known preamble correlation.

3. **Timestamp extraction** — For each detected packet, record the
   sample index (or host time) corresponding to the packet arrival.
   Convert to observation time $t_i$.

4. **Doppler/CFO extraction** — For each packet, estimate the instantaneous
   frequency $y_f(t_i)$ by fitting a phase slope or FFT around the
   packet center.

5. **Generate observation CSV** — Produce `extracted_observations.csv`:
   ```
   time_s,frequency_hz,timestamp_unix
   0.0,-1234.5,1717843200.123
   30.0,-987.3,1717843230.124
   ...
   ```

6. **Run posterior estimator** — Feed the observation CSV to the LEO-DTF
   estimator, using the same TLE and ROI configuration used in the
   injection.

7. **Validate against injected ground truth** — Compare MAP estimate
   and HPD region against the known injected position and nuisance
   parameters.

## Capture Log

All capture sessions must produce a `capture_log.txt` recording the
exact command used and any warnings or errors reported by UHD during
the capture.  This log must be preserved for reproducibility.

## Not Claimed

- This protocol does not involve real satellite OTA signals.
- No live pass validation is claimed.
- The USRP B210 is configured and operated by the experimenter; the
  LEO-DTF repository does not provide an automated capture pipeline.

## References

- Ettus Research: NI USRP B210 Product Overview \cite{todo_usrp_b210}