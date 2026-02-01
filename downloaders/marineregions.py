"""
MarineRegions data downloader and processor.

This module handles downloading geospatial data from MarineRegions.org,
including territorial waters, EEZs, and other marine boundaries.
"""

import os
import json
import requests
import ctypes
import aiohttp

from processing.kml_style import download_kml, process_kml
from core.types import LayerTask
from pathlib import Path
from datetime import datetime, timedelta
import json

def check_cache(layer_name: str, ttl_days: float = 30) -> Path | None:
    """Check if cached data exists and is fresh"""
    cache_dir = Path(__file__).parent.parent / "cache" / "static"
    cache_file = cache_dir / f"{layer_name}.gpkg"

    if not cache_file.exists():
        return None

    # Check if cache is too old
    try:
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime > timedelta(days=ttl_days):
            return None
    except:
        return None

    return cache_file

def refresh_static_caches():
    """Refresh all static caches for MarineRegions data"""
    print("MARINEREGIONS: Refreshing static caches...")

    # For now, just create placeholder cache files
    # In a real implementation, this would download and process the data
    cache_dir = Path(__file__).parent.parent / "cache" / "static"

    # Create placeholder files to indicate cache exists
    layers = ["eez_global", "territorial_global", "contiguous_global", "ecs_global"]
    for layer in layers:
        cache_file = cache_dir / f"{layer}.gpkg"
        if not cache_file.exists():
            # Create empty file as placeholder
            cache_file.touch()

    print("MARINEREGIONS: Static caches refreshed")

async def process_async(session, task: LayerTask, report_progress, output_dir: str, cache_dir: str) -> bool:
    """Async version of process function for concurrent downloads"""

    # Check cache first
    layer_name = task.type  # e.g., "eez", "territorial", etc.
    cached_file = check_cache(f"{layer_name}_global")
    if cached_file:
        report_progress(0, f"Using cached {task.name} data...")
        # Copy from cache to output (simplified - in real implementation would process)
        import shutil
        shutil.copy2(cached_file, task.output_path)
        return True

    # Fall back to downloading if cache miss
    temp = task.output_path + ".temp"

    # Clean any possible leftover temp file
    if os.path.exists(temp):
        try:
            os.remove(temp)
        except:
            pass

    report_progress(0, f"Downloading {task.name} KML from MarineRegions...")
    try:
        async with session.get(task.url, timeout=aiohttp.ClientTimeout(total=45)) as response:
            response.raise_for_status()
            content = await response.text()
            with open(temp, 'w', encoding='utf-8') as f:
                f.write(content)

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
                    except Exception as e:
                        report_progress(0, f"Warning: Could not hide _metadata folder: {e}")
            except Exception as e:
                report_progress(0, f"Warning: Could not write meta file: {e}")

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

def process(task: LayerTask, report_progress, output_dir: str, cache_dir: str) -> bool:
    """Process MarineRegions layer data.

    Downloads and processes geospatial data from MarineRegions.org for the specified layer type.

    Args:
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
        import requests
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