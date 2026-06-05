"""TLE Loader for LEO-DTF.

Loads and parses Two-Line Element (TLE) sets for satellite orbit prediction.
"""

from dataclasses import dataclass
from datetime import datetime
import math


@dataclass
class TLEData:
    """Container for parsed TLE data."""
    catalog_num: int
    classification: str
    epoch: datetime
    mean_motion: float      # rev/day
    eccentricity: float
    inclination: float      # rad
    raan: float             # rad  (Right Ascension of Ascending Node)
    omega: float            # rad  (Argument of Periapsis)
    mean_anomaly: float     # rad  (Mean Anomaly)
    bstar: float
    orbit_num: int
    semi_major_axis: float  # km
    mean_motion_rad_s: float


def parse_tle(line1: str, line2: str) -> TLEData:
    """
    Parse raw TLE lines into structured data.

    Uses sgp4.api.Satrec.twoline2rv if available for robust parsing of
    implied-exponent fields (e.g., "28098-3"). Falls back to manual parsing
    only if sgp4 is unavailable.

    Parameters
    ----------
    line1 : str
        First line of TLE (69 characters)
    line2 : str
        Second line of TLE (69 characters)

    Returns
    -------
    TLEData
        Parsed TLE data

    Raises
    ------
    ValueError
        If TLE lines are not 69 characters or format is invalid.
    """
    if len(line1) != 69 or len(line2) != 69:
        raise ValueError("TLE lines must be exactly 69 characters")
    if line1[0] != '1' or line2[0] != '2':
        raise ValueError("Invalid TLE format")

    # Prefer sgp4 library for robust parsing of implied-exponent fields
    try:
        from sgp4.api import Satrec
        from sgp4.iod_support import twoline2rv
        sat, message = twoline2rv(line1, line2)
        if message != "":
            raise ValueError(f"SGP4 parsing warning: {message}")
        
        # Extract fields from Satrec object
        catalog_num = sat.satnum
        classification = sat.classification
        epoch_year = sat.epochyr
        epoch_day = sat.epochdays
        bstar = sat.bstar
        orbit_num = sat.elnum
        
        inclination = math.radians(sat.inclo)
        raan = math.radians(sat.nodeo)
        eccentricity = sat.ecco
        omega = math.radians(sat.argpo)
        mean_anomaly = math.radians(sat.mo)
        mean_motion = sat.no_kozai  # rev/day
        
        # Compute semi-major axis from mean motion
        MU_EARTH = 3.986004418e5  # km^3/s^2
        n_rad_s = mean_motion * 2 * math.pi / (24 * 3600)
        semi_major_axis = (MU_EARTH / (n_rad_s ** 2)) ** (1/3)
        mean_motion_rad_s = n_rad_s
        
        # Convert epoch (day-of-year to datetime)
        year = 2000 + epoch_year if epoch_year < 57 else 1900 + epoch_year
        from datetime import datetime, timedelta
        # epoch_day is day-of-year (1.0 = Jan 1, 60.5 = Mar 1 noon, etc.)
        epoch = datetime(year, 1, 1) + timedelta(days=epoch_day - 1)
        
        return TLEData(
            catalog_num=catalog_num,
            classification=classification,
            epoch=epoch,
            mean_motion=mean_motion,
            eccentricity=eccentricity,
            inclination=inclination,
            raan=raan,
            omega=omega,
            mean_anomaly=mean_anomaly,
            bstar=bstar,
            orbit_num=orbit_num,
            semi_major_axis=semi_major_axis,
            mean_motion_rad_s=mean_motion_rad_s
        )
    except ImportError:
        pass  # Fall through to manual parsing
    
    # Manual parsing fallback (may fail on implied-exponent fields)
    try:
        bstar_str = line1[53:61]
        # Handle implied exponent format (e.g., "28098-3" means 2.8098e-3)
        if '-' in bstar_str or '+' in bstar_str:
            bstar_parts = bstar_str.replace(' ', '0').split('-') if '-' in bstar_str else bstar_str.replace(' ', '0').split('+')
            if len(bstar_parts) == 2 and bstar_parts[1].strip():
                mantissa = float(bstar_parts[0]) / 1e5
                exponent = int(bstar_parts[1])
                bstar = mantissa * (10 ** (-exponent if '-' in bstar_str else exponent))
            else:
                bstar = float(bstar_str.replace(' ', '0')) * 1e-5
        else:
            bstar = float(bstar_str.replace(' ', '0')) * 1e-5
    except ValueError:
        bstar = 0.0
    
    # Line 1 fields
    catalog_num = int(line1[2:7])
    classification = line1[7]
    epoch_year = int(line1[18:20])
    epoch_day = float(line1[20:32])
    orbit_num = int(line1[63:68])

    # Line 2 fields
    inclination = math.radians(float(line2[8:16]))
    raan = math.radians(float(line2[17:25]))
    eccentricity = float(line2[26:33]) / 1e7
    omega = math.radians(float(line2[34:42]))
    mean_anomaly = math.radians(float(line2[43:51]))
    mean_motion = float(line2[52:63])

    # Convert epoch year and day to datetime
    # Note: This is a simplified conversion; for production use a proper TLE library
    year = 2000 + epoch_year if epoch_year < 57 else 1900 + epoch_year
    month = 1
    day = 1
    # We'll use a simple approach: convert the fractional day to month/day
    # For accuracy, consider using `sgp4` library or `skyfield`
    # For now, we'll just set the day as the integer part and the fraction as time of day
    day_int = int(epoch_day)
    fraction = epoch_day - day_int
    hours = fraction * 24
    minutes = (hours - int(hours)) * 60
    seconds = (minutes - int(minutes)) * 60

    from datetime import datetime, timedelta
    epoch = datetime(year, month, day_int) + timedelta(days=int(fraction), hours=int(hours), minutes=int(minutes), seconds=int(seconds))

    # Compute semi-major axis from mean motion (rev/day)
    # n = mean_motion * 2 * pi / (24*3600)  [rad/s]
    # a^3 = MU / n^2
    MU_EARTH = 3.986004418e5  # km^3/s^2
    n_rad_s = mean_motion * 2 * math.pi / (24 * 3600)
    semi_major_axis = (MU_EARTH / (n_rad_s ** 2)) ** (1/3)
    mean_motion_rad_s = n_rad_s

    return TLEData(
        catalog_num=catalog_num,
        classification=classification,
        epoch=epoch,
        mean_motion=mean_motion,
        eccentricity=eccentricity,
        inclination=inclination,
        raan=raan,
        omega=omega,
        mean_anomaly=mean_anomaly,
        bstar=bstar,
        orbit_num=orbit_num,
        semi_major_axis=semi_major_axis,
        mean_motion_rad_s=mean_motion_rad_s
    )


if __name__ == "__main__":
    # Example usage (for testing)
    line1 = "1 25544U 98067A   26155.53033517  .00012622  00000+0  28098-3 0  9994"
    line2 = "2 25544  51.6416 246.6182 0006706 302.2584 122.9105 15.50040302433475"
    tle = parse_tle(line1, line2)
    print(tle)