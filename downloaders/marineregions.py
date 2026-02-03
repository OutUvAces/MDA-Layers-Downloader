"""
MarineRegions data downloader and processor.

This module handles downloading geospatial data from MarineRegions.org,
including territorial waters, EEZs, and other marine boundaries.
"""

import os
import json
import ctypes
import aiohttp

from processing.kml_style import process_kml
from core.types import LayerTask
from pathlib import Path

def process(task: LayerTask, report_progress, output_dir: str, cache_dir: str) -> bool:
    """Synchronous version of process function"""
    # For now, just call the async version synchronously
    # In a real implementation, this would be a synchronous version
    import asyncio

    async def run_async():
        async with aiohttp.ClientSession() as session:
            return await process_async(session, task, report_progress, output_dir, cache_dir)

    try:
        return asyncio.run(run_async())
    except Exception as e:
        report_progress(0, f"→ Error in synchronous process: {e}")
        return False

async def process_async(session, task: LayerTask, report_progress, output_dir: str, cache_dir: str) -> bool:
    """
    Async version of process function for concurrent downloads.

    Downloads and processes geospatial data from MarineRegions.org for the specified layer type.

    Args:
        session: aiohttp ClientSession for making requests
        task: Layer task configuration
        report_progress: Progress reporting function
        output_dir: Output directory for generated files
        cache_dir: Cache directory for downloaded data

    Returns:
        True if processing successful, False otherwise
    """
    temp = task.output_path + ".temp"

    # Clean any possible leftover temp file
    if os.path.exists(temp):
        try:
            os.remove(temp)
        except:
            pass

    report_progress(0, f"Downloading {task.name} KML from MarineRegions...")
    try:
        # Force disable SSL verification for MarineRegions
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Try direct download with SSL disabled
        response = requests.get(task.url, timeout=45, verify=False)
        response.raise_for_status()
        with open(temp, 'w', encoding='utf-8') as f:
            f.write(response.text)

        report_progress(task.weight * 0.35, "Downloaded → applying custom style...")

        if process_kml(temp, task.output_path, task.color_abgr):
            report_progress(task.weight * 0.65)

            if os.path.exists(task.output_path) and os.path.getsize(task.output_path) < 30000:
                report_progress(0, f"→ No data available for {task.name} (skipped)")
                try:
                    os.remove(task.output_path)
                    meta_dir = Path(output_dir) / "_metadata"
                    meta_path = meta_dir / (Path(task.output_path).name + ".meta")
                    if meta_path.exists():
                        meta_path.unlink()
                except:
                    pass
                return True

            # Write metadata to hidden subfolder
            meta_dir = Path(output_dir) / "_metadata"
            meta_dir.mkdir(exist_ok=True)
            # Use the same logic as the worker for consistency
            kml_filename = os.path.basename(task.output_path)
            meta_path = meta_dir / (kml_filename + ".meta")
            meta_settings = {
                "color": task.settings_color,
                "opacity": task.settings_opacity
            }
            try:
                with open(meta_path, 'w', encoding='utf-8') as f:
                    json.dump(meta_settings, f, indent=2)
                # Hide the folder (run once per folder is enough)
                if os.name == 'nt':
                    try:
                        FILE_ATTRIBUTE_HIDDEN = 0x2
                        ctypes.windll.kernel32.SetFileAttributesW(str(meta_dir), FILE_ATTRIBUTE_HIDDEN)
                    except Exception as hide_err:
                        report_progress(0, f"Warning: Could not hide _metadata folder: {hide_err}")
            except Exception as meta_err:
                report_progress(0, f"Warning: Could not write meta file: {meta_err}")
                # Try to write to a temp file for debugging
                try:
                    temp_meta_path = Path(output_dir) / (kml_filename + ".meta")
                    with open(temp_meta_path, 'w', encoding='utf-8') as f:
                        json.dump(meta_settings, f, indent=2)
                    report_progress(0, f"Temporary metadata written to {temp_meta_path}")
                except:
                    pass

            return True
        else:
            report_progress(0, f"→ Failed to apply style for {task.name}")
            return False

    except Exception as e:
        error_msg = str(e)
        if "CERTIFICATE_VERIFY_FAILED" in error_msg:
            report_progress(0, f"→ SSL certificate error for {task.name}: Server certificate validation failed. This may be a temporary server issue.")
        elif "timeout" in error_msg.lower():
            report_progress(0, f"→ Timeout error for {task.name}: Request timed out. Try again later.")
        elif "connection" in error_msg.lower():
            report_progress(0, f"→ Connection error for {task.name}: Unable to connect to server. Check internet connection.")
        else:
            report_progress(0, f"→ Unexpected error for {task.name}: {type(e).__name__}: {repr(e)}")
        return False

    finally:
        if os.path.exists(temp):
            try:
                os.remove(temp)
            except:
                pass

