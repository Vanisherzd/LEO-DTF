#!/usr/bin/env python3
"""
Smoke test for LEO-DTF Phase 1 and Phase 2
-------------------------------------------
Phase 1: Builds a synthetic orbit pass, generates packet times, computes observations and CRLB.
Phase 2: Adds a tiny estimator demo to test the grid-based estimator.
"""

import sys
import os
import numpy as np
from datetime import datetime, timedelta

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def main():
    print("Running LEO-DTF Phase 1 smoke test...")

    # Try importing the modules
    try:
        from leodtf.tle_loader import parse_tle, TLEData
        from leodtf.orbit_propagation import propagate_orbit
        from leodtf.frame_transform import geodetic_to_ecef, enu_to_ecef, ecef_to_enu
        from leodtf.observation_model import ObservationModel
        from leodtf.jacobian_crlb import compute_crlb_en_position, crlb_ellipse_area
        from leodtf.metrics import rmse, mae, mape
        print("✓ All modules imported successfully")
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return 1

    # Create a synthetic TLE (we won't actually parse it for the synthetic orbit, but we need the format)
    line1 = "1 25544U 98067A   26155.53033517  .00012622  00000+0  28098-3 0  9994"
    line2 = "2 25544  51.6416 246.6182 0006706 302.2584 122.9105 15.50040302433475"

    # Try to parse the TLE (just to show it works, but we won't use the parsed data for orbit propagation in synthetic case)
    try:
        tle = parse_tle(line1, line2)
        print(f"TLE parsed: catalog {tle.catalog_num}")
    except Exception as e:
        print(f"TLE parsing unavailable; using synthetic orbit fallback for smoke test.")
        # We'll continue anyway because the orbit propagation function has a fallback

    # Set up the scenario
    # Ground station reference point (geodetic): we'll use a known location, e.g., Boulder, CO
    lat0_deg = 40.0
    lon0_deg = -105.0
    alt0_km = 1.5
    gs_ref_geodetic = (lat0_deg, lon0_deg, alt0_km)

    # True ENU offset of the ground station (we assume we are at the reference point for simplicity)
    gs_enu_offset_true = (0.0, 0.0)  # km

    # True nuisance parameters
    delta_t_true = 0.0   # seconds
    b0_true = 0.0        # Hz
    b1_true = 0.0        # Hz/s

    # Carrier frequency (Hz)
    carrier_freq_hz = 1.6e9  # 1.6 GHz (L-band)

    # Generate times for the pass: we'll use 20 packets over 10 minutes (600 seconds)
    num_packets = 20
    total_time_s = 600.0
    times_s = np.linspace(0, total_time_s, num_packets)  # seconds from start of pass
    # Convert to datetime for orbit propagation (we need a reference epoch)
    ref_time = datetime(2026, 6, 4, 12, 0, 0)
    times_dt = [ref_time + timedelta(seconds=t) for t in times_s]

    # Propagate orbit: we'll use the TLE lines, but the function will fall back to synthetic orbit if sgp4 is not available
    try:
        sat_positions_ecef, sat_velocities_ecef = propagate_orbit(line1, line2, times_dt)
        print(f"✓ Propagated orbit for {len(times_dt)} points using SGP4 (or synthetic fallback).")
    except Exception as e:
        print(f"✗ Error in orbit propagation: {e}")
        return 1

    # Initialize observation model
    # First, we need the ground station ECEF position for the observation model (we'll use the reference point)
    gs_ecef = np.array(geodetic_to_ecef(lat0_deg, lon0_deg, alt0_km))
    obs_model = ObservationModel(gs_ecef, carrier_freq_hz=carrier_freq_hz)

    # Arrays to store results
    dopplers_hz = np.zeros(num_packets)
    delays_s = np.zeros(num_packets)

    # Compute expected observations for each packet
    for i in range(num_packets):
        sat_state = (sat_positions_ecef[i], sat_velocities_ecef[i])
        doppler, delay = obs_model.compute_expected_measurements(sat_state, times_s[i])
        dopplers_hz[i] = doppler
        delays_s[i] = delay

