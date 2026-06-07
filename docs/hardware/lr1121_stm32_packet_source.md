# LR1121/STM32 Packet Source

> **Status:** Design only. No transmissions have been performed.

## Hardware Role

The Semtech LR1121 evaluation board, driven by an STM32 microcontroller, serves
as a **characterized packet waveform source** for LEO-DTF HIL validation.
Its role is to transmit known, reproducible packets that can be captured by
the USRP B210 and used in the trace-driven Doppler/injection pipeline.

**The LR1121 is configured as transmit-only in this setup.**
It is NOT used as a receiver.  Designing the LR1121 as a receive element
is a separate hardware configuration outside the scope of this HIL plan.

## Important Note on LR-FHSS

The LR1121 supports LR-FHSS (Long Range Frequency Hopping Spread Spectrum)
as a transmit mode.  In the current HIL design:
- LR1121 is used to generate characterized LR-FHSS or LoRa packets as a
  **Tx-only signal source**.
- The LR1121 is NOT claimed to be able to receive LR-FHSS or LoRa signals
  in this repository.
- No Rx capability is assumed or used in the LEO-DTF observation pipeline.

## Serial Logging

The STM32 should log each transmitted packet to serial (or SD card) with:
- Packet index / sequence number
- Timestamp from STM32 RTC (millisecond resolution)
- Central frequency of transmission
- Packet duration

Suggested serial log format:
```
TX_LOG, seq=0001, time_ms=1234567, freq_hz=2437000000, dur_ms=50
TX_LOG, seq=0002, time_ms=1234597, freq_hz=2437000000, dur_ms=50
...
```

## Packet Schedule

For the HIL validation scenario, packets are transmitted at regular
intervals (e.g., every 30 seconds over a 10-minute window).  This mimics
the sparsepacket cadence expected from a D2S IoT device during a satellite
pass.

Recommended settings for synthetic pass matching:
- Packet interval: 30 seconds (matches `sample_interval_s` in synthetic config)
- Number of packets: 20 (matches `num_packets` in synthetic config)
- Packet duration: configurable, ≤ 100 ms
- Center frequency: within ISM band (2.4 GHz or 915 MHz)

## Payload Format

The packet payload should contain:
- A known fixed preamble sequence (for timing extraction in the capture)
- A counter or sequence number (for missed-packet detection)
- A short unique identifier

Example minimal payload structure:
```
[Preamble: 8 bytes] [Seq: 2 bytes] [ID: 4 bytes] [CRC: 2 bytes]
```

## Expected Artifacts

After a capture run, the following artifacts should be archived:

| Artifact | Description |
|----------|-------------|
| `tx_log.csv` | Serial log of all transmitted packets |
| `serial_log.txt` | Raw STM32 serial output |
| `packet_metadata.json` | Summary: frequency, interval, count, schedule parameters |

These artifacts must be preserved alongside the USRP B210 capture files
for full reproducibility.

## Power and Frequency Configuration

Before any HIL run:
- Set LR1121 output power to the minimum level required for successful
  USRP capture (through the attenuator / dummy load chain).
- Verify transmitted frequency with a spectrum analyzer before connecting
  the USRP B210.
- Log the configured frequency and power in `packet_metadata.json`.

## Safety Note

See `rf_safety_checklist.md`.  The LR1121 evaluation board must not be
connected to an antenna for OTA transmission without proper licensing.
Use conducted setups with attenuators for all HIL validation experiments.

## References

- Semtech LR1121 Datasheet \cite{todo_lr1121}
- LoRa and LR-FHSS specifications \cite{todo_lora_phy}