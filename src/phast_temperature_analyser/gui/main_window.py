import os
import re
import logging
from typing import List
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox,
    QProgressBar, QTextEdit, QFileDialog, QMessageBox, QGroupBox,
    QSpinBox, QDoubleSpinBox, QToolButton, QSizePolicy
)
from PySide6.QtCore import Qt, QObject, Signal, QSettings
from PySide6.QtGui import QFont

from phast_temperature_analyser.core.types import (
    TemperatureType, InterpolationMethod, AnalysisResult, ConcentrationBasis
)
from phast_temperature_analyser.core.worker import AnalysisWorker
from phast_temperature_analyser.core.exporter import ResultsExporter

# Anything that separates numbers in free text: commas, semicolons, whitespace.
TEMPERATURE_SEPARATORS = re.compile(r"[,;\s]+")
ABSOLUTE_ZERO = -273.15

SETTINGS_ORGANISATION = "PhastTemperatureAnalyser"
SETTINGS_APPLICATION = "PhastTemperatureAnalyser"


class QtLogHandler(QObject, logging.Handler):
    """Logging handler that forwards records to the GUI via a Qt signal.

    Emitting a signal (rather than touching widgets directly) makes this safe
    to call from the worker thread: the queued connection marshals the append
    onto the GUI thread, so the log updates live during analysis.
    """

    message_logged = Signal(str)

    def __init__(self):
        QObject.__init__(self)
        logging.Handler.__init__(self)

    def emit(self, record):
        try:
            self.message_logged.emit(self.format(record))
        except Exception:
            self.handleError(record)


class CollapsibleSection(QWidget):
    """A titled disclosure triangle that shows or hides its content.

    Qt has no collapsible group box, and the settings below the fold are ones
    most runs never touch, so this keeps them one click away rather than
    filling the window.
    """

    def __init__(self, title: str, parent: QWidget = None):
        super().__init__(parent)

        self.toggle = QToolButton()
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setChecked(False)
        self.toggle.setStyleSheet("QToolButton { border: none; font-weight: bold; }")
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.RightArrow)
        self.toggle.toggled.connect(self._on_toggled)

        self.content = QWidget()
        self.content.setVisible(False)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(12, 4, 0, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.toggle)
        layout.addWidget(self.content)

    def _on_toggled(self, expanded: bool):
        self.toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.content.setVisible(expanded)
        # Shrink the window back down rather than leaving the gap behind.
        window = self.window()
        if window:
            window.adjustSize()

    def addWidget(self, widget: QWidget):
        self.content_layout.addWidget(widget)

    def is_expanded(self) -> bool:
        return self.toggle.isChecked()

    def set_expanded(self, expanded: bool):
        self.toggle.setChecked(expanded)


