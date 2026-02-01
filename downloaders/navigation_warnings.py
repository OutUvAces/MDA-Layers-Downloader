"""
Navigation Warnings Downloader (Refactored)
Main entry point for navigation warnings processing.
"""

import os
import re
import math
import json
import requests
import xml.etree.ElementTree as ET
import ctypes
from datetime import datetime
from pathlib import Path

from core.types import LayerTask

from .navwarnings_fetcher import get_curated_current_warnings
from .navwarnings_parser import (
    extract_coordinates_from_text, create_warning_description,
    extract_navarea_from_memo_name, extract_coordinates_from_api_geometry,
    create_circle_approximation
)
from core.utils import hex_to_kml_abgr

def extract_warning_components(warning_text: str) -> tuple[str, list[str], str]:
    """
    Extract the components of a maritime warning: prefix, feature list, and suffix.

    Uses existing regex algorithms to identify feature boundaries and intelligently
    determine whether post-coordinate text should be preserved or treated as formatting.

    Args:
        warning_text: The complete warning text

    Returns:
        Tuple of (prefix, feature_list, suffix) where:
        - prefix: Header text before first feature
        - feature_list: List of cleaned individual feature texts
        - suffix: Footer text after last feature
    """
    import re

    # Step 1: Use feature start regex to find all feature start positions
    # Process line by line like the original coordinate extraction for safety
    feature_starts = []
    lines = warning_text.split('\n')

    for line_idx, line in enumerate(lines):
        line_stripped = line.strip()
        # Use the same regex pattern as the original coordinate extraction
        section_match = re.match(r'^([A-Z]+)\.\s+(.+)?$', line_stripped)
        if section_match:
            # Calculate the position in the original text
            # Find where this line starts in the full text
            if line_idx == 0:
                line_start_pos = 0
            else:
                # Count the positions of previous lines + their newlines
                line_start_pos = sum(len(lines[i]) + 1 for i in range(line_idx))  # +1 for \n

            feature_starts.append(line_start_pos)

    if not feature_starts:
        # No features found, treat entire text as prefix
        return warning_text.strip(), [], ""

    # Step 2: Create raw text spans for every feature using start positions
    raw_feature_texts = []
    for i, start_pos in enumerate(feature_starts):
        # Begin at feature start
        # End at next feature start (or end of text)
        end_pos = feature_starts[i + 1] if i + 1 < len(feature_starts) else len(warning_text)
        raw_text = warning_text[start_pos:end_pos].rstrip()
        raw_feature_texts.append(raw_text)

    # Step 3: Determine whether to apply coordinate-based cleaning
    apply_cleaning = False
    trailing_texts = []

    # Look only at non-last features
    for raw_text in raw_feature_texts[:-1]:  # Exclude last feature
        # Find coordinates in this feature
        coord_matches = list(re.finditer(r'\b\d{2,3}-\d{2}\.\d{1,2}[EW]\b', raw_text))

        if coord_matches:
            # Get trailing text after last coordinate
            last_coord_end = coord_matches[-1].end()
            trailing_text = raw_text[last_coord_end:].strip()
            trailing_texts.append(trailing_text)
        else:
            # No coordinates, can't determine trailing text reliably
            trailing_texts.append(None)

    # Step 3: Infer the dynamic separation pattern from inter-feature gaps
    # Collect preceding snippets before each non-first feature
    preceding_snippets = []
    safe_lookback = 50  # Look back enough to capture feature endings (e.g., "METERS.\n")

    for i in range(1, len(feature_starts)):  # Skip first feature (no preceding text)
        current_start = feature_starts[i]

        # Go back from current feature start to capture the ending pattern of previous feature
        snippet_start = max(0, current_start - safe_lookback)

        # Collect text from snippet_start to current_start (exclusive)
        snippet = warning_text[snippet_start:current_start]
        preceding_snippets.append(snippet)

    # Find longest common suffix across preceding snippets
    if preceding_snippets:
        # Reverse each snippet to find common suffix via common prefix
        reversed_snippets = [s[::-1] for s in preceding_snippets]

        # Find longest common prefix of reversed snippets
        if reversed_snippets:
            common_prefix_reversed = reversed_snippets[0]
            for snippet in reversed_snippets[1:]:
                # Find common prefix length
                min_len = min(len(common_prefix_reversed), len(snippet))
                for j in range(min_len):
                    if common_prefix_reversed[j] != snippet[j]:
                        common_prefix_reversed = common_prefix_reversed[:j]
                        break
                else:
                    # All characters matched up to min_len
                    common_prefix_reversed = common_prefix_reversed[:min_len]

            # Reverse back to get the common suffix
            separation_pattern = common_prefix_reversed[::-1]

            # Validate pattern: must be reasonable length and not just whitespace
            # For warnings with few features, the pattern might be too long/specific
            if len(separation_pattern.strip()) < 2 or len(separation_pattern) > 20:
                # Fallback: try common structural patterns
                if len(preceding_snippets) >= 1:
                    # Look for simple patterns like ".\n" which are common
                    test_patterns = [".\n", ".\n\n", "\n\n", ".\n "]
                    for pattern in test_patterns:
                        # Check if this pattern appears in all preceding snippets
                        if all(pattern in snippet for snippet in preceding_snippets):
                            separation_pattern = pattern
                            break
                    else:
                        separation_pattern = ""  # No common simple pattern found
                else:
                    separation_pattern = ""
            else:
                # Pattern seems reasonable, keep it
                pass
        else:
            separation_pattern = ""
    else:
        separation_pattern = ""

    # Step 4: Bound the final features using the separation pattern
    cleaned_features = []

    for i, raw_text in enumerate(raw_feature_texts):
        if i < len(raw_feature_texts) - 1:  # Non-last features
            # Keep exact raw bounds (already end at next feature start)
            cleaned_text = raw_text.rstrip()
        else:  # Last feature
            # Find the rightmost occurrence of separation pattern after feature start
            feature_start_pos = feature_starts[i]
            feature_text_from_start = warning_text[feature_start_pos:]

            if separation_pattern:
                # Search for rightmost occurrence of pattern in the feature text
                rightmost_pos = feature_text_from_start.rfind(separation_pattern)
                if rightmost_pos != -1:
                    # End the feature immediately after the pattern
                    pattern_end_pos = feature_start_pos + rightmost_pos + len(separation_pattern)
                    cleaned_text = warning_text[feature_start_pos:pattern_end_pos].rstrip()
                else:
                    # Pattern not found, keep full raw text
                    cleaned_text = raw_text.rstrip()
            else:
                # No valid separation pattern, keep full raw text
                cleaned_text = raw_text.rstrip()

        cleaned_features.append(cleaned_text)

    # Step 5: Extract prefix and suffix
    first_feature_start = feature_starts[0]
    prefix = warning_text[:first_feature_start].rstrip()

    # Suffix: everything from the end of the last cleaned feature to warning end
    if cleaned_features:
        last_feature_end_pos = feature_starts[-1] + len(cleaned_features[-1])
        suffix = warning_text[last_feature_end_pos:].lstrip()
    else:
        suffix = ""

    return prefix, cleaned_features, suffix


def extract_feature_description(full_text: str, all_coord_sets: list, current_coord_set: list) -> str:
    """
    Extract the description text for a specific feature by using the robust warning component extraction.

    Args:
        full_text: The complete warning description text
        all_coord_sets: List of all coordinate sets from the warning (each has feature text at index 2)
        current_coord_set: The specific coordinate set for this feature (must have feature text at index 2)

    Returns:
        The prefix + feature_text + suffix for this specific feature, or None if not found
    """
    import re

    if len(current_coord_set) < 2 or not all_coord_sets:
        return None

    # Special case: if there's only one coordinate set, return full text as-is
    if len(all_coord_sets) == 1:
        return full_text.strip()

    # Extract warning components
    prefix, feature_list, suffix = extract_warning_components(full_text)

    # Extract label from coord_type (e.g., POINT_A, TRACKLINE_BB -> "A", "BB")
    coord_type = current_coord_set[0]
    label_match = re.search(r'(?:POINT_|AREA_|CIRCULAR_AREA_|BOUNDARY_AREA_|TRACKLINE_|COORDINATES_|DEPTH_POINT_|FACILITY_|SCATTERED_POINT_)([A-Z]+)', coord_type)
    label = label_match.group(1) if label_match else None

    feature_index = None
    if label and feature_list:
        expected_start = f"{label}."
        for i, feature_text in enumerate(feature_list):
            if feature_text.strip().startswith(expected_start):
                feature_index = i
                break

    # Fallback to substring matching if label matching fails
    if feature_index is None:
        current_feature_text = current_coord_set[2] or ""
        for i, feature_text in enumerate(feature_list):
            # Normalize for whitespace comparison
            norm_current = re.sub(r'\s+', ' ', current_feature_text.strip())
            norm_feat = re.sub(r'\s+', ' ', feature_text.strip())
            if norm_current in norm_feat or norm_feat in norm_current:
                feature_index = i
                break

    if feature_index is None:
        # Final fallback: return the feature text directly (or full text if unavailable)
        return current_coord_set[2] or full_text.strip()

    # Combine: prefix + this feature + suffix
    result_parts = []
    if prefix:
        result_parts.append(prefix)
    result_parts.append(feature_list[feature_index])
    if suffix:
        result_parts.append(suffix)

    return '\n'.join(result_parts)




class GeocodingCache:
    def __init__(self, cache_dir=None):
        self.cache = {}
        self.file_path = None
        self.cache_dir = Path(cache_dir) if cache_dir else Path("_cache")
        self._ensure_file_path()

    def _ensure_file_path(self):
        if self.file_path is None:
            self.cache_dir.mkdir(exist_ok=True)
            self.file_path = self.cache_dir / "geocoding_cache.json"

    def load(self):
        """Load geocoding cache from disk"""
        self._ensure_file_path()
        try:
            if self.file_path.exists():
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    loaded_cache = json.load(f)
                    self.cache.update(loaded_cache)  # Merge instead of replace
        except Exception:
            # If cache loading fails, keep existing cache
            pass

    def save(self):
        """Save geocoding cache to disk"""
        self._ensure_file_path()
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception:
            # Silently ignore save failures
            pass

    def get(self, key, default=None):
        """Get a cache entry"""
        return self.cache.get(key, default)

    def __getitem__(self, key):
        """Get a cache entry"""
        return self.cache[key]

    def __setitem__(self, key, value):
        """Set a cache entry"""
        self.cache[key] = value

    def __contains__(self, key):
        return key in self.cache

    def __len__(self):
        return len(self.cache)

    def __iter__(self):
        return iter(self.cache.items())

    def items(self):
        """Get cache items"""
        return self.cache.items()

    def clear(self):
        """Clear the cache"""
        self.cache.clear()


