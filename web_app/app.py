"""
MDA Layers Downloader - Web Application
=====================================

Web interface for the MDA Layers Downloader marine geospatial data tool.
Converts the desktop GUI application to a web-based service.

Features:
- Web form interface for layer selection
- Background processing for data downloads
- File download links for generated KML files
- Progress tracking and status updates
"""

import os
import sys
import asyncio
import tempfile
import shutil
import hashlib
import time
import warnings
import gc
from pathlib import Path

# Suppress pyogrio RuntimeWarnings (harmless type conversion warnings)
warnings.filterwarnings("ignore", category=RuntimeWarning, module="pyogrio.raw")
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from werkzeug.utils import secure_filename
import threading
import queue
import json
import requests
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import pandas as pd

# Import config constants
COUNTRIES_JSON_URL = "https://geo.vliz.be/geoserver/MarineRegions/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=MarineRegions:eez_12nm&outputFormat=application/json&propertyName=territory1,iso_ter1"

# Add parent directory to path to import existing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import LayerSettings
from workers.download_worker import worker

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'mda-layers-downloader-web-secret-key')

# Configuration
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Global variables for progress tracking
progress_data = {}
current_tasks = {}

# Cache configuration
CACHE_DIR = Path(__file__).parent.parent / "cache"
RAW_SOURCE_DIR = CACHE_DIR / "raw_source_data"
STATIC_CACHE_DIR = RAW_SOURCE_DIR / "static"
DYNAMIC_CACHE_DIR = RAW_SOURCE_DIR / "dynamic"
PREGENERATED_DIR = CACHE_DIR / "pregenerated_kml"
CACHE_METADATA_FILE = CACHE_DIR / "cache_metadata.json"
CACHE_INITIALIZED_FILE = CACHE_DIR / "cache_initialized.txt"

# Ensure cache directories exist
RAW_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
STATIC_CACHE_DIR.mkdir(parents=True, exist_ok=True)
DYNAMIC_CACHE_DIR.mkdir(parents=True, exist_ok=True)
PREGENERATED_DIR.mkdir(parents=True, exist_ok=True)
PREGENERATED_DIR.mkdir(parents=True, exist_ok=True)

def load_countries():
    """Load country list from MarineRegions API.

    Returns:
        List of tuples containing (country_name, iso_code) for all countries.
    """
    try:
        response = requests.get(COUNTRIES_JSON_URL, timeout=20)
        response.raise_for_status()
        data = response.json()
        country_list = []
        for feature in data.get('features', []):
            props = feature.get('properties', {})
            territory = props.get('territory1')
            iso = props.get('iso_ter1')
            if territory and iso:
                country_list.append((territory, iso))
        # Sort by country name
        country_list.sort(key=lambda x: x[0])
        return country_list
    except Exception as e:
        print(f"Error loading countries: {e}")
        # Fallback to basic list if API fails
        return [
            ("Japan", "JPN"),
            ("United States", "USA"),
            ("China", "CHN"),
            ("South Korea", "KOR"),
            ("Russia", "RUS"),
            ("Philippines", "PHL"),
            ("Vietnam", "VNM"),
            ("Malaysia", "MYS"),
            ("Indonesia", "IDN"),
            ("Australia", "AUS"),
            ("New Zealand", "NZL"),
            ("United Kingdom", "GBR"),
            ("France", "FRA"),
            ("Germany", "DEU"),
            ("Norway", "NOR"),
            ("Canada", "CAN"),
            ("Mexico", "MEX"),
            ("Brazil", "BRA"),
            ("Argentina", "ARG"),
            ("Chile", "CHL"),
            ("Peru", "PER"),
            ("Ecuador", "ECU"),
            ("Colombia", "COL"),
            ("Panama", "PAN"),
            ("Cuba", "CUB"),
            ("Jamaica", "JAM"),
            ("Bahamas", "BHS"),
            ("Haiti", "HTI"),
            ("Dominican Republic", "DOM"),
            ("Puerto Rico", "PRI"),
            ("Trinidad and Tobago", "TTO"),
            ("Barbados", "BRB"),
            ("Grenada", "GRD"),
            ("Saint Lucia", "LCA"),
            ("Saint Vincent and the Grenadines", "VCT"),
            ("Antigua and Barbuda", "ATG"),
            ("Saint Kitts and Nevis", "KNA"),
            ("Dominica", "DMA"),
            ("Montserrat", "MSR"),
            ("Anguilla", "AIA"),
            ("British Virgin Islands", "VGB"),
            ("United States Virgin Islands", "VIR"),
            ("Turks and Caicos Islands", "TCA"),
            ("Cayman Islands", "CYM"),
            ("Bermuda", "BMU"),
            ("Greenland", "GRL"),
            ("Iceland", "ISL"),
            ("Faroe Islands", "FRO"),
            ("Portugal", "PRT"),
            ("Spain", "ESP"),
            ("Italy", "ITA"),
            ("Greece", "GRC"),
            ("Turkey", "TUR"),
            ("Egypt", "EGY"),
            ("Israel", "ISR"),
            ("Lebanon", "LBN"),
            ("Syria", "SYR"),
            ("Cyprus", "CYP"),
            ("Malta", "MLT"),
            ("Tunisia", "TUN"),
            ("Algeria", "DZA"),
            ("Morocco", "MAR"),
            ("Libya", "LBY"),
            ("Sudan", "SDN"),
            ("Eritrea", "ERI"),
            ("Djibouti", "DJI"),
            ("Somalia", "SOM"),
            ("Kenya", "KEN"),
            ("Tanzania", "TZA"),
            ("Mozambique", "MOZ"),
            ("South Africa", "ZAF"),
            ("Namibia", "NAM"),
            ("Angola", "AGO"),
            ("Democratic Republic of the Congo", "COD"),
            ("Republic of the Congo", "COG"),
            ("Gabon", "GAB"),
            ("Equatorial Guinea", "GNQ"),
            ("São Tomé and Príncipe", "STP"),
            ("Cameroon", "CMR"),
            ("Nigeria", "NGA"),
            ("Benin", "BEN"),
            ("Togo", "TGO"),
            ("Ghana", "GHA"),
            ("Côte d'Ivoire", "CIV"),
            ("Liberia", "LBR"),
            ("Sierra Leone", "SLE"),
            ("Guinea", "GIN"),
            ("Guinea-Bissau", "GNB"),
            ("Gambia", "GMB"),
            ("Senegal", "SEN"),
            ("Mauritania", "MRT"),
            ("Cape Verde", "CPV"),
        ]

