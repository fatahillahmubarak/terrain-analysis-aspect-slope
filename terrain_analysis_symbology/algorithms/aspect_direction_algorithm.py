# -*- coding: utf-8 -*-
"""
Aspect Direction Symbology -- Processing algorithm
======================================================

Classifies and symbolizes an ASPECT raster (slope-facing direction,
output of the QGIS/GDAL Slope/Aspect tool) into compass-direction
classes (4 or 8 directions), each class centered on its cardinal or
intercardinal direction, rather than on raw degree breakpoints starting
at 0.

Flat/no-aspect pixels (commonly -9999 or -1, depending on the tool used
to generate the aspect raster) are excluded from the symbology (marked
as NoData on the layer, display-only -- the source file on disk is not
modified) so they don't get wrongly lumped into a direction class.

Because 'North' straddles the 0/360 degree seam, it is represented as
two boundary entries with identical color and label in the underlying
QgsColorRampShader -- this may show as two 'North' rows in the layer
legend. This is a known cosmetic limitation of representing circular
data with QGIS's linear Discrete color-ramp shader, not a bug.

Aspect data is circular (0 degrees = 360 degrees), so a regular linear
color ramp (e.g. RdYlGn) would not wrap around correctly -- its "red"
and "green" ends would not connect even though 0/360 is the same
direction. This tool instead uses a built-in cyclic HSV color wheel
(hue makes a full 360-degree turn, so the first and last class colors
connect smoothly).

An optional compass-rose (polar) preview shows the proportion of the
raster falling into each direction class, oriented like a real compass
(0 degrees/North at the top, clockwise) -- more meaningful for circular
data than a linear bar histogram.

Copyright (C) 2026  Muhammad Fatahillah Mubarak
Licensed under the GNU General Public License v3.0 or later.
See the LICENSE file in the project root for the full license text.
"""

import os
import colorsys
import tempfile

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterBand,
    QgsProcessingParameterEnum,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterNumber,
    QgsProcessingOutputRasterLayer,
    QgsProcessingOutputHtml,
    QgsProcessingException,
    QgsColorRampShader,
    QgsRasterShader,
    QgsSingleBandPseudoColorRenderer,
    QgsMessageLog,
    Qgis,
)

try:
    from osgeo import gdal
    import numpy as np
    _HAS_GDAL_NUMPY = True
except Exception:
    _HAS_GDAL_NUMPY = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _HAS_MPL = True
except Exception:
    _HAS_MPL = False


# Direction names in order + how many classes each scheme has.
DIRECTION_SETS = {
    4: ["North", "East", "South", "West"],
    8: ["North", "Northeast", "East", "Southeast",
        "South", "Southwest", "West", "Northwest"],
}


def _fmt(v):
    """Format a number: plain integer if it's a whole number, 1 decimal
    otherwise."""
    r = round(v, 1)
    if r == int(r):
        return str(int(r))
    return f"{r:g}"


def build_direction_classes(n):
    """
    Build the ascending list of (upper_bound, direction_name) breakpoints
    for an n-direction (4 or 8) compass classification scheme.

    Each class is centered exactly on its compass direction, with a
    width of 360/n degrees. Because the "North" class straddles the
    0/360 seam, it is represented as TWO entries: one at the start of
    the list (0 to +half) and one at the end (360-half to 360) -- see
    the module docstring's note on the resulting legend-row duplication.

    Returns: (entries, centers, half)
      entries = list[(upper_bound: float, name: str)], ascending.
      centers = dict{name: center_degree}, used for labels & plotting.
      half = half the class width (degrees).
    """
    names = DIRECTION_SETS[n]
    step = 360.0 / n
    half = step / 2.0
    centers = {name: i * step for i, name in enumerate(names)}

    entries = [(half, names[0])]  # "North" segment near 0 degrees
    for i in range(1, n):
        entries.append((centers[names[i]] + half, names[i]))
    entries.append((360.0, names[0]))  # "North" segment near 360 degrees
    return entries, centers, half


