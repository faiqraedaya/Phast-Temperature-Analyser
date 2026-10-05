# Phast Temperature Analyser

## Overview
*Phast Temperature Analyser is a desktop tool that reads Phast dispersion reports and finds the maximum downwind distance to one or more temperatures of interest. It supports cryogenic and toxic or flammable risk assessments that need these distances and the matching centreline concentrations.*

## Features
- Batch processing of every Phast dispersion report (.xlsx) in a folder
- Vapour or liquid centreline temperature analysis
- Several temperatures of interest in one run
- Maximum downwind distance, centreline concentration and minimum cloud temperature, each toggled independently
- Linear, cubic spline, quadratic and nearest-neighbour interpolation
- Optional filters for unresolved temperature steps, near-source readings, first-observer-only and merged weathers
- Excel export with configurable decimal places
- Settings remembered between sessions

## Install
```bash
git clone https://github.com/faiqraedaya/Phast-Temperature-Analyser.git
cd Phast-Temperature-Analyser
uv sync
```

## Usage
```bash
uv run main.py
```
Select a folder of Phast dispersion reports, for example `examples/`, and choose an output Excel file. Set the temperature type and type the temperatures of interest, for example `-30, -15, 0`. Click Run Analysis, then open the output workbook.

## Technical details
Inputs are Phast dispersion report workbooks (.xlsx). The tool streams each worksheet with openpyxl and collects the "Time-varying Observer Dispersion Data (before along-wind-diffusion effects)" tables with their equipment, scenario and weather. It reads the downwind distance, centreline concentration and centreline vapour or liquid temperature columns. Excel lock files (`~$*.xlsx`) are skipped.

Each table is split into its observers, and every crossing of each temperature of interest is located on each observer's profile. The output is interpolated across the crossing segment with the chosen method. Cubic and quadratic fits use a local stencil bounded by turning points and clamped to the segment. The furthest downwind crossing gives the reported distance. The concentration is either the highest at any crossing (default) or the one at the furthest crossing. Optional filters drop readings where the temperature step across the crossing exceeds a limit (default 20 °C), or where the furthest crossing lies within a minimum distance of the source (default 5 m). With Ignore weathers set, the weathers of each scenario merge into one worst-case result.

Results are written to an "Analysis Results" sheet in the chosen workbook. Each row holds the subsection, scenario and weather, an optional minimum temperature, and distance and concentration columns per temperature of interest. The concentration basis and interpolation method are also recorded. The dispersion table is quoted before along-wind-diffusion effects, so values can differ by a few percent from Phast's averaged maximum-concentration graph.

## License
MIT — see [LICENSE](LICENSE).