def get_geocoding_cache_stats(cache_dir=None):
    """Get statistics about the geocoding cache"""
    cache = GeocodingCache(cache_dir)
    cache.load()
    return {
        'total_entries': len(cache.cache),
        'cache_file': str(cache.file_path) if cache.file_path else None
    }


def clear_geocoding_cache(cache_dir=None):
    """Clear the geocoding cache"""
    cache = GeocodingCache(cache_dir)
    cache.clear()
    cache.save()


def _hide_metadata_folder(meta_dir: Path):
    """Hide metadata folder on Windows systems"""
    if os.name == 'nt':
        try:
            FILE_ATTRIBUTE_HIDDEN = 0x2
            ctypes.windll.kernel32.SetFileAttributesW(str(meta_dir), FILE_ATTRIBUTE_HIDDEN)
        except Exception as e:
            # Silently ignore if we can't hide the folder
            pass


def _get_task_color_settings(task):
    """Get color and opacity settings from task with defaults"""
    color = getattr(task, 'settings_color', None) or '#ff0000'
    opacity = getattr(task, 'settings_opacity', None) or '80'
    return color, opacity


async def process_async(session, task: LayerTask, report_progress, output_dir: str, cache_dir: str) -> bool:
    """Async version of navigation warnings processing"""
    log_geocoding_cache_stats(cache_dir, report_progress)
    report_progress(0, "Downloading current navigation warnings from official sources...")

    try:
        # For now, use the sync version since the fetcher needs to be made async too
        # TODO: Make the fetcher async for full concurrent processing
        warnings_data = scrape_global_navwarnings(cache_dir, report_progress)
        report_progress(0, f"Retrieved {len(warnings_data)} navigation warnings")

        if not warnings_data:
            report_progress(0, "-> No active navigation warnings found")
            return True

        report_progress(task.weight * 0.3, f"Downloaded {len(warnings_data)} global navigation warnings")

    except Exception as e:
        report_progress(0, f"-> Navigation warnings download failed: {e}")
        import traceback
        report_progress(0, f"Traceback: {traceback.format_exc()}")
        return False

    # Use the same KML creation logic as sync version
    return create_kml_for_warnings(task, report_progress, output_dir, cache_dir, warnings_data)


def create_kml_for_warnings(task, report_progress, output_dir, cache_dir, warnings_data):
    """Create KML file for navigation warnings"""
    report_progress(0, f"Processing {len(warnings_data)} warnings for KML creation...")

    if not task.output_path:
        report_progress(0, "ERROR: Invalid output path")
        return False

    try:
        output_dir_path = Path(task.output_path).parent
        output_dir_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        report_progress(0, f"ERROR: Could not create output directory: {e}")
        return False

    if not task.color_abgr:
        report_progress(0, "ERROR: Invalid color")
        return False

    try:
        opacity_percent = int(task.settings_opacity) if task.settings_opacity else 80
        placemark_count = create_warnings_kml(warnings_data, task.output_path, task.color_abgr, task.use_custom_colors, task.settings_color, opacity_percent, report_progress, cache_dir)
    except Exception as e:
        report_progress(0, f"ERROR: KML creation failed: {e}")
        import traceback
        report_progress(0, f"ERROR: {traceback.format_exc()}")
        return False

    if placemark_count > 0:
        report_progress(task.weight * 0.2, f"KML generation complete: Created {placemark_count} navigation warning features")
        report_progress(0, f"Created {placemark_count} KML features from {len(warnings_data)} warnings")

        # Write metadata
        try:
            meta_dir = Path(output_dir) / "_metadata"
            meta_dir.mkdir(exist_ok=True)
            kml_filename = os.path.basename(task.output_path)
            meta_path = meta_dir / (kml_filename + ".meta")

            # Ensure settings are valid
            color, opacity = _get_task_color_settings(task)

            meta_settings = {
                "color": color,
                "opacity": opacity
            }

            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta_settings, f, indent=2)

            _hide_metadata_folder(meta_dir)
        except Exception as e:
            report_progress(0, f"ERROR: Could not write meta file: {e}")
            # Don't fail the whole process for metadata issues

        report_progress(0, f"Created KML with {placemark_count} navigation warning features")
        return True
    return False


def parse_daily_memorandum(content, source_url, memo_name):
    """Parse daily memorandum content into warning objects"""
    warnings = []

    # Split content into lines
    lines = content.split('\n')

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Look for warning start pattern: timestamp followed by warning number
        # Pattern: "140727Z JAN 26" followed by "HYDROLANT 80/26(35)."
        timestamp_match = re.search(r'^\d{6}Z\s+[A-Z]{3}\s+\d{2}', line)
        if timestamp_match:
            # Found a timestamp, check if next line is a warning number
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                warning_match = re.search(r'^(NAVAREA|HYDRO)[A-Z]*(\s+[A-Z]+)?\s+\d+/\d+\([A-Z0-9,]+\)\.', next_line)
                if warning_match:
                    # Found a warning! Parse it
                    warning_lines = []
                    j = i

                    # Collect all lines until next warning or end
                    while j < len(lines):
                        current_line = lines[j].strip()
                        if j > i + 1:  # Skip the timestamp and warning number lines we already checked
                            # Check if this is the start of a new warning
                            new_timestamp = re.search(r'^\d{6}Z\s+[A-Z]{3}\s+\d{2}', current_line)
                            if new_timestamp and j + 1 < len(lines):
                                next_check = lines[j + 1].strip()
                                new_warning = re.search(r'^(NAVAREA|HYDRO)[A-Z]*\s+\d+/\d+\(\d+\)\.', next_check)
                                if new_warning:
                                    break  # Found start of next warning

                        warning_lines.append(current_line)
                        j += 1

                    # Parse the warning
                    if len(warning_lines) >= 2:
                        warning_text = '\n'.join(warning_lines)

                        # Extract warning details
                        warning_info = parse_warning_text(warning_text, memo_name)
                        if warning_info:
                            warnings.append(warning_info)

                    i = j  # Skip to next potential warning
                    continue

        i += 1

    return warnings


def parse_warning_text(warning_text, memo_name):
    """Parse individual warning text into structured data"""
    lines = warning_text.split('\n')

    if len(lines) < 2:
        return None

    # Extract timestamp (first line)
    timestamp_line = lines[0].strip()

    # Extract warning number and area (second line)
    warning_line = lines[1].strip()

    # Parse warning number like "HYDROLANT 80/26(35)." or "NAVAREA IV 42/26(GEN)."
    warning_match = re.search(r'^(NAVAREA|HYDRO)[A-Z]*(\s+[A-Z]+)?\s+(\d+)/(\d+)\(([A-Z0-9,]+)\)\.', warning_line)
    if not warning_match:
        return None

    area_type = warning_match.group(1)
    msg_number = warning_match.group(3)
    msg_year = warning_match.group(4)
    msg_subnumber = warning_match.group(5)

    # Extract NAVAREA from memo_name
    navarea = extract_navarea_from_memo_name(memo_name)

    # Combine remaining lines as description
    description_lines = []
    for line in lines[2:]:
        if line.strip():
            description_lines.append(line.strip())

    description = '\n'.join(description_lines)

    return {
        'navarea': navarea,
        'msg_number': f"{msg_number}/{msg_year}",
        'msg_year': msg_year,
        'content': warning_text,
        'description': description,
        'source': memo_name,
        'timestamp': timestamp_line
    }


def process(task: LayerTask, report_progress, output_dir: str, cache_dir: str) -> bool:
    """Main processing function for navigation warnings"""
    log_geocoding_cache_stats(cache_dir, report_progress)
    report_progress(0, "Downloading current navigation warnings from official sources...")

    try:
        warnings_data = scrape_global_navwarnings(cache_dir)
        report_progress(0, f"Retrieved {len(warnings_data)} navigation warnings")

        if not warnings_data:
            report_progress(0, "-> No active navigation warnings found")
            return True

        report_progress(task.weight * 0.3, f"Downloaded {len(warnings_data)} global navigation warnings")

    except Exception as e:
        report_progress(0, f"-> Navigation warnings download failed: {e}")
        import traceback
        report_progress(0, f"Traceback: {traceback.format_exc()}")
        return False

    report_progress(0, f"Processing {len(warnings_data)} warnings for KML creation...")

    # Convert warnings to KML (this is CPU-bound, not I/O bound, so it's fine to keep sync)

    if not task.output_path:
        report_progress(0, "ERROR: Invalid output path")
        return False

    try:
        output_dir_path = Path(task.output_path).parent
        output_dir_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        report_progress(0, f"ERROR: Could not create output directory: {e}")
        return False

    if not task.color_abgr:
        report_progress(0, "ERROR: Invalid color")
        return False

    try:
        opacity_percent = int(task.settings_opacity) if task.settings_opacity else 80
        placemark_count = create_warnings_kml(warnings_data, task.output_path, task.color_abgr, task.use_custom_colors, task.settings_color, opacity_percent, report_progress, cache_dir)
    except Exception as e:
        report_progress(0, f"ERROR: KML creation failed: {e}")
        import traceback
        report_progress(0, f"ERROR: {traceback.format_exc()}")
        return False

    if placemark_count > 0:

        # Write metadata
        try:
            meta_dir = Path(output_dir) / "_metadata"
            meta_dir.mkdir(exist_ok=True)
            kml_filename = os.path.basename(task.output_path)
            meta_path = meta_dir / (kml_filename + ".meta")

            # Ensure settings are valid
            color, opacity = _get_task_color_settings(task)

            meta_settings = {
                "color": color,
                "opacity": opacity
            }

            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta_settings, f, indent=2)

            _hide_metadata_folder(meta_dir)

        except Exception as e:
            report_progress(0, f"ERROR: Could not write meta file: {e}")
            # Don't fail the whole process for metadata issues

        return True
    return False


