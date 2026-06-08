"""Estimator Grid Map for LEO-DTF
-----------------------------
Implements grid search over position and time offset, with closed-form nuisance LS for b0/b1.
"""

import numpy as np
from scipy.linalg import cho_factor, cho_solve, lstsq
from scipy.special import logsumexp
from .observation_model import ObservationModel


def build_position_grid(e_min, e_max, n_min, n_max, step_m):
    """
    Build a 2D grid of candidate positions in EN coordinates.

    Parameters
    ----------
    e_min, e_max : float
        Minimum and maximum easting coordinate (meters)
    n_min, n_max : float
        Minimum and maximum northing coordinate (meters)
    step_m : float
        Grid step size in meters

    Returns
    -------
    grid_en : ndarray, shape [G, 2]
        Grid points where each row is [easting, northing] in meters
    """
    e_coords = np.arange(e_min, e_max + step_m, step_m)
    n_coords = np.arange(n_min, n_max + step_m, step_m)
    e_grid, n_grid = np.meshgrid(e_coords, n_coords, indexing='ij')
    grid_en = np.column_stack([e_grid.ravel(), n_grid.ravel()])
    return grid_en


def fit_nuisance_frequency_ls(predicted_doppler, observed_freq, t_rel, sigma_f, b0_prior=None, b1_prior=None):
    """
    Solve for nuisance parameters b0 and b1 using weighted least squares.

    Model: observed_freq = predicted_doppler + b0 + b1 * t_rel + noise

    Parameters
    ----------
    predicted_doppler : ndarray, shape [N]
        Predicted Doppler shift from geometry (Hz)
    observed_freq : ndarray, shape [N]
        Observed frequency offsets (Hz)
    t_rel : ndarray, shape [N]
        Relative times (seconds)
    sigma_f : float
        Frequency noise standard deviation (Hz)
    b0_prior : tuple (mean, std) or None
        Prior for b0 as (mean, std) in Hz
    b1_prior : tuple (mean, std) or None
        Prior for b1 as (mean, std) in Hz/s

    Returns
    -------
    b0_est : float
        Estimated b0 (Hz)
    b1_est : float
        Estimated b1 (Hz/s)
    residual_variance : float
        Variance of residuals after fitting
    """
    N = len(observed_freq)
    if N == 0:
        return 0.0, 0.0, np.inf

    # Design matrix for [b0, b1]
    A = np.column_stack([np.ones(N), t_rel])  # [N, 2]

    # Observations minus predicted Doppler
    y = observed_freq - predicted_doppler  # [N]

    # Weight matrix (inverse noise variance)
    W = np.eye(N) / (sigma_f ** 2)

    # Add priors as virtual observations using normal equations
    P = np.zeros((2, 2))  # Prior precision matrix
    mu = np.zeros(2)  # Prior mean vector
    
    if b0_prior is not None:
        b0_mean, b0_std = b0_prior
        P[0, 0] += 1.0 / (b0_std ** 2)
        mu[0] += b0_mean / (b0_std ** 2)
    
    if b1_prior is not None:
        b1_mean, b1_std = b1_prior
        P[1, 1] += 1.0 / (b1_std ** 2)
        mu[1] += b1_mean / (b1_std ** 2)
    
    # Solve weighted least squares with priors: (A^T W A + P) x = A^T W y + mu
    try:
        ATWA = A.T @ W @ A
        ATWy = A.T @ W @ y
        lhs = ATWA + P
        rhs = ATWy + mu
        x = np.linalg.solve(lhs, rhs)
        b0_est, b1_est = x[0], x[1]
        
        # Compute residuals and variance (using original N observations)
        residuals = y[:N] - A[:N, :] @ x
        residual_variance = np.mean(residuals ** 2) if len(residuals) > 0 else 0.0
    except np.linalg.LinAlgError:
        # Fallback to pseudo-inverse
        x, residuals, rank, s = lstsq(A[:N, :], y[:N])
        b0_est, b1_est = x[0], x[1]
        residual_variance = np.mean(residuals ** 2) if len(residuals) > 0 else np.inf

    return b0_est, b1_est, residual_variance


