"""
Phast Temperature Analyser

Version: 1.3.0
Author: Faiq Raedaya
Date: 2026-07-06

Changelog:
- 1.0.0
    - Initial build
- 1.1.0
    - Added support for analysing concentrations
- 1.2.0
    - Added support for multiple temperatures of interest in a single run
    - Added settings toggles to enable/disable distance and concentration analysis
    - Moved interpolation method selection to the Settings tab
- 1.3.0
    - Rewrote the Excel processing logic around a single streaming pass
    - Fixed a bug where the application would crash if the Excel files contained unexpected data formats
    - Fixed log to update in real time instead of only after the analysis is complete
    - Fixed progress bar to update with files processed instead of only after the analysis is complete
    - Changed exporter column layout
"""

import sys
from PySide6.QtWidgets import QApplication

from phast_temperature_analyser.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setApplicationName("Phast Temperature Analyser")
    app.setApplicationVersion("1.3.0")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()