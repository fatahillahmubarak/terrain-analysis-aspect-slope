# -*- coding: utf-8 -*-
"""
Van Zuidam (1983) Slope Classification Symbology -- Processing algorithm
============================================================================

Classifies a slope raster (output of the QGIS/GDAL Slope tool) into the
7 standard geomorphological classes defined by Van Zuidam (1983) -- Flat,
Gently Sloping, Sloping, Moderately Steep, Steep, Very Steep, Extremely
Steep -- then applies a Singleband Pseudocolor (Discrete) renderer with
legend labels showing the class NAME plus its value range. No new file
is created; only the input layer's symbology changes.

Reference: Van Zuidam, R. A. (1983). Guide to geomorphologic aerial
photographic interpretation and mapping. International Institute for
Aerial Survey and Earth Sciences (ITC).

The "Elevation Difference (m)" column from the original table is
intentionally not used here -- classification is based on the slope
value alone.

Copyright (C) 2026  Muhammad Fatahillah Mubarak
Licensed under the GNU General Public License v3.0 or later.
See the LICENSE file in the project root for the full license text.
"""

import os
import math
import tempfile

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterBand,
    QgsProcessingParameterEnum,
    QgsProcessingParameterBoolean,
    QgsProcessingOutputRasterLayer,
    QgsProcessingOutputHtml,
    QgsProcessingException,
    QgsSingleBandPseudoColorRenderer,
    QgsRasterShader,
    QgsColorRampShader,
    QgsStyle,
    Qgis,
)

import numpy as np

try:
    from osgeo import gdal
except ImportError:
    gdal = None


def _fmt(v):
    """Format a breakpoint number: plain integer if it's (near) a whole
    number, otherwise 2 decimals with no trailing zeros. Explicitly
    handles +/-infinity (the open-ended "Extremely Steep" class uses
    float("inf") as its upper bound -- see the note on open-ended
    classes below); round()/int() cannot accept infinity, so this must
    be guarded here for any code path that formats every breakpoint,
    including the last one (e.g. the class-summary log line)."""
    if math.isinf(v):
        return "inf" if v > 0 else "-inf"
    if abs(v - round(v)) < 1e-6:
        return f"{int(round(v))}"
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _class_label(i, n, name, lo, hi, unit_symbol):
    """Legend label: class name + value range. The last (open-ended)
    class is written as "> lo", matching the original Van Zuidam table
    notation, rather than the raster's actual sampled maximum value."""
    if i == n - 1:
        return f"{name} (> {_fmt(lo)}{unit_symbol})"
    return f"{name} ({_fmt(lo)} - {_fmt(hi)}{unit_symbol})"


# (name, percent_lo, percent_hi, degree_lo, degree_hi) -- *_hi = None means open-ended
VAN_ZUIDAM_CLASSES = [
    ("Flat",              0,   2,    0,  2),
    ("Gently Sloping",    2,   7,    2,  4),
    ("Sloping",           7,   15,   4,  8),
    ("Moderately Steep",  15,  30,   8,  16),
    ("Steep",             30,  70,   16, 35),
    ("Very Steep",        70,  140,  35, 55),
    ("Extremely Steep",   140, None, 55, None),
]


class VanZuidamSlopeSymbologyAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    BAND = "BAND"
    UNIT = "UNIT"
    RAMP = "RAMP"
    INVERT = "INVERT"
    SHOWPLOT = "SHOWPLOT"
    OUTPUT = "OUTPUT"
    HTML_OUTPUT = "HTML_OUTPUT"

    UNIT_LABELS = ["Degree (°)", "Percent (%)"]

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        return VanZuidamSlopeSymbologyAlgorithm()

    def name(self):
        return "vanzuidamslopesymbology"

    def displayName(self):
        return self.tr("Van Zuidam (1983) Slope Classification Symbology")

    def group(self):
        return self.tr("Terrain Analysis Symbology")

    def groupId(self):
        return "terrainanalysissymbology"

    def shortHelpString(self):
        return self.tr(
            "Classifies a slope raster (output of the QGIS/GDAL Slope tool) "
            "into the 7 standard Van Zuidam (1983) classes -- Flat, Gently "
            "Sloping, Sloping, Moderately Steep, Steep, Very Steep, Extremely "
            "Steep -- then applies a Singleband Pseudocolor (Discrete) "
            "renderer with class-name + value-range legend labels. No new "
            "file is created, only the layer's symbology changes.\n\n"
            "Pick your slope raster's unit (Degree or Percent) correctly -- "
            "the two columns of the Van Zuidam table use different "
            "thresholds, so picking the wrong unit will misclassify the "
            "entire raster.\n\n"
            "Class boundaries: each class uses the convention 'lower < "
            "value <= upper' (lower bound excluded, upper bound included). "
            "This is hardcoded in QGIS's rendering engine (QgsColorRampShader, "
            "Discrete mode) and cannot be changed via any parameter here -- "
            "it only matters if a pixel value lands exactly on a breakpoint "
            "(e.g. a slope raster rounded to whole degrees/percent).\n\n"
            "The top class ('Extremely Steep') has no fixed upper bound in "
            "the original scheme (>140% / >55 deg), so it is closed with "
            "+infinity (not the raster's sampled maximum value), so that "
            "extreme pixels possibly missed by the decimated sample still "
            "get colored -- the legend label still reads '> 140%' etc, not "
            "'inf'.\n\n"
            "Default color ramp is RdYlGn with direction reversed (Reverse "
            "ramp direction = on) so that Flat reads green and Extremely "
            "Steep reads red -- turn that option off if the chosen ramp's "
            "default direction already matches without reversing."
        )

    def flags(self):
        return super().flags() | QgsProcessingAlgorithm.FlagNoThreading

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(self.INPUT, self.tr("Slope raster layer"))
        )
        self.addParameter(
            QgsProcessingParameterBand(self.BAND, self.tr("Band"), 1, self.INPUT)
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.UNIT, self.tr("Slope unit"),
                options=self.UNIT_LABELS, defaultValue=0,
            )
        )
        ramp_names = QgsStyle.defaultStyle().colorRampNames()
        default_idx = ramp_names.index("RdYlGn") if "RdYlGn" in ramp_names else 0
        self.addParameter(
            QgsProcessingParameterEnum(
                self.RAMP, self.tr("Color ramp"),
                options=ramp_names, defaultValue=default_idx,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.INVERT, self.tr("Reverse ramp direction"), defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.SHOWPLOT, self.tr("Show histogram preview (requires matplotlib)"),
                defaultValue=True,
            )
        )
        self.addOutput(
            QgsProcessingOutputRasterLayer(self.OUTPUT, self.tr("Symbolized layer"))
        )
        self.addOutput(
            QgsProcessingOutputHtml(self.HTML_OUTPUT, self.tr("Histogram preview"))
        )

    def processAlgorithm(self, parameters, context, feedback):
        if gdal is None:
            raise QgsProcessingException(
                self.tr("The GDAL module (osgeo.gdal) was not found in this QGIS environment.")
            )

        layer = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        band_no = self.parameterAsInt(parameters, self.BAND, context)
        unit_idx = self.parameterAsEnum(parameters, self.UNIT, context)
        unit_label = self.UNIT_LABELS[unit_idx] if 0 <= unit_idx < len(self.UNIT_LABELS) else self.UNIT_LABELS[0]
        is_percent = (unit_label == "Percent (%)")
        unit_symbol = "%" if is_percent else "°"

        ramp_idx = self.parameterAsEnum(parameters, self.RAMP, context)
        ramp_names = QgsStyle.defaultStyle().colorRampNames()
        ramp_name = ramp_names[ramp_idx] if 0 <= ramp_idx < len(ramp_names) else "RdYlGn"
        ramp = QgsStyle.defaultStyle().colorRamp(ramp_name)
        if ramp is None:
            raise QgsProcessingException(self.tr(f"Color ramp '{ramp_name}' was not found in QgsStyle."))
        invert = self.parameterAsBoolean(parameters, self.INVERT, context)
        show_plot = self.parameterAsBoolean(parameters, self.SHOWPLOT, context)

        if layer is None:
            raise QgsProcessingException(self.tr("Input raster layer is invalid."))

        feedback.pushInfo(f"Reading band {band_no} from: {layer.source()}")
        ds = gdal.Open(layer.source())
        if ds is None:
            raise QgsProcessingException(
                self.tr(
                    "GDAL could not open this layer's source directly "
                    "(it may be a temporary/in-memory layer). Save it as a "
                    "raster file (GeoTIFF) first, then reload it."
                )
            )
        band = ds.GetRasterBand(band_no)
        nodata = band.GetNoDataValue()

        # Decimated read -- used here only to find the actual maximum value
        # (for the sanity check below) and for the histogram preview. The
        # open-ended top class is closed with +infinity, not this sample's
        # maximum -- see the note in _apply_symbology().
        xsize, ysize = band.XSize, band.YSize
        target_px = 1_000_000
        scale = min(1.0, (target_px / float(xsize * ysize)) ** 0.5)
        buf_x = max(1, int(xsize * scale))
        buf_y = max(1, int(ysize * scale))
        feedback.pushInfo(
            f"Original size {xsize}x{ysize} -> read decimated at {buf_x}x{buf_y} "
            f"for the maximum-value check & histogram preview."
        )
        arr = band.ReadAsArray(buf_xsize=buf_x, buf_ysize=buf_y).astype(np.float64)

        if nodata is not None:
            mask = ~np.isclose(arr, nodata)
        else:
            mask = np.ones_like(arr, dtype=bool)
        mask &= np.isfinite(arr)
        sample = arr[mask]
        if sample.size == 0:
            raise QgsProcessingException(self.tr("No valid pixels (all NoData) found on this band."))

        vmax = float(sample.max())

        # Sanity check: slope in degrees can theoretically never exceed 90.
        if not is_percent and vmax > 90:
            feedback.pushWarning(
                f"The maximum value found ({vmax:.2f}) exceeds the theoretical "
                f"limit for the Degree unit (90). Double-check whether this "
                f"raster is really in degrees, not percent."
            )

        # Build the classes for the selected unit.
        classes = []  # list of (name, lo, hi) -- hi=None for the last class (temporarily)
        for name, p_lo, p_hi, d_lo, d_hi in VAN_ZUIDAM_CLASSES:
            lo, hi = (p_lo, p_hi) if is_percent else (d_lo, d_hi)
            classes.append((name, float(lo), None if hi is None else float(hi)))

        # Close the open-ended class ("Extremely Steep") with +infinity,
        # NOT the decimated sample's maximum value. QGIS itself does this
        # for the topmost Discrete class (see qgscolorrampshader.cpp:
        # entryValues.push_back(std::numeric_limits<double>::infinity()))
        # -- using the sample's maximum instead carries a real risk: the
        # decimated read (buf_x/buf_y smaller than the source raster) can
        # miss a pixel whose true value is higher than anything captured
        # by the sample, so that pixel would fall above the computed
        # breakpoint ("overflow" in shade()) and end up uncolored
        # (transparent) at full resolution. +infinity removes this risk
        # entirely, since no value can ever exceed it.
        last_name, last_lo, _ = classes[-1]
        classes[-1] = (last_name, last_lo, float("inf"))

        # Numeric breakpoints: [0, class-1 upper, ..., class-7 upper].
        # Kept strictly increasing in case the raster turns out to be very
        # flat (its maximum value falls below one of the Van Zuidam
        # thresholds).
        breaks = [0.0]
        for _, _, hi in classes:
            b = hi
            if b <= breaks[-1]:
                b = breaks[-1] + 1e-6
            breaks.append(b)

        feedback.pushInfo(
            f"Van Zuidam classes ({unit_label}): " +
            ", ".join(f"{c[0]} [{_fmt(c[1])}-{_fmt(c[2])}]" for c in classes)
        )

        self._apply_symbology(layer, band_no, classes, breaks, unit_symbol, ramp, invert)
        feedback.pushInfo("Singleband Pseudocolor (Discrete) symbology applied successfully.")

        results = {self.OUTPUT: layer.id()}

        if show_plot:
            feedback.pushInfo("Building histogram preview...")
            html_path = self._build_histogram_html(sample, breaks, classes, unit_label, unit_symbol, ramp, invert, feedback)
            if html_path:
                results[self.HTML_OUTPUT] = html_path
                feedback.pushInfo(f"Histogram preview: {html_path}")

        return results

    @staticmethod
    def _apply_symbology(layer, band_no, classes, breaks, unit_symbol, ramp, invert):
        n = len(classes)
        shader = QgsColorRampShader()
        shader.setColorRampType(QgsColorRampShader.Discrete)
        # (classificationMode is intentionally not set to "Custom" -- see
        # the note in the Natural Breaks tool: Qgis.ShaderClassificationMethod
        # has no "Custom" member, and it's irrelevant here since color items
        # are set directly via setColorRampItemList(), not classifyColorRamp())

        items = []
        for i, (name, lo, hi) in enumerate(classes):
            t = (i / (n - 1)) if n > 1 else 0.0
            if invert:
                t = 1.0 - t
            color = ramp.color(t)
            label = _class_label(i, n, name, lo, hi, unit_symbol)
            items.append(QgsColorRampShader.ColorRampItem(breaks[i + 1], color, label))
        shader.setColorRampItemList(items)

        # classificationMode + sourceColorRamp: just so the "Mode" dropdown
        # and ramp preview in the Symbology dialog look sane if opened
        # ("Custom" doesn't exist as an option in QGIS's API).
        shader.setClassificationMode(Qgis.ShaderClassificationMethod.EqualInterval)
        shader.setSourceColorRamp(shader.createColorRamp())

        raster_shader = QgsRasterShader()
        raster_shader.setRasterShaderFunction(shader)
        renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), band_no, raster_shader)

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
        # explicitly prevents that. breaks[0] (0) and breaks[-2] (the
        # second-to-last class's upper bound, NOT infinity -- this number is
        # purely informational for the dialog, it does not affect the
        # shader's actual breakpoints) are used as the min/max stand-in.
        renderer.setClassificationMin(breaks[0])
        renderer.setClassificationMax(breaks[-2])

        layer.setRenderer(renderer)
        layer.triggerRepaint()
        layer.emitStyleChanged()

    @staticmethod
    def _build_histogram_html(sample, breaks, classes, unit_label, unit_symbol, ramp, invert, feedback):
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            feedback.pushWarning(
                "matplotlib was not found in this QGIS Python environment -- "
                "skipping the histogram preview (raster symbology was still applied)."
            )
            return None

        n = len(classes)
        fig, ax = plt.subplots(figsize=(8.2, 4.4), dpi=120)
        counts, edges, patches = ax.hist(sample, bins=60, edgecolor="none")

        for patch, edge_left in zip(patches, edges[:-1]):
            cls = int(np.searchsorted(breaks, edge_left, side="right")) - 1
            cls = max(0, min(cls, n - 1))
            t = (cls / (n - 1)) if n > 1 else 0.0
            if invert:
                t = 1.0 - t
            c = ramp.color(t)
            patch.set_facecolor((c.redF(), c.greenF(), c.blueF()))

        for b in breaks[1:-1]:
            ax.axvline(b, color="#21295C", linestyle="--", linewidth=1)

        ax.set_title(f"Van Zuidam (1983) Slope Classification -- {unit_label}")
        ax.set_xlabel(f"Slope value ({unit_symbol})")
        ax.set_ylabel("Frequency")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()

        tmp_dir = tempfile.mkdtemp(prefix="van_zuidam_preview_")
        png_path = os.path.join(tmp_dir, "histogram.png")
        fig.savefig(png_path)
        plt.close(fig)

        rows = "".join(
            f"<tr><td>{name}</td><td>{_class_label(i, n, name, lo, hi, unit_symbol).split('(', 1)[1][:-1]}</td></tr>"
            for i, (name, lo, hi) in enumerate(classes)
        )
        html_path = os.path.join(tmp_dir, "histogram.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(
                "<html><body style='margin:12px;font-family:sans-serif'>"
                f"<h3>Van Zuidam (1983) Slope Classification &mdash; {unit_label}</h3>"
                f"<img src='file:///{png_path}' style='max-width:100%'>"
                "<table border='1' cellpadding='4' cellspacing='0' style='margin-top:10px'>"
                "<tr><th>Class</th><th>Range</th></tr>" + rows + "</table>"
                "</body></html>"
            )
        return html_path
