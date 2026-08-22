"""
Phast Temperature Analyser

Version: 1.8.0
Author: Faiq Raedaya
Date: 2026-07-29

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
- 1.4.0
    - Fixed the temperature-finding algorithm for non-monotonic profiles: all
      crossings of the temperature of interest are now located and the
      worst-case extent is reported (maximum distance, minimum concentration)
      instead of an arbitrary crossing
- 1.5.0
    - Added an "Ignore weathers" setting that combines the weathers of each
      subsection/scenario into a single worst-case result (furthest downwind
      distance, lowest concentration at each temperature of interest)
- 1.6.0
    - Fixed the dispersion tables of time-varying releases being read as one
      profile: they hold several observers concatenated with no separator, and
      the seam between two of them read as a segment running tens of kilometres
      upwind across the whole temperature range. The crossing invented there
      won the worst case outright, reporting tens of kilometres in place of a
      few metres. Each observer is now read on its own profile and the worst
      case is taken across them
    - Fixed interpolation across a temperature plateau anchoring the crossing to
      the wrong end of it, which understated the downwind distance
    - Fixed a temperature of interest colder than the cloud ever gets reporting
      the distance to the coldest point instead of no result, matching how a
      temperature hotter than the cloud was already treated
    - Cubic and quadratic interpolation now fit a local stencil around the
      crossing, bounded by the turning points either side of it, instead of
      fitting across a whole monotonic stretch
    - Added an "Ignore clouds that heat up too quickly to resolve" setting that
      discards a temperature of interest when the cloud warms straight past it
      in a single output step wider than a configurable limit
    - Added an "Ignore temperatures reached too close to the source" setting
      that discards a temperature of interest when even the furthest point
      reaching it lies within a configurable minimum downwind distance
    - Verbose mode now logs the downwind distance and concentration found at
      each temperature of interest, alongside the observer count per table
    - Fixed the reported concentration being read off a different point from
      the reported distance. The two were reduced separately — furthest
      distance from one crossing, lowest concentration from another, possibly
      in a different observer or weather — so the pair described no single
      place on the cloud. On a catastrophic tank rupture, where the cloud
      spreads upwind and is most dilute behind the release, this understated
      the concentration by up to a factor of nine. Both quantities are now read
      off the crossing that gives the reported distance
    - Fixed a report lacking the selected temperature column (e.g. liquid
      temperature on a vapour-only report) aborting the whole file instead of
      skipping that table
    - Excel owner-lock files (~$*.xlsx) are no longer read as reports
    - Added a "Concentration to report" setting. The observer reaching a
      temperature of interest furthest downwind is often a late, dilute
      parcel, so reporting its concentration understated the worst case by
      more than five times on a catastrophic rupture. The new default
      reports the highest concentration at any crossing of that
      temperature; the previous behaviour is still available. The chosen
      basis is written into the exported workbook
    - Added an "Only use first observer" setting that restricts each
      dispersion table to the observer PHAST lists first
- 1.7.0
    - Rebuilt the interface as a single page: the Analysis and Settings tabs
      are gone, and everything most runs never touch now sits in a
      collapsible "Advanced settings" section
    - Temperatures of interest are typed as free text ("-30, -15, 0")
      instead of being added a row at a time to a table
    - Removed Verbose Mode; the log is always written
    - Settings, window geometry and the state of the Advanced section are
      remembered between sessions
    - The log panel now grows with the window, and the duplicated
      completion message is gone
- 1.8.0
    - Added "Minimum temperature" as a third quantity to analyse: the
      coldest centreline temperature anywhere in the cloud, scanned across
      the whole profile and every observer. It adds one column rather than
      one per temperature of interest, and does not keep a leak in the
      results that the filters have removed
"""

import sys
from PySide6.QtWidgets import QApplication

from phast_temperature_analyser.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setApplicationName("Phast Temperature Analyser")
    app.setApplicationVersion("1.8.0")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()