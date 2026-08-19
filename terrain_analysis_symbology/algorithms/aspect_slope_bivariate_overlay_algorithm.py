# -*- coding: utf-8 -*-
r"""
Aspect-Slope Bivariate Overlay -- Processing algorithm
============================================================

Combines a SLOPE raster and an ASPECT raster into ONE new RGB raster,
where:
  - Hue        = aspect direction (0-360 degrees, circular)
  - Saturation = slope steepness (steeper = more saturated/vivid,
                 flatter = paler/whiter)
This is a "bivariate color map" -- 2 variables encoded at once in 1 color.

BACKGROUND & PURPOSE
---------------------
Slope and Aspect are usually analyzed SEPARATELY (one map each), even
though they are physically linked: every steep pixel also necessarily
faces some direction. Viewed separately, a question like "are the steep
slopes in this area mostly facing North or South?" is hard to answer from
2 single-variable maps alone -- you'd have to keep switching layers and
memorizing values in your head.

This overlay answers that question directly in 1 map: a single glance
tells you BOTH (1) how steep an area is (from color saturation) AND (2)
which direction that steepness faces (from hue) -- with no manual overlay/
layer-switching needed. Useful for landslide-susceptibility analysis (a
steep slope facing a particular direction can be wetter/drier depending on
sun exposure and prevailing rain direction), directional erosion
potential, or simply communicating land-form patterns more concisely.

How to read the result: PALE/WHITE = flat (direction becomes irrelevant/
not visible there). VIVID/SATURATED COLOR = steep -- match the hue to the
compass wheel in the HTML legend to see which direction it faces (red-
orange ~ North, green ~ East, cyan ~ South, blue-purple ~ West, with
gradations in between for the diagonal directions).

REFERENCES / PRIOR WORK
-------------------------
Encoding aspect as hue and slope as saturation is a long-established
cartographic technique, not a new invention:
  - Moellering, H., and A. J. Kimerling (1990). A New Digital
    Slope-Aspect Display Process. Cartography and Geographic Information
    Systems, 17(2), 151-159. (the original "MKS-ASPECT" scheme)
  - Brewer, C. A., and K. A. Marlow (1993). Color Representation of
    Aspect and Slope Simultaneously. Proceedings, Auto-Carto 11,
    328-337. (refined the hue/saturation/lightness scheme using the HVC
    color system; still the most commonly cited reference for this
    technique)
  - Esri's ArcGIS "Aspect-slope map" workflow (Mapping Center, since
    2008) implements the Moellering/Kimerling + Brewer/Marlow scheme as a
    discrete 25-class lookup table.
  - Kennelly, P. J., and A. J. Kimerling (2001). Modifications of Marion
    Grelot's hill-shading with an example using a computer program.
    Cartography and Geographic Information Science, 28(2), 111-123 (and
    related work on "layer tints with aspect-variant luminosity") --
    the basis for this algorithm's optional hillshade-modulated
    brightness (Value channel driven by real relief shading rather than
    held constant).
This algorithm follows the same hue-for-aspect / saturation-for-slope
principle. It differs from the classic scheme in two ways: the Continuous
mode uses a smooth HSV gradient rather than a fixed set of ~25 discrete
classes, and the default saturation normalization uses the 95th
percentile of the input data (a common remote-sensing "percentile
stretch" convention) rather than a fixed slope ceiling.

KEY DIFFERENCE FROM THIS PLUGIN'S OTHER ALGORITHMS
-----------------------------------------------------
Van Zuidam Slope Symbology and Aspect Direction Symbology ONLY change the
SYMBOLOGY of an existing layer (no new file). This algorithm is DIFFERENT:
it MUST create a new raster file (a 4-band RGB+Alpha GeoTIFF), because
QGIS's built-in renderers (QgsColorRampShader etc.) can only map ONE pixel
value to one color -- there is no native way to combine 2 input rasters
into 1 color through a normal renderer. So the color is "baked" directly
into the pixels via GDAL + numpy, and the resulting raster is then loaded
as an ordinary Multiband Color layer (no shader/classification needed).

Practical consequence: this algorithm processes the raster at FULL
RESOLUTION (not a decimated sample like the other two algorithms), because
the output must be real pixel data, not just a preview. For large DEMs
(tens of millions of pixels) this can take noticeably longer and use more
memory -- that's expected, not a bug.

TWO MODES
---------
1. Continuous (HSV color wheel) -- default. Hue = raw aspect degrees
   (continuous), Saturation = slope/slope_max (clipped to 0-1). slope_max
   DEFAULTS to the 95th percentile of the data (NOT the absolute maximum)
   -- testing on real data showed that using the absolute maximum makes
   almost the entire raster look pale/nearly white (a handful of extreme
   outlier pixels crush the saturation range for the vast majority of
   pixels down to nearly zero). Value/brightness is held constant.
2. Classified (Van Zuidam x Compass classes) -- a discrete version, reusing
   the classification used by this plugin's other two algorithms (7 Van
   Zuidam slope classes, 4/8 compass directions for aspect). Each class
   combination gets one solid color from a lookup table -- similar to a
   checkerboard-style legend.

OPTIONAL: HILLSHADE-MODULATED BRIGHTNESS
---------------------------------------------
By default, brightness (the HSV "Value" channel) is held constant, so the
output only encodes hue (aspect) and saturation (slope) -- it looks
"flat," with no sense of 3D terrain shape. If you also provide a
**Hillshade raster** (an ordinary QGIS Hillshade output, or any raster
of relief shading), this algorithm blends it into the Value channel, so
the result looks like a real relief map (ridges catch light, valleys are
shaded) while STILL showing the aspect/slope color coding on top. This is
the same principle used by Kennelly & Kimerling (their "layer tints with
aspect-variant luminosity" technique) -- see References.

This is entirely OPTIONAL and fully backward-compatible: if you don't
provide a Hillshade layer, the output is identical to before (constant
brightness). If you do provide one, use "Hillshade blend strength" (0-1)
to control how strongly it affects brightness: 0 = ignore it completely
(same as not providing one), 1 = brightness comes entirely from the
hillshade (can look quite dark in shadowed areas), the default 0.6 is a
middle ground that keeps colors identifiable everywhere while still
showing clear relief shape. The Hillshade raster must also be on the
exact same pixel grid as Slope and Aspect (see grid requirement below) --
generate it in QGIS with Raster > Analysis > Hillshade from the SAME DEM
used for your Slope/Aspect rasters, so all three line up automatically.

ABOUT THE "SLOPE_MAX" PARAMETER (a common source of confusion -- read this!)
-----------------------------------------------------------------------------
This value is NOT a 0-1 scale -- enter a REAL slope number, in the SAME
UNIT as your slope raster (percent OR degree, matching the "Slope unit"
parameter). In other words: pixels with a slope value >= this number are
drawn at FULL Saturation (the most vivid/saturated color), and pixels below
it get proportional saturation (the further below slope_max, the paler).

Why entering "1" makes everything full saturation: it means "a slope of
just 1% (or 1 degree) already counts as the steepest possible" -- in real
data, almost every non-flat pixel has a value greater than 1, so ALL of
them get clipped straight to saturation=1.0 (everything vivid, no
gradation). Enter a LARGE number instead (e.g. 500) and the opposite
happens: almost every pixel looks pale because real slope values are far
below 500, and only super-extreme pixels look saturated.

A PRACTICAL WAY TO PICK THIS NUMBER -- tie it to the Van Zuidam (1983)
thresholds used by this plugin's Slope Symbology algorithm:

    Threshold      | Percent (%) | Degree (deg)
    ---------------|-------------|-------------
    Sloping        |     15      |      8
    Steep          |     70      |     35
    Very Steep     |    140      |     55
    (Extremely Steep has no upper bound -- not relevant to enter here)

Example: enter "70" (percent) if you want everything "Steep and above" to
render as full-color/most vivid, with the rest (Flat through Moderately
Steep) getting a pale-to-medium gradient. Enter "140" for a wider gradient
range (only "Very Steep and above" is full-color). The SMALLER the number
you enter, the FASTER/more aggressively colors reach full saturation (more
area looks vivid); the LARGER the number, the GENTLER the gradient (only
more extreme slopes look vivid).

The default (enter 0 = auto-detect) uses the 95th percentile of YOUR OWN
data -- see above for why not the absolute maximum.

WHAT THE 4 BANDS IN THE OUTPUT RASTER CONTAIN
--------------------------------------------------
The result is NOT an ordinary analytical raster (unlike most "multiband"
rasters, where each band is 1 independent variable -- e.g. a satellite
image where band 1 = raw Red, band 2 = raw NIR, etc., each of which CAN be
read on its own directly). Here:

  - Band 1 (Red), Band 2 (Green), Band 3 (Blue): TOGETHER they form 1
    combined color from an HSV->RGB conversion. They CANNOT be read
    separately as "band 1 = slope" or "band 2 = aspect" -- all three must
    be viewed AT ONCE as a single color to be interpreted (using the
    compass-wheel / swatch-grid legend).
  - Band 4 (Alpha): not data, just a display-transparency flag -- 255
    means the pixel is valid (rendered normally), 0 means NoData (the
    pixel is transparent/hidden from view).

If you need the ACTUAL slope/aspect value at a given point (not just its
color), use QGIS's Identify tool on the ORIGINAL Slope/Aspect layers (not
on this overlay's RGB layer) -- both original layers stay loaded separately
in your project after running this algorithm, so you can compare them
directly.

REQUIREMENT: ALL INPUT RASTERS MUST BE ON THE SAME GRID
-------------------------------------------------------------
Slope and Aspect MUST have EXACTLY the same pixel dimensions (rows x
columns) -- this algorithm does NOT do automatic resampling/alignment.
This is intentional: resampling circular ASPECT data with standard methods
(bilinear, etc.) can produce mathematically wrong values (averaging 359
degrees and 1 degree should give ~0 degrees, not ~180 degrees). If your
slope and aspect rasters aren't already on the same grid, make sure both
were generated from the same DEM with the same resolution/extent (usually
automatic if you run the Slope and Aspect tools on the same DEM in QGIS),
or align them manually first (Raster > Alignment > Align Rasters).

If you also provide an optional Hillshade raster, it must be on that same
grid too -- same reasoning, and generating it from the same DEM as above
makes this automatic.

ABOUT FLAT/NODATA VALUES
-----------------------------
Flat pixels (slope=0) automatically turn out nearly white/gray in
Continuous mode, with NO special handling needed for the aspect sentinel
value -- because saturation is controlled by slope, not aspect, so if
slope~0 the color is automatically pale regardless of the aspect value
(including a -9999/-1 "no direction" sentinel). What still needs separate
handling is TRUE NoData (pixels outside the data's actual coverage, e.g.
raster edges) -- these pixels are made TRANSPARENT (alpha=0) in the 4th
band of the output raster.

LEGEND PREVIEW & HOW TO SAVE IT
------------------------------------
Because the result is a pure RGB raster (not a classified raster with
attributes), QGIS's standard legend won't explain anything about it. That's
why this algorithm ALWAYS builds an HTML preview containing a "color
wheel" (Continuous mode) or a "swatch grid" (Classified mode) so the
result can be interpreted -- it appears automatically in the Results
Viewer panel after Run. Note: the legend always shows hue/saturation at
CONSTANT brightness, even if you blended in a Hillshade layer -- the
legend explains the color coding, not the brightness/shading, which will
vary across your actual map.

By default this file is saved to the OS temp folder (lost if the system
cleans it up). There are 2 ways to save it permanently:
  1. EASIEST: fill in the optional "Save legend image to file" parameter
     with your chosen .png location/name BEFORE clicking Run -- this
     algorithm will automatically copy the legend image there as well.
  2. Manual: open the HTML link from the Results Viewer in a browser,
     right-click the image -> "Save image as...". Or find the "legend.png"
     file in the temp folder path shown in the log/Results Viewer and copy
     it manually.

Copyright (C) 2026  Muhammad Fatahillah Mubarak
Licensed under the GNU General Public License v3.0 or later.
See the LICENSE file in the project root for the full license text.
"""

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterBand,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterFileDestination,
    QgsProcessingOutputHtml,
    QgsProcessingException,
)

