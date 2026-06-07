"""
Simulated Dataset Generator for LEO-DTF
---------------------------------------
Generates synthetic satellite passes and measurements for reproducible
synthetic experiments. Connects TLE/orbit propagation with the observation
model to produce clean and noisy Doppler/time observations.

This module is for synthetic trace-driven evaluation only.
No real satellite OTA validation is claimed.
"""

import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Optional, Union
import json
import csv
import os

# Deterministic synthetic ISS TLE for fallback (400 km, ~53 deg inclination, epoch 2026)
_SYNTHETIC_TLE_LINE1 = "1 99999U 26001A   26155.50000000  .00010000  00000-0  10000-3 0  9994"
_SYNTHETIC_TLE_LINE2 = "2 99999  53.0000 000.0000 0006706 000.0000 000.0000 15.50000000100000"


def _synthetic_inclined_orbit(times, altitude_km=400.0, inclination_deg=53.0):
    """
    Deterministic inclined circular orbit matching typical LEO geometry.
    Used when no TLE is provided.

    Parameters
    ----------
    times : list of datetime
        UTC times for propagation.
    altitude_km : float
        Orbital altitude in km.
    inclination_deg : float
        Orbit inclination in degrees.

    Returns
    -------
    positions_ecef : ndarray, shape (N, 3), km
    velocities_ecef : ndarray, shape (N, 3), km/s
    """
    R = 6378.137 + altitude_km  # km
    mu = 3.986004418e5           # km^3/s^2
    n = np.sqrt(mu / R**3)      # rad/s
    inc = np.radians(inclination_deg)

    positions = []
    velocities = []
    t0 = (times[0] - times[0]).total_seconds() if len(times) > 1 else 0.0

    for t in times:
        dt = (t - times[0]).total_seconds()
        angle = n * dt

        # Position in orbital plane
        x_orb = R * np.cos(angle)
        y_orb = R * np.sin(angle)
        # Rotate by inclination around x-axis
        x = x_orb
        y = y_orb * np.cos(inc)
        z = y_orb * np.sin(inc)

        # Velocity in orbital plane
        vx_orb = -R * n * np.sin(angle)
        vy_orb = R * n * np.cos(angle)
        vx = vx_orb
        vy = vy_orb * np.cos(inc)
        vz = vy_orb * np.sin(inc)

        positions.append([x, y, z])
        velocities.append([vx, vy, vz])

    return np.array(positions), np.array(velocities)