def score_candidate(position_en, delta_t, ground_station_ecef, enu_basis,
                    satellite_positions_ecsf, satellite_velocities_ecsf,
                    nominal_times, observed_freq, observed_tau,
                    carrier_freq_hz, sigma_f, sigma_tau,
                    b0_prior=None, b1_prior=None, delta_t_prior=None):
    """
    Score a candidate position and time offset using negative log-likelihood.

    Parameters
    ----------
    position_en : ndarray, shape [2,]
        Candidate position in EN coordinates (meters)
    delta_t : float
        Time offset nuisance (seconds)
    ground_station_ecef : ndarray, shape [3,]
        Ground station position in ECEF (km)
    enu_basis : ndarray, shape [3, 3]
        Columns are E, N, Up unit vectors in ECEF
    satellite_positions_ecsf : ndarray, shape [N, 3]
        Satellite positions over time (km)
    satellite_velocities_ecsf : ndarray, shape [N, 3]
        Satellite velocities over time (km/s)
    nominal_times : ndarray, shape [N]
        Nominal packet times (seconds)
    observed_freq : ndarray, shape [N]
        Observed frequency offsets (Hz)
    observed_tau : ndarray, shape [N] or None
        Observed timestamp offsets (seconds), or None if not available
    carrier_freq_hz : float
        Carrier frequency (Hz)
    sigma_f : float
        Frequency noise std (Hz)
    sigma_tau : float
        Timestamp noise std (seconds)
    b0_prior : tuple (mean, std) or None
        Prior for b0
    b1_prior : tuple (mean, std) or None
        Prior for b1
    delta_t_prior : tuple (mean, std) or None
        Prior for delta_t

    Returns
    -------
    score : float
        Negative log posterior score (lower is better)
    b0_est : float
        Estimated b0 from LS fit
    b1_est : float
        Estimated b1 from LS fit
    """
    N = len(nominal_times)
    if N == 0:
        return np.inf, 0.0, 0.0

    # Convert EN position to ECEF offset (position_en is in meters, ECEF is in km)
    position_ecef_offset = enu_basis @ np.append(position_en / 1000.0, 0.0)  # Only EN, no up
    ground_station_ecef = np.array(ground_station_ecef)
    candidate_ground_ecef = ground_station_ecef + position_ecef_offset

    # Create observation model instance for this candidate ground position
    obs_model = ObservationModel(candidate_ground_ecef, carrier_freq_hz=carrier_freq_hz)

    # Compute predicted Doppler and delay for each time
    predicted_doppler = np.zeros(N)
    predicted_delay = np.zeros(N)

    for i in range(N):
        sat_state = (satellite_positions_ecsf[i], satellite_velocities_ecsf[i])
        doppler_hz, propagation_delay_s = obs_model.compute_expected_measurements(
            sat_state, nominal_times[i]
        )
        predicted_doppler[i] = doppler_hz
        predicted_delay[i] = propagation_delay_s

    # Frequency observation model: z_f = predicted_doppler + b0 + b1 * t + noise_f
    # Timestamp observation model: z_tau = t_nominal + delta_t + predicted_delay + noise_tau

    # Fit nuisance parameters b0, b1 using frequency observations
    t_rel = nominal_times - nominal_times[0]  # Relative to first timestamp
    b0_est, b1_est, residual_var_f = fit_nuisance_frequency_ls(
        predicted_doppler, observed_freq, t_rel, sigma_f, b0_prior, b1_prior
    )

    # Compute frequency residuals
    predicted_freq = predicted_doppler + b0_est + b1_est * t_rel
    freq_residuals = observed_freq - predicted_freq
    freq_precision = 1.0 / (sigma_f ** 2)
    freq_score = 0.5 * freq_precision * np.sum(freq_residuals ** 2)

    # Compute timestamp residuals (if available)
    tau_score = 0.0
    if observed_tau is not None:
        predicted_tau = nominal_times + delta_t + predicted_delay
        tau_residuals = observed_tau - predicted_tau
        tau_precision = 1.0 / (sigma_tau ** 2)
        tau_score = 0.5 * tau_precision * np.sum(tau_residuals ** 2)

    # Prior scores
    prior_score = 0.0
    if delta_t_prior is not None:
        delta_t_mean, delta_t_std = delta_t_prior
        prior_score += 0.5 * ((delta_t - delta_t_mean) / delta_t_std) ** 2
    if b0_prior is not None:
        b0_mean, b0_std = b0_prior
        prior_score += 0.5 * ((b0_est - b0_mean) / b0_std) ** 2
    if b1_prior is not None:
        b1_mean, b1_std = b1_prior
        prior_score += 0.5 * ((b1_est - b1_mean) / b1_std) ** 2

    total_score = freq_score + tau_score + prior_score
    return total_score, b0_est, b1_est


