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
    """Refresh static caches - MarineRegions uses direct KML downloads, no shapefile caching needed"""
    print("MARINEREGIONS: Static caches not needed - using direct KML downloads")
    return True