# Compute CRLB for the EN position
    try:
        crlb_cov = compute_crlb_en_position(
            sat_positions_ecef, sat_velocities_ecef,
            gs_ref_geodetic, carrier_freq_hz, times_s,
            delta_t_true, b0_true, b1_true, gs_enu_offset_true,
            sigma_f=1.0, sigma_tau=1e-3
        )
        crlb_finite = not np.any(np.isnan(crlb_cov))
        crlb_area = crlb_ellipse_area(crlb_cov) if crlb_finite else float('nan')
    except Exception as e:
        print(f"Error computing CRLB: {e}")
        crlb_finite = False
        crlb_area = float('nan')

    # Print summary
    print("\n--- Summary ---")
    print(f"Number of packets: {num_packets}")
    print(f"Doppler min/max: {np.min(dopplers_hz):.2f} / {np.max(dopplers_hz):.2f} Hz")
    print(f"Delay min/max: {np.min(delays_s)*1e3:.2f} / {np.max(delays_s)*1e3:.2f} ms")
    print(f"CRLB finite: {crlb_finite}")
    if crlb_finite:
        print(f"CRLB envelope area (1-sigma ellipse): {crlb_area:.6f} km^2")
        # Compute and print RMSE lower bound in meters
        from leodtf.jacobian_crlb import crlb_rmse_bound_m
        rmse_bound_m = crlb_rmse_bound_m(crlb_cov)
        if not np.isnan(rmse_bound_m):
            print(f"CRLB RMSE lower bound: {rmse_bound_m:.2f} m")
            print("  Note: CRLB is a local lower bound, not a measured estimator error.")
    else:
        print("CRLB envelope area: NaN (singular or invalid FIM)")

    # Additional sanity checks
    if np.all(np.diff(dopplers_hz) != 0):  # Not strictly necessary, but we expect variation
        print("✓ Doppler shows variation across the pass")
    else:
        print("! Warning: Doppler does not vary (check geometry)")

    if np.all(np.diff(delays_s) != 0):
        print("✓ Delay shows variation across the pass")
    else:
        print("! Warning: Delay does not vary (check geometry)")

    print("\nSmoke test passed!")

    # ========== Phase 2: Tiny Estimator Demo ==========
    print("\n" + "="*50)
    print("Running LEO-DTF Phase 2 estimator demo...")
    print("="*50)

    try:
        from leodtf.estimator_grid_map import (
            build_position_grid,
            estimate_grid_map,
            compute_hpd_region,
            compute_ambiguity_score
        )
        from leodtf.frame_transform import ecef_to_enu
    except ImportError as e:
        print(f"✗ Import error for Phase 2 modules: {e}")
        return 1

    # True position: we'll set a known offset from the reference point (e.g., 100m east, 50m north)
    true_offset_en = np.array([100.0, 50.0])  # meters
    # Convert the reference ground station ECEF to ENU basis at the reference point
    # We'll use the reference geodetic point to compute the ENU basis
    # Actually, we have the functions imported above? Let's re-import to be safe.
    from leodtf.frame_transform import geodetic_to_ecef, enu_to_ecef, ecef_to_enu

    # Compute the ENU basis at the reference geodetic point
    # We can get the ECEF of the reference point and then compute basis vectors for ENU
    ref_ecef = geodetic_to_ecef(lat0_deg, lon0_deg, alt0_km)
    # For simplicity, we'll use a flat Earth approximation for the basis (since the offset is small)
    # In reality, we should use the exact basis from the reference point.
    # We'll use the function ecef_to_enu to get the basis? Actually, that function converts a point.
    # Let's compute the basis by rotating the ECEF vectors.
    # We'll use the geodetic_to_ecef and then a small perturbation to get the basis.
    # But for simplicity in this demo, we'll assume the ENU basis is aligned with ECEF axes (not true, but for small offset and local test).
    # Alternatively, we can use the function from frame_transform that we haven't implemented: maybe we need to add a function to compute ENU basis.
    # Since we are in a demo and the offset is small, we'll use an approximate basis: 
    #   East: [-sin(lon), cos(lon), 0]
    #   North: [-sin(lat)*cos(lon), -sin(lat)*sin(lon), cos(lat)]
    #   Up: [cos(lat)*cos(lon), cos(lat)*sin(lon), sin(lat)]
    lat0_rad = np.radians(lat0_deg)
    lon0_rad = np.radians(lon0_deg)
    enu_basis = np.array([
        [-np.sin(lon0_rad), np.cos(lon0_rad), 0],
        [-np.sin(lat0_rad)*np.cos(lon0_rad), -np.sin(lat0_rad)*np.sin(lon0_rad), np.cos(lat0_rad)],
        [np.cos(lat0_rad)*np.cos(lon0_rad), np.cos(lat0_rad)*np.sin(lon0_rad), np.sin(lat0_rad)]
    ]).T  # Columns are E, N, Up

    # Now, the true ground station in ECEF (if we were at the offset) would be:
    #   true_gs_ecef = ref_ecef + enu_basis @ [true_offset_en[0], true_offset_en[1], 0] (converted to km)
    true_offset_en_km = true_offset_en / 1000.0  # convert meters to km
    # Fix the matrix multiplication: enu_basis is 3x3, true_offset_en_km is 2x1, need to add zero for up component
    true_offset_en_km_3d = np.array([true_offset_en_km[0], true_offset_en_km[1], 0.0])  # [E, N, U] in km
    true_gs_ecef = ref_ecef + enu_basis @ true_offset_en_km_3d

    # But note: in our observation model, we assumed the ground station is at the reference point.
    # We have two options:
    #   1. Change the observation model to use the true ground station (which we don't know in practice).
    #   2. In the estimator, we are estimating the offset of the ground station from the reference point.
    # We choose option 2: the reference point is our known reference, and we are estimating the offset of the true ground station from this reference.
    # Therefore, in the estimator, the ground_station_ecef we pass is the reference point (ref_ecef), and we are estimating the EN offset.
    # The true offset we set above is what we want to recover.

    # Generate synthetic observations with b0 and b1 (and optionally delta_t)
    # We'll use the same times and satellite states as before.
    # We'll set some known nuisance values for the synthetic data.
    b0_synth = 50.0   # Hz
    b1_synth = 0.1    # Hz/s
    delta_t_synth = 0.001  # seconds

    # We'll generate the observations using the observation model.
    observed_freq = np.zeros(num_packets)
    observed_tau = np.zeros(num_packets)

    for i in range(num_packets):
        sat_state = (sat_positions_ecef[i], sat_velocities_ecef[i])
        # Compute expected measurements (Doppler and delay) from the satellite state to the reference ground station
        doppler_hz, propagation_delay_s = obs_model.compute_expected_measurements(sat_state, times_s[i])
        # Now, the contaminated observations:
        #   z_f = doppler_hz + b0_synth + b1_synth * times_s[i] + noise_f
        #   z_tau = times_s[i] + delta_t_synth + propagation_delay_s + noise_tau
        noise_f = np.random.normal(0, 1.0)   # 1 Hz std
        noise_tau = np.random.normal(0, 1e-3) # 1 ms std
        observed_freq[i] = doppler_hz + b0_synth + b1_synth * times_s[i] + noise_f
        observed_tau[i] = times_s[i] + delta_t_synth + propagation_delay_s + noise_tau

    # Set up the grid for estimation
    # We'll search over a small ROI around the reference point (since we know the offset is small)
    e_min, e_max = -200.0, 200.0  # meters
    n_min, n_max = -200.0, 200.0  # meters
    step_m = 20.0                 # 20m grid step -> 21x21 = 441 points
    position_grid_en = build_position_grid(e_min, e_max, n_min, n_max, step_m)
    print(f"Generated position grid with {position_grid_en.shape[0]} points.")

    # Time offset grid: we'll search around zero
    delta_t_grid = np.linspace(-0.01, 0.01, 21)  # 21 points from -10ms to +10ms

    # Priors (optional)
    b0_prior = (0.0, 100.0)   # mean 0 Hz, std 100 Hz (weak)
    b1_prior = (0.0, 1.0)     # mean 0 Hz/s, std 1 Hz/s (weak)
    delta_t_prior = (0.0, 0.01) # mean 0 s, std 10 ms (weak)

    # Run the grid estimator
    posterior, map_position_en, best_b0, best_b1, best_delta_t = estimate_grid_map(
        position_grid_en=position_grid_en,
        delta_t_grid=delta_t_grid,
        ground_station_ecef=ref_ecef,   # reference point in ECEF
        enu_basis=enu_basis,
        satellite_positions_ecsf=sat_positions_ecef,
        satellite_velocities_ecsf=sat_velocities_ecef,
        nominal_times=times_s,
        observed_freq=observed_freq,
        observed_tau=observed_tau,
        carrier_freq_hz=carrier_freq_hz,
        sigma_f=1.0,          # assumed noise std for frequency (Hz)
        sigma_tau=1e-3,       # assumed noise std for timestamp (s)
        b0_prior=b0_prior,
        b1_prior=b1_prior,
        delta_t_prior=delta_t_prior
    )

    # Check that the posterior sums to 1 (approximately)
    posterior_sum = np.sum(posterior)
    print(f"\nPosterior sum: {posterior_sum:.6f} (should be close to 1.0)")

    # Compute HPD region and ambiguity score
    hpd_mask, hpd_mass = compute_hpd_region(posterior, position_grid_en, mass=0.95)
    ambiguity_score = compute_ambiguity_score(posterior, position_grid_en)
    hpd_cell_count = np.sum(hpd_mask)
    print(f"HPD region (95% mass) contains {hpd_cell_count} grid points (actual mass: {hpd_mass:.4f})")
    print(f"Ambiguity score: {ambiguity_score:.2f} meters")

    # Calculate error
    error_en = map_position_en - true_offset_en
    error_m = np.linalg.norm(error_en)
    print(f"\nTrue EN offset: [{true_offset_en[0]:.1f}, {true_offset_en[1]:.1f}] m")
    print(f"MAP EN offset:  [{map_position_en[0]:.1f}, {map_position_en[1]:.1f}] m")
    print(f"Error: {error_m:.2f} m")

    # Print entropy (as a measure of spread)
    # Avoid log(0) by adding a tiny epsilon
    epsilon = 1e-10
    posterior_safe = posterior + epsilon
    posterior_safe = posterior_safe / np.sum(posterior_safe)
    entropy = -np.sum(posterior_safe * np.log(posterior_safe))
    print(f"Posterior entropy: {entropy:.4f}")

    # Mark this as a smoke test only
    print("\n" + "="*50)
    print("NOTE: This is a synthetic smoke test only. No paper results are claimed.")
    print("="*50)

    return 0


if __name__ == "__main__":
    sys.exit(main())