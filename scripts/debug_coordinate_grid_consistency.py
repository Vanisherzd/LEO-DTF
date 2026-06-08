#!/usr/bin/env python3
"""
Coordinate and Grid Consistency Diagnostic
============================================
Checks coordinate system sanity, grid coverage, and unit consistency.
"""

import sys, os, json, csv
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Coordinate and grid consistency diagnostic')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output-dir', default='experiments/results/debug_coordinate_grid')
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    os.makedirs(args.output_dir, exist_ok=True)

    # ---------- Scenario setup (matching run_monte_carlo_synthetic.py) ----------
    LAT0_DEG, LON0_DEG = 40.0, -105.0
    ALT0_KM = 1.5
    TRUE_OFFSET_EN = np.array([100.0, 50.0])  # meters
    E_MIN, E_MAX = -200.0, 200.0
    N_MIN, N_MAX = -200.0, 200.0
    STEP_M = 20.0
    CARRIER_FREQ_HZ = 1.6e9

    # Frame transforms
    from leodtf.frame_transform import geodetic_to_ecef, enu_to_ecef, ecef_to_enu
    from leodtf.orbit_propagation import propagate_orbit

    ref_ecef = np.array(geodetic_to_ecef(LAT0_DEG, LON0_DEG, ALT0_KM))

    # Build ENU basis (E, N, Up columns in ECEF)
    lat_r = np.radians(LAT0_DEG)
    lon_r = np.radians(LON0_DEG)
    slat, clat = np.sin(lat_r), np.cos(lat_r)
    slon, clon = np.sin(lon_r), np.cos(lon_r)
    e_vec = np.array([-slon, clon, 0.0])          # East
    n_vec = np.array([-slat*clon, -slat*slon, clat])  # North
    u_vec = np.array([clat*clon, clat*slon, slat])   # Up
    enu_basis = np.column_stack([e_vec, n_vec, u_vec])

    # True position ECEF
    true_offset_km = np.array([TRUE_OFFSET_EN[0], TRUE_OFFSET_EN[1], 0.0]) / 1000.0
    true_gs_ecef = ref_ecef + enu_basis @ true_offset_km

    true_en = TRUE_OFFSET_EN.copy()

    # ----- Check 1: ENU basis unit vectors -----
    e_len = float(np.linalg.norm(e_vec))
    n_len = float(np.linalg.norm(n_vec))
    u_len = float(np.linalg.norm(u_vec))
    enu_roundtrip_error_m = float(
        np.linalg.norm((enu_basis @ np.array([100.0, 50.0, 0.0])) -
                       (e_vec * 100.0 + n_vec * 50.0))
    )
    print(f"ENU basis unit lengths: E={e_len:.6f} N={n_len:.6f} U={u_len:.6f}")
    print(f"ENU roundtrip (linear combination) error: {enu_roundtrip_error_m:.10f} m")

    # ----- Check 2: 100m unit offset -----
    unit_east_ecef = enu_basis @ np.array([100.0, 0.0, 0.0])
    unit_offset_error_m = float(np.linalg.norm(unit_east_ecef) - 100.0)
    print(f"100m unit offset error: {unit_offset_error_m:.6f} m")

    # ----- Check 3: Build position grid -----
    e_vals = np.arange(E_MIN, E_MAX + STEP_M / 2, STEP_M)
    n_vals = np.arange(N_MIN, N_MAX + STEP_M / 2, STEP_M)
    grid_e, grid_n = np.meshgrid(e_vals, n_vals, indexing='ij')
    position_grid_en = np.stack([grid_e.ravel(), grid_n.ravel()], axis=1)
    grid_center_e = (E_MIN + E_MAX) / 2.0
    grid_center_n = (N_MIN + N_MAX) / 2.0

    # ----- Check 4: True position in grid -----
    true_in_grid = bool(
        E_MIN <= true_en[0] <= E_MAX and
        N_MIN <= true_en[1] <= N_MAX
    )
    print(f"True position in grid: {true_in_grid}  (E={true_en[0]}m, N={true_en[1]}m)")

    # ----- Check 5: Nearest grid cell -----
    idx_e = np.argmin(np.abs(e_vals - true_en[0]))
    idx_n = np.argmin(np.abs(n_vals - true_en[1]))
    nearest_e = e_vals[idx_e]
    nearest_n = n_vals[idx_n]
    nearest_true_cell_error_m = float(
        np.linalg.norm([true_en[0] - nearest_e, true_en[1] - nearest_n])
    )
    print(f"Nearest grid cell: E={nearest_e}m N={nearest_n}m  error={nearest_true_cell_error_m:.2f}m")

    # ----- Check 6: Orbit and Doppler consistency -----
    # Propagate a short orbit to check Doppler
    from datetime import datetime, timezone
    ref_time = datetime(2026, 6, 4, 12, 0, 0, tzinfo=timezone.utc)
    times_dt = [ref_time + timedelta(seconds=t) for t in [0, 300, 600]]
    line1 = "1 25544U 98067A   26155.53033517  .00012622  00000+0  28098-3 0  9994"
    line2 = "2 25544  51.6416 246.6182 0006706 302.2584 122.9105 15.50040302433475"
    sat_pos, sat_vel = propagate_orbit(line1, line2, times_dt)

    from leodtf.observation_model import ObservationModel
    obs_ref = ObservationModel(ref_ecef, carrier_freq_hz=CARRIER_FREQ_HZ)
    obs_true = ObservationModel(true_gs_ecef, carrier_freq_hz=CARRIER_FREQ_HZ)

    doppler_ref = []
    doppler_true = []
    for i in range(3):
        d_ref, _ = obs_ref.compute_expected_measurements((sat_pos[i], sat_vel[i]), 0.0)
        d_true, _ = obs_true.compute_expected_measurements((sat_pos[i], sat_vel[i]), 0.0)
        doppler_ref.append(d_ref)
        doppler_true.append(d_true)

    doppler_diff_means = float(np.mean(np.abs(np.array(doppler_ref) - np.array(doppler_true))))
    print(f"Mean Doppler difference (ref vs true location): {doppler_diff_means:.6f} Hz")

    # ----- Check 7: Run estimator and get MAP -----
    from leodtf.estimator_grid_map import estimate_grid_map, compute_hpd_region

    NUM_PACKETS = 20
    TOTAL_TIME_S = 600.0
    times_s = np.linspace(0, TOTAL_TIME_S, NUM_PACKETS)
    times_dt = [ref_time + timedelta(seconds=t) for t in times_s]
    sat_pos_pkt, sat_vel_pkt = propagate_orbit(line1, line2, times_dt)

    B0_TRUE = 50.0
    B1_TRUE = 0.1
    DELTA_T_TRUE = 0.001
    SIGMA_F = 1.0
    SIGMA_TAU = 1e-3

    # Generate observations from TRUE location
    observed_freq = np.zeros(NUM_PACKETS)
    observed_tau = np.zeros(NUM_PACKETS)
    for i in range(NUM_PACKETS):
        d, p = obs_true.compute_expected_measurements((sat_pos_pkt[i], sat_vel_pkt[i]), times_s[i])
        observed_freq[i] = d + B0_TRUE + B1_TRUE * times_s[i] + rng.normal(0, SIGMA_F)
        observed_tau[i] = times_s[i] + DELTA_T_TRUE + p + rng.normal(0, SIGMA_TAU)

    delta_t_grid = np.linspace(-0.01, 0.01, 21)

    posterior, map_pos_en, best_b0, best_b1, best_delta_t = estimate_grid_map(
        position_grid_en=position_grid_en,
        delta_t_grid=delta_t_grid,
        ground_station_ecef=ref_ecef,
        enu_basis=enu_basis,
        satellite_positions_ecsf=sat_pos_pkt,
        satellite_velocities_ecsf=sat_vel_pkt,
        nominal_times=times_s,
        observed_freq=observed_freq,
        observed_tau=observed_tau,
        carrier_freq_hz=CARRIER_FREQ_HZ,
        sigma_f=SIGMA_F,
        sigma_tau=SIGMA_TAU,
        b0_prior=(0.0, 100.0),
        b1_prior=(0.0, 1.0),
        delta_t_prior=(0.0, 0.01),
    )

    # ----- Check 8: MAP error -----
    map_error_m = float(np.linalg.norm(map_pos_en - true_en))
    delta_east_m = float(map_pos_en[0] - true_en[0])
    delta_north_m = float(map_pos_en[1] - true_en[1])
    print(f"MAP position: E={map_pos_en[0]:.1f}m N={map_pos_en[1]:.1f}m")
    print(f"MAP error: {map_error_m:.2f}m  (dE={delta_east_m:.1f}m, dN={delta_north_m:.1f}m)")

    # ----- Check 9: True cell rank -----
    posterior_2d = posterior.reshape(len(e_vals), len(n_vals))
    sorted_idx = np.argsort(posterior_2d.ravel())[::-1]
    gx, gy = np.meshgrid(range(len(e_vals)), range(len(n_vals)), indexing='ij')
    true_idx_e = int(np.argmin(np.abs(e_vals - true_en[0])))
    true_idx_n = int(np.argmin(np.abs(n_vals - true_en[1])))
    flat_idx = np.ravel_multi_index((true_idx_e, true_idx_n), posterior_2d.shape)
    true_rank = int(np.searchsorted(sorted_idx, flat_idx, side='right'))
    true_prob = float(posterior_2d[true_idx_e, true_idx_n])
    map_flat = np.ravel_multi_index(
        (int(np.argmin(np.abs(e_vals - map_pos_en[0]))),
         int(np.argmin(np.abs(n_vals - map_pos_en[1])))),
        posterior_2d.shape
    )
    map_rank = int(np.searchsorted(sorted_idx, map_flat, side='right'))
    map_prob = float(np.max(posterior))
    print(f"True cell rank: {true_rank}/{len(sorted_idx)}  prob={true_prob:.6f}")
    print(f"MAP cell rank: {map_rank}  prob={map_prob:.6f}")

    # ----- Check 10: Score at true vs MAP -----
    # Find score at true cell
    score_true = float(posterior_2d[true_idx_e, true_idx_n])
    score_map = float(np.max(posterior))
    print(f"Score at true cell: {score_true:.4f}  Score at MAP: {score_map:.4f}")

    # ----- Check 11: Posterior sum -----
    post_sum = float(posterior.sum())
    post_min = float(posterior.min())
    post_max = float(posterior.max())
    print(f"Posterior sum={post_sum:.4f}  min={post_min:.6f}  max={post_max:.6f}")

    # ----- Save results -----
    results = {
        'true_in_grid': true_in_grid,
        'true_en_m': true_en.tolist(),
        'grid_bounds_e_m': [float(E_MIN), float(E_MAX)],
        'grid_bounds_n_m': [float(N_MIN), float(N_MAX)],
        'grid_step_m': float(STEP_M),
        'grid_n_cells': len(position_grid_en),
        'nearest_true_cell_error_m': nearest_true_cell_error_m,
        'nearest_true_cell_en_m': [float(nearest_e), float(nearest_n)],
        'enu_roundtrip_error_m': enu_roundtrip_error_m,
        'unit_offset_error_m': unit_offset_error_m,
        'doppler_diff_ref_vs_true_hz': float(np.mean(np.abs(np.array(doppler_ref) - np.array(doppler_true)))),
        'map_pos_en_m': map_pos_en.tolist(),
        'map_error_m': map_error_m,
        'delta_east_m': delta_east_m,
        'delta_north_m': delta_north_m,
        'true_rank': true_rank,
        'true_n_cells': len(sorted_idx),
        'true_prob': true_prob,
        'map_rank': map_rank,
        'map_prob': map_prob,
        'score_true': score_true,
        'score_map': score_map,
        'posterior_sum': post_sum,
        'posterior_min': post_min,
        'posterior_max': post_max,
    }

    csv_path = os.path.join(args.output_dir, 'coordinate_grid_diagnostic.csv')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=results.keys())
        writer.writeheader()
        writer.writerow(results)

    json_path = os.path.join(args.output_dir, 'coordinate_grid_diagnostic.json')
    with open(json_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nCSV: {csv_path}")
    print(f"JSON: {json_path}")
    return 0

if __name__ == '__main__':
    sys.exit(main())