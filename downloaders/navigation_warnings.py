"""
Navigation warnings data downloader and processor.

This module handles downloading navigation warning data and converting it to KML format.
"""

import os
import json
import datetime
import re
from pathlib import Path
from core.types import LayerTask


def extract_warning_components(text: str) -> tuple:
    """Extract warning components by splitting on lettered sections (A., B., C., etc.)

    Returns:
        tuple: (prefix, feature_list, suffix)
            - prefix: Text before the first lettered section
            - feature_list: List of feature texts for each lettered section
            - suffix: Text after the last lettered section
    """
    # Find all lettered sections (A., B., C., etc.)
    # This regex matches one or more capital letters followed by a period and space
    section_pattern = r'\b([A-Z]+)\.\s+'

    # Find all matches
    matches = list(re.finditer(section_pattern, text))

    if not matches:
        # No sections found, return empty feature list
        return text.strip(), [], ""

    # Split the text into sections
    feature_list = []
    prefix = text[:matches[0].start()].strip()

    for i, match in enumerate(matches):
        section_start = match.start()
        section_label = match.group(1)

        # Find the end of this section (start of next section or end of text)
        if i < len(matches) - 1:
            section_end = matches[i + 1].start()
        else:
            section_end = len(text)

        # Extract the section text (without the label)
        section_text = text[section_start:section_end].strip()
        # Remove the label prefix
        section_text = re.sub(r'^[A-Z]+\.\s+', '', section_text)

        feature_list.append(section_text)

    # Everything after the last section
    suffix = ""
    if matches:
        last_match = matches[-1]
        suffix_start = last_match.start()
        # Find where the last section ends
        last_section_text = text[suffix_start:]
        # Find the actual end of content (look for end markers or just use the rest)
        suffix = ""

    return prefix, feature_list, suffix


def process(task: LayerTask, report_progress, output_dir: str, cache_dir: str) -> bool:
    """Synchronous version of navigation warnings processing"""
    try:
        # Find the latest nav warnings JSON file
        nav_cache_dir = Path(cache_dir) / "raw_source_data" / "dynamic" / "nav_warnings"
        nav_files = list(nav_cache_dir.glob("nav_warnings_*.json"))

        if not nav_files:
            # No cache files found, create placeholder
            report_progress(0, "No navigation warnings cache found, creating placeholder")
            with open(task.output_path, 'w', encoding='utf-8') as f:
                f.write("""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Navigation Warnings</name>
    <Placemark>
      <name>No Navigation Warnings Available</name>
      <Point>
        <coordinates>0,0,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>""")
            report_progress(task.weight, f"Created placeholder {task.name} KML")
            return True

        # Use the most recent file
        nav_file = max(nav_files, key=lambda x: x.stat().st_mtime)
        report_progress(0, f"Processing navigation warnings from {nav_file.name}")

        # Load the navigation warnings data
        with open(nav_file, 'r', encoding='utf-8') as f:
            nav_data = json.load(f)

        # Create KML content
        kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Navigation Warnings</name>
    <Style id="navWarningStyle">
      <IconStyle>
        <color>ff0000ff</color>
        <scale>0.8</scale>
        <Icon>
          <href>http://maps.google.com/mapfiles/kml/shapes/caution.png</href>
        </Icon>
      </IconStyle>
      <LineStyle>
        <color>ff0000ff</color>
        <width>3</width>
      </LineStyle>
      <PolyStyle>
        <color>40ff0000</color>
        <outline>1</outline>
      </PolyStyle>
    </Style>"""

        features = nav_data.get('features', [])
        if not features:
            # Empty warnings
            kml_content += """
    <Placemark>
      <name>No Active Navigation Warnings</name>
      <description>No active navigation warnings found.</description>
      <Point>
        <coordinates>0,0,0</coordinates>
      </Point>
    </Placemark>"""
        else:
            # Create placemarks for each warning
            for i, feature in enumerate(features):
                properties = feature.get('properties', {})
                geometry = feature.get('geometry', {})

                name = properties.get('title', f'NAV WARNING {i+1}')
                description = properties.get('description', 'Navigation warning')

                # Format description with HTML
                html_desc = f"<b>{name}</b><br>"
                html_desc += f"<b>NAVAREA:</b> {properties.get('navarea', 'Unknown')}<br>"
                if properties.get('msg_number') and properties.get('msg_year'):
                    html_desc += f"<b>Warning:</b> {properties.get('msg_number')}/{properties.get('msg_year')}<br>"
                html_desc += f"<b>Source:</b> {properties.get('source', 'NGA MSI')}<br><br>"
                html_desc += description.replace('\n', '<br>')

                geom_type = geometry.get('type', '')
                coordinates = geometry.get('coordinates', [])

                if geom_type == 'Point' and coordinates:
                    # Single point
                    lon, lat = coordinates[0], coordinates[1] if len(coordinates) >= 2 else (0, 0)
                    kml_content += f"""
    <Placemark>
      <name>{name}</name>
      <description>{html_desc}</description>
      <styleUrl>#navWarningStyle</styleUrl>
      <Point>
        <coordinates>{lon},{lat},0</coordinates>
      </Point>
    </Placemark>"""

                elif geom_type == 'LineString' and coordinates:
                    # Line string
                    coord_str = ' '.join([f"{lon},{lat},0" for lon, lat in coordinates])
                    kml_content += f"""
    <Placemark>
      <name>{name}</name>
      <description>{html_desc}</description>
      <styleUrl>#navWarningStyle</styleUrl>
      <LineString>
        <coordinates>{coord_str}</coordinates>
      </LineString>
    </Placemark>"""

                elif geom_type == 'Polygon' and coordinates:
                    # Polygon (coordinates is array of rings)
                    outer_ring = coordinates[0] if coordinates else []
                    if outer_ring:
                        coord_str = ' '.join([f"{lon},{lat},0" for lon, lat in outer_ring])
                        kml_content += f"""
    <Placemark>
      <name>{name}</name>
      <description>{html_desc}</description>
      <styleUrl>#navWarningStyle</styleUrl>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>{coord_str}</coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>"""

        kml_content += """
  </Document>
</kml>"""

        # Write the KML file
        with open(task.output_path, 'w', encoding='utf-8') as f:
            f.write(kml_content)

        total_warnings = len(features)
        report_progress(task.weight, f"Created {task.name} KML with {total_warnings} navigation warnings")
        return True

    except Exception as e:
        report_progress(0, f"Error creating navigation warnings KML: {e}")
        import traceback
        traceback.print_exc()
        return False

