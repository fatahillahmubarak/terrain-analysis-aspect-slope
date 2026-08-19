# -*- coding: utf-8 -*-
"""
Processing provider: groups this plugin's algorithms under a single
entry in the Processing Toolbox -- Van Zuidam (1983) Slope
Classification Symbology, Aspect Direction Symbology, and the
Aspect-Slope Bivariate Overlay. Other terrain-related overlay tools
(e.g. a future Slope+Hillshade combination) can be registered here
later without touching plugin.py.

Copyright (C) 2026  Muhammad Fatahillah Mubarak
Licensed under the GNU General Public License v3.0 or later.
"""

import os

from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

from .algorithms.van_zuidam_slope_algorithm import VanZuidamSlopeSymbologyAlgorithm
from .algorithms.aspect_direction_algorithm import AspectDirectionSymbologyAlgorithm
from .algorithms.aspect_slope_bivariate_overlay_algorithm import AspectSlopeBivariateOverlayAlgorithm


class TerrainAnalysisSymbologyProvider(QgsProcessingProvider):

    def loadAlgorithms(self):
        self.addAlgorithm(VanZuidamSlopeSymbologyAlgorithm())
        self.addAlgorithm(AspectDirectionSymbologyAlgorithm())
        self.addAlgorithm(AspectSlopeBivariateOverlayAlgorithm())

    def id(self):
        return "terrainanalysissymbology"

    def name(self):
        return "Terrain Analysis Symbology"

    def longName(self):
        return "Terrain Analysis Symbology"

    def icon(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        return super().icon()
