# Phast Temperature Dispersion Analyser

A tool for analysing temperature and concentration data from Phast dispersion reports.
Useful for cryogenic and toxic/flammable risk assessments where you want to find the
maximum downwind distance to one or more temperatures of interest, along with the
centreline concentration at those points.

## Features

- Process multiple Excel files containing PHAST dispersion data
- Support for both vapour and liquid temperature analysis
- Analyse several temperatures of interest (°C) in a single run
- Find the maximum downwind distance to each temperature of interest
- Derive the centreline concentration (ppm) at each temperature of interest
- Toggle distance and/or concentration analysis on or off
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
4. Set the temperature type (Vapour or Liquid) and add your temperature(s) of interest
   to the table (use **Add** / **Remove Selected** to enter as many as you need).
5. (Optional) In the Settings tab, choose the interpolation method, set decimal places,
   and toggle whether to analyse downwind distance and/or concentration.
6. Run Analysis.

## License

[MIT](LICENSE)