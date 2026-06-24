import numpy as np
from scipy import interpolate
import logging
from typing import Optional

from phast_temperature_analyser.core.types import InterpolationMethod


class InterpolationEngine:
    """Handles different interpolation methods for dispersion data.

    Reads off an output quantity (e.g. downwind distance or concentration)
    at a target temperature, by interpolating against the centreline
    temperature profile of the dispersion cloud.
    """

    @staticmethod
    def interpolate(
        temperatures: np.ndarray,
        outputs: np.ndarray,
        target_temp: float,
        method: InterpolationMethod
    ) -> Optional[float]:
        """
        Interpolate an output quantity at a target temperature.

        Args:
            temperatures: Array of centreline temperatures
            outputs: Array of the quantity to read off (distance or concentration)
            target_temp: Temperature of interest to interpolate at
            method: Interpolation method to use

        Returns:
            Interpolated output value or None if interpolation fails
        """
        try:
            if len(temperatures) < 2 or len(outputs) < 2:
                return None

            # Ensure arrays are sorted by temperature (descending for dispersion)
            sorted_indices = np.argsort(temperatures)[::-1]
            temp_sorted = temperatures[sorted_indices]
            output_sorted = outputs[sorted_indices]

            # Check if target temperature is within range
            if target_temp > temp_sorted[0] or target_temp < temp_sorted[-1]:
                return InterpolationEngine._handle_extrapolation(
                    temp_sorted, output_sorted, target_temp
                )

            if method == InterpolationMethod.LINEAR:
                return InterpolationEngine._linear_interpolation(
                    temp_sorted, output_sorted, target_temp
                )
            elif method == InterpolationMethod.CUBIC:
                return InterpolationEngine._cubic_interpolation(
                    temp_sorted, output_sorted, target_temp
                )
            elif method == InterpolationMethod.QUADRATIC:
                return InterpolationEngine._quadratic_interpolation(
                    temp_sorted, output_sorted, target_temp
                )
            elif method == InterpolationMethod.NEAREST:
                return InterpolationEngine._nearest_interpolation(
                    temp_sorted, output_sorted, target_temp
                )

        except Exception as e:
            logging.error(f"Interpolation failed: {e}")
            return None
    
    @staticmethod
    def _linear_interpolation(temps: np.ndarray, outputs: np.ndarray, target: float) -> float:
        return float(np.interp(target, temps[::-1], outputs[::-1]))

    @staticmethod
    def _cubic_interpolation(temps: np.ndarray, outputs: np.ndarray, target: float) -> float:
        if len(temps) < 4:
            return InterpolationEngine._linear_interpolation(temps, outputs, target)

        f = interpolate.interp1d(temps, outputs, kind='cubic', bounds_error=False)
        result = f(target)
        return float(result) if not np.isnan(result) else None

    @staticmethod
    def _quadratic_interpolation(temps: np.ndarray, outputs: np.ndarray, target: float) -> float:
        if len(temps) < 3:
            return InterpolationEngine._linear_interpolation(temps, outputs, target)

        f = interpolate.interp1d(temps, outputs, kind='quadratic', bounds_error=False)
        result = f(target)
        return float(result) if not np.isnan(result) else None

    @staticmethod
    def _nearest_interpolation(temps: np.ndarray, outputs: np.ndarray, target: float) -> float:
        idx = np.argmin(np.abs(temps - target))
        return float(outputs[idx])

    @staticmethod
    def _handle_extrapolation(temps: np.ndarray, outputs: np.ndarray, target: float) -> Optional[float]:
        """Handle cases where the target temperature is outside the data range."""
        if target > temps[0]:  # Target hotter than the entire cloud
            return None  # Cannot extrapolate beyond dispersion cloud
        else:  # Target colder than the entire cloud
            return float(outputs[-1])  # Output at the furthest (coldest) point 