def scrape_global_navwarnings(cache_dir=None, report_progress=None):
    """Download current global navigation warnings"""

    try:
        raw_data = get_curated_current_warnings(cache_dir, report_progress)

        # Handle different data formats
        warnings_data = []
        if isinstance(raw_data, dict):
            # Dictionary format from memorandums
            for memo_name, content in raw_data.items():
                parsed_warnings = parse_daily_memorandum(content, "", memo_name)
                warnings_data.extend(parsed_warnings)
        elif isinstance(raw_data, list):
            # List format from API
            for item in raw_data:
                if isinstance(item, dict):
                    warnings_data.append(item)
                elif isinstance(item, str):
                    # Skip string entries for now
                    continue
        # Process coordinates for each warning
        extracted_count = 0
        for warning in warnings_data:
            if isinstance(warning, dict) and not warning.get('coordinates'):
                # Try different sources for coordinate data
                coords = None

                # First, try text content (memorandum style or API text)
                content = warning.get('content', '') or warning.get('description', '') or warning.get('text', '')
                if content:
                    try:
                        coords = extract_coordinates_from_text(content)
                    except Exception:
                        pass

                # If no coordinates from text, try API geometry fields
                if not coords:
                    # Check for API-style geometry fields
                    geometry = warning.get('geometry', {})
                    if geometry:
                        coords = extract_coordinates_from_api_geometry(geometry)

                    # Check for other possible geometry fields
                    if not coords:
                        # Try various possible field names
                        for field_name in ['coordinates', 'location', 'position', 'geom']:
                            geom_data = warning.get(field_name)
                            if geom_data:
                                coords = extract_coordinates_from_api_geometry(geom_data)
                                if coords:
                                    break

                        if coords:
                            warning['coordinates'] = coords
                            extracted_count += 1
                else:
                    warning['coordinates'] = None

        return warnings_data

    except Exception as e:
        import traceback
        report_progress(0, f"ERROR: {traceback.format_exc()}")
        return []


def get_navarea_display_name(navarea_code):
    """Get the full display name for a navarea code"""
    navarea_names = {
        'IV': 'NAVAREA IV (US Atlantic)',
        'XII': 'NAVAREA XII (US Pacific)',
        'HYDROLANT': 'HYDROLANT (Atlantic)',
        'HYDROPAC': 'HYDROPAC (Indo-Pacific)',
        'HYDROARC': 'HYDROARC (Arctic)'
    }
    return navarea_names.get(navarea_code, f'NAVAREA {navarea_code}')


def should_filter_warning_message(warning):
    """Check if a warning message should be filtered out (no plottable navigational information)"""
    text = warning.get('description', '').upper()
    import re

    # Check for different types of non-navigational messages
    should_filter = False

    # Type 1: "CANCEL THIS MSG/MESSAGE" messages
    if 'CANCEL THIS MSG' in text or 'CANCEL THIS MESSAGE' in text:
        should_filter = True
    # Type 2: Messages that cancel specific other warnings (e.g., "CANCEL HYDROLANT 8/26, 23/26")
    elif re.search(r'CANCEL\s+(HYDROPAC|HYDROLANT|HYDROARC|NAVAREA\s+[IVX]+)\s+\d+/\d+', text):
        should_filter = True
    # Type 3: Service advisory messages (e.g., NGA NAVSAFETY watch e-mail unusable)
    # But allow messages that have specific geocodable place names (like CAPE TOWN)
    elif ('NGA NAVSAFETY' in text and ('UNUSABLE' in text or 'CONTACT' in text or 'PHONE' in text)) and 'CAPE TOWN' not in text:
        should_filter = True
    # Type 4: General service messages with (GEN) designation and no coordinates
    elif '(GEN)' in text and not re.search(r'\d{2}-\d{2}\.\d{2}N\s+\d{3}-\d{2}\.\d{2}[EW]', text):
        # Check if it's actually a general service message about communications/services
        service_keywords = ['E-MAIL', 'PHONE', 'CONTACT', 'UNUSABLE', 'OUTAGE', 'MAINTENANCE', 'SERVICE']
        if any(keyword in text for keyword in service_keywords):
            should_filter = True
    # Type 5: ENC/Chart management advisories (e.g., cancelled ENC chart warnings)
    elif ('ELECTRONIC NAVIGATIONAL CHART' in text or 'ENC' in text) and ('ADVISORY' in text or 'ECDIS' in text or 'CANCELLED' in text):
        should_filter = True
    # Type 6: Information access messages (e.g., how to access warnings via website/email)
    elif ('COMPLETE TEXT' in text and 'BROADCAST WARNINGS' in text) or ('AVAILABLE ON' in text and ('WEBSITE' in text or 'MSI.NGA.MIL' in text or 'NAVWARNINGS' in text)):
        should_filter = True
    # Type 7: Reconnaissance and status reports (e.g., iceberg flight reports)
    elif 'RECONNAISSANCE' in text or ('ICEBERG' in text and 'FLIGHT' in text):
        should_filter = True
    # Type 8: Iceberg bulletins (informational bulletins, not specific warnings)
    elif 'ICEBERG BULLETIN' in text or ('ICEBERG' in text and 'BULLETIN' in text):
        should_filter = True
    # Type 9: Reporting instructions (e.g., "REPORT POSITION AND TIME OF ANY ICEBERGS")
    elif 'REPORT POSITION' in text and ('ICEBERGS' in text or 'SEA ICE' in text):
        should_filter = True
    # Type 10: Resource reference messages (e.g., download links, external website references)
    elif ('FOR MORE' in text and 'INFORMATION' in text) or ('DOWNLOAD' in text and ('SHAPEFILES' in text or 'PREDICTIONS' in text)) or ('GO TO' in text and ('WWW.' in text or 'HTTP' in text)):
        should_filter = True
    # Type 11: Contact information messages (pure contact info without navigational content)
    elif (('FOR FURTHER INFORMATION' in text or 'FOR MORE INFORMATION' in text) and
          ('CONTACT' in text or 'PHONE' in text or 'EMAIL' in text) and
          not re.search(r'\d{2}-\d{2}\.\d{2}N\s+\d{3}-\d{2}\.\d{2}[EW]', text) and  # No coordinates
          not any(hazard in text for hazard in ['OPERATIONS', 'EXERCISE', 'MINES', 'SUBMARINE', 'DRILLING', 'CONSTRUCTION', 'CABLE'])):
        should_filter = True
    # Type 12: Warning index/summary messages (e.g., "WARNINGS IN FORCE AS OF")
    elif 'WARNINGS IN FORCE' in text or ('ALL THE INFORCE WARNINGS' in text and 'ARE LISTED' in text):
        should_filter = True
    # Type 13: Administrative reporting messages (e.g., "TO REPORT A MOBILE OFFSHORE DRILLING UNIT")
    elif ('TO REPORT' in text and 'MODU' in text) or ('REPORTING REQUIREMENTS' in text) or ('CONTACT NAVSAFETY@NGA.MIL' in text and 'MODU REPORT' in text):
        should_filter = True
    # Type 14: Military advisory messages (informational warnings about potential course alterations)
    elif ('VESSELS MAY BE REQUESTED TO ALTER COURSE' in text and 'FIRING OPERATIONS' in text) or ('MILITARY OPERATIONS' in text and 'VESSELS ARE ADVISED' in text):
        should_filter = True
    # Type 15: Mine reporting instructions (requests to report mine sightings without specific locations)
    elif ('VESSELS ARE REQUESTED TO' in text and 'REPORT SIGHTINGS OF MINES' in text) or ('REPORT SIGHTINGS' in text and 'MINES OR MINE-LIKE OBJECTS' in text) or ('IMMEDIATELY REPORT' in text and 'MINES OR MINE-LIKE OBJECTS' in text):
        should_filter = True
    # Type 16: Generic berth requests without specific location or activity details
    elif ('WIDE BERTH REQUESTED' in text or 'BERTH REQUESTED' in text) and not re.search(r'\d{2}-\d{2}(\.\d{1,2})?N\s+\d{3}-\d{2}(\.\d{1,2})?[EW]', text) and not any(activity in text for activity in ['DRILLING', 'CONSTRUCTION', 'SURVEY', 'MILITARY', 'DANGER', 'HAZARD']):
        should_filter = True

    if not should_filter:
        return False

    # Check if it has any coordinate information
    coords = warning.get('coordinates')
    if coords and isinstance(coords, list) and len(coords) > 0:
        # Check if any coordinate set has actual coordinates
        for coord_set in coords:
            if isinstance(coord_set, list) and len(coord_set) >= 2:
                coord_type, coord_data = coord_set[:2]  # Handle both 2-element and 3-element sets
                if isinstance(coord_data, list) and len(coord_data) > 0:
                    # Has actual coordinate data
                    return False
                elif isinstance(coord_data, dict) and 'center' in coord_data:
                    # Has CIRCULAR_AREA data
                    return False

    # Check if the text contains coordinate-like patterns
    coord_patterns = [
        r'\d{2}-\d{2}\.\d{2}N\s+\d{3}-\d{2}\.\d{2}[EW]',  # Degree-decimal minute format
        r'\d{2}-\d{2}\.[NS]\s+\d{3}-\d{2}\.[EW]',  # Alternative format
        r'\d{2}\.\d+[NS]\s+\d{3}\.\d+[EW]',  # Decimal degrees
    ]

    for pattern in coord_patterns:
        if re.search(pattern, text):
            return False

    # If we get here, it's a message with no plottable navigational information
    return True


def categorize_warning(warning):
    """
    Categorize a warning based on its description content.

    Returns a category string that determines the icon to use.
    """
    if not warning or not isinstance(warning, dict):
        return 'GENERAL'

    # Get description text
    desc = warning.get('description', '') or warning.get('content', '') or warning.get('text', '')
    desc_upper = desc.upper()

    # Danger zones (explosives, military, high-risk operations)
    # Highest priority - most dangerous
    danger_terms = ['MISSILE', 'TEST FIRING', 'MINE', 'MINES', 'NUCLEAR', 'FIRING', 'MILITARY', 'NAVAL EXERCISE', 'SPACE', 'AIRCRAFT', 'HELICOPTER', 'FLIGHT', 'AIRSPACE', 'PATROL', 'GUNNERY', 'MINING', 'HAZARDOUS', 'ORDNANCE', 'DETONATION', 'PIRATES', 'PIRACY', 'VOLCANIC']
    if any(term in desc_upper for term in danger_terms) or ('ROCKET' in desc_upper):
        return 'DANGER'

    # Ice-related hazards (word boundaries to avoid false matches like "NOTICE")
    if re.search(r'\bICE\b', desc_upper) or 'ICEBERG' in desc_upper or 'SEA ICE' in desc_upper:
        return 'ICE'

    # Physical obstructions (including wrecks marked by navigation aids) - higher priority than navigation aids
    if any(term in desc_upper for term in ['OBSTRUCTION', 'OBSTRUCTED', 'WRECK', 'DEBRIS', 'SANK', 'SUNKEN', 'SUNK', 'DERELICT', 'ABANDONED', 'FOUL']):
        return 'OBSTRUCTIONS'

    # Navigation aids and infrastructure (buoys, beacons, lights, communication stations, shoals, depth reports, racons, navigation systems)
    # High priority - critical safety infrastructure
    navigation_terms = ['BUOY', 'BEACON', 'LIGHT', 'COMMUNICATION', 'STATION', 'RADIO', 'VHF', 'LIGHTHOUSE', 'LANTERN', 'SHOAL', 'SHOALS', 'DEPTHS REPORTED', 'DEPTH REPORTED', 'SHALLOW', 'RACON', 'GPS', 'GNSS', 'AIS', 'RADAR', 'NAVIGATIONAL AIDS']
    # Check for frequency designations as separate words (not inside other words like "M/V")
    if any(term in desc_upper for term in navigation_terms) or re.search(r'\bMF\b', desc_upper) or re.search(r'\bHF\b', desc_upper):
        return 'NAVIGATION'

    # Marine operations and construction (drilling, surveys, underwater work, infrastructure)
    # Activities that may temporarily affect navigation
    operations_terms = ['DRILLING', 'DRILL', 'OIL', 'GAS', 'CONSTRUCTION', 'CABLE', 'PIPELINE', 'BRIDGE', 'LOCK', 'BARRIER', 'MOORING', 'MOORINGS', 'SEISMIC', 'SURVEY', 'RESEARCH', 'DEPTH', 'DEPTHS', 'UNDERWATER', 'INSTALLATION', 'OFFSHORE']
    if any(term in desc_upper for term in operations_terms):
        return 'OPERATIONS'

    # Default category (includes former submarine activities, tracklines, vessel operations, and general maintenance)
    return 'GENERAL'


