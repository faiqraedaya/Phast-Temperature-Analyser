import logging
from pathlib import Path
from typing import List, Dict, Any, Callable, Iterable, Optional, Tuple
import openpyxl

from phast_temperature_analyser.core.types import TemperatureType

TITLE = "Time-varying Observer Dispersion Data (before along-wind-diffusion effects)"
DISTANCE_HEADER = "Downwind distance [m]"
CONCENTRATION_HEADER = "C/Line conc [ppm]"


class ExcelProcessor:
    """Handles Excel file processing and data extraction."""

    def __init__(self, temperature_type: TemperatureType):
        self.temperature_type = temperature_type
        self.logger = logging.getLogger(__name__)
        self.temp_header = (
            "C/Line vapour temperature [degC]"
            if temperature_type == TemperatureType.VAPOUR
            else "C/Line liquid temperature [degC]"
        )

    def process_files(
        self,
        folder_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Process all Excel files in the given folder.

        ``progress_callback`` is invoked as ``(files_done, total_files)`` after
        each file so callers can report parse-phase progress.
        """
        # Skip Excel's owner-lock files (~$Report.xlsx), which appear while a
        # report is open and are not readable reports themselves.
        excel_files = [
            path for path in Path(folder_path).glob("*.xlsx")
            if not path.name.startswith("~$")
        ]
        total = len(excel_files)
        all_data = []

        for index, file_path in enumerate(excel_files):
            try:
                file_data = self._process_single_file(file_path)
                all_data.extend(file_data)
            except Exception as e:
                self.logger.error(f"Error processing {file_path}: {e}")
            if progress_callback:
                progress_callback(index + 1, total)

        return all_data

    def _process_single_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Process a single Excel file."""
        # read_only streams rows instead of building the full in-memory cell
        # model, which is dramatically faster for the large dispersion reports.
        wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
        file_data = []

        self.logger.info(f"Processing file: {file_path}")

        try:
            for ws in wb.worksheets:
                file_data.extend(self._analyze_sheet(ws.iter_rows(values_only=True)))
        finally:
            wb.close()

        return file_data

    def _analyze_sheet(self, rows: Iterable[Tuple]) -> List[Dict[str, Any]]:
        """Analyze a worksheet's rows in a single sequential pass.

        The reports interleave metadata (equipment/scenario/weather) with one or
        more dispersion-data tables. We walk the rows once, tracking the most
        recent metadata and collecting each table's rows until it ends.
        """
        sheet_data: List[Dict[str, Any]] = []
        equipment_item = scenario = weather = None

        # 'search' -> scanning for metadata/title
        # 'await_header' -> title seen, header row is two rows below it
        # 'collect' -> reading numeric data rows
        state = "search"
        header_countdown = 0
        distance_col = temp_col = concentration_col = None
        distances: List[float] = []
        temperatures: List[float] = []
        concentrations: List[Optional[float]] = []

        def flush():
            if not (distances and temperatures and equipment_item and scenario and weather):
                return
            profiles = []
            for start, end in ExcelProcessor._observer_spans(distances):
                if end - start < 2:
                    continue  # a lone point cannot carry a crossing
                profiles.append({
                    "distances": distances[start:end],
                    "concentrations": concentrations[start:end],
                    "temperatures": temperatures[start:end],
                })
            if not profiles:
                return
            if len(profiles) > 1:
                self.logger.info(
                    f"{equipment_item} | {scenario} | {weather}: dispersion table "
                    f"holds {len(profiles)} observer profiles"
                )
            sheet_data.append({
                "equipment_item": equipment_item,
                "scenario": scenario,
                "weather": weather,
                "profiles": profiles,
            })

        for values in rows:
            if not values:
                continue

            if state == "collect":
                distance = values[distance_col] if distance_col < len(values) else None
                if isinstance(distance, (int, float)) and not isinstance(distance, bool):
                    self._append_point(
                        values, distance_col, temp_col, concentration_col,
                        distances, temperatures, concentrations,
                    )
                    continue
                # Non-numeric distance marks the end of the table.
                flush()
                distances, temperatures, concentrations = [], [], []
                state = "search"
                # fall through so this row can still be scanned for metadata

            if state == "await_header":
                header_countdown -= 1
                if header_countdown == 0:
                    headers = list(values)
                    distance_col = (
                        headers.index(DISTANCE_HEADER)
                        if DISTANCE_HEADER in headers else None
                    )
                    temp_col = (
                        headers.index(self.temp_header)
                        if self.temp_header in headers else None
                    )
                    if distance_col is None or temp_col is None:
                        # This table lacks a column the analysis needs — most
                        # often a liquid temperature the report does not carry.
                        # Abandon it and keep scanning; other tables in the same
                        # file may still be usable.
                        self.logger.info(
                            f"Skipping a dispersion table without a "
                            f"'{DISTANCE_HEADER}' and '{self.temp_header}' column"
                        )
                        state = "search"
                        continue
                    # Concentration is optional: not every report contains it.
                    concentration_col = (
                        headers.index(CONCENTRATION_HEADER)
                        if CONCENTRATION_HEADER in headers else None
                    )
                    distances, temperatures, concentrations = [], [], []
                    state = "collect"
                continue

            # state == "search": look for metadata and the table title.
            for v in values:
                if not isinstance(v, str):
                    continue
                s = v.strip()
                if s.startswith("Equipment Item:"):
                    equipment_item = s.split(":", 1)[1].strip()
                elif s.startswith("Scenario ("):
                    scenario = s.split(":", 1)[1].strip()
                elif s.startswith("Weather:"):
                    weather = s.split(":", 1)[1].strip()
                elif s == TITLE:
                    # Header sits two rows below the title; data follows it.
                    state = "await_header"
                    header_countdown = 2

        # Flush a table that runs to the end of the sheet.
        if state == "collect":
            flush()

        return sheet_data

    @staticmethod
    def _observer_spans(distances: List[float]) -> List[Tuple[int, int]]:
        """Split one dispersion table into a span per observer.

        A time-varying release is reported as several observers — parcels
        leaving the source at different times — whose profiles are
        concatenated into a single table with no separator row and no observer
        column. Each one restarts at the source, so a downwind distance that
        steps backwards marks where the next observer begins; along any one
        cloud the distance only ever advances.

        Left joined, that seam reads as a single segment running tens of
        kilometres upwind across the cloud's whole temperature range, and it
        straddles almost any temperature of interest. The crossing read off it
        is fictitious and, being far the furthest downwind, wins the worst case
        outright.

        Returns half-open (start, end) index pairs.
        """
        boundaries = [0]
        boundaries.extend(
            i for i in range(1, len(distances)) if distances[i] < distances[i - 1]
        )
        boundaries.append(len(distances))
        return [(boundaries[k], boundaries[k + 1]) for k in range(len(boundaries) - 1)]

    @staticmethod
    def _append_point(values, distance_col, temp_col, concentration_col,
                      distances, temperatures, concentrations) -> None:
        """Parse and append one numeric data row (skipping unparseable rows)."""
        temperature = values[temp_col] if temp_col < len(values) else None
        if temperature is None:
            return
        concentration = (
            values[concentration_col]
            if concentration_col is not None and concentration_col < len(values)
            else None
        )
        try:
            temp_value = float(temperature)
            conc_value = float(concentration) if concentration is not None else None
            dist_value = float(values[distance_col])
        except (ValueError, TypeError):
            return
        distances.append(dist_value)
        temperatures.append(temp_value)
        concentrations.append(conc_value)
