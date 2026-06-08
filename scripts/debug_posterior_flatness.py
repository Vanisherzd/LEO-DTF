#!/usr/bin/env python3
"""
Debug: Posterior Flatness Diagnostic
=====================================
After fixing the meter/km bug, the posterior became nearly flat.
Diagnoses whether flatness comes from residual variance mismatch,
insufficient Doppler sensitivity, or score scale issues.

Outputs:
  experiments/results/debug_posterior_flatness/posterior_flatness_diagnostic.json
  experiments/results/debug_posterior_flatness/posterior_flatness_scores.csv
"""

import sys, os, json, csv
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def compute_residuals_clean(position_en, delta_t, ref_ecef, enu_basis,
                             sat_pos, sat_vel, times_s,
                             observed_freq, carrier_freq_hz):
    """Compute noise-only Doppler residuals with b0/b1 removed.

    observed_freq is the Doppler shift offset (Hz) from the carrier.
    Returns (residuals_clean, raw_residuals, b0b1_fit).
    """
    N = len(times_s)
    residuals = np.zeros(N)

    offset_ecef = enu_basis @ np.append(position_en / 1000.0, 0.0)
    candidate_ecef = ref_ecef + offset_ecef

    c_km_s = 299792.458  # speed of light in km/s

    for i in range(N):
        los = sat_pos[i] - candidate_ecef
        los_unit = los / np.linalg.norm(los)
        range_rate = np.dot(sat_vel[i], los_unit)  # km/s
        pred_doppler = -range_rate * carrier_freq_hz / c_km_s
        residuals[i] = observed_freq[i] - pred_doppler

    # Remove optimal b0/b1 via lstsq (same as score_candidate does internally)
    t_rel = times_s - times_s[0]
    A = np.column_stack([np.ones(N), t_rel])
    b0b1, _, _, _ = np.linalg.lstsq(A, residuals, rcond=None)
    residuals_clean = residuals - (b0b1[0] + b0b1[1] * t_rel)

    return residuals_clean, residuals, b0b1


