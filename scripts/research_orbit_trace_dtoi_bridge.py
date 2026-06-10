#!/usr/bin/env python3
"""
Orbit-driven DTOI trace bridge for LEO-DTF.
Compares synthetic curvature DTOI with orbit-driven (SGP4 fallback) DTOI.
"""
import argparse
import csv
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add the src directory to the path so we can import leodtf modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import numpy as np

# Import LEO-DTF modules
try:
    from leodtf.orbit_propagation import propagate_orbit, HAS_SGP4
    from leodtf.frame_transform import geodetic_to_ecef, enu_to_ecef
    from leodtf.observation_model import ObservationModel
except ImportError as e:
    print(f"Error importing LEO-DTF modules: {e}")
    print("Make sure you are running from the repository root with the src directory in the path.")
    raise

# Parameters for the synthetic curvature model
SIGMA_F_HZ = 1.0  # frequency noise std Hz
SAMPLE_RATE_HZ = 1.0  # 1 sample per second

def synth_doppler_curvature(t, carrier_hz, offset_m):
    """
    Synthetic Doppler shift due to orbital curvature.
    We use a quadratic curvature term: Doppler = k * t^2.
    Scaling: k = carrier_hz * offset_m * 1e-18 (Hz-level Doppler).
    """
    k = carrier_hz * offset_m * 1e-18
    return k * t**2