def get_warning_icon_url(category, use_custom_icons=True):
    """
    Get the Google Earth icon URL for a warning category.
    """
    icon_map = {
        'ICE': 'http://maps.google.com/mapfiles/kml/shapes/snowflake_simple.png',
        'DANGER': 'http://maps.google.com/mapfiles/kml/shapes/forbidden.png',
        'OPERATIONS': 'http://maps.google.com/mapfiles/kml/shapes/mechanic.png',
        'OBSTRUCTIONS': 'http://maps.google.com/mapfiles/kml/shapes/caution.png',
        'NAVIGATION': 'http://maps.google.com/mapfiles/kml/shapes/lighthouse.png',
        'GENERAL': 'http://maps.google.com/mapfiles/kml/shapes/flag.png'
    }

    if not use_custom_icons:
        # Use default icon for all categories
        return 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png'
    else:
        # Use custom icon scheme
        return icon_map.get(category, icon_map['GENERAL'])


def get_warning_color(category, use_custom_colors=True, single_color_hex=None, opacity_percent=100):
    """
    Get the KML color (AABBGGRR format) for a warning category.
    Colors are chosen to be visually distinct and appropriate for each category.
    """
    color_map = {
        # Ice-related hazards
        'ICE': 'ffffff00',              # Cyan

        # Danger zones (explosives, military)
        'DANGER': 'ff0000ff',           # Red

        # Marine operations
        'OPERATIONS': 'ff0080ff',       # Orange

        # Physical obstructions
        'OBSTRUCTIONS': 'ff00ffff',     # Yellow

        # Navigation aids
        'NAVIGATION': 'ff00ff00',       # Bright Green

        # General warnings
        'GENERAL': 'ffffffff'           # White
    }

    if not use_custom_colors and single_color_hex:
        # Convert hex color to KML ABGR format with specified opacity
        return hex_to_kml_abgr(single_color_hex, opacity_percent)
    else:
        # Use custom color scheme (apply opacity to the predefined colors)
        base_color = color_map.get(category, color_map['GENERAL'])
        # Extract the RGB part and apply new opacity
        if base_color.startswith('ff'):  # ABGR format
            rgb_part = base_color[2:]  # Remove alpha
            # Convert opacity percent to hex (0-255)
            alpha_hex = hex(int((opacity_percent / 100) * 255))[2:].zfill(2)
            return alpha_hex + rgb_part
        else:
            # Fallback: if it's not in expected format, apply opacity using hex_to_kml_abgr
            # Extract RGB part from ABGR and convert back to hex format
            rgb_hex = base_color[2:8]  # Extract RGB part from ABGR
            return hex_to_kml_abgr(f"#{rgb_hex}", opacity_percent)


def parse_index_message_warnings(text):
    """Parse warning numbers referenced in index messages"""
    import re

    # Look for patterns like "5/2026, 4/2026, 3/2026" or "283/2024"
    warning_pattern = r'(\d{1,4}/\d{4})'
    matches = re.findall(warning_pattern, text)

    # Clean up the results - sometimes there might be duplicates or invalid matches
    valid_warnings = []
    for match in matches:
        # Basic validation - should be like "123/2025" format
        if '/' in match and len(match.split('/')[0]) <= 4 and len(match.split('/')[1]) == 4:
            valid_warnings.append(match)

    return list(set(valid_warnings))  # Remove duplicates


def validate_warnings_from_index(filtered_warnings, index_messages):
    """Validate that warnings referenced in index messages are still present"""
    import re

    # Build a set of warning keys from filtered warnings
    present_warnings = set()
    for warning in filtered_warnings:
        navarea = warning.get('navarea', '').upper()
        msg_number = warning.get('msg_number', '')

        if navarea and msg_number:
            # Create a normalized key for comparison
            key = f"{navarea}_{msg_number}"
            present_warnings.add(key)

    validation_results = {
        'total_index_messages': len(index_messages),
        'total_referenced_warnings': 0,
        'found_warnings': 0,
        'missing_warnings': 0,
        'missing_details': []
    }


    for index_msg in index_messages:
        navarea = index_msg.get('navarea', '').upper()
        referenced_warnings = parse_index_message_warnings(index_msg.get('description', ''))


        validation_results['total_referenced_warnings'] += len(referenced_warnings)

        for warning_num in referenced_warnings:
            key = f"{navarea}_{warning_num}"

            if key in present_warnings:
                validation_results['found_warnings'] += 1
            else:
                validation_results['missing_warnings'] += 1
                validation_results['missing_details'].append({
                    'navarea': navarea,
                    'warning_num': warning_num,
                    'key': key
                })

    # Return validation results (can be used for logging if needed)
    return validation_results

    return validation_results


def get_country_iso_code(country_name):
    """Convert country name to ISO 3-letter code for EEZ lookup"""
    # Common country name to ISO code mapping
    country_to_iso = {
        'UKRAINE': 'UKR',
        'RUSSIA': 'RUS',
        'CHINA': 'CHN',
        'JAPAN': 'JPN',
        'INDIA': 'IND',
        'USA': 'USA',
        'UNITED STATES': 'USA',
        'CANADA': 'CAN',
        'FRANCE': 'FRA',
        'GERMANY': 'DEU',
        'ITALY': 'ITA',
        'SPAIN': 'ESP',
        'PORTUGAL': 'PRT',
        'NETHERLANDS': 'NLD',
        'BELGIUM': 'BEL',
        'SWITZERLAND': 'CHE',
        'AUSTRALIA': 'AUS',
        'MEXICO': 'MEX',
        'BRAZIL': 'BRA',
        'ARGENTINA': 'ARG',
        'SWEDEN': 'SWE',
        'NORWAY': 'NOR',
        'DENMARK': 'DNK',
        'FINLAND': 'FIN',
        'POLAND': 'POL',
        'TURKEY': 'TUR',
        'ISRAEL': 'ISR',
        'EGYPT': 'EGY',
        'MOROCCO': 'MAR',
        'TUNISIA': 'TUN',
        'ALGERIA': 'DZA',
        'SOUTH AFRICA': 'ZAF',
        'NIGERIA': 'NGA',
        'KENYA': 'KEN',
        'INDONESIA': 'IDN',
        'MALAYSIA': 'MYS',
        'SINGAPORE': 'SGP',
        'THAILAND': 'THA',
        'VIETNAM': 'VNM',
        'PHILIPPINES': 'PHL',
        'TAIWAN': 'TWN',
        'SOUTH KOREA': 'KOR',
        'NORTH KOREA': 'PRK',
        'MONGOLIA': 'MNG',
        'KAZAKHSTAN': 'KAZ',
        'UZBEKISTAN': 'UZB',
        'IRAN': 'IRN',
        'IRAQ': 'IRQ',
        'SYRIA': 'SYR',
        'LEBANON': 'LBN',
        'JORDAN': 'JOR',
        'PALESTINE': 'PSE',
        'LIBYA': 'LBY',
        'ETHIOPIA': 'ETH',
        'SOMALIA': 'SOM',
        'TANZANIA': 'TZA',
        'UGANDA': 'UGA',
        'MADAGASCAR': 'MDG',
        'COMOROS': 'COM',
        'MAURITIUS': 'MUS',
        'SEYCHELLES': 'SYC'
    }

    return country_to_iso.get(country_name.upper())


def get_eez_center(country_name):
    """Get the center point of a country's EEZ using Marine Regions data"""
    import requests
    import xml.etree.ElementTree as ET
    import time

    try:
        # Get ISO code
        iso_code = get_country_iso_code(country_name)
        if not iso_code:
            return None

        # Rate limiting
        time.sleep(1)

        # Download EEZ data from Marine Regions
        marinerregions_url = "https://geo.vliz.be/geoserver/MarineRegions/wfs"
        params = {
            'service': 'WFS',
            'version': '1.1.0',
            'request': 'GetFeature',
            'typeName': 'MarineRegions:eez',
            'outputFormat': 'KML',
            'CQL_FILTER': f"iso_ter1='{iso_code}'"
        }

        headers = {
            'User-Agent': 'MDA-Layers-Downloader/1.0'
        }

        response = requests.get(marinerregions_url, params=params, headers=headers, timeout=30)
        response.raise_for_status()

        # Parse KML to find EEZ polygons
        root = ET.fromstring(response.content)

        # Find all coordinates in the KML
        all_coords = []
        for coord_elem in root.findall('.//{http://www.opengis.net/kml/2.2}coordinates'):
            coord_text = coord_elem.text.strip()
            if coord_text:
                # Parse coordinate string (longitude,latitude,altitude)
                for coord_str in coord_text.split():
                    parts = coord_str.split(',')
                    if len(parts) >= 2:
                        try:
                            lon = float(parts[0])
                            lat = float(parts[1])
                            all_coords.append((lon, lat))
                        except ValueError:
                            continue

        if not all_coords:
            return None

        # Calculate the center of all EEZ coordinates
        lats = [coord[1] for coord in all_coords]
        lons = [coord[0] for coord in all_coords]

        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)

        return center_lat, center_lon

    except Exception as e:
        return None

# Geocoding cache is now initialized lazily when first accessed

def log_geocoding_cache_stats(cache_dir=None, report_progress=None):
    """Log geocoding cache statistics"""
    stats = get_geocoding_cache_stats(cache_dir)
    if report_progress:
        report_progress(0, f"[CACHE STATS] {stats['total_entries']} place names cached in {stats['cache_file']}")


