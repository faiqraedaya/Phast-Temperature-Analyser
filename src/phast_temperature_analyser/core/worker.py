import logging
import numpy as np
from typing import Dict, Any, List
from PySide6.QtCore import QThread, Signal

from phast_temperature_analyser.core.types import TemperatureType, InterpolationMethod, AnalysisResult
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
            
            for i, data_item in enumerate(raw_data):
                try:
                    distance = InterpolationEngine.interpolate(
                        np.array(data_item['temperatures']),
                        np.array(data_item['distances']),
                        self.config['temperature_of_interest'],
                        InterpolationMethod(self.config['interpolation_method'])
                    )
                    
                    if distance is not None:
                        result = AnalysisResult(
                            subsection=data_item['equipment_item'],
                            scenario=data_item['scenario'],
                            weather=data_item['weather'],
                            downwind_distance=distance,
                            interpolation_method=self.config['interpolation_method'],
                            temperature_of_interest=self.config['temperature_of_interest']
                        )
                        results.append(result)
                    
                    progress = int((i + 1) / total_items * 100)
                    self.progress_updated.emit(progress)
                    
                except Exception as e:
                    logging.error(f"Error processing data item: {e}")
                    continue
            
            self.analysis_completed.emit(results)
            
        except Exception as e:
            self.error_occurred.emit(str(e)) 