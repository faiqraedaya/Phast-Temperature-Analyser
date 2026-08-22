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
- Report the coldest centreline temperature (°C) reached by each cloud
- Toggle each quantity on or off independently
- Optionally ignore clouds that heat up too quickly for the output to resolve
- Optionally ignore temperatures only reached within a minimum downwind distance
- Choose whether the concentration reported is the worst anywhere the temperature
  occurs, or the one at the furthest crossing
- Optionally analyse only the first observer of each dispersion table
- Multiple interpolation methods (Linear, Cubic Spline, Quadratic, Nearest Neighbor)
- Export results to Excel with customizable decimal places
- Settings remembered between sessions

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
4. Set the temperature type (Vapour or Liquid) and type your temperature(s) of
   interest, separated by commas or spaces — for example `-30, -15, 0`.
5. Tick which quantities to analyse: downwind distance, concentration and/or
   minimum temperature.
6. (Optional) Expand **Advanced settings** for the interpolation method, decimal
   places, observer and weather handling, and the two filters.
7. Run Analysis.

Settings, including the window size and whether Advanced settings was expanded,
are remembered between sessions.

## How a reading is chosen

A temperature of interest can be reached several times along a cloud, and a
time-varying release is reported as several observers whose profiles are all
scanned. Every crossing is found, and the one furthest downwind is reported —
that is the extent of the temperature of interest.

Which concentration goes beside it is set by **Concentration to report** under
Advanced settings:

- **Highest at any crossing** (default) — the worst concentration anywhere that
  temperature occurs. The observer reaching furthest downwind is often a late,
  dilute parcel, so this is the conservative reading for toxic and flammable
  assessment alike. It comes from a different point than the reported distance,
  and each column is then the worst case of its own quantity.
- **At the furthest crossing** — the concentration at the point the distance
  refers to, so the row describes one real place on the cloud. On a
  catastrophic rupture this can be an order of magnitude lower.

The choice is written into the exported workbook as a *Concentration Basis*
column, so the basis travels with the numbers.

Cross-checking against PHAST's own *Maximum Concentration versus Distance*
graph, note that the dispersion table is quoted at a short averaging time
"before along-wind-diffusion effects", while the toxic graph is typically a
600 s average after them. Expect a few percent difference on that account.

## Using only the first observer

**Only use first observer** under Advanced settings restricts each dispersion table
to the observer PHAST lists first. For a catastrophic rupture that is the
initial release, before the spreading pool starts feeding later parcels. Off by
default; with it on, the log says so.

Note that clouds from a catastrophic rupture can extend upwind of the release
point, which PHAST reports as a negative downwind distance. Those crossings are
found like any other but never govern, since the furthest downwind one wins.

## Minimum temperature

**Minimum temperature** reports the coldest centreline temperature anywhere
in each cloud. It is usually at the source, but the whole profile is
scanned — and across every observer, unless **Only use first observer** is
set. Under **Ignore weathers**, the coldest of the merged weathers is kept.

It is a property of the cloud rather than of any temperature of interest, so
it adds a single column rather than one per temperature. It also does not
keep a leak in the results that the filters below have removed — a leak still
earns its row on distance or concentration. The exception is ticking it on
its own, in which case it decides which rows appear.

## Clouds that heat up too quickly

Some clouds warm straight past the temperature of interest in a single output
step — for instance -99 °C at 0 m and 17 °C at 1 m, with a temperature of
interest of -40 °C. The crossing could sit anywhere in that step, so any
distance read off it carries the width of the whole step as its error.

Tick **Ignore clouds that heat up too quickly to resolve** under Advanced
settings to discard these. A temperature of interest is dropped when every crossing of
it falls inside a step wider than **Maximum temperature step** (default 20 °C),
leaving its distance and concentration blank. Temperatures of interest that the
same cloud does resolve are kept, and a cloud left with no readings at all drops
out of the results entirely. The log reports how many readings were discarded,
so you can tell whether the limit is cutting into readings you wanted.

The setting is off by default, and a temperature of interest that lands exactly
on a reported row is never discarded — nothing had to be interpolated.

## Temperatures reached only next to the source

A related case: the cloud does resolve the temperature of interest, but reaches
it only a metre or two downwind, inside the near field where the release itself
dominates and the dispersion model is not representative.

Tick **Ignore temperatures reached too close to the source** under Advanced
settings to discard these. A temperature of interest is dropped when even the furthest
point reaching it lies within **Minimum downwind distance** (default 5 m) — the
furthest crossing is the whole extent of that temperature, so if it sits inside
the near field, nothing about the reading describes the dispersing cloud. The
concentration is dropped with it, since it is read off the same crossing.

This works whether or not downwind distance is one of the quantities being
reported. The setting is off by default, and the log reports how many readings
were discarded.

## License

[MIT](LICENSE)