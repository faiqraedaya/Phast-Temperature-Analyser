import sys
from PySide6.QtWidgets import QApplication

from phast_temperature_analyser.gui.main_window import PHASTAnalyzerGUI


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = PHASTAnalyzerGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