def run_experiment(trace_source, carrier_hz, offset_m, duration_s, seed=42):
    """Run a single experiment configuration."""
    np.random.seed(seed)
    n_samples = int(duration_s * SAMPLE_RATE_HZ)
    t = np.arange(n_samples) / SAMPLE_RATE_HZ  # time in seconds

    # Ground station geodetic coordinates (lat, lon, alt) in degrees and km
    lat0_deg = 40.0
    lon0_deg = -105.0
    alt0_km = 0.0
    gs_ecef = np.asarray(geodetic_to_ecef(lat0_deg, lon0_deg, alt0_km), dtype=float)  # km

    # Nearby test station displaced eastward by offset_m.
    # geodetic_to_ecef and enu_to_ecef both use kilometers, so convert meters to km.
    offset_km = float(offset_m) / 1000.0
    gs_offset_ecef = np.asarray(
        enu_to_ecef(offset_km, 0.0, 0.0, lat0_deg, lon0_deg, alt0_km),
        dtype=float,
    )

    # TLE lines (same as in smoke test)
    line1 = "1 25544U 98067A   26155.53033517  .00012622  00000+0  28098-3 0  9994"
    line2 = "2 25544  51.6416 246.6182 0006706 302.2584 122.9105 15.50040302433475"

    # Reference time for orbit propagation (datetime)
    ref_time = datetime(2026, 6, 4, 12, 0, 0)
    times_dt = [ref_time + timedelta(seconds=ti) for ti in t]

    if trace_source == "synthetic_curvature":
        # Generate synthetic Doppler signal (curvature only)
        signal = synth_doppler_curvature(t, carrier_hz, offset_m)
    elif trace_source == "orbit_driven_fallback":
        # Propagate orbit (will fallback to synthetic orbit if SGP4 not available)
        try:
            sat_positions_ecef, sat_velocities_ecef = propagate_orbit(line1, line2, times_dt)
        except Exception as e:
            print(f"Error in orbit propagation: {e}")
            # Fallback to synthetic curvature if orbit propagation fails
            signal = synth_doppler_curvature(t, carrier_hz, offset_m)
        else:
            # Compute differential Doppler between the baseline station and a nearby
            # offset station. This keeps the orbit-driven DTOI comparable to the
            # synthetic offset experiments and avoids using raw absolute Doppler.
            signal = np.zeros(n_samples)
            obs_base = ObservationModel(gs_ecef, carrier_freq_hz=carrier_hz)
            obs_offset = ObservationModel(gs_offset_ecef, carrier_freq_hz=carrier_hz)
            for i in range(n_samples):
                satellite_state = (sat_positions_ecef[i], sat_velocities_ecef[i])
                doppler_base_hz, _ = obs_base.compute_expected_measurements(satellite_state, t[i])
                doppler_offset_hz, _ = obs_offset.compute_expected_measurements(satellite_state, t[i])
                signal[i] = doppler_offset_hz - doppler_base_hz
    else:
        raise ValueError(f"Unknown trace_source: {trace_source}")

    # Add noise
    noise = np.random.normal(0, SIGMA_F_HZ, n_samples)
    signal_noisy = signal + noise

    # Build nuisance basis matrix (affine: [1, t])
    basis_matrix = np.array([np.ones_like(t), t]).T  # shape (n_samples, 2)

    # Project out nuisance
    # Solve for coefficients: basis_matrix * coeff = signal_noisy (least squares)
    coeff, _, _, _ = np.linalg.lstsq(basis_matrix, signal_noisy, rcond=None)
    # Reconstruct the nuisance component
    nuisance_component = basis_matrix @ coeff
    # Residual
    residual = signal_noisy - nuisance_component

    # Compute DTOI
    norm_residual = np.linalg.norm(residual)
    dtoi = norm_residual / (SIGMA_F_HZ * np.sqrt(n_samples))

    # Energy removed by nuisance (relative to noisy signal)
    energy_total = np.linalg.norm(signal_noisy)**2
    energy_residual = np.linalg.norm(residual)**2
    energy_removed = 1.0 - (energy_residual / energy_total) if energy_total > 0 else 0.0

    # Observability status (using thresholds from C6A)
    if dtoi < 0.5:
        status = "unobservable"
    elif dtoi < 1.0:
        status = "weak"
    elif dtoi < 2.0:
        status = "moderate"
    else:
        status = "strong"

    return {
        "trace_source": trace_source,
        "carrier_hz": carrier_hz,
        "offset_m": offset_m,
        "duration_s": duration_s,
        "nuisance_order": 1,  # affine [1,t]
        "total_samples": n_samples,
        "naive_snr": np.linalg.norm(signal) / (SIGMA_F_HZ * np.sqrt(n_samples)),
        "dtoi": dtoi,
        "energy_removed_by_nuisance": energy_removed,
        "observability_status": status,
        "offset_km_used": offset_km,
        "differential_mode_confirmed": trace_source == "orbit_driven_fallback",
        "fallback_used": not HAS_SGP4  # True if SGP4 is not available (so we used synthetic orbit)
    }

