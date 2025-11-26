# PHAST Temperature Dispersion Analyser

A tool for analysing temperature data from PHAST dispersion reports.
Useful for cryogenic risk assessments where you want to find the maximum downwind distance to a temperature of interest.

## Features

- Process multiple Excel files containing PHAST dispersion data
- Support for both vapour and liquid temperature analysis
- Multiple interpolation methods (Linear, Cubic Spline, Quadratic, Nearest Neighbor)
- Export results to Excel with customizable decimal places
- Progress tracking and logging 

## Installation

1. Clone this repository
2. Install the required dependencies:
```bash
pip install numpy pandas scipy openpyxl PySide6
```

## Usage

1. Run the application:
```bash
python main.py
```

2. Load a folder containing Phast dispersion reports (Excel files).
3. Define an output Excel file.
4. Set the temperature type (Vapour or Liquid), your temperature of interest and interpolation method.
5. Run Analysis.

## License

This project is open source and available under the MIT License. 