def geocode_place_name(place_name, report_progress=None, cache_dir=None):
    """Geocode a place name using OpenStreetMap Nominatim API with intelligent fallback strategies"""
    import requests
    import time

    # Get the geocoding cache for this cache directory
    cache = GeocodingCache(cache_dir)
    cache.load()

    # Check cache first (try both uppercase and lowercase keys for backward compatibility)
    cache_key = place_name.strip().upper()  # Use uppercase as primary key
    cache_key_lower = place_name.strip().lower()

    cached_result = None
    cache_hit = False
    if cache_key in cache:
        cached_result = cache.get(cache_key)
        cache_hit = True
    elif cache_key_lower in cache:
        cached_result = cache.get(cache_key_lower)
        cache_hit = True
        # If found with lowercase key, also store with uppercase for consistency
        if cached_result:
            cache[cache_key] = cached_result

    if cached_result and 'lat' in cached_result and 'lon' in cached_result:
        if report_progress:
            report_progress(0, f"[CACHE HIT] '{place_name}' -> ({cached_result['lat']:.4f}, {cached_result['lon']:.4f})")
        return cached_result['lat'], cached_result['lon']

    # Rate limiting to be respectful to the API
    time.sleep(1)

    if report_progress:
        report_progress(0, f"[API CALL] Geocoding '{place_name}' (not in cache)")

    try:
        # Clean up the place name
        clean_name = place_name.strip()

        # Common place name spelling corrections
        spelling_corrections = {
            'AALAND': 'ÅLAND',
            'SEA OF AALAND': 'SEA OF ÅLAND',
            'GULF OF AALAND': 'GULF OF ÅLAND',
            'BAY OF AALAND': 'BAY OF ÅLAND'
        }

        # Apply spelling corrections
        corrected_name = spelling_corrections.get(clean_name.upper(), clean_name)

        # Build a list of search terms to try in order of preference
        search_terms = [corrected_name]

        # Add maritime variations for locations that don't already have maritime suffixes
        maritime_suffixes = ['sea', 'ocean', 'bay', 'gulf', 'strait', 'channel', 'sound', 'fjord']
        if not any(corrected_name.lower().endswith(suffix) for suffix in maritime_suffixes):
            search_terms.extend([
                f"{corrected_name} sea",
                f"{corrected_name} bay",
                f"{corrected_name} gulf"
            ])

        # Generalized country adjective to country mapping
        # This covers common patterns without hardcoding specific cases
        country_adjectives = {
            'UKRAINIAN': 'UKRAINE',
            'RUSSIAN': 'RUSSIA',
            'CHINESE': 'CHINA',
            'JAPANESE': 'JAPAN',
            'INDIAN': 'INDIA',
            'AMERICAN': 'USA',
            'BRITISH': 'UNITED KINGDOM',
            'FRENCH': 'FRANCE',
            'GERMAN': 'GERMANY',
            'ITALIAN': 'ITALY',
            'SPANISH': 'SPAIN',
            'PORTUGUESE': 'PORTUGAL',
            'DUTCH': 'NETHERLANDS',
            'BELGIAN': 'BELGIUM',
            'SWISS': 'SWITZERLAND',
            'AUSTRALIAN': 'AUSTRALIA',
            'CANADIAN': 'CANADA',
            'MEXICAN': 'MEXICO',
            'BRAZILIAN': 'BRAZIL',
            'ARGENTINE': 'ARGENTINA',
            'SWEDISH': 'SWEDEN',
            'NORWEGIAN': 'NORWAY',
            'DANISH': 'DENMARK',
            'FINNISH': 'FINLAND',
            'POLISH': 'POLAND',
            'CZECH': 'CZECH REPUBLIC',
            'HUNGARIAN': 'HUNGARY',
            'ROMANIAN': 'ROMANIA',
            'BULGARIAN': 'BULGARIA',
            'GREEK': 'GREECE',
            'TURKISH': 'TURKEY',
            'ISRAELI': 'ISRAEL',
            'EGYPTIAN': 'EGYPT',
            'MOROCCAN': 'MOROCCO',
            'TUNISIAN': 'TUNISIA',
            'ALGERIAN': 'ALGERIA'
        }

        # If the place name looks like a country adjective, try the country first
        upper_name = corrected_name.upper()
        for adj, country in country_adjectives.items():
            if upper_name == adj or upper_name.startswith(adj + ' '):
                search_terms.insert(0, country)  # Try country first
                search_terms.insert(1, f"{clean_name} {country.lower()}")  # Try "Ukrainian Ukraine"
                break

        # Try each search term with the Nominatim API
        for search_term in search_terms:
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': search_term,
                'format': 'json',
                'limit': 1,
                'addressdetails': 1
            }

            headers = {
                'User-Agent': 'MDA-Layers-Downloader/1.0'
            }

            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data and len(data) > 0:
                lat = float(data[0]['lat'])
                lon = float(data[0]['lon'])

                if report_progress:
                    report_progress(0, f"[API SUCCESS] '{place_name}' geocoded to ({lat:.4f}, {lon:.4f}) using '{search_term}'")

                # Cache the successful result
                cache[cache_key] = {'lat': lat, 'lon': lon, 'search_term': search_term}
                cache.save()

                return lat, lon

    except Exception as e:
        if report_progress:
            report_progress(0, f"[API FAILED] Geocoding '{place_name}' failed: {str(e)[:100]}")
        return None


