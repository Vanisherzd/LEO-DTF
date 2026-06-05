"""Observation Model for LEO-DTF
-----------------------------
Models the relationship between satellite state and measurements (Doppler, time offset).
"""

import numpy as np

class ObservationModel:
    def __init__(self, ground_station_ecef, carrier_freq_hz=1.6e9):
        """
        Initialize observation model.

        Parameters
        ----------
        ground_station_ecef : ndarray
            Ground station position in ECEF (km)
        carrier_freq_hz : float
            Carrier frequency in Hz (default: 1.6 GHz for L-band)
        """
        self.ground_station_ecef = np.array(ground_station_ecef, dtype=float)
        self.carrier_freq_hz = carrier_freq_hz
        self.speed_of_light = 299792.458  # km/s

    def compute_expected_measurements(self, satellite_state_ecef, time_s):
        """
        Compute expected Doppler shift and propagation delay (time offset) from satellite state.

        Parameters
        ----------
        satellite_state_ecef : tuple or ndarray
            (position, velocity) where each is an ndarray of shape (3,) in ECEF (km, km/s)
        time_s : float
            Time in seconds (used for potential time-varying nuisance, but not in base model)

        Returns
        -------
        doppler_hz : float
            Expected Doppler shift (Hz) due to relative motion (negative for approaching)
        propagation_delay_s : float
            Expected propagation delay (seconds) = range / speed_of_light
        """
        sat_pos, sat_vel = satellite_state_ecef
        sat_pos = np.array(sat_pos)
        sat_vel = np.array(sat_vel)

        # Vector from ground station to satellite
        los_vec = sat_pos - self.ground_station_ecef
        range_km = np.linalg.norm(los_vec)

        # Line-of-sight velocity (range rate)
        # Assuming ground station is stationary (velocity = 0)
        los_unit = los_vec / range_km
        range_rate_km_s = np.dot(sat_vel, los_unit)  # km/s

        # Doppler shift: f_d = - (f_c / c) * range_rate
        # Negative because approaching satellite (positive range rate) gives negative Doppler
        doppler_hz = - (self.carrier_freq_hz / self.speed_of_light) * range_rate_km_s

        # Propagation delay
        propagation_delay_s = range_km / self.speed_of_light

        return doppler_hz, propagation_delay_s

    def compute_contaminated_observations(self, satellite_state_ecef, time_s, delta_t, b0, b1, noise_f=0, noise_tau=0):
        """
        Compute contaminated frequency and timestamp observations.

        Parameters
        ----------
        satellite_state_ecef : tuple or ndarray
            (position, velocity) where each is an ndarray of shape (3,) in ECEF (km, km/s)
        time_s : float
            Nominal time in seconds (e.g., transmission time)
        delta_t : float
            Time offset nuisance (seconds)
        b0 : float
            Constant frequency offset (Hz)
        b1 : float
            Frequency drift rate (Hz/s)
        noise_f : float or ndarray, optional
            Additive noise on frequency observation (Hz) (default 0)
        noise_tau : float or ndarray, optional
            Additive noise on timestamp observation (seconds) (default 0)

        Returns
        -------
        z_f : float
            Contaminated frequency observation (Hz)
        z_tau : float
            Contaminated timestamp observation (seconds)
        """
        doppler_hz, propagation_delay_s = self.compute_expected_measurements(satellite_state_ecef, time_s)
        # Frequency observation: z_f = f_D + b0 + b1 * t + noise_f
        z_f = doppler_hz + b0 + b1 * time_s + noise_f
        # Timestamp observation: z_tau = t_nominal + delta_t + rho/c + noise_tau
        z_tau = time_s + delta_t + propagation_delay_s + noise_tau
        return z_f, z_tau

if __name__ == "__main__":
    # Example usage (for testing)
    ground_station = [0, 0, 0]  # Geocentric
    obs_model = ObservationModel(ground_station)
    # Dummy satellite state: position [0, 0, 6371+400] km, velocity [0, 0, 0]
    sat_pos = [0, 0, 6371 + 400]
    sat_vel = [0, 0, 0]
    doppler, delay = obs_model.compute_expected_measurements((sat_pos, sat_vel), 0)
    print(f"Doppler: {doppler} Hz, Delay: {delay} s")
    # Example with nuisance
    z_f, z_tau = obs_model.compute_contaminated_observations((sat_pos, sat_vel), 0, delta_t=1e-3, b0=100, b1=0.1)
    print(f"Contaminated frequency: {z_f} Hz, Contaminated timestamp: {z_tau} s")