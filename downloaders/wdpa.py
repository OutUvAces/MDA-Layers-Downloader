"""
WDPA (World Database on Protected Areas) marine data downloader and processor.

This module handles downloading the latest WDPA marine protected areas data,
extracting and filtering marine MPAs, and converting them to KML format for
use in marine navigation applications.
"""

import os
import json
import shutil
import zipfile
import requests
from datetime import date, timedelta
import geopandas as gpd
from multiprocessing import Pool, cpu_count
import functools
from processing.simplify import simplify_geom
from core.types import LayerTask
from core.config import WDPA_BASE_URL
import xml.etree.ElementTree as ET
from pathlib import Path

async def download_and_extract_wdpa_shp_zip_async(session, cache_dir: str, task: LayerTask, report_progress) -> tuple:
    """Async version of WDPA ZIP download and extraction"""
    today = date.today()
    latest_zip_path = None
    for months_back in range(13):
        target_date = today - timedelta(days=months_back * 30)
        month_str = target_date.strftime("%b")
        year_str = str(target_date.year)
        zip_url = WDPA_BASE_URL.format(month=month_str, year=year_str)
        basename = os.path.basename(zip_url)
        zip_path = os.path.join(cache_dir, basename)

        report_progress(task.weight * 0.02, f"Checking WDPA {month_str} {year_str}...")
        try:
            async with session.head(zip_url) as response:
                if response.status == 200:
                    if os.path.exists(zip_path):
                        report_progress(0, "Using existing ZIP")
                    else:
                        report_progress(0, "Downloading latest ZIP...")
                        async with session.get(zip_url) as response:
                            response.raise_for_status()
                            with open(zip_path, 'wb') as f:
                                async for chunk in response.content.iter_chunked(8192):
                                    f.write(chunk)
                        report_progress(task.weight * 0.08)
                    latest_zip_path = zip_path
                    break  # Found latest, stop loop
                else:
                    continue
        except Exception:
            continue

    if not latest_zip_path:
        return None, None

    extract_path = os.path.join(cache_dir, "wdpa_extract")
    shutil.rmtree(extract_path, ignore_errors=True)
    os.makedirs(extract_path, exist_ok=True)

    try:
        # Extraction is CPU-bound, keep it sync
        with zipfile.ZipFile(latest_zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        report_progress(task.weight * 0.1)
        return extract_path, latest_zip_path
    except Exception as e:
        report_progress(0, f"ZIP extraction failed: {e}")
        return None, None

async def process_async(session, task: LayerTask, report_progress, output_dir: str, cache_dir: str) -> bool:
    """Async version of WDPA processing"""
    report_progress(0, f"Downloading WDPA marine shapefile...")

    try:
        extract_path, zip_path = await download_and_extract_wdpa_shp_zip_async(session, cache_dir, task, report_progress)
        if not extract_path:
            report_progress(0, f"→ Failed to download WDPA data for {task.name}")
            return False

        # Continue with the rest of processing (mostly CPU-bound operations)
        return process_wdpa_core(task, report_progress, output_dir, cache_dir, extract_path)

    except Exception as e:
        error_msg = str(e)
        if "CERTIFICATE_VERIFY_FAILED" in error_msg:
            report_progress(0, f"→ SSL certificate error for {task.name}: Server certificate validation failed.")
        elif "timeout" in error_msg.lower():
            report_progress(0, f"→ Timeout error for {task.name}: Request timed out.")
        elif "connection" in error_msg.lower():
            report_progress(0, f"→ Connection error for {task.name}: Unable to connect to server.")
        else:
            report_progress(0, f"→ Unexpected error for {task.name}: {type(e).__name__}: {repr(e)}")
        return False

def process_wdpa_core(task: LayerTask, report_progress, output_dir: str, cache_dir: str, extract_path: str) -> bool:
    """Core WDPA processing logic (shared between sync and async versions)"""
    # FORCE EXTRACT ALL ZIP FILES RECURSIVELY FIRST (always, even for cached data)
    report_progress(0, f"Force extracting all ZIP files in: {extract_path}")
    force_extracted_count = 0
    extracted_zips = set()

    # Multiple passes to handle deeply nested ZIPs
    max_passes = 5  # Prevent infinite loops
    for pass_num in range(max_passes):
        found_new_zips = False
        for root, dirs, files in os.walk(extract_path):
            for file in files:
                if file.lower().endswith('.zip'):
                    zip_path = os.path.join(root, file)
                    if zip_path in extracted_zips:
                        continue
                    try:
                        with zipfile.ZipFile(zip_path, 'r') as z:
                            bad_file = z.testzip()
                            if bad_file:
                                report_progress(0, f"Skipping corrupted ZIP: {file}")
                                continue
                            z.extractall(extract_path)
                            force_extracted_count += 1
                            extracted_zips.add(zip_path)
                            found_new_zips = True
                            report_progress(0, f"Extracted ZIP (pass {pass_num+1}): {file}")
                    except Exception as e:
                        report_progress(0, f"ZIP extraction failed for {file}: {e}")
                        continue

        if not found_new_zips:
            break  # No more ZIPs found

    if force_extracted_count > 0:
        report_progress(0, f"Force extracted {force_extracted_count} ZIP files total")

    # Look for shapefile in extract directory
    shp_path = None
    all_files = []
    for root, dirs, files in os.walk(extract_path):
        for file in files:
            all_files.append(os.path.join(root, file))

    report_progress(0, f"Found {len(all_files)} total files after extraction")

    # Look for polygons shapefile
    for file_path in all_files:
        if os.path.basename(file_path).lower().endswith('.shp') and 'polygon' in os.path.basename(file_path).lower():
            shp_path = file_path
            break

    if not shp_path:
        # Try any .shp file as fallback
        shp_files = [f for f in all_files if f.lower().endswith('.shp')]
        if shp_files:
            shp_path = shp_files[0]
            report_progress(0, f"Using fallback .shp file: {os.path.basename(shp_path)}")

    if not shp_path:
        report_progress(0, f"→ No Marine Protected Areas shapefile found for {task.name}")
        return False

    success = filter_and_convert_wdpa_shp(shp_path, task, report_progress)
    if extract_path and os.path.exists(extract_path):
        shutil.rmtree(extract_path, ignore_errors=True)

    if success:
        if os.path.exists(task.output_path):
            file_size = os.path.getsize(task.output_path)
            if file_size < 30000:
                report_progress(0, "→ No Marine Protected Areas data available for this country")
                os.remove(task.output_path)
                return True  # Don't create metadata for removed files

            # File exists and is valid size - create metadata
            meta_dir = Path(output_dir) / "_metadata"
            meta_dir.mkdir(exist_ok=True)
            kml_filename = os.path.basename(task.output_path)
            meta_path = meta_dir / (kml_filename + ".meta")
            meta_settings = {
                "color": task.settings_color,
                "opacity": task.settings_opacity
            }
            try:
                with open(meta_path, 'w', encoding='utf-8') as f:
                    json.dump(meta_settings, f, indent=2)
            except Exception as e:
                report_progress(0, f"Warning: Could not write meta file: {e}")
            return True
        else:
            # This shouldn't happen if success is True, but handle it anyway
            return True

    report_progress(0, "→ No Marine Protected Areas data available for this country")
    return False

def download_and_extract_wdpa_shp_zip(cache_dir: str, task: LayerTask, report_progress) -> tuple:
    """Download and extract the latest WDPA marine shapefile ZIP.

    Searches for the most recent WDPA marine data by trying different months
    within the last year, downloads if not cached, and extracts the ZIP.

    Args:
        cache_dir: Directory to store downloaded ZIP files
        task: Layer task configuration
        report_progress: Progress reporting function

    Returns:
        Tuple of (extract_path, zip_path) or (None, None) if failed
    """
    today = date.today()
    latest_zip_path = None
    for months_back in range(13):
        target_date = today - timedelta(days=months_back * 30)
        month_str = target_date.strftime("%b")
        year_str = str(target_date.year)
        zip_url = WDPA_BASE_URL.format(month=month_str, year=year_str)
        basename = os.path.basename(zip_url)
        zip_path = os.path.join(cache_dir, basename)

        report_progress(task.weight * 0.02, f"Checking WDPA {month_str} {year_str}... URL: {zip_url}")
        try:
            head_response = requests.head(zip_url, timeout=15)
            if head_response.status_code == 200:
                if os.path.exists(zip_path):
                    report_progress(0, "Using existing ZIP")
                else:
                    report_progress(0, "Downloading latest ZIP...")
                    response = requests.get(zip_url, stream=True, timeout=60)
                    response.raise_for_status()
                    with open(zip_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    report_progress(task.weight * 0.08)
                latest_zip_path = zip_path
                break  # Found latest, stop loop
            else:
                continue
        except Exception:
            continue

    if not latest_zip_path:
        return None, None

    extract_path = os.path.join(cache_dir, "wdpa_extract")
    shutil.rmtree(extract_path, ignore_errors=True)
    os.makedirs(extract_path, exist_ok=True)

    try:
        # Test if ZIP file is valid before extraction
        with zipfile.ZipFile(latest_zip_path, 'r') as z:
            # Check if ZIP is corrupted
            bad_file = z.testzip()
            if bad_file:
                report_progress(0, f"ZIP file corrupted, bad file: {bad_file}")
                return None, None

            z.extractall(extract_path)
        report_progress(task.weight * 0.05)

        # Look for inner ZIP files (WDPA may have multipart archives)
        inner_zips_found = 0
        for file in os.listdir(extract_path):
            if file.lower().endswith('.zip'):
                inner_zip_path = os.path.join(extract_path, file)
                try:
                    with zipfile.ZipFile(inner_zip_path, 'r') as inner_z:
                        bad_inner = inner_z.testzip()
                        if bad_inner:
                            report_progress(0, f"Inner ZIP corrupted, bad file: {bad_inner}")
                            continue
                        inner_z.extractall(extract_path)
                    report_progress(task.weight * 0.05)
                    inner_zips_found += 1
                    report_progress(0, f"Extracted inner ZIP {inner_zips_found}: {file}")
                except zipfile.BadZipFile as e:
                    report_progress(0, f"Inner ZIP extraction failed: {e}")
                    continue

        if not inner_zips_found:
            report_progress(0, "No inner marine ZIP found, checking for shapefiles directly")
            # Maybe the outer ZIP already contains the shapefile?
            shp_path = None
            for file in os.listdir(extract_path):
                if file.lower().endswith('.shp') and 'polygons' in file.lower():
                    shp_path = os.path.join(extract_path, file)
                    break
            if shp_path:
                return shp_path, extract_path

        # FORCE EXTRACT ALL ZIP FILES RECURSIVELY FIRST
        report_progress(0, f"Force extracting all ZIP files in: {extract_path}")
        force_extracted_count = 0
        extracted_zips = set()

        # Multiple passes to handle nested ZIPs
        max_passes = 5  # Prevent infinite loops
        for pass_num in range(max_passes):
            found_new_zips = False
            for root, dirs, files in os.walk(extract_path):
                for file in files:
                    if file.lower().endswith('.zip'):
                        zip_path = os.path.join(root, file)
                        if zip_path in extracted_zips:
                            continue
                        try:
                            with zipfile.ZipFile(zip_path, 'r') as z:
                                bad_file = z.testzip()
                                if bad_file:
                                    report_progress(0, f"Skipping corrupted ZIP: {file}")
                                    continue
                                z.extractall(extract_path)
                                force_extracted_count += 1
                                extracted_zips.add(zip_path)
                                found_new_zips = True
                                report_progress(0, f"Force extracted (pass {pass_num+1}): {file}")
                        except Exception as e:
                            report_progress(0, f"Force extraction failed for {file}: {e}")
                            continue

            if not found_new_zips:
                break  # No more ZIPs found

        if force_extracted_count > 0:
            report_progress(0, f"Force extracted {force_extracted_count} ZIP files total")

        # Look for shapefile after force extraction
        report_progress(0, f"Looking for shapefiles in: {extract_path}")

        # List all files for debugging first
        all_files = []
        for root, dirs, files in os.walk(extract_path):
            for file in files:
                all_files.append(os.path.join(root, file))
        report_progress(0, f"All extracted files: {len(all_files)} total")

        # Look for polygons shapefile specifically
        shp_path = None
        for file_path in all_files:
            if os.path.basename(file_path).lower().endswith('.shp') and 'polygon' in os.path.basename(file_path).lower():
                shp_path = file_path
                break

        if shp_path:
            report_progress(0, f"Found polygons shapefile: {os.path.basename(shp_path)}")
            return shp_path, extract_path
        else:
            report_progress(0, "No polygons shapefile found")
            # Check for any .shp files at all
            shp_files = [f for f in all_files if f.lower().endswith('.shp')]
            if shp_files:
                report_progress(0, f"All .shp files found: {[os.path.basename(f) for f in shp_files]}")
                # Try to use the first .shp file if no polygons file found
                first_shp = shp_files[0]
                report_progress(0, f"Attempting to use first .shp file: {os.path.basename(first_shp)}")
                return first_shp, extract_path
            else:
                report_progress(0, "No .shp files found at all")
                return None, None

    except zipfile.BadZipFile as e:
        report_progress(0, f"ZIP file is corrupted or not a valid ZIP: {e}")
        # Try to delete the corrupted file so it will be re-downloaded
        try:
            os.remove(latest_zip_path)
            report_progress(0, "Deleted corrupted ZIP file, will re-download next time")
        except:
            pass
    except Exception as e:
        report_progress(0, f"Unexpected error during extraction: {e}")
        pass

    return None, None

def filter_and_convert_wdpa_shp(shp_path: str, task: LayerTask, report_progress) -> bool:
    """Filter and convert WDPA shapefile to KML format.

    Loads the WDPA shapefile, filters marine protected areas, simplifies geometries,
    and converts to KML format with appropriate styling.

    Args:
        shp_path: Path to the input shapefile
        task: Layer task configuration with color and styling info
        report_progress: Progress reporting function

    Returns:
        True if conversion successful, False otherwise
    """
    temp_kml = task.output_path + ".temp"
    try:
        os.environ['SHAPE_RESTORE_SHX'] = 'YES'
        report_progress(5, "Reading shapefile...")

        gdf = gpd.read_file(shp_path)

        if 'ISO3' not in gdf.columns:
            return False

        filtered_gdf = gdf[gdf['ISO3'] == task.iso_code].copy()
        report_progress(task.weight * 0.1)

        if filtered_gdf.empty:
            return False

        num_mpas = len(filtered_gdf)
        total_area = filtered_gdf.geometry.area.sum()

        if num_mpas > 30 or total_area > 1.0:
            SIMPLIFY_TOL = 0.005
            report_progress(10, "Simplifying geometries...")
            num_cores = max(1, cpu_count() - 1)
            with Pool(processes=num_cores) as pool:
                filtered_gdf['geometry'] = pool.map(
                    functools.partial(simplify_geom, tol=SIMPLIFY_TOL),
                    filtered_gdf['geometry']
                )
            report_progress(task.weight * 0.25)

        filtered_gdf = filtered_gdf[['geometry']]
        report_progress(5, "Exporting to temporary KML...")
        filtered_gdf.to_file(temp_kml, driver='KML')

        # Apply style (same as process_kml but inline for MPA)
        ET.register_namespace('', 'http://www.opengis.net/kml/2.2')
        tree = ET.parse(temp_kml)
        root = tree.getroot()
        doc = root.find('kml:Document', {'kml': 'http://www.opengis.net/kml/2.2'}) or root

        for placemark in doc.findall('.//kml:Placemark', {'kml': 'http://www.opengis.net/kml/2.2'}):
            inline = placemark.find('kml:Style', {'kml': 'http://www.opengis.net/kml/2.2'})
            if inline is not None:
                placemark.remove(inline)

        style = ET.SubElement(doc, 'Style')
        style.set('id', 'customStyle')
        poly_style = ET.SubElement(style, 'PolyStyle')
        ET.SubElement(poly_style, 'fill').text = '1'
        ET.SubElement(poly_style, 'color').text = task.color_abgr
        line_style = ET.SubElement(style, 'LineStyle')
        ET.SubElement(line_style, 'width').text = '0.5'
        ET.SubElement(line_style, 'color').text = 'ff000000'

        for pm in doc.findall('.//kml:Placemark', {'kml': 'http://www.opengis.net/kml/2.2'}):
            su = pm.find('kml:styleUrl', {'kml': 'http://www.opengis.net/kml/2.2'})
            if su is None:
                su = ET.SubElement(pm, 'styleUrl')
            su.text = '#customStyle'

        tree.write(task.output_path, encoding='utf-8', xml_declaration=True)
        return True
    except Exception:
        return False
    finally:
        if os.path.exists(temp_kml):
            try:
                os.remove(temp_kml)
            except:
                pass
        os.environ.pop('SHAPE_RESTORE_SHX', None)

def process(task: LayerTask, report_progress, output_dir: str, cache_dir: str) -> bool:
    """Main entry point for WDPA layer processing.

    Downloads the latest WDPA marine data and processes it into a KML layer.

    Args:
        task: Layer task configuration
        report_progress: Progress reporting function
        output_dir: Output directory for generated files
        cache_dir: Cache directory for downloaded data

    Returns:
        True if processing successful, False otherwise
    """
    report_progress(0, "Locating latest WDPA marine shapefile...")
    extract_path, zip_path = download_and_extract_wdpa_shp_zip(cache_dir, task, report_progress)
    if extract_path:
        return process_wdpa_core(task, report_progress, output_dir, cache_dir, extract_path)
    report_progress(0, "→ No Marine Protected Areas data available for this country")
    return False