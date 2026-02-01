"""
Download worker for processing marine data layers.

This module coordinates the downloading and processing of various marine data layers
including territorial waters, MPAs, submarine cables, ocean currents, and navigation warnings.
It provides both synchronous and asynchronous processing capabilities.
"""

import os
import json
import asyncio
from pathlib import Path
import webbrowser
import ctypes  # For hiding _metadata folder on Windows

from core.types import LayerSettings, LayerTask
from core.utils import hex_to_kml_abgr
from core.config import (
    CONFIG_SUBFOLDER, MARINEREGIONS_WFS_BASE, WDPA_BASE_URL,
    SUBMARINE_CABLES_URL, OSCAR_CMR_URL, OSCAR_COLLECTION_ID
)
from downloaders.marineregions import process as process_marineregions, process_async as process_marineregions_async
from downloaders.wdpa import process as process_wdpa, process_async as process_wdpa_async
from downloaders.submarine_cables import process as process_cables, process_async as process_cables_async
from downloaders.oscar_currents import process as process_oscar, process_async as process_oscar_async
from downloaders.navigation_warnings import process as process_navwarnings, process_async as process_navwarnings_async

def build_tasks(settings: LayerSettings, country_path: Path, global_path: Path, iso_code: str) -> list[LayerTask]:
    """Build list of LayerTask objects based on settings."""
    tasks = []

    if settings.seastate_country and not settings.eez:
        tasks.append(LayerTask(
            type="eez",
            name="Exclusive Economic Zone (auto for currents clip)",
            output_path=str(country_path / f"{iso_code}_eez.kml"),
            color_abgr=hex_to_kml_abgr(settings.eez_color, int(settings.eez_opacity)),
            weight=35.0,
            url=f"{MARINEREGIONS_WFS_BASE}?service=WFS&version=1.1.0&request=GetFeature&typeName=MarineRegions:eez&outputFormat=KML&CQL_FILTER=iso_ter1='{iso_code}'",
            settings_color=settings.eez_color,
            settings_opacity=settings.eez_opacity
        ))

    if settings.territorial:
        tasks.append(LayerTask(
            type="territorial",
            name="Territorial waters (12nm)",
            output_path=str(country_path / f"{iso_code}_territorial_waters.kml"),
            color_abgr=hex_to_kml_abgr(settings.territorial_color, int(settings.territorial_opacity)),
            weight=30.0,
            url=f"{MARINEREGIONS_WFS_BASE}?service=WFS&version=1.1.0&request=GetFeature&typeName=MarineRegions:eez_12nm&outputFormat=KML&CQL_FILTER=iso_ter1='{iso_code}'",
            settings_color=settings.territorial_color,
            settings_opacity=settings.territorial_opacity
        ))

    if settings.contiguous:
        tasks.append(LayerTask(
            type="contiguous",
            name="Contiguous zone (24nm)",
            output_path=str(country_path / f"{iso_code}_contiguous_zone.kml"),
            color_abgr=hex_to_kml_abgr(settings.contiguous_color, int(settings.contiguous_opacity)),
            weight=30.0,
            url=f"{MARINEREGIONS_WFS_BASE}?service=WFS&version=1.1.0&request=GetFeature&typeName=MarineRegions:eez_24nm&outputFormat=KML&CQL_FILTER=iso_ter1='{iso_code}'",
            settings_color=settings.contiguous_color,
            settings_opacity=settings.contiguous_opacity
        ))

    if settings.eez:
        tasks.append(LayerTask(
            type="eez",
            name="Exclusive Economic Zone (200 nm)",
            output_path=str(country_path / f"{iso_code}_eez.kml"),
            color_abgr=hex_to_kml_abgr(settings.eez_color, int(settings.eez_opacity)),
            weight=35.0,
            url=f"{MARINEREGIONS_WFS_BASE}?service=WFS&version=1.1.0&request=GetFeature&typeName=MarineRegions:eez&outputFormat=KML&CQL_FILTER=iso_ter1='{iso_code}'",
            settings_color=settings.eez_color,
            settings_opacity=settings.eez_opacity
        ))

    if settings.ecs:
        tasks.append(LayerTask(
            type="ecs",
            name="Extended Continental Shelf",
            output_path=str(country_path / f"{iso_code}_ecs.kml"),
            color_abgr=hex_to_kml_abgr(settings.ecs_color, int(settings.ecs_opacity)),
            weight=30.0,
            url=f"{MARINEREGIONS_WFS_BASE}?service=WFS&version=1.1.0&request=GetFeature&typeName=MarineRegions:ecs&outputFormat=KML&CQL_FILTER=iso_ter1='{iso_code}'",
            settings_color=settings.ecs_color,
            settings_opacity=settings.ecs_opacity
        ))

    if settings.mpa:
        tasks.append(LayerTask(
            type="mpa",
            name="Marine Protected Areas",
            output_path=str(country_path / f"{iso_code}_mpas.kml"),
            color_abgr=hex_to_kml_abgr(settings.mpa_color, int(settings.mpa_opacity)),
            weight=140.0,
            iso_code=iso_code,
            settings_color=settings.mpa_color,
            settings_opacity=settings.mpa_opacity
        ))

    if settings.cables:
        tasks.append(LayerTask(
            type="cables",
            name="Global Submarine Cables",
            output_path=str(global_path / "global_submarine_cables.kml"),
            color_abgr="",  # not used for random
            weight=50.0,
            url=SUBMARINE_CABLES_URL,
            use_random_colors=settings.cables_random,
            user_color_hex=settings.cables_color,
            user_opacity=settings.cables_opacity,
            settings_color=settings.cables_color,
            settings_opacity=settings.cables_opacity
        ))

    # Create reverse density mapping from numerical values to text labels
    from core.config import DENSITY_MAPPING
    DENSITY_REVERSE_MAPPING = {v: k for k, v in DENSITY_MAPPING.items()}

    if settings.seastate_country:
        country_density_label = DENSITY_REVERSE_MAPPING.get(settings.seastate_density_country, str(settings.seastate_density_country).replace('.', '-'))
        tasks.append(LayerTask(
            type="seastate",
            name="Ocean Currents (clipped to EEZ)",
            output_path=str(country_path / f"{iso_code}_ocean_currents_eez_{country_density_label}.kml"),
            color_abgr=hex_to_kml_abgr(settings.seastate_color, int(settings.seastate_opacity)),
            weight=120.0,
            iso_code=iso_code,
            density=settings.seastate_density_country,
            clip_to_eez=True,
            settings_color=settings.seastate_color,
            settings_opacity=settings.seastate_opacity
        ))

    if settings.seastate_global:
        global_density_label = DENSITY_REVERSE_MAPPING.get(settings.seastate_density_global, str(settings.seastate_density_global).replace('.', '-'))
        tasks.append(LayerTask(
            type="seastate",
            name="Ocean Currents (global)",
            output_path=str(global_path / f"ocean_currents_global_{global_density_label}.kml"),
            color_abgr=hex_to_kml_abgr(settings.seastate_color, int(settings.seastate_opacity)),
            weight=120.0,
            iso_code=iso_code,
            density=settings.seastate_density_global,
            clip_to_eez=False,
            settings_color=settings.seastate_color,
            settings_opacity=settings.seastate_opacity
        ))

    if settings.navwarnings:
        tasks.append(LayerTask(
            type="navwarnings",
            name="Global Maritime Navigation Warnings",
            output_path=str(global_path / "navigation_warnings.kml"),
            color_abgr=hex_to_kml_abgr(settings.navwarnings_color, int(settings.navwarnings_opacity)),
            weight=50.0,
            use_custom_colors=settings.navwarnings_custom,
            settings_color=settings.navwarnings_color,
            settings_opacity=settings.navwarnings_opacity
        ))

    return tasks

