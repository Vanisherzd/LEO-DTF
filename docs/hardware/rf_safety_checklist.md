# RF Safety and No-Transmit Checklist

> **Document status:** Planning only. Not legal advice.

## Objective

Ensure that all hardware-in-the-loop (HIL) validation experiments are conducted
safely and in compliance with applicable regulations.  This checklist must be
reviewed before any RF emission activity in a laboratory setting.

## Legal and Safety Assumptions

- The laboratory conducting HIL validation is responsible for obtaining any
  required licenses or exemptions for RF emission.
- Experiments described in this repository use conducted (cable-connected)
  or fully shielded setups unless explicit authorization has been obtained.
- This document does not authorize over-the-air (OTA) transmission.
  All OTA experiments require proper licensing from the relevant spectrum
  authority (e.g., FCC, ETSI, or local equivalent).

## Do-Not-Transmit Checklist

Before applying any power or connecting antennas, confirm ALL of the following:

- [ ] No unlicensed OTA transmission will occur.
- [ ] All transmit-capable devices are connected via attenuator, dummy load,
      or into a shielded enclosure.
- [ ] Antenna ports not in use are terminated with 50-ohm dummy loads.
- [ ] Output power levels are verified to be at or below applicable
      exemption thresholds (e.g., FCC Part 15 for unintentional radiators).
- [ ] Spectrum analyzer or power meter is used to verify no unexpected
      emissions before connecting any antenna.

## Dummy Load and Shielded Setup Recommendation

For LEO-DTF HIL validation using LR1121/STM32 + USRP B210:
- Use a coaxial attenuator (30+ dB) between any transmitter output and
  spectrum analyzer / capture hardware.
- If antennas are used, keep them in a shielded anechoic box or Faraday cage
  during initial characterization.
- Cable losses should be measured and logged for all connections.

## Frequency Plan (Placeholder)

| Device | Mode | Frequency | Max Power | Notes |
|--------|------|-----------|-----------|-------|
| LR1121 (STM32) | TX only | 2.4 GHz (Wi-Fi) or 915 MHz (ISM) | ≤ X dBm | Configure before use |
| USRP B210 | RX only | Configured per experiment | N/A | RX front-end only |

*Fill in max power and frequency before any hardware test.*

## Power Level Logging

Before any capture run, record:
- Transmitter output power (dBm) at antenna port / attenuator input
- Attenuator value (dB)
- Spectrum analyzer reading (dBm)
- Cable loss (dB)

## Antenna and Cable Checklist

- [ ] All antenna cables are verified to be correctly connected.
- [ ] Cable losses at operating frequency are known and logged.
- [ ] No open connectors that could radiate unintentionally.
- [ ] Antenna gain is documented if used.

## Local Regulations Reminder

Users are responsible for complying with:
- FCC Part 15 / Part 18 (USA)
- ETSI EN 300 220 / EN 301 893 (EU)
- Any applicable ISM band rules for the selected frequency
- Local spectrum allocation for L-band (1–2 GHz) if used

## Artifact Checklist

After any HIL run, document:
- Transmitter frequency and power setting
- Whether OTA or conducted setup was used
- Capture file path (SigMF format recommended)
- Date, time, and operator name

**This document does not authorize any transmission. Use conducted setups
or properly licensed OTA environments only.**