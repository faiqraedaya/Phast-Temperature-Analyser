import numpy as np
from scipy import interpolate
import logging
from typing import List, Optional, Sequence, Tuple

from phast_temperature_analyser.core.types import InterpolationMethod, WorstCase


class InterpolationEngine:
    """Handles different interpolation methods for dispersion data.

    Reads off an output quantity (e.g. downwind distance or concentration)
    at a target temperature, by interpolating against the centreline
    temperature profile of the dispersion cloud.

    Real profiles are often non-monotonic: the centreline temperature can
    rise and fall along the cloud, so the temperature of interest may be
    reached several times. Every crossing is located and the worst-case one
    is reported (maximum distance or minimum concentration).

    Crossings are located one profile segment at a time. A segment whose two
    ends straddle the target holds exactly one crossing, so the temperature
    column never has to be deduplicated: rows where the temperature holds
    flat straddle nothing and are passed over, which leaves each crossing
    anchored to the end of the plateau it actually departs from.

    Where the cloud warms so abruptly that the model steps straight past the
    temperature of interest — say -99 °C at 0 m and 17 °C at 1 m — the
    crossing could sit anywhere in that segment. ``max_temperature_step``
    discards such crossings rather than inventing a distance the output does
    not resolve.
    """

    # Points the higher-order methods fit through, the two straddling the
    # target included.
    _STENCIL_SIZE = {
        InterpolationMethod.CUBIC: 4,
        InterpolationMethod.QUADRATIC: 3,
    }
    _SPLINE_KIND = {
        InterpolationMethod.CUBIC: 'cubic',
        InterpolationMethod.QUADRATIC: 'quadratic',
    }

    @staticmethod
    def interpolate(
        temperatures: np.ndarray,
        outputs: np.ndarray,
        target_temp: float,
        method: InterpolationMethod,
        worst_case: WorstCase = WorstCase.MAXIMUM,
        max_temperature_step: Optional[float] = None,
    ) -> Optional[float]:
        """
        Interpolate an output quantity at a target temperature.

        Args:
            temperatures: Array of centreline temperatures, in downwind
                (profile) order — must stay paired with ``outputs``
            outputs: Array of the quantity to read off (distance or concentration)
            target_temp: Temperature of interest to interpolate at
            method: Interpolation method to use
            worst_case: Extreme to report when the target temperature is
                reached more than once (MAXIMUM for distance, MINIMUM for
                concentration)
            max_temperature_step: Widest temperature step, in °C, a crossing
                may be interpolated across; crossings that only occur inside
                coarser steps are treated as unresolved and dropped. None
                disables the check.

        Returns:
            Worst-case interpolated output value, or None if the cloud never
            reaches the target temperature, no crossing is resolved finely
            enough, or the profile is unusable
        """
        try:
            found = InterpolationEngine.crossings(
                temperatures, [outputs], target_temp, method, max_temperature_step
            )
            values = [c[0] for c in found if not np.isnan(c[0])]
            # Without a crossing the target sits outside the span of
            # temperatures the cloud ever takes — whether hotter than the
            # cloud gets or colder than it ever is — so the temperature of
            # interest is simply never reached and there is nothing to report.
            if not values:
                return None

            worst = max(values) if worst_case == WorstCase.MAXIMUM else min(values)
            return float(worst)

        except Exception as e:
            logging.error(f"Interpolation failed: {e}")
            return None

    @staticmethod
    def crossings(
        temperatures: np.ndarray,
        outputs: Sequence[np.ndarray],
        target_temp: float,
        method: InterpolationMethod,
        max_temperature_step: Optional[float] = None,
    ) -> List[Tuple[float, ...]]:
        """Every point along the cloud that reaches the target temperature.

        ``outputs`` is a sequence of arrays read off together. Each crossing
        comes back as one tuple holding every output at that same point, so a
        downwind distance and the concentration beside it always describe the
        same place on the cloud. Reducing the outputs separately — furthest
        distance from one crossing, lowest concentration from another — would
        pair values that never occur together.

        Rows sitting exactly on the target count directly (this also covers
        plateaus); every segment whose ends straddle the target contributes one
        interpolated crossing, unless the step across it is too coarse to place
        that crossing. An output that cannot be read at a crossing comes back
        as NaN there, leaving the other outputs usable.
        """
        temps = np.asarray(temperatures, dtype=float)
        outs = [np.asarray(o, dtype=float) for o in outputs]
        # Only the temperature decides where the crossings are, so a row is
        # unusable only when its temperature is missing. Dropping rows for a
        # missing output would shift the crossings of every other output.
        valid = ~np.isnan(temps)
        temps = temps[valid]
        outs = [o[valid] for o in outs]
        if len(temps) < 2:
            return []

        found = [
            tuple(float(o[i]) for o in outs)
            for i in np.flatnonzero(temps == target_temp)
        ]

        for i in range(len(temps) - 1):
            lo = min(temps[i], temps[i + 1])
            hi = max(temps[i], temps[i + 1])
            if not lo < target_temp < hi:
                continue  # exact hits are already collected above
            if max_temperature_step is not None and hi - lo > max_temperature_step:
                # The profile jumps clean over the target here, so the crossing
                # could sit anywhere across the segment. Reporting it would
                # invent precision the dispersion output does not carry.
                continue
            values = []
            for o in outs:
                value = InterpolationEngine._interpolate_segment(
                    temps, o, i, target_temp, method
                )
                values.append(float('nan') if value is None else value)
            found.append(tuple(values))

        return found

    @staticmethod
    def is_unresolved(
        temperatures: np.ndarray,
        target_temp: float,
        max_temperature_step: Optional[float],
    ) -> bool:
        """Whether the target is reached, but only across steps too coarse to resolve.

        Separates a reading suppressed by ``max_temperature_step`` from one the
        cloud simply never reaches. Both report no value, but only the former
        is worth telling the user about.
        """
        if max_temperature_step is None:
            return False
        temps = np.asarray(temperatures, dtype=float)
        temps = temps[~np.isnan(temps)]
        if len(temps) < 2:
            return False

        if bool(np.any(temps == target_temp)):
            return False  # a row sits on the target; nothing had to be interpolated

        reached = False
        for i in range(len(temps) - 1):
            lo = min(temps[i], temps[i + 1])
            hi = max(temps[i], temps[i + 1])
            if not lo < target_temp < hi:
                continue
            reached = True
            if hi - lo <= max_temperature_step:
                return False  # at least one crossing is resolved finely enough
        return reached

    @staticmethod
    def _interpolate_segment(
        temps: np.ndarray, outs: np.ndarray, i: int, target: float,
        method: InterpolationMethod,
    ) -> Optional[float]:
        """Interpolate the output across the segment from index ``i`` to ``i + 1``.

        The segment's ends straddle the target, so the crossing lies between
        ``outs[i]`` and ``outs[i + 1]``; the higher-order fits are held to that
        range, since an overshooting spline must not place the crossing
        outside the very segment that contains it.
        """
        if method == InterpolationMethod.NEAREST:
            # Nearest-neighbour interpolation of this crossing: snap it to
            # whichever of the two bounding rows is closer in temperature,
            # rather than reading between them.
            nearer = i if abs(temps[i] - target) <= abs(temps[i + 1] - target) else i + 1
            return float(outs[nearer])

        kind = InterpolationEngine._SPLINE_KIND.get(method)
        if kind is not None:
            size = InterpolationEngine._STENCIL_SIZE[method]
            stencil = InterpolationEngine._stencil(temps, i, size)
            if len(stencil) >= size:
                x, y = temps[stencil], outs[stencil]
                if x[0] > x[-1]:  # orient ascending for the interpolator
                    x, y = x[::-1], y[::-1]
                f = interpolate.interp1d(x, y, kind=kind, bounds_error=False)
                value = float(f(target))
                if not np.isnan(value):
                    low, high = sorted((float(outs[i]), float(outs[i + 1])))
                    return min(max(value, low), high)
            # Too few usable points around this segment: fall back to linear.

        fraction = (target - temps[i]) / (temps[i + 1] - temps[i])
        return float(outs[i] + fraction * (outs[i + 1] - outs[i]))

    @staticmethod
    def _stencil(temps: np.ndarray, i: int, size: int) -> List[int]:
        """Indices of up to ``size`` profile points around segment ``i``..``i + 1``.

        Grows outwards from the segment, alternating downwind and upwind, and
        stops at the turning points bounding the segment's monotonic stretch —
        past those the profile folds back and the output stops being a
        function of temperature. Returned in profile order, with strictly
        monotonic temperatures as the interpolators require.
        """
        indices = [i, i + 1]
        rising = bool(temps[i + 1] > temps[i])

        while len(indices) < size:
            grew = False
            following = InterpolationEngine._next_outward(temps, indices[-1], 1, rising)
            if following is not None:
                indices.append(following)
                grew = True
            if len(indices) < size:
                preceding = InterpolationEngine._next_outward(temps, indices[0], -1, rising)
                if preceding is not None:
                    indices.insert(0, preceding)
                    grew = True
            if not grew:
                break

        return indices

    @staticmethod
    def _next_outward(
        temps: np.ndarray, index: int, step: int, rising: bool,
    ) -> Optional[int]:
        """Next index beyond ``index`` whose temperature carries the run onwards.

        Returns None at a turning point or at the end of the profile. Rows
        repeating the temperature at ``index`` are stepped over: a repeated
        temperature cannot be handed to the interpolators, and the row already
        in the stencil is the one nearest the crossing.
        """
        wants_warmer = rising if step > 0 else not rising
        j = index + step
        while 0 <= j < len(temps):
            difference = temps[j] - temps[index]
            if difference == 0:
                j += step
                continue
            return j if (difference > 0) == wants_warmer else None
        return None