import os
import shutil
import tempfile
import numpy as np

try:
    from osgeo import gdal
except ImportError:
    gdal = None

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import hsv_to_rgb
    _HAS_MPL = True
except Exception:
    _HAS_MPL = False


# ---------- classification table (same as the Van Zuidam Slope algorithm) ----------
# (name, percent_lo, percent_hi, degree_lo, degree_hi) -- *_hi = None -> open-ended
VAN_ZUIDAM_CLASSES = [
    ("Flat",              0,   2,    0,  2),
    ("Gently Sloping",    2,   7,    2,  4),
    ("Sloping",           7,   15,   4,  8),
    ("Moderately Steep",  15,  30,   8,  16),
    ("Steep",             30,  70,   16, 35),
    ("Very Steep",        70,  140,  35, 55),
    ("Extremely Steep",   140, None, 55, None),
]

# ---------- direction table (same as the Aspect Direction algorithm) ----------
DIRECTION_SETS = {
    4: ["North", "East", "South", "West"],
    8: ["North", "Northeast", "East", "Southeast",
        "South", "Southwest", "West", "Northwest"],
}


def _van_zuidam_breaks(is_percent):
    """Slope breakpoints [0, ..., inf] for the given unit, same as the
    Van Zuidam Slope algorithm (last class closed with +infinity)."""
    breaks = [0.0]
    for name, p_lo, p_hi, d_lo, d_hi in VAN_ZUIDAM_CLASSES:
        hi = (p_hi if is_percent else d_hi)
        b = float(hi) if hi is not None else float("inf")
        if b <= breaks[-1]:
            b = breaks[-1] + 1e-6
        breaks.append(b)
    return breaks  # length = 8 (7 classes + starting boundary 0)


