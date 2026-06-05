#!/usr/bin/env python3
"""
CRLB Sensitivity Diagnostic for LEO-DTF
----------------------------------------
Analyzes how CRLB RMSE lower bound varies with timestamp noise sigma_tau.

This script reuses the synthetic geometry from run_smoke_test.py to diagnose
the CRLB vs MAP mismatch observed in v0.1.

No performance claims are made. This is for diagnostic purposes only.
"""

import sys
import os
import numpy as np
from datetime import datetime, timedelta

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from leodtf.tle_loader import parse_tle
from leodtf.orbit_propagation import propagate_orbit
from leodtf.jacobian_crlb import (
    compute_crlb_en_position,
    crlb_ellipse_area,
    crlb_rmse_bound_m,
    crlb_cov_km2_to_m2
)

# Synthetic orbit fallback (same as run_smoke_test.py)
def get_synthetic_orbit(times_dt):
    """Generate synthetic circular orbit at 400 km altitude."""
    R = 6378.137 + 400.0  # km
    mu = 3.986004418e5
    n = np.sqrt(mu / R**3)  # rad/s
    
    sat_positions_ecef = []
    sat_velocities_ecef = []
    for dt in times_dt:
        t = (dt - times_dt[0]).total_seconds()
        angle = n * t
        x = R * np.cos(angle)
        y = R * np.sin(angle)
        z = 0.0
        vx = -R * n * np.sin(angle)
        vy = R * n * np.cos(angle)
        vz = 0.0
        sat_positions_ecef.append([x, y, z])
        sat_velocities_ecef.append([vx, vy, vz])
    
    return np.array(sat_positions_ecef), np.array(sat_velocities_ecef)


def main():
    print("LEO-DTF CRLB Sensitivity Diagnostic")
    print("=" * 60)
    print()
    
    # Scenario setup (matches run_smoke_test.py)
    lat0_deg = 40.0
    lon0_deg = -105.0
    alt0_km = 1.5
    gs_ref_geodetic = (lat0_deg, lon0_deg, alt0_km)
    gs_enu_offset_true = (0.0, 0.0)  # km
    
    delta_t_true = 0.0
    b0_true = 0.0
    b1_true = 0.0
    carrier_freq_hz = 1.6e9
    
    num_packets = 20
    total_time_s = 600.0
    times_s = np.linspace(0, total_time_s, num_packets)
    ref_time = datetime(2026, 6, 4, 12, 0, 0)
    times_dt = [ref_time + timedelta(seconds=t) for t in times_s]
    
    # Get satellite orbit (synthetic fallback)
    print("Using synthetic circular orbit (400 km altitude, equatorial)")
    print(f"Ground station: {lat0_deg}N, {lon0_deg}W, {alt0_km} km")
    print(f"Observations: {num_packets} packets over {total_time_s} s")
    print()
    
    sat_positions_ecef, sat_velocities_ecef = get_synthetic_orbit(times_dt)
    
    # Test different sigma_tau values
    sigma_f = 1.0  # Hz (fixed)
    sigma_tau_values = [1e-3, 1e-4, 1e-5, 1e-6]  # seconds
    
    c_km_s = 299792.458  # speed of light in km/s
    
    print("CRLB Sensitivity to Timestamp Noise (sigma_f = 1.0 Hz fixed)")
    print("-" * 90)
    print(f"{'sigma_tau (s)':<15} {'range_noise (km)':<18} {'RMSE bound (m)':<16} {'std_E (m)':<12} {'std_N (m)':<12} {'finite'}")
    print("-" * 90)
    
    results = []
    for sigma_tau in sigma_tau_values:
        crlb_cov = compute_crlb_en_position(
            sat_positions_ecef, sat_velocities_ecef,
            gs_ref_geodetic, carrier_freq_hz, times_s,
            delta_t_true, b0_true, b1_true, gs_enu_offset_true,
            sigma_f=sigma_f, sigma_tau=sigma_tau
        )
        
        crlb_finite = not np.any(np.isnan(crlb_cov))
        rmse_bound_m = crlb_rmse_bound_m(crlb_cov) if crlb_finite else float('nan')
        crlb_cov_m2 = crlb_cov_km2_to_m2(crlb_cov) if crlb_finite else np.full((2, 2), np.nan)
        std_e_m = np.sqrt(crlb_cov_m2[0, 0]) if crlb_finite else float('nan')
        std_n_m = np.sqrt(crlb_cov_m2[1, 1]) if crlb_finite else float('nan')
        range_noise_km = sigma_tau * c_km_s
        
        results.append({
            'sigma_tau': sigma_tau,
            'range_noise_km': range_noise_km,
            'rmse_bound_m': rmse_bound_m,
            'std_e_m': std_e_m,
            'std_n_m': std_n_m,
            'finite': crlb_finite
        })
        
        finite_str = "Yes" if crlb_finite else "No (NaN)"
        print(f"{sigma_tau:<15.1e} {range_noise_km:<18.3f} {rmse_bound_m:<16.2f} {std_e_m:<12.2f} {std_n_m:<12.2f} {finite_str}")
    
    print("-" * 90)
    print()
    
    # Analysis
    print("Analysis:")
    print("-" * 60)
    
    # Check trend
    finite_results = [r for r in results if r['finite']]
    if len(finite_results) >= 2:
        first_rmse = finite_results[0]['rmse_bound_m']
        last_rmse = finite_results[-1]['rmse_bound_m']
        if not np.isnan(first_rmse) and not np.isnan(last_rmse):
            if last_rmse < first_rmse:
                print("✓ CRLB RMSE decreases as sigma_tau decreases (expected)")
            elif last_rmse > first_rmse:
                print("✗ WARNING: CRLB RMSE increases as sigma_tau decreases (unexpected)")
            else:
                print("! CRLB RMSE unchanged (may be Doppler-limited)")
    
    # Check if sigma_tau=1ms is an outlier
    if results[0]['finite'] and results[0]['rmse_bound_m'] > 1e5:
        print(f"! sigma_tau=1ms gives RMSE > 100 km: timestamp information is negligible")
        print(f"  At sigma_tau=1ms, range noise = {results[0]['range_noise_km']:.0f} km")
        print("  This overwhelms the weak position sensitivity of propagation delay.")
    
    print()
    print("Recommendations:")
    print("-" * 60)
    print("1. For realistic CRLB, sigma_tau should be <= 10 microseconds")
    print("   (corresponding to ~3 km range noise or better)")
    print("2. The classical CRLB assumes unbiased estimation (no priors on b0/b1)")
    print("3. The MAP estimator uses priors, which regularizes the b0-position correlation")
    print("4. Therefore, MAP error and classical CRLB are not directly comparable")
    print()
    print("See docs/research_phase2_notes.md for detailed discussion.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
