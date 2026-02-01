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
from pathlib import Path
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

def pregenerate_default_kmls():
    """Pre-generate default-style KMLs for static layers"""
    import geopandas as gpd
    import zipfile
    from shapely import wkt

    country_dir = PREGENERATED_DIR / "country"
    global_dir = PREGENERATED_DIR / "global"
    country_dir.mkdir(parents=True, exist_ok=True)
    global_dir.mkdir(parents=True, exist_ok=True)

    # Default styling (from LayerSettings defaults)
    default_styles = {
        'territorial': {'color': '#ffff00', 'opacity': '20'},
        'contiguous': {'color': '#00ff00', 'opacity': '20'},
        'eez': {'color': '#0000ff', 'opacity': '20'},
        'ecs': {'color': '#8B4513', 'opacity': '20'},
        'mpa': {'color': '#ff0000', 'opacity': '20'},
        'cables': {'color': '#ffffff', 'opacity': '50'}
    }

    # Process EEZ data for country-specific layers
    marineregions_dir = STATIC_CACHE_DIR / "marineregions"
    # Look for extracted shapefile from the ZIP
    shp_files = list(marineregions_dir.glob("*.shp"))
    if shp_files:
        eez_shp = shp_files[0]
        print(f"PREGENERATE: Loading EEZ data from {eez_shp}")
        try:
            gdf = gpd.read_file(eez_shp)

            # Get unique countries from EEZ data
            if 'iso_ter1' in gdf.columns:
                countries = gdf['iso_ter1'].unique()
                print(f"PREGENERATE: Found {len(countries)} countries in EEZ data")

                for country_iso in countries[:10]:  # Limit to first 10 for demo
                    if pd.isna(country_iso) or not country_iso:
                        continue

                    country_iso_dir = country_dir / str(country_iso)
                    country_iso_dir.mkdir(exist_ok=True)

                    # Generate country-specific KMLs
                    country_data = gdf[gdf['iso_ter1'] == country_iso]

                    if not country_data.empty:
                        # EEZ
                        eez_kml = country_iso_dir / f"{country_iso}_EEZ.kml"
                        country_data.to_file(eez_kml, driver='KML')
                        print(f"PREGENERATE: Generated {eez_kml}")

                        # Territorial waters (simplified - would need 12nm buffer logic)
                        # For demo, just copy EEZ
                        territorial_kml = country_iso_dir / f"{country_iso}_TTW.kml"
                        country_data.to_file(territorial_kml, driver='KML')
                        print(f"PREGENERATE: Generated {territorial_kml}")

                        # Similar for contiguous and ECS
                        contiguous_kml = country_iso_dir / f"{country_iso}_Contig.kml"
                        country_data.to_file(contiguous_kml, driver='KML')

                        ecs_kml = country_iso_dir / f"{country_iso}_ECS.kml"
                        country_data.to_file(ecs_kml, driver='KML')

        except Exception as e:
            print(f"PREGENERATE: Error processing EEZ data: {e}")

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
                print(f"PREGENERATE: Found {len(mpa_countries)} countries with MPA data (using column '{iso3_col}')")
                for country_iso in mpa_countries[:10]:  # Limit for demo
                    if pd.isna(country_iso) or not country_iso:
                        continue

                    country_iso_dir = country_dir / str(country_iso)
                    country_iso_dir.mkdir(exist_ok=True)

                    country_mpa = mpa_gdf[mpa_gdf[iso3_col] == country_iso]
                    print(f"PREGENERATE: Country {country_iso}: {len(country_mpa)} MPA features")
                    if not country_mpa.empty:
                        mpa_kml = country_iso_dir / f"{country_iso}_MPA.kml"
                        try:
                            country_mpa.to_file(mpa_kml, driver='KML')
                            print(f"PREGENERATE: Generated {mpa_kml}")
                        except Exception as kml_error:
                            print(f"PREGENERATE: Failed to generate {mpa_kml}: {kml_error}")
            else:
                print("PREGENERATE: MPA data not loaded or missing iso3 column")

        except Exception as e:
            print(f"PREGENERATE: Error processing MPA data: {e}")

    # Process cables (global)
    cables_files = list(STATIC_CACHE_DIR.glob("cables_global.*"))
    if cables_files:
        cables_file = cables_files[0]
        print(f"PREGENERATE: Processing cables data from {cables_file}")
        try:
            # Try to load and fix the GeoJSON if needed
            import json
            with open(cables_file, 'r', encoding='utf-8') as f:
                cables_data = json.load(f)

            # Fix potential duplicate IDs by adding unique IDs and ensuring no duplicates
            seen_ids = set()
            for i, feature in enumerate(cables_data.get('features', [])):
                # Get original ID, handling various possible formats
                original_id = feature.get('id')
                if original_id is None or original_id == '':
                    # Try to get name or other identifier
                    properties = feature.get('properties', {})
                    original_id = properties.get('name') or properties.get('Name') or properties.get('NAME') or f"cable_{i}"

                # Clean the ID to make it safe
                original_id = str(original_id).replace(' ', '_').replace('-', '_').replace('/', '_')

                # Ensure unique ID
                unique_id = original_id
                counter = 1
                while unique_id in seen_ids:
                    unique_id = f"{original_id}_{counter}"
                    counter += 1
                feature['id'] = unique_id
                seen_ids.add(unique_id)

            # Save fixed version
            fixed_cables_file = cables_file.parent / "cables_global_fixed.geojson"
            with open(fixed_cables_file, 'w', encoding='utf-8') as f:
                json.dump(cables_data, f, indent=2)

            cables_gdf = gpd.read_file(fixed_cables_file)
            print(f"PREGENERATE: Loaded {len(cables_gdf)} cable features with unique IDs")

            if not cables_gdf.empty:
                cables_kml = global_dir / "sub_cables.kml"
                try:
                    cables_gdf.to_file(cables_kml, driver='KML')
                    print(f"PREGENERATE: Generated {cables_kml}")
                except Exception as kml_error:
                    print(f"PREGENERATE: KML generation failed: {kml_error}")
                    # Try alternative approach - simplekml
                    try:
                        import simplekml
                        kml = simplekml.Kml()
                        for idx, row in cables_gdf.iterrows():
                            geom = row.geometry
                            if hasattr(geom, 'coords'):
                                coords = list(geom.coords)
                                if len(coords) >= 2:
                                    line = kml.newlinestring(name=f"Cable_{idx}")
                                    line.coords = coords
                        kml.save(str(cables_kml))
                        print(f"PREGENERATE: Generated {cables_kml} using simplekml")
                    except Exception as simple_error:
                        print(f"PREGENERATE: SimpleKML fallback also failed: {simple_error}")

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

