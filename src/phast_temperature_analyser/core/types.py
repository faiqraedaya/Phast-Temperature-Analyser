from enum import Enum
from dataclasses import dataclass


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
    downwind_distance: float
    interpolation_method: str
    temperature_of_interest: float 