# Phast Temperature Dispersion Analyser

A tool for analysing temperature and concentration data from Phast dispersion reports.
Useful for cryogenic and toxic/flammable risk assessments where you want to find the
maximum downwind distance to a temperature of interest, along with the centreline
concentration at that point.

## Features

- Process multiple Excel files containing PHAST dispersion data
- Support for both vapour and liquid temperature analysis
- Find the maximum downwind distance to a temperature of interest (°C)
- Derive the centreline concentration (ppm) at that temperature of interest
- Multiple interpolation methods (Linear, Cubic Spline, Quadratic, Nearest Neighbor)
- Export results to Excel with customizable decimal places

## Installation

```bash
git clone https://github.com/faiqraedaya/Phast-Temperature-Analyser
cd Phast-Temperature-Analyser
uv sync
```

## Usage

1. Run the application 
```bash
uv run main.py
```
2. Load a folder containing Phast dispersion reports (Excel files).
3. Define an output Excel file.
4. Set the temperature type (Vapour or Liquid), your temperature of interest interpolation method.
5. Run Analysis.

## License

[MIT](LICENSE)