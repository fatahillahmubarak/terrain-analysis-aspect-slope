# -*- coding: utf-8 -*-
"""
Terrain Analysis Symbology
--------------------------
A QGIS plugin that adds two Processing algorithms for symbolizing
terrain-derived rasters: Van Zuidam (1983) Slope Classification and
Aspect Direction (Compass Classes).

Copyright (C) 2026  Muhammad Fatahillah Mubarak
Licensed under the GNU General Public License v3.0 or later.
See the LICENSE file in the project root for the full license text.

This file is required by QGIS's plugin loader: it must define
classFactory(iface) at the top level of the plugin's __init__.py.
"""


def classFactory(iface):
    from .plugin import TerrainAnalysisSymbologyPlugin
    return TerrainAnalysisSymbologyPlugin(iface)