def estimate_grid_map(position_grid_en, delta_t_grid, ground_station_ecef, enu_basis,
                      satellite_positions_ecsf, satellite_velocities_ecsf,
                      nominal_times, observed_freq, observed_tau,
                      carrier_freq_hz, sigma_f, sigma_tau,
                      b0_prior=None, b1_prior=None, delta_t_prior=None):
    """
    Perform grid search over position and time offset with Bayesian posterior scoring.

    Parameters
    ----------
    position_grid_en : ndarray, shape [G, 2]
        Grid of candidate positions in EN coordinates (meters)
    delta_t_grid : ndarray, shape [D,]
        Grid of time offset values (seconds)
    ground_station_ecef : ndarray, shape [3,]
        Ground station position in ECEF (km)
    enu_basis : ndarray, shape [3, 3]
        Columns are E, N, Up unit vectors in ECEF
    satellite_positions_ecsf : ndarray, shape [N, 3]
        Satellite positions over time (km)
    satellite_velocities_ecsf : ndarray, shape [N, 3]
        Satellite velocities over time (km/s)
    nominal_times : ndarray, shape [N]
        Nominal packet times (seconds)
    observed_freq : ndarray, shape [N]
        Observed frequency offsets (Hz)
    observed_tau : ndarray, shape [N] or None
        Observed timestamp offsets (seconds), or None
    carrier_freq_hz : float
        Carrier frequency (Hz)
    sigma_f : float
        Frequency noise std (Hz)
    sigma_tau : float
        Timestamp noise std (seconds)
    b0_prior : tuple (mean, std) or None
        Prior for b0
    b1_prior : tuple (mean, std) or None
        Prior for b1
    delta_t_prior : tuple (mean, std) or None
        Prior for delta_t

    Returns
    -------
    posterior : ndarray, shape [G,]
        Normalized posterior probability over position grid
    map_position_en : ndarray, shape [2,]
        MAP position estimate in EN coordinates (meters)
    best_b0 : float
        b0 estimate at MAP
    best_b1 : float
        b1 estimate at MAP
    best_delta_t : float
        delta_t estimate at MAP (marginalized)
    """
    G = position_grid_en.shape[0]
    D = len(delta_t_grid)
    scores = np.zeros((G, D))

    # Compute score for each position and delta_t combination
    for g in range(G):
        position_en = position_grid_en[g]
        for d in range(D):
            delta_t = delta_t_grid[d]
            score, b0_est, b1_est = score_candidate(
                position_en, delta_t, ground_station_ecef, enu_basis,
                satellite_positions_ecsf, satellite_velocities_ecsf,
                nominal_times, observed_freq, observed_tau,
                carrier_freq_hz, sigma_f, sigma_tau,
                b0_prior, b1_prior, delta_t_prior
            )
            scores[g, d] = score

    # Convert scores to log probabilities (negative scores)
    log_probs = -scores  # [G, D]

    # Marginalize over delta_t using logsumexp for numerical stability
    log_posterior_g = logsumexp(log_probs, axis=1)  # [G,]
    log_posterior_g -= logsumexp(log_posterior_g)  # Normalize

    posterior = np.exp(log_posterior_g)  # [G,]

    # Find MAP position
    map_idx = np.argmax(posterior)
    map_position_en = position_grid_en[map_idx]

    # For nuisance parameters at MAP, we need the delta_t that maximizes posterior
    # Get the joint posterior at MAP position
    log_joint_at_map = log_probs[map_idx, :]  # [D,]
    log_joint_at_map -= logsumexp(log_joint_at_map)  # Normalize
    joint_posterior_at_map = np.exp(log_joint_at_map)  # [D,]
    best_delta_t_idx = np.argmax(joint_posterior_at_map)
    best_delta_t = delta_t_grid[best_delta_t_idx]

    # To get b0/b1 at MAP, we'd need to recompute or store them
    # For now, compute at the MAP position and best delta_t
    _, best_b0, best_b1 = score_candidate(
        map_position_en, best_delta_t, ground_station_ecef, enu_basis,
        satellite_positions_ecsf, satellite_velocities_ecsf,
        nominal_times, observed_freq, observed_tau,
        carrier_freq_hz, sigma_f, sigma_tau,
        b0_prior, b1_prior, delta_t_prior
    )

    return posterior, map_position_en, best_b0, best_b1, best_delta_t


