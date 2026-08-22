import logging
from typing import List, Optional

import pandas as pd

from phast_temperature_analyser.core.types import AnalysisResult


class ResultsExporter:
    """Builds the wide-format results table and writes it to an Excel workbook.

    One row per analysed item, with a distance and/or concentration column for
    each temperature of interest, depending on which quantities were enabled.
    """

    SHEET_NAME = "Analysis Results"

    def __init__(
        self,
        decimal_places: int = 2,
        include_distance: bool = True,
        include_concentration: bool = True,
        concentration_basis: Optional[str] = None,
        include_minimum_temperature: bool = False,
    ):
        self.decimal_places = decimal_places
        self.include_distance = include_distance
        self.include_concentration = include_concentration
        self.concentration_basis = concentration_basis
        self.include_minimum_temperature = include_minimum_temperature
        self.logger = logging.getLogger(__name__)

    def export(self, results: List[AnalysisResult], output_file: str) -> None:
        """Build the results table and write it to ``output_file``."""
        if not results:
            raise ValueError("No results to export")

        df = self.build_dataframe(results)
        self._write_workbook(df, output_file)

    def build_dataframe(self, results: List[AnalysisResult]) -> pd.DataFrame:
        """Convert analysis results into a wide-format DataFrame."""
        rows = []
        for result in results:
            row = {
                'Subsection': result.subsection,
                'Scenario': result.scenario,
                'Weather': result.weather,
            }
            # A property of the cloud, not of any temperature of interest,
            # so it sits with the identifying columns rather than the
            # per-temperature ones.
            if self.include_minimum_temperature:
                row['Minimum Temperature (°C)'] = self._round(
                    result.minimum_temperature)
            # Group all distances first, then all concentrations, so columns read
            # Distance@T1..Tx, then Conc@T1..Tx (rather than interleaved per temp).
            if self.include_distance:
                for reading in result.readings:
                    temp = f"{reading.temperature_of_interest:g}"
                    row[f'Downwind Distance at {temp}°C (m)'] = self._round(reading.downwind_distance)
            if self.include_concentration:
                for reading in result.readings:
                    temp = f"{reading.temperature_of_interest:g}"
                    row[f'Concentration at {temp}°C (ppm)'] = self._round(reading.concentration)
            # Record which concentration the numbers are, so the basis
            # travels with them rather than living only in the settings.
            if self.include_concentration and self.concentration_basis:
                row['Concentration Basis'] = self.concentration_basis
            row['Interpolation Method'] = result.interpolation_method
            rows.append(row)

        return pd.DataFrame(rows)

    def _round(self, value: Optional[float]) -> Optional[float]:
        return round(value, self.decimal_places) if value is not None else None

    @classmethod
    def _write_workbook(cls, df: pd.DataFrame, output_file: str) -> None:
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=cls.SHEET_NAME, index=False)

            # Auto-adjust column widths
            worksheet = writer.sheets[cls.SHEET_NAME]
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except Exception:
                        pass
                worksheet.column_dimensions[column_letter].width = min(max_length + 2, 50)