def load_cache_metadata():
    """Load cache metadata from JSON file"""
    if CACHE_METADATA_FILE.exists():
        try:
            with open(CACHE_METADATA_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading cache metadata: {e}")
    return {"last_refresh_static": None, "last_refresh_dynamic": None, "version": "1.0"}

def save_cache_metadata(metadata):
    """Save cache metadata to JSON file"""
    try:
        with open(CACHE_METADATA_FILE, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
    except Exception as e:
        print(f"Error saving cache metadata: {e}")

def get_cache_age(last_refresh, unit='hours'):
    """Get age of cache in specified unit"""
    if not last_refresh:
        return float('inf')
    try:
        if isinstance(last_refresh, str):
            last_refresh = datetime.fromisoformat(last_refresh.replace('Z', '+00:00'))
        age = datetime.now() - last_refresh.replace(tzinfo=None)
        if unit == 'hours':
            return age.total_seconds() / 3600
        elif unit == 'days':
            return age.total_seconds() / (3600 * 24)
    except Exception as e:
        print(f"Error calculating cache age: {e}")
        return float('inf')

def pregenerate_default_kmls(force_regeneration=False, changed_layers=None):
    """Pre-generate default-style KMLs for static layers using desktop processing logic"""
    import geopandas as gpd
    import zipfile
    import xml.etree.ElementTree as ET
    from shapely import wkt
    from processing.kml_style import download_kml, process_kml, process_line_kml
    from core.utils import hex_to_kml_abgr

    country_dir = PREGENERATED_DIR / "country"
    global_dir = PREGENERATED_DIR / "global"
    country_dir.mkdir(parents=True, exist_ok=True)
    global_dir.mkdir(parents=True, exist_ok=True)

    # Check if we can skip regeneration (for static data only)
    if not force_regeneration and changed_layers is not None:
        # Check if country KMLs exist
        country_kmls_exist = country_dir.exists() and any(country_dir.rglob("*.kml"))
        global_kmls_exist = global_dir.exists() and any(global_dir.rglob("*.kml"))

        if country_kmls_exist and global_kmls_exist and not changed_layers:
            print("PREGENERATE: All KMLs exist and no layers changed - skipping regeneration")
            return

        if not changed_layers:
            print("PREGENERATE: No layers changed - skipping regeneration")
            return

    # Default styling (from config defaults, converted to ABGR)
    from core.config import DEFAULT_COLORS, DEFAULT_OPACITIES
    default_styles = {}
    for layer_type in ['territorial', 'contiguous', 'eez', 'ecs', 'mpa', 'cables']:
        color_abgr = hex_to_kml_abgr(DEFAULT_COLORS[layer_type], int(DEFAULT_OPACITIES[layer_type]))
        default_styles[layer_type] = {'color_abgr': color_abgr}

    # Load MarineRegions shapefiles and process like desktop version
    marineregions_dir = STATIC_CACHE_DIR / "marineregions"

    # Define layer configurations matching desktop defaults (hard-coded)
    layer_configs = {
        'eez': {
            'shp_pattern': 'eez*.shp',
            'color_hex': '#0000FF',  # Blue
            'opacity': 20,
            'kml_suffix': 'eez'
        },
        'territorial': {
            'shp_pattern': 'territorial_seas*.shp',
            'color_hex': '#FFFF00',  # Yellow
            'opacity': 20,
            'kml_suffix': 'territorial_waters'
        },
        'contiguous': {
            'shp_pattern': 'contiguous_zones*.shp',
            'color_hex': '#00FF00',  # Green
            'opacity': 20,
            'kml_suffix': 'contiguous_zone'
        },
        'ecs': {
            'shp_pattern': 'ecs*.shp',
            'color_hex': '#8B4513',  # Brown
            'opacity': 20,
            'kml_suffix': 'ecs'
        }
    }

    # Find all shapefiles in the marineregions directory
    all_shp_files = list(marineregions_dir.glob("*.shp"))
    print(f"PREGENERATE: Found {len(all_shp_files)} shapefiles in marineregions: {[str(f.name) for f in all_shp_files]}")

    if all_shp_files:
        # Collect all unique countries from EEZ data (matching desktop approach)
        eez_shp_files = [f for f in all_shp_files if f.match('eez*.shp')]
        if eez_shp_files:
            eez_shp = eez_shp_files[0]
            print(f"PREGENERATE: Loading EEZ shapefile for countries: {eez_shp}")
            try:
                gdf_eez = gpd.read_file(eez_shp)

                # Clean and validate geometries (matching desktop)
                print(f"PREGENERATE: Cleaning EEZ geometries ({len(gdf_eez)} features)")
                gdf_eez = gdf_eez[gdf_eez.geometry.is_valid & ~gdf_eez.geometry.is_empty]
                gdf_eez['geometry'] = gdf_eez['geometry'].make_valid().buffer(0)
                gdf_eez = gdf_eez.to_crs('EPSG:4326')

                # Get unique countries from EEZ data
                iso_col = 'iso_ter1' if 'iso_ter1' in gdf_eez.columns else ('ISO_TERR1' if 'ISO_TERR1' in gdf_eez.columns else None)
                if iso_col:
                    all_countries = gdf_eez[iso_col].unique()
                    all_countries = [c for c in all_countries if c and not pd.isna(c)]
                    all_countries = sorted(list(set(all_countries)))
                    print(f"PREGENERATE: Found {len(all_countries)} countries from EEZ data (column '{iso_col}')")
                else:
                    print("PREGENERATE: No ISO column found in EEZ data")
                    all_countries = []

                # Clean up EEZ GeoDataFrame
                del gdf_eez
                gc.collect()

            except Exception as e:
                print(f"PREGENERATE: Error loading EEZ shapefile: {e}")
                all_countries = []
        else:
            print("PREGENERATE: No EEZ shapefile found")
            all_countries = []

        # Process each layer type separately (matching desktop)
        for layer_key, config in layer_configs.items():
            try:
                shp_files = [f for f in all_shp_files if f.match(config['shp_pattern']) or layer_key.lower() in str(f).lower()]
                if not shp_files:
                    print(f"PREGENERATE: No shapefiles found for {layer_key}")
                    continue

                shp_file = shp_files[0]
                print(f"PREGENERATE: Processing {layer_key} from {shp_file.name}")

                # Load the shapefile
                gdf = gpd.read_file(shp_file)
                if gdf.empty:
                    print(f"PREGENERATE: {layer_key} shapefile is empty")
                    continue

                # Clean and validate geometries (matching desktop)
                print(f"PREGENERATE: Cleaning {layer_key} geometries ({len(gdf)} features)")
                gdf = gdf[gdf.geometry.is_valid & ~gdf.geometry.is_empty]
                gdf['geometry'] = gdf['geometry'].make_valid().buffer(0)
                gdf = gdf.to_crs('EPSG:4326')

                # Fix problematic fields (matching desktop)
                for col in gdf.columns:
                    if col in ['mrgid_sov1', 'mrgid_eez', 'mrgid_ter1', 'mrgid_sov2']:
                        gdf[col] = gdf[col].fillna(0).astype(int)
                    elif gdf[col].dtype == 'object':
                        gdf[col] = gdf[col].fillna('').astype(str)

                # Determine ISO column
                iso_col = 'iso_ter1' if 'iso_ter1' in gdf.columns else ('ISO_TERR1' if 'ISO_TERR1' in gdf.columns else None)

                if iso_col:
                    # Process each country for this layer
                    for country_iso in all_countries:
                        try:
                            country_iso_dir = country_dir / str(country_iso)
                            country_iso_dir.mkdir(exist_ok=True)

                            # Filter data for this country
                            country_data = gdf[gdf[iso_col] == country_iso]

                            if not country_data.empty:
                                # Generate temp KML with geopandas (matching desktop)
                                temp_kml = country_iso_dir / f"{country_iso}_{config['kml_suffix']}_temp.kml"
                                final_kml = country_iso_dir / f"{country_iso}_{config['kml_suffix']}.kml"

                                # Convert to KML using geopandas
                                country_data.to_file(str(temp_kml), driver='KML')

                                # Apply desktop styling using process_kml
                                color_abgr = hex_to_kml_abgr(config['color_hex'], config['opacity'])
                                if process_kml(str(temp_kml), str(final_kml), color_abgr):
                                    print(f"PREGENERATE: Generated {config['kml_suffix']} for {country_iso}")
                                else:
                                    print(f"PREGENERATE: Failed to style {config['kml_suffix']} for {country_iso}")

                                # Clean up temp file
                                if temp_kml.exists():
                                    temp_kml.unlink()
                            else:
                                print(f"PREGENERATE: No {layer_key} data for {country_iso}")

                        except Exception as country_error:
                            print(f"PREGENERATE: Error processing {layer_key} for country {country_iso}: {country_error}")
                            continue

                # Clean up GeoDataFrame
                del gdf
                gc.collect()

            except Exception as layer_error:
                print(f"PREGENERATE: Error processing {layer_key}: {layer_error}")
                continue

        print(f"PREGENERATE: MarineRegions processing complete - processed {len(all_countries)} countries")
    else:
        print("PREGENERATE: No MarineRegions shapefiles found")

    # Process WDPA data for MPAs
    wdpa_dir = STATIC_CACHE_DIR / "wdpa"
    wdpa_files = list(wdpa_dir.glob("*.zip"))
    if wdpa_files:
        wdpa_file = wdpa_files[0]
        print(f"PREGENERATE: Processing MPA data from {wdpa_file}")
        mpa_gdf = None
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                print(f"PREGENERATE: Extracting WDPA ZIP to {temp_dir}")
                with zipfile.ZipFile(wdpa_file, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)

                # Check for direct shapefiles
                shp_files = list(Path(temp_dir).glob("*.shp"))
                if not shp_files:
                    # Check for nested ZIP files
                    nested_zips = list(Path(temp_dir).glob("*.zip"))
                    print(f"PREGENERATE: Found {len(nested_zips)} nested ZIPs")
                    for nested_zip in nested_zips[:1]:  # Just extract the first one for demo
                        print(f"PREGENERATE: Extracting nested ZIP {nested_zip}")
                        with zipfile.ZipFile(nested_zip, 'r') as inner_zip:
                            inner_zip.extractall(temp_dir)
                        break

                shp_files = list(Path(temp_dir).glob("*.shp"))
                print(f"PREGENERATE: Found {len(shp_files)} shapefiles: {[str(f) for f in shp_files]}")
                if shp_files:
                    # Prefer polygons shapefile over points
                    polygons_shp = None
                    for shp_file in shp_files:
                        if 'polygons' in str(shp_file).lower():
                            polygons_shp = shp_file
                            break
                    if not polygons_shp:
                        polygons_shp = shp_files[0]  # fallback to first one

                    print(f"PREGENERATE: Reading shapefile {polygons_shp}")
                    mpa_gdf = gpd.read_file(polygons_shp)
                    print(f"PREGENERATE: Loaded {len(mpa_gdf)} MPA features")
                    print(f"PREGENERATE: MPA columns: {list(mpa_gdf.columns)}")
                else:
                    print("PREGENERATE: No shapefiles found in extracted ZIP")

            # Generate country-specific MPA KMLs
            if mpa_gdf is not None and any(col.lower() == 'iso3' for col in mpa_gdf.columns):
                # Find the correct column name (case-insensitive)
                iso3_col = next(col for col in mpa_gdf.columns if col.lower() == 'iso3')

                mpa_countries = mpa_gdf[iso3_col].unique()
                mpa_countries = [c for c in mpa_countries if c and not pd.isna(c)]
                print(f"PREGENERATE: Found {len(mpa_countries)} countries with MPA data (using column '{iso3_col}')")

                success_count = 0
                for country_iso in mpa_countries:
                    try:
                        country_iso_dir = country_dir / str(country_iso)
                        country_iso_dir.mkdir(exist_ok=True)

                        country_mpa = mpa_gdf[mpa_gdf[iso3_col] == country_iso]
                        if not country_mpa.empty:
                            mpa_kml = country_iso_dir / f"{country_iso}_MPA.kml"
                            temp_kml = country_iso_dir / f"{country_iso}_MPA_temp.kml"

                            # Clean MPA data
                            country_mpa = country_mpa[country_mpa.geometry.is_valid & ~country_mpa.geometry.is_empty]

                            try:
                                # Create basic KML first
                                country_mpa.to_file(str(temp_kml), driver='KML')

                                # Apply desktop MPA styling (red fill)
                                mpa_color_abgr = "ff0000ff"  # Red with full opacity
                                if process_kml(str(temp_kml), str(mpa_kml), mpa_color_abgr):
                                    print(f"PREGENERATE: Generated MPA for {country_iso} ({len(country_mpa)} features)")
                                    success_count += 1
                                else:
                                    print(f"PREGENERATE: Failed to style MPA for {country_iso}")

                                # Clean up temp file
                                if temp_kml.exists():
                                    temp_kml.unlink()

                            except Exception as kml_error:
                                print(f"PREGENERATE: Failed to generate MPA KML for {country_iso}: {kml_error}")
                    except Exception as country_error:
                        print(f"PREGENERATE: Error processing MPA country {country_iso}: {country_error}")
                        continue

                print(f"PREGENERATE: MPA processing complete - {success_count}/{len(mpa_countries)} countries succeeded")
            else:
                print("PREGENERATE: MPA data not loaded or missing iso3 column")

            # Clean up MPA GeoDataFrame and force garbage collection
            if 'mpa_gdf' in locals() and mpa_gdf is not None:
                del mpa_gdf
            gc.collect()

        except Exception as e:
            print(f"PREGENERATE: Error processing MPA data: {e}")
            # Clean up on error too
            if 'mpa_gdf' in locals() and mpa_gdf is not None:
                del mpa_gdf
            gc.collect()

    # Process cables (global) - use desktop process_line_kml for proper styling
    cables_files = list(STATIC_CACHE_DIR.glob("cables_global.*"))
    if cables_files:
        cables_file = cables_files[0]
        print(f"PREGENERATE: Processing cables data from {cables_file}")
        try:
            cables_kml = global_dir / "sub_cables.kml"

            # Use desktop process_line_kml with random colors (handles duplicates automatically)
            default_color_hex = "#ffffff"  # White cables
            default_opacity = "50"

            if process_line_kml(str(cables_file), str(cables_kml), default_color_hex, default_opacity, use_random=True):
                print(f"PREGENERATE: Generated cables KML with desktop processing")
            else:
                print(f"PREGENERATE: Failed to generate cables KML using desktop processing")

        except Exception as e:
            print(f"PREGENERATE: Error processing cables data: {e}")

    # Process nav warnings (global)
    nav_files = list(DYNAMIC_CACHE_DIR.glob("nav_warnings/*"))
    if nav_files:
        nav_file = max(nav_files, key=lambda x: x.stat().st_mtime)
        print(f"PREGENERATE: Processing nav warnings from {nav_file}")
        try:
            # For now, create a simple placeholder KML
            # Use today's date for the filename
            today = datetime.now().strftime("%d%m%Y")
            nav_kml = global_dir / f"NAVWARN_{today}.kml"
            # In real implementation, would parse the nav data and create proper KML
            with open(nav_kml, 'w', encoding='utf-8') as f:
                f.write("""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Navigation Warnings</name>
    <Placemark>
      <name>Navigation Warnings Data</name>
      <Point>
        <coordinates>0,0,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>""")
            print(f"PREGENERATE: Generated {nav_kml}")

        except Exception as e:
            print(f"PREGENERATE: Error processing nav warnings: {e}")

def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA-256 hash of a file."""
    hash_sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()

def calculate_directory_hash(dir_path: Path) -> dict:
    """Calculate hashes for all files in a directory."""
    hashes = {}
    for file_path in dir_path.rglob("*"):
        if file_path.is_file():
            relative_path = file_path.relative_to(dir_path)
            hashes[str(relative_path)] = calculate_file_hash(file_path)
    return hashes

def compare_directory_hashes(old_hashes: dict, new_hashes: dict) -> bool:
    """Compare two directory hash dictionaries. Return True if identical."""
    return old_hashes == new_hashes

def calculate_layer_hashes(static_dir: Path) -> dict:
    """Calculate hashes for each static layer subdirectory."""
    layer_hashes = {}

    # Define the static layers and their subdirectories
    static_layers = {
        'marineregions': static_dir / 'marineregions',
        'wdpa': static_dir / 'wdpa',
        'cables': static_dir / 'cables_global.geojson'  # This is a file, not dir
    }

    for layer_name, layer_path in static_layers.items():
        if layer_path.exists():
            if layer_path.is_file():
                # For single files like cables_global.geojson
                layer_hashes[layer_name] = calculate_file_hash(layer_path)
            elif layer_path.is_dir():
                # For directories like marineregions, wdpa
                layer_hashes[layer_name] = calculate_directory_hash(layer_path)
        else:
            layer_hashes[layer_name] = None

    return layer_hashes

def has_layer_changed(old_layer_hashes: dict, new_layer_hashes: dict, layer_name: str) -> bool:
    """Check if a specific layer has changed by comparing hashes."""
    old_hash = old_layer_hashes.get(layer_name)
    new_hash = new_layer_hashes.get(layer_name)

    if old_hash is None and new_hash is None:
        return False  # Both missing - no change
    if old_hash is None or new_hash is None:
        return True   # One missing, one present - changed
    if isinstance(old_hash, dict) and isinstance(new_hash, dict):
        return not compare_directory_hashes(old_hash, new_hash)  # Directory comparison
    else:
        return old_hash != new_hash  # File hash comparison

def backup_directory(source_dir: Path, backup_suffix: str) -> Path:
    """Create a timestamped backup of a directory in temp location outside OneDrive."""
    import tempfile

    # Use system temp directory instead of OneDrive to avoid permission issues
    temp_base = Path(tempfile.gettempdir()) / "mda_backups"
    temp_base.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = temp_base / f"{source_dir.name}_backup_{timestamp}_{backup_suffix}"

    if source_dir.exists():
        shutil.copytree(source_dir, backup_dir)
        print(f"PIPELINE: Backed up {source_dir} to temp location: {backup_dir}")
    return backup_dir

def safe_delete_backup(backup_dir: Path):
    """Safely delete a backup directory with enhanced Windows permission handling."""
    if not backup_dir.exists():
        return

    log_pipeline_action("BACKUP DELETE", f"Attempting to delete: {backup_dir}")

    # Force garbage collection before deletion to release file handles
    gc.collect()
    time.sleep(1)  # Give system time to release handles

    # Make all files writable (helps on Windows/OneDrive)
    for root, dirs, files in os.walk(backup_dir):
        for d in dirs:
            try:
                (Path(root) / d).chmod(0o777)
            except Exception:
                pass  # Ignore permission errors during chmod
        for f in files:
            try:
                (Path(root) / f).chmod(0o666)
            except Exception:
                pass  # Ignore permission errors during chmod

    # Try deletion with increased retries and longer delays
    for attempt in range(1, 11):  # Increased to 10 attempts
        try:
            shutil.rmtree(backup_dir)
            log_pipeline_action("BACKUP DELETE", f"Successfully deleted: {backup_dir}")
            return
        except PermissionError as e:
            wait_time = min(3 + attempt, 8)  # Progressive delay up to 8s
            log_pipeline_action("BACKUP DELETE", f"PermissionError on attempt {attempt}/10: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
            # Force garbage collection again
            gc.collect()
        except Exception as e:
            log_pipeline_action("BACKUP DELETE", f"Failed to delete backup {backup_dir}: {e}")
            break

    # Final fallback - ignore errors and extended cleanup
    try:
        shutil.rmtree(backup_dir, ignore_errors=True)
        time.sleep(2)  # Wait for ignore_errors to complete
        if backup_dir.exists():
            log_pipeline_action("BACKUP DELETE", f"Could not delete backup {backup_dir} after retries - manual cleanup needed: {backup_dir}")
        else:
            log_pipeline_action("BACKUP DELETE", f"Backup eventually deleted via ignore_errors")
    except Exception as e:
        log_pipeline_action("BACKUP DELETE", f"Final deletion attempt failed: {e}")

def retry_download(func, max_retries=3, backoff_factor=2):
    """Retry a download function with exponential backoff."""
    for attempt in range(max_retries):
        try:
            result = func()
            return result, True  # Success
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = backoff_factor ** attempt
                print(f"PIPELINE: Download attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"PIPELINE: Download failed after {max_retries} attempts: {e}")
                return None, False  # Failure

def log_pipeline_action(action: str, details: str = ""):
    """Log pipeline actions with timestamps."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"PIPELINE [{timestamp}]: {action} {details}")

def fix_duplicate_kml_ids(kml_path: Path):
    """Fix duplicate IDs in KML files by appending counters."""
    if not kml_path.exists():
        return False

    try:
        ET.register_namespace('', 'http://www.opengis.net/kml/2.2')
        tree = ET.parse(kml_path)
        root = tree.getroot()

        # Find all placemarks and track IDs
        seen_ids = set()
        placemarks = root.findall('.//{http://www.opengis.net/kml/2.2}Placemark')

        for pm in placemarks:
            pm_id = pm.get('id')
            if pm_id:
                original_id = pm_id
                counter = 1
                while pm_id in seen_ids:
                    pm_id = f"{original_id}_{counter}"
                    counter += 1
                if pm_id != original_id:
                    pm.set('id', pm_id)
                seen_ids.add(pm_id)

        tree.write(kml_path, encoding='utf-8', xml_declaration=True)
        return True
    except Exception as e:
        print(f"Failed to fix duplicate IDs in {kml_path}: {e}")
        return False

def refresh_static_data():
    """Refresh STATIC data with granular change detection and conditional KML regeneration."""
    log_pipeline_action("STATIC REFRESH", "Starting static data refresh")

    metadata = load_cache_metadata()
    static_dir = RAW_SOURCE_DIR / "static"

    # Check if refresh is needed (30 days OR manual flag)
    static_age_days = get_cache_age(metadata.get('last_refresh_static'), 'days')
    static_changed_flag = metadata.get('static_changed', False)

    if static_age_days <= 30 and not static_changed_flag:
        log_pipeline_action("STATIC REFRESH", f"Skipped - age {static_age_days:.1f} days, no change flag")
        return True  # Not an error, just no refresh needed

    log_pipeline_action("STATIC REFRESH", f"Refresh triggered - age {static_age_days:.1f} days, change flag: {static_changed_flag}")

    # Get old layer hashes for comparison
    old_layer_hashes = metadata.get('static_layers', {})

    # Create backup before any changes
    backup_dir = backup_directory(static_dir, "static_pre_download")

    # Download new static data with retry logic
    download_success = True
    try:
        from downloaders.marineregions import refresh_static_caches
        from downloaders.wdpa import refresh_static_caches as refresh_wdpa
        from downloaders.submarine_cables import refresh_static_caches as refresh_cables

        def download_static():
            refresh_static_caches()
            refresh_wdpa()
            refresh_cables()
            return True

        result, success = retry_download(download_static, max_retries=3)
        if not success:
            log_pipeline_action("STATIC REFRESH", "Download failed after retries - keeping backup")
            download_success = False
            return False

        log_pipeline_action("STATIC REFRESH", "Download completed successfully")

    except Exception as e:
        log_pipeline_action("STATIC REFRESH", f"Download failed: {e}")
        download_success = False
        return False

    if download_success:
        # Calculate new layer hashes for change detection
        new_layer_hashes = calculate_layer_hashes(static_dir)

        # Check which layers changed
        changed_layers = []
        for layer_name in ['marineregions', 'wdpa', 'cables']:
            if has_layer_changed(old_layer_hashes, new_layer_hashes, layer_name):
                changed_layers.append(layer_name)

        # Check if country KMLs exist
        kml_dir = PREGENERATED_DIR / "country"
        kmls_exist = kml_dir.exists() and any(kml_dir.rglob("*.kml"))

        needs_kml_regen = bool(changed_layers) or not kmls_exist

        kml_generation_success = True
        if needs_kml_regen:
            log_pipeline_action("STATIC REFRESH", f"Changed layers: {changed_layers}, KMLs exist: {kmls_exist} - regenerating KMLs")
            try:
                pregenerate_default_kmls(force_regeneration=False, changed_layers=changed_layers)
                log_pipeline_action("STATIC REFRESH", "KML regeneration completed")
            except Exception as e:
                log_pipeline_action("STATIC REFRESH", f"KML regeneration failed: {e}")
                kml_generation_success = False

        # Only mark as successful if both download and KML generation succeeded
        if not kml_generation_success:
            return False
        else:
            log_pipeline_action("STATIC REFRESH", "No changes detected and KMLs exist - skipping regeneration")

        # Update metadata with new hashes and timestamp
        metadata['static_layers'] = new_layer_hashes
        metadata['last_refresh_static'] = datetime.now()
        metadata['static_changed'] = False  # Reset flag

        # Success: delete backup and save metadata
        safe_delete_backup(backup_dir)
        save_cache_metadata(metadata)
        log_pipeline_action("STATIC REFRESH", "Completed successfully")
        return True

    return False

def refresh_dynamic_data():
    """Refresh DYNAMIC data unconditionally with immediate KML regeneration."""
    log_pipeline_action("DYNAMIC REFRESH", "Starting unconditional dynamic data refresh")

    metadata = load_cache_metadata()
    dynamic_dir = RAW_SOURCE_DIR / "dynamic"

    # Check age - allow some tolerance for testing (unconditional refresh every run for now)
    dynamic_age_hours = get_cache_age(metadata.get('last_refresh_dynamic'), 'hours')
    log_pipeline_action("DYNAMIC REFRESH", f"Age: {dynamic_age_hours:.1f} hours - unconditional refresh")

    # Create backup before downloading
    backup_dir = backup_directory(dynamic_dir, "dynamic_pre_download")

    # Download new dynamic data with retry logic
    download_success = True
    try:
        from downloaders.oscar_currents import refresh_dynamic_caches
        from downloaders.navigation_warnings import refresh_dynamic_caches as refresh_nav

        def download_dynamic():
            refresh_dynamic_caches()
            refresh_nav()
            return True

        result, success = retry_download(download_dynamic, max_retries=3)
        if not success:
            log_pipeline_action("DYNAMIC REFRESH", "Download failed after retries - keeping backup")
            download_success = False
            return False

        log_pipeline_action("DYNAMIC REFRESH", "Download completed successfully")

    except Exception as e:
        log_pipeline_action("DYNAMIC REFRESH", f"Download failed: {e}")
        download_success = False
        return False

    if download_success:
        # Always regenerate global KMLs for dynamic data (sub_cables and NAVWARN)
        try:
            # Force regeneration for dynamic data
            pregenerate_default_kmls(force_regeneration=True, changed_layers=None)
            log_pipeline_action("DYNAMIC REFRESH", "KML regeneration completed")
        except Exception as e:
            log_pipeline_action("DYNAMIC REFRESH", f"KML regeneration failed: {e}")
            return False

        # Success: delete backup and update metadata
        safe_delete_backup(backup_dir)
        metadata['last_refresh_dynamic'] = datetime.now()
        save_cache_metadata(metadata)
        log_pipeline_action("DYNAMIC REFRESH", "Completed successfully")
        return True

    return False

def refresh_caches():
    """Main pipeline: Refresh static and dynamic data following exact rules."""
    log_pipeline_action("PIPELINE", "Starting automated data pipeline refresh")

    metadata = load_cache_metadata()

    # Always refresh dynamic data (every 12 hours, unconditionally)
    log_pipeline_action("PIPELINE", "Phase 1: Refreshing DYNAMIC data (unconditional)")
    dynamic_success = refresh_dynamic_data()

    # Conditionally refresh static data (every 30 days OR change flag)
    log_pipeline_action("PIPELINE", "Phase 2: Checking STATIC data refresh conditions")
    static_success = refresh_static_data()

    # Save final metadata state
    save_cache_metadata(metadata)

    # Summary logging
    if dynamic_success and static_success:
        log_pipeline_action("PIPELINE", "Pipeline refresh completed successfully - both phases succeeded")
    elif dynamic_success:
        log_pipeline_action("PIPELINE", "Pipeline refresh completed - dynamic succeeded, static skipped or failed")
    elif static_success:
        log_pipeline_action("PIPELINE", "Pipeline refresh completed - static succeeded, dynamic failed")
    else:
        log_pipeline_action("PIPELINE", "Pipeline refresh completed with failures in both phases")

# Initialize and start the scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(refresh_caches, 'interval', hours=12, id='cache_refresh')
scheduler.start()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def run_download_task(task_id, settings, country_path, global_path, cache_path, iso_code, country_name, username, password, progress_queue):
    """Run the download task in a separate thread"""
    print(f"RUN DOWNLOAD TASK STARTED for task_id={task_id}")
    try:
        def progress_callback(delta: float, message: str = ""):
            print(f"PROGRESS UPDATE SENT: delta={delta}, message='{message}'")
            if message:
                progress_queue.put({"type": "message", "content": message})
            if delta > 0:
                progress_queue.put({"type": "progress", "content": delta})

        # Run the processing
        success = worker(settings, username, password, str(country_path), str(global_path), cache_path, iso_code, country_name, progress_callback)

        if success:
            progress_queue.put({"type": "complete", "content": "Download completed successfully!"})
        else:
            progress_queue.put({"type": "error", "content": "Download failed. Check logs for details."})

    except Exception as e:
        progress_queue.put({"type": "error", "content": f"Task failed: {str(e)}"})

@app.route('/')
def index():
    """Main page with layer selection form"""
    # Get cache status for display
    metadata = load_cache_metadata()
    static_age = get_cache_age(metadata.get('last_refresh_static'), 'days')
    dynamic_age = get_cache_age(metadata.get('last_refresh_dynamic'), 'hours')

    cache_status = {
        'static_age_days': static_age,
        'dynamic_age_hours': dynamic_age,
        'static_never_refreshed': static_age == float('inf') or static_age > 999,
        'dynamic_never_refreshed': dynamic_age == float('inf') or dynamic_age > 999,
        'last_static': metadata.get('last_refresh_static'),
        'last_dynamic': metadata.get('last_refresh_dynamic')
    }

    # Load countries for dropdown
    countries = load_countries()

    return render_template('index.html', cache_status=cache_status, countries=countries)

@app.route('/cache_status')
def cache_status():
    """API endpoint for cache status"""
    metadata = load_cache_metadata()
    return jsonify({
        'static_age_days': get_cache_age(metadata.get('last_refresh_static'), 'days'),
        'dynamic_age_hours': get_cache_age(metadata.get('last_refresh_dynamic'), 'hours'),
        'last_refresh_static': metadata.get('last_refresh_static'),
        'last_refresh_dynamic': metadata.get('last_refresh_dynamic')
    })

@app.route('/get_iso_code')
def get_iso_code():
    """API endpoint to get ISO code for a country"""
    country = request.args.get('country', '')

    # Load countries and find matching ISO code
    countries = load_countries()
    for country_name, iso_code in countries:
        if country_name == country:
            return jsonify({'iso_code': iso_code})

    # If not found, try to extract from parenthetical in the display name
    # (e.g., "Japan (JPN)" -> extract "JPN")
    if ' (' in country and country.endswith(')'):
        iso_code = country.split(' (')[-1].rstrip(')')
        return jsonify({'iso_code': iso_code})

    return jsonify({'iso_code': ''})

@app.route('/start_download', methods=['POST'])
def start_download():
    """Handle the download request"""
    try:
        # Extract form data
        country = request.form.get('country', '')
        iso_code = request.form.get('iso_code', '')
        username = request.form.get('nasa_username') or None
        password = request.form.get('nasa_password') or None

        print("MAIN THREAD: Form data extracted")
        print(f"  country={country}, iso_code={iso_code}")
        print(f"  layers selected: territorial={request.form.get('territorial')}, eez={request.form.get('eez')}")

        # Validate that we have both country and ISO code
        if not country:
            return jsonify({'error': 'Country is required'}), 400
        if not iso_code:
            return jsonify({'error': 'ISO code could not be determined for the selected country'}), 400

        print(f"MAIN THREAD: Processing for {country} ({iso_code})")
        print(f"MAIN THREAD: Passing NASA creds - username='{username[:3] if username else ''}...', password length={len(password) if password is not None else 'None'}")

        # Parse layer selections
        print("MAIN THREAD: Preparing LayerSettings args")
        print(f"  territorial={request.form.get('territorial')}")
        print(f"  eez={request.form.get('eez')}")
        print(f"  contiguous={request.form.get('contiguous')}")
        print(f"  mpa={request.form.get('mpa')}")
        print(f"  ecs={request.form.get('ecs')}")
        print(f"  cables={request.form.get('cables')}")
        print(f"  seastate_country={request.form.get('seastate_country')}")
        print(f"  seastate_global={request.form.get('seastate_global')}")
        print(f"  navwarnings={request.form.get('navwarnings')}")
        print(f"  territorial_color={request.form.get('territorial_color')}")
        print(f"  eez_color={request.form.get('eez_color')}")
        print(f"  contiguous_color={request.form.get('contiguous_color')}")
        print(f"  mpa_color={request.form.get('mpa_color')}")
        print(f"  ecs_color={request.form.get('ecs_color')}")
        print(f"  cables_color={request.form.get('cables_color')}")
        print(f"  seastate_color={request.form.get('seastate_color')}")
        print(f"  navwarnings_color={request.form.get('navwarnings_color')}")
        print(f"  territorial_opacity={request.form.get('territorial_opacity')}")
        print(f"  eez_opacity={request.form.get('eez_opacity')}")
        print(f"  contiguous_opacity={request.form.get('contiguous_opacity')}")
        print(f"  mpa_opacity={request.form.get('mpa_opacity')}")
        print(f"  ecs_opacity={request.form.get('ecs_opacity')}")
        print(f"  cables_opacity={request.form.get('cables_opacity')}")
        print(f"  seastate_opacity={request.form.get('seastate_opacity')}")
        print(f"  navwarnings_opacity={request.form.get('navwarnings_opacity')}")

        print("MAIN THREAD: Creating LayerSettings...")
        layer_settings = LayerSettings(
            # Country-specific layers
            territorial=request.form.get('territorial') == 'on',
            contiguous=request.form.get('contiguous') == 'on',
            mpa=request.form.get('mpa') == 'on',
            eez=request.form.get('eez') == 'on',
            ecs=request.form.get('ecs') == 'on',

            # Global layers
            cables=request.form.get('cables') == 'on',
            seastate_global=request.form.get('seastate_global') == 'on',
            navwarnings=request.form.get('navwarnings') == 'on',

            # Settings
            territorial_color=request.form.get('territorial_color', '#ffff00'),
            contiguous_color=request.form.get('contiguous_color', '#00ff00'),
            mpa_color=request.form.get('mpa_color', '#ff0000'),
            eez_color=request.form.get('eez_color', '#0000ff'),
            ecs_color=request.form.get('ecs_color', '#8B4513'),
            cables_color=request.form.get('cables_color', '#ffffff'),
            seastate_color=request.form.get('seastate_color', '#000000'),
            navwarnings_color=request.form.get('navwarnings_color', '#ff0000'),

            # Opacity values (as strings)
            territorial_opacity=request.form.get('territorial_opacity', '20'),
            contiguous_opacity=request.form.get('contiguous_opacity', '20'),
            mpa_opacity=request.form.get('mpa_opacity', '20'),
            eez_opacity=request.form.get('eez_opacity', '20'),
            ecs_opacity=request.form.get('ecs_opacity', '20'),
            cables_opacity=request.form.get('cables_opacity', '50'),
            seastate_opacity=request.form.get('seastate_opacity', '20'),
            navwarnings_opacity=request.form.get('navwarnings_opacity', '80'),

            # Other settings
            seastate_country=request.form.get('seastate_country') == 'on',

            # Sea state density settings (convert from form)
            seastate_density_country=float(request.form.get('seastate_density_country', '1.5')),
            seastate_density_global=float(request.form.get('seastate_density_global', '1.5')),

            # Other flags
            navwarnings_custom=request.form.get('navwarnings_custom') == 'on',
            cables_random=request.form.get('cables_random') == 'on'
        )
        print("MAIN THREAD: LayerSettings created successfully")
        print(f"  layer_settings type = {type(layer_settings)}")
        if hasattr(layer_settings, 'layers'):
            print(f"  layer_settings.layers type = {type(layer_settings.layers)}, len = {len(layer_settings.layers) if layer_settings.layers else 'None'}")
        else:
            print("  layer_settings has no 'layers' attribute")

        # Create unique task ID
        task_id = f"task_{len(current_tasks)}"

        # Set up directories
        base_dir = Path(app.config['OUTPUT_FOLDER']) / task_id
        base_dir.mkdir(exist_ok=True)

        country_dir = base_dir / "country" if country else None
        global_dir = base_dir / "global"
        cache_dir = base_dir / "cache"

        country_dir.mkdir(exist_ok=True)
        global_dir.mkdir(exist_ok=True)
        cache_dir.mkdir(exist_ok=True)

        # Set up progress tracking
        progress_queue = queue.Queue()
        progress_data[task_id] = {
            'messages': [],
            'progress': 0,
            'status': 'running',
            'country_dir': str(country_dir) if country_dir else None,
            'global_dir': str(global_dir),
            'queue': progress_queue
        }

        # Start the download task in a background thread
        print("MAIN THREAD: Starting download task")
        print(f"  task_id = {task_id}")
        print(f"  layer_settings type = {type(layer_settings)}")
        if hasattr(layer_settings, 'layers'):
            print(f"  layer_settings.layers type = {type(layer_settings.layers)}, len = {len(layer_settings.layers) if layer_settings.layers else 'None'}")
        else:
            print("  layer_settings has no 'layers' attribute")
        print(f"  country_path = {country_dir}, type = {type(country_dir)}")
        print(f"  global_path = {global_dir}, type = {type(global_dir)}")
        print(f"  cache_path = {cache_dir}, type = {type(cache_dir)}")
        print(f"  iso_code = {iso_code}, country_name = {country}")
        print(f"  username = {username}, password_len = {len(password) if password else 'None'}")

        download_thread = threading.Thread(
            target=run_download_task,
            args=(task_id, layer_settings, country_dir, global_dir, cache_dir, iso_code, country, username, password, progress_queue)
        )
        print("MAIN THREAD: Thread object created")
        download_thread.daemon = True
        download_thread.start()
        print(f"MAIN THREAD: Thread started, alive: {download_thread.is_alive()}")

        current_tasks[task_id] = download_thread

        return redirect(url_for('progress', task_id=task_id))

    except Exception as e:
        print("MAIN THREAD: LayerSettings or thread failed:", str(e))
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

        # Create unique task ID
        task_id = f"task_{len(current_tasks)}"

        # Set up directories
        base_dir = Path(app.config['OUTPUT_FOLDER']) / task_id
        base_dir.mkdir(exist_ok=True)

        country_dir = base_dir / "country" if country else None
        global_dir = base_dir / "global"
        cache_dir = base_dir / "cache"

        country_dir.mkdir(exist_ok=True)
        global_dir.mkdir(exist_ok=True)
        cache_dir.mkdir(exist_ok=True)

        # Set up progress tracking
        progress_queue = queue.Queue()
        progress_data[task_id] = {
            'messages': [],
            'progress': 0,
            'status': 'running',
            'country_dir': str(country_dir) if country_dir else None,
            'global_dir': str(global_dir),
            'queue': progress_queue
        }

        # Start the download task in a background thread
        print("MAIN THREAD: Starting download task")
        print(f"  task_id = {task_id}")
        print(f"  settings = {layer_settings}, layers = {layer_settings.layers if layer_settings else None}, layers type = {type(layer_settings.layers) if layer_settings and hasattr(layer_settings, 'layers') and layer_settings.layers else 'None'}")
        print(f"  country_path = {country_dir}, type = {type(country_dir)}")
        print(f"  global_path = {global_dir}, type = {type(global_dir)}")
        print(f"  cache_path = {cache_dir}, type = {type(cache_dir)}")
        print(f"  iso_code = {iso_code}, country_name = {country}")
        print(f"  username = {username}, password_len = {len(password) if password else 'None'}")

        print("MAIN THREAD: Creating thread with args...")
        download_thread = threading.Thread(
            target=run_download_task,
            args=(task_id, layer_settings, country_dir, global_dir, cache_dir, iso_code, country, username, password, progress_queue)
        )
        print("MAIN THREAD: Thread object created")
        download_thread.daemon = True
        download_thread.start()
        print(f"MAIN THREAD: Thread started, alive: {download_thread.is_alive()}")

        current_tasks[task_id] = download_thread

        return redirect(url_for('progress', task_id=task_id))

    except Exception as e:
        flash(f'Error starting download: {str(e)}')
        return redirect(url_for('index'))

@app.route('/progress/<task_id>')
def progress(task_id):
    """Show download progress"""
    if task_id not in progress_data:
        flash('Task not found')
        return redirect(url_for('index'))

    return render_template('progress.html', task_id=task_id)

@app.route('/progress_update/<task_id>')
def progress_update(task_id):
    """API endpoint for progress updates"""
    print(f"Progress poll requested for task {task_id} — current data: messages={len(progress_data.get(task_id, {}).get('messages', []))}, progress={progress_data.get(task_id, {}).get('progress', 0)}")

    if task_id not in progress_data:
        return jsonify({'error': 'Task not found'}), 404

    task_data = progress_data[task_id]
    progress_queue = task_data['queue']

    # Process new messages from the queue
    try:
        while True:
            update = progress_queue.get_nowait()
            print(f"PROCESSING QUEUE UPDATE: {update}")

            if update['type'] == 'message':
                task_data['messages'].append(update['content'])
            elif update['type'] == 'progress':
                task_data['progress'] = min(100, task_data['progress'] + update['content'])
            elif update['type'] == 'complete':
                task_data['status'] = 'completed'
                task_data['messages'].append(update['content'])
            elif update['type'] == 'error':
                task_data['status'] = 'error'
                task_data['messages'].append(update['content'])
    except queue.Empty:
        pass  # No more updates in queue

    return jsonify({
        'messages': task_data['messages'],
        'progress': task_data['progress'],
        'status': task_data['status']
    })

@app.route('/download/<task_id>/<path_type>')
def download(task_id, path_type):
    """Download generated files"""
    if task_id not in progress_data:
        flash('Task not found')
        return redirect(url_for('index'))

    task_data = progress_data[task_id]

    if path_type == 'country' and task_data['country_dir']:
        download_dir = task_data['country_dir']
    elif path_type == 'global':
        download_dir = task_data['global_dir']
    else:
        flash('Invalid download type')
        return redirect(url_for('progress', task_id=task_id))

    # Create a zip file of the output directory
    import zipfile
    zip_path = os.path.join(app.config['OUTPUT_FOLDER'], f'{task_id}_{path_type}.zip')

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(download_dir):
            for file in files:
                zipf.write(os.path.join(root, file),
                          os.path.relpath(os.path.join(root, file), download_dir))

    return send_file(zip_path, as_attachment=True, download_name=f'{task_id}_{path_type}.zip')

if __name__ == '__main__':
    # Initial cache check on startup (only once, using persistent file)
    if not CACHE_INITIALIZED_FILE.exists():
        print("APP STARTUP: Checking cache status and pre-generating KMLs...")
        refresh_caches()
        # Create initialization flag file
        CACHE_INITIALIZED_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_INITIALIZED_FILE.write_text("initialized")
        print("APP STARTUP: Cache initialization completed and marked as done")

    app.run(debug=True, host='0.0.0.0', port=5000)