def refresh_static_caches():
    """Refresh all static caches for MarineRegions data using separate shapefile downloads (matching desktop)"""
    print("MARINEREGIONS: Refreshing static caches...")

    try:
        cache_dir = Path(__file__).parent.parent / "cache" / "raw_source_data" / "static" / "marineregions"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Force disable SSL verification for MarineRegions (as in desktop)
        import urllib3
        import requests
        import zipfile
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Define the MarineRegions layers to download using GeoServer WFS (working URLs)
        layers = {
            'eez': {
                'url': "https://geo.vliz.be/geoserver/MarineRegions/wfs?service=WFS&version=1.0.0&request=GetFeature&typeName=eez&outputFormat=SHAPE-ZIP",
                'zip_name': "eez.zip",
                'description': "Exclusive Economic Zones"
            },
            'territorial_seas': {
                'url': "https://geo.vliz.be/geoserver/MarineRegions/wfs?service=WFS&version=1.0.0&request=GetFeature&typeName=eez_12nm&outputFormat=SHAPE-ZIP",
                'zip_name': "territorial_seas.zip",
                'description': "Territorial Seas"
            },
            'contiguous_zones': {
                'url': "https://geo.vliz.be/geoserver/MarineRegions/wfs?service=WFS&version=1.0.0&request=GetFeature&typeName=eez_24nm&outputFormat=SHAPE-ZIP",
                'zip_name': "contiguous_zones.zip",
                'description': "Contiguous Zones"
            },
            'ecs': {
                'url': "https://geo.vliz.be/geoserver/MarineRegions/wfs?service=WFS&version=1.0.0&request=GetFeature&typeName=ecs&outputFormat=SHAPE-ZIP",
                'zip_name': "ecs.zip",
                'description': "Extended Continental Shelf"
            }
        }

        success_count = 0

        for layer_key, layer_info in layers.items():
            try:
                print(f"MARINEREGIONS: Processing {layer_info['description']}...")
                zip_path = cache_dir / layer_info['zip_name']

                # Check if shapefiles already exist for this layer
                expected_shp = None
                if layer_key == 'eez':
                    expected_shp = cache_dir / "eez.shp"
                elif layer_key == 'territorial_seas':
                    expected_shp = cache_dir / "territorial_seas.shp"
                elif layer_key == 'contiguous_zones':
                    expected_shp = cache_dir / "contiguous_zones.shp"
                elif layer_key == 'ecs':
                    expected_shp = cache_dir / "ecs.shp"

                if expected_shp and expected_shp.exists():
                    print(f"MARINEREGIONS: {layer_info['description']} shapefiles already extracted")
                    success_count += 1
                    continue

                # Download if ZIP doesn't exist
                if not zip_path.exists():
                    print(f"MARINEREGIONS: Downloading {layer_info['description']}...")
                    # Add browser headers to mimic real browser request
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': '*/*',
                        'Referer': 'https://www.marineregions.org/',
                    }

                    try:
                        print(f"MARINEREGIONS: Starting download request for {layer_info['description']}...")
                        # Use shorter timeout and add connection timeout
                        response = requests.get(layer_info['url'], timeout=(10, 30), verify=False, headers=headers, stream=True)
                        print(f"MARINEREGIONS: Got response for {layer_info['description']}, status: {response.status_code}")
                        response.raise_for_status()

                        # Get total size for progress feedback
                        total_size = int(response.headers.get('Content-Length', 0))

                        # Download content in chunks with progress feedback
                        print(f"MARINEREGIONS: Downloading content for {layer_info['description']}...")
                        try:
                            from tqdm import tqdm
                            with open(zip_path, 'wb') as f, tqdm(
                                desc=f"Downloading {layer_info['description']}",
                                total=total_size,
                                unit='B',
                                unit_scale=True,
                                ncols=80
                            ) as pbar:
                                downloaded_size = 0
                                for chunk in response.iter_content(chunk_size=8192):
                                    if chunk:
                                        f.write(chunk)
                                        downloaded_size += len(chunk)
                                        pbar.update(len(chunk))
                        except ImportError:
                            # Fallback without progress bar if tqdm not available
                            print(f"MARINEREGIONS: Downloading {layer_info['description']} without progress (install tqdm for progress bars)...")
                            with open(zip_path, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    if chunk:
                                        f.write(chunk)

                        response.close()

                        # Validate download
                        if not zip_path.exists() or zip_path.stat().st_size == 0:
                            print(f"MARINEREGIONS: ERROR - Downloaded file is empty")
                            print(f"MARINEREGIONS: Skipping {layer_info['description']} - no data downloaded")
                            if zip_path.exists():
                                zip_path.unlink()
                            continue

                        # Validate that we actually downloaded a ZIP file
                        with open(zip_path, 'rb') as f:
                            header = f.read(20)
                            if not header.startswith(b'PK\x03\x04'):
                                print(f"MARINEREGIONS: ERROR - Downloaded file is not a ZIP (starts with {header})")
                                print(f"MARINEREGIONS: Skipping {layer_info['description']} - no shapefile data available")
                                zip_path.unlink()
                                continue

                        print(f"MARINEREGIONS: Downloaded {layer_info['description']}, size = {zip_path.stat().st_size:,} bytes")

                    except requests.exceptions.Timeout:
                        print(f"MARINEREGIONS: Timeout downloading {layer_info['description']} - server not responding within 30s")
                        print(f"MARINEREGIONS: Skipping {layer_info['description']} - will use cached data if available")
                        continue
                    except requests.exceptions.ConnectionError as ce:
                        print(f"MARINEREGIONS: Connection error downloading {layer_info['description']}: {ce}")
                        print(f"MARINEREGIONS: Skipping {layer_info['description']} - network connectivity issue")
                        continue
                    except requests.exceptions.RequestException as re:
                        print(f"MARINEREGIONS: Request error downloading {layer_info['description']}: {re}")
                        print(f"MARINEREGIONS: Skipping {layer_info['description']} - HTTP error")
                        continue
                    except Exception as e:
                        print(f"MARINEREGIONS: Unexpected error downloading {layer_info['description']}: {e}")
                        print(f"MARINEREGIONS: Skipping {layer_info['description']} - unexpected error")
                        continue

                # Extract the ZIP file (always try to extract if shapefiles don't exist)
                if not (expected_shp and expected_shp.exists()):
                    print(f"MARINEREGIONS: Extracting {layer_info['description']}...")
                    try:
                        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                            zip_ref.extractall(cache_dir)
                        print(f"MARINEREGIONS: {layer_info['description']} extracted")
                    except zipfile.BadZipFile as zip_error:
                        print(f"MARINEREGIONS: ERROR - Downloaded file is not a valid ZIP: {zip_error}")
                        print(f"MARINEREGIONS: Deleting invalid file: {zip_path}")
                        if zip_path.exists():
                            zip_path.unlink()
                        continue
                else:
                    print(f"MARINEREGIONS: {layer_info['description']} ZIP already downloaded and extracted")

                success_count += 1

            except Exception as layer_error:
                print(f"MARINEREGIONS: Failed to download/extract {layer_info['description']}: {layer_error}")
                continue

        if success_count > 0:
            print(f"MARINEREGIONS: Static caches refreshed - {success_count}/{len(layers)} layers successful")
            return True
        else:
            print("MARINEREGIONS: No layers were successfully downloaded")
            return False

    except Exception as e:
        print(f"MARINEREGIONS: Static cache refresh failed: {e}")
        return False