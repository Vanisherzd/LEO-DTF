#!/usr/bin/env python3
"""
Posterior Score Surface Diagnostic
===================================
Deep-dives into the posterior score at the true cell vs MAP cell,
score sign check, posterior normalization, and true cell ranking.
"""

import sys, os, json, csv
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output-dir', default='experiments/results/debug_posterior_score')
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    os.makedirs(args.output_dir, exist_ok=True)

    from leodtf.frame_transform import geodetic_to_ecef
    from leodtf.orbit_propagation import propagate_orbit
    from leodtf.observation_model import ObservationModel
    from leodtf.estimator_grid_map import estimate_grid_map

    # Standard scenario
    LAT0_DEG, LON0_DEG = 40.0, -105.0
    ALT0_KM = 1.5
    TRUE_OFFSET_EN = np.array([100.0, 50.0])
    E_MIN, E_MAX = -200.0, 200.0
    N_MIN, N_MAX = -200.0, 200.0
    STEP_M = 20.0
    CARRIER_FREQ_HZ = 1.6e9
    B0_TRUE, B1_TRUE, DELTA_T_TRUE = 50.0, 0.1, 0.001
    SIGMA_F, SIGMA_TAU = 1.0, 1e-3
    NUM_PACKETS, TOTAL_TIME_S = 20, 600.0

    ref_ecef = np.array(geodetic_to_ecef(LAT0_DEG, LON0_DEG, ALT0_KM))
    lat_r, lon_r = np.radians(LAT0_DEG), np.radians(LON0_DEG)
    slat, clat = np.sin(lat_r), np.cos(lat_r)
    slon, clon = np.sin(lon_r), np.cos(lon_r)
    enu_basis = np.column_stack([
        np.array([-slon, clon, 0.0]),
        np.array([-slat*clon, -slat*slon, clat]),
        np.array([clat*clon, clat*slon, slat]),
    ])

    true_offset_km = np.array([TRUE_OFFSET_EN[0], TRUE_OFFSET_EN[1], 0.0]) / 1000.0
    true_gs_ecef = ref_ecef + enu_basis @ true_offset_km
    true_en = TRUE_OFFSET_EN.copy()

    # Build grid
    e_vals = np.arange(E_MIN, E_MAX + STEP_M / 2, STEP_M)
    n_vals = np.arange(N_MIN, N_MAX + STEP_M / 2, STEP_M)
    grid_e, grid_n = np.meshgrid(e_vals, n_vals, indexing='ij')
    position_grid_en = np.stack([grid_e.ravel(), grid_n.ravel()], axis=1)
    delta_t_grid = np.linspace(-0.01, 0.01, 21)

    # Propagate orbit
    ref_time = datetime(2026, 6, 4, 12, 0, 0)
    times_s = np.linspace(0, TOTAL_TIME_S, NUM_PACKETS)
    times_dt = [ref_time + timedelta(seconds=t) for t in times_s]
    line1 = "1 25544U 98067A   26155.53033517  .00012622  00000+0  28098-3 0  9994"
    line2 = "2 25544  51.6416 246.6182 0006706 302.2584 122.9105 15.50040302433475"
    sat_pos, sat_vel = propagate_orbit(line1, line2, times_dt)

    # Generate observations from true location
    obs_true = ObservationModel(true_gs_ecef, carrier_freq_hz=CARRIER_FREQ_HZ)
    observed_freq = np.zeros(NUM_PACKETS)
    observed_tau = np.zeros(NUM_PACKETS)
    for i in range(NUM_PACKETS):
        d, p = obs_true.compute_expected_measurements((sat_pos[i], sat_vel[i]), times_s[i])
        observed_freq[i] = d + B0_TRUE + B1_TRUE * times_s[i] + rng.normal(0, SIGMA_F)
        observed_tau[i] = times_s[i] + DELTA_T_TRUE + p + rng.normal(0, SIGMA_TAU)

    posterior, map_pos_en, best_b0, best_b1, best_delta_t = estimate_grid_map(
        position_grid_en=position_grid_en,
        delta_t_grid=delta_t_grid,
        ground_station_ecef=ref_ecef,
        enu_basis=enu_basis,
        satellite_positions_ecsf=sat_pos,
        satellite_velocities_ecsf=sat_vel,
        nominal_times=times_s,
        observed_freq=observed_freq,
        observed_tau=observed_tau,
        carrier_freq_hz=CARRIER_FREQ_HZ,
        sigma_f=SIGMA_F,
        sigma_tau=SIGMA_TAU,
        b0_prior=(0.0, 100.0), b1_prior=(0.0, 1.0), delta_t_prior=(0.0, 0.01),
    )

    posterior_2d = posterior.reshape(len(e_vals), len(n_vals))
    sorted_flat = np.argsort(posterior_2d.ravel())[::-1]

    # True cell
    t_e_idx = int(np.argmin(np.abs(e_vals - true_en[0])))
    t_n_idx = int(np.argmin(np.abs(n_vals - true_en[1])))
    t_flat = np.ravel_multi_index((t_e_idx, t_n_idx), posterior_2d.shape)
    true_rank = int(np.searchsorted(sorted_flat, t_flat, side='right'))
    true_prob = float(posterior_2d[t_e_idx, t_n_idx])
    true_prob_norm = true_prob / posterior.sum() if posterior.sum() > 0 else 0.0

    # MAP cell
    map_e_idx = int(np.argmin(np.abs(e_vals - map_pos_en[0])))
    map_n_idx = int(np.argmin(np.abs(n_vals - map_pos_en[1])))
    m_flat = np.ravel_multi_index((map_e_idx, map_n_idx), posterior_2d.shape)
    map_rank = int(np.searchsorted(sorted_flat, m_flat, side='right'))
    map_prob = float(posterior_2d[map_e_idx, map_n_idx])

    # Check if flipping score sign would make true cell better
    # (just a sanity check — not actually flipping)
    top1_cells = np.unravel_index(sorted_flat[:1], posterior_2d.shape)
    top5_cells = np.unravel_index(sorted_flat[:5], posterior_2d.shape)
    top10_cells = np.unravel_index(sorted_flat[:10], posterior_2d.shape)
    top50_cells = np.unravel_index(sorted_flat[:50], posterior_2d.shape)

    true_in_top1 = bool(t_flat == sorted_flat[0])
    true_in_top5 = bool(t_flat in sorted_flat[:5])
    true_in_top10 = bool(t_flat in sorted_flat[:10])
    true_in_top50 = bool(t_flat in sorted_flat[:50])

    # Score at specific cells (raw scores, lower is better)
    from leodtf.estimator_grid_map import score_candidate
    score_true, b0_t, b1_t = score_candidate(
        true_en, 0.001, ref_ecef, enu_basis,
        sat_pos, sat_vel, times_s, observed_freq, observed_tau,
        CARRIER_FREQ_HZ, SIGMA_F, SIGMA_TAU,
        (0.0, 100.0), (0.0, 1.0), (0.0, 0.01),
    )
    score_map, b0_m, b1_m = score_candidate(
        map_pos_en, best_delta_t, ref_ecef, enu_basis,
        sat_pos, sat_vel, times_s, observed_freq, observed_tau,
        CARRIER_FREQ_HZ, SIGMA_F, SIGMA_TAU,
        (0.0, 100.0), (0.0, 1.0), (0.0, 0.01),
    )
    # Also check score at grid center (0, 0)
    score_center, _, _ = score_candidate(
        np.array([0.0, 0.0]), 0.001, ref_ecef, enu_basis,
        sat_pos, sat_vel, times_s, observed_freq, observed_tau,
        CARRIER_FREQ_HZ, SIGMA_F, SIGMA_TAU,
        (0.0, 100.0), (0.0, 1.0), (0.0, 0.01),
    )

    # Posterior normalization check
    post_sum = float(posterior.sum())
    post_min = float(posterior.min())
    post_max = float(posterior.max())
    post_entropy = float(-np.sum(posterior * np.log(posterior + 1e-300)))

    # HPD coverage: simple top-k approach
    total_mass = posterior.sum()
    sorted_cells = np.argsort(posterior.ravel())[::-1]
    cumsum = np.cumsum(posterior.ravel()[sorted_cells])
    for frac in [0.5, 0.8, 0.9, 0.95]:
        n_cells = int(np.searchsorted(cumsum, frac)) + 1
        top_cells = sorted_cells[:n_cells]
        top_set = set(top_cells)
        if t_flat in top_set:
            print(f"  True cell in top-{frac*100:.0f}% HPD ({n_cells} cells, {cumsum[min(n_cells-1, len(cumsum)-1)]:.3f} mass)")

    results = {
        'true_in_grid': bool(E_MIN <= true_en[0] <= E_MAX and N_MIN <= true_en[1] <= N_MAX),
        'true_en_m': true_en.tolist(),
        'map_pos_en_m': map_pos_en.tolist(),
        'map_error_m': float(np.linalg.norm(map_pos_en - true_en)),
        'delta_east_m': float(map_pos_en[0] - true_en[0]),
        'delta_north_m': float(map_pos_en[1] - true_en[1]),
        'true_rank': true_rank,
        'true_n_cells': len(sorted_flat),
        'true_prob': true_prob,
        'true_prob_normalized': true_prob_norm,
        'map_rank': map_rank,
        'map_prob': map_prob,
        'score_true_cell': float(score_true),
        'score_map_cell': float(score_map),
        'score_grid_center': float(score_center),
        'score_difference_true_minus_center': float(score_true - score_center),
        'score_difference_true_minus_map': float(score_true - score_map),
        'b0_at_true': float(b0_t),
        'b1_at_true_hz_s': float(b1_t),
        'b0_at_map': float(b0_m),
        'b1_at_map_hz_s': float(b1_m),
        'true_in_top1': true_in_top1,
        'true_in_top5': true_in_top5,
        'true_in_top10': true_in_top10,
        'true_in_top50': true_in_top50,
        'posterior_sum': post_sum,
        'posterior_min': post_min,
        'posterior_max': post_max,
        'posterior_entropy': post_entropy,
        'posterior_normalized_ok': bool(abs(post_sum - 1.0) < 0.01),
    }

    csv_path = os.path.join(args.output_dir, 'posterior_score_surface.csv')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=results.keys())
        writer.writeheader()
        writer.writerow(results)

    json_path = os.path.join(args.output_dir, 'posterior_score_surface.json')
    with open(json_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"Score at TRUE cell:     {score_true:.6f}")
    print(f"Score at GRID CENTER:   {score_center:.6f}")
    print(f"Score at MAP cell:       {score_map:.6f}")
    print(f"True cell rank: {true_rank}/{len(sorted_flat)}  prob={true_prob:.6f}")
    print(f"MAP cell rank: {map_rank}  prob={map_prob:.6f}")
    print(f"Posterior sum={post_sum:.4f}  entropy={post_entropy:.2f}")
    print(f"\nCSV: {csv_path}")
    print(f"JSON: {json_path}")
    return 0

if __name__ == '__main__':
    sys.exit(main())