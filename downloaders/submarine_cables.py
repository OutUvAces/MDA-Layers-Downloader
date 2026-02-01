"""
Submarine cables data downloader and processor.

This module handles downloading submarine cable data from public sources.
"""

import os
import json
import requests
from pathlib import Path

def refresh_static_caches():
    """Refresh submarine cables static cache"""
    print("CABLES: Refreshing static cache...")

    try:
        # Create cache directory if it doesn't exist
        cache_dir = Path(__file__).parent.parent / "cache" / "static"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Download submarine cable data from the known working source
        cables_url = "https://raw.githubusercontent.com/telegeography/www.submarinecablemap.com/master/public/cable-geo.json"
        cache_file = cache_dir / "cables_global.geojson"

        print(f"CABLES: Downloading submarine cable data from {cables_url}")
        try:
            response = requests.get(cables_url, timeout=60, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()

            # Validate that we got JSON data
            data = response.json()

            if isinstance(data, dict) and 'features' in data:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)

                print(f"CABLES: Downloaded submarine cable data, size = {cache_file.stat().st_size} bytes")
            else:
                print("CABLES: Invalid GeoJSON structure received")
                return False

        except requests.RequestException as e:
            print(f"CABLES: Network error downloading cables: {e}")
            return False
        except json.JSONDecodeError as e:
            print(f"CABLES: Invalid JSON response: {e}")
            return False
        except Exception as e:
            print(f"CABLES: Unexpected error downloading cables: {e}")
            return False

        # If download succeeded, continue with success
        print("CABLES: Static cache refreshed successfully")
        return True
    except Exception as e:
        print(f"CABLES: Static cache refresh failed: {e}")
        return False

def process(task, report_progress, output_dir: str, cache_dir: str) -> bool:
    """Process submarine cables layer data (placeholder).

    Args:
        task: Layer task configuration
        report_progress: Progress reporting function
        output_dir: Output directory for generated files
        cache_dir: Cache directory for downloaded data

    Returns:
        True if processing successful, False otherwise
    """
    print("Submarine cables: process called (placeholder implementation)")

    # Check cache first
    from downloaders.marineregions import check_cache
    cached_file = check_cache("cables_global")
    if cached_file:
        report_progress(0, f"✓ {task.name} loaded from cache")
        # Copy from cache to output
        import shutil
        shutil.copy2(cached_file, task.output_path)
        return True
    else:
        report_progress(0, f"✗ {task.name} cache not available - admin needs to refresh cache")
        return False

async def process_async(session, task, report_progress, output_dir: str, cache_dir: str) -> bool:
    """Async version of process function for submarine cables (placeholder).

    Args:
        session: aiohttp session
        task: Layer task configuration
        report_progress: Progress reporting function
        output_dir: Output directory for generated files
        cache_dir: Cache directory for downloaded data

    Returns:
        True if processing successful, False otherwise
    """
    print("Submarine cables: process_async called (placeholder implementation)")

    # For now, just call the sync version
    import asyncio
    return await asyncio.get_event_loop().run_in_executor(None, process, task, report_progress, output_dir, cache_dir)