def extract_place_names(text):
    """Extract potential place names from warning text using generalized pattern recognition"""
    import re

    # Preprocess text to handle newlines and normalize spacing
    text = re.sub(r'\s+', ' ', text)  # Replace newlines and multiple spaces with single spaces

    found_places = []

    # Priority-based extraction: more specific patterns first

    # 1. Geographic features with "OF" (Gulf of X, Sea of X, etc.)
    # Very restrictive patterns to avoid matching across conjunctions
    of_patterns = [
        (r'\bGULF\s+OF\s+([A-Z]+(?:\s+[A-Z]+)*?)(?=\s+(?:AND|OR|THE|IN|AT|ON|FROM|TO)|\b|$)', 'Gulf of'),
        (r'\bSEA\s+OF\s+([A-Z]+(?:\s+[A-Z]+)*?)(?=\s+(?:AND|OR|THE|IN|AT|ON|FROM|TO)|\b|$)', 'Sea of'),
        (r'\bBAY\s+OF\s+([A-Z]+(?:\s+[A-Z]+)*?)(?=\s+(?:AND|OR|THE|IN|AT|ON|FROM|TO)|\b|$)', 'Bay of'),
        (r'\bSTRAIT\s+OF\s+([A-Z]+(?:\s+[A-Z]+)*?)(?=\s+(?:AND|OR|THE|IN|AT|ON|FROM|TO)|\b|$)', 'Strait of')
    ]

    for pattern, prefix in of_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            place = f"{prefix} {match}".title()
            found_places.append(place)

    # 2. Maritime bodies with directional qualifiers
    directional_maritime = r'\b(?:NORTH|SOUTH|EAST|WEST|NORTHWEST|NORTHEAST|SOUTHWEST|SOUTHEAST|CENTRAL|WESTERN|EASTERN|NORTHERN|SOUTHERN)\s+(?:SEA|OCEAN|BAY|GULF|STRAIT|CHANNEL|SOUND)\b'
    matches = re.findall(directional_maritime, text, re.IGNORECASE)
    found_places.extend(matches)

    # 3. Named maritime bodies
    named_maritime = r'\b(?:BLACK|CASPIAN|RED|MEDITERRANEAN|ARABIAN|BALTIC|CARIBBEAN|BERING|BEAUFORT|CHUKCHI|LABRADOR|GREENLAND|NORWEGIAN|BARENTS|WHITE|KARAS|SCOTIA|WEDDELL|BELLINGSHAUSEN|ROSS|AMUNDSEN|CORAL|TASMAN|JAVA|TIMOR|ARAFURA|ANDAMAN|BENGAL|CHINA|MOLUCCA|SULU|SAVU|FLORES|BANDA|MAKASSAR|CELEBES|HALMAHERA|SERAM)\s+(?:SEA|OCEAN|BAY|GULF|STRAIT|CHANNEL|SOUND)\b'
    matches = re.findall(named_maritime, text, re.IGNORECASE)
    found_places.extend(matches)

    # 4. Countries - exclude when part of compound geographic terms
    countries = r'\b(?:UKRAINE|RUSSIA|CHINA|JAPAN|INDIA|USA|UNITED\s+STATES|CANADA|FRANCE|GERMANY|ITALY|SPAIN|PORTUGAL|NETHERLANDS|BELGIUM|SWITZERLAND|AUSTRALIA|MEXICO|BRAZIL|ARGENTINA|SWEDEN|NORWAY|DENMARK|FINLAND|POLAND|CZECH\s+REPUBLIC|HUNGARY|ROMANIA|BULGARIA|GREECE|TURKEY|ISRAEL|EGYPT|MOROCCO|TUNISIA|ALGERIA|SOUTH\s+AFRICA|NIGERIA|KENYA|INDONESIA|MALAYSIA|SINGAPORE|THAILAND|VIETNAM|PHILIPPINES|TAIWAN|SOUTH\s+KOREA|NORTH\s+KOREA|MONGOLIA|KAZAKHSTAN|UZBEKISTAN|IRAN|IRAQ|SYRIA|LEBANON|JORDAN|PALESTINE|LIBYA|ETHIOPIA|SOMALIA|TANZANIA|UGANDA|MADAGASCAR|COMOROS|MAURITIUS|SEYCHELLES)\b'
    matches = re.findall(countries, text, re.IGNORECASE)
    # Filter out countries that appear to be part of compound geographic terms
    filtered_countries = []
    for country in matches:
        # Skip if this country appears right after geographic indicators
        country_start = text.upper().find(country.upper())
        if country_start > 0:
            preceding_text = text[:country_start].upper()
            # Skip if preceded by words like "INDIAN", "ATLANTIC", etc.
            if (preceding_text.endswith(('INDIAN ', 'ATLANTIC ', 'PACIFIC ', 'ARCTIC ', 'MEDITERRANEAN ',
                                       'CARIBBEAN ', 'NORTHERN ', 'SOUTHERN ', 'EASTERN ', 'WESTERN ',
                                       'NORTH ', 'SOUTH ', 'EAST ', 'WEST '))):
                continue
        filtered_countries.append(country)
    found_places.extend(filtered_countries)

    # 5. Geographic place names (Cape X, Point X, etc.) - more restrictive patterns
    geographic_names = [
        r'\bCAPE\s+[A-Z]+\b',  # CAPE TOWN (just the immediate word after CAPE)
        r'\bPOINT\s+[A-Z]+\b',  # POINT REYES
        r'\bPORT\s+[A-Z]+\b',  # PORT SAID
        r'\bHARBOR\s+[A-Z]+\b',  # PEARL HARBOR
        r'\bSABA\s+BANK\b',  # Specific case for Saba Bank
        r'\b[A-Z]+\s+BANK\b',  # DOGGER BANK
        r'\b[A-Z]+\s+SHOAL\b',  # BROWN SHOAL
        r'\b[A-Z]+(?:\s+[A-Z]+)*\s+REEF\b'   # GREAT BARRIER REEF
    ]

    for pattern in geographic_names:
        matches = re.findall(pattern, text, re.IGNORECASE)
        # Filter out overly long matches and matches that contain non-geographic words
        for match in matches:
            # Skip if it contains words that indicate it's not just a place name
            skip_words = ['HAS', 'BEEN', 'DESIGNATED', 'ADOPTED', 'AREA', 'AVOIDED', 'SENSITIVE', 'RADIO', 'EMAIL', 'CONTACT']
            if len(match) < 25 and not any(skip_word in match.upper() for skip_word in skip_words):
                found_places.append(match)

    # 6. Island names (common patterns)
    islands = r'\b(?:HAWAII|OAHU|MAUI|KAUAI|NIIHAU|LANAI|MOLOKAI|KOHALA|BIG\s+ISLAND|TAHITI|MOOREA|BORABORA|FIJI|VITI\s+LEVU|VANUA\s+LEVU|SUVA|SAMOA|UPOLU|SAVAI|TONGA|NUKU|ALOFA|KIRIBATI|TARAWA|NAURU|PALAU|KOROR|GUAM|SAIPAN|TINIAN|ROTA|CHUUK|POHNPEI|YAP|KOSRAE|MARSHALL\s+ISLANDS|MAJURO|EBEYE|KWAJALEIN|BIKINI|ENEWETAK)\b'
    matches = re.findall(islands, text, re.IGNORECASE)
    found_places.extend(matches)

    # 7. Country adjective handling (UKRAINIAN -> UKRAINE, etc.)
    country_adjectives = {
        'UKRAINIAN': 'UKRAINE',
        'RUSSIAN': 'RUSSIA',
        'CHINESE': 'CHINA',
        'JAPANESE': 'JAPAN',
        'INDIAN': 'INDIA',
        'AMERICAN': 'USA',
        'BRITISH': 'UNITED KINGDOM',
        'FRENCH': 'FRANCE',
        'GERMAN': 'GERMANY',
        'ITALIAN': 'ITALY',
        'SPANISH': 'SPAIN',
        'PORTUGUESE': 'PORTUGAL',
        'DUTCH': 'NETHERLANDS',
        'BELGIAN': 'BELGIUM',
        'SWISS': 'SWITZERLAND',
        'AUSTRALIAN': 'AUSTRALIA',
        'CANADIAN': 'CANADA',
        'MEXICAN': 'MEXICO',
        'BRAZILIAN': 'BRAZIL',
        'ARGENTINE': 'ARGENTINA'
    }

    for adj, country in country_adjectives.items():
        # Find all occurrences of this adjective
        for match in re.finditer(r'\b' + adj + r'\b', text, re.IGNORECASE):
            start_pos = match.start()
            # Check if this adjective is followed by geographic terms
            following_text = text[start_pos + len(adj):].upper()
            following_text = following_text.lstrip()
            # Skip if followed by OCEAN, SEA, etc. (indicating it's a geographic adjective, not a country reference)
            if following_text.startswith(('OCEAN', 'SEA', 'GULF', 'BAY', 'STRAIT', 'CHANNEL')):
                continue
            found_places.append(country)

    # Remove duplicates and prioritize more specific places
    seen = set()
    unique_places = []

    # Define priority order (more specific first)
    priority_keywords = {
        'CAPE': 1, 'POINT': 1, 'PORT': 1, 'HARBOR': 1, 'BANK': 1, 'SHOAL': 1, 'REEF': 1,
        'ISLAND': 1, 'ISLANDS': 1, 'GULF': 2, 'SEA': 2, 'BAY': 2, 'STRAIT': 2, 'CHANNEL': 2,
        'OCEAN': 3, 'ATLANTIC': 3, 'PACIFIC': 3, 'INDIAN': 3, 'ARCTIC': 3,
        'COUNTRY': 4, 'CONTINENT': 4  # Countries and continents last
    }

    # Check if we have any water bodies (seas, gulfs, bays, etc.) OR specific geographic locations
    has_water_bodies = any(
        any(keyword in place.upper() for keyword in ['SEA', 'GULF', 'BAY', 'STRAIT', 'CHANNEL', 'OCEAN'])
        for place in found_places
    )
    has_specific_locations = any(
        place.upper().startswith(('CAPE ', 'POINT ', 'PORT ', 'HARBOR ', 'BANK ', 'SHOAL ', 'REEF ')) or
        any(island in place.upper() for island in ['HAWAII', 'OAHU', 'MAUI', 'KAUAI', 'NIIHAU', 'LANAI', 'MOLOKAI', 'KOHALA'])
        for place in found_places
    )

    # Score each place by specificity
    scored_places = []
    for place in found_places:
        place_upper = place.upper()
        if place_upper in seen:
            continue
        seen.add(place_upper)

        # Calculate specificity score (lower is more specific)
        score = 5  # Default high score
        is_country = False

        # Check if this is a country name
        country_names = ['UKRAINE', 'RUSSIA', 'CHINA', 'JAPAN', 'INDIA', 'USA', 'CANADA', 'FRANCE', 'GERMANY', 'ITALY', 'SPAIN', 'PORTUGAL', 'NETHERLANDS', 'BELGIUM', 'SWITZERLAND', 'AUSTRALIA', 'MEXICO', 'BRAZIL', 'ARGENTINA', 'SWEDEN', 'NORWAY', 'DENMARK', 'FINLAND', 'POLAND', 'TURKEY', 'ISRAEL', 'EGYPT', 'MOROCCO', 'TUNISIA', 'ALGERIA', 'SOUTH AFRICA', 'NIGERIA', 'KENYA', 'INDONESIA', 'MALAYSIA', 'SINGAPORE', 'THAILAND', 'VIETNAM', 'PHILIPPINES', 'TAIWAN', 'SOUTH KOREA', 'NORTH KOREA', 'MONGOLIA', 'KAZAKHSTAN', 'UZBEKISTAN', 'IRAN', 'IRAQ', 'SYRIA', 'LEBANON', 'JORDAN', 'PALESTINE', 'LIBYA', 'ETHIOPIA', 'SOMALIA', 'TANZANIA', 'UGANDA', 'MADAGASCAR', 'COMOROS', 'MAURITIUS', 'SEYCHELLES']
        if place_upper in country_names:
            score = 4
            is_country = True
        else:
            for keyword, keyword_score in priority_keywords.items():
                if keyword in place_upper:
                    score = min(score, keyword_score)
                    break

        # If we have water bodies or specific locations, deprioritize countries
        # This prevents plotting both "Cape Town" and "South Africa"
        if (has_water_bodies or has_specific_locations) and is_country:
            score = 6  # Even lower priority

        scored_places.append((score, place.strip()))

    # Sort by score (more specific first) then alphabetically
    scored_places.sort(key=lambda x: (x[0], x[1]))

    # Filter out deprioritized countries (score 6) when water bodies or specific locations are present
    if has_water_bodies or has_specific_locations:
        filtered_places = [(score, place) for score, place in scored_places if score < 6]
        return [place for score, place in filtered_places]
    else:
        return [place for score, place in scored_places]


def try_geocode_warning(warning, report_progress=None, cache_dir=None):
    """Try to geocode a warning that has no coordinates by finding place names"""
    text = warning.get('description', '')

    # Extract potential place names (already prioritized)
    place_names = extract_place_names(text)

    if not place_names:
        return None

    # Collect all successful geocoding results (prioritization already done in extract_place_names)
    geocoded_locations = []

    # Try to geocode each prioritized place name
    for place_name in place_names:
        coords = geocode_place_name(place_name, report_progress, cache_dir)
        if coords:
            lat, lon = coords
            geocoded_locations.append([lat, lon])

    # If we have place names but no geocoding results, try EEZ center for countries
    if not geocoded_locations and len(place_names) == 1:
        place_name = place_names[0].upper()
        country_names = ['UKRAINE', 'RUSSIA', 'CHINA', 'JAPAN', 'INDIA', 'USA', 'CANADA', 'FRANCE', 'GERMANY', 'ITALY', 'SPAIN', 'PORTUGAL', 'NETHERLANDS', 'BELGIUM', 'AUSTRALIA', 'MEXICO', 'BRAZIL', 'ARGENTINA', 'SWEDEN', 'NORWAY', 'DENMARK', 'FINLAND', 'POLAND', 'TURKEY', 'ISRAEL', 'EGYPT', 'MOROCCO', 'TUNISIA', 'ALGERIA', 'SOUTH AFRICA', 'NIGERIA', 'KENYA', 'INDONESIA', 'MALAYSIA', 'SINGAPORE', 'THAILAND', 'VIETNAM', 'PHILIPPINES', 'TAIWAN', 'SOUTH KOREA', 'NORTH KOREA', 'MONGOLIA', 'KAZAKHSTAN', 'UZBEKISTAN', 'IRAN', 'IRAQ', 'SYRIA', 'LEBANON', 'JORDAN', 'PALESTINE', 'LIBYA', 'ETHIOPIA', 'SOMALIA', 'TANZANIA', 'UGANDA', 'MADAGASCAR', 'COMOROS', 'MAURITIUS', 'SEYCHELLES']
        if place_name in country_names:
            eez_coords = get_eez_center(place_names[0])
            if eez_coords:
                geocoded_locations = [list(eez_coords)]

    # If we still have geocoding results after potential EEZ fallback, return them
    if geocoded_locations:
        return geocoded_locations

    return None


def filter_cancellation_messages(warnings_data):
    """Filter out messages with no plottable navigational information, but try geocoding first"""
    filtered_warnings = []
    geocoded_count = 0
    filtered_count = 0
    index_messages = []

    for warning in warnings_data:
        original_coords = warning.get('coordinates')

        # Geocoding happens later in KML generation as fallback for warnings with no coordinates

        # Check if it should be filtered
        should_filter = should_filter_warning_message(warning)
        if should_filter:
            # Check if this is a warning index message for validation
            text = warning.get('description', '').upper()
            if 'WARNINGS IN FORCE' in text or ('ALL THE INFORCE WARNINGS' in text and 'ARE LISTED' in text):
                index_messages.append(warning)

            # Filter it out
            filtered_count += 1
            continue

        # Warning is plottable, keep it
        filtered_warnings.append(warning)


    # Validate warnings referenced in index messages
    if index_messages:
        validate_warnings_from_index(filtered_warnings, index_messages)

    return filtered_warnings


