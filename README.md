# Terrain Analysis Symbology (QGIS Plugin)

A QGIS Processing provider with three algorithms for visualizing terrain-derived rasters:

- **Van Zuidam (1983) Slope Classification Symbology** — classifies a slope raster into the 7 standard Van Zuidam geomorphological classes and applies a Singleband Pseudocolor (Discrete) renderer with class-name legend labels.
- **Aspect Direction Symbology (Compass Classes)** — classifies an aspect raster into 4 or 8 compass-direction classes, each centered on its true cardinal/intercardinal direction, using a cyclic color wheel suited to circular data, with an optional compass-rose preview.
- **Aspect-Slope Bivariate Overlay** — combines a Slope raster and an Aspect raster into one new RGB(A) raster: hue encodes aspect direction, saturation encodes slope steepness, so a single map shows *how steep* and *which way it faces* at once.

The first two algorithms only change the input layer's symbology; the third creates a new raster file (see [Why the bivariate overlay is different](#why-the-bivariate-overlay-is-different) below).

## Why this exists

QGIS has no built-in symbology preset for the Van Zuidam (1983) slope classification scheme commonly used in geomorphology and hazard-mapping work, nor a compass-direction classification for aspect rasters (QGIS/GDAL's Aspect tool outputs raw 0–360° values with no compass-aware symbology of its own), nor a way to visualize slope and aspect together in one map. This plugin adds all three as one themed "Terrain Analysis" toolset.

It was originally built as separate trial scripts while producing an AHP + GIS flood-hazard map for Samarinda, Indonesia, then combined into a single plugin once each was individually validated in QGIS.

This plugin is a companion to [Natural Breaks Raster Symbology](https://github.com/fatahillahmubarak/raster-natural-breaks-jenks-symbology) (a separate plugin), which stays independent because it's a generic statistical classification tool for any raster, not terrain-specific.

## Features

### Van Zuidam (1983) Slope Classification Symbology
- Classifies a slope raster into Flat, Gently Sloping, Sloping, Moderately Steep, Steep, Very Steep, and Extremely Steep, in either **Degree** or **Percent** (matching the two columns of the original Van Zuidam table).
- The open-ended top class ("Extremely Steep") is closed with `+infinity`, matching QGIS's own native convention for open-ended Discrete classes — not the raster's sampled maximum, which would risk leaving extreme outlier pixels uncolored.
- Any QGIS color ramp, with an option to reverse its direction (defaults to reversed RdYlGn: green = flat, red = extremely steep).
- Optional histogram preview (HTML report via matplotlib), with dashed lines at each Van Zuidam breakpoint — useful as a sanity check (e.g. spotting an accidental Degree/Percent mix-up), even though these breakpoints are fixed rather than data-driven.

### Aspect Direction Symbology (Compass Classes)
- Classifies an aspect raster into **4 directions** (N/E/S/W) or **8 directions** (N/NE/E/SE/S/SW/W/NW), each class centered on its compass direction rather than starting at 0°.
- Flat/no-aspect sentinel pixels (commonly `-9999` or `-1`, depending on the tool used to generate the aspect raster) are excluded from the symbology (marked as NoData for display, without touching the source file).
- A cyclic HSV color wheel (not a linear named ramp) so the first and last class colors connect smoothly at the 0°/360° seam.
- Optional compass-rose (polar) preview showing the proportion of the raster in each direction class, oriented like a real compass.

### Van Zuidam & Aspect Direction algorithms
- Class boundaries follow QGIS's native Discrete-shader convention: `lower < value <= upper` (lower bound excluded, upper bound included). This is hardcoded in QGIS's rendering engine and isn't exposed as a parameter — it only matters if pixel values land exactly on a breakpoint (e.g. rasters rounded to whole numbers).
- No new raster file is created — only the input layer's symbology is changed.

### Aspect-Slope Bivariate Overlay
- Encodes aspect as **hue** and slope steepness as **saturation** in one new RGB(A) GeoTIFF — a single glance shows both how steep an area is and which direction that steepness faces, without switching between two layers. See [Why the bivariate overlay is different](#why-the-bivariate-overlay-is-different) and [References](#references) below.
- **Continuous mode** (default): a smooth HSV color wheel. Saturation defaults to a 95th-percentile stretch of the slope data rather than the absolute maximum, since real slope distributions are heavily right-skewed and a max-based stretch leaves almost the whole raster looking pale.
- **Classified mode**: reuses this plugin's 7 Van Zuidam classes × 4/8 compass directions as a discrete lookup table, closer to the traditional aspect-slope map's ~25-class legend.
- **Optional Hillshade blending (v1.2)**: supply a Hillshade raster (from Raster > Analysis > Hillshade, same grid) to modulate brightness with real relief shading instead of a flat constant, so the output doubles as an actual 3D-looking relief map while still showing the aspect/slope color coding. Fully backward-compatible — omit it and the output is unchanged. A "blend strength" slider (0–1, default 0.6) controls how much the hillshade affects brightness.
- Requires the Slope and Aspect rasters (and Hillshade, if used) to be on the exact same pixel grid (no automatic resampling — circular aspect data can't be resampled with ordinary methods without producing wrong values).
- Always builds an HTML legend preview (a compass color wheel or a swatch grid, since a plain RGB raster has no automatic legend), with an optional parameter to save the legend image permanently. The legend always shows constant-brightness hue/saturation, even when Hillshade blending is used — it explains the color coding, not the shading.

## Installation

### Option A — Install as a QGIS plugin (recommended)

1. Download/clone this repository.
2. Copy the `terrain_analysis_symbology/` folder into your QGIS profile's plugin directory:
   - Windows: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   - Linux: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - macOS: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
3. Restart QGIS, then enable it in **Plugins → Manage and Install Plugins → Installed**.
4. All three algorithms appear in the **Processing Toolbox** under **Terrain Analysis Symbology**.

### Option B — Install from ZIP (no manual copying)

In QGIS, go to **Plugins → Manage and Install Plugins → Install from ZIP**, and select `terrain_analysis_symbology.zip` from this repository. QGIS will install it into the correct plugin directory automatically.

### Option C — Try as standalone Processing scripts (no install)

Open any of `terrain_analysis_symbology/algorithms/van_zuidam_slope_algorithm.py`, `aspect_direction_algorithm.py`, or `aspect_slope_bivariate_overlay_algorithm.py`, and in QGIS go to **Processing Toolbox → Scripts → Add Script to Toolbox...**, then pick the file. This is exactly the same code the plugin uses.

## Usage

### Van Zuidam (1983) Slope Classification Symbology

1. Open **Processing Toolbox** (`Ctrl+Alt+T`) and run **Van Zuidam (1983) Slope Classification Symbology**.
2. Pick your **slope raster layer** and **band**.
3. Pick the **slope unit** (Degree or Percent) — must match how your Slope tool actually computed it, or the whole raster will be misclassified.
4. Pick a **color ramp** and whether to reverse it (default: RdYlGn, reversed).
5. Leave **"Show histogram preview"** checked for a visual sanity check, or uncheck to skip it.
6. Run. Check the Layers panel legend and, if enabled, the histogram preview in the **Results Viewer**.

| Parameter | Description |
|---|---|
| Slope raster layer / Band | The input layer and band to classify. |
| Slope unit | Degree (°) or Percent (%) — must match the source raster. |
| Color ramp | Any ramp from QGIS's style manager (default: `RdYlGn`). |
| Reverse ramp direction | Default on, so Flat reads green and Extremely Steep reads red. |
| Show histogram preview | Build an HTML report with a colored histogram + Van Zuidam breakpoints (needs `matplotlib`). |

### Aspect Direction Symbology (Compass Classes)

1. Run **Aspect Direction Symbology (Compass Classes)** from the Processing Toolbox.
2. Pick your **aspect raster layer** and **band**.
3. Pick the **classification scheme** (4 or 8 directions).
4. Leave **"Exclude flat/no-aspect pixels"** checked and set the correct **sentinel value** for your raster (default `-9999`), unless every pixel already has a valid aspect.
5. Leave **"Show compass-rose preview"** checked for a visual proportion-per-direction check.
6. Run. Note: because "North" straddles the 0°/360° seam, it may appear as **two identical rows** in the legend — this is a known cosmetic limitation of QGIS's linear Discrete shader representing circular data, not a bug.

| Parameter | Description |
|---|---|
| Aspect raster layer / Band | The input layer and band to classify. |
| Classification scheme | 4 directions (N/E/S/W) or 8 directions (N/NE/E/SE/S/SW/W/NW). |
| Exclude flat/no-aspect pixels | Marks a sentinel value as NoData before symbolizing (display-only). |
| Flat/no-aspect sentinel value | The value your aspect raster uses for flat/undefined pixels (commonly `-9999` or `-1`). |
| Show compass-rose preview | Build an HTML report with a polar chart of proportion per direction (needs `matplotlib`). |

### Aspect-Slope Bivariate Overlay

1. Run **Aspect-Slope Bivariate Overlay** from the Processing Toolbox.
2. Pick your **Slope raster + band**, **slope unit**, and **Aspect raster + band**. Both rasters must be on the exact same pixel grid (same rows/columns) — typically automatic if you ran Slope and Aspect on the same DEM.
3. Pick **Continuous** or **Classified** mode.
4. For Continuous mode, optionally set **Slope value ... maximum steepness** — a real slope number in your raster's unit (not 0–1) marking "fully saturated"; leave at `0` to auto-use the 95th percentile of your data. A practical anchor: use a Van Zuidam threshold (70%/35° = "Steep and above", 140%/55° = "Very Steep and above").
5. Optionally pick a **Hillshade raster + band** (generate it first via Raster > Analysis > Hillshade from the same DEM) and set **Hillshade blend strength** (default `0.6`) to give the output real relief shading instead of flat brightness. Leave the Hillshade parameter empty to keep the original flat-brightness behavior.
6. Optionally set **Save legend image to file** to keep a permanent copy of the color-wheel/swatch-grid legend (otherwise it's written to the OS temp folder).
7. Run. A new 4-band (RGB+Alpha) raster is added to the map, plus an HTML legend preview in the Results Viewer — the legend is required reading, since a plain RGB raster has no classified attributes for QGIS to build a legend from automatically, and it always shows constant-brightness colors even if Hillshade blending was used.

| Parameter | Description |
|---|---|
| Slope / Aspect raster layer + band | The two required input layers; must be on the same pixel grid. |
| Slope unit | Degree (°) or Percent (%) — must match the source raster. |
| Hillshade raster + band (optional) | Real relief shading to modulate brightness; must be on the same grid. Omit for the original flat-brightness look. |
| Hillshade blend strength | `0` = ignore hillshade (default look), `1` = brightness purely from hillshade, default `0.6`. Only used if a Hillshade raster is provided. |
| Overlay mode | Continuous (smooth HSV wheel) or Classified (Van Zuidam × compass lookup table). |
| Compass scheme | 4 or 8 directions (Classified mode only). |
| Slope value for maximum steepness | Real slope number (not 0–1) treated as full saturation; `0` = auto (95th percentile). Continuous mode only. |
| Save legend image to file | Optional permanent save path for the legend PNG. |

#### Why the bivariate overlay is different

The other two algorithms only *restyle* an existing layer. This one *creates a new raster*, because QGIS's renderers can only map one pixel value to one color — there's no built-in way to combine two input rasters into a single color live. So the color is computed pixel-by-pixel with GDAL + numpy and written out as an ordinary 4-band GeoTIFF, which is why it runs at full resolution (not a decimated preview sample like the other two) and can take longer on large DEMs.

Each output pixel's Red/Green/Blue bands jointly encode one HSV-derived color — they are not independently meaningful the way, say, a satellite image's separate spectral bands are. The Alpha band is a transparency flag only (255 = valid, 0 = NoData). For the actual slope/aspect numbers at a point, use QGIS's Identify tool on the original Slope/Aspect layers, which remain loaded separately in the project.

By default the HSV "Value" (brightness) channel is held constant, so the output looks flat/2D — it only encodes hue and saturation. The optional Hillshade parameter drives Value from real relief shading instead, at a strength you control (0–1), so the map gains a genuine 3D look while keeping the aspect/slope color coding on top (see [References](#references) — Kennelly & Kimerling).

## How it works (short version)

**Slope:** the raster band is opened with GDAL and read at a decimated resolution (~1,000,000 pixels) to find the actual maximum value (for a sanity check) and build the histogram preview. The 7 Van Zuidam breakpoints are fixed by the classification scheme itself (not data-driven); the top class is closed with `+infinity`. A `QgsColorRampShader` (Discrete) is built from these breakpoints and the chosen ramp, wrapped in a `QgsSingleBandPseudoColorRenderer`, and applied to the layer.

**Aspect:** breakpoints are generated for the chosen 4- or 8-direction scheme, each class centered on its compass direction; a cyclic HSV color wheel is generated to match. Flat/sentinel pixels are marked NoData on the layer (display-only). A `QgsColorRampShader` (Discrete) is built and applied the same way as above. If enabled, a decimated sample is read to build the compass-rose preview.

Both symbology algorithms also set `classificationMin()`/`classificationMax()` on the renderer — this prevents a real QGIS behavior where reopening Layer Properties > Symbology without this set causes the dialog to silently recompute and overwrite the applied classes (see `CHANGELOG.md` for details, confirmed against QGIS's own source).

**Aspect-Slope Bivariate Overlay:** all rasters (Slope, Aspect, and optionally Hillshade) are opened with GDAL at full resolution (dimensions must match exactly). Aspect is mapped to Hue (0–360° around the color wheel) and slope is mapped to Saturation, either continuously (`slope / slope_max`, clipped 0–1) or via the Van Zuidam × compass lookup table in Classified mode. Value (brightness) is either held constant, or — if a Hillshade layer was supplied — blended as `(1 - blend) * 0.95 + blend * hillshade_normalized`, where `hillshade_normalized` auto-detects whether the input is a 0–255 Byte raster or already 0–1 and rescales accordingly. HSV is converted to RGB (`matplotlib.colors.hsv_to_rgb`, with a manual numpy fallback), written as a 4-band Byte GeoTIFF (RGB + Alpha, `ALPHA=YES`, `PHOTOMETRIC=RGB`) via `gdal.GetDriverByName("GTiff").Create()`, and loaded into the project as an ordinary Multiband Color layer — no custom renderer needed. A separate HTML/PNG legend (compass wheel or swatch grid) is generated with matplotlib since the raster itself carries no classification metadata for QGIS to build a legend from; it always renders at constant brightness regardless of Hillshade blending, with a note added when Hillshade was used.

## References

The Aspect-Slope Bivariate Overlay follows a cartographic technique with a long history, rather than a new invention:

- Moellering, H., and A. J. Kimerling (1990). *A New Digital Slope-Aspect Display Process*. Cartography and Geographic Information Systems, 17(2), 151–159. — the original "MKS-ASPECT" hue-for-aspect scheme.
- Brewer, C. A., and K. A. Marlow (1993). *Color Representation of Aspect and Slope Simultaneously*. Proceedings, Auto-Carto 11, 328–337. — refined the scheme with a saturation-for-slope dimension using the HVC color system; the most commonly cited reference for this technique. ([online reprint](https://sites.psu.edu/cbrewer/home/fugitive-publications/color-for-aspect-slope-mapping/))
- Esri, *Aspect-slope map*, ArcGIS Blog / Mapping Center (2008, updated for ArcGIS 10). ([link](https://www.esri.com/arcgis-blog/products/product/mapping/aspect-slope-map)) — a widely used implementation of the Moellering/Kimerling + Brewer/Marlow scheme as a fixed 25-class lookup table (4 slope classes × 8 directions + flat).
- Kennelly, P. J., and A. J. Kimerling (2001). *Modifications of Marion Grelot's hill-shading method for tri-variable choropleth maps*. Cartography and Geographic Information Science, 28(2), 111–123 — layer tints with aspect-variant luminosity; basis for this plugin's optional Hillshade-blended brightness (v1.2).

This algorithm follows the same hue-for-aspect / saturation-for-slope principle, but differs in a few implementation choices: the Continuous mode uses a smooth HSV gradient instead of a fixed ~25-class palette, the default saturation stretch uses the 95th percentile of the input data (a common remote-sensing convention) rather than a fixed slope ceiling, and brightness/Value can optionally be driven by a real Hillshade raster instead of a fixed lightness sequence per class.

## Requirements

- QGIS 3.18+ (uses `QgsColorRampShader.createColorRamp()` and the modern `Qgis.*` enum namespace; tested on 3.44).
- GDAL with Python bindings (`osgeo.gdal`) — bundled with QGIS. The Aspect-Slope Bivariate Overlay requires this to open rasters directly and write the new GeoTIFF; if it's missing, that algorithm raises a clear error (the other two algorithms don't need it).
- `numpy` — bundled with QGIS.
- `matplotlib` — optional. Needed for the histogram/compass-rose previews (Van Zuidam/Aspect algorithms) and the legend preview (Bivariate Overlay, which is otherwise skipped with a warning if matplotlib is missing). Most QGIS installations already ship it.

## Roadmap / ideas

- Other terrain overlay algorithms in the same spirit as the bivariate overlay — no specific plan yet, kept in mind by naming this one "Aspect-Slope" rather than a generic "bivariate overlay" name, to leave room for siblings (ideas discussed: TRI/TPI/Roughness classification, Curvature classification, Hypsometric/elevation tinting, TPI-based landform classification).
- A dedicated Aspect algorithm color-ramp picker (currently a fixed cyclic wheel).
- An optional boundary-inclusivity toggle (`lower <= value < upper` vs the current native `lower < value <= upper`), simulated via an epsilon-shift on breakpoints, if requested.
- Proper `.ts`/`.qm` translation files for non-English UI.

Contributions and issue reports are welcome once this is published — see below.

## License

GNU General Public License v3.0 or later — see [`LICENSE`](LICENSE). This is required for eventual listing on the official [QGIS Plugin Repository](https://plugins.qgis.org/), which only accepts GPL-compatible plugins.

## Authors / Credits

**Muhammad Fatahillah Mubarak** — project author
Email: fatahillah.mubarak@gmail.com
LinkedIn: [linkedin.com/in/mfatahillahm](https://www.linkedin.com/in/mfatahillahm)
Portfolio: [bit.ly/portofolio-muhammadfatahillah](https://bit.ly/portofolio-muhammadfatahillah)

**Claude (Anthropic)** — AI coding assistant, co-developed both algorithms (classification logic, QGIS Processing/plugin architecture, compass-rose/histogram previews) and this documentation together with the author.

If you use or build on this plugin, a credit/link back is appreciated but not required by the license.

## Publishing to GitHub

See [`PUBLISHING.md`](PUBLISHING.md) for a step-by-step guide (including first-time GitHub/git setup).
