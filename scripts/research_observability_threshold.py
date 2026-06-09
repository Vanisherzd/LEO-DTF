#!/usr/bin/env python3
"""
Observability Threshold Diagnostic
===================================
Quantifies Doppler-time fingerprint separability across carrier frequency,
observation duration, packet interval, and position offset.

This is a forward-model-only diagnostic — no estimator, no posterior.
Measures whether the Doppler difference between two ground positions
exceeds the noise floor (sigma_f).

Outputs:
  experiments/results/research_observability_threshold/observability_threshold_trials.csv
  experiments/results/research_observability_threshold/observability_threshold_summary.json
"""

import sys, os, csv, json, argparse
from datetime import datetime, timedelta
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

C_KM_S = 299792.458  # speed of light, km/s
SIGMA_F = 1.0  # Hz, reference noise floor
GS_LAT, GS_LON, GS_ALT = 40.0, -105.0, 0.0


def geodetic_to_ecef(lat, lon, alt_km):
    lat_r = np.radians(lat)
    lon_r = np.radians(lon)
    a, e2 = 6378.137, 2.668959e-3
    N = a / np.sqrt(1 - e2 * np.sin(lat_r)**2)
    x = (N + alt_km) * np.cos(lat_r) * np.cos(lon_r)
    y = (N + alt_km) * np.cos(lat_r) * np.sin(lon_r)
    z = (N * (1 - e2) + alt_km) * np.sin(lat_r)
    return np.array([x, y, z])


def enu_basis_from_geodetic(lat, lon):
    lat_r, lon_r = np.radians(lat), np.radians(lon)
    slat, clat = np.sin(lat_r), np.cos(lat_r)
    slon, clon = np.sin(lon_r), np.cos(lon_r)
    E = np.array([-slon, clon, 0.0])
    N = np.array([-slat*clon, -slat*slon, clat])
    U = np.array([clat*clon, clat*slon, slat])
    return np.column_stack([E, N, U])


def compute_doppler_timeseries(gs_ecef, sat_pos_km, sat_vel_km_s, carrier_hz):
    """Compute Doppler shift time series for a ground station at gs_ecef (km)."""
    N = len(sat_pos_km)
    doppler = np.zeros(N)
    for i in range(N):
        los = sat_pos_km[i] - gs_ecef
        rng = np.linalg.norm(los)
        los_unit = los / rng
        range_rate = np.dot(sat_vel_km_s[i], los_unit)  # km/s
        doppler[i] = -range_rate * carrier_hz / C_KM_S
    return doppler


def propagate_orbit_quick(seed):
    """Generate satellite positions/velocities for a single pass."""
    rng = np.random.default_rng(seed)
    t0 = datetime(2026, 6, 4, 12, 0, 0)

    # Two-line element for ISS
    l1 = "1 25544U 98067A   26155.53033517  .00012622  00000+0  28098-3 0  9994"
    l2 = "2 25544  51.6416 246.6182 0006706 302.2584 122.9105 15.50040302433475"

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    from leodtf.orbit_propagation import propagate_orbit

    times_dt = [t0 + timedelta(seconds=t) for t in [0, 60, 120, 180, 240, 300, 360, 420, 480, 540, 600]]
    sat_pos, sat_vel = propagate_orbit(l1, l2, times_dt)
    times_s = np.array([(t - t0).total_seconds() for t in times_dt])
    return sat_pos, sat_vel, times_s


