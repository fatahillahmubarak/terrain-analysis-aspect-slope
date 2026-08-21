# Changelog

All notable changes to this project are documented in this file.

## [1.2.1] - 2026-08-21

Co-developed by Muhammad Fatahillah Mubarak with Claude (Anthropic) as a coding assistant.

### Fixed
- Packaging only, no code changes: the plugin ZIP now includes the `LICENSE` file (required by the QGIS Plugin Repository) and all files are packaged with standard non-executable permissions (previously flagged by the repository's automated security scan as "Python file has executable permission").

## [1.2.0] - 2026-08-19

Co-developed by Muhammad Fatahillah Mubarak with Claude (Anthropic) as a coding assistant.

### Added
- "Aspect-Slope Bivariate Overlay" gained an optional Hillshade input (raster + band + "Hillshade blend strength" 0-1, default 0.6). When provided, the HSV Value/brightness channel is blended from real relief shading (`(1 - blend) * 0.95 + blend * hillshade_normalized`) instead of a flat constant, so the output map gains a genuine 3D relief look while still showing the aspect/slope color coding on top. Hillshade values are auto-detected as either a 0-255 Byte range (e.g. QGIS's own Hillshade tool output) or an already-normalized 0-1 range.
- Follows the "layer tints with aspect-variant luminosity" principle described by Kennelly & Kimerling (2001) -- see README References.

### Changed
- Fully backward-compatible: omitting the Hillshade parameter produces byte-identical output to v1.1.0 (Value stays a constant 0.95).
- The Hillshade raster (if provided) must be on the exact same pixel grid as Slope and Aspect, extending the existing same-grid requirement.
- The HTML legend preview now adds a note when Hillshade blending was used, clarifying that the legend itself always shows constant-brightness hue/saturation and does not reflect the shading in the actual output raster.

## [1.1.0] - 2026-08-05

Co-developed by Muhammad Fatahillah Mubarak with Claude (Anthropic) as a coding assistant.

### Added
- Processing algorithm "Aspect-Slope Bivariate Overlay": combines a Slope raster and an Aspect raster into one new 4-band (RGB+Alpha) GeoTIFF, encoding aspect direction as Hue and slope steepness as Saturation. Unlike the other two algorithms in this plugin, it creates a new raster file rather than only changing symbology, because QGIS has no live renderer that can combine two input rasters into one color.
- Two modes: **Continuous** (smooth HSV gradient; saturation defaults to a 95th-percentile stretch of the slope data rather than the absolute maximum, since real slope distributions are heavily right-skewed and a max-based stretch left almost the entire test raster looking pale) and **Classified** (discrete, reusing this plugin's existing 7 Van Zuidam classes × 4/8 compass directions as a lookup table).
- Both input rasters must be on the exact same pixel grid; the algorithm deliberately does not auto-resample, since resampling circular aspect data with standard methods (e.g. bilinear) can produce mathematically wrong values.
- Always generates an HTML legend preview (a compass color wheel for Continuous mode, a swatch grid for Classified mode), since a plain RGB raster carries no classification metadata for QGIS to build a legend from automatically. An optional "Save legend image to file" parameter copies the legend PNG to a permanent location, instead of leaving it in the OS temp folder.
- Follows the aspect-slope color mapping technique described by Moellering & Kimerling (1990) and Brewer & Marlow (1993), and implemented by Esri's "Aspect-slope map" workflow since 2008 — see README References. Extends the classic technique with a continuous (non-25-class) mode and a data-driven percentile-based saturation stretch.
- Started as a standalone trial script (validated against user-provided real Slope/Aspect GeoTIFFs), archived under `trial-script/` for reference, then folded into this plugin as a third algorithm.

## [1.0.0] - 2026-08-05

Co-developed by Muhammad Fatahillah Mubarak with Claude (Anthropic) as a coding assistant.

### Added
- Initial public release, combining two previously separate trial scripts into one plugin.
- Processing algorithm "Van Zuidam (1983) Slope Classification Symbology": classifies a slope raster (Degree or Percent) into the 7 standard Van Zuidam geomorphological classes and applies a Singleband Pseudocolor (Discrete) renderer with class-name legend labels. The open-ended top class ("Extremely Steep") is closed with `+infinity`, matching QGIS's own native convention for open-ended Discrete classes, rather than a sampled maximum (which risked leaving extreme outlier pixels uncolored on the full-resolution raster).
- Processing algorithm "Aspect Direction Symbology (Compass Classes)": classifies an aspect raster into 4 or 8 compass-direction classes, each centered on its true direction, using a cyclic HSV color wheel suited to circular data. Flat/no-aspect sentinel pixels (e.g. `-9999`) are excluded from the symbology (display-only). Includes an optional compass-rose (polar) preview.
- Both algorithms set `classificationMin()`/`classificationMax()` on the renderer. This prevents a real QGIS behavior (confirmed by reading QGIS's own source, `qgssinglebandpseudocolorrendererwidget.cpp`): if these are left unset, reopening Layer Properties > Symbology causes the dialog to assume no min/max exists, recompute it from the raw raster, and unconditionally re-classify -- silently overwriting the applied custom classes the moment the dialog is opened, with no click required. This was found and fixed during development of the earlier Natural Breaks Symbology plugin and carried forward here from the start.
- Both algorithms document QGIS's native class-boundary convention (`lower < value <= upper`) in their in-app help text, since it isn't otherwise visible to users and isn't configurable via any parameter.
- Packaged as a standard QGIS plugin (Processing provider), in addition to being usable as standalone Processing scripts.
