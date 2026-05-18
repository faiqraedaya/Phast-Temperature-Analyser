import numpy as np
from scipy import interpolate
import logging
from typing import Optional

from phast_temperature_analyser.core.types import InterpolationMethod


class InterpolationEngine:
    """Handles different interpolation methods for temperature-distance data."""
    
    @staticmethod
    def interpolate(
        temperatures: np.ndarray,
        distances: np.ndarray,
        target_temp: float,
        method: InterpolationMethod
    ) -> Optional[float]:
        """
        Interpolate downwind distance for target temperature.
        
        Args:
            temperatures: Array of temperature values
            distances: Array of corresponding distance values
            target_temp: Target temperature for interpolation
            method: Interpolation method to use
            
        Returns:
            Interpolated distance or None if interpolation fails
        """
        try:
            if len(temperatures) < 2 or len(distances) < 2:
                return None
                
            # Ensure arrays are sorted by temperature (descending for dispersion)
            sorted_indices = np.argsort(temperatures)[::-1]
            temp_sorted = temperatures[sorted_indices]
            dist_sorted = distances[sorted_indices]
            
            # Check if target temperature is within range
            if target_temp > temp_sorted[0] or target_temp < temp_sorted[-1]:
                return InterpolationEngine._handle_extrapolation(
                    temp_sorted, dist_sorted, target_temp
                )
            
            if method == InterpolationMethod.LINEAR:
                return InterpolationEngine._linear_interpolation(
                    temp_sorted, dist_sorted, target_temp
                )
            elif method == InterpolationMethod.CUBIC:
                return InterpolationEngine._cubic_interpolation(
                    temp_sorted, dist_sorted, target_temp
                )
            elif method == InterpolationMethod.QUADRATIC:
                return InterpolationEngine._quadratic_interpolation(
                    temp_sorted, dist_sorted, target_temp
                )
            elif method == InterpolationMethod.NEAREST:
                return InterpolationEngine._nearest_interpolation(
                    temp_sorted, dist_sorted, target_temp
                )
                
        except Exception as e:
            logging.error(f"Interpolation failed: {e}")
            return None
    
    @staticmethod
    def _linear_interpolation(temps: np.ndarray, dists: np.ndarray, target: float) -> float:
        return float(np.interp(target, temps[::-1], dists[::-1]))
    
    @staticmethod
    def _cubic_interpolation(temps: np.ndarray, dists: np.ndarray, target: float) -> float:
        if len(temps) < 4:
            return InterpolationEngine._linear_interpolation(temps, dists, target)
        
        f = interpolate.interp1d(temps, dists, kind='cubic', bounds_error=False)
        result = f(target)
        return float(result) if not np.isnan(result) else None
    
    @staticmethod
    def _quadratic_interpolation(temps: np.ndarray, dists: np.ndarray, target: float) -> float:
        if len(temps) < 3:
            return InterpolationEngine._linear_interpolation(temps, dists, target)
        
        f = interpolate.interp1d(temps, dists, kind='quadratic', bounds_error=False)
        result = f(target)
        return float(result) if not np.isnan(result) else None
    
    @staticmethod
    def _nearest_interpolation(temps: np.ndarray, dists: np.ndarray, target: float) -> float:
        idx = np.argmin(np.abs(temps - target))
        return float(dists[idx])
    
    @staticmethod
    def _handle_extrapolation(temps: np.ndarray, dists: np.ndarray, target: float) -> Optional[float]:
        """Handle cases where target temperature is outside the data range."""
        if target > temps[0]:  # Target higher than all temperatures
            return None  # Cannot extrapolate beyond dispersion cloud
        else:  # Target lower than all temperatures
            return float(dists[-1])  # Return maximum distance 