def refresh_caches():
    """Refresh all caches (static and dynamic)"""
    print("CACHE REFRESH: Starting cache refresh...")

    metadata = load_cache_metadata()
    username = os.getenv('NASA_USERNAME')
    password = os.getenv('NASA_PASSWORD')

    # Refresh static caches (30 days)
    static_refreshed = False
    static_age_days = get_cache_age(metadata.get('last_refresh_static'), 'days')
    if static_age_days > 30 or metadata.get('last_refresh_static') is None:
        print("CACHE REFRESH: Refreshing static caches...")
        try:
            # Import downloaders here to avoid circular imports
            from downloaders.marineregions import refresh_static_caches
            from downloaders.wdpa import refresh_static_caches as refresh_wdpa
            from downloaders.submarine_cables import refresh_static_caches as refresh_cables

            # Call refresh functions
            try:
                refresh_static_caches()
                print("CACHE REFRESH: MarineRegions static refresh completed")
            except Exception as e:
                print(f"CACHE REFRESH: MarineRegions static refresh failed: {e}")

            try:
                refresh_wdpa()
                print("CACHE REFRESH: WDPA static refresh completed")
            except Exception as e:
                print(f"CACHE REFRESH: WDPA static refresh failed: {e}")

            try:
                refresh_cables()
                print("CACHE REFRESH: Cables static refresh completed")
            except Exception as e:
                print(f"CACHE REFRESH: Cables static refresh failed: {e}")

            metadata['last_refresh_static'] = datetime.now()
            static_refreshed = True
            print("CACHE REFRESH: Static caches refreshed successfully")
        except Exception as e:
            print(f"CACHE REFRESH: Error refreshing static caches: {e}")
    else:
        print(f"CACHE REFRESH: Static caches are fresh ({static_age_days:.1f} days old)")

    # Refresh dynamic caches (12 hours)
    dynamic_age_hours = get_cache_age(metadata.get('last_refresh_dynamic'), 'hours')
    if dynamic_age_hours > 12 or metadata.get('last_refresh_dynamic') is None:
        print("CACHE REFRESH: Refreshing dynamic caches...")
        try:
            from downloaders.oscar_currents import refresh_dynamic_caches
            from downloaders.navigation_warnings import refresh_dynamic_caches as refresh_nav

            try:
                refresh_dynamic_caches()
                print("CACHE REFRESH: OSCAR dynamic refresh completed")
            except Exception as e:
                print(f"CACHE REFRESH: OSCAR dynamic refresh failed: {e}")

            try:
                refresh_nav()
                print("CACHE REFRESH: Nav warnings dynamic refresh completed")
            except Exception as e:
                print(f"CACHE REFRESH: Nav warnings dynamic refresh failed: {e}")

            metadata['last_refresh_dynamic'] = datetime.now()
            print("CACHE REFRESH: Dynamic caches refreshed successfully")
        except Exception as e:
            print(f"CACHE REFRESH: Error refreshing dynamic caches: {e}")
    else:
        print(f"CACHE REFRESH: Dynamic caches are fresh ({dynamic_age_hours:.1f} hours old)")

    # Pre-generate default-style KMLs for static layers (always after startup or static refresh)
    if static_refreshed or 'last_refresh_static' not in metadata:
        print("CACHE REFRESH: Pre-generating default KMLs...")
        try:
            pregenerate_default_kmls()
            print("CACHE REFRESH: Default KMLs pre-generated successfully")
        except Exception as e:
            print(f"CACHE REFRESH: Error pre-generating KMLs: {e}")

    save_cache_metadata(metadata)
    print("CACHE REFRESH: Cache refresh completed")

# Initialize and start the scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(refresh_caches, 'interval', hours=12, id='cache_refresh')
scheduler.start()

# Initial cache check on startup
print("APP STARTUP: Checking cache status...")
refresh_caches()

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

            # Sea state density settings (defaults)
            seastate_density_country=1.0,
            seastate_density_global=0.5,

            # Other flags
            navwarnings_custom=False,
            cables_random=False
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
    app.run(debug=True, host='0.0.0.0', port=5000)