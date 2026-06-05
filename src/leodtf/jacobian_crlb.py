"""Jacobian and CRLB for LEO-DTF
-----------------------------
Computes Jacobian of observation model and Cramér-Rao Lower Bound for parameter estimation.
"""

import numpy as np
import scipy.linalg
from . import frame_transform


def _compute_observation_and_jacobian_at_time(sat_pos_ecef, sat_vel_ecef, gs_ref_geodetic, carrier_freq_hz, time_s, delta_t, b0, b1, gs_enu_offset):
    """
    Compute the observation vector and its Jacobian with respect to the state [e, n, delta_t, b0, b1] at a single time.

    Parameters
    ----------
    sat_pos_ecef : ndarray of shape (3,)
        Satellite position in ECEF (km).
    sat_vel_ecef : ndarray of shape (3,)
        Satellite velocity in ECEF (km/s).
    gs_ref_geodetic : tuple (lat0, lon0, alt0)
        Reference geodetic point for the ground station (lat0, lon0 in degrees, alt0 in km).
    carrier_freq_hz : float
        Carrier frequency in Hz.
    time_s : float
        Nominal time in seconds (e.g., transmission time).
    delta_t : float
        Current value of time offset nuisance (seconds).
    b0 : float
        Current value of constant frequency offset (Hz).
    b1 : float
        Current value of frequency drift rate (Hz/s).
    gs_enu_offset : tuple (e, n)
        Current ENU offset of the ground station from the reference point (km).

    Returns
    -------
    h : ndarray of shape (2,)
        Observation vector [Doppler_observation, timestamp_observation].
    H : ndarray of shape (2, 5)
        Jacobian matrix of h with respect to [e, n, delta_t, b0, b1].
    """
    lat0, lon0, alt0 = gs_ref_geodetic
    e, n = gs_enu_offset
    # We assume the up component is zero (or known and fixed). We'll set u=0 for the ENU offset.
    u = 0.0

    # Compute ground station ECEF position from ENU offset
    gs_pos_ecef = np.array(frame_transform.enu_to_ecef(e, n, u, lat0, lon0, alt0))
    # Vector from ground station to satellite
    los_vec = sat_pos_ecef - gs_pos_ecef
    range_km = np.linalg.norm(los_vec)
    los_unit = los_vec / range_km if range_km > 0 else np.array([0,0,0])

    # Range rate: projection of relative velocity onto los
    # Ground station velocity is assumed zero
    range_rate_km_s = np.dot(sat_vel_ecef, los_unit)  # km/s

    # Doppler shift (Hz)
    doppler_hz = - (carrier_freq_hz / 299792.458) * range_rate_km_s

    # Propagation delay (seconds)
    propagation_delay_s = range_km / 299792.458

    # Observations
    h1 = doppler_hz + b0 + b1 * time_s  # frequency observation
    h2 = time_s + delta_t + propagation_delay_s  # timestamp observation
    h = np.array([h1, h2])

    # Jacobian: we compute numerically by finite differences
    # State vector: [e, n, delta_t, b0, b1]
    state = np.array([e, n, delta_t, b0, b1])
    perturb = 1e-6
    H = np.zeros((2, 5))
    for i in range(5):
        state_pert = state.copy()
        state_pert[i] += perturb
        e_pert, n_pert, delta_t_pert, b0_pert, b1_pert = state_pert
        # Compute observation at perturbed state
        gs_pos_ecef_pert = np.array(frame_transform.enu_to_ecef(e_pert, n_pert, u, lat0, lon0, alt0))
        los_vec_pert = sat_pos_ecef - gs_pos_ecef_pert
        range_km_pert = np.linalg.norm(los_vec_pert)
        los_unit_pert = los_vec_pert / range_km_pert if range_km_pert > 0 else np.array([0,0,0])
        range_rate_km_s_pert = np.dot(sat_vel_ecef, los_unit_pert)
        doppler_hz_pert = - (carrier_freq_hz / 299792.458) * range_rate_km_s_pert
        propagation_delay_s_pert = range_km_pert / 299792.458
        h1_pert = doppler_hz_pert + b0_pert + b1_pert * time_s
        h2_pert = time_s + delta_t_pert + propagation_delay_s_pert
        h_pert = np.array([h1_pert, h2_pert])
        H[:, i] = (h_pert - h) / perturb

    return h, H


