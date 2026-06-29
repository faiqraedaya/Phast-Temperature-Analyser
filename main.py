"""
Phast Temperature Analyser

Version: 1.2.0
Author: Faiq Raedaya
Date: 2026-06-29

Changelog:
- 1.0.0
    - Initial build
- 1.1.0
    - Added support for analysing concentrations
- 1.2.0
    - Added support for multiple temperatures of interest in a single run
    - Added settings toggles to enable/disable distance and concentration analysis
    - Moved interpolation method selection to the Settings tab
"""

import sys
from PySide6.QtWidgets import QApplication

from phast_temperature_analyser.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setApplicationName("Phast Temperature Analyser")
    app.setApplicationVersion("1.2.0")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()