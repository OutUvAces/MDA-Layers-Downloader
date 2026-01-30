"""
Configuration constants for the MDA Layers Downloader application.

This module contains all configuration settings, URLs, default colors, and other
constants used throughout the application.
"""

from pathlib import Path
from typing import Final

# Output and configuration directories
OUTPUT_SUBFOLDER: Final = "MDA_Layers_Output"
"""Subfolder name for output files."""

CONFIG_SUBFOLDER: Final = "_config"
"""Subfolder name for configuration files."""

DOWNLOADS_DIR: Final = Path.home() / "Downloads"
"""Default downloads directory path."""

# Default colors for different layer types (hex color codes)
DEFAULT_COLORS = {
    "territorial": "#ffff00",  # Yellow
    "contiguous": "#00ff00",  # Green
    "mpa": "#ff0000",         # Red
    "eez": "#0000ff",         # Blue
    "ecs": "#8B4513",         # Brown
    "cables": "#ffffff",      # White
    "seastate": "#000000",    # Black
    "navwarnings": "#ff0000", # Red
}
"""Default KML color codes for different layer types."""

# Default opacity values for different layer types (0-100)
DEFAULT_OPACITIES = {
    "territorial": "20",   # 20% opacity
    "contiguous": "20",    # 20% opacity
    "mpa": "20",           # 20% opacity
    "eez": "20",           # 20% opacity
    "ecs": "20",           # 20% opacity
    "cables": "50",        # 50% opacity
    "seastate": "100",     # 100% opacity
    "navwarnings": "80",   # 80% opacity
}
"""Default opacity values for different layer types."""

# Density options for data processing
DENSITY_OPTIONS = ["low", "med", "high"]
"""Available density options for data simplification."""

DENSITY_MAPPING = {
    "low": 3.0,   # Low density (coarser simplification)
    "med": 1.5,   # Medium density
    "high": 0.5   # High density (finer detail)
}
"""Mapping of density options to simplification tolerance values."""

OPACITY_OPTIONS = [str(i) for i in range(0, 101, 10)]
"""Available opacity options (0-100 in steps of 10)."""

# Data source URLs
MARINEREGIONS_WFS_BASE = "https://geo.vliz.be/geoserver/MarineRegions/wfs"
"""Base URL for MarineRegions Web Feature Service."""

MARINEREGIONS_SOURCE_URL = "https://www.marineregions.org/"
"""Source website for MarineRegions data."""

PROTECTED_PLANET_SOURCE_URL = "https://www.protectedplanet.net/en/thematic-areas/marine-protected-areas"
"""Source website for Protected Planet MPA data."""

OSCAR_SOURCE_URL = "https://podaac.jpl.nasa.gov/dataset/OSCAR_L4_OC_NRT_V2.0"
"""Source website for OSCAR ocean currents data."""

WDPA_BASE_URL = "https://d1gam3xoknrgr2.cloudfront.net/current/WDPA_WDOECM_{month}{year}_Public_marine_shp.zip"
"""Base URL template for WDPA (World Database on Protected Areas) shapefile downloads."""

SUBMARINE_CABLES_URL = "https://www.submarinecablemap.com/api/v3/cable/cable-geo.json"
"""API URL for submarine cable data."""

OSCAR_CMR_URL = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
"""NASA CMR (Common Metadata Repository) search URL for OSCAR data."""

OSCAR_COLLECTION_ID = "C2102958977-POCLOUD"
"""NASA CMR collection ID for OSCAR L4 ocean currents data."""

COUNTRIES_JSON_URL = "https://geo.vliz.be/geoserver/MarineRegions/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=MarineRegions:eez_12nm&outputFormat=application/json&propertyName=territory1,iso_ter1"
"""URL for country/territory data from MarineRegions."""

NGA_MSI_NAVWARNINGS_URL = "https://msi.nga.mil/api/publications/broadcast-warn"
"""API URL for NGA MSI navigation warnings."""

NGA_MSI_SOURCE_URL = "https://msi.nga.mil/NavWarnings"
"""Source website for NGA MSI navigation warnings."""