def residual_stats(residuals, sigma_f):
    """Compute statistics from a residual vector (already clean, no b0/b1)."""
    n = len(residuals)
    dof = max(n - 2, 1)
    rms = float(np.sqrt(np.mean(residuals**2)))
    var = float(np.var(residuals))
    mean_val = float(np.mean(residuals))
    max_abs = float(np.max(np.abs(residuals)))
    chi2 = float(np.sum((residuals / sigma_f)**2))
    red_chi2 = chi2 / dof
    return dict(
        residual_mean_hz=mean_val,
        residual_std_hz=float(np.std(residuals)),
        residual_rms_hz=rms,
        residual_var_hz2=var,
        residual_max_abs_hz=max_abs,
        num_observations=n,
        expected_sigma_f_hz=sigma_f,
        normalized_chi2=chi2,
        reduced_chi2=red_chi2,
    )


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output-dir', default='experiments/results/debug_posterior_flatness')
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    os.makedirs(args.output_dir, exist_ok=True)

    from leodtf.frame_transform import geodetic_to_ecef
    from leodtf.orbit_propagation import propagate_orbit
    from leodtf.observation_model import ObservationModel
    from leodtf.estimator_grid_map import estimate_grid_map, score_candidate

    # Scenario (matches debug_posterior_score_surface.py)
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

    # Run estimator
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

    # MAP cell
    map_e_idx = int(np.argmin(np.abs(e_vals - map_pos_en[0])))
    map_n_idx = int(np.argmin(np.abs(n_vals - map_pos_en[1])))
    map_prob = float(posterior_2d[map_e_idx, map_n_idx])
    map_error = float(np.linalg.norm(map_pos_en - true_en))

    # Part A: Score distribution
    score_true, _, _ = score_candidate(
        true_en, DELTA_T_TRUE, ref_ecef, enu_basis,
        sat_pos, sat_vel, times_s, observed_freq, observed_tau,
        CARRIER_FREQ_HZ, SIGMA_F, SIGMA_TAU,
        (0.0, 100.0), (0.0, 1.0), (0.0, 0.01),
    )
    score_map, _, _ = score_candidate(
        map_pos_en, best_delta_t, ref_ecef, enu_basis,
        sat_pos, sat_vel, times_s, observed_freq, observed_tau,
        CARRIER_FREQ_HZ, SIGMA_F, SIGMA_TAU,
        (0.0, 100.0), (0.0, 1.0), (0.0, 0.01),
    )
    score_center, _, _ = score_candidate(
        np.array([0.0, 0.0]), DELTA_T_TRUE, ref_ecef, enu_basis,
        sat_pos, sat_vel, times_s, observed_freq, observed_tau,
        CARRIER_FREQ_HZ, SIGMA_F, SIGMA_TAU,
        (0.0, 100.0), (0.0, 1.0), (0.0, 0.01),
    )

    # All grid scores
    all_scores = []
    for g in range(len(position_grid_en)):
        pos = position_grid_en[g]
        sc, _, _ = score_candidate(
            pos, 0.0, ref_ecef, enu_basis,
            sat_pos, sat_vel, times_s, observed_freq, observed_tau,
            CARRIER_FREQ_HZ, SIGMA_F, SIGMA_TAU,
            (0.0, 100.0), (0.0, 1.0), (0.0, 0.01),
        )
        err = float(np.linalg.norm(pos - true_en))
        all_scores.append(dict(
            idx=g, e=float(pos[0]), n=float(pos[1]),
            score=float(sc), error_m=err,
            prob=float(posterior[g]),
        ))
    all_scores.sort(key=lambda x: x["score"])
    score_vals = np.array([s["score"] for s in all_scores])

    score_dynamic_range = float(score_vals.max() - score_vals.min())
    score_mean = float(score_vals.mean())
    score_std = float(score_vals.std())
    p01, p05, p50, p95, p99 = (float(np.percentile(score_vals, q))
                                for q in [1, 5, 50, 95, 99])

    top10_gaps = []
    for i in range(min(10, len(score_vals) - 1)):
        top10_gaps.append(float(score_vals[i + 1] - score_vals[i]))

    # Part B: Posterior distribution
    post_sum = float(posterior.sum())
    post_min = float(posterior.min())
    post_max = float(posterior.max())
    post_entropy = float(-np.sum(posterior * np.log(posterior + 1e-300)))
    ess = 1.0 / float(np.sum(posterior**2))
    uniform_prob = 1.0 / float(posterior.size)
    max_prob = float(posterior.max())
    max_over_uniform = max_prob / uniform_prob if uniform_prob > 0 else np.nan

    # Part C: Residual diagnostics at true and MAP cells
    # Use cleaned residuals (b0/b1 removed) to get noise-only statistics
    res_true_clean, res_true_raw, b0b1_true = compute_residuals_clean(
        true_en, DELTA_T_TRUE, ref_ecef, enu_basis,
        sat_pos, sat_vel, times_s, observed_freq, CARRIER_FREQ_HZ,
    )
    res_map_clean, res_map_raw, b0b1_map = compute_residuals_clean(
        map_pos_en, best_delta_t, ref_ecef, enu_basis,
        sat_pos, sat_vel, times_s, observed_freq, CARRIER_FREQ_HZ,
    )

    stats_true = residual_stats(res_true_clean, SIGMA_F)
    stats_map = residual_stats(res_map_clean, SIGMA_F)

    # Part D: Sensitivity around true cell (noise-only RMS)
    neighborhood = []
    for de in [-STEP_M, 0, STEP_M]:
        for dn in [-STEP_M, 0, STEP_M]:
            if de == 0 and dn == 0:
                continue
            en_pos = np.array([true_en[0] + de, true_en[1] + dn])
            res_clean, _, _ = compute_residuals_clean(
                en_pos, DELTA_T_TRUE, ref_ecef, enu_basis,
                sat_pos, sat_vel, times_s, observed_freq, CARRIER_FREQ_HZ,
            )
            rms = float(np.sqrt(np.mean(res_clean**2)))
            err = float(np.linalg.norm([de, dn]))
            neighborhood.append(dict(de=float(de), dn=float(dn), error_m=err, residual_rms_hz=rms))

    # Part E: Sigma sweep (score only, not modifying estimator)
    sigma_sweep = []
    for sigma_test in [0.5, 1.0, 2.0, 5.0, 10.0]:
        # Recompute NLL at key positions with different sigma
        # Use cleaned residuals (b0/b1 removed) to match score_candidate behavior
        def alt_nll(en_pos, dt):
            res_clean, _, _ = compute_residuals_clean(
                en_pos, dt, ref_ecef, enu_basis,
                sat_pos, sat_vel, times_s, observed_freq, CARRIER_FREQ_HZ,
            )
            return float(0.5 * np.sum((res_clean / sigma_test)**2))

        sc_true = alt_nll(true_en, DELTA_T_TRUE)
        sc_map = alt_nll(map_pos_en, best_delta_t)
        sc_center = alt_nll(np.array([0.0, 0.0]), DELTA_T_TRUE)

        # Compute posterior approximation over grid (marginalize delta_t not done,
        # so just rank by score difference)
        sigma_sweep.append(dict(
            sigma_f_hz=sigma_test,
            true_score=sc_true,
            map_score=sc_map,
            center_score=sc_center,
            true_minus_map=float(sc_true - sc_map),
            true_minus_center=float(sc_true - sc_center),
            score_dynamic_range=score_dynamic_range,
        ))

    # Compile results
    result = {
        # Part A
        "num_candidates": len(all_scores),
        "score_dynamic_range": score_dynamic_range,
        "score_mean": score_mean,
        "score_std": score_std,
        "score_p01": p01, "score_p05": p05,
        "score_p50": p50, "score_p95": p95, "score_p99": p99,
        "top10_score_gaps": top10_gaps,
        "true_score": float(score_true),
        "map_score": float(score_map),
        "center_score": float(score_center),
        "true_minus_map_score": float(score_true - score_map),
        "true_minus_center_score": float(score_true - score_center),
        "true_rank": true_rank,
        "map_error_m": map_error,
        "true_cell_error_m": 0.0,
        # Part B
        "posterior_sum": post_sum,
        "posterior_min": post_min,
        "posterior_max": post_max,
        "posterior_entropy": post_entropy,
        "effective_sample_size": ess,
        "max_prob": max_prob,
        "uniform_prob": uniform_prob,
        "max_prob_over_uniform": max_over_uniform,
        "true_prob": true_prob,
        "map_prob": map_prob,
        # Part C
        "residual_at_true_cell": stats_true,
        "residual_at_map_cell": stats_map,
        # Part D
        "neighborhood_rms": neighborhood,
        # Part E
        "sigma_sweep": sigma_sweep,
        "seed": args.seed,
    }

    json_path = os.path.join(args.output_dir, 'posterior_flatness_diagnostic.json')
    with open(json_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"JSON: {json_path}")

    # CSV: all scores
    csv_path = os.path.join(args.output_dir, 'posterior_flatness_scores.csv')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['idx', 'e', 'n', 'score', 'error_m', 'prob'])
        writer.writeheader()
        for s in all_scores:
            writer.writerow({k: s[k] for k in ['idx', 'e', 'n', 'score', 'error_m', 'prob']})
    print(f"CSV: {csv_path}")

    # Summary print
    print("\n=== POSTERIOR FLATNESS SUMMARY ===")
    print(f"  Score dynamic range: {score_dynamic_range:.4f}")
    print(f"  Score std: {score_std:.4f}")
    print(f"  True rank: {true_rank}/{len(all_scores)}")
    print(f"  Posterior entropy: {post_entropy:.4f}")
    print(f"  ESS: {ess:.2f}")
    print(f"  max_prob / uniform: {max_over_uniform:.4f}")
    print(f"  True score: {score_true:.4f}, MAP: {score_map:.4f}, diff: {score_true - score_map:.4f}")
    print(f"  True residual: RMS={stats_true['residual_rms_hz']:.4f}Hz  var={stats_true['residual_var_hz2']:.4f}Hz²  max={stats_true['residual_max_abs_hz']:.4f}Hz")
    print(f"  MAP residual:  RMS={stats_map['residual_rms_hz']:.4f}Hz  var={stats_map['residual_var_hz2']:.4f}Hz²  max={stats_map['residual_max_abs_hz']:.4f}Hz")
    print(f"  True reduced chi2: {stats_true['reduced_chi2']:.4f}")
    print(f"  [CHECK] var≈RMS²? var={stats_true['residual_var_hz2']:.4f}  RMS²={stats_true['residual_rms_hz']**2:.4f}")
    print(f"  Neighborhood RMS around true:")
    for n in neighborhood:
        print(f"    dE={n['de']:+.0f} dN={n['dn']:+.0f} err={n['error_m']:.0f}m RMS={n['residual_rms_hz']:.4f}Hz")
    return 0


if __name__ == '__main__':
    sys.exit(main())