def process_async(session, task, report_progress, output_dir: str, cache_dir: str) -> bool:
    """Async version of navigation warnings processing"""
    # For now, same as sync version
    return process(task, report_progress, output_dir, cache_dir)

def refresh_dynamic_caches():
    """Refresh navigation warnings dynamic cache"""
    print("NAV WARNINGS: Refreshing dynamic cache...")

    try:
        cache_dir = Path(__file__).parent.parent / "cache" / "raw_source_data" / "dynamic" / "nav_warnings"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Use the real fetching logic from navwarnings_fetcher
        print("NAV WARNINGS: Downloading latest navigation warnings...")
        from .navwarnings_fetcher import get_curated_current_warnings

        # Create a cache directory for URL caching
        cache_dir_str = str(cache_dir.parent.parent / "_cache")
        warnings = get_curated_current_warnings(cache_dir=cache_dir_str)

        if not warnings:
            print("NAV WARNINGS: No warnings retrieved, creating empty cache")
            warnings = []

        # Convert warnings to GeoJSON-like structure for storage
        features = []
        for warning in warnings:
            # Extract coordinates from the warning
            coordinates = warning.get('coordinates', [])
            if coordinates:
                # Handle different coordinate formats
                geom_coords = []
                geom_type = "Point"

                if isinstance(coordinates, list) and coordinates:
                    coord_data = coordinates[0] if len(coordinates) == 1 else coordinates

                    if isinstance(coord_data, list) and len(coord_data) >= 2:
                        # Single coordinate pair [lat, lon]
                        lat, lon = coord_data[0], coord_data[1]
                        geom_coords = [lon, lat]  # GeoJSON uses [lon, lat]
                        geom_type = "Point"
                    elif isinstance(coord_data, list) and isinstance(coord_data[0], list):
                        # Multiple coordinate pairs
                        if len(coord_data) == 1:
                            # Single point in list
                            lat, lon = coord_data[0][0], coord_data[0][1]
                            geom_coords = [lon, lat]
                            geom_type = "Point"
                        elif len(coord_data) >= 2:
                            # LineString or Polygon
                            coords_list = []
                            for coord in coord_data:
                                if isinstance(coord, list) and len(coord) >= 2:
                                    lat, lon = coord[0], coord[1]
                                    coords_list.append([lon, lat])

                            if len(coords_list) >= 2:
                                geom_coords = coords_list
                                geom_type = "LineString"
                            elif len(coords_list) == 1:
                                geom_coords = coords_list[0]
                                geom_type = "Point"

                if geom_coords:
                    feature = {
                        "type": "Feature",
                        "properties": {
                            "navarea": warning.get('navarea', ''),
                            "msg_number": warning.get('msg_number', ''),
                            "msg_year": warning.get('msg_year', ''),
                            "title": f"NAV WARNING {warning.get('msg_number', '')}/{warning.get('msg_year', '')}",
                            "description": warning.get('description', ''),
                            "source": warning.get('source', ''),
                            "timestamp": warning.get('timestamp', '')
                        },
                        "geometry": {
                            "type": geom_type,
                            "coordinates": geom_coords
                        }
                    }
                    features.append(feature)

        nav_data = {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "total_warnings": len(features),
                "last_updated": datetime.datetime.now().isoformat(),
                "source": "NGA MSI Navigation Warnings"
            }
        }

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
        cache_file = cache_dir / f"nav_warnings_{timestamp}.json"

        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(nav_data, f, indent=2)

        print(f"NAV WARNINGS: Retrieved {len(features)} navigation warnings, size = {cache_file.stat().st_size} bytes")
        print("NAV WARNINGS: Dynamic cache refreshed successfully")
        return True
    except Exception as e:
        print(f"NAV WARNINGS: Dynamic cache refresh failed: {e}")
        import traceback
        traceback.print_exc()
        return False