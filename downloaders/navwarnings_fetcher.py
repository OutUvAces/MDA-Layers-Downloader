"""
Navigation Warnings Data Fetcher
Handles downloading and processing of navigation warning data from various sources.
"""

import os
import json
import requests
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.config import NGA_MSI_NAVWARNINGS_URL
from .navwarnings_parser import parse_daily_memorandum


def load_url_cache(cache_dir=None) -> list:
    """Load cached URL list"""
    if cache_dir is None:
        cache_dir = "_cache"

    cache_file = os.path.join(cache_dir, "nga_memo_urls.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_url_cache(urls: list, cache_dir=None):
    """Save URL list to cache"""
    if cache_dir is None:
        cache_dir = "_cache"

    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, "nga_memo_urls.json")

    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(urls, f, indent=2)
    except Exception:
        pass


def validate_urls(urls: list) -> list:
    """Test URLs and return only the working ones"""
    working_urls = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    for url in urls:
        try:
            response = requests.head(url, headers=headers, timeout=10)  # HEAD request is faster
            if response.status_code == 200:
                # Do a quick content check with GET
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200 and len(response.text) > 1000:  # Reasonable content size
                    working_urls.append(url)
        except Exception as e:
            continue
            continue

    return working_urls


def discover_urls_from_website() -> list:
    """Attempt to discover current memorandum URLs using algorithmic key testing (no web scraping)"""

    # The URLs follow a predictable pattern:
    # https://msi.nga.mil/api/publications/download?key={KEY}/SFH00000/DailyMem{AREA}.txt&type=view

    # Try variations of the key in case it changes
    potential_keys = [
        "16694640",  # Current known key
        "16694641", "16694642", "16694643",  # Nearby variations
        "16694630", "16694650",  # Range variations
    ]

    areas = [
        ('IV', 'NAVAREA IV'),
        ('XII', 'NAVAREA XII'),
        ('LAN', 'HYDROLANT'),
        ('PAC', 'HYDROPAC'),
        ('ARC', 'HYDROARC')
    ]

    discovered_urls = []

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    # Test each key variation
    for key in potential_keys:
        key_urls = []
        for area_code, area_name in areas:
            url = f"https://msi.nga.mil/api/publications/download?key={key}/SFH00000/DailyMem{area_code}.txt&type=view"

            try:
                # Test with HEAD request (faster than GET)
                response = requests.head(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    key_urls.append(url)
            except Exception:
                continue

        # If we found all 5 areas with this key, use it
        if len(key_urls) == 5:
            return key_urls

        # If we found at least 3, keep them as candidates
        if len(key_urls) >= 3:
            discovered_urls.extend(key_urls)

    # Return any working URLs we found, even if not complete set
    if discovered_urls:
        unique_urls = list(set(discovered_urls))  # Remove duplicates
        return unique_urls
    return []


def discover_current_memo_urls(cache_dir=None) -> list:
    """Get the five standard NGA MSI memorandum URLs for all areas with fallback discovery

    This function provides robust URL discovery for exe packaging compatibility:
    1. Try cached URLs (if available)
    2. Fall back to hardcoded defaults (always available in exe)
    3. If defaults fail, attempt dynamic discovery from NGA website
    4. Validate all URLs work before returning
    5. Cache working URLs for future use

    This ensures the application works for new users without cached data."""
    if cache_dir is None:
        cache_dir = "_cache"

    # Try to load from cache first
    cached_urls = load_url_cache(cache_dir)
    if cached_urls and len(cached_urls) >= 3:  # Accept 3+ working URLs
        # Validate cached URLs still work
        working_urls = validate_urls(cached_urls)
        if len(working_urls) >= 3:
            return working_urls

    # Try hardcoded default URLs
    default_urls = [
        "https://msi.nga.mil/api/publications/download?key=16694640/SFH00000/DailyMemIV.txt&type=view",    # NAVAREA IV
        "https://msi.nga.mil/api/publications/download?key=16694640/SFH00000/DailyMemXII.txt&type=view",  # NAVAREA XII
        "https://msi.nga.mil/api/publications/download?key=16694640/SFH00000/DailyMemLAN.txt&type=view",  # HYDROLANT
        "https://msi.nga.mil/api/publications/download?key=16694640/SFH00000/DailyMemPAC.txt&type=view",  # HYDROPAC
        "https://msi.nga.mil/api/publications/download?key=16694640/SFH00000/DailyMemARC.txt&type=view"   # HYDROARC
    ]

    working_defaults = validate_urls(default_urls)
    if len(working_defaults) >= 3:
        save_url_cache(working_defaults, cache_dir)
        return working_defaults

    # If defaults fail, try algorithmic URL discovery
    discovered_urls = discover_urls_from_website()

    if discovered_urls and len(discovered_urls) >= 3:
        working_discovered = validate_urls(discovered_urls)
        if len(working_discovered) >= 3:
            save_url_cache(working_discovered, cache_dir)
            return working_discovered

    # Final fallback - return any working URLs we found
    all_candidates = list(set(cached_urls + default_urls + discovered_urls))
    final_working = validate_urls(all_candidates)

    if final_working:
        save_url_cache(final_working, cache_dir)
        return final_working

    # Complete failure
    return []
    return []


def validate_memo_content(content: str, memo_name: str) -> bool:
    """Validate that memorandum content is reasonable"""
    if not content or len(content.strip()) < 100:
        return False

    # Check for common error patterns
    if "404 Not Found" in content or "File not found" in content:
        return False

    # Check that it contains expected NAVAREA content
    content_upper = content.upper()
    if "NAVAREA" in memo_name.upper() and "NAVAREA" not in content_upper:
        return False
    if "HYDRO" in memo_name.upper() and not any(x in content_upper for x in ["HYDRO", "WARNING", "NAVWARN"]):
        return False

    return True


def _download_single_memorandum(url: str) -> tuple:
    """Download a single memorandum and return (memo_name, content) or (None, None) on failure"""
    try:
        # Extract memo name from URL
        if 'DailyMemIV' in url:
            memo_name = "NAVAREA IV (US Atlantic)"
        elif 'DailyMemXII' in url:
            memo_name = "NAVAREA XII (US Pacific)"
        elif 'DailyMemLAN' in url:
            memo_name = "HYDROLANT (Atlantic)"
        elif 'DailyMemPAC' in url:
            memo_name = "HYDROPAC (Indo-Pacific)"
        elif 'DailyMemARC' in url:
            memo_name = "HYDROARC (Arctic)"
        else:
            return None, None

        # Always download fresh content (no caching for safety-critical navigation warnings)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        content = response.text

        if validate_memo_content(content, memo_name):
            return memo_name, content
        else:
            return None, None

    except Exception as e:
        return None, None


def scrape_daily_memorandums_from_page(cache_dir=None) -> dict:
    """Scrape daily memorandums from NGA MSI page using concurrent downloads"""
    if cache_dir is None:
        cache_dir = "_cache"

    urls = discover_current_memo_urls(cache_dir)
    memorandums = {}

    # If no URLs discovered, cannot proceed (no fallback to cached data for safety)
    if not urls:
        return memorandums

    # Download all memorandums concurrently for maximum speed
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all download tasks
        future_to_url = {executor.submit(_download_single_memorandum, url): url for url in urls}

        # Collect results as they complete
        for future in as_completed(future_to_url):
            memo_name, content = future.result()
            if memo_name and content:
                memorandums[memo_name] = content

    return memorandums


def scrape_daily_memorandums_sequential(cache_dir=None) -> dict:
    """Scrape daily memorandums from NGA MSI page using sequential downloads (fallback)"""
    if cache_dir is None:
        cache_dir = "_cache"

    urls = discover_current_memo_urls(cache_dir)
    memorandums = {}

    # If no URLs discovered, cannot proceed
    if not urls:
        return memorandums

    # Download memorandums sequentially (one by one)
    for url in urls:
        memo_name, content = _download_single_memorandum(url)
        if memo_name and content:
            memorandums[memo_name] = content

    return memorandums


def try_direct_api_calls() -> dict:
    """Try to get warnings directly from NGA MSI API"""
    warnings = {}

    try:
        # Try different endpoints
        endpoints_to_try = [
            (NGA_MSI_NAVWARNINGS_URL, {'output': 'json'}),
            ("https://msi.nga.mil/api/publications/current-warnings", {'output': 'json'}),
        ]

        for url, params in endpoints_to_try:
            try:
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()

                data = response.json()
                if 'broadcast-warn' in data and data['broadcast-warn']:
                    warnings = data['broadcast-warn']
                    break
                elif 'warnings' in data and data['warnings']:
                    warnings = data['warnings']
                    break
                elif isinstance(data, list) and data:
                    warnings = data
                    break
            except Exception as e:
                continue
                continue

    except Exception:
        pass

    return warnings


def get_curated_current_warnings(cache_dir=None, report_progress=None) -> dict:
    """Get current warnings using memorandum scraping with API fallback"""
    all_warnings = []

    if cache_dir is None:
        cache_dir = "_cache"

    # For now, focus on enhanced memorandum scraping which provides good coverage
    # Browser automation proved complex due to NGA's JavaScript-heavy interface
    # TODO: Implement browser automation in future if detailed coordinates become critical

    # Primary method: concurrent memorandum scraping
    if report_progress:
        report_progress(0, "Retrieving navigation warnings from all five NGA MSI areas via concurrent memorandum scraping")
    memo_warnings = scrape_daily_memorandums_from_page(cache_dir)

    if not memo_warnings:
        # Fallback 1: Try sequential memorandum downloads if concurrent failed
        if report_progress:
            report_progress(0, "Concurrent downloads failed, trying sequential memorandum downloads")
        memo_warnings = scrape_daily_memorandums_sequential(cache_dir)

    if memo_warnings:
        if report_progress:
            report_progress(0, f"Found memorandums for {len(memo_warnings)} areas")

        # Parse warnings from each memorandum (all five areas)
        for memo_name, content in memo_warnings.items():
            parsed_warnings = parse_daily_memorandum(content, "", memo_name)
            all_warnings.extend(parsed_warnings)
            if report_progress:
                report_progress(0, f"Processed {len(parsed_warnings)} warnings from {memo_name}")

        # Verify we got data from all expected areas
        areas_found = set()
        for warning in all_warnings:
            if isinstance(warning, dict):
                navarea = warning.get('navarea', '').upper()
                if navarea:
                    areas_found.add(navarea)

        expected_areas = {'NAVAREA IV', 'NAVAREA XII', 'HYDROLANT', 'HYDROPAC', 'HYDROARC'}
        if report_progress:
            report_progress(0, f"Areas covered: {sorted(areas_found)}")

        if len(areas_found) >= 5:
            if report_progress:
                report_progress(0, "All five NGA MSI areas successfully retrieved")
        else:
            missing = expected_areas - areas_found
            if report_progress:
                report_progress(0, f"WARNING: Missing areas: {sorted(missing)}")
    else:
        # Final fallback: Try direct API calls if all memorandum methods fail
        if report_progress:
            report_progress(0, "All memorandum scraping methods failed, trying direct API calls as final fallback")
        api_warnings = try_direct_api_calls()
        if api_warnings:
            all_warnings = api_warnings
            if report_progress:
                report_progress(0, f"Retrieved {len(all_warnings)} warnings via API fallback")
        else:
            if report_progress:
                report_progress(0, "ERROR: All data sources failed - no navigation warnings retrieved")

    if report_progress:
        if memo_warnings:
            report_progress(0, f"Total warnings: {len(all_warnings)} from {len(memo_warnings)} areas")
        else:
            report_progress(0, f"Total warnings: {len(all_warnings)} from API fallback")
    return all_warnings