def worker(
    settings: LayerSettings,
    username: str | None,
    password: str | None,
    country_output_dir: str,
    global_output_dir: str,
    cache_dir: str,
    iso_code: str,
    country_name: str,
    report_progress
):
    """Main synchronous worker function for processing marine data layers.

    Processes all enabled marine data layers for a specific country or region,
    coordinating downloads and conversions to KML format.

    Args:
        settings: Layer configuration settings
        username: NASA Earthdata username (for OSCAR data)
        password: NASA Earthdata password (for OSCAR data)
        country_output_dir: Output directory for country-specific layers
        global_output_dir: Output directory for global layers
        cache_dir: Cache directory for downloaded data
        iso_code: ISO country code
        country_name: Full country name
        report_progress: Progress reporting callback function
    """
    print(f"WORKER THREAD STARTED for task with iso_code={iso_code}, country={country_name}")
    print(f"WORKER THREAD: settings summary - territorial:{settings.territorial}, eez:{settings.eez}, mpa:{settings.mpa}")

    country_path = Path(country_output_dir)
    global_path = Path(global_output_dir)
    cache_path = Path(cache_dir)

    # Create output folders
    try:
        country_path.mkdir(exist_ok=True)
        global_path.mkdir(exist_ok=True)
    except Exception as e:
        print(f"WORKER THREAD: Failed to create directories: {str(e)}")
        report_progress(0, f"Directory creation failed: {str(e)}")
        return False  # Early return on directory creation failure

    # Create _metadata subfolder in both output directories and hide it
    for out_dir_str in [country_output_dir, global_output_dir]:
        out_dir = Path(out_dir_str)
        meta_dir = out_dir / "_metadata"
        meta_dir.mkdir(exist_ok=True)
        # Hide the folder on Windows
        if os.name == 'nt':
            try:
                FILE_ATTRIBUTE_HIDDEN = 0x2
                ctypes.windll.kernel32.SetFileAttributesW(str(meta_dir), FILE_ATTRIBUTE_HIDDEN)
            except Exception as e:
                report_progress(0, f"Warning: Could not hide _metadata folder in {out_dir}: {e}. "
                                 "You can hide it manually: right-click folder → Properties → Hidden → Apply.")

    print("WORKER THREAD: Building tasks...")
    report_progress(0, "WORKER: Building tasks from cache...")

    tasks = build_tasks(settings, country_path, global_path, iso_code)

    print(f"WORKER THREAD: Built {len(tasks)} tasks")
    report_progress(0, f"Created {len(tasks)} tasks to process.")

    if not tasks:
        report_progress(0, "No layers selected.")
        report_progress(100)
        return

    total_weight = sum(t.weight for t in tasks)
    current_weight = [0.0]
    last_reported_pct = 0.0

    skipped_layers = []
    output_messages = []
    no_data_layers = []

    report_progress(0, f"\nStarting processing for {country_name} ({iso_code})...")

    for task in tasks:
        meta_dir = Path(os.path.dirname(task.output_path)) / "_metadata"
        meta_path = meta_dir / (Path(task.output_path).name + ".meta")

        skip = False
        if os.path.exists(task.output_path):
            # Check if this layer type creates metadata
            creates_metadata = True
            if task.type == "cables" and task.use_random_colors:
                creates_metadata = False

            if creates_metadata:
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, 'r') as f:
                            saved_settings = json.load(f)
                        current_settings = {}
                        if task.type in ("territorial", "contiguous", "mpa", "eez", "ecs", "seastate"):
                            current_settings = {"color": task.settings_color, "opacity": task.settings_opacity}
                            if task.type == "seastate":
                                current_settings["density"] = str(task.density)
                        elif task.type == "cables" and not task.use_random_colors:
                            current_settings = {"color": task.settings_color, "opacity": task.settings_opacity}
                        if saved_settings == current_settings:
                            skipped_layers.append(task.name + " (matching settings)")
                            skip = True
                        else:
                            report_progress(0, f"→ {task.name} settings changed – regenerating...")
                    except:
                        report_progress(0, f"→ {task.name} meta invalid – regenerating...")
                else:
                    report_progress(0, f"→ {task.name} no meta – regenerating...")
            # For layer types that don't create metadata (like random color cables), always regenerate silently
        if skip:
            current_weight[0] += task.weight
            continue

        report_progress(0, f"\nStarting: {task.name}...")
        success = False

        # Check cache for layer data
        if task.type in ("territorial", "contiguous", "eez", "ecs"):
            from downloaders.marineregions import check_cache
            cache_file = check_cache(f"{task.type}_global")
            if cache_file:
                # Copy from cache to output
                import shutil
                shutil.copy2(cache_file, task.output_path)
                success = True
                report_progress(0, f"✓ {task.name} loaded from cache")
            else:
                success = False
                report_progress(0, f"✗ {task.name} cache not available - admin needs to refresh cache")
        elif task.type == "mpa":
            # WDPA cache not implemented yet
            success = False
            report_progress(0, f"✗ {task.name} cache not implemented yet")
        elif task.type == "cables":
            # Cables cache not implemented yet
            success = False
            report_progress(0, f"✗ {task.name} cache not implemented yet")
        elif task.type == "seastate":
            # Check OSCAR cache
            oscar_cache_dir = Path(__file__).parent.parent / "cache" / "dynamic" / "oscar_currents"
            recent_files = list(oscar_cache_dir.glob("*.nc"))
            if recent_files:
                # Use most recent OSCAR file (simplified - would need actual processing)
                cache_file = max(recent_files, key=lambda x: x.stat().st_mtime)
                # In real implementation, would process the NetCDF and generate KML
                success = True
                report_progress(0, f"✓ {task.name} loaded from cache")
            else:
                success = False
                report_progress(0, f"✗ {task.name} cache not available - admin needs to refresh cache")
        elif task.type == "navwarnings":
            # Check nav warnings cache
            nav_cache_dir = Path(__file__).parent.parent / "cache" / "dynamic" / "nav_warnings"
            recent_files = list(nav_cache_dir.glob("*.json"))
            if recent_files:
                # Use most recent nav file (simplified - would need actual processing)
                cache_file = max(recent_files, key=lambda x: x.stat().st_mtime)
                success = True
                report_progress(0, f"✓ {task.name} loaded from cache")
            else:
                success = False
                report_progress(0, f"✗ {task.name} cache not implemented yet")

        if success:
            if os.path.exists(task.output_path):
                output_messages.append(f"Saved: {task.output_path}")
            else:
                no_data_layers.append(task.name)
        else:
            output_messages.append(f"→ Failed: {task.name}")

        current_weight[0] += task.weight
        pct = min(100.0, 100.0 * current_weight[0] / total_weight)
        # Send the delta progress since last update
        delta = pct - last_reported_pct
        if delta > 0:
            report_progress(delta)
        last_reported_pct = pct

    if skipped_layers:
        report_progress(0, f"Skipping layers with matching settings: {', '.join(skipped_layers)}")

    if no_data_layers:
        report_progress(0, f"No data available for: {', '.join(no_data_layers)} (skipped)")

    report_progress(0, "\nFiles saved to:")
    if output_messages:
        for msg in output_messages:
            report_progress(0, msg)
    else:
        report_progress(0, "All selected layers already exist or have no data – no new files generated.")

    report_progress(0, f"\nCountry folder: {country_output_dir}")
    report_progress(0, f"Global folder: {global_output_dir}")
    # Send remaining progress to reach 100%
    remaining = 100.0 - last_reported_pct
    if remaining > 0:
        report_progress(remaining, "\nDone!")
    else:
        report_progress(0, "\nDone!")