def generate_synthetic_pass_dataset(
    tle_line1: Optional[str] = None,
    tle_line2: Optional[str] = None,
    true_lat_deg: float = 40.0,
    true_lon_deg: float = -105.0,
    true_alt_m: float = 0.0,
    start_time: Optional[datetime] = None,
    duration_s: float = 600.0,
    sample_interval_s: float = 30.0,
    carrier_hz: float = 1.6e9,
    cfo_hz: float = 0.0,
    drift_hz_per_s: float = 0.0,
    time_offset_s: float = 0.0,
    doppler_noise_std: float = 0.0,
    delay_noise_std: float = 0.0,
    seed: Optional[int] = None,
) -> dict:
    """
    Generate a synthetic satellite pass with Doppler and delay observations.

    Parameters
    ----------
    tle_line1, tle_line2 : str or None
        Two-line element set. If None, uses a deterministic synthetic orbit
        (inclined circular, 400 km, 53 deg) so results are reproducible.
    true_lat_deg, true_lon_deg : float
        True receiver geodetic coordinates (degrees).
    true_alt_m : float
        True receiver altitude (meters).
    start_time : datetime or None
        Pass start time (UTC). If None, uses 2026-06-04 12:00:00 UTC.
    duration_s : float
        Pass duration in seconds.
    sample_interval_s : float
        Interval between observations in seconds.
    carrier_hz : float
        Carrier frequency in Hz.
    cfo_hz : float
        Constant frequency offset (Hz).
    drift_hz_per_s : float
        Linear frequency drift rate (Hz/s).
    time_offset_s : float
        Time offset nuisance (seconds).
    doppler_noise_std : float
        Std dev of additive Doppler noise (Hz).
    delay_noise_std : float
        Std dev of additive delay noise (seconds).
    seed : int or None
        Random seed for reproducibility.

    Returns
    -------
    dataset : dict
        Contains:
        - time_offsets_s : ndarray — time since pass start (s)
        - satellite_positions_ecef_km : ndarray — (N, 3) ECEF km
        - satellite_velocities_ecef_km_s : ndarray — (N, 3) ECEF km/s
        - true_receiver_ecef_km : ndarray — (3,) ECEF km
        - true_receiver_geodetic : tuple — (lat, lon, alt_m) degrees/degrees/meters
        - clean_doppler_hz : ndarray — geometric Doppler only (Hz)
        - observed_doppler_hz : ndarray — geometric + cfo + drift + noise (Hz)
        - clean_delay_s : ndarray — geometric propagation delay (s)
        - observed_delay_s : ndarray — delay + time_offset + noise (s)
        - cfo_hz : float
        - drift_hz_per_s : float
        - time_offset_s : float
        - doppler_noise_std_hz : float
        - delay_noise_std_s : float
        - carrier_hz : float
        - duration_s : float
        - sample_interval_s : float
        - seed : int or None
        - tle_line1, tle_line2 : str or None
        - orbit_altitude_km : float
        - orbit_inclination_deg : float
    """
    rng = np.random.default_rng(seed)
    n_points = max(1, int(np.round(duration_s / sample_interval_s)) + 1)
    time_offsets_s = np.linspace(0, duration_s, n_points)

    if start_time is None:
        start_time = datetime(2026, 6, 4, 12, 0, 0, tzinfo=timezone.utc)

    times_dt = [
        start_time + timedelta(seconds=float(t)) for t in time_offsets_s
    ]

    # --- Satellite geometry ---
    if tle_line1 is not None and tle_line2 is not None:
        from .tle_loader import parse_tle
        from .orbit_propagation import propagate_orbit
        tle_data = parse_tle(tle_line1, tle_line2)
        sat_pos, sat_vel = propagate_orbit(tle_line1, tle_line2, times_dt)
        orbit_altitude_km = tle_data.semi_major_axis - 6378.137
        orbit_inclination_deg = float(np.degrees(tle_data.inclination))
    else:
        sat_pos, sat_vel = _synthetic_inclined_orbit(
            times_dt, altitude_km=400.0, inclination_deg=53.0
        )
        orbit_altitude_km = 400.0
        orbit_inclination_deg = 53.0

    # --- True receiver position ---
    from .frame_transform import geodetic_to_ecef
    true_alt_km = true_alt_m / 1000.0
    true_ecef = np.array(geodetic_to_ecef(true_lat_deg, true_lon_deg, true_alt_km))

    # --- Observation model ---
    from .observation_model import ObservationModel
    obs = ObservationModel(true_ecef, carrier_freq_hz=carrier_hz)

    clean_doppler = np.zeros(n_points)
    clean_delay = np.zeros(n_points)
    for i in range(n_points):
        sat_state = (sat_pos[i], sat_vel[i])
        doppler_hz, delay_s = obs.compute_expected_measurements(
            sat_state, time_offsets_s[i]
        )
        clean_doppler[i] = doppler_hz
        clean_delay[i] = delay_s

    # --- Add nuisances and noise ---
    noise_doppler = rng.normal(0.0, doppler_noise_std, size=n_points)
    noise_delay = rng.normal(0.0, delay_noise_std, size=n_points)

    observed_doppler = clean_doppler + cfo_hz + drift_hz_per_s * time_offsets_s + noise_doppler
    observed_delay = clean_delay + time_offset_s + noise_delay

    return {
        "time_offsets_s": time_offsets_s.tolist(),
        "satellite_positions_ecef_km": sat_pos.tolist(),
        "satellite_velocities_ecef_km_s": sat_vel.tolist(),
        "true_receiver_ecef_km": true_ecef.tolist(),
        "true_receiver_geodetic": {
            "lat_deg": true_lat_deg,
            "lon_deg": true_lon_deg,
            "alt_m": true_alt_m,
        },
        "clean_doppler_hz": clean_doppler.tolist(),
        "observed_doppler_hz": observed_doppler.tolist(),
        "clean_delay_s": clean_delay.tolist(),
        "observed_delay_s": observed_delay.tolist(),
        "cfo_hz": float(cfo_hz),
        "drift_hz_per_s": float(drift_hz_per_s),
        "time_offset_s": float(time_offset_s),
        "doppler_noise_std_hz": float(doppler_noise_std),
        "delay_noise_std_s": float(delay_noise_std),
        "carrier_hz": float(carrier_hz),
        "duration_s": float(duration_s),
        "sample_interval_s": float(sample_interval_s),
        "seed": seed,
        "tle_line1": tle_line1,
        "tle_line2": tle_line2,
        "orbit_altitude_km": float(orbit_altitude_km),
        "orbit_inclination_deg": float(orbit_inclination_deg),
    }


def export_dataset_json(dataset: dict, path: str) -> None:
    """Save a dataset dict to a JSON file. Creates parent directories if needed."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(dataset, f, indent=2)


def export_dataset_csv(dataset: dict, path: str) -> None:
    """
    Save observation arrays from a dataset to a CSV file.

    Columns: time_s, clean_doppler_hz, observed_doppler_hz,
             clean_delay_s, observed_delay_s
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    times = dataset["time_offsets_s"]
    data = zip(
        times,
        dataset["clean_doppler_hz"],
        dataset["observed_doppler_hz"],
        dataset["clean_delay_s"],
        dataset["observed_delay_s"],
    )
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "time_s", "clean_doppler_hz", "observed_doppler_hz",
            "clean_delay_s", "observed_delay_s",
        ])
        writer.writerows(data)


if __name__ == "__main__":
    # Example: generate a default synthetic pass
    dataset = generate_synthetic_pass_dataset(
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
    print(f"Generated {len(dataset['time_offsets_s'])} observations")
    print(f"True receiver (ECEF km): {dataset['true_receiver_ecef_km']}")
    print(f"Clean Doppler range: {min(dataset['clean_doppler_hz']):.2f} – {max(dataset['clean_doppler_hz']):.2f} Hz")
    print(f"Orbit: {dataset['orbit_altitude_km']:.0f} km, {dataset['orbit_inclination_deg']:.0f} deg inclination")