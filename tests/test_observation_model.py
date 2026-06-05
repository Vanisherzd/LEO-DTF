"""Tests for the observation model.
"""

import numpy as np
import pytest
from leodtf.observation_model import ObservationModel

def test_observation_model_basic():
    # Ground station at origin
    gs_ecef = np.array([0.0, 0.0, 0.0])
    obs_model = ObservationModel(gs_ecef, carrier_freq_hz=1.6e9)

    # Satellite at (0, 0, 6371+400) km, velocity zero
    sat_pos = [0.0, 0.0, 6371.0 + 400.0]
    sat_vel = [0.0, 0.0, 0.0]
    doppler, delay = obs_model.compute_expected_measurements((sat_pos, sat_vel), 0.0)

    # Expected: zero range rate -> zero Doppler
    assert abs(doppler) < 1e-9
    # Expected delay: distance / speed of light
    expected_delay = (6371.0 + 400.0) / 299792.458
    assert abs(delay - expected_delay) < 1e-9

def test_observation_model_with_velocity():
    gs_ecef = np.array([0.0, 0.0, 0.0])
    obs_model = ObservationModel(gs_ecef, carrier_freq_hz=1.6e9)

    # Satellite moving along z-axis away from ground station
    sat_pos = [0.0, 0.0, 6371.0 + 400.0]
    sat_vel = [0.0, 0.0, 1.0]  # 1 km/s away
    doppler, delay = obs_model.compute_expected_measurements((sat_pos, sat_vel), 0.0)

    # Expected Doppler: negative because moving away (positive range rate -> negative Doppler)
    # f_d = - (f_c / c) * range_rate
    expected_doppler = - (1.6e9 / 299792.458) * 1.0
    assert abs(doppler - expected_doppler) < 1e-9
    # Delay unchanged
    expected_delay = (6371.0 + 400.0) / 299792.458
    assert abs(delay - expected_delay) < 1e-9

def test_contaminated_observations():
    gs_ecef = np.array([0.0, 0.0, 0.0])
    obs_model = ObservationModel(gs_ecef, carrier_freq_hz=1.6e9)

    sat_pos = [0.0, 0.0, 6371.0 + 400.0]
    sat_vel = [0.0, 0.0, 0.0]
    time_s = 0.0
    delta_t = 1e-3
    b0 = 100.0
    b1 = 0.1

    z_f, z_tau = obs_model.compute_contaminated_observations(
        (sat_pos, sat_vel), time_s, delta_t, b0, b1, noise_f=0.0, noise_tau=0.0
    )

    # Expected frequency: Doppler (0) + b0 + b1 * t
    assert abs(z_f - (b0 + b1 * time_s)) < 1e-9
    # Expected timestamp: t_nominal + delta_t + delay
    delay = (6371.0 + 400.0) / 299792.458
    assert abs(z_tau - (time_s + delta_t + delay)) < 1e-9

if __name__ == "__main__":
    pytest.main([__file__, "-v"])