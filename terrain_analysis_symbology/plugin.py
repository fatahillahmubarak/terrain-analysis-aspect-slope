# -*- coding: utf-8 -*-
"""
Main plugin class. QGIS calls initGui() when the plugin is enabled and
unload() when it's disabled/uninstalled. This plugin has no toolbar
button or menu entry by design -- its only job is to register a
Processing provider (a group of algorithms) so its tools show up under
Processing Toolbox > Terrain Analysis Symbology.

Copyright (C) 2026  Muhammad Fatahillah Mubarak
Licensed under the GNU General Public License v3.0 or later.
"""

from qgis.core import QgsApplication

from .provider import TerrainAnalysisSymbologyProvider


class TerrainAnalysisSymbologyPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.provider = None

    def initProcessing(self):
        self.provider = TerrainAnalysisSymbologyProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()

    def unload(self):
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
