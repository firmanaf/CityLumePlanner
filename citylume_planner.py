# -*- coding: utf-8 -*-

import os
import re
import csv
import json
import math
import shutil
import tempfile
import traceback
from pathlib import Path
from collections import Counter, defaultdict

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsApplication,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterString,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFeatureSink,
    QgsProcessingOutputFile,
    QgsProcessingOutputFolder,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsRectangle,
    QgsWkbTypes,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsVectorLayer,
    QgsFeatureSink,
    QgsSpatialIndex,
    QgsVectorFileWriter,
    QgsRasterLayer,
    QgsRaster,
    QgsProcessingUtils,
    edit,
)

import processing


class CityLumeUrbanDynamics(QgsProcessingAlgorithm):
    """
    CityLume

    This algorithm converts NTL time series, POI, and building attributes into an
    integrated urban dynamics diagnosis and future core prediction workflow.
    """

    NTL_INPUT_MODE = 'NTL_INPUT_MODE'
    NTL_RASTERS = 'NTL_RASTERS'
    YEARS = 'YEARS'
    NTL_TEMPORAL_MODE = 'NTL_TEMPORAL_MODE'
    NTL_COMPOSITE_STAT = 'NTL_COMPOSITE_STAT'
    START_YEAR = 'START_YEAR'
    END_YEAR = 'END_YEAR'
    NTL_MONTHS = 'NTL_MONTHS'
    GEE_SCALE = 'GEE_SCALE'
    GEE_EXPORT_CRS = 'GEE_EXPORT_CRS'
    POI = 'POI'
    POI_CATEGORY_FIELD = 'POI_CATEGORY_FIELD'
    POI_NAME_FIELD = 'POI_NAME_FIELD'
    BUILDINGS = 'BUILDINGS'
    BUILDING_HEIGHT_FIELD = 'BUILDING_HEIGHT_FIELD'
    BUILDING_OCCUPANCY_FIELD = 'BUILDING_OCCUPANCY_FIELD'
    ROADS = 'ROADS'
    ROAD_CLASS_FIELD = 'ROAD_CLASS_FIELD'
    MAJOR_ROAD_CLASSES = 'MAJOR_ROAD_CLASSES'
    USE_ROAD_ACCESSIBILITY = 'USE_ROAD_ACCESSIBILITY'
    DOWNSCALE_MODE = 'DOWNSCALE_MODE'
    DOWNSCALE_BLEND = 'DOWNSCALE_BLEND'
    BOUNDARY = 'BOUNDARY'
    EXISTING_POP_RASTER = 'EXISTING_POP_RASTER'
    PLANNING_ZONE = 'PLANNING_ZONE'
    PLANNING_ZONE_FIELD = 'PLANNING_ZONE_FIELD'
    PLANNED_CENTER = 'PLANNED_CENTER'
    PLANNED_CENTER_LEVEL_FIELD = 'PLANNED_CENTER_LEVEL_FIELD'
    ENABLE_SPATIAL_PLANNING_MODULES = 'ENABLE_SPATIAL_PLANNING_MODULES'
    GRID_SIZE = 'GRID_SIZE'
    PREDICTION_YEAR = 'PREDICTION_YEAR'
    ML_MODEL = 'ML_MODEL'
    CORE_TOP_PERCENT = 'CORE_TOP_PERCENT'
    MAX_BUILDING_CANDIDATES = 'MAX_BUILDING_CANDIDATES'
    SHRINKING_SENSITIVITY = 'SHRINKING_SENSITIVITY'
    MIN_NTL_THRESHOLD = 'MIN_NTL_THRESHOLD'
    GENERATE_PNG = 'GENERATE_PNG'
    GENERATE_GIF = 'GENERATE_GIF'
    GIF_DURATION = 'GIF_DURATION'
    GENERATE_XLSX = 'GENERATE_XLSX'
    GENERATE_REPORT = 'GENERATE_REPORT'
    OUTPUT_FOLDER = 'OUTPUT_FOLDER'

    OUTPUT_GRID = 'OUTPUT_GRID'
    OUTPUT_POI_CORE = 'OUTPUT_POI_CORE'
    OUTPUT_BUILDING_CORE = 'OUTPUT_BUILDING_CORE'
    OUTPUT_REPORT_TXT = 'OUTPUT_REPORT_TXT'
    OUTPUT_GPKG = 'OUTPUT_GPKG'
    OUTPUT_FOLDER_OUT = 'OUTPUT_FOLDER_OUT'

    def tr(self, string):
        return QgsApplication.translate('Processing', string)

    def createInstance(self):
        return CityLumeUrbanDynamics()

    def name(self):
        return 'citylume_planner'

    def displayName(self):
        return self.tr('CityLume Planner: NTL-Based Urban Structure and Planning Intelligence')

    def shortHelpString(self):
        return self.tr(
            '<p><b>Created By: Firman Afrianto, Maya Safira</b></p>'
            '<p><b>CityLume Planner: NTL-Based Urban Structure and Planning Intelligence</b> is a QGIS Processing Toolbox '
            'for diagnosing urban dynamics, evaluating empirical urban structure, identifying current and future urban centers, '
            'detecting planning mismatch, and generating a spatial planning action matrix using Nighttime Light (NTL), POI, buildings, roads, population, and planning layers.</p>'

            '<p><b>Purpose</b></p>'
            '<p>This tool is designed for practical and research-oriented urban and regional planning work, especially statutory spatial plan and zoning plan evaluation, '
            'urban structure review, center hierarchy assessment, sub-center detection, growth corridor monitoring, urban shrinking diagnosis, '
            'planning mismatch analysis, and evidence-based spatial planning recommendations.</p>'

            '<p><b>Core Inputs</b></p>'
            '<ul>'
            '<li><b>NTL input mode</b>: choose Manual Raster Time Series, Auto Download VIIRS Annual from Google Earth Engine, or Auto Download VIIRS Monthly Composite from Google Earth Engine.</li>'
            '<li><b>NTL raster time series</b>: multiple NTL rasters. Required only when manual mode is selected. At least two years are required for time-series analysis.</li>'
            '<li><b>Years</b>: comma-separated years, for example <pre>2015,2016,2017,2018,2019,2020,2021,2022,2023,2024,2025</pre>. If empty, years are extracted from raster names.</li>'
            '<li><b>Automatic NTL download parameters</b>: start year, end year, annual or monthly mode, composite statistic, month filter, export CRS, and export scale.</li>'
            '<li><b>Boundary layer</b>: polygon boundary of the study area. A projected CRS in meters is recommended for grid, area, and density calculations.</li>'
            '<li><b>Grid size</b>: analysis cell size in CRS map units. For city-scale analysis, 250 m is a practical starting point.</li>'
            '<li><b>POI layer</b>: optional point layer representing activity locations. Used for POI density, POI diversity, dominant activity, and future-core scoring.</li>'
            '<li><b>Building layer</b>: optional polygon layer representing building footprints. Used for building density, footprint area, coverage ratio, height indicators, and occupancy mix.</li>'
            '<li><b>Road layer</b>: optional line layer used for road density, major road density, intersection proxy, and road accessibility score.</li>'
            '</ul>'

            '<p><b>New Spatial Planning Intelligence Inputs</b></p>'
            '<ul>'
            '<li><b>Existing population raster</b> (optional): raster population input such as WorldPop or other gridded population datasets. The tool samples population values to the grid and creates population indicators including <pre>pop_mean</pre>, <pre>pop_sum</pre>, <pre>pop_density</pre>, <pre>pop_density_norm</pre>, and <pre>pop_mean_norm</pre>. These indicators are used to strengthen activity pressure, center hierarchy, and planning action priority.</li>'
            '<li><b>Planning zone / spatial plan allocation layer</b> (optional): polygon layer containing spatial plan zones, zoning plan allocation, statutory spatial plan allocation, zoning categories, or similar planning designations.</li>'
            '<li><b>Planning zone field</b> (optional): attribute field used to read the name or class of each planning zone. The tool automatically groups the zone into planning intent classes such as planned center, commercial or mixed use, residential, industrial or logistics, protected or low-urbanization zone, infrastructure or transport zone, and other planned zone.</li>'
            '<li><b>Planned urban center layer</b> (optional): point or polygon layer representing planned city centers, sub-centers, service centers, TOD nodes, or other official urban structure nodes.</li>'
            '<li><b>Planned center level/name field</b> (optional): attribute field containing hierarchy, name, or level of planned centers.</li>'
            '<li><b>Enable Spatial Planning Intelligence modules</b>: when enabled, the tool creates Planning Mismatch, Urban Center Hierarchy, and Spatial Planning Action Matrix outputs. All new spatial planning inputs are optional; if left empty, the tool still runs using available NTL, POI, building, road, and boundary inputs.</li>'
            '</ul>'

            '<p><b>Processing Logic</b></p>'
            '<ol>'
            '<li>Create a clipped analysis grid inside the boundary.</li>'
            '<li>Extract NTL statistics from every year into each grid cell.</li>'
            '<li>Optionally download VIIRS NTL from Google Earth Engine, save GeoTIFF outputs into <pre>ntl_downloaded</pre>, and use them directly in the analysis.</li>'
            '<li>Aggregate POI density, POI diversity, and dominant activity category.</li>'
            '<li>Aggregate building count, footprint area, building coverage ratio, mean height, maximum height, and occupancy mix.</li>'
            '<li>Aggregate optional road accessibility indicators including road density, major road density, intersection proxy, and road accessibility score.</li>'
            '<li>Extract optional population raster values into grid-based population indicators.</li>'
            '<li>Overlay optional planning zones and planned urban centers to read planning intent and planned center presence.</li>'
            '<li>Calculate NTL trend, change, CAGR, volatility, acceleration, and persistent decline.</li>'
            '<li>Predict future NTL using Auto, Linear Trend, Random Forest, Extra Trees, or HistGradientBoosting.</li>'
            '<li>Diagnose urban dynamics, shrinking risk, future core probability, and future core rank.</li>'
            '<li>Run Spatial Planning Intelligence modules for planning mismatch, center hierarchy, and planning action recommendations.</li>'
            '</ol>'

            '<p><b>Urban Dynamics Outputs</b></p>'
            '<ul>'
            '<li><b>Urban dynamics class</b>: classifies grids into Stable Mature Core, Intensifying Core, Road-Supported Emerging Future Core, Emerging Future Core, Corridor Growth, Urban Expansion, Future Growth Area, Vertical Intensification, Activity Without Density, Isolated Light Anomaly, Dormant Built-up Area, Declining Urban Area, Strong Urban Shrinking, and Stable or Low-Dynamics Area.</li>'
            '<li><b>Shrinking risk</b>: 0-1 composite score from negative NTL slope, negative NTL change, low POI density, underused built-up fabric, and persistent decline.</li>'
            '<li><b>Future core probability</b>: 0-1 composite score from predicted NTL, NTL growth, POI density, POI diversity, building intensity, occupancy mix, road accessibility, and NTL stability.</li>'
            '<li><b>Future core rank</b>: ranked priority of future core probability, with rank 1 representing the strongest future core candidate.</li>'
            '</ul>'

            '<p><b>Planning Mismatch Module</b></p>'
            '<p>The Planning Mismatch module compares empirical urban activity signals with planning intent from zoning or spatial plan layers. It produces:</p>'
            '<ul>'
            '<li><pre>activity_pressure_score</pre>: composite signal from NTL, NTL trend, POI density, building density, road accessibility, and population density.</li>'
            '<li><pre>planning_activity_alignment_score</pre>: 0-1 score indicating whether observed activity aligns with planning intent.</li>'
            '<li><pre>planning_mismatch_type</pre>: planning mismatch typology such as Planned Core, Active Core; Planned Core, Weak Activity; Unplanned Emerging Core; Predicted Growth Outside Clear Plan Direction; High Activity in Protected or Low-Urbanization Zone; Residential Zone Under Activity Intensification; Industrial Light Anomaly; Planned Core Under Shrinking Pressure; Shrinking Risk Area; or Plan-Activity Relatively Aligned or Neutral.</li>'
            '</ul>'

            '<p><b>Urban Center Hierarchy Module</b></p>'
            '<p>This module converts future-core and activity signals into an empirical hierarchy of centers. It produces:</p>'
            '<ul>'
            '<li><pre>center_hierarchy_score</pre>: composite score from future core probability, NTL intensity, POI density, building density, road accessibility, and population density.</li>'
            '<li><pre>urban_center_hierarchy</pre>: Primary Urban Center, Secondary Urban Center, Emerging Local Center, Planned Center with Weak Empirical Signal, Declining or Shrinking Center, or Non-Center or Low-Order Area.</li>'
            '</ul>'

            '<p><b>Spatial Planning Action Matrix</b></p>'
            '<p>This module translates the analytical results into planning actions and priority classes. It produces:</p>'
            '<ul>'
            '<li><pre>spatial_planning_priority</pre>: Critical, High, Medium-High, Medium, Low, or Not Classified.</li>'
            '<li><pre>spatial_planning_action</pre>: recommended planning response such as Growth Control and Environmental Protection Audit, Evaluate New Sub-Center or Revise Spatial Structure, Activate Planned Center through Infrastructure and Public Facility Investment, Urban Renewal and Adaptive Reuse, Strengthen Urban Center Hierarchy, Upgrade Urban Services, Manage Corridor Growth, Guide Urban Expansion, or Monitor Existing Spatial Function.</li>'
            '<li><pre>spatial_planning_rationale</pre>: short explanation of why the action is recommended for each grid.</li>'
            '</ul>'

            '<p><b>Machine Learning Models</b></p>'
            '<ul>'
            '<li><b>Auto</b>: compares candidate models and selects the best available model.</li>'
            '<li><b>Linear Trend</b>: transparent deterministic baseline.</li>'
            '<li><b>Random Forest</b>: robust nonlinear ensemble model.</li>'
            '<li><b>Extra Trees</b>: fast ensemble model for stable prediction.</li>'
            '<li><b>HistGradientBoosting</b>: stronger nonlinear model when enough grid samples are available.</li>'
            '</ul>'

            '<p><b>What It Produces</b></p>'
            '<ul>'
            '<li><b>GeoPackage</b>: analysis grid, future core POI candidates, and future core building candidates.</li>'
            '<li><b>CSV tables</b>: grid indicators, model validation, urban diagnosis summary, future core grid candidates, shrinking risk candidates, planning mismatch summary, urban center hierarchy summary, and spatial planning action matrix summary.</li>'
            '<li><b>Optional XLSX workbook</b>: consolidated tables when openpyxl is available.</li>'
            '<li><b>PNG maps and charts</b>: NTL maps, trend maps, shrinking risk, future core probability, future core rank, POI/building/road maps, standalone urban dynamics map, NTL initial-final-predicted triptych, planning mismatch map, urban center hierarchy map, spatial planning action priority map, action matrix chart, and summary dashboard.</li>'
            '<li><b>GIF animations</b>: NTL time series and future core emergence when imageio is available.</li>'
            '<li><b>Diagnostic report TXT</b>: automatic narrative summary for quick interpretation.</li>'
            '</ul>'

            '<p><b>Important Notes</b></p>'
            '<ul>'
            '<li>Use projected CRS in meters for reliable grid, area, density, and accessibility calculations.</li>'
            '<li>In automatic NTL mode, Google Earth Engine access and the <pre>ee</pre> and <pre>geemap</pre> packages must be available in the QGIS Python environment.</li>'
            '<li>Population raster values are sampled at grid centroids. Depending on the population raster definition, values may represent count, density, or another population surface. Validate interpretation before using results in formal policy documents.</li>'
            '<li>Planning mismatch is an analytical signal, not a legal determination. Always compare with official statutory spatial plan and zoning maps, zoning tables, local knowledge, and field verification.</li>'
            '<li>All thresholds are adaptive and relative to the study area distribution; results should not be compared across cities without recalibration.</li>'
            '<li>NTL can reflect urban activity, lighting infrastructure, industrial facilities, ports, airports, or other light emitters. Interpret high NTL together with POI, building, road, population, and planning context.</li>'
            '</ul>'

            '<p><b>Dependencies</b></p>'
            '<p>Core processing uses QGIS, numpy, pandas, matplotlib, and scikit-learn. GIF output uses imageio. XLSX output uses openpyxl if available. Automatic NTL download requires Google Earth Engine access plus ee and geemap packages inside the QGIS Python environment.</p>'
        )

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterEnum(
                self.NTL_INPUT_MODE,
                self.tr('NTL input mode'),
                options=[
                    'Manual Raster Time Series',
                    'Auto Download VIIRS Annual from Google Earth Engine',
                    'Auto Download VIIRS Monthly Composite from Google Earth Engine'
                ],
                defaultValue=0
            )
        )

        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.NTL_RASTERS,
                self.tr('NTL raster time series, required only for Manual mode'),
                QgsProcessing.TypeRaster,
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterString(
                self.YEARS,
                self.tr('Years, comma-separated. Manual mode only; leave empty to extract from raster names'),
                defaultValue='',
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.START_YEAR,
                self.tr('Auto NTL start year'),
                QgsProcessingParameterNumber.Integer,
                defaultValue=2015,
                minValue=2012,
                maxValue=2100
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.END_YEAR,
                self.tr('Auto NTL end year'),
                QgsProcessingParameterNumber.Integer,
                defaultValue=2025,
                minValue=2012,
                maxValue=2100
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.NTL_COMPOSITE_STAT,
                self.tr('Auto NTL composite statistic'),
                options=['Mean', 'Median', 'Maximum'],
                defaultValue=0
            )
        )

        self.addParameter(
            QgsProcessingParameterString(
                self.NTL_MONTHS,
                self.tr('Auto monthly mode months, comma-separated. Empty = all months'),
                defaultValue='',
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.GEE_SCALE,
                self.tr('Google Earth Engine export scale, meters'),
                QgsProcessingParameterNumber.Double,
                defaultValue=500.0,
                minValue=100.0
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.GEE_EXPORT_CRS,
                self.tr('Google Earth Engine export CRS'),
                options=[
                    'EPSG:4326 - WGS 84 geographic, safest for GEE export',
                    'EPSG:3857 - Web Mercator, common web map CRS',
                    'ESRI:54034 - World Cylindrical Equal Area'
                ],
                defaultValue=0
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.POI,
                self.tr('POI layer'),
                [QgsProcessing.TypeVectorPoint],
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.POI_CATEGORY_FIELD,
                self.tr('POI category field'),
                parentLayerParameterName=self.POI,
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.POI_NAME_FIELD,
                self.tr('POI name field, optional'),
                parentLayerParameterName=self.POI,
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.BUILDINGS,
                self.tr('Building layer'),
                [QgsProcessing.TypeVectorPolygon],
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.BUILDING_HEIGHT_FIELD,
                self.tr('Building height field'),
                parentLayerParameterName=self.BUILDINGS,
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.BUILDING_OCCUPANCY_FIELD,
                self.tr('Building occupancy field'),
                parentLayerParameterName=self.BUILDINGS,
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.ROADS,
                self.tr('Road layer, optional'),
                [QgsProcessing.TypeVectorLine],
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.ROAD_CLASS_FIELD,
                self.tr('Road class field, optional'),
                parentLayerParameterName=self.ROADS,
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterString(
                self.MAJOR_ROAD_CLASSES,
                self.tr('Major road classes, comma-separated'),
                defaultValue='motorway,trunk,primary,secondary,tertiary'
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.USE_ROAD_ACCESSIBILITY,
                self.tr('Use road accessibility in future core and diagnosis'),
                defaultValue=True
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.BOUNDARY,
                self.tr('Boundary layer'),
                [QgsProcessing.TypeVectorPolygon]
            )
        )

        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.EXISTING_POP_RASTER,
                self.tr('Existing population raster, optional'),
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.PLANNING_ZONE,
                self.tr('Planning zone / spatial plan allocation layer, optional for Planning Mismatch'),
                [QgsProcessing.TypeVectorPolygon],
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.PLANNING_ZONE_FIELD,
                self.tr('Planning zone field, optional'),
                parentLayerParameterName=self.PLANNING_ZONE,
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.PLANNED_CENTER,
                self.tr('Planned urban center layer, optional for Urban Center Hierarchy validation'),
                [QgsProcessing.TypeVectorPoint, QgsProcessing.TypeVectorPolygon],
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.PLANNED_CENTER_LEVEL_FIELD,
                self.tr('Planned center level/name field, optional'),
                parentLayerParameterName=self.PLANNED_CENTER,
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.ENABLE_SPATIAL_PLANNING_MODULES,
                self.tr('Enable Spatial Planning Intelligence modules: Planning Mismatch, Center Hierarchy, and Action Matrix'),
                defaultValue=True
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.GRID_SIZE,
                self.tr('Analysis grid size, in CRS map units, preferably meters'),
                QgsProcessingParameterNumber.Double,
                defaultValue=250.0,
                minValue=10.0
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.PREDICTION_YEAR,
                self.tr('Prediction year. Use 0 for last year + 10. Values 1-99 are treated as horizon years'),
                QgsProcessingParameterNumber.Integer,
                defaultValue=0,
                minValue=0
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.ML_MODEL,
                self.tr('NTL prediction model'),
                options=[
                    'Auto',
                    'Linear Trend',
                    'Random Forest',
                    'Extra Trees',
                    'HistGradientBoosting'
                ],
                defaultValue=0
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.CORE_TOP_PERCENT,
                self.tr('Top percent for high future core candidates'),
                QgsProcessingParameterNumber.Double,
                defaultValue=10.0,
                minValue=1.0,
                maxValue=50.0
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_BUILDING_CANDIDATES,
                self.tr('Maximum building core candidates to write, use 0 for all candidates but it can be slow'),
                QgsProcessingParameterNumber.Integer,
                defaultValue=5000,
                minValue=0
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.SHRINKING_SENSITIVITY,
                self.tr('Shrinking diagnosis sensitivity'),
                options=['Low', 'Medium', 'High'],
                defaultValue=1
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.MIN_NTL_THRESHOLD,
                self.tr('Minimum NTL threshold. Values below this are treated as very low activity'),
                QgsProcessingParameterNumber.Double,
                defaultValue=0.0,
                minValue=0.0
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.DOWNSCALE_MODE,
                self.tr('NTL downscaling mode'),
                options=[
                    'None',
                    'Building-POI Weighted Downscaling',
                    'ML-Based Dasymetric Downscaling'
                ],
                defaultValue=1
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.DOWNSCALE_BLEND,
                self.tr('Downscale blend factor, 0 keeps raw NTL and 1 uses full dasymetric redistribution'),
                QgsProcessingParameterNumber.Double,
                defaultValue=0.35,
                minValue=0.0,
                maxValue=1.0
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.GENERATE_PNG,
                self.tr('Generate PNG maps and charts'),
                defaultValue=True
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.GENERATE_GIF,
                self.tr('Generate GIF animations'),
                defaultValue=True
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.GIF_DURATION,
                self.tr('GIF frame duration, seconds per frame'),
                QgsProcessingParameterNumber.Double,
                defaultValue=1.5,
                minValue=0.1,
                maxValue=10.0
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.GENERATE_XLSX,
                self.tr('Generate XLSX workbook if openpyxl is available'),
                defaultValue=True
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.GENERATE_REPORT,
                self.tr('Generate automatic TXT diagnostic report'),
                defaultValue=True
            )
        )

        self.addParameter(
            QgsProcessingParameterFolderDestination(
                self.OUTPUT_FOLDER,
                self.tr('Output folder')
            )
        )

        self.addOutput(
            QgsProcessingOutputFile(
                self.OUTPUT_GPKG,
                self.tr('Output GeoPackage')
            )
        )

        self.addOutput(
            QgsProcessingOutputFile(
                self.OUTPUT_REPORT_TXT,
                self.tr('Diagnostic report TXT')
            )
        )

        self.addOutput(
            QgsProcessingOutputFolder(
                self.OUTPUT_FOLDER_OUT,
                self.tr('Output folder')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        try:
            import numpy as np
            import pandas as pd
        except Exception as e:
            raise QgsProcessingException(
                'Missing dependency. Please install numpy and pandas in the QGIS Python environment. Error: {}'.format(e)
            )

        out_dir = Path(self.parameterAsString(parameters, self.OUTPUT_FOLDER, context))
        out_dir.mkdir(parents=True, exist_ok=True)

        dirs = {
            'vector': out_dir / 'vector',
            'tables': out_dir / 'tables',
            'maps': out_dir / 'maps',
            'charts': out_dir / 'charts',
            'gif': out_dir / 'gif',
            'report': out_dir / 'report',
            'tmp': out_dir / '_tmp'
        }
        for p in dirs.values():
            p.mkdir(parents=True, exist_ok=True)

        gpkg_path = str(dirs['vector'] / 'citylume_urban_dynamics.gpkg')
        report_path = str(dirs['report'] / 'urban_dynamics_diagnostic_report.txt')
        metadata_path = str(dirs['report'] / 'metadata.json')
        ntl_download_dir = dirs['tmp'].parent / 'ntl_downloaded'
        ntl_download_dir.mkdir(parents=True, exist_ok=True)

        boundary_source = self.parameterAsSource(parameters, self.BOUNDARY, context)
        if boundary_source is None:
            raise QgsProcessingException('Boundary layer is required.')
        boundary_layer = self._materialize_source(boundary_source, 'boundary_materialized', context)

        ntl_input_mode_idx = int(self.parameterAsEnum(parameters, self.NTL_INPUT_MODE, context))
        ntl_input_mode = [
            'Manual Raster Time Series',
            'Auto Download VIIRS Annual from Google Earth Engine',
            'Auto Download VIIRS Monthly Composite from Google Earth Engine'
        ][ntl_input_mode_idx]

        if ntl_input_mode_idx == 0:
            ntl_layers = self.parameterAsLayerList(parameters, self.NTL_RASTERS, context)
            if not ntl_layers or len(ntl_layers) < 2:
                raise QgsProcessingException('At least two NTL rasters are required for time-series dynamics analysis in Manual mode.')

            years_text = self.parameterAsString(parameters, self.YEARS, context).strip()
            years = self._parse_years(years_text, ntl_layers)
            if len(years) != len(ntl_layers):
                raise QgsProcessingException(
                    'Number of years must match number of NTL rasters. Rasters: {}, Years: {}'.format(len(ntl_layers), len(years))
                )
        else:
            start_year = int(self.parameterAsInt(parameters, self.START_YEAR, context))
            end_year = int(self.parameterAsInt(parameters, self.END_YEAR, context))
            if end_year < start_year:
                raise QgsProcessingException('Auto NTL end year must be greater than or equal to start year.')
            if (end_year - start_year + 1) < 2:
                raise QgsProcessingException('At least two years are required for time-series dynamics analysis.')

            stat_idx = int(self.parameterAsEnum(parameters, self.NTL_COMPOSITE_STAT, context))
            composite_stat = ['mean', 'median', 'max'][stat_idx]
            months_text = self.parameterAsString(parameters, self.NTL_MONTHS, context).strip()
            gee_scale = float(self.parameterAsDouble(parameters, self.GEE_SCALE, context))
            gee_crs_idx = int(self.parameterAsEnum(parameters, self.GEE_EXPORT_CRS, context))
            gee_crs_options = [
                'EPSG:4326',
                'EPSG:3857',
                'EPSG:3395',
                'ESRI:54034'
            ]
            gee_crs = gee_crs_options[gee_crs_idx] if 0 <= gee_crs_idx < len(gee_crs_options) else 'EPSG:4326'
            temporal_mode = 'annual' if ntl_input_mode_idx == 1 else 'monthly'

            feedback.pushInfo('Automatic NTL download mode selected: {}'.format(ntl_input_mode))
            ntl_layers, years = self._download_ntl_from_gee(
                boundary_layer=boundary_layer,
                output_dir=ntl_download_dir,
                start_year=start_year,
                end_year=end_year,
                temporal_mode=temporal_mode,
                composite_stat=composite_stat,
                months_text=months_text,
                scale=gee_scale,
                export_crs=gee_crs,
                feedback=feedback
            )

        paired = sorted(zip(years, ntl_layers), key=lambda x: x[0])
        years = [p[0] for p in paired]
        ntl_layers = [p[1] for p in paired]

        grid_size = float(self.parameterAsDouble(parameters, self.GRID_SIZE, context))
        prediction_year_input = int(self.parameterAsInt(parameters, self.PREDICTION_YEAR, context))
        if prediction_year_input <= 0:
            prediction_year = int(max(years) + 10)
        elif prediction_year_input < 100:
            prediction_year = int(max(years) + prediction_year_input)
            feedback.pushInfo('Prediction year input {} is treated as a horizon. Target prediction year: {}'.format(prediction_year_input, prediction_year))
        else:
            prediction_year = prediction_year_input

        if prediction_year <= max(years):
            prediction_year = int(max(years) + 10)
            feedback.reportError('Prediction year must be after the last NTL year. It has been reset to {}'.format(prediction_year))

        ml_model_idx = int(self.parameterAsEnum(parameters, self.ML_MODEL, context))
        ml_model_name = ['Auto', 'Linear Trend', 'Random Forest', 'Extra Trees', 'HistGradientBoosting'][ml_model_idx]

        core_top_percent = float(self.parameterAsDouble(parameters, self.CORE_TOP_PERCENT, context))
        max_building_candidates = int(self.parameterAsInt(parameters, self.MAX_BUILDING_CANDIDATES, context))
        shrinking_sensitivity_idx = int(self.parameterAsEnum(parameters, self.SHRINKING_SENSITIVITY, context))
        shrinking_sensitivity = ['Low', 'Medium', 'High'][shrinking_sensitivity_idx]
        min_ntl_threshold = float(self.parameterAsDouble(parameters, self.MIN_NTL_THRESHOLD, context))
        downscale_mode_idx = int(self.parameterAsEnum(parameters, self.DOWNSCALE_MODE, context))
        downscale_mode = ['None', 'Building-POI Weighted Downscaling', 'ML-Based Dasymetric Downscaling'][downscale_mode_idx]
        downscale_blend = float(self.parameterAsDouble(parameters, self.DOWNSCALE_BLEND, context))
        use_road_accessibility = bool(self.parameterAsBool(parameters, self.USE_ROAD_ACCESSIBILITY, context))

        generate_png = bool(self.parameterAsBool(parameters, self.GENERATE_PNG, context))
        generate_gif = bool(self.parameterAsBool(parameters, self.GENERATE_GIF, context))
        gif_duration = float(self.parameterAsDouble(parameters, self.GIF_DURATION, context))
        generate_xlsx = bool(self.parameterAsBool(parameters, self.GENERATE_XLSX, context))
        generate_report = bool(self.parameterAsBool(parameters, self.GENERATE_REPORT, context))

        feedback.pushInfo('CityLume started.')
        feedback.pushInfo('NTL years: {}'.format(', '.join(map(str, years))))
        feedback.pushInfo('Prediction year: {}'.format(prediction_year))
        feedback.pushInfo('Model mode: {}'.format(ml_model_name))

        if boundary_layer.crs().isGeographic():
            feedback.reportError(
                'Boundary CRS is geographic. The tool can run, but grid size, area, and density may be unreliable. '
                'A projected CRS in meters is strongly recommended.'
            )

        extent = boundary_layer.extent()
        extent_str = '{},{},{},{}'.format(extent.xMinimum(), extent.xMaximum(), extent.yMinimum(), extent.yMaximum())

        feedback.pushInfo('Creating analysis grid.')
        grid_raw_result = processing.run(
            'native:creategrid',
            {
                'TYPE': 2,
                'EXTENT': extent_str,
                'HSPACING': grid_size,
                'VSPACING': grid_size,
                'HOVERLAY': 0,
                'VOVERLAY': 0,
                'CRS': boundary_layer.crs(),
                'OUTPUT': 'memory:urban_grid_raw'
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )['OUTPUT']
        grid_raw = self._resolve_output_layer(grid_raw_result, context, 'urban_grid_raw')

        grid_clip_result = processing.run(
            'native:clip',
            {
                'INPUT': grid_raw,
                'OVERLAY': boundary_layer,
                'OUTPUT': 'memory:urban_grid_clipped'
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )['OUTPUT']
        grid_clip = self._resolve_output_layer(grid_clip_result, context, 'urban_grid_clipped')

        grid_layer_result = processing.run(
            'native:multiparttosingleparts',
            {
                'INPUT': grid_clip,
                'OUTPUT': 'memory:urban_grid_singlepart'
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )['OUTPUT']
        grid_layer = self._resolve_output_layer(grid_layer_result, context, 'urban_grid_singlepart')

        feedback.pushInfo('Building indicator table.')
        grid_records = self._init_grid_records(grid_layer)

        feedback.pushInfo('Extracting NTL time-series statistics per grid.')
        self._extract_ntl_by_grid(grid_layer, grid_records, ntl_layers, years, feedback)

        feedback.pushInfo('Aggregating POI indicators.')
        poi_source = self.parameterAsSource(parameters, self.POI, context)
        poi_category_field = self.parameterAsString(parameters, self.POI_CATEGORY_FIELD, context)
        poi_name_field = self.parameterAsString(parameters, self.POI_NAME_FIELD, context)
        poi_layer = None
        if poi_source is not None:
            poi_layer = self._materialize_source(poi_source, 'poi_materialized', context)
            self._aggregate_poi(grid_layer, grid_records, poi_layer, poi_category_field, feedback)

        feedback.pushInfo('Aggregating building indicators.')
        building_source = self.parameterAsSource(parameters, self.BUILDINGS, context)
        height_field = self.parameterAsString(parameters, self.BUILDING_HEIGHT_FIELD, context)
        occupancy_field = self.parameterAsString(parameters, self.BUILDING_OCCUPANCY_FIELD, context)
        building_layer = None
        if building_source is not None:
            building_layer = self._materialize_source(building_source, 'building_materialized', context)
            self._aggregate_buildings(grid_layer, grid_records, building_layer, height_field, occupancy_field, feedback)

        feedback.pushInfo('Aggregating optional road accessibility indicators.')
        roads_source = self.parameterAsSource(parameters, self.ROADS, context)
        road_class_field = self.parameterAsString(parameters, self.ROAD_CLASS_FIELD, context)
        major_road_classes_text = self.parameterAsString(parameters, self.MAJOR_ROAD_CLASSES, context)
        road_layer = None
        if roads_source is not None and use_road_accessibility:
            road_layer = self._materialize_source(roads_source, 'roads_materialized', context)
            self._aggregate_roads(grid_layer, grid_records, road_layer, road_class_field, major_road_classes_text, feedback)
        else:
            self._init_empty_road_indicators(grid_records)

        feedback.pushInfo('Extracting optional existing population raster.')
        pop_raster = self.parameterAsRasterLayer(parameters, self.EXISTING_POP_RASTER, context)
        if pop_raster is not None:
            self._extract_population_raster_by_grid(grid_layer, grid_records, pop_raster, feedback)
        else:
            self._init_empty_population_indicators(grid_records)

        feedback.pushInfo('Aggregating optional planning zone and planned center context.')
        planning_zone_source = self.parameterAsSource(parameters, self.PLANNING_ZONE, context)
        planning_zone_field = self.parameterAsString(parameters, self.PLANNING_ZONE_FIELD, context)
        if planning_zone_source is not None:
            planning_zone_layer = self._materialize_source(planning_zone_source, 'planning_zone_materialized', context)
            self._aggregate_planning_zones(grid_layer, grid_records, planning_zone_layer, planning_zone_field, feedback)
        else:
            self._init_empty_planning_zone_indicators(grid_records)

        planned_center_source = self.parameterAsSource(parameters, self.PLANNED_CENTER, context)
        planned_center_level_field = self.parameterAsString(parameters, self.PLANNED_CENTER_LEVEL_FIELD, context)
        if planned_center_source is not None:
            planned_center_layer = self._materialize_source(planned_center_source, 'planned_center_materialized', context)
            self._aggregate_planned_centers(grid_layer, grid_records, planned_center_layer, planned_center_level_field, feedback)
        else:
            self._init_empty_planned_center_indicators(grid_records)

        feedback.pushInfo('Preparing indicator table and optional NTL downscaling.')
        df = self._records_to_dataframe(grid_records, years)
        if downscale_mode != 'None' and downscale_blend > 0:
            df = self._apply_ntl_downscaling(df, years, downscale_mode, downscale_blend, feedback)

        feedback.pushInfo('Calculating NTL trend indicators.')
        df = self._calculate_trend_indicators(df, years, min_ntl_threshold)

        feedback.pushInfo('Predicting future NTL.')
        df, model_info, validation_df = self._predict_future_ntl(df, years, prediction_year, ml_model_name, feedback)

        feedback.pushInfo('Diagnosing urban dynamics and future core probability.')
        df = self._diagnose_urban_dynamics(df, core_top_percent, shrinking_sensitivity)

        enable_spatial_planning_modules = bool(self.parameterAsBool(parameters, self.ENABLE_SPATIAL_PLANNING_MODULES, context))
        if enable_spatial_planning_modules:
            feedback.pushInfo('Running Spatial Planning Intelligence modules: Planning Mismatch, Urban Center Hierarchy, and Spatial Planning Action Matrix.')
            df = self._run_spatial_planning_intelligence_modules(df, core_top_percent)
        else:
            df = self._init_empty_spatial_planning_outputs(df)

        feedback.pushInfo('Writing output grid.')
        output_grid_layer = self._write_grid_layer(grid_layer, df, gpkg_path, 'analysis_grid', context, feedback)

        feedback.pushInfo('Selecting future core POI candidates.')
        poi_core_layer = None
        poi_core_csv = None
        if poi_layer is not None:
            poi_core_layer, poi_core_csv = self._write_poi_core_candidates(
                poi_layer, grid_layer, df, poi_name_field, poi_category_field,
                gpkg_path, dirs['tables'], context, feedback
            )

        feedback.pushInfo('Selecting future core building candidates.')
        building_core_layer = None
        building_core_csv = None
        if building_layer is not None:
            building_core_layer, building_core_csv = self._write_building_core_candidates(
                building_layer, grid_layer, df, height_field, occupancy_field,
                gpkg_path, dirs['tables'], context, feedback,
                max_building_candidates=max_building_candidates,
                core_top_percent=core_top_percent
            )

        feedback.pushInfo('Writing tables.')
        grid_csv = str(dirs['tables'] / '01_grid_indicators.csv')
        df.to_csv(grid_csv, index=False, encoding='utf-8-sig')

        validation_csv = str(dirs['tables'] / '02_model_validation.csv')
        validation_df.to_csv(validation_csv, index=False, encoding='utf-8-sig')

        class_summary = self._class_summary(df)
        class_summary_csv = str(dirs['tables'] / '03_urban_diagnosis_summary.csv')
        class_summary.to_csv(class_summary_csv, index=False, encoding='utf-8-sig')

        core_summary = df.sort_values('future_core_probability', ascending=False).head(max(1, int(len(df) * core_top_percent / 100.0)))
        core_summary_csv = str(dirs['tables'] / '04_future_core_grid_candidates.csv')
        core_summary.to_csv(core_summary_csv, index=False, encoding='utf-8-sig')

        shrinking_summary = df.sort_values('shrinking_risk', ascending=False).head(max(1, int(len(df) * core_top_percent / 100.0)))
        shrinking_summary_csv = str(dirs['tables'] / '05_shrinking_risk_grid_candidates.csv')
        shrinking_summary.to_csv(shrinking_summary_csv, index=False, encoding='utf-8-sig')

        try:
            mismatch_summary = self._planning_mismatch_summary(df)
            mismatch_summary_csv = str(dirs['tables'] / '06_planning_mismatch_summary.csv')
            mismatch_summary.to_csv(mismatch_summary_csv, index=False, encoding='utf-8-sig')

            hierarchy_summary = self._center_hierarchy_summary(df)
            hierarchy_summary_csv = str(dirs['tables'] / '07_urban_center_hierarchy_summary.csv')
            hierarchy_summary.to_csv(hierarchy_summary_csv, index=False, encoding='utf-8-sig')

            action_summary = self._action_matrix_summary(df)
            action_summary_csv = str(dirs['tables'] / '08_spatial_planning_action_matrix_summary.csv')
            action_summary.to_csv(action_summary_csv, index=False, encoding='utf-8-sig')
        except Exception as e:
            feedback.reportError('Spatial Planning Intelligence summary tables skipped: {}'.format(e))

        if generate_xlsx:
            self._write_xlsx(
                dirs['tables'] / 'citylume_urban_dynamics_report.xlsx',
                df,
                validation_df,
                class_summary,
                core_summary,
                shrinking_summary,
                feedback
            )

        if generate_png:
            feedback.pushInfo('Generating PNG maps and charts.')
            self._generate_png_outputs(df, years, prediction_year, dirs['maps'], dirs['charts'], feedback)

        if generate_gif:
            feedback.pushInfo('Generating GIF animations.')
            self._generate_gif_outputs(df, years, dirs['gif'], feedback, gif_duration)

        if generate_report:
            feedback.pushInfo('Generating automatic diagnostic report.')
            self._write_report(report_path, df, years, prediction_year, model_info, validation_df, class_summary)

        metadata = {
            'tool': 'CityLume',
            'created_by': 'Firman Afrianto, Maya Safira',
            'years': years,
            'ntl_input_mode': ntl_input_mode,
            'ntl_download_folder': str(ntl_download_dir),
            'prediction_year': prediction_year,
            'ml_model_selected': model_info.get('selected_model'),
            'ml_model_mode': ml_model_name,
            'grid_size': grid_size,
            'downscale_mode': downscale_mode,
            'downscale_blend': downscale_blend,
            'use_road_accessibility': use_road_accessibility,
            'core_top_percent': core_top_percent,
            'shrinking_sensitivity': shrinking_sensitivity,
            'gif_duration_seconds': gif_duration,
            'outputs': {
                'gpkg': gpkg_path,
                'report': report_path,
                'folder': str(out_dir)
            }
        }
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        try:
            shutil.rmtree(str(dirs['tmp']), ignore_errors=True)
        except Exception:
            pass

        feedback.pushInfo('Finished. Output folder: {}'.format(str(out_dir)))
        feedback.pushInfo('Output GeoPackage: {}'.format(gpkg_path))

        return {
            self.OUTPUT_GPKG: gpkg_path,
            self.OUTPUT_REPORT_TXT: report_path,
            self.OUTPUT_FOLDER_OUT: str(out_dir)
        }

    # -------------------------------------------------------------------------
    # Automatic NTL download from Google Earth Engine
    # -------------------------------------------------------------------------

    def _parse_months(self, months_text):
        if not months_text:
            return list(range(1, 13))
        months = []
        for part in str(months_text).split(','):
            part = part.strip()
            if not part:
                continue
            try:
                m = int(part)
            except Exception:
                raise QgsProcessingException('Invalid month value in Auto monthly mode: {}'.format(part))
            if m < 1 or m > 12:
                raise QgsProcessingException('Month value must be between 1 and 12. Invalid value: {}'.format(m))
            months.append(m)
        if not months:
            return list(range(1, 13))
        return sorted(set(months))

    def _boundary_to_ee_geometry(self, boundary_layer, ee):
        """
        Convert the QGIS boundary layer into an Earth Engine geometry in EPSG:4326.
        The function dissolves all boundary features first, so multipart administrative
        boundaries are handled as a single export region.
        """
        geoms = []
        transform = None
        if boundary_layer.crs() != QgsCoordinateReferenceSystem('EPSG:4326'):
            transform = QgsCoordinateTransform(
                boundary_layer.crs(),
                QgsCoordinateReferenceSystem('EPSG:4326'),
                QgsProject.instance()
            )

        for f in boundary_layer.getFeatures():
            g = QgsGeometry(f.geometry())
            if g is None or g.isEmpty():
                continue
            if transform is not None:
                try:
                    g.transform(transform)
                except Exception as e:
                    raise QgsProcessingException('Failed to transform boundary to EPSG:4326 for GEE export. Error: {}'.format(e))
            geoms.append(g)

        if not geoms:
            raise QgsProcessingException('Boundary layer has no valid geometry for GEE export.')

        if len(geoms) == 1:
            union_geom = geoms[0]
        else:
            union_geom = QgsGeometry.unaryUnion(geoms)

        if union_geom is None or union_geom.isEmpty():
            raise QgsProcessingException('Boundary dissolve failed. Cannot build GEE export region.')

        geojson_geom = json.loads(union_geom.asJson())
        return ee.Geometry(geojson_geom)

    def _safe_ee_collection_size(self, collection):
        """Return ImageCollection size as a Python integer, with a clear Processing error."""
        try:
            return int(collection.size().getInfo())
        except Exception as e:
            raise QgsProcessingException(
                'Could not evaluate Earth Engine ImageCollection size. '
                'Check internet connection, Earth Engine authentication, and dataset access. Error: {}'.format(e)
            )

    def _monthly_viirs_collection(self, ee, year, months):
        """Monthly VIIRS VCMSLCFG collection filtered by year and selected months."""
        months = months or list(range(1, 13))
        collection = (
            ee.ImageCollection('NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG')
            .filterDate('{}-01-01'.format(year), '{}-01-01'.format(year + 1))
            .filter(ee.Filter.calendarRange(int(min(months)), int(max(months)), 'month'))
            .select('avg_rad')
        )
        # If user entered non-contiguous months, calendarRange is too broad; refine by month list.
        if len(set(months)) < (int(max(months)) - int(min(months)) + 1):
            collection = collection.filter(ee.Filter.inList('month', [int(m) for m in months]))
        return collection

    def _compose_viirs_image(self, ee, year, temporal_mode, composite_stat, months):
        """
        Build one analysis image for a single year.

        Important source logic:
        - VIIRS annual V2.1 is used for 2013-2021.
        - VIIRS annual V2.2 is used for 2022-2024 when available.
        - Years not available in annual collections, including 2025 in many GEE catalogs,
          automatically fall back to the monthly VCMSLCFG collection.

        This prevents the common GEE error:
        "Expression evaluates to an image with no bands."
        """
        year = int(year)
        months = months or list(range(1, 13))
        source_used = ''

        if temporal_mode == 'annual':
            candidate_collections = []
            if year <= 2021:
                candidate_collections.append(('NOAA/VIIRS/DNB/ANNUAL_V21', 'average'))
            else:
                candidate_collections.append(('NOAA/VIIRS/DNB/ANNUAL_V22', 'average'))
            # Safety fallback: try both annual collections before monthly fallback.
            candidate_collections.append(('NOAA/VIIRS/DNB/ANNUAL_V21', 'average'))
            candidate_collections.append(('NOAA/VIIRS/DNB/ANNUAL_V22', 'average'))

            seen = set()
            collection = None
            for collection_id, band_name in candidate_collections:
                key = (collection_id, band_name)
                if key in seen:
                    continue
                seen.add(key)
                test = (
                    ee.ImageCollection(collection_id)
                    .filterDate('{}-01-01'.format(year), '{}-01-01'.format(year + 1))
                    .select(band_name)
                )
                if self._safe_ee_collection_size(test) > 0:
                    collection = test
                    source_used = collection_id
                    break

            if collection is None:
                collection = self._monthly_viirs_collection(ee, year, list(range(1, 13)))
                source_used = 'NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG fallback'
                if self._safe_ee_collection_size(collection) <= 0:
                    raise QgsProcessingException(
                        'No VIIRS annual or monthly NTL image is available for year {}. '
                        'For annual mode, try reducing END_YEAR to the latest available annual year, '
                        'or use monthly mode with available months.'.format(year)
                    )
        else:
            collection = self._monthly_viirs_collection(ee, year, months)
            source_used = 'NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG'
            if self._safe_ee_collection_size(collection) <= 0:
                raise QgsProcessingException(
                    'No VIIRS monthly NTL image is available for year {} and months {}. '
                    'Try changing the month list or reducing END_YEAR.'.format(year, ','.join(map(str, months)))
                )

        if composite_stat == 'median':
            image = collection.median()
        elif composite_stat == 'max':
            image = collection.max()
        else:
            image = collection.mean()

        # Rename after a non-empty collection is confirmed.
        return image.rename('ntl').set({
            'citylume_year': int(year),
            'citylume_temporal_mode': temporal_mode,
            'citylume_composite_stat': composite_stat,
            'citylume_source_used': source_used
        })


    def _ee_download_crs(self, export_crs, feedback):
        """
        Earth Engine download URLs are most reliable with EPSG CRS strings.
        ESRI:54034 is retained as a user-facing QGIS/analysis option, but the
        direct GEE download uses EPSG:4326 first and then the downstream QGIS
        sampling logic safely transforms grid centroids to the raster CRS.
        """
        if str(export_crs).upper() == 'ESRI:54034':
            feedback.pushInfo(
                'ESRI:54034 selected. Using EPSG:4326 for the direct GEE GeoTIFF download '
                'to avoid invalid geemap download output; QGIS will transform sampling coordinates automatically.'
            )
            return 'EPSG:4326'
        return export_crs

    def _validate_downloaded_raster_file(self, tif_path):
        """
        Return (is_valid, diagnostic_text). This catches common GEE cases
        where the output path does not exist, contains text/HTML/JSON error
        content, contains a ZIP payload, or is not readable as a QGIS raster.
        """
        tif_path = Path(tif_path)
        if not tif_path.exists():
            return False, 'file does not exist'
        size = tif_path.stat().st_size
        if size < 1024:
            head = b''
            try:
                head = tif_path.read_bytes()[:300]
            except Exception:
                pass
            return False, 'file is too small ({} bytes). Header: {}'.format(size, repr(head[:120]))
        try:
            with open(str(tif_path), 'rb') as f:
                head = f.read(8)
            if head.startswith(b'PK'):
                return False, 'file appears to be a ZIP archive, not a GeoTIFF'
            if head.startswith(b'<') or head.startswith(b'{'):
                return False, 'file appears to contain text/HTML/JSON error content, not a GeoTIFF'
        except Exception as e:
            return False, 'could not inspect file header: {}'.format(e)

        layer = QgsRasterLayer(str(tif_path), tif_path.stem)
        if not layer.isValid():
            return False, 'QgsRasterLayer cannot open the file although it exists ({} bytes)'.format(size)
        return True, 'valid GeoTIFF ({} bytes)'.format(size)

    def _download_file_from_url(self, url, out_path, feedback, timeout=600):
        """Download a URL to disk with requests. Used as the primary GEE path.
        This is more explicit than geemap.ee_export_image inside QGIS Processing,
        because some geemap versions fail silently and leave no file.
        """
        import requests

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = out_path.with_suffix(out_path.suffix + '.download')
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass

        with requests.get(url, stream=True, timeout=timeout) as response:
            status = int(getattr(response, 'status_code', 0))
            content_type = str(response.headers.get('content-type', '')).lower()
            if status != 200:
                text = ''
                try:
                    text = response.text[:500]
                except Exception:
                    pass
                raise QgsProcessingException(
                    'GEE download URL returned HTTP {}. Content-Type: {}. Message: {}'.format(status, content_type, text)
                )

            total = 0
            with open(str(tmp_path), 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if feedback.isCanceled():
                        raise QgsProcessingException('Download canceled by user.')
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)

        if total <= 0:
            raise QgsProcessingException('GEE download returned an empty response.')

        if out_path.exists():
            try:
                out_path.unlink()
            except Exception:
                pass
        tmp_path.rename(out_path)
        return out_path

    def _extract_geotiff_from_zip_if_needed(self, downloaded_path, target_tif, feedback):
        """Handle Earth Engine responses that are ZIP archives even when a TIFF is requested."""
        import zipfile
        downloaded_path = Path(downloaded_path)
        target_tif = Path(target_tif)

        try:
            head = downloaded_path.read_bytes()[:4]
        except Exception:
            return downloaded_path

        if not head.startswith(b'PK'):
            return downloaded_path

        extract_dir = target_tif.parent / ('_zip_extract_' + target_tif.stem)
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(str(downloaded_path), 'r') as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(('.tif', '.tiff'))]
            if not names:
                raise QgsProcessingException('GEE returned a ZIP file, but no .tif/.tiff file was found inside it.')
            chosen = names[0]
            zf.extract(chosen, str(extract_dir))
            src = extract_dir / chosen
            if target_tif.exists():
                try:
                    target_tif.unlink()
                except Exception:
                    pass
            try:
                import shutil
                shutil.move(str(src), str(target_tif))
            finally:
                try:
                    shutil.rmtree(str(extract_dir), ignore_errors=True)
                except Exception:
                    pass
        feedback.pushInfo('Extracted GeoTIFF from GEE ZIP response: {}'.format(str(target_tif)))
        return target_tif

    def _download_ee_image_direct(self, image, region, out_tif, scale, crs, feedback):
        """Download one Earth Engine image using ee.Image.getDownloadURL + requests.
        Returns the path to a valid local GeoTIFF candidate. Validation happens outside.
        """
        out_tif = Path(out_tif)
        params = {
            'name': out_tif.stem,
            'scale': float(scale),
            'crs': str(crs),
            'region': region,
            'filePerBand': False,
            'format': 'GEO_TIFF'
        }

        try:
            url = image.getDownloadURL(params)
        except Exception as e:
            raise QgsProcessingException(
                'Failed to create Earth Engine download URL. Try increasing scale or simplifying boundary. Error: {}'.format(e)
            )

        self._download_file_from_url(url, out_tif, feedback)
        return self._extract_geotiff_from_zip_if_needed(out_tif, out_tif, feedback)

    def _download_ntl_from_gee(
        self,
        boundary_layer,
        output_dir,
        start_year,
        end_year,
        temporal_mode,
        composite_stat,
        months_text,
        scale,
        export_crs,
        feedback
    ):
        """
        Download VIIRS NTL composites from Google Earth Engine as local GeoTIFF files
        and return them as valid QgsRasterLayer objects.

        Requirements inside QGIS Python:
        - earthengine-api package importable as ee
        - geemap package
        - Earth Engine authentication already completed, or interactive authentication available
        """
        try:
            import ee
        except Exception as e:
            raise QgsProcessingException(
                'Automatic NTL download requires the earthengine-api package. '
                'Install it in the QGIS Python environment. Error: {}'.format(e)
            )

        # geemap is no longer required for the primary download path. It is used only
        # as a secondary fallback if available. The primary path uses
        # ee.Image.getDownloadURL() + requests, which is more reliable inside QGIS.
        try:
            import geemap
        except Exception:
            geemap = None

        try:
            try:
                ee.Initialize()
            except Exception:
                feedback.pushInfo('Earth Engine is not initialized. Trying interactive authentication.')
                ee.Authenticate()
                ee.Initialize()
        except Exception as e:
            raise QgsProcessingException(
                'Google Earth Engine authentication/initialization failed. '
                'Run earthengine authenticate in the same QGIS Python environment first. Error: {}'.format(e)
            )

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        months = self._parse_months(months_text) if temporal_mode == 'monthly' else list(range(1, 13))
        region = self._boundary_to_ee_geometry(boundary_layer, ee)
        years = list(range(int(start_year), int(end_year) + 1))
        ntl_layers = []

        feedback.pushInfo('Downloading VIIRS NTL from Google Earth Engine.')
        feedback.pushInfo('Years: {}'.format(', '.join(map(str, years))))
        if temporal_mode == 'monthly':
            feedback.pushInfo('Monthly composite months: {}'.format(', '.join(map(str, months))))
        feedback.pushInfo('Composite statistic: {}'.format(composite_stat))
        download_crs = self._ee_download_crs(export_crs, feedback)
        feedback.pushInfo('Export scale: {} m | Selected CRS: {} | GEE download CRS: {}'.format(scale, export_crs, download_crs))

        for i, year in enumerate(years):
            if feedback.isCanceled():
                break

            feedback.setProgress(int((i / max(1, len(years))) * 15))
            raster_name = 'citylume_viirs_{}_{}_{}.tif'.format(temporal_mode, composite_stat, year)
            out_tif = output_dir / raster_name

            if out_tif.exists() and out_tif.stat().st_size > 0:
                feedback.pushInfo('Existing NTL GeoTIFF found, using cached file: {}'.format(str(out_tif)))
            else:
                feedback.pushInfo('Downloading NTL composite for {}'.format(year))
                image = self._compose_viirs_image(ee, year, temporal_mode, composite_stat, months).clip(region).toFloat()
                try:
                    self._download_ee_image_direct(
                        image=image,
                        region=region,
                        out_tif=out_tif,
                        scale=float(scale),
                        crs=download_crs,
                        feedback=feedback
                    )
                except Exception as e:
                    # Secondary fallback for environments where getDownloadURL is blocked,
                    # but geemap is available and functional.
                    if geemap is None:
                        raise QgsProcessingException(
                            'Direct GEE download failed for {} and geemap fallback is not available. '
                            'Try increasing export scale to 750 or 1000, or simplify the boundary. Error: {}'.format(year, e)
                        )
                    feedback.reportError('Direct GEE download failed for {}. Trying geemap fallback. Detail: {}'.format(year, e))
                    try:
                        geemap.ee_export_image(
                            image,
                            filename=str(out_tif),
                            scale=float(scale),
                            region=region,
                            crs=download_crs,
                            file_per_band=False
                        )
                    except Exception as e2:
                        raise QgsProcessingException(
                            'Both direct GEE download and geemap fallback failed for {}. '
                            'For large boundaries, increase export scale or clip to a smaller boundary. '
                            'Direct error: {} | geemap error: {}'.format(year, e, e2)
                        )

            ok, diag = self._validate_downloaded_raster_file(out_tif)
            if not ok:
                # If a cached invalid file exists, remove it and retry once with EPSG:4326.
                try:
                    if out_tif.exists():
                        out_tif.unlink()
                except Exception:
                    pass
                feedback.reportError('Downloaded NTL raster is not valid for {}. Diagnostic: {}. Retrying once with direct EPSG:4326 download.'.format(year, diag))
                image = self._compose_viirs_image(ee, year, temporal_mode, composite_stat, months).clip(region).toFloat()
                try:
                    self._download_ee_image_direct(
                        image=image,
                        region=region,
                        out_tif=out_tif,
                        scale=float(scale),
                        crs='EPSG:4326',
                        feedback=feedback
                    )
                except Exception as e:
                    if geemap is None:
                        raise QgsProcessingException(
                            'Retry direct EPSG:4326 download failed for {} and geemap fallback is not available. '
                            'Try scale 750 or 1000. Error: {}'.format(year, e)
                        )
                    try:
                        geemap.ee_export_image(
                            image,
                            filename=str(out_tif),
                            scale=float(scale),
                            region=region,
                            crs='EPSG:4326',
                            file_per_band=False
                        )
                    except Exception as e2:
                        raise QgsProcessingException(
                            'Retry download failed for {}. Try increasing export scale or simplifying boundary. '
                            'Direct retry error: {} | geemap retry error: {}'.format(year, e, e2)
                        )
                ok, diag = self._validate_downloaded_raster_file(out_tif)
                if not ok:
                    raise QgsProcessingException(
                        'Downloaded NTL raster is still not valid after direct EPSG:4326 retry: {}. Diagnostic: {}'.format(str(out_tif), diag)
                    )

            feedback.pushInfo('Validated NTL raster for {}: {}'.format(year, diag))
            layer = QgsRasterLayer(str(out_tif), 'NTL_{}'.format(year))
            QgsProject.instance().addMapLayer(layer, False)
            ntl_layers.append(layer)

        if len(ntl_layers) < 2:
            raise QgsProcessingException('Automatic NTL download produced fewer than two valid rasters.')

        feedback.pushInfo('Automatic NTL download finished. Files saved to: {}'.format(str(output_dir)))
        return ntl_layers, years

    # -------------------------------------------------------------------------
    # Basic utilities
    # -------------------------------------------------------------------------

    def _parse_years(self, years_text, layers):
        if years_text:
            values = []
            for part in years_text.split(','):
                part = part.strip()
                if part:
                    values.append(int(part))
            return values

        years = []
        for layer in layers:
            name = layer.name()
            found = re.findall(r'(19\d{2}|20\d{2}|21\d{2})', name)
            if not found:
                source = layer.source()
                found = re.findall(r'(19\d{2}|20\d{2}|21\d{2})', source)
            if found:
                years.append(int(found[-1]))
            else:
                raise QgsProcessingException(
                    'Could not extract year from raster name: {}. Please fill the Years parameter manually.'.format(name)
                )
        return years

    def _materialize_source(self, source, name, context):
        layer = QgsProcessingUtils.mapLayerFromString(source.sourceName(), context)
        if layer is not None and layer.isValid():
            return layer

        features = list(source.getFeatures())
        crs = source.sourceCrs()
        geom_type = QgsWkbTypes.displayString(source.wkbType())
        uri = '{}?crs={}'.format(geom_type, crs.authid())
        mem = QgsVectorLayer(uri, name, 'memory')
        mem_dp = mem.dataProvider()
        mem_dp.addAttributes(source.fields())
        mem.updateFields()
        mem_dp.addFeatures(features)
        mem.updateExtents()
        return mem

    def _resolve_output_layer(self, output_value, context, expected_name='processing output'):
        """
        QGIS Processing sometimes returns a layer object, a layer id, or a source string.
        This helper normalizes that return value into a valid QgsVectorLayer/QgsRasterLayer.
        It prevents errors such as: AttributeError: 'str' object has no attribute 'getFeatures'.
        """
        if hasattr(output_value, 'isValid') and output_value.isValid():
            return output_value

        if isinstance(output_value, str):
            layer = QgsProcessingUtils.mapLayerFromString(output_value, context)
            if layer is not None and layer.isValid():
                return layer

            layer = QgsProject.instance().mapLayer(output_value)
            if layer is not None and layer.isValid():
                return layer

            # Fallback for file paths or provider source strings.
            vlayer = QgsVectorLayer(output_value, expected_name, 'ogr')
            if vlayer.isValid():
                return vlayer

            rlayer = QgsRasterLayer(output_value, expected_name)
            if rlayer.isValid():
                return rlayer

        raise QgsProcessingException('Could not resolve {} as a valid QGIS layer: {}'.format(expected_name, output_value))

    def _safe_float(self, value, default=0.0):
        try:
            if value is None:
                return default
            if isinstance(value, QVariant):
                value = value.value()
            if value == '':
                return default
            v = float(value)
            if math.isnan(v) or math.isinf(v):
                return default
            return v
        except Exception:
            return default

    def _normalize_series(self, s):
        import numpy as np
        arr = np.array(s, dtype=float)
        valid = np.isfinite(arr)
        out = np.zeros_like(arr, dtype=float)
        if not valid.any():
            return out
        mn = np.nanmin(arr[valid])
        mx = np.nanmax(arr[valid])
        if abs(mx - mn) < 1e-12:
            out[valid] = 0.0
        else:
            out[valid] = (arr[valid] - mn) / (mx - mn)
        out[~valid] = 0.0
        return out

    def _entropy(self, values):
        total = sum(values)
        if total <= 0:
            return 0.0
        ent = 0.0
        for v in values:
            if v > 0:
                p = v / total
                ent -= p * math.log(p)
        max_ent = math.log(len([v for v in values if v > 0])) if len([v for v in values if v > 0]) > 1 else 1.0
        return float(ent / max_ent) if max_ent > 0 else 0.0

    # -------------------------------------------------------------------------
    # Grid and aggregation
    # -------------------------------------------------------------------------

    def _init_grid_records(self, grid_layer):
        records = {}
        for i, f in enumerate(grid_layer.getFeatures()):
            fid = int(f.id())
            geom = f.geometry()
            area = geom.area() if geom and not geom.isEmpty() else 0.0
            centroid = geom.centroid().asPoint() if geom and not geom.isEmpty() else QgsPointXY(0, 0)
            records[fid] = {
                'grid_fid': fid,
                'grid_id': i + 1,
                'area_m2': float(area),
                'centroid_x': float(centroid.x()),
                'centroid_y': float(centroid.y()),
                'poi_count': 0,
                'poi_density': 0.0,
                'poi_diversity': 0.0,
                'poi_dom_category': '',
                'building_count': 0,
                'building_density': 0.0,
                'building_footprint_area': 0.0,
                'building_coverage_ratio': 0.0,
                'building_height_mean': 0.0,
                'building_height_max': 0.0,
                'occupancy_mix': 0.0,
                'occupancy_dom': '',
                'road_length_m': 0.0,
                'road_density': 0.0,
                'major_road_length_m': 0.0,
                'major_road_density': 0.0,
                'intersection_count': 0,
                'intersection_density': 0.0,
                'road_accessibility_score': 0.0
            }
        return records

    def _extract_ntl_by_grid(self, grid_layer, grid_records, ntl_layers, years, feedback):
        import numpy as np

        grid_features = list(grid_layer.getFeatures())
        for year, raster in zip(years, ntl_layers):
            if feedback.isCanceled():
                break

            provider = raster.dataProvider()
            band = 1
            r_crs = raster.crs()
            g_crs = grid_layer.crs()
            transform_to_raster = None
            if r_crs != g_crs:
                transform_to_raster = QgsCoordinateTransform(g_crs, r_crs, QgsProject.instance())

            feedback.pushInfo('Sampling NTL raster for year {}'.format(year))

            for idx, gf in enumerate(grid_features):
                if idx % 200 == 0:
                    feedback.setProgress(int(idx / max(1, len(grid_features)) * 35))

                geom = gf.geometry()
                if geom is None or geom.isEmpty():
                    val = 0.0
                else:
                    centroid = geom.centroid().asPoint()
                    pt = QgsPointXY(centroid.x(), centroid.y())
                    if transform_to_raster is not None:
                        try:
                            pt = transform_to_raster.transform(pt)
                        except Exception:
                            pass
                    result = provider.sample(pt, band)
                    try:
                        val = float(result[0]) if result[1] else 0.0
                    except Exception:
                        val = 0.0
                    if math.isnan(val) or math.isinf(val):
                        val = 0.0

                grid_records[int(gf.id())]['ntl_{}'.format(year)] = val

    def _aggregate_poi(self, grid_layer, grid_records, poi_layer, category_field, feedback):
        grid_features = list(grid_layer.getFeatures())
        grid_index = QgsSpatialIndex()
        geom_by_fid = {}
        for gf in grid_features:
            grid_index.addFeature(gf)
            geom_by_fid[int(gf.id())] = gf.geometry()

        category_counts = defaultdict(Counter)

        for i, pf in enumerate(poi_layer.getFeatures()):
            if i % 500 == 0:
                feedback.setProgress(35 + int((i % 5000) / 5000 * 10))
            geom = pf.geometry()
            if geom is None or geom.isEmpty():
                continue
            bbox = geom.boundingBox()
            candidates = grid_index.intersects(bbox)
            cat = str(pf[category_field]) if category_field and category_field in pf.fields().names() else 'Unknown'
            for fid in candidates:
                ggeom = geom_by_fid.get(int(fid))
                if ggeom is not None and ggeom.intersects(geom):
                    rec = grid_records[int(fid)]
                    rec['poi_count'] += 1
                    category_counts[int(fid)][cat] += 1
                    break

        for fid, rec in grid_records.items():
            area_km2 = rec['area_m2'] / 1_000_000.0 if rec['area_m2'] > 0 else 0.0
            rec['poi_density'] = rec['poi_count'] / area_km2 if area_km2 > 0 else 0.0
            counts = category_counts.get(fid, Counter())
            rec['poi_diversity'] = self._entropy(list(counts.values()))
            rec['poi_dom_category'] = counts.most_common(1)[0][0] if counts else ''

    def _aggregate_buildings(self, grid_layer, grid_records, building_layer, height_field, occupancy_field, feedback):
        grid_features = list(grid_layer.getFeatures())
        grid_index = QgsSpatialIndex()
        geom_by_fid = {}
        for gf in grid_features:
            grid_index.addFeature(gf)
            geom_by_fid[int(gf.id())] = gf.geometry()

        height_values = defaultdict(list)
        occupancy_counts = defaultdict(Counter)

        for i, bf in enumerate(building_layer.getFeatures()):
            if i % 500 == 0:
                feedback.setProgress(45 + int((i % 5000) / 5000 * 10))
            bgeom = bf.geometry()
            if bgeom is None or bgeom.isEmpty():
                continue

            bbox = bgeom.boundingBox()
            candidates = grid_index.intersects(bbox)
            b_area = bgeom.area()
            height = self._safe_float(bf[height_field], 0.0) if height_field and height_field in bf.fields().names() else 0.0
            occ = str(bf[occupancy_field]) if occupancy_field and occupancy_field in bf.fields().names() else 'Unknown'

            best_fid = None
            best_area = 0.0
            for fid in candidates:
                ggeom = geom_by_fid.get(int(fid))
                if ggeom is None:
                    continue
                if not ggeom.intersects(bgeom):
                    continue
                inter = ggeom.intersection(bgeom)
                ia = inter.area() if inter and not inter.isEmpty() else 0.0
                if ia > best_area:
                    best_area = ia
                    best_fid = int(fid)

            if best_fid is not None:
                rec = grid_records[best_fid]
                rec['building_count'] += 1
                rec['building_footprint_area'] += float(best_area if best_area > 0 else b_area)
                if height > 0:
                    height_values[best_fid].append(height)
                occupancy_counts[best_fid][occ] += 1

        for fid, rec in grid_records.items():
            area_km2 = rec['area_m2'] / 1_000_000.0 if rec['area_m2'] > 0 else 0.0
            rec['building_density'] = rec['building_count'] / area_km2 if area_km2 > 0 else 0.0
            rec['building_coverage_ratio'] = rec['building_footprint_area'] / rec['area_m2'] if rec['area_m2'] > 0 else 0.0

            hv = height_values.get(fid, [])
            if hv:
                rec['building_height_mean'] = float(sum(hv) / len(hv))
                rec['building_height_max'] = float(max(hv))

            counts = occupancy_counts.get(fid, Counter())
            rec['occupancy_mix'] = self._entropy(list(counts.values()))
            rec['occupancy_dom'] = counts.most_common(1)[0][0] if counts else ''


    def _init_empty_road_indicators(self, grid_records):
        for rec in grid_records.values():
            rec.setdefault('road_length_m', 0.0)
            rec.setdefault('road_density', 0.0)
            rec.setdefault('major_road_length_m', 0.0)
            rec.setdefault('major_road_density', 0.0)
            rec.setdefault('intersection_count', 0)
            rec.setdefault('intersection_density', 0.0)
            rec.setdefault('road_accessibility_score', 0.0)

    def _aggregate_roads(self, grid_layer, grid_records, road_layer, road_class_field, major_road_classes_text, feedback):
        major_classes = set([c.strip().lower() for c in str(major_road_classes_text).split(',') if c.strip()])
        grid_features = list(grid_layer.getFeatures())
        grid_index = QgsSpatialIndex()
        geom_by_fid = {}
        for gf in grid_features:
            grid_index.addFeature(gf)
            geom_by_fid[int(gf.id())] = gf.geometry()

        endpoint_points = []
        road_count = 0
        for rf in road_layer.getFeatures():
            road_count += 1
            if road_count % 500 == 0:
                feedback.setProgress(55 + int((road_count % 5000) / 5000 * 10))

            rgeom = rf.geometry()
            if rgeom is None or rgeom.isEmpty():
                continue

            rclass = ''
            if road_class_field and road_class_field in rf.fields().names():
                rclass = str(rf[road_class_field]).lower()
            is_major = any(mc in rclass for mc in major_classes) if major_classes else False

            candidates = grid_index.intersects(rgeom.boundingBox())
            for fid in candidates:
                ggeom = geom_by_fid.get(int(fid))
                if ggeom is None or not ggeom.intersects(rgeom):
                    continue
                inter = ggeom.intersection(rgeom)
                length = inter.length() if inter and not inter.isEmpty() else 0.0
                if length > 0:
                    rec = grid_records[int(fid)]
                    rec['road_length_m'] += float(length)
                    if is_major:
                        rec['major_road_length_m'] += float(length)

            try:
                if rgeom.isMultipart():
                    parts = rgeom.asMultiPolyline()
                else:
                    parts = [rgeom.asPolyline()]
                for part in parts:
                    if part and len(part) >= 2:
                        endpoint_points.append(QgsGeometry.fromPointXY(QgsPointXY(part[0])))
                        endpoint_points.append(QgsGeometry.fromPointXY(QgsPointXY(part[-1])))
            except Exception:
                pass

        for pt_geom in endpoint_points:
            for fid in grid_index.intersects(pt_geom.boundingBox()):
                ggeom = geom_by_fid.get(int(fid))
                if ggeom is not None and ggeom.intersects(pt_geom):
                    grid_records[int(fid)]['intersection_count'] += 1
                    break

        # Density and normalized accessibility score.
        road_densities = []
        major_densities = []
        inter_densities = []
        for rec in grid_records.values():
            area_km2 = rec['area_m2'] / 1_000_000.0 if rec['area_m2'] > 0 else 0.0
            rec['road_density'] = rec['road_length_m'] / area_km2 if area_km2 > 0 else 0.0
            rec['major_road_density'] = rec['major_road_length_m'] / area_km2 if area_km2 > 0 else 0.0
            rec['intersection_density'] = rec['intersection_count'] / area_km2 if area_km2 > 0 else 0.0
            road_densities.append(rec['road_density'])
            major_densities.append(rec['major_road_density'])
            inter_densities.append(rec['intersection_density'])

        rd_norm = self._normalize_series(road_densities)
        md_norm = self._normalize_series(major_densities)
        id_norm = self._normalize_series(inter_densities)
        for i, rec in enumerate(grid_records.values()):
            rec['road_accessibility_score'] = float(0.45 * rd_norm[i] + 0.35 * md_norm[i] + 0.20 * id_norm[i])

    def _init_empty_population_indicators(self, grid_records):
        for rec in grid_records.values():
            rec.setdefault('pop_sum', 0.0)
            rec.setdefault('pop_mean', 0.0)
            rec.setdefault('pop_density', 0.0)

    def _extract_population_raster_by_grid(self, grid_layer, grid_records, pop_raster, feedback):
        """
        Lightweight population extraction using centroid sampling. The value is interpreted
        as population count or population density depending on the raster supplied by the user.
        For spatial planning decision support, the sampled value is stored as pop_mean and pop_sum proxy.
        """
        provider = pop_raster.dataProvider()
        band = 1
        r_crs = pop_raster.crs()
        g_crs = grid_layer.crs()
        transform_to_raster = None
        if r_crs != g_crs:
            transform_to_raster = QgsCoordinateTransform(g_crs, r_crs, QgsProject.instance())

        values = []
        grid_features = list(grid_layer.getFeatures())
        for idx, gf in enumerate(grid_features):
            if idx % 200 == 0:
                feedback.setProgress(58 + int(idx / max(1, len(grid_features)) * 5))
            geom = gf.geometry()
            val = 0.0
            if geom is not None and not geom.isEmpty():
                pt = QgsPointXY(geom.centroid().asPoint())
                if transform_to_raster is not None:
                    try:
                        pt = transform_to_raster.transform(pt)
                    except Exception:
                        pass
                try:
                    result = provider.sample(pt, band)
                    val = float(result[0]) if result[1] else 0.0
                except Exception:
                    val = 0.0
                if math.isnan(val) or math.isinf(val):
                    val = 0.0
            rec = grid_records[int(gf.id())]
            rec['pop_mean'] = float(val)
            # If raster is count-per-pixel, this is a proxy. If density, pop_density is more meaningful.
            rec['pop_sum'] = float(val)
            area_km2 = rec.get('area_m2', 0.0) / 1_000_000.0 if rec.get('area_m2', 0.0) > 0 else 0.0
            rec['pop_density'] = float(val / area_km2) if area_km2 > 0 else 0.0
            values.append(val)

        feedback.pushInfo('Existing population raster sampled for {} grid cells.'.format(len(values)))

    def _init_empty_planning_zone_indicators(self, grid_records):
        for rec in grid_records.values():
            rec.setdefault('planning_zone', '')
            rec.setdefault('planning_zone_area_m2', 0.0)
            rec.setdefault('planning_zone_share', 0.0)
            rec.setdefault('planning_intent_group', 'Unknown Plan')

    def _aggregate_planning_zones(self, grid_layer, grid_records, planning_zone_layer, planning_zone_field, feedback):
        grid_features = list(grid_layer.getFeatures())
        grid_index = QgsSpatialIndex()
        geom_by_fid = {}
        for gf in grid_features:
            grid_index.addFeature(gf)
            geom_by_fid[int(gf.id())] = gf.geometry()

        best = {}
        for i, zf in enumerate(planning_zone_layer.getFeatures()):
            if i % 300 == 0:
                feedback.setProgress(63 + int((i % 3000) / 3000 * 3))
            zgeom = zf.geometry()
            if zgeom is None or zgeom.isEmpty():
                continue
            zname = str(zf[planning_zone_field]) if planning_zone_field and planning_zone_field in zf.fields().names() else ''
            for fid in grid_index.intersects(zgeom.boundingBox()):
                ggeom = geom_by_fid.get(int(fid))
                if ggeom is None or not ggeom.intersects(zgeom):
                    continue
                inter = ggeom.intersection(zgeom)
                ia = inter.area() if inter and not inter.isEmpty() else 0.0
                if ia <= 0:
                    continue
                if fid not in best or ia > best[fid][1]:
                    best[fid] = (zname, ia)

        for fid, rec in grid_records.items():
            if fid in best:
                zname, area = best[fid]
                rec['planning_zone'] = zname
                rec['planning_zone_area_m2'] = float(area)
                rec['planning_zone_share'] = float(area / rec['area_m2']) if rec.get('area_m2', 0) > 0 else 0.0
                rec['planning_intent_group'] = self._classify_planning_intent(zname)
            else:
                rec['planning_zone'] = ''
                rec['planning_zone_area_m2'] = 0.0
                rec['planning_zone_share'] = 0.0
                rec['planning_intent_group'] = 'No Plan Overlay'

    def _classify_planning_intent(self, text):
        s = str(text).lower()
        if not s:
            return 'Unknown Plan'
        commercial_kw = ['trade', 'service', 'commercial', 'business', 'cbd', 'center', 'mixed-use', 'mixed']
        center_kw = ['service center', 'city center', 'sub-center', 'central area', 'urban center', 'tod', 'transit']
        industry_kw = ['industry', 'industrial', 'warehousing', 'warehouse', 'port', 'airport', 'logistics']
        residential_kw = ['settlement', 'housing', 'dwelling', 'residential']
        protected_kw = ['protected', 'forest', 'buffer', 'conservation', 'green open space', 'park', 'farmland', 'agriculture', 'water body']
        infrastructure_kw = ['road', 'transport', 'terminal', 'station', 'infrastructure', 'utility']
        if any(k in s for k in protected_kw):
            return 'Protected or Low-Urbanization Zone'
        if any(k in s for k in center_kw):
            return 'Planned Center Zone'
        if any(k in s for k in commercial_kw):
            return 'Commercial or Mixed-Use Zone'
        if any(k in s for k in industry_kw):
            return 'Industrial or Logistics Zone'
        if any(k in s for k in residential_kw):
            return 'Residential Zone'
        if any(k in s for k in infrastructure_kw):
            return 'Infrastructure or Transport Zone'
        return 'Other Planned Zone'

    def _init_empty_planned_center_indicators(self, grid_records):
        for rec in grid_records.values():
            rec.setdefault('planned_center_count', 0)
            rec.setdefault('planned_center_level', '')
            rec.setdefault('planned_center_proximity_flag', 0)

    def _aggregate_planned_centers(self, grid_layer, grid_records, planned_center_layer, level_field, feedback):
        # Always initialize fields first. This prevents KeyError when a planned-center
        # layer is supplied, because _init_empty_planned_center_indicators() is only
        # called in the no-input branch.
        self._init_empty_planned_center_indicators(grid_records)

        grid_features = list(grid_layer.getFeatures())
        grid_index = QgsSpatialIndex()
        geom_by_fid = {}
        for gf in grid_features:
            grid_index.addFeature(gf)
            geom_by_fid[int(gf.id())] = gf.geometry()

        levels = defaultdict(Counter)
        for i, cf in enumerate(planned_center_layer.getFeatures()):
            if i % 200 == 0:
                feedback.setProgress(66 + int((i % 2000) / 2000 * 2))
            cgeom = cf.geometry()
            if cgeom is None or cgeom.isEmpty():
                continue
            clevel = str(cf[level_field]) if level_field and level_field in cf.fields().names() else 'Planned Center'
            candidates = grid_index.intersects(cgeom.boundingBox())
            hit = False
            for fid in candidates:
                ggeom = geom_by_fid.get(int(fid))
                if ggeom is not None and ggeom.intersects(cgeom):
                    rec = grid_records[int(fid)]
                    rec.setdefault('planned_center_count', 0)
                    rec.setdefault('planned_center_level', '')
                    rec.setdefault('planned_center_proximity_flag', 0)
                    rec['planned_center_count'] += 1
                    rec['planned_center_proximity_flag'] = 1
                    levels[int(fid)][clevel] += 1
                    hit = True
            # For point centers that do not intersect due to precision, nearest is intentionally not forced.

        for fid, rec in grid_records.items():
            cnt = levels.get(fid, Counter())
            rec['planned_center_level'] = cnt.most_common(1)[0][0] if cnt else ''

    def _records_to_dataframe(self, grid_records, years):
        import pandas as pd

        rows = []
        for fid, rec in grid_records.items():
            row = dict(rec)
            for y in years:
                row.setdefault('ntl_{}'.format(y), 0.0)
            rows.append(row)
        df = pd.DataFrame(rows)
        df = df.sort_values('grid_id').reset_index(drop=True)
        return df

    # -------------------------------------------------------------------------
    # Spatial planning intelligence modules
    # -------------------------------------------------------------------------

    def _init_empty_spatial_planning_outputs(self, df):
        import numpy as np
        df['planning_activity_alignment_score'] = 0.0
        df['planning_mismatch_type'] = 'Spatial Planning Modules Disabled'
        df['urban_center_hierarchy'] = 'Not Classified'
        df['center_hierarchy_score'] = 0.0
        df['spatial_planning_action'] = 'No Action Matrix'
        df['spatial_planning_priority'] = 'Not Classified'
        df['spatial_planning_rationale'] = ''
        return df

    def _run_spatial_planning_intelligence_modules(self, df, core_top_percent):
        import numpy as np

        # Ensure optional columns exist.
        defaults = {
            'pop_mean': 0.0,
            'pop_sum': 0.0,
            'pop_density': 0.0,
            'planning_zone': '',
            'planning_intent_group': 'Unknown Plan',
            'planned_center_count': 0,
            'planned_center_level': '',
            'planned_center_proximity_flag': 0,
            'road_accessibility_norm': 0.0,
            'future_core_probability': 0.0,
            'shrinking_risk': 0.0,
            'ntl_end_norm': 0.0,
            'ntl_slope_norm': 0.0,
            'poi_density_norm': 0.0,
            'building_density_norm': 0.0,
            'building_height_norm': 0.0,
            'bcr_norm': 0.0,
        }
        for c, v in defaults.items():
            if c not in df.columns:
                df[c] = v

        df['pop_density_norm'] = self._normalize_series(df['pop_density'].fillna(0))
        df['pop_mean_norm'] = self._normalize_series(df['pop_mean'].fillna(0))

        # Activity pressure score: empirically observed urban activity plus population.
        df['activity_pressure_score'] = np.clip(
            0.24 * df['ntl_end_norm'] +
            0.18 * df['ntl_slope_norm'] +
            0.17 * df['poi_density_norm'] +
            0.14 * df['building_density_norm'] +
            0.10 * df['road_accessibility_norm'] +
            0.17 * df['pop_density_norm'],
            0, 1
        )

        # Center hierarchy score: future core + observed activity + accessibility + population.
        df['center_hierarchy_score'] = np.clip(
            0.30 * df['future_core_probability'] +
            0.20 * df['ntl_end_norm'] +
            0.15 * df['poi_density_norm'] +
            0.12 * df['building_density_norm'] +
            0.10 * df['road_accessibility_norm'] +
            0.13 * df['pop_density_norm'],
            0, 1
        )

        # Quantile-based hierarchy thresholds.
        q90 = np.nanpercentile(df['center_hierarchy_score'], 90) if len(df) else 1
        q75 = np.nanpercentile(df['center_hierarchy_score'], 75) if len(df) else 1
        q60 = np.nanpercentile(df['center_hierarchy_score'], 60) if len(df) else 1

        def hierarchy(row):
            score = row['center_hierarchy_score']
            planned = row.get('planned_center_proximity_flag', 0) > 0
            if score >= q90 and row['future_core_probability'] >= 0.65:
                return 'Primary Urban Center'
            if score >= q75 and row['future_core_probability'] >= 0.55:
                return 'Secondary Urban Center'
            if score >= q60 and row['ntl_slope_norm'] >= 0.55:
                return 'Emerging Local Center'
            if planned and score < q60:
                return 'Planned Center with Weak Empirical Signal'
            if row['shrinking_risk'] >= 0.70:
                return 'Declining or Shrinking Center'
            return 'Non-Center or Low-Order Area'

        df['urban_center_hierarchy'] = df.apply(hierarchy, axis=1)

        # Planning mismatch type.
        def mismatch(row):
            intent = str(row.get('planning_intent_group', 'Unknown Plan'))
            activity = float(row.get('activity_pressure_score', 0))
            future_core = float(row.get('future_core_probability', 0))
            shrink = float(row.get('shrinking_risk', 0))
            planned_center = int(row.get('planned_center_proximity_flag', 0)) > 0
            dyn = str(row.get('urban_dynamics_class', ''))

            if intent in ['Protected or Low-Urbanization Zone'] and (activity >= 0.58 or future_core >= 0.62):
                return 'High Activity in Protected or Low-Urbanization Zone'
            if intent in ['Planned Center Zone', 'Commercial or Mixed-Use Zone'] and activity >= 0.55 and future_core >= 0.55:
                return 'Planned Core, Active Core'
            if intent in ['Planned Center Zone', 'Commercial or Mixed-Use Zone'] and activity < 0.35 and future_core < 0.45:
                return 'Planned Core, Weak Activity'
            if planned_center and activity < 0.38:
                return 'Planned Center with Weak Activity'
            if intent not in ['Planned Center Zone', 'Commercial or Mixed-Use Zone'] and future_core >= 0.70:
                return 'Unplanned Emerging Core'
            if intent in ['Residential Zone'] and activity >= 0.62 and future_core >= 0.60:
                return 'Residential Zone Under Activity Intensification'
            if intent in ['Industrial or Logistics Zone'] and 'Isolated Light Anomaly' in dyn:
                return 'Industrial Light Anomaly, Not Urban Service Core'
            if shrink >= 0.70 and intent in ['Planned Center Zone', 'Commercial or Mixed-Use Zone']:
                return 'Planned Core Under Shrinking Pressure'
            if shrink >= 0.70:
                return 'Shrinking Risk Area'
            if future_core >= 0.60 and intent in ['No Plan Overlay', 'Unknown Plan', 'Other Planned Zone']:
                return 'Predicted Growth Outside Clear Plan Direction'
            return 'Plan-Activity Relatively Aligned or Neutral'

        df['planning_mismatch_type'] = df.apply(mismatch, axis=1)

        def alignment_score(row):
            mismatch_type = row['planning_mismatch_type']
            if mismatch_type in ['Planned Core, Active Core', 'Plan-Activity Relatively Aligned or Neutral']:
                return 1.0
            if mismatch_type in ['Planned Core, Weak Activity', 'Planned Center with Weak Activity']:
                return 0.45
            if mismatch_type in ['Unplanned Emerging Core', 'Predicted Growth Outside Clear Plan Direction',
                                 'Residential Zone Under Activity Intensification']:
                return 0.35
            if mismatch_type in ['High Activity in Protected or Low-Urbanization Zone',
                                 'Planned Core Under Shrinking Pressure']:
                return 0.20
            return 0.60

        df['planning_activity_alignment_score'] = df.apply(alignment_score, axis=1)

        # Spatial Planning Action Matrix.
        def action_priority(row):
            future_core = float(row.get('future_core_probability', 0))
            shrink = float(row.get('shrinking_risk', 0))
            mismatch_type = str(row.get('planning_mismatch_type', ''))
            activity = float(row.get('activity_pressure_score', 0))
            popn = float(row.get('pop_density_norm', 0))

            if mismatch_type == 'High Activity in Protected or Low-Urbanization Zone':
                return ('Critical', 'Growth Control and Environmental Protection Audit',
                        'High activity pressure is emerging inside protected or low-urbanization planning intent.')
            if mismatch_type in ['Unplanned Emerging Core', 'Predicted Growth Outside Clear Plan Direction'] and future_core >= 0.70:
                return ('High', 'Evaluate New Sub-Center or Revise Spatial Structure',
                        'Future core probability is high but the planning direction does not clearly recognize this center.')
            if mismatch_type in ['Planned Core, Weak Activity', 'Planned Center with Weak Activity']:
                return ('High', 'Activate Planned Center through Infrastructure and Public Facility Investment',
                        'A planned center exists but empirical activity and future-core signal remain weak.')
            if shrink >= 0.70:
                return ('High', 'Urban Renewal, Adaptive Reuse, and Service Consolidation',
                        'Shrinking risk is high and requires regeneration-oriented planning response.')
            if row.get('urban_center_hierarchy') in ['Primary Urban Center', 'Secondary Urban Center']:
                return ('Medium-High', 'Strengthen Urban Center Hierarchy and Manage Intensification',
                        'The area functions as an empirical urban center and needs controlled intensification.')
            if activity >= 0.60 and popn >= 0.55:
                return ('Medium', 'Upgrade Urban Services and Local Infrastructure',
                        'Activity and population pressure indicate rising service demand.')
            if str(row.get('urban_dynamics_class', '')) == 'Corridor Growth':
                return ('Medium', 'Manage Corridor Growth and Prevent Ribbon Development',
                        'Growth follows road corridors and should be controlled through access management and zoning detail.')
            if str(row.get('urban_dynamics_class', '')) == 'Urban Expansion':
                return ('Medium', 'Guide Urban Expansion and Check Infrastructure Capacity',
                        'Urban activity is expanding and needs phased development control.')
            return ('Low', 'Monitor and Maintain Existing Spatial Function',
                    'No urgent mismatch or high-risk planning signal is detected.')

        actions = df.apply(action_priority, axis=1)
        df['spatial_planning_priority'] = [a[0] for a in actions]
        df['spatial_planning_action'] = [a[1] for a in actions]
        df['spatial_planning_rationale'] = [a[2] for a in actions]

        return df

    def _planning_mismatch_summary(self, df):
        import pandas as pd
        if 'planning_mismatch_type' not in df.columns:
            return pd.DataFrame()
        g = df.groupby('planning_mismatch_type').agg(
            grid_count=('grid_id', 'count'),
            area_m2=('area_m2', 'sum'),
            mean_activity_pressure=('activity_pressure_score', 'mean'),
            mean_future_core=('future_core_probability', 'mean'),
            mean_shrinking_risk=('shrinking_risk', 'mean'),
            mean_alignment_score=('planning_activity_alignment_score', 'mean')
        ).reset_index()
        g['area_ha'] = g['area_m2'] / 10000.0
        return g.sort_values(['mean_future_core', 'grid_count'], ascending=[False, False])

    def _center_hierarchy_summary(self, df):
        import pandas as pd
        if 'urban_center_hierarchy' not in df.columns:
            return pd.DataFrame()
        g = df.groupby('urban_center_hierarchy').agg(
            grid_count=('grid_id', 'count'),
            area_m2=('area_m2', 'sum'),
            mean_center_score=('center_hierarchy_score', 'mean'),
            mean_future_core=('future_core_probability', 'mean'),
            mean_pop_density=('pop_density', 'mean'),
            mean_poi_density=('poi_density', 'mean')
        ).reset_index()
        g['area_ha'] = g['area_m2'] / 10000.0
        return g.sort_values('mean_center_score', ascending=False)

    def _action_matrix_summary(self, df):
        import pandas as pd
        if 'spatial_planning_action' not in df.columns:
            return pd.DataFrame()
        g = df.groupby(['spatial_planning_priority', 'spatial_planning_action']).agg(
            grid_count=('grid_id', 'count'),
            area_m2=('area_m2', 'sum'),
            mean_future_core=('future_core_probability', 'mean'),
            mean_shrinking_risk=('shrinking_risk', 'mean'),
            mean_activity_pressure=('activity_pressure_score', 'mean')
        ).reset_index()
        g['area_ha'] = g['area_m2'] / 10000.0
        order = {'Critical': 1, 'High': 2, 'Medium-High': 3, 'Medium': 4, 'Low': 5}
        g['_order'] = g['spatial_planning_priority'].map(order).fillna(99)
        return g.sort_values(['_order', 'grid_count'], ascending=[True, False]).drop(columns=['_order'])

    # -------------------------------------------------------------------------
    # Trend, prediction, diagnosis
    # -------------------------------------------------------------------------


    def _apply_ntl_downscaling(self, df, years, downscale_mode, downscale_blend, feedback):
        import numpy as np
        blend = max(0.0, min(1.0, float(downscale_blend)))

        # Dasymetric weight from urban predictors. All components are normalized to 0-1.
        for c in [
            'building_density', 'building_height_mean', 'building_coverage_ratio',
            'poi_density', 'poi_diversity', 'occupancy_mix', 'road_accessibility_score'
        ]:
            if c not in df.columns:
                df[c] = 0.0

        bld_d = self._normalize_series(df['building_density'].fillna(0))
        bld_h = self._normalize_series(df['building_height_mean'].fillna(0))
        bcr = self._normalize_series(df['building_coverage_ratio'].fillna(0))
        poi_d = self._normalize_series(df['poi_density'].fillna(0))
        poi_div = self._normalize_series(df['poi_diversity'].fillna(0))
        occ_mix = self._normalize_series(df['occupancy_mix'].fillna(0))
        road_acc = self._normalize_series(df['road_accessibility_score'].fillna(0))

        weight = (
            0.22 * bld_d +
            0.15 * bld_h +
            0.13 * bcr +
            0.20 * poi_d +
            0.10 * poi_div +
            0.08 * occ_mix +
            0.12 * road_acc
        )
        weight = np.array(weight, dtype=float)
        weight = np.where(np.isfinite(weight), weight, 0.0)
        if float(weight.sum()) <= 0:
            weight = np.ones(len(df), dtype=float)
        weight = weight / max(float(weight.sum()), 1e-12)
        df['downscale_weight'] = weight

        if downscale_mode == 'ML-Based Dasymetric Downscaling':
            try:
                from sklearn.ensemble import ExtraTreesRegressor
                X = np.column_stack([bld_d, bld_h, bcr, poi_d, poi_div, occ_mix, road_acc])
                for y in years:
                    col = 'ntl_{}'.format(y)
                    raw = df[col].fillna(0).values.astype(float)
                    df['raw_ntl_{}'.format(y)] = raw
                    if len(df) >= 15 and np.nanstd(raw) > 0:
                        model = ExtraTreesRegressor(n_estimators=120, random_state=42, min_samples_leaf=2, n_jobs=-1)
                        model.fit(X, raw)
                        ml_pred = np.maximum(model.predict(X), 0)
                        total = float(np.nansum(raw))
                        if float(np.nansum(ml_pred)) > 0 and total > 0:
                            ml_scaled = ml_pred / float(np.nansum(ml_pred)) * total
                        else:
                            ml_scaled = weight * total
                        df[col] = np.maximum((1.0 - blend) * raw + blend * ml_scaled, 0)
                    else:
                        total = float(np.nansum(raw))
                        redistributed = weight * total
                        df[col] = np.maximum((1.0 - blend) * raw + blend * redistributed, 0)
                df['downscale_mode_used'] = downscale_mode
                return df
            except Exception as e:
                feedback.reportError('ML-based downscaling failed. Weighted downscaling fallback is used. Error: {}'.format(e))

        for y in years:
            col = 'ntl_{}'.format(y)
            raw = df[col].fillna(0).values.astype(float)
            df['raw_ntl_{}'.format(y)] = raw
            total = float(np.nansum(raw))
            redistributed = weight * total
            df[col] = np.maximum((1.0 - blend) * raw + blend * redistributed, 0)
        df['downscale_mode_used'] = 'Building-POI Weighted Downscaling'
        return df

    def _calculate_trend_indicators(self, df, years, min_ntl_threshold):
        import numpy as np

        year_arr = np.array(years, dtype=float)
        ntl_cols = ['ntl_{}'.format(y) for y in years]
        vals = df[ntl_cols].fillna(0).values.astype(float)
        vals[~np.isfinite(vals)] = 0.0

        start = vals[:, 0]
        end = vals[:, -1]
        mean = vals.mean(axis=1)
        maxv = vals.max(axis=1)
        minv = vals.min(axis=1)
        stdv = vals.std(axis=1)

        slopes = []
        intercepts = []
        acceleration = []
        for row in vals:
            if len(year_arr) >= 2:
                p = np.polyfit(year_arr, row, 1)
                slopes.append(float(p[0]))
                intercepts.append(float(p[1]))
            else:
                slopes.append(0.0)
                intercepts.append(float(row[0]) if len(row) else 0.0)

            if len(year_arr) >= 3:
                p2 = np.polyfit(year_arr - year_arr[0], row, 2)
                acceleration.append(float(p2[0]))
            else:
                acceleration.append(0.0)

        slopes = np.array(slopes, dtype=float)
        acceleration = np.array(acceleration, dtype=float)

        year_span = max(1.0, float(years[-1] - years[0]))
        cagr = np.zeros(len(df), dtype=float)
        for i in range(len(df)):
            if start[i] > min_ntl_threshold and end[i] > 0:
                cagr[i] = ((end[i] / max(start[i], 1e-9)) ** (1.0 / year_span)) - 1.0
            elif start[i] <= min_ntl_threshold and end[i] > min_ntl_threshold:
                cagr[i] = 1.0
            elif end[i] <= min_ntl_threshold and start[i] > min_ntl_threshold:
                cagr[i] = -1.0
            else:
                cagr[i] = 0.0

        df['ntl_start'] = start
        df['ntl_end'] = end
        df['ntl_change'] = end - start
        df['ntl_pct_change'] = np.where(start > min_ntl_threshold, (end - start) / np.maximum(start, 1e-9), 0.0)
        df['ntl_mean'] = mean
        df['ntl_max'] = maxv
        df['ntl_min'] = minv
        df['ntl_std'] = stdv
        df['ntl_volatility'] = np.where(mean > 0, stdv / np.maximum(mean, 1e-9), 0.0)
        df['ntl_slope'] = slopes
        df['ntl_acceleration'] = acceleration
        df['ntl_cagr'] = cagr
        df['persistent_decline'] = self._persistent_decline(vals)

        return df

    def _persistent_decline(self, vals):
        import numpy as np
        out = []
        for row in vals:
            diffs = np.diff(row)
            if len(diffs) == 0:
                out.append(0.0)
            else:
                out.append(float((diffs < 0).sum() / len(diffs)))
        return np.array(out, dtype=float)

    def _predict_future_ntl(self, df, years, prediction_year, ml_model_name, feedback):
        import numpy as np
        import pandas as pd

        ntl_cols = ['ntl_{}'.format(y) for y in years]
        y_last = df[ntl_cols[-1]].fillna(0).values.astype(float)

        feature_cols_base = [
            'centroid_x', 'centroid_y', 'area_m2',
            'poi_count', 'poi_density', 'poi_diversity',
            'building_count', 'building_density', 'building_coverage_ratio',
            'building_height_mean', 'building_height_max', 'occupancy_mix',
            'ntl_start', 'ntl_mean', 'ntl_max', 'ntl_min', 'ntl_std',
            'ntl_slope', 'ntl_cagr', 'ntl_volatility', 'ntl_acceleration',
            'persistent_decline',
            'road_density', 'major_road_density', 'intersection_density',
            'road_accessibility_score', 'downscale_weight'
        ]
        for c in feature_cols_base:
            if c not in df.columns:
                df[c] = 0.0

        validation_rows = []

        # If there are not enough years, use deterministic linear extrapolation.
        if len(years) < 4:
            pred = df['ntl_end'].values + df['ntl_slope'].values * (prediction_year - years[-1])
            df['predicted_ntl'] = np.maximum(pred, 0)
            model_info = {
                'selected_model': 'Linear Trend',
                'reason': 'Less than four years available. Linear trend fallback was used.'
            }
            validation_df = pd.DataFrame([model_info])
            return df, model_info, validation_df

        try:
            from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, HistGradientBoostingRegressor
            from sklearn.linear_model import LinearRegression
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
            from sklearn.model_selection import train_test_split
            from sklearn.preprocessing import StandardScaler
            from sklearn.pipeline import make_pipeline
        except Exception as e:
            feedback.reportError('scikit-learn is not available. Linear trend fallback is used. Error: {}'.format(e))
            pred = df['ntl_end'].values + df['ntl_slope'].values * (prediction_year - years[-1])
            df['predicted_ntl'] = np.maximum(pred, 0)
            model_info = {
                'selected_model': 'Linear Trend',
                'reason': 'scikit-learn unavailable. Linear trend fallback was used.'
            }
            validation_df = pd.DataFrame([model_info])
            return df, model_info, validation_df

        # Backtesting: target each recent year from previous features.
        candidate_models = {}
        candidate_models['Linear Trend'] = make_pipeline(StandardScaler(), LinearRegression())
        candidate_models['Random Forest'] = RandomForestRegressor(
            n_estimators=160, random_state=42, min_samples_leaf=2, n_jobs=-1
        )
        candidate_models['Extra Trees'] = ExtraTreesRegressor(
            n_estimators=180, random_state=42, min_samples_leaf=2, n_jobs=-1
        )
        candidate_models['HistGradientBoosting'] = HistGradientBoostingRegressor(
            random_state=42, max_iter=180, learning_rate=0.06
        )

        if ml_model_name != 'Auto':
            candidate_models = {ml_model_name: candidate_models[ml_model_name]}

        X_all = df[feature_cols_base].fillna(0).replace([np.inf, -np.inf], 0).values.astype(float)
        y_all = y_last.copy()

        selected_model_name = None
        best_rmse = float('inf')
        best_model = None

        for mname, model in candidate_models.items():
            try:
                if len(df) >= 20:
                    X_train, X_test, y_train, y_test = train_test_split(
                        X_all, y_all, test_size=0.25, random_state=42
                    )
                    model.fit(X_train, y_train)
                    pred_test = model.predict(X_test)
                    rmse = float(math.sqrt(mean_squared_error(y_test, pred_test)))
                    mae = float(mean_absolute_error(y_test, pred_test))
                    r2 = float(r2_score(y_test, pred_test)) if len(y_test) > 1 else 0.0
                else:
                    model.fit(X_all, y_all)
                    pred_test = model.predict(X_all)
                    rmse = float(math.sqrt(mean_squared_error(y_all, pred_test)))
                    mae = float(mean_absolute_error(y_all, pred_test))
                    r2 = float(r2_score(y_all, pred_test)) if len(y_all) > 1 else 0.0

                validation_rows.append({
                    'model': mname,
                    'rmse': rmse,
                    'mae': mae,
                    'r2': r2,
                    'n_samples': int(len(df))
                })

                if rmse < best_rmse:
                    best_rmse = rmse
                    selected_model_name = mname
                    best_model = model
            except Exception as e:
                validation_rows.append({
                    'model': mname,
                    'rmse': None,
                    'mae': None,
                    'r2': None,
                    'n_samples': int(len(df)),
                    'error': str(e)
                })

        if best_model is None:
            pred = df['ntl_end'].values + df['ntl_slope'].values * (prediction_year - years[-1])
            df['predicted_ntl'] = np.maximum(pred, 0)
            model_info = {
                'selected_model': 'Linear Trend',
                'reason': 'All ML models failed. Linear trend fallback was used.'
            }
            validation_df = pd.DataFrame(validation_rows if validation_rows else [model_info])
            return df, model_info, validation_df

        best_model.fit(X_all, y_all)

        horizon = float(prediction_year - years[-1])
        deterministic_trend = df['ntl_end'].values + df['ntl_slope'].values * horizon

        # ML predicts last-year structure. Trend extrapolation adds temporal direction.
        ml_base = best_model.predict(X_all)
        pred_future = (0.55 * deterministic_trend) + (0.45 * ml_base)
        pred_future = np.maximum(pred_future, 0)

        df['predicted_ntl'] = pred_future
        df['predicted_ntl_change'] = df['predicted_ntl'] - df['ntl_end']
        df['prediction_horizon'] = horizon

        # Feature importance.
        feature_importance = {}
        try:
            if hasattr(best_model, 'feature_importances_'):
                importances = best_model.feature_importances_
                feature_importance = {
                    feature_cols_base[i]: float(importances[i]) for i in range(len(feature_cols_base))
                }
        except Exception:
            feature_importance = {}

        model_info = {
            'selected_model': selected_model_name,
            'rmse': best_rmse,
            'prediction_year': prediction_year,
            'feature_importance': feature_importance
        }
        validation_df = pd.DataFrame(validation_rows)
        return df, model_info, validation_df

    def _diagnose_urban_dynamics(self, df, core_top_percent, shrinking_sensitivity):
        import numpy as np

        df['ntl_end_norm'] = self._normalize_series(df['ntl_end'])
        df['ntl_mean_norm'] = self._normalize_series(df['ntl_mean'])
        df['ntl_slope_norm'] = self._normalize_series(df['ntl_slope'])
        df['ntl_change_norm'] = self._normalize_series(df['ntl_change'])
        df['predicted_ntl_norm'] = self._normalize_series(df['predicted_ntl'])
        df['predicted_change_norm'] = self._normalize_series(df.get('predicted_ntl_change', df['predicted_ntl'] - df['ntl_end']))
        df['poi_density_norm'] = self._normalize_series(df['poi_density'])
        df['poi_diversity_norm'] = self._normalize_series(df['poi_diversity'])
        df['building_density_norm'] = self._normalize_series(df['building_density'])
        df['building_height_norm'] = self._normalize_series(df['building_height_mean'])
        df['bcr_norm'] = self._normalize_series(df['building_coverage_ratio'])
        df['occupancy_mix_norm'] = self._normalize_series(df['occupancy_mix'])
        df['road_density_norm'] = self._normalize_series(df.get('road_density', 0))
        df['major_road_density_norm'] = self._normalize_series(df.get('major_road_density', 0))
        df['intersection_density_norm'] = self._normalize_series(df.get('intersection_density', 0))
        df['road_accessibility_norm'] = self._normalize_series(df.get('road_accessibility_score', 0))
        df['volatility_norm'] = self._normalize_series(df['ntl_volatility'])

        neg_slope = np.maximum(-df['ntl_slope'].values.astype(float), 0)
        neg_change = np.maximum(-df['ntl_change'].values.astype(float), 0)
        df['neg_slope_norm'] = self._normalize_series(neg_slope)
        df['neg_change_norm'] = self._normalize_series(neg_change)

        low_poi = 1 - df['poi_density_norm']
        underused_building = np.maximum(df['building_density_norm'] - df['ntl_end_norm'], 0)
        persistent_decline = df['persistent_decline'].values.astype(float)

        sensitivity_factor = {
            'Low': 0.85,
            'Medium': 1.00,
            'High': 1.15
        }.get(shrinking_sensitivity, 1.0)

        shrinking = (
            0.32 * df['neg_slope_norm'].values +
            0.22 * df['neg_change_norm'].values +
            0.14 * low_poi.values +
            0.16 * underused_building +
            0.16 * persistent_decline
        ) * sensitivity_factor
        df['shrinking_risk'] = np.clip(shrinking, 0, 1)

        building_intensity = (
            0.45 * df['building_density_norm'] +
            0.30 * df['building_height_norm'] +
            0.25 * df['bcr_norm']
        )

        future_core = (
            0.26 * df['predicted_ntl_norm'] +
            0.17 * df['ntl_slope_norm'] +
            0.13 * df['poi_density_norm'] +
            0.09 * df['poi_diversity_norm'] +
            0.10 * building_intensity +
            0.08 * df['occupancy_mix_norm'] +
            0.12 * df['road_accessibility_norm'] +
            0.05 * (1 - df['volatility_norm'])
        )
        df['future_core_probability'] = np.clip(future_core, 0, 1)
        df['future_core_rank'] = df['future_core_probability'].rank(ascending=False, method='dense').astype(int)

        q_high_core = np.nanpercentile(df['future_core_probability'], max(0, 100 - core_top_percent))
        q_ntl_high = np.nanpercentile(df['ntl_end'], 75)
        q_ntl_low = np.nanpercentile(df['ntl_end'], 25)
        q_slope_high = np.nanpercentile(df['ntl_slope'], 75)
        q_slope_low = np.nanpercentile(df['ntl_slope'], 25)
        q_poi_high = np.nanpercentile(df['poi_density'], 75)
        q_build_high = np.nanpercentile(df['building_density'], 75)
        q_road_high = np.nanpercentile(df.get('road_accessibility_score', 0), 75)
        q_major_high = np.nanpercentile(df.get('major_road_density', 0), 75)

        classes = []
        for _, r in df.iterrows():
            ntl_end = r['ntl_end']
            slope = r['ntl_slope']
            poi = r['poi_density']
            bdens = r['building_density']
            road_acc = r.get('road_accessibility_score', 0)
            major_rd = r.get('major_road_density', 0)
            shr = r['shrinking_risk']
            fcore = r['future_core_probability']
            pred_ch = r.get('predicted_ntl_change', 0)

            if shr >= 0.70 and slope < 0:
                cls = 'Strong Urban Shrinking'
            elif shr >= 0.50 and slope < 0:
                cls = 'Declining Urban Area'
            elif ntl_end >= q_ntl_high and poi >= q_poi_high and bdens >= q_build_high and abs(slope) <= max(1e-9, abs(q_slope_high) * 0.25):
                cls = 'Stable Mature Core'
            elif ntl_end >= q_ntl_high and slope > q_slope_high:
                cls = 'Intensifying Core'
            elif fcore >= q_high_core and slope > 0 and road_acc >= q_road_high:
                cls = 'Road-Supported Emerging Future Core'
            elif fcore >= q_high_core and slope > 0:
                cls = 'Emerging Future Core'
            elif slope > q_slope_high and major_rd >= q_major_high:
                cls = 'Corridor Growth'
            elif ntl_end >= q_ntl_high and poi < q_poi_high * 0.5 and road_acc < q_road_high * 0.5:
                cls = 'Isolated Light Anomaly'
            elif ntl_end <= q_ntl_low and slope > q_slope_high:
                cls = 'Urban Expansion'
            elif bdens >= q_build_high and ntl_end <= q_ntl_low:
                cls = 'Dormant Built-up Area'
            elif poi >= q_poi_high and bdens < q_build_high:
                cls = 'Activity Without Density'
            elif r['building_height_mean'] > 0 and r['building_height_norm'] >= 0.75 and slope >= 0:
                cls = 'Vertical Intensification'
            elif pred_ch > 0 and fcore >= 0.60:
                cls = 'Future Growth Area'
            else:
                cls = 'Stable or Low-Dynamics Area'

            classes.append(cls)

        df['urban_dynamics_class'] = classes

        def risk_class(v):
            if v >= 0.75:
                return 'Very High'
            if v >= 0.50:
                return 'High'
            if v >= 0.25:
                return 'Medium'
            return 'Low'

        def core_class(v):
            if v >= np.nanpercentile(df['future_core_probability'], 90):
                return 'Very High'
            if v >= np.nanpercentile(df['future_core_probability'], 75):
                return 'High'
            if v >= np.nanpercentile(df['future_core_probability'], 50):
                return 'Medium'
            return 'Low'

        df['shrinking_risk_class'] = df['shrinking_risk'].apply(risk_class)
        df['future_core_class'] = df['future_core_probability'].apply(core_class)

        return df

    # -------------------------------------------------------------------------
    # Output writers
    # -------------------------------------------------------------------------

    def _save_layer_to_gpkg(self, layer, gpkg_path, layer_name, context, feedback):
        """Save a memory/vector layer into a GeoPackage layer using QgsVectorFileWriter.

        This avoids the fragile 'file.gpkg|layername=...' syntax in native:savefeatures,
        which can fail in some QGIS/GDAL builds with: OGR driver for '' not found.
        """
        if layer is None or not layer.isValid():
            raise QgsProcessingException('Cannot save invalid layer: {}'.format(layer_name))

        gpkg_path = str(gpkg_path)
        os.makedirs(os.path.dirname(gpkg_path), exist_ok=True)

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = 'GPKG'
        options.layerName = layer_name
        options.fileEncoding = 'UTF-8'

        if os.path.exists(gpkg_path):
            options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
        else:
            options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile

        transform_context = QgsProject.instance().transformContext()
        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer,
            gpkg_path,
            transform_context,
            options
        )

        # QGIS versions return tuples with slightly different lengths.
        error_code = result[0] if isinstance(result, tuple) and len(result) > 0 else result
        error_message = result[1] if isinstance(result, tuple) and len(result) > 1 else ''

        if error_code != QgsVectorFileWriter.NoError:
            raise QgsProcessingException(
                'Could not write layer {} to GeoPackage. Error: {}'.format(layer_name, error_message)
            )

        feedback.pushInfo('Saved GeoPackage layer: {}'.format(layer_name))

    def _write_grid_layer(self, grid_layer, df, gpkg_path, layer_name, context, feedback):
        df_by_fid = {int(r['grid_fid']): r for _, r in df.iterrows()}

        fields = QgsFields()
        fields.append(QgsField('grid_id', QVariant.Int))
        fields.append(QgsField('area_m2', QVariant.Double))
        fields.append(QgsField('ntl_start', QVariant.Double))
        fields.append(QgsField('ntl_end', QVariant.Double))
        fields.append(QgsField('ntl_change', QVariant.Double))
        fields.append(QgsField('ntl_slope', QVariant.Double))
        fields.append(QgsField('ntl_cagr', QVariant.Double))
        fields.append(QgsField('ntl_vol', QVariant.Double))
        fields.append(QgsField('pred_ntl', QVariant.Double))
        fields.append(QgsField('shrink_r', QVariant.Double))
        fields.append(QgsField('shrink_c', QVariant.String, len=50))
        fields.append(QgsField('fcore_p', QVariant.Double))
        fields.append(QgsField('fcore_r', QVariant.Int))
        fields.append(QgsField('fcore_c', QVariant.String, len=50))
        fields.append(QgsField('dyn_class', QVariant.String, len=80))
        fields.append(QgsField('poi_count', QVariant.Int))
        fields.append(QgsField('poi_dens', QVariant.Double))
        fields.append(QgsField('poi_div', QVariant.Double))
        fields.append(QgsField('poi_dom', QVariant.String, len=100))
        fields.append(QgsField('bld_count', QVariant.Int))
        fields.append(QgsField('bld_dens', QVariant.Double))
        fields.append(QgsField('bcr', QVariant.Double))
        fields.append(QgsField('h_mean', QVariant.Double))
        fields.append(QgsField('h_max', QVariant.Double))
        fields.append(QgsField('occ_mix', QVariant.Double))
        fields.append(QgsField('occ_dom', QVariant.String, len=100))
        fields.append(QgsField('road_len', QVariant.Double))
        fields.append(QgsField('road_den', QVariant.Double))
        fields.append(QgsField('majrd_len', QVariant.Double))
        fields.append(QgsField('majrd_den', QVariant.Double))
        fields.append(QgsField('inter_den', QVariant.Double))
        fields.append(QgsField('road_acc', QVariant.Double))
        fields.append(QgsField('ds_weight', QVariant.Double))

        uri = 'Polygon?crs={}'.format(grid_layer.crs().authid())
        out = QgsVectorLayer(uri, layer_name, 'memory')
        dp = out.dataProvider()
        dp.addAttributes(fields)
        out.updateFields()

        feats = []
        for gf in grid_layer.getFeatures():
            fid = int(gf.id())
            if fid not in df_by_fid:
                continue
            r = df_by_fid[fid]
            feat = QgsFeature(fields)
            feat.setGeometry(gf.geometry())
            feat.setAttributes([
                int(r.get('grid_id', 0)),
                float(r.get('area_m2', 0)),
                float(r.get('ntl_start', 0)),
                float(r.get('ntl_end', 0)),
                float(r.get('ntl_change', 0)),
                float(r.get('ntl_slope', 0)),
                float(r.get('ntl_cagr', 0)),
                float(r.get('ntl_volatility', 0)),
                float(r.get('predicted_ntl', 0)),
                float(r.get('shrinking_risk', 0)),
                str(r.get('shrinking_risk_class', '')),
                float(r.get('future_core_probability', 0)),
                int(r.get('future_core_rank', 0)),
                str(r.get('future_core_class', '')),
                str(r.get('urban_dynamics_class', '')),
                int(r.get('poi_count', 0)),
                float(r.get('poi_density', 0)),
                float(r.get('poi_diversity', 0)),
                str(r.get('poi_dom_category', '')),
                int(r.get('building_count', 0)),
                float(r.get('building_density', 0)),
                float(r.get('building_coverage_ratio', 0)),
                float(r.get('building_height_mean', 0)),
                float(r.get('building_height_max', 0)),
                float(r.get('occupancy_mix', 0)),
                str(r.get('occupancy_dom', '')),
                float(r.get('road_length_m', 0)),
                float(r.get('road_density', 0)),
                float(r.get('major_road_length_m', 0)),
                float(r.get('major_road_density', 0)),
                float(r.get('intersection_density', 0)),
                float(r.get('road_accessibility_score', 0)),
                float(r.get('downscale_weight', 0))
            ])
            feats.append(feat)

        dp.addFeatures(feats)
        out.updateExtents()

        self._save_layer_to_gpkg(out, gpkg_path, layer_name, context, feedback)

        return out

    def _write_poi_core_candidates(self, poi_layer, grid_layer, df, name_field, category_field, gpkg_path, tables_dir, context, feedback):
        import pandas as pd

        grid_features = list(grid_layer.getFeatures())
        grid_index = QgsSpatialIndex()
        geom_by_fid = {}
        df_by_fid = {int(r['grid_fid']): r for _, r in df.iterrows()}

        for gf in grid_features:
            grid_index.addFeature(gf)
            geom_by_fid[int(gf.id())] = gf.geometry()

        fields = QgsFields()
        fields.append(QgsField('poi_name', QVariant.String, len=150))
        fields.append(QgsField('poi_cat', QVariant.String, len=120))
        fields.append(QgsField('grid_id', QVariant.Int))
        fields.append(QgsField('fcore_p', QVariant.Double))
        fields.append(QgsField('ntl_grow', QVariant.Double))
        fields.append(QgsField('poi_score', QVariant.Double))
        fields.append(QgsField('bld_score', QVariant.Double))
        fields.append(QgsField('poi_core', QVariant.Double))
        fields.append(QgsField('core_rank', QVariant.Int))
        fields.append(QgsField('core_class', QVariant.String, len=50))

        out = QgsVectorLayer('Point?crs={}'.format(poi_layer.crs().authid()), 'future_core_poi_candidates', 'memory')
        dp = out.dataProvider()
        dp.addAttributes(fields)
        out.updateFields()

        rows = []
        feats = []

        for pf in poi_layer.getFeatures():
            geom = pf.geometry()
            if geom is None or geom.isEmpty():
                continue

            matched = None
            for fid in grid_index.intersects(geom.boundingBox()):
                ggeom = geom_by_fid.get(int(fid))
                if ggeom and ggeom.intersects(geom):
                    matched = int(fid)
                    break
            if matched is None or matched not in df_by_fid:
                continue

            r = df_by_fid[matched]
            cat = str(pf[category_field]) if category_field and category_field in pf.fields().names() else 'Unknown'
            name = str(pf[name_field]) if name_field and name_field in pf.fields().names() else ''

            cat_weight = self._poi_category_weight(cat)
            poi_core_score = (
                0.30 * float(r.get('future_core_probability', 0)) +
                0.18 * cat_weight +
                0.14 * float(r.get('poi_density_norm', 0)) +
                0.14 * float(r.get('ntl_slope_norm', 0)) +
                0.14 * float(r.get('building_density_norm', 0)) +
                0.10 * float(r.get('road_accessibility_norm', 0))
            )
            row = {
                'poi_name': name,
                'poi_category': cat,
                'grid_id': int(r.get('grid_id', 0)),
                'future_core_probability': float(r.get('future_core_probability', 0)),
                'ntl_growth_score': float(r.get('ntl_slope_norm', 0)),
                'poi_density_score': float(r.get('poi_density_norm', 0)),
                'building_intensity_score': float(r.get('building_density_norm', 0)),
                'poi_core_score': float(poi_core_score)
            }
            rows.append(row)

        if not rows:
            csv_path = str(tables_dir / '06_poi_future_core_candidates.csv')
            pd.DataFrame([]).to_csv(csv_path, index=False, encoding='utf-8-sig')
            return out, csv_path

        rows_sorted = sorted(rows, key=lambda x: x['poi_core_score'], reverse=True)
        score_to_rank = {id(row): i + 1 for i, row in enumerate(rows_sorted)}

        score_values = [r['poi_core_score'] for r in rows_sorted]
        q90 = self._percentile(score_values, 90)
        q75 = self._percentile(score_values, 75)
        q50 = self._percentile(score_values, 50)

        # Second pass for features.
        row_idx = 0
        for pf in poi_layer.getFeatures():
            geom = pf.geometry()
            if geom is None or geom.isEmpty():
                continue

            matched = None
            for fid in grid_index.intersects(geom.boundingBox()):
                ggeom = geom_by_fid.get(int(fid))
                if ggeom and ggeom.intersects(geom):
                    matched = int(fid)
                    break
            if matched is None or matched not in df_by_fid:
                continue

            if row_idx >= len(rows):
                break
            row = rows[row_idx]
            row_idx += 1
            s = row['poi_core_score']
            c = 'Very High' if s >= q90 else 'High' if s >= q75 else 'Medium' if s >= q50 else 'Low'
            row['core_rank'] = int(sorted(score_values, reverse=True).index(s) + 1)
            row['core_class'] = c

            feat = QgsFeature(fields)
            feat.setGeometry(geom)
            feat.setAttributes([
                row['poi_name'],
                row['poi_category'],
                int(row['grid_id']),
                float(row['future_core_probability']),
                float(row['ntl_growth_score']),
                float(row['poi_density_score']),
                float(row['building_intensity_score']),
                float(row['poi_core_score']),
                int(row['core_rank']),
                row['core_class']
            ])
            feats.append(feat)

        dp.addFeatures(feats)
        out.updateExtents()

        self._save_layer_to_gpkg(out, gpkg_path, 'future_core_poi_candidates', context, feedback)

        csv_path = str(tables_dir / '06_poi_future_core_candidates.csv')
        pd.DataFrame(rows).sort_values('poi_core_score', ascending=False).to_csv(csv_path, index=False, encoding='utf-8-sig')
        return out, csv_path

    def _write_building_core_candidates(self, building_layer, grid_layer, df, height_field, occupancy_field, gpkg_path, tables_dir, context, feedback, max_building_candidates=5000, core_top_percent=10.0):
        """
        Optimized building future-core candidate writer.

        Earlier versions evaluated all building polygons against all candidate grid cells and
        wrote every building to GeoPackage. That is very slow for large city datasets.
        This version:
        1. limits matching to high future-core grid cells,
        2. uses building centroid-in-grid matching first,
        3. avoids polygon intersection area unless absolutely necessary,
        4. keeps only the top N building candidates in memory and output.
        """
        import pandas as pd
        import heapq

        try:
            max_building_candidates = int(max_building_candidates)
        except Exception:
            max_building_candidates = 5000

        if max_building_candidates < 0:
            max_building_candidates = 5000

        # Select only high-potential grids for building candidate extraction.
        # Minimum top share is 10% to avoid being too restrictive.
        try:
            q = max(0.0, 100.0 - max(float(core_top_percent), 10.0))
            future_core_threshold = self._percentile(df['future_core_probability'].fillna(0).tolist(), q)
        except Exception:
            future_core_threshold = 0.0

        eligible_df = df[df['future_core_probability'].fillna(0) >= future_core_threshold].copy()
        if eligible_df.empty:
            eligible_df = df.copy()

        eligible_fids = set(int(v) for v in eligible_df['grid_fid'].tolist())
        df_by_fid = {int(r['grid_fid']): r for _, r in df.iterrows()}

        grid_index = QgsSpatialIndex()
        geom_by_fid = {}
        for gf in grid_layer.getFeatures():
            fid = int(gf.id())
            if fid not in eligible_fids:
                continue
            grid_index.addFeature(gf)
            geom_by_fid[fid] = gf.geometry()

        fields = QgsFields()
        fields.append(QgsField('bld_id', QVariant.Int))
        fields.append(QgsField('height', QVariant.Double))
        fields.append(QgsField('occupancy', QVariant.String, len=120))
        fields.append(QgsField('area_m2', QVariant.Double))
        fields.append(QgsField('grid_id', QVariant.Int))
        fields.append(QgsField('fcore_p', QVariant.Double))
        fields.append(QgsField('bld_core', QVariant.Double))
        fields.append(QgsField('core_rank', QVariant.Int))
        fields.append(QgsField('core_class', QVariant.String, len=50))

        out = QgsVectorLayer('Polygon?crs={}'.format(building_layer.crs().authid()), 'future_core_building_candidates', 'memory')
        dp = out.dataProvider()
        dp.addAttributes(fields)
        out.updateFields()

        # Bounded min-heap: (score, uid, row, geometry)
        # If max_building_candidates = 0, keep all eligible candidates.
        heap = []
        rows_all = [] if max_building_candidates == 0 else None
        processed = 0
        matched_count = 0
        uid = 0

        total_buildings = building_layer.featureCount()
        if total_buildings < 0:
            total_buildings = 0

        feedback.pushInfo(
            'Optimized building candidate extraction: using {} high-potential grid cells and max {} building candidates.'.format(
                len(eligible_fids),
                'all' if max_building_candidates == 0 else max_building_candidates
            )
        )

        for bf in building_layer.getFeatures():
            if feedback.isCanceled():
                break

            processed += 1
            if processed % 5000 == 0:
                if total_buildings > 0:
                    feedback.setProgress(65 + int(min(20, processed / max(1, total_buildings) * 20)))
                feedback.pushInfo('Processed {:,} buildings, matched {:,} candidate buildings.'.format(processed, matched_count))

            geom = bf.geometry()
            if geom is None or geom.isEmpty():
                continue

            # Fast path: match building centroid to an eligible grid.
            try:
                cgeom = geom.centroid()
                cbbox = cgeom.boundingBox()
            except Exception:
                cgeom = None
                cbbox = geom.boundingBox()

            matched = None
            if cgeom is not None and not cgeom.isEmpty():
                for fid in grid_index.intersects(cbbox):
                    ggeom = geom_by_fid.get(int(fid))
                    if ggeom and ggeom.contains(cgeom):
                        matched = int(fid)
                        break

            # Fallback: bbox/intersects only, no expensive intersection-area computation.
            if matched is None:
                for fid in grid_index.intersects(geom.boundingBox()):
                    ggeom = geom_by_fid.get(int(fid))
                    if ggeom and ggeom.intersects(geom):
                        matched = int(fid)
                        break

            if matched is None or matched not in df_by_fid:
                continue

            r = df_by_fid[matched]
            h = self._safe_float(bf[height_field], 0.0) if height_field and height_field in bf.fields().names() else 0.0
            occ = str(bf[occupancy_field]) if occupancy_field and occupancy_field in bf.fields().names() else 'Unknown'
            area = geom.area()
            occ_weight = self._occupancy_weight(occ)

            score = (
                0.25 * float(r.get('future_core_probability', 0)) +
                0.18 * float(r.get('building_height_norm', 0)) +
                0.14 * float(r.get('bcr_norm', 0)) +
                0.14 * occ_weight +
                0.10 * float(r.get('poi_density_norm', 0)) +
                0.09 * float(r.get('ntl_slope_norm', 0)) +
                0.10 * float(r.get('road_accessibility_norm', 0))
            )

            row = {
                'building_id': int(bf.id()),
                'height': float(h),
                'occupancy': occ,
                'area_m2': float(area),
                'grid_id': int(r.get('grid_id', 0)),
                'future_core_probability': float(r.get('future_core_probability', 0)),
                'building_core_score': float(score)
            }

            # Store only top N geometries to keep writing fast.
            geom_copy = QgsGeometry(geom)
            uid += 1
            matched_count += 1

            if max_building_candidates == 0:
                rows_all.append((score, uid, row, geom_copy))
            else:
                item = (score, uid, row, geom_copy)
                if len(heap) < max_building_candidates:
                    heapq.heappush(heap, item)
                else:
                    if score > heap[0][0]:
                        heapq.heapreplace(heap, item)

        if max_building_candidates == 0:
            selected = rows_all if rows_all is not None else []
        else:
            selected = list(heap)

        if not selected:
            csv_path = str(tables_dir / '07_building_future_core_candidates.csv')
            pd.DataFrame([]).to_csv(csv_path, index=False, encoding='utf-8-sig')
            return out, csv_path

        selected_sorted = sorted(selected, key=lambda x: x[0], reverse=True)
        scores = [item[0] for item in selected_sorted]
        q90 = self._percentile(scores, 90)
        q75 = self._percentile(scores, 75)
        q50 = self._percentile(scores, 50)

        feats = []
        rows = []

        for rank, (score, uid, row, geom) in enumerate(selected_sorted, start=1):
            c = 'Very High' if score >= q90 else 'High' if score >= q75 else 'Medium' if score >= q50 else 'Low'
            row['core_rank'] = int(rank)
            row['core_class'] = c
            rows.append(row)

            feat = QgsFeature(fields)
            feat.setGeometry(geom)
            feat.setAttributes([
                int(row['building_id']),
                float(row['height']),
                row['occupancy'],
                float(row['area_m2']),
                int(row['grid_id']),
                float(row['future_core_probability']),
                float(row['building_core_score']),
                int(rank),
                c
            ])
            feats.append(feat)

        dp.addFeatures(feats)
        out.updateExtents()

        feedback.pushInfo(
            'Writing {:,} selected building candidates from {:,} matched buildings.'.format(
                len(rows),
                matched_count
            )
        )

        self._save_layer_to_gpkg(out, gpkg_path, 'future_core_building_candidates', context, feedback)

        csv_path = str(tables_dir / '07_building_future_core_candidates.csv')
        pd.DataFrame(rows).sort_values('building_core_score', ascending=False).to_csv(csv_path, index=False, encoding='utf-8-sig')
        return out, csv_path


    def _poi_category_weight(self, cat):
        text = str(cat).lower()
        high = [
            'commercial', 'retail', 'market', 'mall', 'shop', 'perdagangan', 'jasa',
            'office', 'kantor', 'transport', 'station', 'terminal',
            'hospital', 'health', 'kesehatan', 'university', 'college', 'pendidikan tinggi',
            'tourism', 'hotel', 'pariwisata'
        ]
        medium = [
            'restaurant', 'food', 'kuliner', 'school', 'education', 'pendidikan',
            'bank', 'atm', 'service', 'public', 'government', 'pemerintahan'
        ]
        if any(k in text for k in high):
            return 1.0
        if any(k in text for k in medium):
            return 0.7
        return 0.45

    def _occupancy_weight(self, occ):
        text = str(occ).lower()
        high = [
            'commercial', 'retail', 'perdagangan', 'jasa', 'office', 'kantor',
            'mixed', 'campuran', 'hotel', 'hospital', 'university', 'mall'
        ]
        medium = [
            'residential', 'permukiman', 'rumah', 'school', 'education',
            'industrial', 'industri', 'warehouse'
        ]
        if any(k in text for k in high):
            return 1.0
        if any(k in text for k in medium):
            return 0.65
        return 0.45

    def _percentile(self, values, q):
        import numpy as np
        if not values:
            return 0.0
        return float(np.nanpercentile(values, q))

    # -------------------------------------------------------------------------
    # Tables, PNG, GIF, report
    # -------------------------------------------------------------------------

    def _class_summary(self, df):
        import pandas as pd
        g = df.groupby('urban_dynamics_class', dropna=False).agg(
            grid_count=('grid_id', 'count'),
            area_m2=('area_m2', 'sum'),
            mean_ntl_end=('ntl_end', 'mean'),
            mean_ntl_slope=('ntl_slope', 'mean'),
            mean_shrinking_risk=('shrinking_risk', 'mean'),
            mean_future_core_probability=('future_core_probability', 'mean')
        ).reset_index()
        total_area = g['area_m2'].sum()
        g['area_share'] = g['area_m2'] / total_area if total_area > 0 else 0
        return g.sort_values('area_m2', ascending=False)

    def _write_xlsx(self, xlsx_path, df, validation_df, class_summary, core_summary, shrinking_summary, feedback):
        try:
            import pandas as pd
            with pd.ExcelWriter(str(xlsx_path), engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='grid_indicators', index=False)
                validation_df.to_excel(writer, sheet_name='model_validation', index=False)
                class_summary.to_excel(writer, sheet_name='diagnosis_summary', index=False)
                core_summary.to_excel(writer, sheet_name='future_core_grid', index=False)
                shrinking_summary.to_excel(writer, sheet_name='shrinking_grid', index=False)
        except Exception as e:
            feedback.reportError('XLSX was not created. pandas or openpyxl may be unavailable, or the workbook may be locked. Error: {}'.format(e))

    def _generate_png_outputs(self, df, years, prediction_year, maps_dir, charts_dir, feedback):
        try:
            import matplotlib.pyplot as plt
            import matplotlib.colors as mcolors
            import matplotlib.patches as mpatches
            import matplotlib.gridspec as gridspec
            import numpy as np
        except Exception as e:
            feedback.reportError('matplotlib is not available. PNG outputs skipped. Error: {}'.format(e))
            return

        # ── Light-theme palette ──────────────────────────────────────────────
        BG        = '#F7F8FA'
        PANEL     = '#FFFFFF'
        GRID_C    = '#E8EBF0'
        TEXT_PRI  = '#1A1D23'
        TEXT_SEC  = '#5C6370'
        ACCENT    = '#2563EB'
        ACCENT2   = '#10B981'
        WARN      = '#F59E0B'
        DANGER    = '#EF4444'
        BORDER    = '#D1D5DB'

        # Colormaps: light-friendly
        CMAP_NTL    = 'YlOrRd'
        CMAP_GROWTH = 'RdYlGn'
        CMAP_CORE   = 'Blues'
        CMAP_RISK   = 'OrRd'
        CMAP_POI    = 'YlGnBu'
        CMAP_BUILD  = 'PuBuGn'
        CMAP_ROAD   = 'GnBu'
        CMAP_DIV    = 'RdYlBu'

        # ── Typography & rcParams ───────────────────────────────────────────
        plt.rcParams.update({
            'figure.facecolor':    BG,
            'axes.facecolor':      PANEL,
            'axes.edgecolor':      BORDER,
            'axes.labelcolor':     TEXT_SEC,
            'axes.titlecolor':     TEXT_PRI,
            'axes.titlesize':      13,
            'axes.titleweight':    'bold',
            'axes.labelsize':      10,
            'axes.grid':           True,
            'axes.spines.top':     False,
            'axes.spines.right':   False,
            'grid.color':          GRID_C,
            'grid.linewidth':      0.6,
            'xtick.color':         TEXT_SEC,
            'ytick.color':         TEXT_SEC,
            'xtick.labelsize':     9,
            'ytick.labelsize':     9,
            'legend.frameon':      True,
            'legend.framealpha':   0.92,
            'legend.edgecolor':    BORDER,
            'legend.fontsize':     9,
            'font.family':         'DejaVu Sans',
            'savefig.facecolor':   BG,
            'savefig.edgecolor':   'none',
        })

        def _stamp(ax, label):
            """Bottom-right watermark stamp."""
            ax.text(
                0.995, 0.005, 'CityLume  |  Firman Afrianto & Maya Safira',
                transform=ax.transAxes,
                ha='right', va='bottom',
                fontsize=6.5, color=TEXT_SEC, alpha=0.65,
                style='italic'
            )

        def _colorbar_modern(fig, sc, ax, label, cmap=None):
            cb = fig.colorbar(sc, ax=ax, fraction=0.035, pad=0.02, shrink=0.85)
            cb.ax.tick_params(labelsize=8, colors=TEXT_SEC)
            cb.set_label(label, fontsize=8.5, color=TEXT_SEC)
            cb.outline.set_edgecolor(BORDER)
            return cb

        def scatter_map(col, title, filename, size_col=None, cmap=CMAP_NTL, unit_label=None):
            fig, ax = plt.subplots(figsize=(11, 8.5))
            fig.patch.set_facecolor(BG)
            ax.set_facecolor(PANEL)
            x = df['centroid_x'].values
            y = df['centroid_y'].values
            v = df[col].fillna(0).values
            s = 18
            if size_col and size_col in df.columns:
                sv = self._normalize_series(df[size_col].fillna(0)) * 48 + 9
                s = sv.values if hasattr(sv, 'values') else sv
            sc = ax.scatter(x, y, c=v, s=s, cmap=cmap, alpha=0.88,
                            linewidths=0, edgecolors='none', zorder=3)
            ax.set_title(title, pad=12, fontsize=13, fontweight='bold', color=TEXT_PRI)
            ax.set_xlabel('Easting (m)', labelpad=6)
            ax.set_ylabel('Northing (m)', labelpad=6)
            ax.set_aspect('equal')
            ax.grid(True, color=GRID_C, linewidth=0.5, zorder=0)
            for sp in ax.spines.values():
                sp.set_edgecolor(BORDER)
            lbl = unit_label if unit_label else col.replace('_', ' ').title()
            _colorbar_modern(fig, sc, ax, lbl)
            _stamp(ax, title)
            plt.tight_layout(pad=1.4)
            plt.savefig(str(maps_dir / filename), dpi=180, bbox_inches='tight')
            plt.close(fig)

        def bar_chart(data, title, filename, xlabel='', ylabel='', color=ACCENT):
            fig, ax = plt.subplots(figsize=(11, 6))
            fig.patch.set_facecolor(BG)
            ax.set_facecolor(PANEL)
            bars = ax.bar(range(len(data)), data.values, color=color, alpha=0.82,
                          width=0.65, edgecolor=PANEL, linewidth=0.6, zorder=3)
            ax.set_xticks(range(len(data)))
            ax.set_xticklabels([str(i) for i in data.index], rotation=45, ha='right', fontsize=8.5)
            ax.set_title(title, pad=10, fontsize=13, fontweight='bold', color=TEXT_PRI)
            ax.set_xlabel(xlabel, labelpad=6)
            ax.set_ylabel(ylabel, labelpad=6)
            ax.grid(True, axis='y', color=GRID_C, linewidth=0.6, zorder=0)
            ax.set_axisbelow(True)
            for sp in ['top', 'right']:
                ax.spines[sp].set_visible(False)
            for sp in ['left', 'bottom']:
                ax.spines[sp].set_edgecolor(BORDER)
            _stamp(ax, title)
            plt.tight_layout(pad=1.4)
            plt.savefig(str(charts_dir / filename), dpi=180, bbox_inches='tight')
            plt.close(fig)

        map_specs = [
            ('ntl_start',              'NTL First Year {}'.format(years[0]),              '01_ntl_first_year.png',          CMAP_NTL,   'NTL Radiance'),
            ('ntl_end',                'NTL Last Year {}'.format(years[-1]),               '02_ntl_last_year.png',           CMAP_NTL,   'NTL Radiance'),
            ('ntl_change',             'NTL Change {} → {}'.format(years[0], years[-1]),  '03_ntl_change_map.png',          CMAP_GROWTH,'NTL Change'),
            ('ntl_slope',              'NTL Trend Slope',                                  '04_ntl_slope_map.png',           CMAP_GROWTH,'Slope'),
            ('ntl_cagr',               'NTL CAGR (%)',                                    '05_ntl_cagr_map.png',            CMAP_GROWTH,'CAGR %'),
            ('ntl_volatility',         'NTL Volatility',                                  '06_ntl_volatility_map.png',      CMAP_DIV,   'Volatility'),
            ('predicted_ntl',          'Predicted NTL — {}'.format(prediction_year),      '07_predicted_ntl_map.png',       CMAP_NTL,   'Predicted NTL'),
            ('shrinking_risk',         'Urban Shrinking Risk',                             '08_shrinking_risk_map.png',      CMAP_RISK,  'Shrinking Risk'),
            ('future_core_probability','Future Core Probability',                          '09_future_core_probability_map.png', CMAP_CORE,'Probability'),
            ('future_core_rank',       'Future Core Rank',                                 '10_future_core_rank_map.png',    'Blues_r',  'Rank'),
            ('poi_density',            'POI Density',                                      '11_poi_density_map.png',         CMAP_POI,   'POI / km²'),
            ('poi_diversity',          'POI Diversity (Shannon)',                           '12_poi_diversity_map.png',       CMAP_POI,   'Shannon H'),
            ('building_density',       'Building Density',                                 '13_building_density_map.png',    CMAP_BUILD, 'BCR'),
            ('building_height_mean',   'Mean Building Height (m)',                         '14_building_height_map.png',     CMAP_BUILD, 'Height (m)'),
            ('occupancy_mix',          'Occupancy Mix Score',                              '15_occupancy_mix_map.png',       CMAP_BUILD, 'Mix Score'),
            ('road_density',           'Road Density',                                     '16_road_density_map.png',        CMAP_ROAD,  'km/km²'),
            ('major_road_density',     'Major Road Density',                               '17_major_road_density_map.png',  CMAP_ROAD,  'km/km²'),
            ('intersection_density',   'Intersection Density Proxy',                       '18_intersection_density_map.png',CMAP_ROAD,  'Intersections/km²'),
            ('road_accessibility_score','Road Accessibility Score',                        '19_road_accessibility_map.png',  CMAP_ROAD,  'Accessibility'),
            ('downscale_weight',       'NTL Downscale Weight',                             '20_downscale_weight_map.png',    CMAP_NTL,   'Weight'),
        ]
        for col, title, filename, cmap, unit_lbl in map_specs:
            if col in df.columns:
                try:
                    scatter_map(col, title, filename, cmap=cmap, unit_label=unit_lbl)
                except Exception as e:
                    feedback.reportError('PNG map skipped [{}]: {}'.format(filename, e))
                    plt.close('all')

        # ── Chart 21: Citywide NTL time series ─────────────────────────────
        try:
            ntl_cols = ['ntl_{}'.format(y) for y in years]
            city_ts = df[ntl_cols].sum(axis=0)
            city_ts.index = years
            fig, ax = plt.subplots(figsize=(11, 5))
            fig.patch.set_facecolor(BG)
            ax.set_facecolor(PANEL)
            ax.fill_between(city_ts.index, city_ts.values, alpha=0.14, color=ACCENT)
            ax.plot(city_ts.index, city_ts.values, marker='o', markersize=6,
                    color=ACCENT, linewidth=2.2, zorder=4)
            ax.set_title('Citywide NTL Time Series', pad=10, fontsize=13, fontweight='bold', color=TEXT_PRI)
            ax.set_xlabel('Year', labelpad=6)
            ax.set_ylabel('Total NTL Radiance', labelpad=6)
            ax.grid(True, color=GRID_C, linewidth=0.6, zorder=0)
            for sp in ['top', 'right']:
                ax.spines[sp].set_visible(False)
            for sp in ['left', 'bottom']:
                ax.spines[sp].set_edgecolor(BORDER)
            _stamp(ax, 'Citywide NTL')
            plt.tight_layout(pad=1.4)
            plt.savefig(str(charts_dir / '21_ntl_timeseries_citywide.png'), dpi=180, bbox_inches='tight')
            plt.close(fig)
        except Exception as e:
            feedback.reportError('Chart 21 skipped: {}'.format(e))
            plt.close('all')

        # ── Chart 22: NTL Distribution by Year (boxplot) ───────────────────
        try:
            fig, ax = plt.subplots(figsize=(11, 6))
            fig.patch.set_facecolor(BG)
            ax.set_facecolor(PANEL)
            data_box = [df['ntl_{}'.format(y)].fillna(0).values for y in years]
            bp = ax.boxplot(data_box, labels=[str(y) for y in years], patch_artist=True,
                            whiskerprops=dict(color=ACCENT, linewidth=1.3),
                            capprops=dict(color=ACCENT, linewidth=1.3),
                            medianprops=dict(color=DANGER, linewidth=2.0),
                            flierprops=dict(marker='o', color=WARN, alpha=0.4, markersize=3.5))
            cmap_box = plt.cm.get_cmap('Blues', len(years) + 2)
            for i, patch in enumerate(bp['boxes']):
                patch.set_facecolor(cmap_box(i + 2))
                patch.set_alpha(0.72)
            ax.set_title('NTL Distribution by Year', pad=10, fontsize=13, fontweight='bold', color=TEXT_PRI)
            ax.set_xlabel('Year', labelpad=6)
            ax.set_ylabel('NTL Radiance', labelpad=6)
            ax.grid(True, axis='y', color=GRID_C, linewidth=0.6, zorder=0)
            ax.set_axisbelow(True)
            for sp in ['top', 'right']:
                ax.spines[sp].set_visible(False)
            for sp in ['left', 'bottom']:
                ax.spines[sp].set_edgecolor(BORDER)
            _stamp(ax, 'NTL Distribution')
            plt.tight_layout(pad=1.4)
            plt.savefig(str(charts_dir / '22_ntl_distribution_by_year.png'), dpi=180, bbox_inches='tight')
            plt.close(fig)
        except Exception as e:
            feedback.reportError('Chart 22 skipped: {}'.format(e))
            plt.close('all')

        # ── Chart 23 & 24: Top growth / decline bar charts ─────────────────
        try:
            top_growth = df.sort_values('ntl_slope', ascending=False).head(20).set_index('grid_id')['ntl_slope']
            bar_chart(top_growth, 'Top 20 Growth Grids — NTL Slope', '23_top_growth_grids.png',
                      'Grid ID', 'NTL Slope', color=ACCENT2)
        except Exception as e:
            feedback.reportError('Chart 23 skipped: {}'.format(e))
            plt.close('all')

        try:
            top_decline = df.sort_values('ntl_slope', ascending=True).head(20).set_index('grid_id')['ntl_slope']
            bar_chart(top_decline, 'Top 20 Declining Grids — NTL Slope', '24_top_declining_grids.png',
                      'Grid ID', 'NTL Slope', color=DANGER)
        except Exception as e:
            feedback.reportError('Chart 24 skipped: {}'.format(e))
            plt.close('all')

        # ── Chart 25: Urban Dynamics Diagnosis Count ────────────────────────
        CLASS_COLORS = {
            'Stable Mature Core':                    '#1D4ED8',
            'Intensifying Core':                     '#2563EB',
            'Road-Supported Emerging Future Core':   '#0EA5E9',
            'Emerging Future Core':                  '#38BDF8',
            'Corridor Growth':                       '#10B981',
            'Urban Expansion':                       '#34D399',
            'Future Growth Area':                    '#A3E635',
            'Vertical Intensification':              '#8B5CF6',
            'Activity Without Density':              '#F59E0B',
            'Isolated Light Anomaly':                '#FCD34D',
            'Dormant Built-up Area':                 '#9CA3AF',
            'Declining Urban Area':                  '#F97316',
            'Strong Urban Shrinking':                '#EF4444',
            'Stable or Low-Dynamics Area':           '#D1D5DB',
        }
        try:
            class_counts = df['urban_dynamics_class'].value_counts()
            colors_bar = [CLASS_COLORS.get(c, ACCENT) for c in class_counts.index]
            fig, ax = plt.subplots(figsize=(12, 6.5))
            fig.patch.set_facecolor(BG)
            ax.set_facecolor(PANEL)
            ax.barh(range(len(class_counts)), class_counts.values,
                    color=colors_bar, alpha=0.87, edgecolor=PANEL, linewidth=0.5, zorder=3)
            ax.set_yticks(range(len(class_counts)))
            ax.set_yticklabels(class_counts.index, fontsize=10)
            ax.set_xlabel('Grid Count', labelpad=6)
            ax.set_title('Urban Dynamics Diagnosis Distribution', pad=10, fontsize=13,
                         fontweight='bold', color=TEXT_PRI)
            ax.grid(True, axis='x', color=GRID_C, linewidth=0.6, zorder=0)
            ax.set_axisbelow(True)
            for sp in ['top', 'right']:
                ax.spines[sp].set_visible(False)
            for sp in ['left', 'bottom']:
                ax.spines[sp].set_edgecolor(BORDER)
            for i, v in enumerate(class_counts.values):
                ax.text(v + max(class_counts.values) * 0.01, i, str(v),
                        va='center', fontsize=9, color=TEXT_PRI)
            _stamp(ax, 'Class Distribution')
            plt.tight_layout(pad=1.4)
            plt.savefig(str(charts_dir / '25_diagnosis_class_count.png'), dpi=180, bbox_inches='tight')
            plt.close(fig)
        except Exception as e:
            feedback.reportError('Chart 25 skipped: {}'.format(e))
            plt.close('all')

        # ── Chart 26: Future Core Probability Distribution ──────────────────
        try:
            fig, ax = plt.subplots(figsize=(10, 5.5))
            fig.patch.set_facecolor(BG)
            ax.set_facecolor(PANEL)
            vals26 = df['future_core_probability'].fillna(0)
            n26, bins26, patches26 = ax.hist(vals26, bins=35, edgecolor=PANEL, linewidth=0.5)
            cmap26 = plt.cm.Blues
            norm26 = mcolors.Normalize(vmin=bins26.min(), vmax=bins26.max())
            for patch, left in zip(patches26, bins26[:-1]):
                patch.set_facecolor(cmap26(norm26(left) * 0.7 + 0.3))
            ax.axvline(vals26.mean(), color=DANGER, linewidth=1.6, linestyle='--',
                       label='Mean {:.2f}'.format(vals26.mean()))
            ax.set_title('Future Core Probability Distribution', pad=10, fontsize=13,
                         fontweight='bold', color=TEXT_PRI)
            ax.set_xlabel('Future Core Probability', labelpad=6)
            ax.set_ylabel('Grid Count', labelpad=6)
            ax.legend()
            ax.grid(True, axis='y', color=GRID_C, linewidth=0.6, zorder=0)
            ax.set_axisbelow(True)
            for sp in ['top', 'right']:
                ax.spines[sp].set_visible(False)
            for sp in ['left', 'bottom']:
                ax.spines[sp].set_edgecolor(BORDER)
            _stamp(ax, 'Future Core Dist')
            plt.tight_layout(pad=1.4)
            plt.savefig(str(charts_dir / '26_future_core_score_distribution.png'), dpi=180, bbox_inches='tight')
            plt.close(fig)
        except Exception as e:
            feedback.reportError('Chart 26 skipped: {}'.format(e))
            plt.close('all')

        # ── Chart 27: Shrinking Risk Distribution ──────────────────────────
        try:
            fig, ax = plt.subplots(figsize=(10, 5.5))
            fig.patch.set_facecolor(BG)
            ax.set_facecolor(PANEL)
            vals27 = df['shrinking_risk'].fillna(0)
            n27, bins27, patches27 = ax.hist(vals27, bins=35, edgecolor=PANEL, linewidth=0.5)
            cmap27 = plt.cm.Oranges
            norm27 = mcolors.Normalize(vmin=bins27.min(), vmax=bins27.max())
            for patch, left in zip(patches27, bins27[:-1]):
                patch.set_facecolor(cmap27(norm27(left) * 0.7 + 0.3))
            ax.axvline(vals27.mean(), color=DANGER, linewidth=1.6, linestyle='--',
                       label='Mean {:.2f}'.format(vals27.mean()))
            ax.set_title('Urban Shrinking Risk Distribution', pad=10, fontsize=13,
                         fontweight='bold', color=TEXT_PRI)
            ax.set_xlabel('Shrinking Risk Score', labelpad=6)
            ax.set_ylabel('Grid Count', labelpad=6)
            ax.legend()
            ax.grid(True, axis='y', color=GRID_C, linewidth=0.6, zorder=0)
            ax.set_axisbelow(True)
            for sp in ['top', 'right']:
                ax.spines[sp].set_visible(False)
            for sp in ['left', 'bottom']:
                ax.spines[sp].set_edgecolor(BORDER)
            _stamp(ax, 'Shrinking Risk Dist')
            plt.tight_layout(pad=1.4)
            plt.savefig(str(charts_dir / '27_shrinking_score_distribution.png'), dpi=180, bbox_inches='tight')
            plt.close(fig)
        except Exception as e:
            feedback.reportError('Chart 27 skipped: {}'.format(e))
            plt.close('all')

        # ── Chart 28: Urban Dynamics Radar ─────────────────────────────────
        try:
            radar_cols = [
                'ntl_end_norm', 'ntl_slope_norm', 'poi_density_norm',
                'poi_diversity_norm', 'building_density_norm',
                'occupancy_mix_norm', 'future_core_probability'
            ]
            if all(c in df.columns for c in radar_cols):
                values = [float(df[c].mean()) for c in radar_cols]
                labels = [
                    'NTL Intensity', 'NTL Growth', 'POI Density',
                    'POI Diversity', 'Building Density', 'Occupancy Mix', 'Future Core'
                ]
                angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
                values_r = values + values[:1]
                angles_r = angles + angles[:1]
                fig = plt.figure(figsize=(8.5, 8.5), facecolor=BG)
                ax = plt.subplot(111, polar=True, facecolor=PANEL)
                ax.plot(angles_r, values_r, color=ACCENT, linewidth=2.2, zorder=4)
                ax.fill(angles_r, values_r, color=ACCENT, alpha=0.16, zorder=3)
                ax.scatter(angles, values, color=ACCENT, s=52, zorder=5)
                ax.set_xticks(angles)
                ax.set_xticklabels(labels, fontsize=9.5, color=TEXT_PRI)
                ax.set_yticklabels([])
                ax.set_ylim(0, 1)
                ax.yaxis.grid(True, color=GRID_C, linewidth=0.8)
                ax.xaxis.grid(True, color=BORDER, linewidth=0.6)
                ax.spines['polar'].set_edgecolor(BORDER)
                ax.set_title('Urban Dynamics Profile — Radar', pad=18, fontsize=13,
                             fontweight='bold', color=TEXT_PRI)
                fig.text(0.5, 0.02, 'CityLume  |  Firman Afrianto & Maya Safira',
                         ha='center', fontsize=7, color=TEXT_SEC, alpha=0.65, style='italic')
                plt.tight_layout(pad=1.4)
                plt.savefig(str(charts_dir / '28_radar_urban_dynamics.png'), dpi=180, bbox_inches='tight')
                plt.close(fig)
        except Exception as e:
            feedback.reportError('Chart 28 skipped: {}'.format(e))
            plt.close('all')

        # ── Standalone map: Urban Dynamics Classification — Spatial Distribution ──
        try:
            self._generate_urban_dynamics_spatial_distribution_png(
                df, maps_dir, CLASS_COLORS, BG, PANEL, GRID_C,
                TEXT_PRI, TEXT_SEC, ACCENT, BORDER, feedback
            )
        except Exception as e:
            feedback.reportError('Standalone urban dynamics map skipped: {}'.format(e))
            plt.close('all')

        # ── Standalone map: NTL initial-final-predicted triptych ───────────
        try:
            self._generate_ntl_triptych_change_aware_png(
                df, years, prediction_year, maps_dir, BG, PANEL, GRID_C,
                TEXT_PRI, TEXT_SEC, ACCENT, BORDER, feedback
            )
        except Exception as e:
            feedback.reportError('NTL triptych comparison map skipped: {}'.format(e))
            plt.close('all')

        # ── Spatial Planning Intelligence visual outputs ─────────────────────────────────
        try:
            self._generate_spatial_planning_intelligence_png_outputs(
                df, maps_dir, charts_dir, BG, PANEL, GRID_C,
                TEXT_PRI, TEXT_SEC, ACCENT, BORDER, feedback
            )
        except Exception as e:
            feedback.reportError('Spatial Planning Intelligence PNG outputs skipped: {}'.format(e))
            plt.close('all')

        # ── Chart 29: Urban Dynamics Category Summary ───────────────────────
        try:
            self._generate_urban_dynamics_category_png(
                df, maps_dir, charts_dir, CLASS_COLORS, BG, PANEL, GRID_C,
                TEXT_PRI, TEXT_SEC, ACCENT, BORDER, feedback
            )
        except Exception as e:
            feedback.reportError('Chart 29 skipped: {}'.format(e))
            plt.close('all')

    def _generate_urban_dynamics_spatial_distribution_png(
        self, df, maps_dir, CLASS_COLORS,
        BG, PANEL, GRID_C, TEXT_PRI, TEXT_SEC, ACCENT, BORDER, feedback
    ):
        """
        Standalone map PNG for the spatial distribution of urban dynamics classes.
        The composition is optimized for report-ready export with a larger map panel,
        compact legend panel, reduced whitespace, and softer background cells.
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib.lines as mlines
            import matplotlib.gridspec as gridspec
            import numpy as np
        except Exception:
            return

        FALLBACK = '#94A3B8'
        BASE_GRID = '#E5E7EB'
        LOW_DYN = 'Stable or Low-Dynamics Area'
        DORMANT = 'Dormant Built-up Area'

        preferred_order = [
            'Stable or Low-Dynamics Area',
            'Stable Mature Core',
            'Intensifying Core',
            'Road-Supported Emerging Future Core',
            'Emerging Future Core',
            'Corridor Growth',
            'Urban Expansion',
            'Future Growth Area',
            'Vertical Intensification',
            'Activity Without Density',
            'Isolated Light Anomaly',
            'Dormant Built-up Area',
            'Declining Urban Area',
            'Strong Urban Shrinking',
        ]

        class_counts = df['urban_dynamics_class'].fillna('Unknown').value_counts()
        present_classes = [c for c in preferred_order if c in class_counts.index]
        for c in class_counts.index:
            if c not in present_classes:
                present_classes.append(c)

        fig = plt.figure(figsize=(15.8, 8.8), facecolor=BG)
        gs = gridspec.GridSpec(1, 2, figure=fig, width_ratios=[4.9, 1.55],
                               left=0.045, right=0.985, top=0.90, bottom=0.08, wspace=0.06)

        ax_map = fig.add_subplot(gs[0, 0])
        ax_map.set_facecolor(PANEL)
        ax_leg = fig.add_subplot(gs[0, 1])
        ax_leg.set_facecolor(PANEL)
        ax_leg.axis('off')

        x = df['centroid_x'].values
        y = df['centroid_y'].values

        # Base grid in soft grey so all cells remain visible.
        ax_map.scatter(x, y, s=17, c=BASE_GRID, alpha=1.0, linewidths=0, zorder=1)

        # Overlay active classes. Low-dynamics and dormant classes are shown but kept subdued.
        handles = []
        legend_labels = []
        for cl in present_classes:
            sub = df[df['urban_dynamics_class'].fillna('Unknown') == cl]
            if sub.empty:
                continue
            color = CLASS_COLORS.get(cl, FALLBACK)
            size = 19
            alpha = 0.92
            zorder = 3
            if cl == LOW_DYN:
                color = '#C8CDD6'
                size = 16
                alpha = 0.95
                zorder = 2
            elif cl == DORMANT:
                color = '#9AA4B2'
                size = 17
                alpha = 0.95
                zorder = 2.5

            ax_map.scatter(sub['centroid_x'].values, sub['centroid_y'].values,
                           s=size, c=color, alpha=alpha, linewidths=0, zorder=zorder)
            handles.append(mlines.Line2D([], [], color=color, marker='o', linestyle='None', markersize=6))
            legend_labels.append('{} (n={})'.format(cl, int(class_counts.get(cl, 0))))

        # Fit map tightly to data with small padding.
        if len(x) > 0 and len(y) > 0:
            x_min, x_max = float(np.nanmin(x)), float(np.nanmax(x))
            y_min, y_max = float(np.nanmin(y)), float(np.nanmax(y))
            x_pad = max((x_max - x_min) * 0.02, 1.0)
            y_pad = max((y_max - y_min) * 0.02, 1.0)
            ax_map.set_xlim(x_min - x_pad, x_max + x_pad)
            ax_map.set_ylim(y_min - y_pad, y_max + y_pad)

        ax_map.set_aspect('equal')
        ax_map.set_title('Urban Dynamics Classification — Spatial Distribution',
                         fontsize=14, fontweight='bold', color=TEXT_PRI, pad=10)
        ax_map.set_xlabel('Easting (m)', fontsize=9.8, color=TEXT_SEC)
        ax_map.set_ylabel('Northing (m)', fontsize=9.8, color=TEXT_SEC)
        ax_map.grid(True, color=GRID_C, linewidth=0.55, zorder=0)
        ax_map.tick_params(colors=TEXT_SEC, labelsize=8.7)
        for sp in ax_map.spines.values():
            sp.set_edgecolor(BORDER)

        # Legend/info panel
        total_cells = int(len(df))
        active_cells = int((df['urban_dynamics_class'].fillna('Unknown') != LOW_DYN).sum())
        subtitle = (
            'Report-ready standalone map\n'
            'Total grid cells: {}\n'
            'Non-background classified cells: {}\n'
            'Classes present: {}'
        ).format(total_cells, active_cells, len(present_classes))
        ax_leg.text(0.05, 0.97, 'Urban Dynamics Class', va='top', ha='left',
                    fontsize=11, fontweight='bold', color=TEXT_PRI)
        ax_leg.text(0.05, 0.91, subtitle, va='top', ha='left',
                    fontsize=8.7, color=TEXT_SEC, linespacing=1.35)
        legend = ax_leg.legend(handles, legend_labels, loc='upper left', bbox_to_anchor=(0.02, 0.80),
                               frameon=False, fontsize=8.6, ncol=1, handletextpad=0.55,
                               borderaxespad=0.0, labelspacing=0.58, markerscale=1.0)

        # Small footer note
        fig.text(0.985, 0.018,
                 'CityLume  |  Firman Afrianto & Maya Safira  |  Standalone map export',
                 ha='right', va='bottom', fontsize=7.2, color=TEXT_SEC, alpha=0.68, style='italic')

        out_path = maps_dir / '21_urban_dynamics_classification_spatial_distribution.png'
        plt.savefig(str(out_path), dpi=220, bbox_inches='tight', facecolor=BG)
        plt.close(fig)
        feedback.pushInfo('Standalone urban dynamics spatial distribution map saved: {}'.format(str(out_path)))


    def _generate_spatial_planning_intelligence_png_outputs(
        self, df, maps_dir, charts_dir,
        BG, PANEL, GRID_C, TEXT_PRI, TEXT_SEC, ACCENT, BORDER, feedback
    ):
        try:
            import matplotlib.pyplot as plt
            import matplotlib.lines as mlines
            import matplotlib as mpl
            import numpy as np
        except Exception:
            return

        if 'planning_mismatch_type' not in df.columns:
            return

        def _categorical_map(col, title, filename, preferred_order=None):
            vals = df[col].fillna('Unknown').astype(str)
            counts = vals.value_counts()
            if preferred_order:
                cats = [c for c in preferred_order if c in counts.index]
                cats += [c for c in counts.index if c not in cats]
            else:
                cats = list(counts.index)

            palette = [
                '#EF4444', '#F97316', '#F59E0B', '#EAB308', '#84CC16',
                '#10B981', '#14B8A6', '#0EA5E9', '#2563EB', '#6366F1',
                '#8B5CF6', '#A855F7', '#64748B', '#94A3B8'
            ]
            color_map = {c: palette[i % len(palette)] for i, c in enumerate(cats)}
            if 'Plan-Activity Relatively Aligned or Neutral' in color_map:
                color_map['Plan-Activity Relatively Aligned or Neutral'] = '#CBD5E1'
            if 'Low' in color_map:
                color_map['Low'] = '#CBD5E1'
            if 'Critical' in color_map:
                color_map['Critical'] = '#B91C1C'
            if 'High' in color_map:
                color_map['High'] = '#EF4444'

            fig = plt.figure(figsize=(15.8, 8.8), facecolor=BG)
            gs = mpl.gridspec.GridSpec(1, 2, figure=fig, width_ratios=[4.9, 1.55],
                                       left=0.045, right=0.985, top=0.90, bottom=0.08, wspace=0.06)
            ax = fig.add_subplot(gs[0, 0])
            ax_leg = fig.add_subplot(gs[0, 1])
            ax.set_facecolor(PANEL)
            ax_leg.set_facecolor(PANEL)
            ax_leg.axis('off')

            x = df['centroid_x'].values
            y = df['centroid_y'].values
            ax.scatter(x, y, s=17, c='#E5E7EB', alpha=1.0, linewidths=0, zorder=1)
            handles, labels = [], []
            for cat in cats:
                sub = df[vals == cat]
                if sub.empty:
                    continue
                color = color_map.get(cat, '#94A3B8')
                ax.scatter(sub['centroid_x'].values, sub['centroid_y'].values,
                           s=20, c=color, alpha=0.90, linewidths=0, zorder=3)
                handles.append(mlines.Line2D([], [], color=color, marker='o', linestyle='None', markersize=6))
                labels.append('{} (n={})'.format(cat, int(counts.get(cat, 0))))

            if len(x) > 0 and len(y) > 0:
                x_min, x_max = float(np.nanmin(x)), float(np.nanmax(x))
                y_min, y_max = float(np.nanmin(y)), float(np.nanmax(y))
                ax.set_xlim(x_min - (x_max-x_min)*0.02, x_max + (x_max-x_min)*0.02)
                ax.set_ylim(y_min - (y_max-y_min)*0.02, y_max + (y_max-y_min)*0.02)
            ax.set_aspect('equal')
            ax.set_title(title, fontsize=14, fontweight='bold', color=TEXT_PRI, pad=10)
            ax.set_xlabel('Easting (m)', fontsize=9.5, color=TEXT_SEC)
            ax.set_ylabel('Northing (m)', fontsize=9.5, color=TEXT_SEC)
            ax.grid(True, color=GRID_C, linewidth=0.5)
            ax.tick_params(colors=TEXT_SEC, labelsize=8.3)
            for sp in ax.spines.values():
                sp.set_edgecolor(BORDER)

            ax_leg.text(0.05, 0.97, title, va='top', ha='left',
                        fontsize=10.5, fontweight='bold', color=TEXT_PRI)
            ax_leg.legend(handles, labels, loc='upper left', bbox_to_anchor=(0.02, 0.88),
                          frameon=False, fontsize=8.2, labelspacing=0.55,
                          handletextpad=0.55, borderaxespad=0.0)
            fig.text(0.985, 0.018, 'CityLume Planner  |  Firman Afrianto & Maya Safira',
                     ha='right', va='bottom', fontsize=7.0, color=TEXT_SEC, alpha=0.68, style='italic')
            plt.savefig(str(maps_dir / filename), dpi=220, bbox_inches='tight', facecolor=BG)
            plt.close(fig)

        mismatch_order = [
            'High Activity in Protected or Low-Urbanization Zone',
            'Unplanned Emerging Core',
            'Predicted Growth Outside Clear Plan Direction',
            'Residential Zone Under Activity Intensification',
            'Planned Core Under Shrinking Pressure',
            'Planned Core, Weak Activity',
            'Planned Center with Weak Activity',
            'Shrinking Risk Area',
            'Industrial Light Anomaly, Not Urban Service Core',
            'Planned Core, Active Core',
            'Plan-Activity Relatively Aligned or Neutral'
        ]
        hierarchy_order = [
            'Primary Urban Center',
            'Secondary Urban Center',
            'Emerging Local Center',
            'Planned Center with Weak Empirical Signal',
            'Declining or Shrinking Center',
            'Non-Center or Low-Order Area'
        ]
        priority_order = ['Critical', 'High', 'Medium-High', 'Medium', 'Low']

        if 'planning_mismatch_type' in df.columns:
            _categorical_map('planning_mismatch_type',
                             'Planning Mismatch — Plan versus Activity Signal',
                             '23_planning_mismatch_map.png',
                             mismatch_order)
        if 'urban_center_hierarchy' in df.columns:
            _categorical_map('urban_center_hierarchy',
                             'Urban Center Hierarchy — Empirical and Predicted Centers',
                             '24_urban_center_hierarchy_map.png',
                             hierarchy_order)
        if 'spatial_planning_priority' in df.columns:
            _categorical_map('spatial_planning_priority',
                             'Spatial Planning Action Priority Matrix',
                             '25_spatial_planning_action_priority_map.png',
                             priority_order)

        # Compact action summary bar chart.
        try:
            summary = df['spatial_planning_action'].fillna('Unknown').value_counts().head(12)
            fig, ax = plt.subplots(figsize=(12.5, 6.8), facecolor=BG)
            ax.set_facecolor(PANEL)
            ax.barh(range(len(summary)), summary.values, color=ACCENT, alpha=0.86, zorder=3)
            ax.set_yticks(range(len(summary)))
            ax.set_yticklabels(summary.index, fontsize=8.7, color=TEXT_PRI)
            ax.invert_yaxis()
            ax.set_xlabel('Grid Count', fontsize=9, color=TEXT_SEC)
            ax.set_title('Spatial Planning Action Matrix — Dominant Recommended Actions',
                         fontsize=13, fontweight='bold', color=TEXT_PRI, pad=10)
            ax.grid(True, axis='x', color=GRID_C, linewidth=0.6, zorder=0)
            for i, v in enumerate(summary.values):
                ax.text(v + max(summary.values) * 0.01, i, str(v),
                        va='center', fontsize=8.3, color=TEXT_PRI)
            for sp in ['top', 'right']:
                ax.spines[sp].set_visible(False)
            for sp in ['left', 'bottom']:
                ax.spines[sp].set_edgecolor(BORDER)
            plt.tight_layout(pad=1.4)
            plt.savefig(str(charts_dir / '30_spatial_planning_action_matrix_summary.png'),
                        dpi=220, bbox_inches='tight', facecolor=BG)
            plt.close(fig)
        except Exception as e:
            feedback.reportError('Spatial Planning action summary chart skipped: {}'.format(e))

        feedback.pushInfo('Spatial Planning Intelligence PNG outputs saved.')

    def _generate_ntl_triptych_change_aware_png(
        self, df, years, prediction_year, maps_dir,
        BG, PANEL, GRID_C, TEXT_PRI, TEXT_SEC, ACCENT, BORDER, feedback
    ):
        """
        Compact standalone three-panel NTL comparison map.

        Revision goals:
        - keep all spatial planning inputs optional;
        - reduce vertical whitespace between the main title and the maps;
        - move panel titles/subtitles above the map frame so they do not overlap the data;
        - move the change-overlay legend above the maps and use green for strong increase;
        - keep the NTL colorbar below the maps, separated from other elements;
        - expand the summary cards so they compare both total NTL and mean NTL.
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib.lines as mlines
            import matplotlib.gridspec as gridspec
            import matplotlib as mpl
            import numpy as np
        except Exception:
            return

        required = ['centroid_x', 'centroid_y', 'ntl_start', 'ntl_end', 'predicted_ntl']
        for col in required:
            if col not in df.columns:
                feedback.reportError('NTL triptych map skipped because required field is missing: {}'.format(col))
                return

        x = np.asarray(df['centroid_x'].values, dtype=float)
        y = np.asarray(df['centroid_y'].values, dtype=float)
        ntl_start = np.asarray(df['ntl_start'].fillna(0).values, dtype=float)
        ntl_end = np.asarray(df['ntl_end'].fillna(0).values, dtype=float)
        ntl_pred = np.asarray(df['predicted_ntl'].fillna(0).values, dtype=float)
        chg_obs = ntl_end - ntl_start
        chg_pred = ntl_pred - ntl_end
        n_cells = max(1, len(ntl_start))

        all_ntl = np.concatenate([ntl_start, ntl_end, ntl_pred])
        finite = np.isfinite(all_ntl)
        if finite.any():
            vmin = float(np.nanpercentile(all_ntl[finite], 2))
            vmax = float(np.nanpercentile(all_ntl[finite], 98))
            if abs(vmax - vmin) < 1e-12:
                vmin = float(np.nanmin(all_ntl[finite]))
                vmax = float(np.nanmax(all_ntl[finite]) + 1.0)
        else:
            vmin, vmax = 0.0, 1.0

        def _limited_change_masks(change_values, percentile=90, max_points_each=240):
            arr = np.asarray(change_values, dtype=float)
            valid = np.isfinite(arr)
            pos_idx = np.where(valid & (arr > 0))[0]
            neg_idx = np.where(valid & (arr < 0))[0]
            pos_mask = np.zeros(len(arr), dtype=bool)
            neg_mask = np.zeros(len(arr), dtype=bool)
            if pos_idx.size > 0:
                pos_thr = float(np.nanpercentile(arr[pos_idx], percentile))
                sel = pos_idx[arr[pos_idx] >= pos_thr]
                if sel.size > max_points_each:
                    sel = sel[np.argsort(arr[sel])[-max_points_each:]]
                pos_mask[sel] = True
            if neg_idx.size > 0:
                neg_thr = float(np.nanpercentile(np.abs(arr[neg_idx]), percentile))
                sel = neg_idx[np.abs(arr[neg_idx]) >= neg_thr]
                if sel.size > max_points_each:
                    sel = sel[np.argsort(np.abs(arr[sel]))[-max_points_each:]]
                neg_mask[sel] = True
            return pos_mask, neg_mask

        obs_pos, obs_neg = _limited_change_masks(chg_obs, percentile=90, max_points_each=240)
        pred_pos, pred_neg = _limited_change_masks(chg_pred, percentile=90, max_points_each=240)

        cmap = plt.get_cmap('YlOrRd')
        norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)
        increase_c = '#10B981'
        decline_c = '#2563EB'

        fig = plt.figure(figsize=(16.2, 9.2), facecolor=BG)
        gs = gridspec.GridSpec(
            4, 3, figure=fig,
            height_ratios=[0.68, 9.75, 0.62, 1.70],
            hspace=0.07, wspace=0.055,
            left=0.035, right=0.985, top=0.955, bottom=0.062
        )

        ax_title = fig.add_subplot(gs[0, :])
        ax_title.axis('off')
        ax_title.set_facecolor(BG)
        axes = [fig.add_subplot(gs[1, i]) for i in range(3)]
        cax = fig.add_subplot(gs[2, :])
        cax.set_facecolor(BG)
        ax_kpi = fig.add_subplot(gs[3, :])
        ax_kpi.set_facecolor(BG)
        ax_kpi.axis('off')

        ax_title.text(
            0.5, 0.73,
            'Observed and Predicted Nighttime Light Dynamics',
            ha='center', va='center', fontsize=15.2, fontweight='bold', color=TEXT_PRI
        )
        ax_title.text(
            0.5, 0.26,
            'Shared NTL scale. Green hollow rings mark strongest increase cells; blue hollow rings mark strongest decline cells.',
            ha='center', va='center', fontsize=8.7, color=TEXT_SEC
        )

        up_handle = mlines.Line2D([], [], color=increase_c, marker='o', linestyle='None',
                                  markerfacecolor='none', markersize=6.2, markeredgewidth=1.0)
        down_handle = mlines.Line2D([], [], color=decline_c, marker='o', linestyle='None',
                                    markerfacecolor='none', markersize=6.2, markeredgewidth=1.0)
        leg = ax_title.legend(
            [up_handle, down_handle],
            ['Strong increase', 'Strong decline'],
            loc='center right', bbox_to_anchor=(0.99, 0.48),
            frameon=True, framealpha=0.92, edgecolor=BORDER,
            fontsize=7.7, title='Change overlay', title_fontsize=8.1,
            borderpad=0.55, labelspacing=0.35, handletextpad=0.45
        )
        leg.get_title().set_fontweight('bold')
        leg.get_title().set_color(TEXT_PRI)

        panels = [
            ('Initial NTL ({})'.format(years[0]), ntl_start, None, None,
             'Baseline observed intensity'),
            ('Final NTL ({})'.format(years[-1]), ntl_end, obs_pos, obs_neg,
             'Observed change: {} → {}'.format(years[0], years[-1])),
            ('Predicted NTL ({})'.format(prediction_year), ntl_pred, pred_pos, pred_neg,
             'Projected change: {} → {}'.format(years[-1], prediction_year)),
        ]

        if len(x) > 0 and len(y) > 0:
            x_min, x_max = float(np.nanmin(x)), float(np.nanmax(x))
            y_min, y_max = float(np.nanmin(y)), float(np.nanmax(y))
            x_pad = max((x_max - x_min) * 0.018, 1.0)
            y_pad = max((y_max - y_min) * 0.018, 1.0)
        else:
            x_min = y_min = 0.0
            x_max = y_max = 1.0
            x_pad = y_pad = 0.1

        for idx, (ax, (title, vals, pos_mask, neg_mask, subtitle)) in enumerate(zip(axes, panels)):
            ax.set_facecolor(PANEL)
            ax.scatter(x, y, c=vals, cmap=cmap, norm=norm, s=16, alpha=0.96, linewidths=0, zorder=2)
            if pos_mask is not None and np.any(pos_mask):
                ax.scatter(x[pos_mask], y[pos_mask], s=43, facecolors='none', edgecolors=increase_c,
                           linewidths=0.85, alpha=0.88, zorder=4)
            if neg_mask is not None and np.any(neg_mask):
                ax.scatter(x[neg_mask], y[neg_mask], s=43, facecolors='none', edgecolors=decline_c,
                           linewidths=0.85, alpha=0.90, zorder=4)
            ax.set_xlim(x_min - x_pad, x_max + x_pad)
            ax.set_ylim(y_min - y_pad, y_max + y_pad)
            ax.set_aspect('equal')
            ax.grid(True, color=GRID_C, linewidth=0.48, zorder=0)
            ax.tick_params(colors=TEXT_SEC, labelsize=7.8, pad=1.5)
            for sp in ax.spines.values():
                sp.set_edgecolor(BORDER)

            # Titles are placed above the map frame to avoid overlap.
            ax.text(0.5, 1.040, title, transform=ax.transAxes,
                    ha='center', va='bottom', fontsize=11.6,
                    fontweight='bold', color=TEXT_PRI, clip_on=False)
            ax.text(0.5, 1.010, subtitle, transform=ax.transAxes,
                    ha='center', va='bottom', fontsize=7.5,
                    color=TEXT_SEC, clip_on=False)

            if idx == 0:
                ax.set_ylabel('Northing (m)', fontsize=8.7, color=TEXT_SEC)
            else:
                ax.set_yticklabels([])
            ax.set_xlabel('Easting (m)', fontsize=8.7, color=TEXT_SEC)

        sm = mpl.cm.ScalarMappable(norm=norm, cmap=cmap)
        sm.set_array([])
        cax.set_axis_off()
        cbar_ax = cax.inset_axes([0.10, 0.28, 0.80, 0.46])
        cbar = fig.colorbar(sm, cax=cbar_ax, orientation='horizontal')
        cbar.set_label('NTL Radiance, shared scale', fontsize=7.9, color=TEXT_SEC, labelpad=2)
        cbar.ax.tick_params(labelsize=7.0, colors=TEXT_SEC, pad=1)
        cbar.outline.set_edgecolor(BORDER)
        for sp in cbar_ax.spines.values():
            sp.set_edgecolor(BORDER)

        total_start = float(np.nansum(ntl_start))
        total_end = float(np.nansum(ntl_end))
        total_pred = float(np.nansum(ntl_pred))
        mean_start = float(np.nanmean(ntl_start)) if len(ntl_start) else 0.0
        mean_end = float(np.nanmean(ntl_end)) if len(ntl_end) else 0.0
        mean_pred = float(np.nanmean(ntl_pred)) if len(ntl_pred) else 0.0
        pct_obs_total = ((total_end - total_start) / total_start * 100.0) if abs(total_start) > 1e-12 else 0.0
        pct_pred_total = ((total_pred - total_end) / total_end * 100.0) if abs(total_end) > 1e-12 else 0.0
        pct_obs_mean = ((mean_end - mean_start) / mean_start * 100.0) if abs(mean_start) > 1e-12 else 0.0
        pct_pred_mean = ((mean_pred - mean_end) / mean_end * 100.0) if abs(mean_end) > 1e-12 else 0.0
        obs_up_n = int(np.sum(obs_pos))
        obs_dn_n = int(np.sum(obs_neg))
        pred_up_n = int(np.sum(pred_pos))
        pred_dn_n = int(np.sum(pred_neg))

        kpis = [
            ('Initial {}'.format(years[0]), 'Total: {:,.1f}'.format(total_start), 'Mean: {:,.2f}'.format(mean_start), '#6B7280'),
            ('Final {}'.format(years[-1]), 'Total: {:,.1f}'.format(total_end), 'Mean: {:,.2f}'.format(mean_end), '#F59E0B'),
            ('Observed change', 'Total Δ: {:+.1f}% | ↑ {}  ↓ {}'.format(pct_obs_total, obs_up_n, obs_dn_n), 'Mean Δ: {:+.1f}%'.format(pct_obs_mean), '#111827'),
            ('Predicted {}'.format(prediction_year), 'Total: {:,.1f}'.format(total_pred), 'Mean: {:,.2f}'.format(mean_pred), '#DC2626'),
            ('Projected change', 'Total Δ: {:+.1f}% | ↑ {}  ↓ {}'.format(pct_pred_total, pred_up_n, pred_dn_n), 'Mean Δ: {:+.1f}%'.format(pct_pred_mean), '#111827'),
        ]
        x_pos = [0.018, 0.213, 0.408, 0.617, 0.809]
        widths = [0.170, 0.170, 0.190, 0.170, 0.175]
        for (label, line1, line2, accent), x0, w in zip(kpis, x_pos, widths):
            rect = mpl.patches.FancyBboxPatch(
                (x0, 0.15), w, 0.70,
                boxstyle='round,pad=0.010,rounding_size=0.018',
                transform=ax_kpi.transAxes, linewidth=0.75,
                edgecolor=BORDER, facecolor=PANEL
            )
            ax_kpi.add_patch(rect)
            ax_kpi.text(x0 + 0.014, 0.70, label, transform=ax_kpi.transAxes,
                        ha='left', va='center', fontsize=8.0, color=TEXT_SEC, fontweight='bold')
            ax_kpi.text(x0 + 0.014, 0.47, line1, transform=ax_kpi.transAxes,
                        ha='left', va='center', fontsize=9.0, color=accent, fontweight='bold')
            ax_kpi.text(x0 + 0.014, 0.27, line2, transform=ax_kpi.transAxes,
                        ha='left', va='center', fontsize=8.3, color=TEXT_PRI)

        fig.text(
            0.985, 0.015,
            'CityLume  |  Firman Afrianto & Maya Safira  |  NTL triptych comparison',
            ha='right', va='bottom', fontsize=6.9, color=TEXT_SEC, alpha=0.66, style='italic'
        )

        out_path = maps_dir / '22_ntl_initial_final_predicted_comparison.png'
        plt.savefig(str(out_path), dpi=220, bbox_inches='tight', facecolor=BG)
        plt.close(fig)
        feedback.pushInfo('Revised NTL triptych comparison PNG saved: {}'.format(str(out_path)))

    def _generate_urban_dynamics_category_png(
        self, df, maps_dir, charts_dir, CLASS_COLORS,
        BG, PANEL, GRID_C, TEXT_PRI, TEXT_SEC, ACCENT, BORDER, feedback
    ):
        """
        Standalone PNG: Urban Dynamics Category Summary Dashboard.

        Revised layout:
          Top row    [large spatial map] [separate legend panel]
          Bottom row [pie panel] [future core panel] [shrinking risk panel]

        The three lower charts are placed in independent panel boxes so they no longer
        overlap one another. Long class labels in the bar charts are wrapped and kept
        inside their own panel area.
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib.gridspec as gridspec
            import matplotlib.lines as mlines
            import numpy as np
            import textwrap
        except Exception:
            return

        FALLBACK = '#94A3B8'

        class_counts = df['urban_dynamics_class'].value_counts()
        all_classes = list(class_counts.index)

        def _wrap_label(lbl, width=20):
            s = str(lbl)
            return '\\n'.join(textwrap.wrap(s, width=width, break_long_words=False, break_on_hyphens=False)) or s

        wrapped_labels = [_wrap_label(c, 20) for c in all_classes]

        fig = plt.figure(figsize=(19.5, 13.4), facecolor=BG)
        outer = gridspec.GridSpec(
            2, 1,
            figure=fig,
            height_ratios=[1.55, 1.0],
            hspace=0.34,
            left=0.045, right=0.98, top=0.92, bottom=0.075
        )

        top = outer[0].subgridspec(1, 2, width_ratios=[4.8, 1.35], wspace=0.14)
        bottom = outer[1].subgridspec(1, 3, width_ratios=[1.05, 1.35, 1.35], wspace=0.28)

        # ── Top left: Spatial map ───────────────────────────────────────
        ax_map = fig.add_subplot(top[0, 0])
        ax_map.set_facecolor(PANEL)

        # base grid softly visible
        ax_map.scatter(df['centroid_x'].values, df['centroid_y'].values,
                       s=19, c='#D8DDE6', alpha=0.95, linewidths=0, zorder=1)
        for cl in all_classes:
            sub = df.loc[df['urban_dynamics_class'] == cl]
            ax_map.scatter(
                sub['centroid_x'].values,
                sub['centroid_y'].values,
                c=CLASS_COLORS.get(cl, FALLBACK),
                s=23, alpha=0.90, linewidths=0,
                label=cl, zorder=3
            )
        ax_map.set_aspect('equal')
        ax_map.set_title('Urban Dynamics Classification — Spatial Distribution',
                         fontsize=13.5, fontweight='bold', color=TEXT_PRI, pad=8)
        ax_map.set_xlabel('Easting (m)', fontsize=9.5, color=TEXT_SEC)
        ax_map.set_ylabel('Northing (m)', fontsize=9.5, color=TEXT_SEC)
        ax_map.grid(True, color=GRID_C, linewidth=0.5, zorder=0)
        ax_map.tick_params(colors=TEXT_SEC, labelsize=8.4)
        for sp in ax_map.spines.values():
            sp.set_edgecolor(BORDER)

        # ── Top right: independent legend panel ─────────────────────────
        ax_leg = fig.add_subplot(top[0, 1])
        ax_leg.set_facecolor(PANEL)
        ax_leg.set_xticks([])
        ax_leg.set_yticks([])
        for sp in ax_leg.spines.values():
            sp.set_edgecolor(BORDER)
        ax_leg.text(0.5, 0.965, 'Urban Dynamics Class', ha='center', va='top',
                    fontsize=10, fontweight='bold', color=TEXT_PRI, transform=ax_leg.transAxes)
        handles = [mlines.Line2D([], [], color=CLASS_COLORS.get(c, FALLBACK), marker='o',
                                 linestyle='None', markersize=6) for c in all_classes]
        legend_labels = ['{} (n={})'.format(c, int(class_counts.get(c, 0))) for c in all_classes]
        leg = ax_leg.legend(handles, legend_labels, loc='upper left', bbox_to_anchor=(0.06, 0.90),
                            frameon=False, fontsize=8.5, labelspacing=0.52,
                            handletextpad=0.55, borderaxespad=0.0)
        
        # ── Bottom helper: create a clean panel with an inset chart area ─
        def _panel_with_inner(spec, title):
            panel = fig.add_subplot(spec)
            panel.set_facecolor(PANEL)
            panel.set_xticks([])
            panel.set_yticks([])
            for sp in panel.spines.values():
                sp.set_edgecolor(BORDER)
            panel.set_title(title, fontsize=11.3, fontweight='bold', color=TEXT_PRI, pad=8)
            return panel

        # ── Bottom left: Pie panel ───────────────────────────────────────
        panel_pie = _panel_with_inner(bottom[0, 0], 'Area Share by Class')
        ax_pie = panel_pie.inset_axes([0.06, 0.07, 0.88, 0.86])
        ax_pie.set_facecolor(PANEL)
        area_by_class = df.groupby('urban_dynamics_class')['area_m2'].sum().reindex(all_classes, fill_value=0)
        pie_colors = [CLASS_COLORS.get(c, FALLBACK) for c in area_by_class.index]
        wedges, texts, autotexts = ax_pie.pie(
            area_by_class.values,
            labels=None,
            colors=pie_colors,
            autopct=lambda p: '{:.1f}%'.format(p) if p >= 2.0 else '',
            pctdistance=0.80,
            startangle=90,
            wedgeprops=dict(edgecolor=BG, linewidth=1.6)
        )
        for at in autotexts:
            at.set_fontsize(8.0)
            at.set_color(TEXT_PRI)
        ax_pie.set_aspect('equal')

        # ── Bottom middle: Mean future core by class ─────────────────────
        panel_core = _panel_with_inner(bottom[0, 1], 'Future Core by Class')
        ax_core = panel_core.inset_axes([0.32, 0.11, 0.63, 0.80])
        ax_core.set_facecolor(PANEL)
        mean_core = df.groupby('urban_dynamics_class')['future_core_probability'].mean().reindex(all_classes, fill_value=0)
        bar_colors_c = [CLASS_COLORS.get(c, FALLBACK) for c in mean_core.index]
        ypos = np.arange(len(mean_core))
        ax_core.barh(ypos, mean_core.values, color=bar_colors_c, alpha=0.88,
                     edgecolor=PANEL, linewidth=0.4, zorder=3)
        ax_core.set_yticks(ypos)
        ax_core.set_yticklabels(wrapped_labels, fontsize=8.0, color=TEXT_PRI)
        ax_core.set_xlabel('Mean Future Core Probability', fontsize=8.8, color=TEXT_SEC)
        ax_core.grid(True, axis='x', color=GRID_C, linewidth=0.6, zorder=0)
        ax_core.set_axisbelow(True)
        ax_core.set_xlim(0, 1.05)
        for sp in ['top', 'right']:
            ax_core.spines[sp].set_visible(False)
        for sp in ['left', 'bottom']:
            ax_core.spines[sp].set_edgecolor(BORDER)
        for i, v in enumerate(mean_core.values):
            ax_core.text(v + 0.012, i, '{:.2f}'.format(v), va='center', ha='left',
                         fontsize=7.9, color=TEXT_PRI)

        # ── Bottom right: Mean shrinking risk by class ───────────────────
        panel_risk = _panel_with_inner(bottom[0, 2], 'Shrinking Risk by Class')
        ax_risk = panel_risk.inset_axes([0.32, 0.11, 0.63, 0.80])
        ax_risk.set_facecolor(PANEL)
        mean_risk = df.groupby('urban_dynamics_class')['shrinking_risk'].mean().reindex(all_classes, fill_value=0)
        bar_colors_r = [CLASS_COLORS.get(c, FALLBACK) for c in mean_risk.index]
        ypos_r = np.arange(len(mean_risk))
        ax_risk.barh(ypos_r, mean_risk.values, color=bar_colors_r, alpha=0.88,
                     edgecolor=PANEL, linewidth=0.4, zorder=3)
        ax_risk.set_yticks(ypos_r)
        ax_risk.set_yticklabels(wrapped_labels, fontsize=8.0, color=TEXT_PRI)
        ax_risk.set_xlabel('Mean Shrinking Risk Score', fontsize=8.8, color=TEXT_SEC)
        ax_risk.grid(True, axis='x', color=GRID_C, linewidth=0.6, zorder=0)
        ax_risk.set_axisbelow(True)
        ax_risk.set_xlim(0, 1.05)
        for sp in ['top', 'right']:
            ax_risk.spines[sp].set_visible(False)
        for sp in ['left', 'bottom']:
            ax_risk.spines[sp].set_edgecolor(BORDER)
        for i, v in enumerate(mean_risk.values):
            ax_risk.text(v + 0.012, i, '{:.2f}'.format(v), va='center', ha='left',
                         fontsize=7.9, color=TEXT_PRI)

        fig.suptitle(
            'CityLume — Urban Dynamics Category Summary',
            fontsize=16.2, fontweight='bold', color=TEXT_PRI, y=0.97
        )
        fig.text(
            0.5, 0.018,
            'CityLume  |  Firman Afrianto & Maya Safira  |  NTL-based Urban Dynamics Intelligence',
            ha='center', fontsize=7.5, color=TEXT_SEC, alpha=0.65, style='italic'
        )

        plt.savefig(
            str(charts_dir / '29_urban_dynamics_category_summary.png'),
            dpi=210, bbox_inches='tight', facecolor=BG
        )
        plt.close(fig)
        feedback.pushInfo('Urban dynamics category summary PNG saved with separated lower chart panels.')

    def _generate_gif_outputs(self, df, years, gif_dir, feedback, gif_duration=1.5):
        try:
            import matplotlib.pyplot as plt
            import matplotlib.colors as mcolors
            import numpy as np
            import imageio.v2 as imageio
        except Exception as e:
            feedback.reportError('imageio or matplotlib is unavailable. GIF outputs skipped. Error: {}'.format(e))
            return

        # ── Light-theme palette (mirrors _generate_png_outputs) ──────────
        BG       = '#F7F8FA'
        PANEL    = '#FFFFFF'
        GRID_C   = '#E8EBF0'
        TEXT_PRI = '#1A1D23'
        TEXT_SEC = '#5C6370'
        BORDER   = '#D1D5DB'
        CMAP_NTL = 'YlOrRd'

        plt.rcParams.update({
            'figure.facecolor': BG,
            'axes.facecolor':   PANEL,
            'axes.edgecolor':   BORDER,
            'axes.labelcolor':  TEXT_SEC,
            'axes.titlecolor':  TEXT_PRI,
            'axes.titlesize':   13,
            'axes.titleweight': 'bold',
            'axes.labelsize':   10,
            'grid.color':       GRID_C,
            'grid.linewidth':   0.5,
            'xtick.color':      TEXT_SEC,
            'ytick.color':      TEXT_SEC,
            'xtick.labelsize':  8.5,
            'ytick.labelsize':  8.5,
            'savefig.facecolor': BG,
            'savefig.edgecolor': 'none',
            'font.family':      'DejaVu Sans',
        })

        # gif_duration is in SECONDS per frame.
        # imageio.mimsave with a list of durations (in ms) is the portable way to
        # produce slow animated GIFs that are respected by all viewers.
        frame_ms = max(200, int(float(gif_duration) * 1000))  # ms per frame

        tmp_dir = gif_dir / '_frames'
        tmp_dir.mkdir(parents=True, exist_ok=True)

        # ── Compute shared NTL colour range across all years ─────────────
        ntl_min = min(float(df['ntl_{}'.format(y)].fillna(0).min()) for y in years)
        ntl_max = max(float(df['ntl_{}'.format(y)].fillna(0).max()) for y in years)
        if ntl_max <= ntl_min:
            ntl_max = ntl_min + 1.0
        norm_ntl = mcolors.Normalize(vmin=ntl_min, vmax=ntl_max)

        # ── NTL time-series animation ─────────────────────────────────────
        frame_paths = []
        for y in years:
            col = 'ntl_{}'.format(y)
            fig, ax = plt.subplots(figsize=(11, 8.5))
            fig.patch.set_facecolor(BG)
            ax.set_facecolor(PANEL)

            sc = ax.scatter(
                df['centroid_x'].values, df['centroid_y'].values,
                c=df[col].fillna(0).values, s=18,
                cmap=CMAP_NTL, norm=norm_ntl,
                alpha=0.88, linewidths=0, zorder=3
            )
            ax.set_title('Nighttime Light — {}'.format(y), pad=10, fontsize=13,
                         fontweight='bold', color=TEXT_PRI)
            ax.set_xlabel('Easting (m)', labelpad=6)
            ax.set_ylabel('Northing (m)', labelpad=6)
            ax.set_aspect('equal')
            ax.grid(True, color=GRID_C, linewidth=0.5, zorder=0)
            for sp in ax.spines.values():
                sp.set_edgecolor(BORDER)

            cb = fig.colorbar(sc, ax=ax, fraction=0.035, pad=0.02, shrink=0.85)
            cb.ax.tick_params(labelsize=8, colors=TEXT_SEC)
            cb.set_label('NTL Radiance', fontsize=8.5, color=TEXT_SEC)
            cb.outline.set_edgecolor(BORDER)

            # Year badge
            ax.text(
                0.02, 0.97, str(y),
                transform=ax.transAxes, ha='left', va='top',
                fontsize=22, fontweight='bold', color=TEXT_PRI, alpha=0.75
            )
            # Watermark
            ax.text(
                0.995, 0.005, 'CityLume  |  Firman Afrianto & Maya Safira',
                transform=ax.transAxes, ha='right', va='bottom',
                fontsize=6.5, color=TEXT_SEC, alpha=0.65, style='italic'
            )

            plt.tight_layout(pad=1.4)
            frame = tmp_dir / 'ntl_{}.png'.format(y)
            plt.savefig(str(frame), dpi=130, bbox_inches='tight', facecolor=BG)
            plt.close(fig)
            frame_paths.append(frame)

        if frame_paths:
            images = [imageio.imread(str(p)) for p in frame_paths]
            # Repeat last frame to create a natural pause before loop
            images += [images[-1]] * 2
            durations = [frame_ms] * (len(images) - 2) + [frame_ms * 3, frame_ms * 3]
            imageio.mimsave(
                str(gif_dir / 'ntl_timeseries_animation.gif'),
                images,
                duration=durations,
                loop=0
            )

        # ── Future core emergence animation ───────────────────────────────
        frame_paths = []
        thresholds = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]
        fcp = df['future_core_probability'].fillna(0).reset_index(drop=True)
        df_reset = df.reset_index(drop=True)
        norm_fcp = mcolors.Normalize(vmin=float(fcp.min()), vmax=float(fcp.max()) or 1.0)

        for th in thresholds:
            fig, ax = plt.subplots(figsize=(11, 8.5))
            fig.patch.set_facecolor(BG)
            ax.set_facecolor(PANEL)

            # Background: all grids with low opacity
            ax.scatter(
                df_reset['centroid_x'].values, df_reset['centroid_y'].values,
                c=fcp.values, cmap='Blues', norm=norm_fcp,
                s=10, alpha=0.25, linewidths=0, zorder=2
            )
            # Highlighted: grids at or above threshold
            mask = fcp >= th
            subset = df_reset[mask]
            fcp_sub = fcp[mask]
            if len(subset) > 0:
                sc_hi = ax.scatter(
                    subset['centroid_x'].values, subset['centroid_y'].values,
                    c=fcp_sub.values, cmap='Blues', norm=norm_fcp,
                    s=48, alpha=0.92, linewidths=0.3,
                    edgecolors='#1D4ED8', zorder=4
                )

            ax.set_title(
                'Future Core Emergence  ·  Threshold ≥ {:.0f}%'.format(th * 100),
                pad=10, fontsize=13, fontweight='bold', color=TEXT_PRI
            )
            ax.set_xlabel('Easting (m)', labelpad=6)
            ax.set_ylabel('Northing (m)', labelpad=6)
            ax.set_aspect('equal')
            ax.grid(True, color=GRID_C, linewidth=0.5, zorder=0)
            for sp in ax.spines.values():
                sp.set_edgecolor(BORDER)

            # Count badge
            pct_active = len(subset) / max(len(df), 1) * 100.0
            ax.text(
                0.02, 0.97,
                '{} grids  ({:.1f}%)'.format(len(subset), pct_active),
                transform=ax.transAxes, ha='left', va='top',
                fontsize=10.5, fontweight='bold', color='#1D4ED8', alpha=0.85
            )
            ax.text(
                0.995, 0.005, 'CityLume  |  Firman Afrianto & Maya Safira',
                transform=ax.transAxes, ha='right', va='bottom',
                fontsize=6.5, color=TEXT_SEC, alpha=0.65, style='italic'
            )

            plt.tight_layout(pad=1.4)
            frame = tmp_dir / 'future_core_{:.2f}.png'.format(th)
            plt.savefig(str(frame), dpi=130, bbox_inches='tight', facecolor=BG)
            plt.close(fig)
            frame_paths.append(frame)

        if frame_paths:
            images = [imageio.imread(str(p)) for p in frame_paths]
            images += [images[-1]] * 2
            durations = [frame_ms] * (len(images) - 2) + [frame_ms * 3, frame_ms * 3]
            imageio.mimsave(
                str(gif_dir / 'future_core_emergence.gif'),
                images,
                duration=durations,
                loop=0
            )

        try:
            shutil.rmtree(str(tmp_dir), ignore_errors=True)
        except Exception:
            pass

    def _write_report(self, report_path, df, years, prediction_year, model_info, validation_df, class_summary):
        total_area = df['area_m2'].sum()
        high_core = df[df['future_core_class'].isin(['Very High', 'High'])]
        high_shrink = df[df['shrinking_risk_class'].isin(['Very High', 'High'])]

        dominant_class = class_summary.iloc[0]['urban_dynamics_class'] if len(class_summary) else 'Unknown'
        mean_slope = float(df['ntl_slope'].mean())
        mean_change = float(df['ntl_change'].mean())
        mean_core = float(df['future_core_probability'].mean())
        mean_shrink = float(df['shrinking_risk'].mean())

        lines = []
        lines.append('CityLume Diagnostic Report')
        lines.append('Created By: Firman Afrianto, Maya Safira')
        lines.append('')
        lines.append('Analysis period: {} to {}'.format(years[0], years[-1]))
        lines.append('Prediction year: {}'.format(prediction_year))
        lines.append('Selected model: {}'.format(model_info.get('selected_model', 'Unknown')))
        lines.append('')
        lines.append('1. General Dynamics')
        lines.append('The dominant urban dynamics class is: {}.'.format(dominant_class))
        lines.append('Mean NTL change is {:.4f}, and mean NTL slope is {:.6f}.'.format(mean_change, mean_slope))
        if mean_slope > 0:
            lines.append('Overall, the study area shows a positive NTL trajectory, indicating increasing nighttime activity or urban-economic intensification.')
        elif mean_slope < 0:
            lines.append('Overall, the study area shows a negative NTL trajectory, indicating possible activity decline or spatial weakening.')
        else:
            lines.append('Overall, the study area shows a relatively stable NTL trajectory.')
        lines.append('')
        lines.append('2. Urban Shrinking Risk')
        lines.append('Mean shrinking risk score is {:.3f}.'.format(mean_shrink))
        lines.append('High and very high shrinking-risk grids: {} out of {} grids.'.format(len(high_shrink), len(df)))
        if len(high_shrink) > 0:
            lines.append('These areas should be reviewed as potential declining cores, underused built-up areas, or locations where activity has weakened despite existing urban fabric.')
        else:
            lines.append('No major concentration of high shrinking risk is detected based on the current NTL, POI, and building indicators.')
        lines.append('')
        lines.append('3. Future Core')
        lines.append('Mean future core probability is {:.3f}.'.format(mean_core))
        lines.append('High and very high future-core grids: {} out of {} grids.'.format(len(high_core), len(df)))
        if len(high_core) > 0:
            lines.append('These grids represent candidate future centers supported by predicted NTL, NTL growth, POI concentration, building intensity, occupancy mix, and road accessibility when road data is provided.')
        lines.append('')
        lines.append('4. Planning Interpretation')
        lines.append('The result can support urban structure evaluation, center hierarchy review, zoning-based service center delineation, investment prioritization, and monitoring of urban expansion or decline.')
        lines.append('')
        lines.append('5. Important Limitation')
        lines.append('NTL is a proxy for nighttime activity and should be interpreted together with local knowledge, land use policy, field survey, economic data, and infrastructure plans.')
        lines.append('')
        lines.append('Class Summary')
        for _, r in class_summary.iterrows():
            lines.append('- {}: {} grids, {:.2f}% of analyzed area'.format(
                r['urban_dynamics_class'],
                int(r['grid_count']),
                float(r['area_share']) * 100.0
            ))

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))