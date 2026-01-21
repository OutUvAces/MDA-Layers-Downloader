from pathlib import Path
from typing import Final

OUTPUT_SUBFOLDER: Final = "MDA_Layers_Output"
CONFIG_SUBFOLDER: Final = "_config"
DOWNLOADS_DIR: Final = Path.home() / "Downloads"

DEFAULT_COLORS = {
    "territorial": "#ffff00",
    "contiguous": "#00ff00",
    "mpa": "#ff0000",
    "eez": "#0000ff",
    "ecs": "#8B4513",
    "cables": "#ffffff",
    "seastate": "#000000",
    "navwarnings": "#ff0000",
}

DEFAULT_OPACITIES = {
    "territorial": "20",
    "contiguous": "20",
    "mpa": "20",
    "eez": "20",
    "ecs": "20",
    "cables": "50",
    "seastate": "100",
    "navwarnings": "80",
}

DENSITY_OPTIONS = ["low", "med", "high"]
DENSITY_MAPPING = {
    "low": 3.0,
    "med": 1.5,
    "high": 0.5
}
OPACITY_OPTIONS = [str(i) for i in range(0, 101, 10)]

MARINEREGIONS_WFS_BASE = "https://geo.vliz.be/geoserver/MarineRegions/wfs"
MARINEREGIONS_SOURCE_URL = "https://www.marineregions.org/"
PROTECTED_PLANET_SOURCE_URL = "https://www.protectedplanet.net/en/thematic-areas/marine-protected-areas"
OSCAR_SOURCE_URL = "https://podaac.jpl.nasa.gov/dataset/OSCAR_L4_OC_NRT_V2.0"

WDPA_BASE_URL = "https://d1gam3xoknrgr2.cloudfront.net/current/WDPA_WDOECM_{month}{year}_Public_marine_shp.zip"
SUBMARINE_CABLES_URL = "https://www.submarinecablemap.com/api/v3/cable/cable-geo.json"
OSCAR_CMR_URL = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
OSCAR_COLLECTION_ID = "C2102958977-POCLOUD"
COUNTRIES_JSON_URL = "https://geo.vliz.be/geoserver/MarineRegions/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=MarineRegions:eez_12nm&outputFormat=application/json&propertyName=territory1,iso_ter1"
NGA_MSI_NAVWARNINGS_URL = "https://msi.nga.mil/api/publications/broadcast-warn"
NGA_MSI_SOURCE_URL = "https://msi.nga.mil/NavWarnings"