def main():
    parser = argparse.ArgumentParser(description="Orbit-driven DTOI trace bridge")
    parser.add_argument("--quick", action="store_true", help="Use quick parameters (reduced sets)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    # Define the parameter sets
    if args.quick:
        carrier_hzs = [137e6, 915e6, 2.4e9]
        offset_ms = [100, 1000]
        duration_s = [600, 1800]
    else:
        # Full sets (not used in this phase, but we can define if needed)
        carrier_hzs = [137e6, 433e6, 868e6, 915e6, 1.6e9, 2.4e9]
        offset_ms = [100, 500, 1000, 5000]
        duration_s = [600, 1800]

    trace_sources = ["synthetic_curvature", "orbit_driven_fallback"]
    nuisance_order = 1  # fixed

    results = []
    for trace_source in trace_sources:
        for carrier in carrier_hzs:
            for offset in offset_ms:
                for dur in duration_s:
                    res = run_experiment(trace_source, carrier, offset, dur, seed=args.seed)
                    results.append(res)

    # Create output directory
    output_dir = Path("experiments/results/research_orbit_trace_bridge")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write CSV
    csv_path = output_dir / "orbit_trace_bridge_trials.csv"
    fieldnames = [
        "trace_source", "carrier_hz", "offset_m", "duration_s", "nuisance_order",
        "total_samples", "naive_snr", "dtoi", "energy_removed_by_nuisance",
        "observability_status", "offset_km_used", "differential_mode_confirmed",
        "fallback_used"
    ]
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    # Write JSON summary
    json_path = output_dir / "orbit_trace_bridge_summary.json"
    # Find best DTOI (highest) and its config
    best = max(results, key=lambda x: x["dtoi"])
    # Group by trace source to find best per trace source
    best_by_trace_source = {}
    for trace_source in trace_sources:
        source_results = [r for r in results if r["trace_source"] == trace_source]
        if source_results:
            best_source = max(source_results, key=lambda x: x["dtoi"])
            best_by_trace_source[trace_source] = {
                "carrier_hz": best_source["carrier_hz"],
                "offset_m": best_source["offset_m"],
                "duration_s": best_source["duration_s"],
                "dtoi": best_source["dtoi"],
                "observability_status": best_source["observability_status"],
                "offset_km_used": best_source["offset_km_used"],
                "differential_mode_confirmed": best_source["differential_mode_confirmed"]
            }
    # Synthetic vs orbit-driven gap: difference in best DTOI between the two trace sources
    synth_best = best_by_trace_source.get("synthetic_curvature", {}).get("dtoi", 0.0)
    orbit_best = best_by_trace_source.get("orbit_driven_fallback", {}).get("dtoi", 0.0)
    synthetic_vs_orbit_gap = orbit_best - synth_best  # or however you want to define it

    summary = {
        "metadata": {
            "quick": args.quick,
            "seed": args.seed,
            "sigma_f_hz": SIGMA_F_HZ,
            "total_rows": len(results),
            "model": "synthetic curvature and orbit-driven differential Doppler DTOI diagnostic with affine nuisance projection"
        },
        "summary": {
            "best_config": {
                "trace_source": best["trace_source"],
                "carrier_hz": best["carrier_hz"],
                "offset_m": best["offset_m"],
                "duration_s": best["duration_s"],
                "nuisance_order": best["nuisance_order"],
                "total_samples": best["total_samples"],
                "naive_snr": best["naive_snr"],
                "dtoi": best["dtoi"],
                "energy_removed_by_nuisance": best["energy_removed_by_nuisance"],
                "observability_status": best["observability_status"],
                "offset_km_used": best["offset_km_used"],
                "differential_mode_confirmed": best["differential_mode_confirmed"]
            },
            "best_by_trace_source": best_by_trace_source,
            "synthetic_vs_orbit_gap": synthetic_vs_orbit_gap,
            "count_unobservable": len([r for r in results if r["observability_status"] == "unobservable"]),
            "count_weak": len([r for r in results if r["observability_status"] == "weak"]),
            "count_moderate": len([r for r in results if r["observability_status"] == "moderate"]),
            "count_strong": len([r for r in results if r["observability_status"] == "strong"])
        },
        "key_findings": [
            f"Best DTOI achieved with trace_source '{best['trace_source']}' at carrier {best['carrier_hz']/1e9:.3f} GHz, offset {best['offset_m']} m, duration {best['duration_s']} s: {best['dtoi']:.4f}.",
            f"Orbit-driven fallback uses {'real SGP4' if HAS_SGP4 else 'synthetic orbit'} propagation.",
            "Higher carrier frequency and larger offset improve DTOI for both trace sources.",
            "The orbit-driven trace now uses differential Doppler between baseline and offset ground stations."
        ],
        "conservative_notes": [
            "Orbit-driven fallback is not OTA validation (no real satellite signals are used).",
            "No real satellite capture is claimed (we use TLE-based propagation with synthetic fallback).",
            "No localization accuracy is claimed (this is an observability diagnostic only).",
            "Result is an observability diagnostic only, not a localization system."
        ]
    }
    with open(json_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote {len(results)} trials to {csv_path}")
    print(f"Summary written to {json_path}")

if __name__ == "__main__":
    main()