def compute_crlb_en_position(sat_positions_ecef, sat_velocities_ecef, gs_ref_geodetic, carrier_freq_hz, times, delta_t_true, b0_true, b1_true, gs_enu_offset_true, sigma_f=1.0, sigma_tau=1e-3):
    """
    Compute the Cramér-Rao Lower Bound for the EN position of the ground station.

    Parameters
    ----------
    sat_positions_ecef : ndarray of shape (N, 3)
        Satellite positions in ECEF (km) at each time.
    sat_velocities_ecef : ndarray of shape (N, 3)
        Satellite velocities in ECEF (km/s) at each time.
    gs_ref_geodetic : tuple (lat0, lon0, alt0)
        Reference geodetic point for the ground station (lat0, lon0 in degrees, alt0 in km).
    carrier_freq_hz : float
        Carrier frequency in Hz.
    times : ndarray of shape (N,)
        Times in seconds (e.g., seconds since an epoch).
    delta_t_true : float
        True value of time offset nuisance (seconds).
    b0_true : float
        True value of constant frequency offset (Hz).
    b1_true : float
        True value of frequency drift rate (Hz/s).
    gs_enu_offset_true : tuple (e, n)
        True ENU offset of the ground station from the reference point (km).
    sigma_f : float, optional
        Standard deviation of frequency observation noise (Hz) (default 1.0).
    sigma_tau : float, optional
        Standard deviation of timestamp observation noise (seconds) (default 1e-3).

    Returns
    -------
    crlb_cov : ndarray of shape (2, 2)
        CRLB covariance matrix for the EN position [e, n] (km^2). Returns a matrix of NaNs if the FIM is singular.
    """
    N = len(times)
    # We'll stack the Jacobians for all measurements (2 per time: frequency and timestamp)
    H_total = np.zeros((2*N, 5))  # 2N measurements, 5 state parameters
    for i in range(N):
        h, H_i = _compute_observation_and_jacobian_at_time(
            sat_positions_ecef[i], sat_velocities_ecef[i],
            gs_ref_geodetic, carrier_freq_hz,
            times[i], delta_t_true, b0_true, b1_true, gs_enu_offset_true
        )
        H_total[2*i:2*i+2, :] = H_i

    # Noise covariance for each measurement pair: R = diag([sigma_f^2, sigma_tau^2])
    # We assume independent across time, so the total noise covariance is block diagonal with these blocks.
    R_inv = np.eye(2*N)
    for i in range(N):
        R_inv[2*i, 2*i] = 1.0 / (sigma_f**2)
        R_inv[2*i+1, 2*i+1] = 1.0 / (sigma_tau**2)

    # Fisher Information Matrix: FIM = H^T R^{-1} H
    FIM = H_total.T @ R_inv @ H_total

    # Partition the FIM: position parameters (e,n) and nuisance parameters (delta_t, b0, b1)
    F_pp = FIM[0:2, 0:2]
    F_pn = FIM[0:2, 2:5]
    F_np = FIM[2:5, 0:2]
    F_nn = FIM[2:5, 2:5]

    # Compute the Schur complement: FIM_eff = F_pp - F_pn * F_nn^{-1} * F_np
    try:
        F_nn_inv = np.linalg.inv(F_nn)
    except np.linalg.LinAlgError:
        # If F_nn is singular, we cannot compute the Schur complement; return NaN
        return np.full((2, 2), np.nan)

    FIM_eff = F_pp - F_pn @ F_nn_inv @ F_np

    # Compute the CRLB covariance for position: inverse of FIM_eff
    try:
        crlb_cov = np.linalg.inv(FIM_eff)
    except np.linalg.LinAlgError:
        # If FIM_eff is singular, return NaN
        return np.full((2, 2), np.nan)

    return crlb_cov


def crlb_ellipse_area(crlb_cov):
    """
    Compute the area of the 1-sigma error ellipse from the CRLB covariance matrix.

    Parameters
    ----------
    crlb_cov : ndarray of shape (2, 2)
        CRLB covariance matrix for the EN position (units match input, typically km^2).

    Returns
    -------
    area : float
        Area of the 1-sigma error ellipse. Returns NaN if the input is invalid.
        Units are the square of the input covariance units (e.g., km^2 if CRLB is in km^2).
    """
    if np.any(np.isnan(crlb_cov)):
        return np.nan
    # The area of the ellipse defined by the covariance matrix is pi * sqrt(det(C))
    # For a 2D Gaussian, the 1-sigma ellipse area is pi * sqrt(det(C))
    det = np.linalg.det(crlb_cov)
    if det < 0:
        # This should not happen for a valid covariance matrix, but just in case
        return np.nan
    return np.pi * np.sqrt(det)