class MainWindow(QMainWindow):
    """Main GUI application for PHAST temperature analysis."""

    def __init__(self, settings: QSettings = None):
        super().__init__()
        self.setWindowTitle("PHAST Temperature Analyser")
        self.resize(760, 700)

        self.logger = logging.getLogger(__name__)
        # Injectable so tests can point it at a scratch file rather than
        # the real user profile.
        self.settings = settings or QSettings(
            SETTINGS_ORGANISATION, SETTINGS_APPLICATION)

        self.init_ui()
        self.setup_logging()
        self.restore_settings()

    # ------------------------------------------------------------------ setup

    def init_ui(self):
        """Build the single-page interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.addWidget(self._build_files_group())
        layout.addWidget(self._build_analysis_group())
        layout.addWidget(self._build_advanced_section())

        self.run_button = QPushButton("Run Analysis")
        self.run_button.clicked.connect(self.run_analysis)
        self.run_button.setStyleSheet("QPushButton { font-weight: bold; padding: 10px; }")
        layout.addWidget(self.run_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

        # The log is the only running commentary now, so let it take the slack.
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(160)
        self.log_output.setFont(QFont("Consolas", 9))
        self.log_output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.log_output, stretch=1)

    def _build_files_group(self) -> QGroupBox:
        group = QGroupBox("Files")
        form = QFormLayout(group)

        input_row = QHBoxLayout()
        self.input_folder_edit = QLineEdit()
        self.input_folder_edit.setPlaceholderText("Folder of Phast dispersion reports")
        input_row.addWidget(self.input_folder_edit)
        input_browse_btn = QPushButton("Browse")
        input_browse_btn.clicked.connect(self.browse_input_folder)
        input_row.addWidget(input_browse_btn)
        form.addRow("Input folder:", input_row)

        output_row = QHBoxLayout()
        self.output_file_edit = QLineEdit()
        self.output_file_edit.setPlaceholderText("Output.xlsx")
        output_row.addWidget(self.output_file_edit)
        output_browse_btn = QPushButton("Browse")
        output_browse_btn.clicked.connect(self.browse_output_file)
        output_row.addWidget(output_browse_btn)
        form.addRow("Output file:", output_row)

        return group

    def _build_analysis_group(self) -> QGroupBox:
        group = QGroupBox("Analysis")
        form = QFormLayout(group)

        self.temp_type_combo = QComboBox()
        self.temp_type_combo.addItems([t.value for t in TemperatureType])
        form.addRow("Temperature type:", self.temp_type_combo)

        self.temperatures_edit = QLineEdit()
        self.temperatures_edit.setPlaceholderText("-30, -15, 0")
        self.temperatures_edit.setToolTip(
            "One or more temperatures of interest in °C, separated by commas "
            "or spaces."
        )
        form.addRow("Temperatures of interest (°C):", self.temperatures_edit)

        # These decide which columns the workbook gets, so they stay in view.
        quantities = QHBoxLayout()
        self.analyse_distance_checkbox = QCheckBox("Downwind distance")
        self.analyse_distance_checkbox.setChecked(True)
        quantities.addWidget(self.analyse_distance_checkbox)
        self.analyse_concentration_checkbox = QCheckBox("Concentration")
        self.analyse_concentration_checkbox.setChecked(True)
        quantities.addWidget(self.analyse_concentration_checkbox)
        self.analyse_minimum_temperature_checkbox = QCheckBox("Minimum temperature")
        self.analyse_minimum_temperature_checkbox.setChecked(False)
        self.analyse_minimum_temperature_checkbox.setToolTip(
            "Report the coldest centreline temperature anywhere in each "
            "cloud. Usually at the source, but the whole profile is "
            "scanned.\n\n"
            "It is a property of the cloud rather than of any temperature of "
            "interest, so it adds one column and does not keep a leak in the "
            "results that the filters have removed."
        )
        quantities.addWidget(self.analyse_minimum_temperature_checkbox)
        quantities.addStretch()
        form.addRow("Analyse:", quantities)

        return group

    def _build_advanced_section(self) -> CollapsibleSection:
        section = CollapsibleSection("Advanced settings")

        # --- reading the data -------------------------------------------------
        reading = QGroupBox("Reading the data")
        reading_layout = QVBoxLayout(reading)
        method_form = QFormLayout()
        self.interp_method_combo = QComboBox()
        self.interp_method_combo.addItems([m.value for m in InterpolationMethod])
        method_form.addRow("Interpolation method:", self.interp_method_combo)
        reading_layout.addLayout(method_form)

        self.first_observer_checkbox = QCheckBox("Only use first observer")
        self.first_observer_checkbox.setToolTip(
            "A time-varying release is reported as several observers — parcels "
            "leaving the source at different times — and by default every one "
            "is analysed. Tick this to read only the observer PHAST lists "
            "first, which for a catastrophic rupture is the initial release "
            "before the pool starts feeding later parcels."
        )
        reading_layout.addWidget(self.first_observer_checkbox)
        section.addWidget(reading)

        # --- reporting --------------------------------------------------------
        reporting = QGroupBox("Reporting")
        reporting_form = QFormLayout(reporting)

        self.concentration_basis_combo = QComboBox()
        self.concentration_basis_combo.addItems([b.value for b in ConcentrationBasis])
        self.concentration_basis_combo.setToolTip(
            "A temperature of interest can be reached at many points, and the "
            "observer reaching it furthest downwind is often a late, dilute "
            "parcel.\n\n"
            "'Highest at any crossing' reports the worst concentration "
            "anywhere that temperature occurs — conservative for toxic and "
            "flammable assessment, but from a different point than the "
            "reported distance.\n\n"
            "'At the furthest crossing' keeps distance and concentration "
            "describing the same point, which can understate the "
            "concentration by an order of magnitude."
        )
        self.concentration_basis_label = QLabel("Concentration to report:")
        reporting_form.addRow(self.concentration_basis_label,
                              self.concentration_basis_combo)
        self.analyse_concentration_checkbox.toggled.connect(
            self.concentration_basis_label.setEnabled)
        self.analyse_concentration_checkbox.toggled.connect(
            self.concentration_basis_combo.setEnabled)

        self.decimal_places_spin = QSpinBox()
        self.decimal_places_spin.setRange(0, 10)
        self.decimal_places_spin.setValue(2)
        reporting_form.addRow("Decimal places:", self.decimal_places_spin)

        self.ignore_weathers_checkbox = QCheckBox(
            "Ignore weathers (one worst-case result per scenario)"
        )
        self.ignore_weathers_checkbox.setToolTip(
            "Combine the weathers of each subsection/scenario into a single "
            "result. At each temperature of interest the weather reaching it "
            "furthest downwind governs, and the concentration reported is the "
            "one that weather gives at that distance."
        )
        reporting_form.addRow(self.ignore_weathers_checkbox)
        section.addWidget(reporting)

        # --- filters ----------------------------------------------------------
        filters = QGroupBox("Filters")
        filters_layout = QVBoxLayout(filters)

        self.ignore_unresolved_checkbox = QCheckBox(
            "Ignore clouds that heat up too quickly to resolve"
        )
        self.ignore_unresolved_checkbox.setToolTip(
            "Discard a temperature of interest when the cloud warms straight "
            "past it in a single output step wider than the limit below — for "
            "example -99 °C at 0 m and 17 °C at 1 m. The crossing could sit "
            "anywhere in that step, so no distance or concentration is "
            "reported for it. Other temperatures of interest are unaffected, "
            "and a cloud left with no readings at all drops out of the results."
        )
        filters_layout.addWidget(self.ignore_unresolved_checkbox)

        step_row = QHBoxLayout()
        step_row.addSpacing(20)
        self.max_temp_step_label = QLabel("Maximum temperature step (°C):")
        step_row.addWidget(self.max_temp_step_label)
        self.max_temp_step_spin = QDoubleSpinBox()
        self.max_temp_step_spin.setRange(0.1, 1000.0)
        self.max_temp_step_spin.setDecimals(1)
        self.max_temp_step_spin.setSingleStep(5.0)
        self.max_temp_step_spin.setValue(20.0)
        step_row.addWidget(self.max_temp_step_spin)
        step_row.addStretch()
        filters_layout.addLayout(step_row)

        self.ignore_unresolved_checkbox.toggled.connect(self.max_temp_step_label.setEnabled)
        self.ignore_unresolved_checkbox.toggled.connect(self.max_temp_step_spin.setEnabled)
        self.max_temp_step_label.setEnabled(False)
        self.max_temp_step_spin.setEnabled(False)

        self.ignore_near_field_checkbox = QCheckBox(
            "Ignore temperatures reached too close to the source"
        )
        self.ignore_near_field_checkbox.setToolTip(
            "Discard a temperature of interest when even the furthest point "
            "reaching it lies within the minimum distance below. The reading "
            "then describes the release itself rather than the dispersing "
            "cloud, so no distance or concentration is reported for it. Other "
            "temperatures of interest are unaffected, and a cloud left with no "
            "readings at all drops out of the results."
        )
        filters_layout.addWidget(self.ignore_near_field_checkbox)

        distance_row = QHBoxLayout()
        distance_row.addSpacing(20)
        self.min_distance_label = QLabel("Minimum downwind distance (m):")
        distance_row.addWidget(self.min_distance_label)
        self.min_distance_spin = QDoubleSpinBox()
        self.min_distance_spin.setRange(0.0, 100000.0)
        self.min_distance_spin.setDecimals(2)
        self.min_distance_spin.setSingleStep(1.0)
        self.min_distance_spin.setValue(5.0)
        distance_row.addWidget(self.min_distance_spin)
        distance_row.addStretch()
        filters_layout.addLayout(distance_row)

        self.ignore_near_field_checkbox.toggled.connect(self.min_distance_label.setEnabled)
        self.ignore_near_field_checkbox.toggled.connect(self.min_distance_spin.setEnabled)
        self.min_distance_label.setEnabled(False)
        self.min_distance_spin.setEnabled(False)

        section.addWidget(filters)

        self.advanced_section = section
        return section

    def setup_logging(self):
        """Route application logging into the in-app log panel (not the console)."""
        handler = QtLogHandler()
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        handler.message_logged.connect(self.log_output.append)

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(handler)
        self.log_handler = handler

    # ------------------------------------------------------------ persistence

    def restore_settings(self):
        """Reload the previous session's settings."""
        s = self.settings
        geometry = s.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

        self.input_folder_edit.setText(s.value("files/input_folder", "", str))
        self.output_file_edit.setText(s.value("files/output_file", "", str))

        self._restore_combo(self.temp_type_combo, s.value("analysis/temperature_type", "", str))
        self.temperatures_edit.setText(s.value("analysis/temperatures", "", str))
        self.analyse_distance_checkbox.setChecked(
            s.value("analysis/distance", True, bool))
        self.analyse_concentration_checkbox.setChecked(
            s.value("analysis/concentration", True, bool))
        self.analyse_minimum_temperature_checkbox.setChecked(
            s.value("analysis/minimum_temperature", False, bool))

        self._restore_combo(self.interp_method_combo,
                            s.value("advanced/interpolation_method", "", str))
        self.first_observer_checkbox.setChecked(
            s.value("advanced/first_observer_only", False, bool))
        self._restore_combo(self.concentration_basis_combo,
                            s.value("advanced/concentration_basis", "", str))
        self.decimal_places_spin.setValue(s.value("advanced/decimal_places", 2, int))
        self.ignore_weathers_checkbox.setChecked(
            s.value("advanced/ignore_weathers", False, bool))

        self.ignore_unresolved_checkbox.setChecked(
            s.value("advanced/ignore_unresolved", False, bool))
        self.max_temp_step_spin.setValue(
            s.value("advanced/max_temperature_step", 20.0, float))
        self.ignore_near_field_checkbox.setChecked(
            s.value("advanced/ignore_near_field", False, bool))
        self.min_distance_spin.setValue(
            s.value("advanced/min_downwind_distance", 5.0, float))

        self.advanced_section.set_expanded(s.value("advanced/expanded", False, bool))

        # The concentration basis follows the checkbox, which may have just
        # been restored without emitting a change.
        enabled = self.analyse_concentration_checkbox.isChecked()
        self.concentration_basis_label.setEnabled(enabled)
        self.concentration_basis_combo.setEnabled(enabled)

    def save_settings(self):
        """Remember the current settings for the next session."""
        s = self.settings
        s.setValue("window/geometry", self.saveGeometry())

        s.setValue("files/input_folder", self.input_folder_edit.text())
        s.setValue("files/output_file", self.output_file_edit.text())

        s.setValue("analysis/temperature_type", self.temp_type_combo.currentText())
        s.setValue("analysis/temperatures", self.temperatures_edit.text())
        s.setValue("analysis/distance", self.analyse_distance_checkbox.isChecked())
        s.setValue("analysis/concentration", self.analyse_concentration_checkbox.isChecked())
        s.setValue("analysis/minimum_temperature",
                   self.analyse_minimum_temperature_checkbox.isChecked())

        s.setValue("advanced/interpolation_method", self.interp_method_combo.currentText())
        s.setValue("advanced/first_observer_only", self.first_observer_checkbox.isChecked())
        s.setValue("advanced/concentration_basis",
                   self.concentration_basis_combo.currentText())
        s.setValue("advanced/decimal_places", self.decimal_places_spin.value())
        s.setValue("advanced/ignore_weathers", self.ignore_weathers_checkbox.isChecked())
        s.setValue("advanced/ignore_unresolved",
                   self.ignore_unresolved_checkbox.isChecked())
        s.setValue("advanced/max_temperature_step", self.max_temp_step_spin.value())
        s.setValue("advanced/ignore_near_field",
                   self.ignore_near_field_checkbox.isChecked())
        s.setValue("advanced/min_downwind_distance", self.min_distance_spin.value())
        s.setValue("advanced/expanded", self.advanced_section.is_expanded())

    @staticmethod
    def _restore_combo(combo: QComboBox, value: str):
        """Select a stored combo entry, ignoring one that no longer exists."""
        if value and combo.findText(value) >= 0:
            combo.setCurrentText(value)

    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)

    # ------------------------------------------------------------------ input

    def collect_temperatures(self) -> List[float]:
        """Parse the temperatures of interest entered as free text.

        Raises ValueError naming the offending text, so the warning can say
        which entry is wrong rather than that something is.
        """
        text = self.temperatures_edit.text().strip()
        if not text:
            return []
        temperatures = []
        for token in TEMPERATURE_SEPARATORS.split(text):
            if not token:
                continue
            try:
                value = float(token)
            except ValueError:
                raise ValueError(f"'{token}' is not a number.")
            if value < ABSOLUTE_ZERO:
                raise ValueError(f"{value:g} °C is below absolute zero.")
            temperatures.append(value)
        return temperatures

    def browse_input_folder(self):
        """Browse for input folder."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Input Folder", self.input_folder_edit.text().strip()
        )
        if folder:
            self.input_folder_edit.setText(folder)
            # Default the output to Output.xlsx in the input folder, unless the
            # user has already chosen an output file themselves.
            if not self.output_file_edit.text().strip():
                self.output_file_edit.setText(os.path.join(folder, "Output.xlsx"))

    def browse_output_file(self):
        """Browse for output file."""
        default_path = self.output_file_edit.text().strip()
        if not default_path:
            input_folder = self.input_folder_edit.text().strip()
            default_path = os.path.join(input_folder, "Output.xlsx") if input_folder else ""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Output File", default_path, "Excel Files (*.xlsx);;All Files (*)"
        )
        if file_path:
            if not file_path.endswith('.xlsx'):
                file_path += '.xlsx'
            self.output_file_edit.setText(file_path)

    # ---------------------------------------------------------------- running

    def run_analysis(self):
        """Run the analysis in a separate thread."""
        if not self.input_folder_edit.text() or not self.output_file_edit.text():
            QMessageBox.warning(self, "Warning", "Please select both input folder and output file.")
            return

        if not os.path.exists(self.input_folder_edit.text()):
            QMessageBox.warning(self, "Warning", "Input folder does not exist.")
            return

        try:
            temperatures_of_interest = self.collect_temperatures()
        except ValueError as e:
            QMessageBox.warning(
                self, "Warning",
                f"Could not read the temperatures of interest: {e}\n\n"
                f"Enter them separated by commas or spaces, for example: -30, -15, 0"
            )
            return
        if not temperatures_of_interest:
            QMessageBox.warning(self, "Warning", "Please enter at least one temperature of interest.")
            return

        analyse_distance = self.analyse_distance_checkbox.isChecked()
        analyse_concentration = self.analyse_concentration_checkbox.isChecked()
        analyse_minimum_temperature = (
            self.analyse_minimum_temperature_checkbox.isChecked())
        if not (analyse_distance or analyse_concentration
                or analyse_minimum_temperature):
            QMessageBox.warning(
                self, "Warning",
                "Enable at least one quantity to analyse (distance, "
                "concentration or minimum temperature)."
            )
            return

        # Keep the settings even if the run fails or the app is killed.
        self.save_settings()

        config = {
            'input_folder': self.input_folder_edit.text(),
            'output_file': self.output_file_edit.text(),
            'temperature_type': self.temp_type_combo.currentText(),
            'temperatures_of_interest': temperatures_of_interest,
            'interpolation_method': self.interp_method_combo.currentText(),
            'analyse_distance': analyse_distance,
            'analyse_concentration': analyse_concentration,
            'analyse_minimum_temperature': analyse_minimum_temperature,
            'ignore_weathers': self.ignore_weathers_checkbox.isChecked(),
            'first_observer_only': self.first_observer_checkbox.isChecked(),
            'concentration_basis': self.concentration_basis_combo.currentText(),
            'max_temperature_step': (
                self.max_temp_step_spin.value()
                if self.ignore_unresolved_checkbox.isChecked() else None
            ),
            'min_downwind_distance': (
                self.min_distance_spin.value()
                if self.ignore_near_field_checkbox.isChecked() else None
            ),
            'decimal_places': self.decimal_places_spin.value()
        }

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
        """Show a status message, letting the log handler format it."""
        self.status_label.setText(message)
        logging.info(message)

    def on_analysis_completed(self, results: List[AnalysisResult]):
        """Handle analysis completion."""
        try:
            self.export_results(results)

            self.progress_bar.setVisible(False)
            self.run_button.setEnabled(True)

            logging.info(
                f"{len(results)} record(s) exported to {self.output_file_edit.text()}"
            )
            QMessageBox.information(
                self, "Success",
                f"Analysis completed successfully!\n"
                f"Results exported to: {self.output_file_edit.text()}\n"
                f"Total records: {len(results)}"
            )
            self.open_output_file(self.output_file_edit.text())

        except Exception as e:
            self.on_error(f"Export failed: {str(e)}")

    def open_output_file(self, file_path: str):
        """Attempt to open the output file in the default application."""
        try:
            os.startfile(file_path)
        except Exception as e:
            logging.warning(f"Could not open output file: {str(e)}")

    def on_error(self, error_message: str):
        """Handle analysis errors."""
        self.progress_bar.setVisible(False)
        self.run_button.setEnabled(True)
        self.status_label.setText("Analysis failed")
        logging.error(error_message)

        QMessageBox.critical(self, "Error", f"Analysis failed:\n{error_message}")

    def export_results(self, results: List[AnalysisResult]):
        """Hand the results to the core exporter using the current settings."""
        exporter = ResultsExporter(
            decimal_places=self.decimal_places_spin.value(),
            include_distance=self.analyse_distance_checkbox.isChecked(),
            include_concentration=self.analyse_concentration_checkbox.isChecked(),
            concentration_basis=self.concentration_basis_combo.currentText(),
            include_minimum_temperature=(
                self.analyse_minimum_temperature_checkbox.isChecked()),
        )
        exporter.export(results, self.output_file_edit.text())
