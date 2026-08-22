from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List


class InterpolationMethod(Enum):
    LINEAR = "Linear"
    CUBIC = "Cubic Spline"
    QUADRATIC = "Quadratic"
    NEAREST = "Nearest Neighbor"


class TemperatureType(Enum):
    VAPOUR = "Vapour"
    LIQUID = "Liquid"


class ConcentrationBasis(Enum):
    """Which concentration to report when a temperature of interest is reached
    at several points along the cloud.

    A time-varying release is modelled as many observers, and they can reach
    the same temperature at very different concentrations. The one that reaches
    furthest downwind is often a late, dilute parcel, so the two choices can
    differ by an order of magnitude.
    """
    # Worst case for exposure, taken across every crossing. Comes from a
    # different point than the reported distance, and is the conservative
    # reading for toxic and flammable assessment alike.
    MAXIMUM = "Highest at any crossing"
    # The concentration where the temperature of interest reaches furthest
    # downwind, so distance and concentration describe one real point.
    AT_FURTHEST = "At the furthest crossing"


class WorstCase(Enum):
    """Which extreme of an output counts as the worst case when the
    temperature of interest is reached more than once along the cloud."""
    MAXIMUM = "Maximum"  # e.g. furthest downwind distance
    MINIMUM = "Minimum"  # e.g. lowest concentration


@dataclass
class TemperatureReading:
    """Quantities derived at a single temperature of interest."""
    temperature_of_interest: float
    downwind_distance: Optional[float] = None
    concentration: Optional[float] = None


@dataclass
class AnalysisResult:
    subsection: str
    scenario: str
    weather: str
    interpolation_method: str
    # One reading per requested temperature of interest
    readings: List[TemperatureReading] = field(default_factory=list)
    # Coldest centreline temperature anywhere in the cloud. A property of
    # the whole profile rather than of any one temperature of interest,
    # so it sits here instead of on TemperatureReading.
    minimum_temperature: Optional[float] = None 