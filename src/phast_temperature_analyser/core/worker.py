import logging
import numpy as np
from typing import Dict, Any, List
from PySide6.QtCore import QThread, Signal

from phast_temperature_analyser.core.types import (
    TemperatureType, InterpolationMethod, AnalysisResult, TemperatureReading
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
                TemperatureType(self.config['temperature_type']),
                self.config['verbose']
            )
            
            self.status_updated.emit("Processing Excel files...")
            raw_data = processor.process_files(self.config['input_folder'])
            
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

            for i, data_item in enumerate(raw_data):
                try:
                    temperatures = np.array(data_item['temperatures'])
                    distances = np.array(data_item['distances'])
                    concentrations = np.array(data_item['concentrations'])

                    readings = []
                    for target_temp in target_temps:
                        # Each enabled quantity is read off at the temperature of interest
                        distance = InterpolationEngine.interpolate(
                            temperatures, distances, target_temp, method
                        ) if analyse_distance else None

                        concentration = InterpolationEngine.interpolate(
                            temperatures, concentrations, target_temp, method
                        ) if analyse_concentration else None

                        readings.append(TemperatureReading(
                            temperature_of_interest=target_temp,
                            downwind_distance=distance,
                            concentration=concentration
                        ))

                    # Keep the item only if at least one reading produced a value
                    if any(r.downwind_distance is not None or r.concentration is not None
                           for r in readings):
                        results.append(AnalysisResult(
                            subsection=data_item['equipment_item'],
                            scenario=data_item['scenario'],
                            weather=data_item['weather'],
                            interpolation_method=self.config['interpolation_method'],
                            readings=readings
                        ))

                    progress = int((i + 1) / total_items * 100)
                    self.progress_updated.emit(progress)

                except Exception as e:
                    logging.error(f"Error processing data item: {e}")
                    continue
            
            self.analysis_completed.emit(results)
            
        except Exception as e:
            self.error_occurred.emit(str(e)) 