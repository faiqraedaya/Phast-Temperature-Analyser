import logging
import numpy as np
from typing import Dict, Any, List, Tuple
from PySide6.QtCore import QThread, Signal

from phast_temperature_analyser.core.types import (
    TemperatureType, InterpolationMethod, AnalysisResult, TemperatureReading,
    ConcentrationBasis
)
from phast_temperature_analyser.core.excel_processor import ExcelProcessor
from phast_temperature_analyser.core.interpolation import InterpolationEngine


class AnalysisWorker(QThread):
    """Worker thread for performing analysis without blocking the GUI."""
    
    progress_updated = Signal(int)
    status_updated = Signal(str)
    analysis_completed = Signal(list)
    error_occurred = Signal(str)
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
    
    def run(self):
        try:
            self.status_updated.emit("Initializing analysis...")
            
            processor = ExcelProcessor(
                TemperatureType(self.config['temperature_type'])
            )
            
            self.status_updated.emit("Processing Excel files...")

            # Parsing is the slow phase, so it drives the first 90% of the bar.
            def on_parse_progress(files_done: int, total_files: int):
                if total_files:
                    self.progress_updated.emit(int(files_done / total_files * 90))

            raw_data = processor.process_files(
                self.config['input_folder'], progress_callback=on_parse_progress
            )
            
            if not raw_data:
                self.error_occurred.emit("No valid data found in Excel files")
                return
            
            self.status_updated.emit("Performing interpolation analysis...")
            results = []
            total_items = len(raw_data)
            
            method = InterpolationMethod(self.config['interpolation_method'])
            # Normalise the requested temperatures: de-duplicate and sort ascending
            target_temps = sorted(set(self.config['temperatures_of_interest']))
            analyse_distance = self.config['analyse_distance']
            analyse_concentration = self.config['analyse_concentration']
            analyse_minimum_temperature = self.config.get(
                'analyse_minimum_temperature', False)
            ignore_weathers = self.config.get('ignore_weathers', False)
            # None disables the check; otherwise the widest temperature step a
            # crossing may be interpolated across.
            max_temperature_step = self.config.get('max_temperature_step')
            # None disables the check; otherwise how far downwind the
            # temperature of interest must be reached to count.
            min_downwind_distance = self.config.get('min_downwind_distance')
            # Which concentration stands beside the reported distance.
            concentration_basis = ConcentrationBasis(
                self.config.get('concentration_basis', ConcentrationBasis.MAXIMUM.value)
            )
            # Restrict each dispersion table to the observer PHAST lists first
            # — for a catastrophic rupture that is the initial release, before
            # the pool starts feeding later parcels.
            first_observer_only = self.config.get('first_observer_only', False)
            decimal_places = self.config.get('decimal_places', 2)
            unresolved_readings = 0
            near_field_readings = 0

            if first_observer_only:
                logging.info(
                    "Analysing only the first observer of each dispersion table"
                )

            for i, data_item in enumerate(raw_data):
                try:
                    # A time-varying release is reported as several observers.
                    # They are alternative realisations of the same scenario
                    # rather than separate hazards, so each is read off on its
                    # own profile and the worst case across them is kept.
                    observers = data_item['profiles']
                    if first_observer_only:
                        observers = observers[:1]
                    profiles = [
                        (np.array(p['temperatures']), np.array(p['distances']),
                         np.array(p['concentrations']))
                        for p in observers
                    ]

                    # The coldest the cloud gets anywhere, usually at the
                    # source but not always, so the whole profile is scanned.
                    minimum_temperature = None
                    if analyse_minimum_temperature:
                        coldest = [
                            float(np.nanmin(temperatures))
                            for temperatures, _, _ in profiles
                            if len(temperatures) and not np.all(np.isnan(temperatures))
                        ]
                        minimum_temperature = min(coldest) if coldest else None

                    readings = []
                    for target_temp in target_temps:
                        # Each enabled quantity is read off at the temperature of
                        # interest; non-monotonic profiles can reach it several
                        # times, so ask for the worst-case extent of each.
                        # Distance and concentration are read off together at
                        # every crossing, so the pair kept below is a real point
                        # on the cloud rather than two extremes picked from
                        # different places.
                        found = []
                        unresolved_anywhere = False

                        for temperatures, distances, concentrations in profiles:
                            found.extend(
                                pair for pair in InterpolationEngine.crossings(
                                    temperatures, [distances, concentrations],
                                    target_temp, method, max_temperature_step,
                                )
                                if not np.isnan(pair[0])
                            )
                            if InterpolationEngine.is_unresolved(
                                temperatures, target_temp, max_temperature_step
                            ):
                                unresolved_anywhere = True

                        # The furthest crossing is the extent of the temperature
                        # of interest. Which concentration goes beside it is the
                        # user's call: the worst one anywhere that temperature
                        # occurs, or the one at that same point.
                        if found:
                            worst_distance, at_furthest = max(
                                found, key=lambda pair: pair[0]
                            )
                            if concentration_basis == ConcentrationBasis.MAXIMUM:
                                seen = [c for _, c in found if not np.isnan(c)]
                                worst_concentration = max(seen) if seen else None
                            else:
                                worst_concentration = (
                                    None if np.isnan(at_furthest) else at_furthest
                                )
                        else:
                            worst_distance = worst_concentration = None
                        if not analyse_concentration:
                            worst_concentration = None

                        # The furthest crossing is the whole extent of the
                        # temperature of interest, so if even that sits inside
                        # the near field the reading describes the release
                        # rather than the dispersing cloud, and the
                        # concentration read off it goes with it.
                        near_field = (
                            min_downwind_distance is not None
                            and worst_distance is not None
                            and worst_distance < min_downwind_distance
                        )
                        if near_field:
                            worst_distance = worst_concentration = None
                            near_field_readings += 1

                        reading = TemperatureReading(
                            temperature_of_interest=target_temp,
                            downwind_distance=worst_distance if analyse_distance else None,
                            concentration=worst_concentration,
                        )
                        # Only count the reading as unresolved when no observer
                        # resolved it; one that did leaves the reading intact.
                        if (reading.downwind_distance is None
                                and reading.concentration is None
                                and unresolved_anywhere
                                and not near_field):
                            unresolved_readings += 1

                        readings.append(reading)

                    summary = self._format_readings(
                        readings, analyse_distance, analyse_concentration,
                        decimal_places,
                    )
                    if minimum_temperature is not None:
                        coldest_text = f"min {minimum_temperature:.{decimal_places}f} °C"
                        summary = f"{summary}; {coldest_text}" if summary else coldest_text
                    logging.info(
                        f"{data_item['equipment_item']} | {data_item['scenario']} | "
                        f"{data_item['weather']}: {summary}"
                    )

                    # A leak earns its row on distance or concentration; the
                    # minimum temperature rides along rather than reviving a
                    # row the filters removed. Only when it is the sole
                    # quantity asked for does it decide retention itself.
                    if analyse_distance or analyse_concentration:
                        keep = any(r.downwind_distance is not None
                                   or r.concentration is not None
                                   for r in readings)
                    else:
                        keep = minimum_temperature is not None
                    if keep:
                        results.append(AnalysisResult(
                            subsection=data_item['equipment_item'],
                            scenario=data_item['scenario'],
                            weather=data_item['weather'],
                            interpolation_method=self.config['interpolation_method'],
                            readings=readings,
                            minimum_temperature=minimum_temperature,
                        ))

                    # Interpolation fills the remaining 90 -> 100% of the bar.
                    progress = 90 + int((i + 1) / total_items * 10)
                    self.progress_updated.emit(progress)

                except Exception as e:
                    logging.error(f"Error processing data item: {e}")
                    continue
            
            # Surface these: they are the user's cue that a threshold may be
            # cutting into readings they wanted to keep.
            if unresolved_readings:
                logging.info(
                    f"Discarded {unresolved_readings} reading(s) where the cloud "
                    f"warmed past the temperature of interest in a single step "
                    f"wider than {max_temperature_step:g} °C"
                )
            if near_field_readings:
                logging.info(
                    f"Discarded {near_field_readings} reading(s) where the "
                    f"temperature of interest was reached within "
                    f"{min_downwind_distance:g} m of the source"
                )

            if ignore_weathers and results:
                self.status_updated.emit("Combining weathers into worst-case results...")
                results = self._combine_weathers(results, concentration_basis)

            self.analysis_completed.emit(results)
            self.status_updated.emit("Analysis completed successfully.")

        except Exception as e:
            self.error_occurred.emit(str(e))

    @staticmethod
    def _format_readings(
        readings: List[TemperatureReading],
        analyse_distance: bool,
        analyse_concentration: bool,
        decimal_places: int,
    ) -> str:
        """Summarise an item's readings on one line for the log.

        Only the quantities being analysed are shown, at the same precision as
        the exported workbook. A temperature of interest with nothing to report
        — never reached, or discarded by one of the filters — is called out
        rather than left blank, so the line still accounts for every one.
        """
        parts = []
        for reading in readings:
            values = []
            if analyse_distance and reading.downwind_distance is not None:
                values.append(f"{reading.downwind_distance:.{decimal_places}f} m")
            if analyse_concentration and reading.concentration is not None:
                values.append(f"{reading.concentration:.{decimal_places}f} ppm")
            parts.append(
                f"{reading.temperature_of_interest:g} °C: "
                + (" / ".join(values) if values else "no result")
            )
        return "; ".join(parts)

    @staticmethod
    def _combine_weathers(
        results: List[AnalysisResult],
        concentration_basis: ConcentrationBasis = ConcentrationBasis.MAXIMUM,
    ) -> List[AnalysisResult]:
        """Collapse the weather dimension of the results.

        Produces one result per subsection/scenario, keeping the weather that
        reaches each temperature of interest furthest downwind, along with the
        concentration that weather gives there. Taking the furthest distance
        and the lowest concentration separately would report a pair belonging
        to no single weather.
        """
        grouped: Dict[Tuple[str, str], List[AnalysisResult]] = {}
        for result in results:
            grouped.setdefault((result.subsection, result.scenario), []).append(result)

        combined = []
        for (subsection, scenario), group in grouped.items():
            readings = []
            # Every result carries one reading per temperature of interest, in
            # the same order, so zip pairs up readings at the same temperature.
            for readings_at_temp in zip(*(r.readings for r in group)):
                reached = [r for r in readings_at_temp if r.downwind_distance is not None]
                concentrations = [r.concentration for r in readings_at_temp
                                  if r.concentration is not None]
                highest = max(concentrations) if concentrations else None
                if reached:
                    governing = max(reached, key=lambda r: r.downwind_distance)
                    distance = governing.downwind_distance
                    concentration = (
                        highest if concentration_basis == ConcentrationBasis.MAXIMUM
                        else governing.concentration
                    )
                else:
                    # No distance to pick a governing weather by — only
                    # concentration is being reported — so take the worst of it.
                    distance = None
                    concentration = highest
                readings.append(TemperatureReading(
                    temperature_of_interest=readings_at_temp[0].temperature_of_interest,
                    downwind_distance=distance,
                    concentration=concentration,
                ))

            coldest = [r.minimum_temperature for r in group
                       if r.minimum_temperature is not None]
            weathers = {r.weather for r in group}
            combined.append(AnalysisResult(
                subsection=subsection,
                scenario=scenario,
                weather=(next(iter(weathers)) if len(weathers) == 1
                         else f"Worst case of {len(weathers)} weathers"),
                interpolation_method=group[0].interpolation_method,
                readings=readings,
                minimum_temperature=min(coldest) if coldest else None,
            ))
        return combined 