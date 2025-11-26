import sys
from PySide6.QtWidgets import QApplication

from gui.main_window import PHASTAnalyzerGUI

def main():
    """Main application entry point."""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look
    
    window = PHASTAnalyzerGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()