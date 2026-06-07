"""Orbit Propagation for LEO-DTF
-----------------------------
Propagates satellite orbit using SGP4 from TLE data with TEME to ECEF conversion.
If SGP4 is not available, provides a synthetic circular orbit for testing.
"""

import numpy as np
from datetime import datetime

from . import frame_transform

try:
    from sgp4.api import Satrec, jday
    HAS_SGP4 = True
except ImportError:
    HAS_SGP4 = False

# Earth gravitational constant (km^3/s^2)
MU_EARTH = 3.986004418e5
# Earth radius (km)
R_EARTH = 6378.137


def _synthetic_circular_orbit(tle_line1, tle_line2, times):
    """
    Generate a synthetic circular orbit for testing when SGP4 is not available.
    Assumes a circular orbit at 400 km altitude, zero inclination, and RAAN=0.
    Note: This orbit is in an inertial frame (non-rotating) and is output as if it were ECEF.
          This is a limitation and should be replaced with proper SGP4 when available.

    Parameters
    ----------
    tle_line1 : str
        First line of TLE (ignored in synthetic orbit)
    tle_line2 : str
        Second line of TLE (ignored in synthetic orbit)
    times : list of datetime
        Times at which to compute position and velocity.

    Returns
    -------
    positions : ndarray of shape (len(times), 3)
        Satellite position in ECEF (km).
    velocities : ndarray of shape (len(times), 3)
        Satellite velocity in ECEF (km/s).
    """
    # Orbital parameters for synthetic orbit
    altitude = 400.0  # km
    radius = R_EARTH + altitude  # km
    # Mean motion for circular orbit: n = sqrt(mu / r^3)
    n = np.sqrt(MU_EARTH / radius**3)  # rad/s

    positions = []
    velocities = []
    for t in times:
        # Use seconds since epoch for simplicity (we don't use the TLE epoch in synthetic)
        # We'll use the time in seconds since an arbitrary epoch (e.g., the first time)
        # For simplicity, we assume the orbit starts at (radius, 0, 0) at t=0 seconds.
        # We need a time reference: let's use the first time in the list as t=0.
        if len(times) == 0:
            dt_sec = 0.0
        else:
            dt_sec = (t - times[0]).total_seconds()
        # Angle from reference
        angle = n * dt_sec  # rad
        # Position in the orbital plane (which we align with equatorial plane for simplicity)
        x = radius * np.cos(angle)
        y = radius * np.sin(angle)
        z = 0.0
        # Velocity
        vx = -radius * n * np.sin(angle)
        vy = radius * n * np.cos(angle)
        vz = 0.0
        positions.append([x, y, z])
        velocities.append([vx, vy, vz])

    return np.array(positions), np.array(velocities)


def propagate_orbit(tle_line1, tle_line2, times):
    """
    Propagate satellite orbit from TLE lines to given times.

    Parameters
    ----------
    tle_line1 : str
        First line of TLE (69 characters)
    tle_line2 : str
        Second line of TLE (69 characters)
    times : list of datetime
        Times at which to compute position and velocity (UTC).

    Returns
    -------
    positions : ndarray of shape (len(times), 3)
        Satellite position in ECEF (km).
    velocities : ndarray of shape (len(times), 3)
        Satellite velocity in ECEF (km/s).

    Notes
    -----
    - If SGP4 is available, uses the SGP4 propagator to compute TEME coordinates and converts to ECEF.
      The conversion uses GMST and neglects nutation and polar motion (see frame_transform.teme_to_ecef).
      This is a limitation; for high-accuracy applications, a more rigorous transformation should be used.
    - If SGP4 is not available, falls back to a synthetic circular orbit (for testing only).
      The synthetic orbit ignores Earth rotation and is not suitable for realistic simulations.
    """
    if HAS_SGP4:
        # Initialize satellite object from TLE
        satellite = Satrec.twoline2rv(tle_line1, tle_line2)

        positions = []
        velocities = []
        for t in times:
            # Break datetime into components for sgp4
            year = t.year
            month = t.month
            day = t.day
            hour = t.hour
            minute = t.minute
            second = t.second + t.microsecond * 1e-6  # fractional seconds

            # Compute Julian date (needed for TEME-to-ECEF conversion)
            jd, fr = jday(year, month, day, hour, minute, second)
            jd_utc = jd + fr

            # Propagate using SGP4 (returns TEME position and velocity)
            # New API: sgp4(jd, fr) — Julian date as (integer, fraction)
            e, r, v = satellite.sgp4(jd, fr)
            if e != 0:
                raise RuntimeError(f"SGP4 propagation error {e} at time {t}")

            # Convert TEME to ECEF
            r_ecef, v_ecef = frame_transform.teme_to_ecef(r, v, jd_utc)
            positions.append(r_ecef)
            velocities.append(v_ecef)

        return np.array(positions), np.array(velocities)
    else:
        # Fallback to synthetic orbit
        return _synthetic_circular_orbit(tle_line1, tle_line2, times)


if __name__ == "__main__":
    # Example usage (for testing)
    # Use a TLE for the ISS (example)
    line1 = "1 25544U 98067A   26155.53033517  .00012622  00000+0  28098-3 0  9994"
    line2 = "2 25544  51.6416 246.6182 0006706 302.2584 122.9105 15.50040302433475"
    from datetime import datetime, timedelta
    times = [datetime(2026, 6, 4, 12, 0, 0) + timedelta(seconds=i*30) for i in range(10)]
    try:
        pos, vel = propagate_orbit(line1, line2, times)
        print(f"Propagated {len(times)} points.")
        print(f"First position (ECEF): {pos[0]} km")
        print(f"First velocity (ECEF): {vel[0]} km/s")
    except Exception as e:
        print(f"Error: {e}")