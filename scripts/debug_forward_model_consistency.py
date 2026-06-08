#!/usr/bin/env python3
"""
Forward Model Self-Consistency Diagnostic
==========================================
Verifies that the synthetic observation generator and the estimator's
forward model produce consistent Doppler predictions for the same ground truth.
"""

import sys, os, json, csv
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Forward model consistency diagnostic')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output-dir', default='experiments/results/debug_forward_model')
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    os.makedirs(args.output_dir, exist_ok=True)

    # Scenario setup
    LAT0_DEG, LON0_DEG = 40.0, -105.0
    ALT0_KM = 1.5
    TRUE_OFFSET_EN = np.array([100.0, 50.0])
    CARRIER_FREQ_HZ = 1.6e9
    B0_TRUE = 50.0
    B1_TRUE = 0.1
    DELTA_T_TRUE = 0.001
    SIGMA_F = 1.0
    SIGMA_TAU = 1e-3
    NUM_PACKETS = 20
    TOTAL_TIME_S = 600.0

    from leodtf.frame_transform import geodetic_to_ecef
    from leodtf.orbit_propagation import propagate_orbit
    from leodtf.observation_model import ObservationModel
    from leodtf.estimator_grid_map import estimate_grid_map

    # Build reference and true positions
    ref_ecef = np.array(geodetic_to_ecef(LAT0_DEG, LON0_DEG, ALT0_KM))
    lat_r = np.radians(LAT0_DEG)
    lon_r = np.radians(LON0_DEG)
    slat, clat = np.sin(lat_r), np.cos(lat_r)
    slon, clon = np.sin(lon_r), np.cos(lon_r)
    e_vec = np.array([-slon, clon, 0.0])
    n_vec = np.array([-slat*clon, -slat*slon, clat])
    u_vec = np.array([clat*clon, clat*slon, slat])
    enu_basis = np.column_stack([e_vec, n_vec, u_vec])

    true_offset_km = np.array([TRUE_OFFSET_EN[0], TRUE_OFFSET_EN[1], 0.0]) / 1000.0
    true_gs_ecef = ref_ecef + enu_basis @ true_offset_km

    # Propagate orbit
    ref_time = datetime(2026, 6, 4, 12, 0, 0)
    times_s = np.linspace(0, TOTAL_TIME_S, NUM_PACKETS)
    times_dt = [ref_time + timedelta(seconds=t) for t in times_s]
    line1 = "1 25544U 98067A   26155.53033517  .00012622  00000+0  28098-3 0  9994"
    line2 = "2 25544  51.6416 246.6182 0006706 302.2584 122.9105 15.50040302433475"
    sat_pos, sat_vel = propagate_orbit(line1, line2, times_dt)

    # Observation model at both locations
    obs_ref = ObservationModel(ref_ecef, carrier_freq_hz=CARRIER_FREQ_HZ)
    obs_true = ObservationModel(true_gs_ecef, carrier_freq_hz=CARRIER_FREQ_HZ)

    # Generate observations at TRUE location
    clean_doppler = np.zeros(NUM_PACKETS)
    for i in range(NUM_PACKETS):
        d, _ = obs_true.compute_expected_measurements((sat_pos[i], sat_vel[i]), times_s[i])
        clean_doppler[i] = d

    observed_freq = clean_doppler + B0_TRUE + B1_TRUE * times_s + rng.normal(0, SIGMA_F, NUM_PACKETS)

    print("=== Forward Model Consistency Check ===")
    print(f"True location Doppler range: {clean_doppler.min():.2f} to {clean_doppler.max():.2f} Hz")
    print(f"Observed freq range (with CFO/drift/noise): {observed_freq.min():.2f} to {observed_freq.max():.2f} Hz")
    print()

    # Compare: predicted Doppler at TRUE location vs at GRID CENTER (ref_ecef)
    pred_at_true = np.zeros(NUM_PACKETS)
    pred_at_ref = np.zeros(NUM_PACKETS)
    for i in range(NUM_PACKETS):
        d_true, _ = obs_true.compute_expected_measurements((sat_pos[i], sat_vel[i]), times_s[i])
        d_ref, _ = obs_ref.compute_expected_measurements((sat_pos[i], sat_vel[i]), times_s[i])
        pred_at_true[i] = d_true
        pred_at_ref[i] = d_ref

    doppler_residual_at_true = observed_freq - pred_at_true  # residuals should be ~b0+b1*t+noise
    doppler_residual_at_ref = observed_freq - pred_at_ref   # residuals include geometry error

    print(f"Predicted Doppler at TRUE location: {pred_at_true.min():.6f} to {pred_at_true.max():.6f} Hz")
    print(f"Predicted Doppler at GRID CENTER:    {pred_at_ref.min():.6f} to {pred_at_ref.max():.6f} Hz")
    print(f"Difference (true - center):         {(pred_at_true - pred_at_ref).min():.6f} to {(pred_at_true - pred_at_ref).max():.6f} Hz")
    print()

    # Check: if we use pred_at_true as the predicted Doppler in the LS fit,
    # what b0, b1 do we recover?
    t_rel = times_s - times_s[0]

    # LS fit at true position
    A = np.column_stack([np.ones(NUM_PACKETS), t_rel])
    b0b1_true, residuals_true, _, _ = np.linalg.lstsq(A, observed_freq - pred_at_true, rcond=None)
    residual_var_true = np.mean(residuals_true**2) if len(residuals_true) > 0 else 0.0

    # LS fit at ref position
    b0b1_ref, residuals_ref, _, _ = np.linalg.lstsq(A, observed_freq - pred_at_ref, rcond=None)
    residual_var_ref = np.mean(residuals_ref**2) if len(residuals_ref) > 0 else 0.0

    print(f"At TRUE position:  b0_est={b0b1_true[0]:.4f} Hz  b1_est={b0b1_true[1]:.6f} Hz/s  resid_var={residual_var_true:.4f}")
    print(f"At GRID CENTER:    b0_est={b0b1_ref[0]:.4f} Hz  b1_est={b0b1_ref[1]:.6f} Hz/s  resid_var={residual_var_ref:.4f}")
    print(f"True values:       b0={B0_TRUE} Hz  b1={B1_TRUE} Hz/s")
    print()

    # Frequency residuals after removing fitted b0, b1
    freq_residuals_true = (observed_freq - pred_at_true) - (b0b1_true[0] + b0b1_true[1] * t_rel)
    freq_residuals_ref = (observed_freq - pred_at_ref) - (b0b1_ref[0] + b0b1_ref[1] * t_rel)

    doppler_res_mean_hz = float(np.mean(np.abs(freq_residuals_true)))
    doppler_res_max_hz = float(np.max(np.abs(freq_residuals_true)))
    doppler_res_ref_mean_hz = float(np.mean(np.abs(freq_residuals_ref)))
    doppler_res_ref_max_hz = float(np.max(np.abs(freq_residuals_ref)))

    print(f"Freq residuals at TRUE (after b0/b1 removal): mean={doppler_res_mean_hz:.4f} Hz  max={doppler_res_max_hz:.4f} Hz")
    print(f"Freq residuals at CENTER (after b0/b1 removal): mean={doppler_res_ref_mean_hz:.4f} Hz  max={doppler_res_ref_max_hz:.4f} Hz")
    print()

    # Score computation (log-likelihood)
    from scipy.special import logsumexp

    score_true = 0.5 * np.sum(freq_residuals_true**2) / (SIGMA_F**2)
    score_ref = 0.5 * np.sum(freq_residuals_ref**2) / (SIGMA_F**2)
    print(f"Frequency score at TRUE:   {score_true:.4f}")
    print(f"Frequency score at CENTER: {score_ref:.4f}")
    print(f"Difference (true - ref):   {score_true - score_ref:.4f}")
    print()

    # Correlation between predicted_doppler at true and at ref
    corr_pred = float(np.corrcoef(pred_at_true, pred_at_ref)[0, 1])
    print(f"Correlation of predicted Doppler (true vs center): {corr_pred:.6f}")
    print()

    # Sign check: is the Doppler at center opposite sign?
    mean_diff = float(np.mean(pred_at_true - pred_at_ref))
    print(f"Mean Doppler difference (true - center): {mean_diff:.6f} Hz")

    # Check if there's a systematic sign flip or offset
    is_close_geometry = bool(np.mean(np.abs(pred_at_true - pred_at_ref)) < 0.5)
    print(f"Geometry nearly identical at both positions: {is_close_geometry}")

    results = {
        'clean_doppler_min_hz': float(clean_doppler.min()),
        'clean_doppler_max_hz': float(clean_doppler.max()),
        'clean_doppler_span_hz': float(clean_doppler.max() - clean_doppler.min()),
        'doppler_diff_true_minus_center_mean_hz': float(np.mean(pred_at_true - pred_at_ref)),
        'doppler_diff_true_minus_center_max_hz': float(np.max(np.abs(pred_at_true - pred_at_ref))),
        'geometry_nearly_identical': is_close_geometry,
        'b0_est_at_true_hz': float(b0b1_true[0]),
        'b1_est_at_true_hz_s': float(b0b1_true[1]),
        'b0_est_at_center_hz': float(b0b1_ref[0]),
        'b1_est_at_center_hz_s': float(b0b1_ref[1]),
        'corr_pred_true_vs_center': corr_pred,
        'freq_score_at_true': float(score_true),
        'freq_score_at_center': float(score_ref),
        'score_difference': float(score_true - score_ref),
        'resid_var_at_true': float(residual_var_true),
        'resid_var_at_center': float(residual_var_ref),
        'doppler_res_mean_hz_at_true': doppler_res_mean_hz,
        'doppler_res_max_hz_at_true': doppler_res_max_hz,
        'doppler_res_mean_hz_at_center': doppler_res_ref_mean_hz,
        'doppler_res_max_hz_at_center': doppler_res_ref_max_hz,
        'true_position_ecef_km': true_gs_ecef.tolist(),
        'grid_center_ecef_km': ref_ecef.tolist(),
        'enu_offset_m': TRUE_OFFSET_EN.tolist(),
        'enu_offset_ecef_magnitude_m': float(np.linalg.norm(enu_basis @ true_offset_km) * 1000),
    }

    csv_path = os.path.join(args.output_dir, 'forward_model_residuals.csv')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=results.keys())
        writer.writeheader()
        writer.writerow(results)

    json_path = os.path.join(args.output_dir, 'forward_model_consistency.json')
    with open(json_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")
    return 0

if __name__ == '__main__':
    sys.exit(main())