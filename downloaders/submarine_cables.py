"""
Submarine cables data downloader and processor.

This module handles downloading submarine cable data from Submarine Cable Map
and converting it to KML format for visualization.
"""

import os
import json
import time
import requests
import ctypes

from processing.kml_style import process_line_kml
from core.types import LayerTask
from pathlib import Path

# aiohttp is only needed for async operations
try:
    import aiohttp
except ImportError:
    aiohttp = None

async def process_async(session, task: LayerTask, report_progress, output_dir: str, cache_dir: str) -> bool:
    """Async version of process function for concurrent downloads"""
    if aiohttp is None:
        report_progress(0, "-> Submarine cables async download failed: aiohttp not available")
        return False

    temp_geojson = os.path.join(cache_dir, "cables.geojson")
    CACHE_TTL = 30 * 24 * 3600  # 30 days

    if os.path.exists(temp_geojson) and (time.time() - os.path.getmtime(temp_geojson) < CACHE_TTL):
        report_progress(0, "Using cached global submarine cable GeoJSON...")
    else:
        report_progress(0, "Downloading global submarine cable GeoJSON...")
        try:
            async with session.get(task.url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                response.raise_for_status()
                content = await response.text()
                with open(temp_geojson, 'w', encoding='utf-8') as f:
                    f.write(content)
            report_progress(task.weight * 0.3, "Downloaded -> processing KML...")
        except Exception as e:
            report_progress(0, f"-> Submarine cables download failed: {e}")
            return False

    success = process_line_kml(
        temp_geojson,
        task.output_path,
        task.user_color_hex or "",
        task.user_opacity or "50",
        task.use_random_colors
    )
    if success:
        report_progress(task.weight * 0.2)
        if not task.use_random_colors:
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
                if os.name == 'nt':
                    try:
                        FILE_ATTRIBUTE_HIDDEN = 0x2
                        ctypes.windll.kernel32.SetFileAttributesW(str(meta_dir), FILE_ATTRIBUTE_HIDDEN)
                    except Exception as e:
                        report_progress(0, f"Warning: Could not hide _metadata folder: {e}")
            except Exception as e:
                report_progress(0, f"Warning: Could not write meta file: {e}")
        return True
    return False

def process(task: LayerTask, report_progress, output_dir: str, cache_dir: str) -> bool:
    """Process submarine cables data.

    Downloads submarine cable data from the configured URL and converts it to KML format.

    Args:
        task: Layer task configuration
        report_progress: Progress reporting function
        output_dir: Output directory for generated files
        cache_dir: Cache directory for downloaded data

    Returns:
        True if processing successful, False otherwise
    """
    temp_geojson = os.path.join(cache_dir, "cables.geojson")
    CACHE_TTL = 30 * 24 * 3600  # 30 days

    if os.path.exists(temp_geojson) and (time.time() - os.path.getmtime(temp_geojson) < CACHE_TTL):
        report_progress(0, "Using cached global submarine cable GeoJSON...")
    else:
        report_progress(0, "Downloading global submarine cable GeoJSON...")
        try:
            response = requests.get(task.url, timeout=60)
            response.raise_for_status()
            with open(temp_geojson, 'w', encoding='utf-8') as f:
                f.write(response.text)
            report_progress(task.weight * 0.3, "Downloaded -> processing KML...")
        except Exception as e:
            report_progress(0, f"-> Submarine cables download failed: {e}")
            return False

    success = process_line_kml(
        temp_geojson,
        task.output_path,
        task.user_color_hex or "",
        task.user_opacity or "50",
        task.use_random_colors
    )
    if success:
        report_progress(task.weight * 0.2)
        if not task.use_random_colors:
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
                if os.name == 'nt':
                    try:
                        FILE_ATTRIBUTE_HIDDEN = 0x2
                        ctypes.windll.kernel32.SetFileAttributesW(str(meta_dir), FILE_ATTRIBUTE_HIDDEN)
                    except Exception as e:
                        report_progress(0, f"Warning: Could not hide _metadata folder: {e}")
            except Exception as e:
                report_progress(0, f"Warning: Could not write meta file: {e}")
        return True
    return False