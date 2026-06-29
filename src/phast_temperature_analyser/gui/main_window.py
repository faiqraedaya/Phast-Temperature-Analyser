import os
import logging
from typing import List
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox,
    QProgressBar, QTextEdit, QFileDialog, QMessageBox, QGroupBox,
    QSpinBox, QDoubleSpinBox, QTabWidget, QTableWidget, QHeaderView,
    QAbstractItemView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from phast_temperature_analyser.core.types import TemperatureType, InterpolationMethod, AnalysisResult
from phast_temperature_analyser.core.worker import AnalysisWorker
from phast_temperature_analyser.core.exporter import ResultsExporter


class MainWindow(QMainWindow):
    """Main GUI application for PHAST temperature analysis."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PHAST Temperature Analyser")
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

        layout.addWidget(params_group)

        # Temperatures of interest (editable table, one value per row)
        temp_group = QGroupBox("Temperatures of Interest (°C)")
        temp_layout = QVBoxLayout(temp_group)

        self.temp_table = QTableWidget(0, 1)
        self.temp_table.setHorizontalHeaderLabels(["Temperature (°C)"])
        self.temp_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.temp_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.temp_table.setMaximumHeight(180)
        temp_layout.addWidget(self.temp_table)

        temp_buttons = QHBoxLayout()
        add_temp_btn = QPushButton("Add")
        add_temp_btn.clicked.connect(lambda: self.add_temperature_row())
        temp_buttons.addWidget(add_temp_btn)
        remove_temp_btn = QPushButton("Remove Selected")
        remove_temp_btn.clicked.connect(self.remove_temperature_rows)
        temp_buttons.addWidget(remove_temp_btn)
        temp_buttons.addStretch()
        temp_layout.addLayout(temp_buttons)

        layout.addWidget(temp_group)

        # Seed with a sensible default row
        self.add_temperature_row(-15.0)

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

        settings_layout.addWidget(QLabel("Interpolation Method:"))
        self.interp_method_combo = QComboBox()
        self.interp_method_combo.addItems([m.value for m in InterpolationMethod])
        settings_layout.addWidget(self.interp_method_combo)

        layout.addWidget(settings_group)

        # Quantities to analyse at each temperature of interest
        analyse_group = QGroupBox("Quantities to Analyse")
        analyse_layout = QVBoxLayout(analyse_group)

        self.analyse_distance_checkbox = QCheckBox("Downwind Distance")
        self.analyse_distance_checkbox.setChecked(True)
        analyse_layout.addWidget(self.analyse_distance_checkbox)

        self.analyse_concentration_checkbox = QCheckBox("Concentration")
        self.analyse_concentration_checkbox.setChecked(True)
        analyse_layout.addWidget(self.analyse_concentration_checkbox)

        layout.addWidget(analyse_group)

        # Add stretch to push everything to top
        layout.addStretch()

        return tab

    def add_temperature_row(self, value: float = -15.0):
        """Append a new temperature row backed by a numeric spin box."""
        row = self.temp_table.rowCount()
        self.temp_table.insertRow(row)
        spin = QDoubleSpinBox()
        spin.setRange(-273, 1000)
        spin.setDecimals(2)
        spin.setValue(value)
        self.temp_table.setCellWidget(row, 0, spin)
        self.temp_table.setCurrentCell(row, 0)

    def remove_temperature_rows(self):
        """Remove the selected rows, or the last row if none are selected."""
        selected_rows = {index.row() for index in self.temp_table.selectionModel().selectedRows()}
        if not selected_rows and self.temp_table.rowCount() > 0:
            selected_rows = {self.temp_table.rowCount() - 1}
        for row in sorted(selected_rows, reverse=True):
            self.temp_table.removeRow(row)

    def collect_temperatures(self) -> List[float]:
        """Read the temperature values currently entered in the table."""
        return [
            self.temp_table.cellWidget(row, 0).value()
            for row in range(self.temp_table.rowCount())
            if self.temp_table.cellWidget(row, 0) is not None
        ]
    
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

        temperatures_of_interest = self.collect_temperatures()
        if not temperatures_of_interest:
            QMessageBox.warning(self, "Warning", "Please add at least one temperature of interest.")
            return

        analyse_distance = self.analyse_distance_checkbox.isChecked()
        analyse_concentration = self.analyse_concentration_checkbox.isChecked()
        if not analyse_distance and not analyse_concentration:
            QMessageBox.warning(
                self, "Warning",
                "Enable at least one quantity to analyse (distance or concentration)."
            )
            return

        # Prepare configuration
        config = {
            'input_folder': self.input_folder_edit.text(),
            'output_file': self.output_file_edit.text(),
            'temperature_type': self.temp_type_combo.currentText(),
            'temperatures_of_interest': temperatures_of_interest,
            'interpolation_method': self.interp_method_combo.currentText(),
            'analyse_distance': analyse_distance,
            'analyse_concentration': analyse_concentration,
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
        """Hand the results to the core exporter using the current settings."""
        exporter = ResultsExporter(
            decimal_places=self.decimal_places_spin.value(),
            include_distance=self.analyse_distance_checkbox.isChecked(),
            include_concentration=self.analyse_concentration_checkbox.isChecked(),
        )
        exporter.export(results, self.output_file_edit.text())