def build_direction_colors(names, hue_offset=1.0 / 3.0):
    """
    Cyclic HSV colors, one per direction, automatically connecting
    smoothly at 0/360 degrees since hue makes one full turn. hue_offset
    shifts the wheel so "North" lands near green (an aesthetic default
    choice only).

    Returns: dict{name: QColor}, dict{name: (r, g, b) float 0-1 (for matplotlib)}
    """
    n = len(names)
    qcolors, rgbs = {}, {}
    for i, name in enumerate(names):
        hue = ((i / n) + hue_offset) % 1.0
        r, g, b = colorsys.hsv_to_rgb(hue, 0.80, 0.92)
        rgbs[name] = (r, g, b)
        qcolors[name] = QColor(int(r * 255), int(g * 255), int(b * 255))
    return qcolors, rgbs


def _direction_label(name, center, half):
    lo, hi = center - half, center + half
    return f"{name} ({_fmt(lo)} deg - {_fmt(hi)} deg)"


class AspectDirectionSymbologyAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    BAND = "BAND"
    SCHEME = "SCHEME"
    EXCLUDE_FLAT = "EXCLUDE_FLAT"
    FLATVALUE = "FLATVALUE"
    SHOWPLOT = "SHOWPLOT"
    OUTPUT = "OUTPUT"
    HTML_OUTPUT = "HTML_OUTPUT"

    SCHEME_LABELS = [
        "4 Directions (N, E, S, W)",
        "8 Directions (N, NE, E, SE, S, SW, W, NW)",
    ]

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        return AspectDirectionSymbologyAlgorithm()

    def name(self):
        return "aspectdirectionsymbology"

    def displayName(self):
        return self.tr("Aspect Direction Symbology (Compass Classes)")

    def group(self):
        return self.tr("Terrain Analysis Symbology")

    def groupId(self):
        return "terrainanalysissymbology"

    def shortHelpString(self):
        return self.tr(
            "Classify and symbolize an ASPECT raster (0-360 degrees) into "
            "compass-direction classes (4 or 8 directions), each class "
            "centered on its cardinal/intercardinal direction.\n\n"
            "Flat/no-aspect pixels (commonly -9999 or -1, depending on the "
            "tool used to generate the aspect raster) are excluded from "
            "the symbology (marked as NoData on the layer) so they don't "
            "get wrongly lumped into a direction class.\n\n"
            "Because 'North' straddles the 0/360 degree seam, it is "
            "represented as two boundary entries with identical color and "
            "label -- this may show as two 'North' rows in the legend. "
            "This is a known cosmetic limitation of representing circular "
            "data with QGIS's linear Discrete color-ramp shader.\n\n"
            "Class boundaries: each class uses the convention 'lower < value "
            "<= upper' (lower bound excluded, upper bound included). This is "
            "hardcoded in QGIS's rendering engine (QgsColorRampShader, "
            "Discrete mode) and cannot be changed via any parameter here -- "
            "it only matters if a pixel value lands exactly on a breakpoint "
            "(e.g. an aspect raster rounded to whole degrees).\n\n"
            "An optional compass-rose (polar) preview shows the proportion "
            "of the raster falling into each direction class."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT, self.tr("Aspect raster layer")))
        self.addParameter(QgsProcessingParameterBand(
            self.BAND, self.tr("Band"), parentLayerParameterName=self.INPUT, defaultValue=1))
        self.addParameter(QgsProcessingParameterEnum(
            self.SCHEME, self.tr("Classification scheme"),
            options=self.SCHEME_LABELS, defaultValue=1))  # default: 8 directions
        self.addParameter(QgsProcessingParameterBoolean(
            self.EXCLUDE_FLAT, self.tr("Exclude flat/no-aspect pixels (mark as NoData)"),
            defaultValue=True))
        self.addParameter(QgsProcessingParameterNumber(
            self.FLATVALUE, self.tr("Flat/no-aspect sentinel value in the source raster"),
            type=QgsProcessingParameterNumber.Double, defaultValue=-9999.0))
        self.addParameter(QgsProcessingParameterBoolean(
            self.SHOWPLOT, self.tr("Show compass-rose preview (proportion per direction)"),
            defaultValue=True))
        self.addOutput(QgsProcessingOutputRasterLayer(
            self.OUTPUT, self.tr("Symbolized aspect layer")))
        self.addOutput(QgsProcessingOutputHtml(
            self.HTML_OUTPUT, self.tr("Compass-rose preview (HTML)")))

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        band_no = self.parameterAsInt(parameters, self.BAND, context)
        scheme_idx = self.parameterAsEnum(parameters, self.SCHEME, context)
        n_classes = 4 if scheme_idx == 0 else 8
        exclude_flat = self.parameterAsBoolean(parameters, self.EXCLUDE_FLAT, context)
        flat_value = self.parameterAsDouble(parameters, self.FLATVALUE, context)
        showplot = self.parameterAsBoolean(parameters, self.SHOWPLOT, context)

        if layer is None:
            raise QgsProcessingException(self.tr("Input raster layer is invalid."))

        provider = layer.dataProvider()

        if exclude_flat:
            provider.setNoDataValue(band_no, flat_value)
            feedback.pushInfo(
                f"Value {flat_value} on band {band_no} marked as NoData "
                f"(flat/no-aspect) for display purposes only -- the source "
                f"file on disk is not modified."
            )

        entries, centers, half = build_direction_classes(n_classes)
        names_ordered = DIRECTION_SETS[n_classes]
        qcolors, rgbs = build_direction_colors(names_ordered)

        items = []
        for upper, name in entries:
            label = _direction_label(name, centers[name], half)
            items.append(QgsColorRampShader.ColorRampItem(upper, qcolors[name], label))

        shader = QgsColorRampShader()
        shader.setColorRampType(QgsColorRampShader.Discrete)
        shader.setColorRampItemList(items)

        # classificationMode + sourceColorRamp: just so the "Mode" dropdown
        # and ramp preview in the Symbology dialog look sane if opened
        # ("Custom" doesn't exist as an option in QGIS's API).
        shader.setClassificationMode(Qgis.ShaderClassificationMethod.EqualInterval)
        shader.setSourceColorRamp(shader.createColorRamp())

        raster_shader = QgsRasterShader()
        raster_shader.setRasterShaderFunction(shader)

        renderer = QgsSingleBandPseudoColorRenderer(provider, band_no, raster_shader)

        # THE ACTUAL ROOT CAUSE of custom classes getting silently replaced
        # when reopening Layer Properties > Symbology (confirmed by reading
        # QGIS's own source, qgssinglebandpseudocolorrendererwidget.cpp):
        # the widget reads renderer.classificationMin()/Max() to populate
        # the dialog's Min/Max fields. If left unset (NaN), the widget
        # assumes "no min/max yet", recomputes them fresh from the raw
        # raster data, and that recomputation path unconditionally calls
        # classify() -- regenerating a brand new classification and
        # overwriting our custom class list. This happens automatically the
        # moment the dialog opens, no click required. Setting these
        # explicitly prevents that entirely.
        renderer.setClassificationMin(0.0)
        renderer.setClassificationMax(360.0)

        layer.setRenderer(renderer)
        layer.triggerRepaint()

        feedback.pushInfo(
            f"Applied {n_classes}-direction Discrete symbology to band {band_no}."
        )

        html_path = None
        if showplot:
            if not (_HAS_GDAL_NUMPY and _HAS_MPL):
                feedback.pushWarning(
                    "GDAL/numpy or matplotlib not available -- skipping "
                    "compass-rose preview. Symbology was still applied."
                )
            else:
                try:
                    html_path = self._build_rose_html(
                        layer, band_no, entries, names_ordered, centers,
                        rgbs, exclude_flat, flat_value, feedback
                    )
                except Exception as e:
                    feedback.pushWarning(
                        f"Could not build compass-rose preview ({e}). "
                        f"Symbology was still applied successfully."
                    )
                    QgsMessageLog.logMessage(
                        f"Aspect Direction Symbology: histogram preview failed: {e}",
                        level=Qgis.Warning,
                    )

        results = {self.OUTPUT: layer.id()}
        if html_path:
            results[self.HTML_OUTPUT] = html_path
        return results

    def _build_rose_html(self, layer, band_no, entries, names_ordered, centers,
                          rgbs, exclude_flat, flat_value, feedback):
        ds = gdal.Open(layer.source())
        if ds is None:
            raise RuntimeError("GDAL could not open the raster source.")
        band = ds.GetRasterBand(band_no)
        nodata = band.GetNoDataValue()

        target_px = 500_000
        xsize, ysize = ds.RasterXSize, ds.RasterYSize
        total_px = max(xsize * ysize, 1)
        scale = min(1.0, (target_px / total_px) ** 0.5)
        bx = max(1, int(xsize * scale))
        by = max(1, int(ysize * scale))

        arr = band.ReadAsArray(buf_xsize=bx, buf_ysize=by).astype(float)
        valid = np.isfinite(arr)
        if nodata is not None:
            valid &= (arr != nodata)
        if exclude_flat:
            valid &= (arr != flat_value)
        valid &= (arr >= 0) & (arr <= 360)
        sample = arr[valid]

        if sample.size == 0:
            feedback.pushWarning(
                "No valid aspect pixels found for the compass-rose preview "
                "(after excluding NoData/flat values)."
            )
            return None

        upper_bounds = np.array([e[0] for e in entries])
        names_arr = np.array([e[1] for e in entries], dtype=object)
        idx = np.searchsorted(upper_bounds, sample, side="left")
        idx = np.clip(idx, 0, len(entries) - 1)
        assigned = names_arr[idx]

        unique, counts = np.unique(assigned, return_counts=True)
        proportions = dict(zip(unique, counts / counts.sum()))

        theta = np.radians([centers[name] for name in names_ordered])
        values = [proportions.get(name, 0.0) * 100.0 for name in names_ordered]
        bar_colors = [rgbs[name] for name in names_ordered]
        width = np.radians(360.0 / len(names_ordered)) * 0.92

        fig = plt.figure(figsize=(5.5, 5.5))
        ax = fig.add_subplot(111, projection="polar")
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.bar(theta, values, width=width, color=bar_colors,
               edgecolor="white", linewidth=1.2, alpha=0.95)
        ax.set_xticks(np.radians([centers[n] for n in names_ordered]))
        ax.set_xticklabels(names_ordered, fontsize=9)
        ax.set_ylabel("")
        ax.set_title("Aspect direction distribution (% of valid pixels)", pad=20, fontsize=11)

        tmp_dir = tempfile.mkdtemp(prefix="aspect_rose_")
        png_path = os.path.join(tmp_dir, "aspect_rose.png")
        fig.savefig(png_path, dpi=140, bbox_inches="tight")
        plt.close(fig)

        rows = "".join(
            f"<tr><td>{name}</td><td>{proportions.get(name, 0.0) * 100:.1f}%</td></tr>"
            for name in names_ordered
        )
        html_path = os.path.join(tmp_dir, "aspect_rose.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Aspect direction preview</title>
<style>
body {{ font-family: sans-serif; margin: 16px; }}
table {{ border-collapse: collapse; margin-top: 12px; }}
td {{ padding: 4px 12px; border-bottom: 1px solid #ddd; }}
</style></head>
<body>
<h3>Aspect direction distribution</h3>
<img src="file:///{png_path}" style="max-width:520px;">
<table><tr><th>Direction</th><th>% of valid pixels</th></tr>{rows}</table>
</body></html>""")
        return html_path
