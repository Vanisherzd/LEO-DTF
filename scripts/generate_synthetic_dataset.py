#!/usr/bin/env python3
"""
Generate synthetic pass dataset and observations for LEO-DTF experiments.
Produces reproducible JSON + CSV outputs under experiments/results/.

Usage:
    python scripts/generate_synthetic_dataset.py

Outputs:
    experiments/results/synthetic_pass_dataset.json
    experiments/results/synthetic_pass_observations.csv
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from leodtf.sim_dataset_gen import (
    generate_synthetic_pass_dataset,
    export_dataset_json,
    export_dataset_csv,
)

# Default scenario (matches smoke test geometry)
SCENARIO = dict(
    true_lat_deg=40.0,
    true_lon_deg=-105.0,
    true_alt_m=0.0,
    duration_s=600.0,
    sample_interval_s=30.0,
    cfo_hz=50.0,
    drift_hz_per_s=0.1,
    time_offset_s=1e-3,
    doppler_noise_std=1.0,
    delay_noise_std=1e-3,
    seed=42,
)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "experiments", "results")
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "synthetic_pass_dataset.json")
OUTPUT_CSV = os.path.join(OUTPUT_DIR, "synthetic_pass_observations.csv")


def main():
    print("LEO-DTF Synthetic Dataset Generator")
    print("=" * 50)

    # Use deterministic synthetic orbit (no real TLE needed)
    dataset = generate_synthetic_pass_dataset(**SCENARIO)

    # Print summary
    n = len(dataset["time_offsets_s"])
    print(f"Observations: {n}")
    print(f"True receiver: {dataset['true_receiver_geodetic']}")
    print(f"Doppler range (clean): {min(dataset['clean_doppler_hz']):.2f} – "
          f"{max(dataset['clean_doppler_hz']):.2f} Hz")
    print(f"Delay range (clean):   {min(dataset['clean_delay_s'])*1e3:.2f} – "
          f"{max(dataset['clean_delay_s'])*1e3:.2f} ms")
    print(f"CFO: {dataset['cfo_hz']} Hz, drift: {dataset['drift_hz_per_s']} Hz/s")
    print(f"Time offset: {dataset['time_offset_s']*1e3:.2f} ms")
    print(f"Doppler noise std: {dataset['doppler_noise_std_hz']} Hz")
    print(f"Delay noise std: {dataset['delay_noise_std_s']*1e6:.1f} µs")
    print(f"Orbit: {dataset['orbit_altitude_km']:.0f} km @ "
          f"{dataset['orbit_inclination_deg']:.0f}° inclination")
    print()

    # Export
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    export_dataset_json(dataset, OUTPUT_JSON)
    export_dataset_csv(dataset, OUTPUT_CSV)
    print(f"JSON: {OUTPUT_JSON}")
    print(f"CSV:  {OUTPUT_CSV}")
    print()
    print("NOTE: Synthetic only. No paper results claimed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())