def crlb_cov_km2_to_m2(crlb_cov_km2):
    """
    Convert CRLB covariance from km^2 to m^2.

    Parameters
    ----------
    crlb_cov_km2 : ndarray of shape (2, 2)
        CRLB covariance matrix in km^2.

    Returns
    -------
    crlb_cov_m2 : ndarray of shape (2, 2)
        CRLB covariance matrix in m^2.
    """
    if np.any(np.isnan(crlb_cov_km2)):
        return np.full((2, 2), np.nan)
    return crlb_cov_km2 * 1e6  # (1000 m/km)^2 = 1e6


def crlb_rmse_bound_m(crlb_cov_km2):
    """
    Compute the RMSE lower bound from CRLB covariance, converted to meters.

    The RMSE lower bound is sqrt(trace(CRLB)), which is the best-case RMS position
    error achievable by any unbiased estimator.

    Parameters
    ----------
    crlb_cov_km2 : ndarray of shape (2, 2)
        CRLB covariance matrix in km^2.

    Returns
    -------
    rmse_bound_m : float
        RMSE lower bound in meters. Returns NaN if the input is invalid.
    """
    if np.any(np.isnan(crlb_cov_km2)):
        return np.nan
    trace_km2 = np.trace(crlb_cov_km2)
    if trace_km2 < 0:
        return np.nan
    return np.sqrt(trace_km2) * 1000.0  # Convert km to m


if __name__ == "__main__":
    # Example usage (for testing)
    # We'll create a simple circular orbit scenario
    from datetime import datetime, timedelta
    import orbit_propagation

    # Reference ground station (geodetic)
    gs_ref_geodetic = (40.0, -105.0, 1.5)  # Boulder, CO: lat, lon, alt
    # True ENU offset of the ground station (we assume we know it for this test)
    gs_enu_offset_true = (0.0, 0.0)  # at the reference point
    # True nuisance parameters
    delta_t_true = 0.0
    b0_true = 0.0
    b1_true = 0.0
    carrier_freq_hz = 1.6e9  # 1.6 GHz
    # Times
    times = np.array([0, 30, 60, 90, 120])  # seconds
    # Convert times to datetime for orbit propagation (we need a reference epoch)
    ref_time = datetime(2026, 6, 4, 12, 0, 0)
    times_dt = [ref_time + timedelta(seconds=t) for t in times]

    # Get satellite orbit (using synthetic orbit if sgp4 not available, but we'll try to use the function)
    # We need a TLE: we'll use a dummy TLE (the function will fall back to synthetic if sgp4 not available)
    line1 = "1 25544U 98067A   26155.53033517  .00012622  00000+0  28098-3 0  9994"
    line2 = "2 25544  51.6416 246.6182 0006706 302.2584 122.9105 15.50040302433475"
    try:
        sat_positions_ecef, sat_velocities_ecef = orbit_propagation.propagate_orbit(line1, line2, times_dt)
    except Exception as e:
        print(f"Error in orbit propagation: {e}")
        # Fallback to a simple circular orbit for testing
        # We'll create a simple circular orbit in the equatorial plane at 400 km altitude
        R = 6378.137 + 400.0  # km
        mu = 3.986004418e5
        n = np.sqrt(mu / R**3)  # rad/s
        sat_positions_ecef = []
        sat_velocities_ecef = []
        for t in times:
            angle = n * t
            x = R * np.cos(angle)
            y = R * np.sin(angle)
            z = 0.0
            vx = -R * n * np.sin(angle)
            vy = R * n * np.cos(angle)
            vz = 0.0
            sat_positions_ecef.append([x, y, z])
            sat_velocities_ecef.append([vx, vy, vz])
        sat_positions_ecef = np.array(sat_positions_ecef)
        sat_velocities_ecef = np.array(sat_velocities_ecef)

    # Compute CRLB
    crlb_cov = compute_crlb_en_position(
        sat_positions_ecef, sat_velocities_ecef,
        gs_ref_geodetic, carrier_freq_hz, times,
        delta_t_true, b0_true, b1_true, gs_enu_offset_true,
        sigma_f=1.0, sigma_tau=1e-3
    )
    print("CRLB covariance matrix (EN position, km^2):")
    print(crlb_cov)
    print("Ellipse area (km^2):", crlb_ellipse_area(crlb_cov))