def compute_hpd_region(posterior, grid, mass=0.95):
    """
    Compute Highest Posterior Density (HPD) region from discrete posterior.

    Parameters
    ----------
    posterior : ndarray, shape [G,]
        Posterior probabilities (must sum to 1)
    grid : ndarray, shape [G, 2]
        Grid points corresponding to posterior
    mass : float
        Desired probability mass in HPD region (default 0.95)

    Returns
    -------
    hpd_mask : ndarray, shape [G,], dtype=bool
        Boolean mask indicating which grid points are in HPD region
    hpd_mass : float
        Actual probability mass in returned region
    """
    if len(posterior) == 0:
        return np.array([], dtype=bool), 0.0

    # Sort by posterior density (descending)
    sorted_indices = np.argsort(posterior)[::-1]
    sorted_posterior = posterior[sorted_indices]

    # Accumulate probability until we reach desired mass
    cumulative_mass = np.cumsum(sorted_posterior)
    hpd_size = np.searchsorted(cumulative_mass, mass) + 1
    hpd_size = min(hpd_size, len(sorted_indices))  # Don't exceed grid size

    # Create mask
    hpd_mask = np.zeros(len(posterior), dtype=bool)
    hpd_mask[sorted_indices[:hpd_size]] = True
    hpd_mass = np.sum(posterior[hpd_mask])

    return hpd_mask, hpd_mass


def compute_ambiguity_score(posterior, grid):
    """
    Compute ambiguity score based on separation between modes.

    Parameters
    ----------
    posterior : ndarray, shape [G,]
        Posterior probabilities
    grid : ndarray, shape [G, 2]
        Grid points in EN coordinates (meters)

    Returns
    -------
    ambiguity_score : float
        Approximate ambiguity score (distance between top modes in meters)
        Returns 0 if only one significant mode
    """
    if len(posterior) < 2:
        return 0.0

    # Find local maxima (simple approach: check neighbors in sorted order)
    sorted_indices = np.argsort(posterior)[::-1]
    sorted_posterior = posterior[sorted_indices]
    sorted_grid = grid[sorted_indices]

    # Consider top peaks that have significant posterior mass
    # Find peaks where posterior drops significantly after
    posterior_threshold = 0.1 * np.max(posterior)  # 10% of peak
    peak_mask = sorted_posterior > posterior_threshold
    peak_indices = np.where(peak_mask)[0]

    if len(peak_indices) < 2:
        return 0.0

    # Get the top few peaks
    n_peaks = min(len(peak_indices), 5)  # Consider up to top 5 peaks
    top_peak_indices = peak_indices[:n_peaks]
    top_peaks_grid = sorted_grid[top_peak_indices]
    top_peaks_posterior = sorted_posterior[top_peak_indices]

    # Compute weighted centroid of top peaks
    weights = top_peaks_posterior
    weights = weights / np.sum(weights)
    centroid = np.sum(top_peaks_grid * weights[:, np.newaxis], axis=0)

    # Compute ambiguity as RMS distance from centroid
    distances = np.linalg.norm(top_peaks_grid - centroid, axis=1)
    ambiguity_score = np.sqrt(np.average(distances ** 2, weights=weights))

    return ambiguity_score


if __name__ == "__main__":
    # Example usage (for testing)
    print("EstimatorGridMap module loaded successfully")