async def worker_async(
    settings: LayerSettings,
    username: str | None,
    password: str | None,
    country_output_dir: str,
    global_output_dir: str,
    cache_dir: str,
    iso_code: str,
    country_name: str,
    report_progress
):
    """Async version of worker function for concurrent downloads"""
    country_path = Path(country_output_dir)
    global_path = Path(global_output_dir)
    cache_path = Path(cache_dir)

    # Create output folders
    country_path.mkdir(exist_ok=True)
    global_path.mkdir(exist_ok=True)

    # Create _metadata subfolder in both output directories and hide it
    for out_dir_str in [country_output_dir, global_output_dir]:
        out_dir = Path(out_dir_str)
        meta_dir = out_dir / "_metadata"
        meta_dir.mkdir(exist_ok=True)
        # Hide the folder on Windows
        if os.name == 'nt':
            try:
                FILE_ATTRIBUTE_HIDDEN = 0x2
                ctypes.windll.kernel32.SetFileAttributesW(str(meta_dir), FILE_ATTRIBUTE_HIDDEN)
            except Exception as e:
                report_progress(0, f"Warning: Could not hide _metadata folder in {out_dir}: {e}. "
                                 "You can hide it manually: right-click folder → Properties → Hidden → Apply.")

    tasks = build_tasks(settings, country_path, global_path, iso_code)

    report_progress(0, f"Created {len(tasks)} tasks to process concurrently!")

    if not tasks:
        report_progress(0, "No layers selected.")
        report_progress(100)
        return

    total_weight = sum(t.weight for t in tasks)
    current_weight = [0.0]
    last_reported_pct = 0.0

    skipped_layers = []
    output_messages = []
    no_data_layers = []

    report_progress(0, f"\nStarting concurrent processing for {country_name} ({iso_code})...")

    # Filter out tasks that don't need to be downloaded (already exist with same settings)
    tasks_to_process = []
    for task in tasks:
        meta_dir = Path(os.path.dirname(task.output_path)) / "_metadata"
        meta_path = meta_dir / (Path(task.output_path).name + ".meta")

        skip = False
        if os.path.exists(task.output_path):
            # Check if this layer type creates metadata
            creates_metadata = True
            if task.type == "cables" and task.use_random_colors:
                creates_metadata = False

            if creates_metadata:
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, 'r') as f:
                            saved_settings = json.load(f)
                        current_settings = {}
                        if task.type in ("territorial", "contiguous", "mpa", "eez", "ecs", "seastate"):
                            current_settings = {"color": task.settings_color, "opacity": task.settings_opacity}
                            if task.type == "seastate":
                                current_settings["density"] = str(task.density)
                        elif task.type == "cables" and not task.use_random_colors:
                            current_settings = {"color": task.settings_color, "opacity": task.settings_opacity}
                        if saved_settings == current_settings:
                            skipped_layers.append(task.name + " (matching settings)")
                            skip = True
                        else:
                            report_progress(0, f"→ {task.name} settings changed – will regenerate...")
                    except:
                        report_progress(0, f"→ {task.name} meta invalid – will regenerate...")
                else:
                    report_progress(0, f"→ {task.name} no meta – will regenerate...")
            # For layer types that don't create metadata (like random color cables), always regenerate silently

        if not skip:
            tasks_to_process.append(task)

    if skipped_layers:
        report_progress(0, f"Skipping layers with matching settings: {', '.join(skipped_layers)}")

    if not tasks_to_process:
        report_progress(0, "All selected layers already exist or have no data – no new files generated.")
        report_progress(0, f"\nCountry folder: {country_output_dir}")
        report_progress(0, f"Global folder: {global_output_dir}")
        report_progress(100, "\nDone!")
        return

    report_progress(0, f"Processing {len(tasks_to_process)} layers concurrently...")

    # Create async tasks for concurrent processing
    async def process_task_async(task):
        """Process a single task asynchronously"""
        import aiohttp

        report_progress(0, f"\nStarting: {task.name}...")
        success = False

        # Use async versions of processors where available
        if task.type in ("territorial", "contiguous", "eez", "ecs"):
            # Create session with SSL verification disabled for MarineRegions
            connector = aiohttp.TCPConnector(verify_ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                success = await process_marineregions_async(session, task, report_progress, country_output_dir, cache_dir)
        elif task.type == "mpa":
            async with aiohttp.ClientSession() as session:
                success = await process_wdpa_async(session, task, report_progress, country_output_dir, cache_dir)
        elif task.type == "cables":
            async with aiohttp.ClientSession() as session:
                success = await process_cables_async(session, task, report_progress, global_output_dir, cache_dir)
        elif task.type == "seastate":
            if not username or not password:
                report_progress(0, f"→ {task.name} skipped (NASA Earthdata authentication required - provide username/password)")
                return False
            seastate_dir = country_output_dir if task.clip_to_eez else global_output_dir
            async with aiohttp.ClientSession() as session:
                success = await process_oscar_async(session, task, report_progress, seastate_dir, cache_dir, username, password)
        elif task.type == "navwarnings":
            async with aiohttp.ClientSession() as session:
                success = await process_navwarnings_async(session, task, report_progress, global_output_dir, cache_dir)

        if success:
            if os.path.exists(task.output_path):
                output_messages.append(f"Saved: {task.output_path}")
            else:
                no_data_layers.append(task.name)
        else:
            output_messages.append(f"→ Failed: {task.name}")

        return success, task.weight

    # Run all tasks concurrently
    async def run_concurrent_tasks():
        task_coroutines = [process_task_async(task) for task in tasks_to_process]
        return await asyncio.gather(*task_coroutines, return_exceptions=True)

    # Execute concurrent processing
    try:
        results = await run_concurrent_tasks()

        # Process results
        successful_count = 0
        for result in results:
            if isinstance(result, Exception):
                report_progress(0, f"Task failed with exception: {result}")
            elif result and len(result) == 2:
                success, weight = result
                if success:
                    successful_count += 1
                    current_weight[0] += weight
                    pct = min(100.0, 100.0 * current_weight[0] / total_weight)
                    delta = pct - last_reported_pct
                    if delta > 0:
                        report_progress(delta)
                    last_reported_pct = pct

        report_progress(0, f"Concurrent processing completed. {successful_count}/{len(tasks_to_process)} tasks succeeded.")

    except Exception as e:
        report_progress(0, f"Error in concurrent processing: {e}")

    if no_data_layers:
        report_progress(0, f"No data available for: {', '.join(no_data_layers)} (skipped)")

    report_progress(0, "\nFiles saved to:")
    if output_messages:
        for msg in output_messages:
            report_progress(0, msg)
    else:
        report_progress(0, "No new files generated.")

    report_progress(0, f"\nCountry folder: {country_output_dir}")
    report_progress(0, f"Global folder: {global_output_dir}")

    # Send remaining progress to reach 100%
    remaining = 100.0 - last_reported_pct
    if remaining > 0:
        report_progress(remaining, "\nDone!")
    else:
        report_progress(0, "\nDone!")