def run_trial(carrier_hz, duration_s, packet_interval_s, offset_m, direction, seed=42):
    """Compute Doppler separability between base and offset positions."""
    rng = np.random.default_rng(seed)

    # Base ground station
    gs_ecef_base = geodetic_to_ecef(GS_LAT, GS_LON, GS_ALT)
    enu_basis = enu_basis_from_geodetic(GS_LAT, GS_LON)

    # Offset ground station
    if direction == 'east':
        offset_vec = np.array([offset_m, 0.0, 0.0])
    elif direction == 'north':
        offset_vec = np.array([0.0, offset_m, 0.0])
    else:
        offset_vec = np.array([offset_m, offset_m, 0.0])

    offset_ecef = enu_basis @ (offset_vec / 1000.0)
    gs_ecef_offset = gs_ecef_base + offset_ecef

    # Satellite trajectory
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    from leodtf.orbit_propagation import propagate_orbit

    ref_time = datetime(2026, 6, 4, 12, 0, 0)
    num_packets = max(2, int(duration_s / packet_interval_s))
    times_s = np.linspace(0, duration_s, num_packets)
    times_dt = [ref_time + timedelta(seconds=t) for t in times_s]

    l1 = "1 25544U 98067A   26155.53033517  .00012622  00000+0  28098-3 0  9994"
    l2 = "2 25544  51.6416 246.6182 0006706 302.2584 122.9105 15.50040302433475"
    sat_pos, sat_vel = propagate_orbit(l1, l2, times_dt)

    # Doppler at each position
    doppler_base = compute_doppler_timeseries(gs_ecef_base, sat_pos, sat_vel, carrier_hz)
    doppler_offset = compute_doppler_timeseries(gs_ecef_offset, sat_pos, sat_vel, carrier_hz)

    # Separation
    diff = doppler_offset - doppler_base
    rms = float(np.sqrt(np.mean(diff**2)))
    max_abs = float(np.max(np.abs(diff)))
    separation = rms / SIGMA_F

    if separation < 1:
        status = 'unobservable'
    elif separation < 3:
        status = 'weak'
    elif separation < 10:
        status = 'moderate'
    else:
        status = 'strong'

    return dict(
        carrier_hz=carrier_hz,
        duration_s=duration_s,
        packet_interval_s=packet_interval_s,
        offset_m=offset_m,
        offset_direction=direction,
        num_samples=len(times_s),
        doppler_separation_rms_hz=rms,
        doppler_separation_max_hz=max_abs,
        separation_over_noise=separation,
        observability_status=status,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--output-dir',
                        default='experiments/results/research_observability_threshold')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Parameter grids
    if args.quick:
        carrier_vals = [137e6, 915e6, 2.4e9]
        duration_vals = [600, 1800]
        interval_vals = [10, 30]
        offset_vals = [100, 1000]
    else:
        carrier_vals = [137e6, 433e6, 915e6, 1.6e9, 2.4e9]
        duration_vals = [600, 1200, 1800, 3600]
        interval_vals = [1, 5, 10, 30]
        offset_vals = [100, 500, 1000, 5000]

    directions = ['east', 'north']

    rows = []
    for carrier in carrier_vals:
        for dur in duration_vals:
            for interval in interval_vals:
                for offset in offset_vals:
                    for direction in directions:
                        row = run_trial(carrier, dur, interval, offset, direction, args.seed)
                        rows.append(row)

    # CSV
    csv_path = os.path.join(args.output_dir, 'observability_threshold_trials.csv')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV: {csv_path} ({len(rows)} rows)")

    # Summary
    statuses = [r['observability_status'] for r in rows]
    counts = {s: statuses.count(s) for s in ['unobservable', 'weak', 'moderate', 'strong']}

    best = max(rows, key=lambda r: r['separation_over_noise'])
    worst = min(rows, key=lambda r: r['separation_over_noise'])

    over_1 = [r for r in rows if r['separation_over_noise'] >= 1]
    over_3 = [r for r in rows if r['separation_over_noise'] >= 3]
    over_10 = [r for r in rows if r['separation_over_noise'] >= 10]

    def fmt(r):
        return f"f={r['carrier_hz']/1e6:.0f}MHz d={r['duration_s']}s i={r['packet_interval_s']}s o={r['offset_m']}m {r['offset_direction']}"

    summary = {
        'metadata': {
            'seed': args.seed,
            'sigma_f_hz': SIGMA_F,
            'quick': args.quick,
            'total_configs': len(rows),
        },
        'summary': {
            'count_unobservable': counts.get('unobservable', 0),
            'count_weak': counts.get('weak', 0),
            'count_moderate': counts.get('moderate', 0),
            'count_strong': counts.get('strong', 0),
            'best_config': fmt(best),
            'best_separation_over_noise': best['separation_over_noise'],
            'worst_config': fmt(worst),
            'worst_separation_over_noise': worst['separation_over_noise'],
        },
        'thresholds': {
            'first_over_1': fmt(over_1[0]) if over_1 else None,
            'first_over_3': fmt(over_3[0]) if over_3 else None,
            'first_over_10': fmt(over_10[0]) if over_10 else None,
            'count_over_1': len(over_1),
            'count_over_3': len(over_3),
            'count_over_10': len(over_10),
        },
        'key_findings': {
            '137mhz_600s_100m_unobservable': bool(
                any(r['observability_status'] == 'unobservable'
                    for r in rows if r['carrier_hz'] == 137e6
                    and r['duration_s'] == 600 and r['offset_m'] == 100)),
            '915mhz_better_than_137mhz': bool(
                np.mean([r['separation_over_noise'] for r in rows
                         if r['carrier_hz'] == 915e6]) >
                np.mean([r['separation_over_noise'] for r in rows
                         if r['carrier_hz'] == 137e6])
            ),
            'longer_duration_helps': bool(
                np.mean([r['separation_over_noise'] for r in rows
                         if r['duration_s'] >= 1800]) >
                np.mean([r['separation_over_noise'] for r in rows
                         if r['duration_s'] <= 600])
            ),
            'larger_offset_helps': bool(
                np.mean([r['separation_over_noise'] for r in rows
                         if r['offset_m'] >= 1000]) >
                np.mean([r['separation_over_noise'] for r in rows
                         if r['offset_m'] <= 100])
            ),
        },
    }

    json_path = os.path.join(args.output_dir, 'observability_threshold_summary.json')
    with open(json_path, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"JSON: {json_path}")

    # Print table
    print(f"\n{'Carrier':>10} {'Dur':>5} {'Int':>4} {'Off':>6} {'Dir':>4} "
          f"{'RMS Hz':>8} {'Max Hz':>8} {'S/N':>6} {'Status':>12}")
    print("-" * 75)
    for r in sorted(rows, key=lambda x: x['separation_over_noise']):
        print(f"{r['carrier_hz']/1e6:>10.0f} {r['duration_s']:>5} "
              f"{r['packet_interval_s']:>4} {r['offset_m']:>6} "
              f"{r['offset_direction']:>4} "
              f"{r['doppler_separation_rms_hz']:>8.4f} "
              f"{r['doppler_separation_max_hz']:>8.4f} "
              f"{r['separation_over_noise']:>6.2f} {r['observability_status']:>12}")

    print(f"\nCounts: unobservable={counts.get('unobservable',0)} "
          f"weak={counts.get('weak',0)} moderate={counts.get('moderate',0)} "
          f"strong={counts.get('strong',0)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())