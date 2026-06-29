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