def create_warnings_kml(warnings_data, output_path, color_abgr=None, use_custom_colors=True, single_color_hex=None, opacity_percent=80, report_progress=None, cache_dir=None):
    """Create KML file from warnings data with category-specific colors"""
    ET.register_namespace('', 'http://www.opengis.net/kml/2.2')

    # Note: color_abgr parameter kept for backward compatibility but not used
    # Colors are now determined by warning category

    # Filter out pure cancellation messages
    warnings_data = filter_cancellation_messages(warnings_data)

    # Create root KML structure
    kml = ET.Element('kml', xmlns='http://www.opengis.net/kml/2.2')
    doc = ET.SubElement(kml, 'Document')
    doc_name = ET.SubElement(doc, 'name')
    doc_name.text = 'Global Maritime Navigation Warnings'

    placemark_count = 0

    # Define warning categories and their icons
    categories = [
        'ICE', 'DANGER', 'OPERATIONS', 'OBSTRUCTIONS',
        'NAVIGATION', 'GENERAL'
    ]

    # Create styles for each category with category-specific colors
    for category in categories:
        style = ET.SubElement(doc, 'Style', id=f'{category.lower()}Style')
        category_color = get_warning_color(category, use_custom_colors, single_color_hex, opacity_percent)

        icon_style = ET.SubElement(style, 'IconStyle')
        ET.SubElement(icon_style, 'color').text = category_color
        ET.SubElement(icon_style, 'scale').text = '1.0'
        icon = ET.SubElement(icon_style, 'Icon')
        ET.SubElement(icon, 'href').text = get_warning_icon_url(category, use_custom_colors)

        label_style = ET.SubElement(style, 'LabelStyle')
        ET.SubElement(label_style, 'color').text = category_color
        ET.SubElement(label_style, 'scale').text = '1.0'

        line_style = ET.SubElement(style, 'LineStyle')
        ET.SubElement(line_style, 'color').text = category_color
        ET.SubElement(line_style, 'width').text = '3'

        poly_style = ET.SubElement(style, 'PolyStyle')
        ET.SubElement(poly_style, 'color').text = category_color.replace('ff', '80')  # Semi-transparent
        ET.SubElement(poly_style, 'fill').text = '1'
        ET.SubElement(poly_style, 'outline').text = '1'

    # Group warnings by category
    category_groups = {}
    for warning in warnings_data:
        # Categorize the warning
        category = categorize_warning(warning)
        if category not in category_groups:
            category_groups[category] = []
        category_groups[category].append((warning, category))

    # Create folders for each category
    for category, warning_category_pairs in category_groups.items():
        folder = ET.SubElement(doc, 'Folder')
        folder_name = ET.SubElement(folder, 'name')
        # Convert category name to readable format
        readable_category = category.replace('_', ' ').title()
        folder_name.text = readable_category
        ET.SubElement(folder, 'open').text = '0'

        for warning, category in warning_category_pairs:
            coords = warning.get('coordinates')

            # If warning has multiple coordinate sets, create separate placemarks for each
            geometry_created = False
            geocoded_coords_list = None
            geometry_created_for_warning = False
            if coords and isinstance(coords, list) and len(coords) > 0:
                for coord_set in coords:
                    geometry_for_this_set = False
                    placemark = ET.SubElement(folder, 'Placemark')
                    placemark_count += 1
                    geometry_created_for_warning = True  # At least one placemark created
                    name_elem = ET.SubElement(placemark, 'name')

                    # Generate descriptive name based on coordinate type
                    navarea_code = warning.get('navarea', warning.get('navArea', 'Unknown'))
                    msg_number = warning.get('msg_number', warning.get('msgNumber', 'Unknown'))
                    msg_year = warning.get('msg_year', warning.get('msgYear', 'Unknown'))
                    navarea_display = get_navarea_display_name(navarea_code)
                    base_name = f"{navarea_display} {msg_number}/{msg_year}"

                    # Create name based on coordinate set type
                    if isinstance(coord_set, list) and len(coord_set) >= 2:
                        coord_type = None
                        coord_data = None

                        if isinstance(coord_set[0], str):
                            # Named coordinate set (handle both 2-element and 3-element sets)
                            coord_type = coord_set[0]
                            coord_data = coord_set[1]

                        # Try specific geometry creation first
                        geometry_created = False
                        if coord_type and coord_type.startswith('CIRCULAR_AREA') and isinstance(coord_data, list) and len(coord_data) > 2:
                            geometry_created = True

                        # Remove marker names - only show icons
                        name_elem.text = ""

                    # Categorize warning and assign appropriate style
                    category = categorize_warning(warning)
                    style_url = ET.SubElement(placemark, 'styleUrl')
                    style_url.text = f'#{category.lower()}Style'

                    # Create description with feature-specific text (after category is determined)
                    feature_text = None

                    # Extract feature-specific description from coordinate set type
                    if isinstance(coord_set, list) and len(coord_set) >= 1 and isinstance(coord_set[0], str):
                        coord_type = coord_set[0]

                        # Check if this is a labeled feature (POINT_A, POINT_B, CIRCULAR_AREA_WW, etc.)
                        import re
                        label_match = re.search(r'(?:POINT|AREA|CIRCULAR_AREA|BOUNDARY_AREA|COORDINATES|TRACKLINE)_([A-Z]+)$', coord_type)
                        if label_match:
                            label = label_match.group(1)
                            # Extract the feature-specific text from the full warning description
                            full_text = warning.get('description', warning.get('content', warning.get('text', '')))
                            # Extract feature-specific description using subtraction method
                            coords = warning.get('coordinates', [])
                            feature_text = extract_feature_description(full_text, coords, coord_set)

                    desc = create_warning_description(warning, category, feature_text)

                    desc_elem = ET.SubElement(placemark, 'description')
                    desc_elem.text = desc

                    # Add geometry for this coordinate set
                    if isinstance(coord_set, list) and len(coord_set) >= 2:
                        coord_type = None
                        coord_data = None

                        if isinstance(coord_set[0], str):
                            # Named coordinate set (handle both 2-element and 3-element sets)
                            coord_type = coord_set[0]
                            coord_data = coord_set[1]

                        # Simple POINT geometry creation for POINT types
                        if coord_type and coord_type.startswith('POINT') and coord_data and isinstance(coord_data, list) and len(coord_data) >= 1:
                            if len(coord_data) >= 1 and isinstance(coord_data[0], (list, tuple)) and len(coord_data[0]) >= 2:
                                lat, lon = coord_data[0][0], coord_data[0][1]
                                if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and not (math.isnan(lat) or math.isnan(lon)):
                                    point = ET.SubElement(placemark, 'Point')
                                    coord_elem = ET.SubElement(point, 'coordinates')
                                    coord_elem.text = f"{lon},{lat},0"
                                    # Skip the rest of geometry creation for this coordinate set
                                    continue

                        if coord_type and coord_type.startswith('CIRCULAR_AREA') and isinstance(coord_data, list) and len(coord_data) > 2:
                            # Create polygon for circular area approximation (coordinates already calculated)
                            geometry_created = True
                            polygon = ET.SubElement(placemark, 'Polygon')
                            ET.SubElement(polygon, 'extrude').text = '0'
                            altitude_mode = ET.SubElement(polygon, 'altitudeMode')
                            altitude_mode.text = 'clampToGround'
                            outer = ET.SubElement(polygon, 'outerBoundaryIs')
                            linear_ring = ET.SubElement(outer, 'LinearRing')
                            coord_elem = ET.SubElement(linear_ring, 'coordinates')

                            coord_string = ""
                            for lat, lon in coord_data:
                                if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and not (math.isnan(lat) or math.isnan(lon)):
                                    coord_string += f"{lon},{lat},0 "
                            coord_elem.text = coord_string.strip()
                        elif coord_type.startswith('CIRCULAR_AREA') and isinstance(coord_data, dict) and 'center' in coord_data and 'radius_nm' in coord_data:
                            # Create polygon for circular area from center/radius specification
                            center_lat, center_lon = coord_data['center']
                            radius_nm = coord_data['radius_nm']

                            # Convert nautical miles to degrees (1 NM ≈ 0.01667 degrees)
                            radius_deg = radius_nm * 0.01667

                            # Create circular area approximation with smooth 64-point circles
                            circular_coords = create_circle_approximation(center_lat, center_lon, radius_deg, num_points=64)

                            polygon = ET.SubElement(placemark, 'Polygon')
                            ET.SubElement(polygon, 'extrude').text = '0'
                            ET.SubElement(polygon, 'tessellate').text = '1'  # Ensure proper rendering over Earth's surface
                            # Remove altitudeMode for ocean polygons - let Google Earth handle altitude
                            outer = ET.SubElement(polygon, 'outerBoundaryIs')
                            linear_ring = ET.SubElement(outer, 'LinearRing')
                            coord_elem = ET.SubElement(linear_ring, 'coordinates')

                            coord_string = ""
                            for lat, lon in circular_coords:
                                if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and not (math.isnan(lat) or math.isnan(lon)):
                                    coord_string += f"{lon},{lat},0 "
                            coord_elem.text = coord_string.strip()

                        elif coord_type.startswith('BOUNDARY_AREA'):
                            # Create polygon for boundary area
                            polygon = ET.SubElement(placemark, 'Polygon')
                            ET.SubElement(polygon, 'extrude').text = '0'
                            altitude_mode = ET.SubElement(polygon, 'altitudeMode')
                            altitude_mode.text = 'clampToGround'
                            outer = ET.SubElement(polygon, 'outerBoundaryIs')
                            linear_ring = ET.SubElement(outer, 'LinearRing')
                            coord_elem = ET.SubElement(linear_ring, 'coordinates')

                            coord_string = ""
                            for lat, lon in coord_data:
                                if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and not (math.isnan(lat) or math.isnan(lon)):
                                    coord_string += f"{lon},{lat},0 "

                            # Ensure polygon is closed by repeating the first coordinate at the end
                            if coord_data and len(coord_data) > 0 and coord_string.strip():
                                first_lat, first_lon = coord_data[0]
                                if isinstance(first_lat, (int, float)) and isinstance(first_lon, (int, float)):
                                    coord_string += f"{first_lon},{first_lat},0 "

                            coord_elem.text = coord_string.strip()

                        elif coord_type.startswith('CABLE_TRACKLINE') and isinstance(coord_data, list) and len(coord_data) > 1:
                            # Create linestring for trackline
                            linestring = ET.SubElement(placemark, 'LineString')
                            ET.SubElement(linestring, 'extrude').text = '0'
                            altitude_mode = ET.SubElement(linestring, 'altitudeMode')
                            altitude_mode.text = 'clampToGround'
                            coord_elem = ET.SubElement(linestring, 'coordinates')

                            coord_string = ""
                            for lat, lon in coord_data:
                                if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and not (math.isnan(lat) or math.isnan(lon)):
                                    coord_string += f"{lon},{lat},0 "
                            coord_elem.text = coord_string.strip()

                        elif coord_type.startswith('TRACKLINE_BERTH_AREA') and isinstance(coord_data, list) and len(coord_data) >= 3:
                            # Create polygon for trackline berth area (both labeled and unlabeled)
                            polygon = ET.SubElement(placemark, 'Polygon')
                            ET.SubElement(polygon, 'extrude').text = '0'
                            altitude_mode = ET.SubElement(polygon, 'altitudeMode')
                            altitude_mode.text = 'clampToGround'
                            outer = ET.SubElement(polygon, 'outerBoundaryIs')
                            linear_ring = ET.SubElement(outer, 'LinearRing')
                            coord_elem = ET.SubElement(linear_ring, 'coordinates')

                            coord_string = ""
                            for lat, lon in coord_data:
                                if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and not (math.isnan(lat) or math.isnan(lon)):
                                    coord_string += f"{lon},{lat},0 "

                            # Close the polygon by repeating the first coordinate (if not already closed)
                            if coord_data and len(coord_data) > 0:
                                first_lat, first_lon = coord_data[0]
                                last_lat, last_lon = coord_data[-1]
                                # Only add first coordinate if polygon isn't already closed
                                if not (abs(first_lat - last_lat) < 1e-10 and abs(first_lon - last_lon) < 1e-10):
                                    if isinstance(first_lat, (int, float)) and isinstance(first_lon, (int, float)):
                                        coord_string += f"{first_lon},{first_lat},0 "

                            coord_elem.text = coord_string.strip()

                        elif coord_type.startswith('TRACKLINE') and not coord_type.endswith('_AREA') and isinstance(coord_data, list) and len(coord_data) > 1:
                            # Create linestring for regular trackline
                            linestring = ET.SubElement(placemark, 'LineString')
                            ET.SubElement(linestring, 'extrude').text = '0'
                            altitude_mode = ET.SubElement(linestring, 'altitudeMode')
                            altitude_mode.text = 'clampToGround'
                            coord_elem = ET.SubElement(linestring, 'coordinates')

                            coord_string = ""
                            for lat, lon in coord_data:
                                if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and not (math.isnan(lat) or math.isnan(lon)):
                                    coord_string += f"{lon},{lat},0 "
                            coord_elem.text = coord_string.strip()

                        elif coord_type == 'GEOCODED_LOCATION' and isinstance(coord_data, list) and len(coord_data) == 2:
                            # Create point for geocoded location
                            lat, lon = coord_data[0], coord_data[1]
                            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and not (math.isnan(lat) or math.isnan(lon)):
                                point = ET.SubElement(placemark, 'Point')
                                coord_elem = ET.SubElement(point, 'coordinates')
                                coord_elem.text = f"{lon},{lat},0"

                        elif isinstance(coord_data, list) and len(coord_data) >= 1:
                            # Create point for single coordinates
                            if len(coord_data) == 2 and isinstance(coord_data[0], (int, float)) and isinstance(coord_data[1], (int, float)):
                                # Simple coordinate pair [lat, lon]
                                lat, lon = coord_data[0], coord_data[1]
                                if not (math.isnan(lat) or math.isnan(lon)):
                                    point = ET.SubElement(placemark, 'Point')
                                    coord_elem = ET.SubElement(point, 'coordinates')
                                    coord_elem.text = f"{lon},{lat},0"
                            elif len(coord_data) >= 1 and isinstance(coord_data[0], (list, tuple)) and len(coord_data[0]) >= 2:
                                # List of coordinate pairs
                                lat, lon = coord_data[0][0], coord_data[0][1] if len(coord_data[0]) >= 2 else (0, 0)
                                if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and not (math.isnan(lat) or math.isnan(lon)):
                                    point = ET.SubElement(placemark, 'Point')
                                    coord_elem = ET.SubElement(point, 'coordinates')
                                    coord_elem.text = f"{lon},{lat},0"

                        elif len(coord_set) >= 2 and isinstance(coord_set[0], (int, float)) and isinstance(coord_set[1], (int, float)):
                            # Simple coordinate pair - create point
                            lat, lon = coord_set[0], coord_set[1]
                            if not (math.isnan(lat) or math.isnan(lon)):
                                point = ET.SubElement(placemark, 'Point')
                                coord_elem = ET.SubElement(point, 'coordinates')
                                coord_elem.text = f"{lon},{lat},0"

                        else:
                            # No geometry created - try geocoding as final fallback
                            geocoded_coords_list = try_geocode_warning(warning, report_progress, cache_dir)
                    if geocoded_coords_list:
                        # Create separate placemarks for each geocoded location
                        for coords in geocoded_coords_list:
                            placemark = ET.SubElement(folder, 'Placemark')
                            placemark_count += 1
                            name_elem = ET.SubElement(placemark, 'name')

                            # Remove marker names - only show icons
                            name_elem.text = ""

                            # Categorize warning and assign appropriate style
                            category = categorize_warning(warning)
                            style_url = ET.SubElement(placemark, 'styleUrl')
                            style_url.text = f'#{category.lower()}Style'

                            # Create description
                            desc = create_warning_description(warning, category)
                            desc_elem = ET.SubElement(placemark, 'description')
                            desc_elem.text = desc

                            # Create point at geocoded location
                            lat, lon = coords
                            point = ET.SubElement(placemark, 'Point')
                            coord_elem = ET.SubElement(point, 'coordinates')
                            coord_elem.text = f"{lon},{lat},0"
                    elif not geometry_created_for_warning:
                        # No geocoding possible and no geometry created - create single placemark at 0,0 as final fallback
                        placemark = ET.SubElement(folder, 'Placemark')
                        placemark_count += 1
                        name_elem = ET.SubElement(placemark, 'name')

                        # Remove marker names - only show icons
                        name_elem.text = ""

                        # Categorize warning and assign appropriate style
                        category = categorize_warning(warning)
                        style_url = ET.SubElement(placemark, 'styleUrl')
                        style_url.text = f'#{category.lower()}Style'

                        # Create description
                        desc = create_warning_description(warning, category)
                        desc_elem = ET.SubElement(placemark, 'description')
                        desc_elem.text = desc

                        # Create point at 0,0 as final fallback
                        point = ET.SubElement(placemark, 'Point')
                        coord_elem = ET.SubElement(point, 'coordinates')
                        coord_elem.text = "0,0,0"

            else:
                # Warning has no coordinates at all - try geocoding
                geocoded_coords_list = try_geocode_warning(warning, report_progress, cache_dir)
                if geocoded_coords_list:
                    # Create separate placemarks for each geocoded location
                    for coords in geocoded_coords_list:
                        placemark = ET.SubElement(folder, 'Placemark')
                        placemark_count += 1
                        name_elem = ET.SubElement(placemark, 'name')

                        # Remove marker names - only show icons
                        name_elem.text = ""

                        # Categorize warning and assign appropriate style
                        category = categorize_warning(warning)
                        style_url = ET.SubElement(placemark, 'styleUrl')
                        style_url.text = f'#{category.lower()}Style'

                        # Create description
                        desc = create_warning_description(warning, category)
                        desc_elem = ET.SubElement(placemark, 'description')
                        desc_elem.text = desc

                        # Create point at geocoded location
                        lat, lon = coords
                        point = ET.SubElement(placemark, 'Point')
                        coord_elem = ET.SubElement(point, 'coordinates')
                        coord_elem.text = f"{lon},{lat},0"
                else:
                    # No geocoding possible - create single placemark at 0,0 as final fallback
                    placemark = ET.SubElement(folder, 'Placemark')
                    placemark_count += 1
                    name_elem = ET.SubElement(placemark, 'name')

                    # Remove marker names - only show icons
                    name_elem.text = ""

                    # Categorize warning and assign appropriate style
                    category = categorize_warning(warning)
                    style_url = ET.SubElement(placemark, 'styleUrl')
                    style_url.text = f'#{category.lower()}Style'

                    # Create description
                    desc = create_warning_description(warning, category)
                    desc_elem = ET.SubElement(placemark, 'description')
                    desc_elem.text = desc

                    # Create point at 0,0 as final fallback
                    point = ET.SubElement(placemark, 'Point')
                    coord_elem = ET.SubElement(point, 'coordinates')
                    coord_elem.text = "0,0,0"

    # Write KML file
    try:
        tree = ET.ElementTree(kml)
        tree.write(output_path, encoding='utf-8', xml_declaration=True)
        return placemark_count
    except Exception as e:
        return 0

