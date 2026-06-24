from enum import Enum
from dataclasses import dataclass
from typing import Optional


class InterpolationMethod(Enum):
    LINEAR = "Linear"
    CUBIC = "Cubic Spline"
    QUADRATIC = "Quadratic"
    NEAREST = "Nearest Neighbor"


class TemperatureType(Enum):
    VAPOUR = "Vapour"
    LIQUID = "Liquid"


@dataclass
class AnalysisResult:
    subsection: str
    scenario: str
    weather: str
    interpolation_method: str
    temperature_of_interest: float
    # Both derived at the temperature of interest
    downwind_distance: Optional[float]
    concentration: Optional[float] 