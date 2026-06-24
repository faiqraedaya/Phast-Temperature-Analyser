import os
import logging
import pandas as pd
from typing import List
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox,
    QProgressBar, QTextEdit, QFileDialog, QMessageBox, QGroupBox,
    QSpinBox, QDoubleSpinBox, QTabWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from phast_temperature_analyser.core.types import TemperatureType, InterpolationMethod, AnalysisResult
from phast_temperature_analyser.core.worker import AnalysisWorker


class PHASTAnalyzerGUI(QMainWindow):
    """Main GUI application for PHAST dispersion analysis."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PHAST Temperature Dispersion Analyser")
        self.setGeometry(100, 100, 800, 600)
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Create tab widget
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)
        
        # Analysis tab
        analysis_tab = self.create_analysis_tab()
        tab_widget.addTab(analysis_tab, "Analysis")
        
        # Settings tab
        settings_tab = self.create_settings_tab()
        tab_widget.addTab(settings_tab, "Settings")
        
        # Progress and status
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        
        # Log output
        self.log_output = QTextEdit()
        self.log_output.setMaximumHeight(150)
        self.log_output.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_output)
        
    def create_analysis_tab(self) -> QWidget:
        """Create the main analysis tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # File selection group
        file_group = QGroupBox("File Selection")
        file_layout = QGridLayout(file_group)
        
        # Input folder
        file_layout.addWidget(QLabel("Input Folder:"), 0, 0)
        self.input_folder_edit = QLineEdit()
        file_layout.addWidget(self.input_folder_edit, 0, 1)
        input_browse_btn = QPushButton("Browse")
        input_browse_btn.clicked.connect(self.browse_input_folder)
        file_layout.addWidget(input_browse_btn, 0, 2)
        
        # Output file
        file_layout.addWidget(QLabel("Output File:"), 1, 0)
        self.output_file_edit = QLineEdit()
        file_layout.addWidget(self.output_file_edit, 1, 1)
        output_browse_btn = QPushButton("Browse")
        output_browse_btn.clicked.connect(self.browse_output_file)
        file_layout.addWidget(output_browse_btn, 1, 2)
        
        layout.addWidget(file_group)
        
        # Analysis parameters group
        params_group = QGroupBox("Analysis Parameters")
        params_layout = QGridLayout(params_group)
        
        # Temperature type
        params_layout.addWidget(QLabel("Temperature Type:"), 0, 0)
        self.temp_type_combo = QComboBox()
        self.temp_type_combo.addItems([t.value for t in TemperatureType])
        params_layout.addWidget(self.temp_type_combo, 0, 1)
        
        # Temperature of interest
        params_layout.addWidget(QLabel("Temperature of Interest (°C):"), 1, 0)
        self.temp_interest_spin = QDoubleSpinBox()
        self.temp_interest_spin.setRange(-273, 1000)
        self.temp_interest_spin.setValue(-15)
        self.temp_interest_spin.setDecimals(2)
        params_layout.addWidget(self.temp_interest_spin, 1, 1)

        # Interpolation method
        params_layout.addWidget(QLabel("Interpolation Method:"), 2, 0)
        self.interp_method_combo = QComboBox()
        self.interp_method_combo.addItems([m.value for m in InterpolationMethod])
        params_layout.addWidget(self.interp_method_combo, 2, 1)
        
        layout.addWidget(params_group)
        
        # Run button
        self.run_button = QPushButton("Run Analysis")
        self.run_button.clicked.connect(self.run_analysis)
        self.run_button.setStyleSheet("QPushButton { font-weight: bold; padding: 10px; }")
        layout.addWidget(self.run_button)
        
        return tab
    
    def create_settings_tab(self) -> QWidget:
        """Create the settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        settings_group = QGroupBox("General Settings")
        settings_layout = QVBoxLayout(settings_group)
        
        self.verbose_checkbox = QCheckBox("Verbose Mode")
        self.verbose_checkbox.setChecked(True)
        settings_layout.addWidget(self.verbose_checkbox)
        
        settings_layout.addWidget(QLabel("Decimal Places:"))
        self.decimal_places_spin = QSpinBox()
        self.decimal_places_spin.setRange(0, 10)
        self.decimal_places_spin.setValue(2)
        settings_layout.addWidget(self.decimal_places_spin)
        
        layout.addWidget(settings_group)
        # Add stretch to push everything to top
        layout.addStretch()
        
        return tab
    
    def browse_input_folder(self):
        """Browse for input folder."""
        folder = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if folder:
            self.input_folder_edit.setText(folder)
    
    def browse_output_file(self):
        """Browse for output file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Output File", "", "Excel Files (*.xlsx);;All Files (*)"
        )
        if file_path:
            if not file_path.endswith('.xlsx'):
                file_path += '.xlsx'
            self.output_file_edit.setText(file_path)
    
    def run_analysis(self):
        """Run the analysis in a separate thread."""
        # Validate inputs
        if not self.input_folder_edit.text() or not self.output_file_edit.text():
            QMessageBox.warning(self, "Warning", "Please select both input folder and output file.")
            return
        
        if not os.path.exists(self.input_folder_edit.text()):
            QMessageBox.warning(self, "Warning", "Input folder does not exist.")
            return
        
        # Prepare configuration
        config = {
            'input_folder': self.input_folder_edit.text(),
            'output_file': self.output_file_edit.text(),
            'temperature_type': self.temp_type_combo.currentText(),
            'temperature_of_interest': self.temp_interest_spin.value(),
            'interpolation_method': self.interp_method_combo.currentText(),
            'verbose': self.verbose_checkbox.isChecked(),
            'decimal_places': self.decimal_places_spin.value()
        }
        
        # Start analysis worker
        self.worker = AnalysisWorker(config)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.status_updated.connect(self.update_status)
        self.worker.analysis_completed.connect(self.on_analysis_completed)
        self.worker.error_occurred.connect(self.on_error)
        
        self.run_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.worker.start()
    
    def update_progress(self, value: int):
        """Update progress bar."""
        self.progress_bar.setValue(value)
    
    def update_status(self, message: str):
        """Update status label."""
        self.status_label.setText(message)
        self.log_output.append(f"[INFO] {message}")
    
    def on_analysis_completed(self, results: List[AnalysisResult]):
        """Handle analysis completion."""
        try:
            self.export_results(results)
            
            self.progress_bar.setVisible(False)
            self.run_button.setEnabled(True)
            
            QMessageBox.information(
                self, "Success", 
                f"Analysis completed successfully!\n"
                f"Results exported to: {self.output_file_edit.text()}\n"
                f"Total records: {len(results)}"
            )
            self.log_output.append(f"[INFO] Analysis completed successfully. Results exported to: {self.output_file_edit.text()}")
            
        except Exception as e:
            self.on_error(f"Export failed: {str(e)}")
    
    def on_error(self, error_message: str):
        """Handle analysis errors."""
        self.progress_bar.setVisible(False)
        self.run_button.setEnabled(True)
        self.status_label.setText("Analysis failed")
        self.log_output.append(f"[ERROR] {error_message}")
        
        QMessageBox.critical(self, "Error", f"Analysis failed:\n{error_message}")
    
    def export_results(self, results: List[AnalysisResult]):
        """Export results to Excel file."""
        if not results:
            raise ValueError("No results to export")
        
        # Convert results to DataFrame
        decimals = self.decimal_places_spin.value()

        def rounded(value):
            return round(value, decimals) if value is not None else None

        data = []
        for result in results:
            data.append({
                'Subsection': result.subsection,
                'Scenario': result.scenario,
                'Weather': result.weather,
                f'Downwind Distance at {result.temperature_of_interest}°C (m)':
                    rounded(result.downwind_distance),
                f'Concentration at {result.temperature_of_interest}°C (ppm)':
                    rounded(result.concentration),
                'Interpolation Method': result.interpolation_method
            })
        
        df = pd.DataFrame(data)
        
        # Export to Excel
        with pd.ExcelWriter(self.output_file_edit.text(), engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Analysis Results', index=False)
            
            # Auto-adjust column widths
            worksheet = writer.sheets['Analysis Results']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width 