def _direction_breaks(n):
    """Direction breakpoints [half, ..., 360] for the given n-direction
    scheme (4/8), same as the Aspect Direction algorithm (North is split
    between the start and end of the list)."""
    step = 360.0 / n
    half = step / 2.0
    centers = [i * step for i in range(n)]
    breaks = [half]
    for c in centers[1:]:
        breaks.append(c + half)
    breaks.append(360.0)
    return breaks, centers, half


class AspectSlopeBivariateOverlayAlgorithm(QgsProcessingAlgorithm):
    INPUT_SLOPE = "INPUT_SLOPE"
    SLOPE_BAND = "SLOPE_BAND"
    SLOPE_UNIT = "SLOPE_UNIT"
    SLOPE_MAX = "SLOPE_MAX"
    INPUT_ASPECT = "INPUT_ASPECT"
    ASPECT_BAND = "ASPECT_BAND"
    INPUT_HILLSHADE = "INPUT_HILLSHADE"
    HILLSHADE_BAND = "HILLSHADE_BAND"
    HILLSHADE_BLEND = "HILLSHADE_BLEND"
    MODE = "MODE"
    SCHEME = "SCHEME"
    OUTPUT = "OUTPUT"
    HTML_OUTPUT = "HTML_OUTPUT"
    LEGEND_OUTPUT = "LEGEND_OUTPUT"

    UNIT_LABELS = ["Degree (°)", "Percent (%)"]
    MODE_LABELS = ["Continuous (HSV color wheel)", "Classified (Van Zuidam x Compass classes)"]
    SCHEME_LABELS = ["4 Directions (N, E, S, W)", "8 Directions (N, NE, E, SE, S, SW, W, NW)"]

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        return AspectSlopeBivariateOverlayAlgorithm()

    def name(self):
        return "aspectslopebivariateoverlay"

    def displayName(self):
        return self.tr("Aspect-Slope Bivariate Overlay")

    def group(self):
        return self.tr("Terrain Analysis Symbology")

    def groupId(self):
        return "terrainanalysissymbology"

    def shortHelpString(self):
        return self.tr(
            "Combines a Slope raster and an Aspect raster into ONE new "
            "RGB(A) raster: Hue = aspect direction, Saturation = slope "
            "steepness. Follows the aspect-slope mapping technique "
            "described by Moellering & Kimerling (1990) and refined by "
            "Brewer & Marlow (1993) -- see the plugin README for full "
            "references.\n\n"
            "UNLIKE this plugin's other two algorithms, this one creates a "
            "NEW FILE (not just a symbology change), because QGIS has no "
            "renderer that can combine 2 input rasters into 1 color live.\n\n"
            "Slope & Aspect MUST have exactly the same pixel dimensions "
            "(rows x columns) -- there is no automatic resampling (circular "
            "aspect data can become mathematically wrong if resampled "
            "carelessly).\n\n"
            "'Continuous' mode produces a smooth color gradient (like a "
            "compass wheel). 'Classified' mode uses the 7 Van Zuidam "
            "classes x 4/8 compass directions, with each combination "
            "getting a solid color from a lookup table.\n\n"
            "For Continuous mode: 'Slope value ... maximum steepness' is "
            "NOT a 0-1 scale -- enter a real slope number in your raster's "
            "own unit (e.g. 70 for 70%, or 35 for 35 degrees). Pixels >= "
            "that number are drawn most saturated/vivid; the smaller the "
            "number, the faster colors reach full saturation (more area "
            "looks vivid). Tip: use a Van Zuidam threshold, e.g. 70%/35deg "
            "= 'Steep and above', 140%/55deg = 'Very Steep and above'. The "
            "default (0=auto) uses the 95TH PERCENTILE of the data, not the "
            "absolute maximum -- real data shows the absolute maximum is "
            "usually an extreme outlier pixel that makes almost the whole "
            "raster look pale.\n\n"
            "Output bands: Bands 1-3 (R,G,B) are LINKED TOGETHER to form 1 "
            "combined color (cannot be read separately as 'band=slope' or "
            "'band=aspect'); Band 4 (Alpha) is just a transparency flag "
            "(255=valid, 0=NoData), not data. For actual values, check the "
            "original Slope/Aspect layers (they stay loaded separately).\n\n"
            "OPTIONAL: provide a Hillshade raster (from Raster > Analysis > "
            "Hillshade, same DEM/grid as Slope & Aspect) to modulate "
            "brightness with real relief shading instead of a flat constant "
            "-- the result looks like a proper 3D relief map while still "
            "showing the aspect/slope color coding. 'Hillshade blend "
            "strength' controls how much: 0 = ignore it (identical to not "
            "providing one), 1 = brightness purely from hillshade (can be "
            "dark in shadow), default 0.6 balances both. The legend preview "
            "always shows constant-brightness hue/saturation only; it does "
            "not reflect hillshade shading in your actual output.\n\n"
            "Processing runs at the raster's FULL RESOLUTION (not a "
            "decimated sample), so it can be slower for large DEMs. An "
            "HTML preview (color wheel / swatch grid) is always built "
            "because a pure RGB raster has no automatic legend -- fill in "
            "the optional 'Save legend image to file' parameter to keep it "
            "permanently, otherwise the file lives in the OS temp folder."
        )

    def flags(self):
        return super().flags() | QgsProcessingAlgorithm.FlagNoThreading

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT_SLOPE, self.tr("Slope raster layer")))
        self.addParameter(QgsProcessingParameterBand(
            self.SLOPE_BAND, self.tr("Slope band"), 1, self.INPUT_SLOPE))
        self.addParameter(QgsProcessingParameterEnum(
            self.SLOPE_UNIT, self.tr("Slope unit"),
            options=self.UNIT_LABELS, defaultValue=0))
        self.addParameter(QgsProcessingParameterNumber(
            self.SLOPE_MAX, self.tr(
                "Slope value, in the SAME UNIT as your raster (e.g. 70 for 70%, "
                "or 35 for 35deg), treated as 'fully saturated / most vivid color' "
                "(Continuous mode only). NOT a 0-1 scale. 0 = auto-detect as the "
                "95th percentile of the data. Tip: use a Van Zuidam threshold, "
                "e.g. 70%/35deg = 'Steep and above', 140%/55deg = 'Very Steep and "
                "above' -- see help for the full table."),
            type=QgsProcessingParameterNumber.Double, defaultValue=0.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT_ASPECT, self.tr("Aspect raster layer")))
        self.addParameter(QgsProcessingParameterBand(
            self.ASPECT_BAND, self.tr("Aspect band"), 1, self.INPUT_ASPECT))
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT_HILLSHADE, self.tr(
                "Hillshade raster layer (optional -- modulates brightness "
                "with real relief shading instead of a flat constant)"),
            optional=True))
        self.addParameter(QgsProcessingParameterBand(
            self.HILLSHADE_BAND, self.tr("Hillshade band"), 1,
            self.INPUT_HILLSHADE, optional=True))
        self.addParameter(QgsProcessingParameterNumber(
            self.HILLSHADE_BLEND, self.tr(
                "Hillshade blend strength (0 = ignore hillshade, same as "
                "not providing one; 1 = brightness purely from hillshade). "
                "Only used if a Hillshade raster is provided above."),
            type=QgsProcessingParameterNumber.Double, defaultValue=0.6,
            minValue=0.0, maxValue=1.0))
        self.addParameter(QgsProcessingParameterEnum(
            self.MODE, self.tr("Overlay mode"),
            options=self.MODE_LABELS, defaultValue=0))
        self.addParameter(QgsProcessingParameterEnum(
            self.SCHEME, self.tr("Compass scheme (Classified mode only)"),
            options=self.SCHEME_LABELS, defaultValue=1))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT, self.tr("Bivariate overlay (RGB)")))
        legend_dest_param = QgsProcessingParameterFileDestination(
            self.LEGEND_OUTPUT, self.tr("Save legend image to file (optional, PNG)"),
            fileFilter="PNG files (*.png)", optional=True, createByDefault=False)
        self.addParameter(legend_dest_param)
        self.addOutput(QgsProcessingOutputHtml(
            self.HTML_OUTPUT, self.tr("Legend preview")))

    def processAlgorithm(self, parameters, context, feedback):
        if gdal is None:
            raise QgsProcessingException(
                self.tr("The GDAL module (osgeo.gdal) was not found in this QGIS environment.")
            )

        slope_layer = self.parameterAsRasterLayer(parameters, self.INPUT_SLOPE, context)
        slope_band_no = self.parameterAsInt(parameters, self.SLOPE_BAND, context)
        unit_idx = self.parameterAsEnum(parameters, self.SLOPE_UNIT, context)
        is_percent = (unit_idx == 1)
        unit_symbol = "%" if is_percent else "°"
        slope_max_param = self.parameterAsDouble(parameters, self.SLOPE_MAX, context)

        aspect_layer = self.parameterAsRasterLayer(parameters, self.INPUT_ASPECT, context)
        aspect_band_no = self.parameterAsInt(parameters, self.ASPECT_BAND, context)

        hillshade_layer = self.parameterAsRasterLayer(parameters, self.INPUT_HILLSHADE, context)
        hillshade_band_no = self.parameterAsInt(parameters, self.HILLSHADE_BAND, context) or 1
        hillshade_blend = self.parameterAsDouble(parameters, self.HILLSHADE_BLEND, context)

        legend_output_override = self.parameterAsFileOutput(parameters, self.LEGEND_OUTPUT, context)
        if not legend_output_override:
            legend_output_override = None

        mode_idx = self.parameterAsEnum(parameters, self.MODE, context)
        is_classified = (mode_idx == 1)
        scheme_idx = self.parameterAsEnum(parameters, self.SCHEME, context)
        n_dir = 4 if scheme_idx == 0 else 8

        output_path = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        if slope_layer is None or aspect_layer is None:
            raise QgsProcessingException(self.tr("Invalid input raster layer(s)."))

        ds_slope = gdal.Open(slope_layer.source())
        ds_aspect = gdal.Open(aspect_layer.source())
        if ds_slope is None or ds_aspect is None:
            raise QgsProcessingException(
                self.tr(
                    "GDAL could not open one of the layer sources directly "
                    "(it may be a temporary/in-memory layer). Save it as a "
                    "raster file (GeoTIFF) first, then reload it."
                )
            )

        # ---- Must be on the same grid: check pixel dimensions match exactly ----
        sx, sy = ds_slope.RasterXSize, ds_slope.RasterYSize
        ax, ay = ds_aspect.RasterXSize, ds_aspect.RasterYSize
        if (sx, sy) != (ax, ay):
            raise QgsProcessingException(
                self.tr(
                    f"Slope raster ({sx}x{sy} px) and Aspect raster ({ax}x{ay} px) "
                    f"have DIFFERENT dimensions. This algorithm requires both to be "
                    f"on the exact same grid (same rows & columns) -- there is no "
                    f"automatic resampling because circular aspect data can become "
                    f"wrong if resampled carelessly. Make sure both rasters come "
                    f"from the same DEM with the same extent/resolution, or align "
                    f"them manually first (Raster > Alignment > Align Rasters)."
                )
            )

        feedback.pushInfo(f"Raster size: {sx}x{sy} pixels (processed at full resolution).")

        # ---- Optional Hillshade: open + check grid if provided ----
        ds_hillshade = None
        if hillshade_layer is not None:
            ds_hillshade = gdal.Open(hillshade_layer.source())
            if ds_hillshade is None:
                raise QgsProcessingException(
                    self.tr(
                        "GDAL could not open the Hillshade layer source directly "
                        "(it may be a temporary/in-memory layer). Save it as a "
                        "raster file (GeoTIFF) first, then reload it."
                    )
                )
            hx, hy = ds_hillshade.RasterXSize, ds_hillshade.RasterYSize
            if (hx, hy) != (sx, sy):
                raise QgsProcessingException(
                    self.tr(
                        f"Hillshade raster ({hx}x{hy} px) does not match the "
                        f"Slope/Aspect grid ({sx}x{sy} px). Generate the Hillshade "
                        f"from the SAME DEM as your Slope/Aspect rasters so all "
                        f"three line up on the same grid."
                    )
                )

        slope_band = ds_slope.GetRasterBand(slope_band_no)
        aspect_band = ds_aspect.GetRasterBand(aspect_band_no)
        slope_nodata = slope_band.GetNoDataValue()
        aspect_nodata = aspect_band.GetNoDataValue()

        feedback.pushInfo("Reading slope & aspect rasters at full resolution...")
        slope_arr = slope_band.ReadAsArray().astype(np.float32)
        aspect_arr = aspect_band.ReadAsArray().astype(np.float32)
        feedback.setProgress(20)

        valid = np.isfinite(slope_arr) & np.isfinite(aspect_arr)
        if slope_nodata is not None:
            valid &= ~np.isclose(slope_arr, slope_nodata)
        if aspect_nodata is not None:
            valid &= ~np.isclose(aspect_arr, aspect_nodata)

        # ---- Optional Hillshade: read + normalize to 0-1 ----
        hillshade_norm = None
        if ds_hillshade is not None:
            feedback.pushInfo("Reading hillshade raster at full resolution...")
            hillshade_band = ds_hillshade.GetRasterBand(hillshade_band_no)
            hillshade_nodata = hillshade_band.GetNoDataValue()
            hillshade_arr = hillshade_band.ReadAsArray().astype(np.float32)

            hs_valid = np.isfinite(hillshade_arr)
            if hillshade_nodata is not None:
                hs_valid &= ~np.isclose(hillshade_arr, hillshade_nodata)
            valid &= hs_valid

            # Hillshade is usually a Byte raster (0-255, e.g. QGIS's own
            # Hillshade tool); some workflows produce it already normalized
            # to 0-1. Auto-detect which one we have from the actual data
            # range rather than assuming a fixed data type.
            sample_max = float(np.nanmax(np.where(hs_valid, hillshade_arr, np.nan))) if np.any(hs_valid) else 0.0
            if sample_max > 1.5:
                hillshade_norm = np.clip(hillshade_arr / 255.0, 0.0, 1.0)
            else:
                hillshade_norm = np.clip(hillshade_arr, 0.0, 1.0)
            feedback.pushInfo(
                f"Hillshade blend strength: {hillshade_blend:.2f} "
                f"(0=ignored, 1=brightness purely from hillshade)."
            )

        if not np.any(valid):
            raise QgsProcessingException(self.tr("No valid pixels (all NoData) in the input raster(s)."))

        # slope_max: auto-detect if param = 0. DELIBERATELY uses the 95th
        # percentile of the data, NOT the absolute maximum -- proven via
        # testing on real data: real-world slope value distributions are
        # HEAVILY skewed (the majority of pixels sit in a reasonable range,
        # but a handful of extreme outlier pixels, e.g. steep cliffs or DEM
        # artifacts, have values far above the bulk of the data). Using the
        # absolute maximum as the Saturation=1.0 reference crushes nearly
        # the entire raster into a pale/near-white look (saturation squeezed
        # into a tiny range) -- almost no visual contrast at all. The 95th
        # percentile gives much better visual contrast for the majority of
        # the area, at the cost of extreme pixels (above the 95th percentile)
        # being clipped to full Saturation=1.0 (still reasonable: pixels
        # that steep genuinely are "the steepest" visually). This is a
        # common remote-sensing convention (similar to a "2%-98% stretch"
        # for imagery) -- see the README.
        if slope_max_param > 0:
            slope_max = float(slope_max_param)
        else:
            slope_max = float(np.nanpercentile(np.where(valid, slope_arr, np.nan), 95))
            if slope_max <= 0:
                slope_max = 1.0
        feedback.pushInfo(
            f"Slope max used to normalize Saturation: {slope_max:.2f}{unit_symbol}"
            + (" (auto-detected: 95th percentile of the data)" if slope_max_param <= 0 else " (manual)")
        )

        feedback.setProgress(35)

        if not is_classified:
            h, s = self._continuous_hs(slope_arr, aspect_arr, slope_max)
        else:
            h, s = self._classified_hs(slope_arr, aspect_arr, is_percent, n_dir)

        # Value/brightness: constant 0.95 by default (matches pre-hillshade
        # behavior exactly), or blended with the hillshade if one was given.
        if hillshade_norm is not None:
            v = np.clip((1.0 - hillshade_blend) * 0.95 + hillshade_blend * hillshade_norm, 0.0, 1.0)
        else:
            v = np.full_like(h, 0.95, dtype=np.float32)

        feedback.setProgress(60)

        hsv = np.stack([h, s, v], axis=-1)
        if _HAS_MPL:
            rgb = hsv_to_rgb(hsv)  # vectorized, (rows, cols, 3), 0-1
        else:
            rgb = self._hsv_to_rgb_manual(hsv)
        rgb_u8 = np.clip(rgb * 255.0, 0, 255).astype(np.uint8)
        alpha_u8 = np.where(valid, 255, 0).astype(np.uint8)

        feedback.setProgress(75)
        feedback.pushInfo(f"Writing new RGBA raster to: {output_path}")

        driver = gdal.GetDriverByName("GTiff")
        out_ds = driver.Create(output_path, sx, sy, 4, gdal.GDT_Byte,
                                options=["COMPRESS=DEFLATE", "PHOTOMETRIC=RGB", "ALPHA=YES"])
        out_ds.SetGeoTransform(ds_slope.GetGeoTransform())
        out_ds.SetProjection(ds_slope.GetProjection())

        for i, interp in enumerate([gdal.GCI_RedBand, gdal.GCI_GreenBand, gdal.GCI_BlueBand]):
            band = out_ds.GetRasterBand(i + 1)
            band.WriteArray(rgb_u8[:, :, i])
            band.SetColorInterpretation(interp)
        alpha_band = out_ds.GetRasterBand(4)
        alpha_band.WriteArray(alpha_u8)
        alpha_band.SetColorInterpretation(gdal.GCI_AlphaBand)
        out_ds.FlushCache()
        out_ds = None

        feedback.setProgress(90)
        feedback.pushInfo("Bivariate overlay raster created successfully.")

        results = {self.OUTPUT: output_path}

        try:
            html_path, png_path = self._build_legend_html(
                is_classified, slope_max, unit_symbol, is_percent, n_dir, feedback,
                hillshade_used=(hillshade_norm is not None)
            )
            if html_path:
                results[self.HTML_OUTPUT] = html_path
            if legend_output_override and png_path:
                dest = legend_output_override
                if not dest.lower().endswith(".png"):
                    dest += ".png"
                shutil.copy(png_path, dest)
                feedback.pushInfo(f"Legend image saved to: {dest}")
        except Exception as e:
            feedback.pushWarning(f"Failed to build legend preview ({e}). The output raster is still valid.")

        feedback.setProgress(100)
        return results

    # ---------- Hue/Saturation builders (Value/brightness handled separately -- see processAlgorithm) ----------
    @staticmethod
    def _continuous_hs(slope_arr, aspect_arr, slope_max):
        h = (np.mod(aspect_arr, 360.0)) / 360.0
        s = np.clip(slope_arr / slope_max, 0.0, 1.0)
        return h.astype(np.float32), s.astype(np.float32)

    @staticmethod
    def _classified_hs(slope_arr, aspect_arr, is_percent, n_dir):
        slope_breaks = np.array(_van_zuidam_breaks(is_percent), dtype=np.float64)  # len 8
        n_slope_classes = len(slope_breaks) - 1  # 7
        slope_idx = np.searchsorted(slope_breaks, slope_arr, side="left") - 1
        slope_idx = np.clip(slope_idx, 0, n_slope_classes - 1)

        dir_breaks, dir_centers, half = _direction_breaks(n_dir)
        dir_breaks = np.array(dir_breaks, dtype=np.float64)
        aspect_mod = np.mod(aspect_arr, 360.0)
        dir_idx_raw = np.searchsorted(dir_breaks, aspect_mod, side="left")
        dir_idx_raw = np.clip(dir_idx_raw, 0, len(dir_breaks) - 1)
        # last entry (360) & first entry (half) are both "North" (direction index 0)
        dir_idx = np.where(dir_idx_raw == len(dir_breaks) - 1, 0, dir_idx_raw)

        centers_arr = np.array(dir_centers, dtype=np.float64)
        h = centers_arr[dir_idx] / 360.0
        # saturation from slope class: index 0 (Flat) -> pale, last index -> vivid
        s = 0.15 + 0.85 * (slope_idx.astype(np.float64) / max(n_slope_classes - 1, 1))
        return h.astype(np.float32), s.astype(np.float32)

    @staticmethod
    def _hsv_to_rgb_manual(hsv):
        """Manual vectorized HSV->RGB fallback in case matplotlib isn't
        available (matplotlib usually ships with QGIS already)."""
        h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
        i = np.floor(h * 6.0).astype(int) % 6
        f = (h * 6.0) - np.floor(h * 6.0)
        p = v * (1.0 - s)
        q = v * (1.0 - f * s)
        t = v * (1.0 - (1.0 - f) * s)
        r = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5], [v, q, p, p, t, v])
        g = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5], [t, v, v, q, p, p])
        b = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5], [p, p, t, v, v, q])
        return np.stack([r, g, b], axis=-1)

    # ---------- legend preview ----------
    def _build_legend_html(self, is_classified, slope_max, unit_symbol, is_percent, n_dir, feedback,
                            hillshade_used=False):
        if not _HAS_MPL:
            feedback.pushWarning("matplotlib is not available -- skipping legend preview.")
            return None, None

        tmp_dir = tempfile.mkdtemp(prefix="bivariate_legend_")
        png_path = os.path.join(tmp_dir, "legend.png")

        if not is_classified:
            self._render_continuous_wheel(png_path, slope_max, unit_symbol)
            title = "Aspect-Slope Bivariate Overlay -- Continuous"
            body = (
                "<p>Hue = aspect direction (0-360&deg;, N at top, clockwise). "
                "Saturation = slope steepness, from pale (flat) at the center of "
                f"the wheel to vivid (steep, &ge; {slope_max:.1f}{unit_symbol}) at the rim.</p>"
            )
        else:
            names = DIRECTION_SETS[n_dir]
            self._render_classified_grid(png_path, names, is_percent)
            title = "Aspect-Slope Bivariate Overlay -- Classified"
            body = (
                "<p>Each cell = a combination of Van Zuidam class (row) x compass "
                "direction (column). Hue = direction, Saturation = steepness class "
                "(pale=Flat, vivid=Extremely Steep).</p>"
            )

        if hillshade_used:
            body += (
                "<p><i>Note: a Hillshade layer was blended into this output's "
                "brightness, so your actual map's light/dark shading (relief) "
                "will vary across the area -- this legend shows the hue/"
                "saturation color coding only, at constant brightness.</i></p>"
            )

        html_path = os.path.join(tmp_dir, "legend.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(
                "<html><body style='margin:12px;font-family:sans-serif'>"
                f"<h3>{title}</h3>{body}"
                f"<img src='file:///{png_path}' style='max-width:100%'>"
                "</body></html>"
            )
        return html_path, png_path

    @staticmethod
    def _render_continuous_wheel(png_path, slope_max, unit_symbol):
        size = 400
        yy, xx = np.mgrid[0:size, 0:size].astype(np.float64)
        cx = cy = size / 2.0
        x = (xx - cx) / (size / 2.0)
        y = (yy - cy) / (size / 2.0)
        r = np.sqrt(x ** 2 + y ** 2)
        theta = (np.degrees(np.arctan2(x, -y))) % 360.0

        h = theta / 360.0
        s = np.clip(r, 0.0, 1.0)
        v = np.full_like(h, 0.95)
        rgb = hsv_to_rgb(np.stack([h, s, v], axis=-1))
        alpha = (r <= 1.0).astype(np.float64)
        rgba = np.dstack([rgb, alpha])

        fig, ax = plt.subplots(figsize=(4.2, 4.2), dpi=110)
        ax.imshow(rgba, extent=(-1, 1, -1, 1))
        ax.set_xlim(-1.25, 1.25)
        ax.set_ylim(-1.25, 1.25)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.text(0, 1.12, "N", ha="center", va="bottom", fontsize=12, fontweight="bold")
        ax.text(0, -1.12, "S", ha="center", va="top", fontsize=12, fontweight="bold")
        ax.text(1.12, 0, "E", ha="left", va="center", fontsize=12, fontweight="bold")
        ax.text(-1.12, 0, "W", ha="right", va="center", fontsize=12, fontweight="bold")
        ax.text(0, 0.05, "flat", ha="center", va="bottom", fontsize=8, color="black")
        ax.text(0, 0.97, f">= {slope_max:.0f}{unit_symbol}", ha="center", va="bottom", fontsize=8, color="black")
        fig.tight_layout()
        fig.savefig(png_path, transparent=True)
        plt.close(fig)

    @staticmethod
    def _render_classified_grid(png_path, dir_names, is_percent):
        n_slope = len(VAN_ZUIDAM_CLASSES)
        n_dir = len(dir_names)
        dir_breaks, dir_centers, half = _direction_breaks(n_dir)

        grid = np.zeros((n_slope, n_dir, 3))
        for si in range(n_slope):
            s = 0.15 + 0.85 * (si / max(n_slope - 1, 1))
            for di in range(n_dir):
                h = dir_centers[di] / 360.0
                grid[n_slope - 1 - si, di] = hsv_to_rgb(np.array([h, s, 0.95]))

        fig, ax = plt.subplots(figsize=(1.1 * n_dir + 1.5, 0.55 * n_slope + 1.0), dpi=110)
        ax.imshow(grid, aspect="auto")
        ax.set_xticks(range(n_dir))
        ax.set_xticklabels(dir_names, rotation=45, ha="right", fontsize=8)
        slope_names = [c[0] for c in VAN_ZUIDAM_CLASSES][::-1]
        ax.set_yticks(range(n_slope))
        ax.set_yticklabels(slope_names, fontsize=8)
        ax.set_title("Slope class (rows) x Direction (columns)", fontsize=10)
        fig.tight_layout()
        fig.savefig(png_path)
        plt.close(fig)