def refresh_dynamic_caches():
    """Refresh navigation warnings dynamic cache"""
    print("NAV WARNINGS: Refreshing dynamic cache...")

    try:
        from core.config import NGA_MSI_NAVWARNINGS_URL
        cache_dir = Path(__file__).parent.parent / "cache" / "dynamic" / "nav_warnings"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Download latest navigation warnings
        print("NAV WARNINGS: Downloading latest navigation warnings...")

        # Try the NGA MSI API
        nav_urls = [
            NGA_MSI_NAVWARNINGS_URL,
            "https://msi.nga.mil/api/publications/broadcast-warn",
            "https://msi.nga.mil/api/publications/weekly"
        ]

        nav_data = None
        for url in nav_urls:
            try:
                print(f"NAV WARNINGS: Trying {url}")
                response = requests.get(url, timeout=60, headers={'User-Agent': 'Mozilla/5.0'})

                if response.status_code == 200:
                    try:
                        nav_data = response.json()
                        if nav_data:
                            print(f"NAV WARNINGS: Successfully got data from {url}")
                            break
                    except json.JSONDecodeError:
                        # Try to save as text if not JSON
                        nav_data = {"text": response.text, "url": url}
                        print(f"NAV WARNINGS: Got text data from {url}")
                        break
                else:
                    print(f"NAV WARNINGS: HTTP {response.status_code} from {url}")
                    continue
            except Exception as e:
                print(f"NAV WARNINGS: Error with {url}: {e}")
                continue

        if not nav_data:
            print("NAV WARNINGS: Failed to download from any source")
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        cache_file = cache_dir / f"nav_warnings_{timestamp}.json"

        # Save the data
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({
                "data": nav_data,
                "timestamp": timestamp,
                "source_url": url if 'url' in locals() else NGA_MSI_NAVWARNINGS_URL
            }, f, indent=2)

        print(f"NAV WARNINGS: Downloaded navigation warnings, size = {cache_file.stat().st_size} bytes")
        print("NAV WARNINGS: Dynamic cache refreshed successfully")
        return True
    except Exception as e:
        print(f"NAV WARNINGS: Dynamic cache refresh failed: {e}")
        return False
