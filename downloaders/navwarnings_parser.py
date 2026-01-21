"""
Navigation Warnings Parser
Contains all parsing and coordinate extraction functions for navigation warnings.
"""

import re
import math
from typing import List, Tuple, Optional, Union, Any


def extract_navarea_from_memo_name(memo_name: str) -> str:
    """Extract NAVAREA code from memorandum name"""
    # Extract the NAVAREA identifier from the memo name
    # Check more specific patterns first to avoid conflicts
    if "HYDROPAC" in memo_name:
        return "HYDROPAC"
    elif "HYDROARC" in memo_name:
        return "HYDROARC"
    elif "HYDROLANT" in memo_name:
        return "HYDROLANT"
    elif "NAVAREA IV" in memo_name or "MemIV" in memo_name:
        return "IV"
    elif "NAVAREA XII" in memo_name or "MemXII" in memo_name:
        return "XII"
    elif "MemPAC" in memo_name:
        return "HYDROPAC"
    elif "MemLAN" in memo_name:
        return "HYDROLANT"
    elif "MemARC" in memo_name:
        return "HYDROARC"
    # Fallback checks
    elif "US Atlantic" in memo_name:
        return "IV"
    elif "Arctic" in memo_name:
        return "HYDROARC"
    elif "Atlantic" in memo_name:
        return "HYDROLANT"
    elif "Pacific" in memo_name:
        return "XII"  # NAVAREA XII is the only Pacific NAVAREA
    return ""


def extract_title_from_text(text: str) -> str:
    """Extract warning title from text"""
    lines = text.strip().split('\n')
    if lines:
        title = lines[0].strip()
        # Remove common prefixes
        title = re.sub(r'^(NAVAREA|HYDRO)\s+\w+\s+\d+/\d+\s+', '', title, flags=re.IGNORECASE)
        return title
    return "Navigation Warning"


def _is_pure_cancellation(text: str) -> bool:
    """Check if warning is a pure cancellation"""
    text_upper = text.upper()
    return ('CANCEL' in text_upper and
            ('THIS MESSAGE IS CANCELLED' in text_upper or
             'MESSAGE IS CANCELLED' in text_upper or
             'WARNING IS CANCELLED' in text_upper))


def _is_general_notice(text: str) -> bool:
    """Check if warning is a general notice"""
    text_upper = text.upper()
    return ('GENERAL NOTICE' in text_upper or
            'GENERAL NOTICES' in text_upper or
            text_upper.startswith('GENERAL '))


def create_warning_description(warning: dict, category: str = None, feature_text: str = None) -> str:
    """Create HTML description for warning

    Args:
        warning: Warning dictionary
        category: Warning category
        feature_text: If provided, use this specific text instead of full warning description
    """
    # Handle both API and memorandum warning formats
    navarea = warning.get('navarea', warning.get('navArea', 'Unknown'))
    msg_number = warning.get('msg_number', warning.get('msgNumber', 'Unknown'))
    msg_year = warning.get('msg_year', warning.get('msgYear', warning.get('year', 'Unknown')))

    description = f"<b>NAVAREA:</b> {navarea}<br>"
    description += f"<b>Warning:</b> {msg_number}/{msg_year}<br>"

    # Add category information
    if category:
        # Convert category name to more readable format
        readable_category = category.replace('_', ' ').title()
        description += f"<b>Category:</b> {readable_category}<br><br>"
    else:
        description += "<br>"

    # Add status if available (API warnings)
    status = warning.get('status')
    if status:
        description += f"<b>Status:</b> {status}<br><br>"

    if 'title' in warning and warning['title']:
        description += f"<b>Title:</b> {warning['title']}<br><br>"

    description += "<b>Description:</b><br>"
    # Use feature_text if provided, otherwise use full description
    if feature_text:
        desc_text = feature_text
    else:
        desc_text = warning.get('description', warning.get('content', warning.get('text', 'No description available')))
    description += desc_text.replace('\n', '<br>')
    description += "<br><br>"

    # Add coordinate information
    if 'coordinates' in warning and warning['coordinates']:
        coords = warning['coordinates']
        if isinstance(coords, list) and coords:
            # Check for special coordinate types
            if len(coords) == 1 and isinstance(coords[0], list) and len(coords[0]) == 2:
                coord_type, coord_data = coords[0]
                if coord_type == 'CIRCULAR_AREA' and isinstance(coord_data, dict):
                    center = coord_data.get('center', [])
                    radius_nm = coord_data.get('radius_nm', 0)
                    if len(center) >= 2:
                        lat, lon = center
                        try:
                            lat_val = float(lat)
                            lon_val = float(lon)
                            description += f"<b>Circular Area:</b><br>"
                            description += f"  Center: {lat_val:.4f}°N, {lon_val:.4f}°W<br>"
                            description += f"  Radius: {radius_nm:.1f} nautical miles<br>"
                        except (ValueError, TypeError):
                            description += f"<b>Circular Area:</b><br>"
                            description += f"  Center: {lat}°N, {lon}°W<br>"
                            description += f"  Radius: {radius_nm} nautical miles<br>"
                elif coord_type == 'TRACKLINE_AREA' and isinstance(coord_data, list):
                    description += f"<b>Trackline Area:</b> {len(coord_data)} coordinate points<br>"
                elif coord_type == 'FACILITY_LOCATIONS' and isinstance(coord_data, list):
                    description += f"<b>Facility Locations:</b> {len(coord_data)} coordinate points<br>"
                else:
                    # Fallback for unknown coordinate types
                    description += f"<b>Special Area ({coord_type}):</b> {len(coord_data) if hasattr(coord_data, '__len__') else 'N/A'} items<br>"
            elif isinstance(coords[0], list) and len(coords[0]) >= 2:
                # Count total coordinate points
                total_points = 0
                for coord_list in coords:
                    if isinstance(coord_list, list):
                        total_points += len(coord_list)

                description += f"<b>Area Boundary:</b> {len(coords)} coordinate sets ({total_points} total points)<br>"
            else:
                description += f"<b>Coordinates:</b> {len(coords)} coordinate sets<br>"

    return description


def parse_distance_to_nautical_miles(distance_str: str) -> Optional[float]:
    """Parse distance string to nautical miles"""
    if not distance_str:
        return None

    # Remove extra spaces and convert to uppercase
    distance_str = distance_str.strip().upper()

    # Handle written numbers
    written_numbers = {
        'ONE': 1, 'TWO': 2, 'THREE': 3, 'FOUR': 4, 'FIVE': 5,
        'SIX': 6, 'SEVEN': 7, 'EIGHT': 8, 'NINE': 9, 'TEN': 10
    }

    # Check for written numbers first
    for word, value in written_numbers.items():
        if distance_str.startswith(word):
            remaining = distance_str[len(word):].strip()
            if remaining in ('MILES', 'MILE', 'NM', 'NAUTICAL MILES'):
                return float(value)  # In navigation context, treat as nautical miles

    # Handle numeric formats
    # "5 MILES", "5 NAUTICAL MILES", "5 NM", "200 METERS", etc.
    match = re.search(r'(\d+(?:\.\d+)?)\s*(MILES?|METERS?|NM|NAUTICAL\s+MILES?)', distance_str)
    if match:
        value = float(match.group(1))
        unit = match.group(2)

        if 'METERS' in unit or 'METER' in unit:
            # Convert meters to nautical miles (1 NM = 1852 meters)
            return value / 1852.0
        elif 'NM' in unit or 'NAUTICAL' in unit or 'MILES' in unit or 'MILE' in unit:
            return value  # In navigation context, "miles" means nautical miles

    return None


def extract_circular_area(text: str) -> Optional[dict]:
    """Extract circular area information from text"""
    text_upper = text.upper()

    # Look for circular area patterns
    # "WITHIN 5 MILES OF 41-42.80N 070-30.30W"
    # "CIRCLE OF RADIUS 5 NM CENTERED ON 41-42.80N 070-30.30W"

    patterns = [
        r'WITHIN\s+([A-Z0-9\s.]+(?:MILES?|METERS?|NM|NAUTICAL\s+MILES?))\s+OF\s+([\d\-NSWE\s.]+)',
        r'AREA\s+WITHIN\s+([A-Z0-9\s.]+(?:MILES?|METERS?|NM|NAUTICAL\s+MILES?))\s+OF\s+([\d\-NSWE\s.]+)',
        r'CIRCLE\s+OF\s+RADIUS\s+([A-Z0-9\s.]+(?:MILES?|METERS?|NM|NAUTICAL\s+MILES?))\s+CENTERED\s+ON\s+([\d\-NSWE\s.]+)',
        r'RADIUS\s+([A-Z0-9\s.]+(?:MILES?|METERS?|NM|NAUTICAL\s+MILES?))\s+CENTERED?\s+ON\s+([\d\-NSWE\s.]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text_upper, re.IGNORECASE | re.DOTALL)
        if match:
            radius_str = match.group(1)
            center_str = match.group(2)

            radius_nm = parse_distance_to_nautical_miles(radius_str)
            if radius_nm is None:
                continue

            # Check for berth requests and add them to the radius
            berth_match = re.search(r'([A-Z0-9]+)\s*MILE\s*BERTH\s*REQUESTED', text_upper, re.IGNORECASE)
            if berth_match:
                berth_str = berth_match.group(1)
                berth_nm = parse_distance_to_nautical_miles(berth_str + " MILE")
                if berth_nm:
                    radius_nm += berth_nm

            # Extract center coordinates
            center_coords = extract_general_coordinates(center_str)
            if center_coords and len(center_coords) >= 1:
                center_lat, center_lon = center_coords[0]
                return {
                    'center': [center_lat, center_lon],
                    'radius_nm': radius_nm
                }

    return None


def _lines_intersect(p1: List[float], p2: List[float], p3: List[float], p4: List[float]) -> bool:
    """Check if two line segments intersect (simplified 2D check)"""
    def orientation(p, q, r):
        val = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
        if val == 0: return 0  # Colinear
        return 1 if val > 0 else 2  # Clockwise or counterclockwise

    o1 = orientation(p1, p2, p3)
    o2 = orientation(p1, p2, p4)
    o3 = orientation(p3, p4, p1)
    o4 = orientation(p3, p4, p2)

    if o1 != o2 and o3 != o4:
        return True

    return False


def expand_polygon_by_berth(coords: List[List[float]], berth_nm: float) -> List[List[float]]:
    """Expand a polygon by creating a larger bounding box"""
    if not coords or len(coords) < 3:
        return coords

    # Convert berth from nautical miles to approximate degrees
    # Use average latitude for longitude scaling
    avg_lat = sum(lat for lat, lon in coords) / len(coords)
    berth_deg_lat = berth_nm * 0.01667
    berth_deg_lon = berth_nm * 0.01667 / abs(math.cos(math.radians(avg_lat))) if avg_lat != 0 else berth_nm * 0.01667

    # Find bounding box
    lats = [lat for lat, lon in coords]
    lons = [lon for lat, lon in coords]

    min_lat = min(lats) - berth_deg_lat
    max_lat = max(lats) + berth_deg_lat
    min_lon = min(lons) - berth_deg_lon
    max_lon = max(lons) + berth_deg_lon

    # Create expanded rectangular boundary
    expanded_coords = [
        [min_lat, min_lon],
        [min_lat, max_lon],
        [max_lat, max_lon],
        [max_lat, min_lon]
    ]

    return expanded_coords


def create_trackline_berth_polygon(coords: List[List[float]], berth_nm: float) -> Optional[List[List[float]]]:
    """Create a berth polygon around a trackline"""
    if not coords or len(coords) < 2:
        return None

    # Convert berth from nautical miles to approximate degrees
    # Use average latitude for longitude scaling
    avg_lat = sum(lat for lat, lon in coords) / len(coords)
    berth_deg_lat = berth_nm * 0.01667
    berth_deg_lon = berth_nm * 0.01667 / abs(math.cos(math.radians(avg_lat))) if avg_lat != 0 else berth_nm * 0.01667

    if len(coords) == 2:
        # Simple 2-point case
        lat1, lon1 = coords[0]
        lat2, lon2 = coords[1]

        # Calculate direction vector
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        # Normalize direction vector
        dir_length = math.sqrt(dlat**2 + dlon**2)
        if dir_length > 0:
            dlat /= dir_length
            dlon /= dir_length

        # Calculate perpendicular vector (rotate 90 degrees)
        perp_lat = -dlon
        perp_lon = dlat

        # Scale vectors by berth distance
        dlat *= berth_deg_lat
        dlon *= berth_deg_lon
        perp_lat *= berth_deg_lat
        perp_lon *= berth_deg_lon

        # Extend the trackline at both ends by berth distance
        extended_lat1 = lat1 - dlat
        extended_lon1 = lon1 - dlon
        extended_lat2 = lat2 + dlat
        extended_lon2 = lon2 + dlon

        # Create the six corner points (rectangle with extended ends)
        p1_lat = extended_lat1 + perp_lat  # Start point + perpendicular
        p1_lon = extended_lon1 + perp_lon

        p2_lat = extended_lat1 - perp_lat  # Start point - perpendicular
        p2_lon = extended_lon1 - perp_lon

        p3_lat = extended_lat2 - perp_lat  # End point - perpendicular
        p3_lon = extended_lon2 - perp_lon

        p4_lat = extended_lat2 + perp_lat  # End point + perpendicular
        p4_lon = extended_lon2 + perp_lon

        # Return as polygon (closed shape)
        return [[p1_lat, p1_lon], [p2_lat, p2_lon], [p3_lat, p3_lon], [p4_lat, p4_lon]]

    else:
        # Multi-point trackline - use Shapely for accurate geodesic buffering
        try:
            from shapely.geometry import LineString
            from shapely.ops import transform
            from pyproj import CRS, Transformer
            from functools import partial

            # Create LineString from coordinates (Shapely expects lon, lat)
            line_coords = [(lon, lat) for lat, lon in coords]
            line = LineString(line_coords)

            # Compute centroid for AEQD centering
            centroid = line.centroid
            lon_0, lat_0 = centroid.x, centroid.y

            # Define custom AEQD CRS centered on the trackline
            aeqd_crs = CRS.from_proj4(
                f"+proj=aeqd +lat_0={lat_0} +lon_0={lon_0} +x_0=0 +y_0=0 +ellps=WGS84 +units=m +no_defs"
            )

            # Create transformers
            project = Transformer.from_crs(CRS.from_epsg(4326), aeqd_crs, always_xy=True).transform
            unproject = Transformer.from_crs(aeqd_crs, CRS.from_epsg(4326), always_xy=True).transform

            # Project the line and buffer
            projected_line = transform(project, line)
            buffer_distance_meters = berth_nm * 1852  # Convert nautical miles to meters (1 NM = 1852 meters)

            buffered_projected = projected_line.buffer(
                buffer_distance_meters,
                resolution=32,          # Higher resolution for smoother curves
                cap_style='round',      # Round ends
                join_style='round',     # Round joins for smooth turns
                mitre_limit=5.0
            )

            # Project back to WGS84
            buffered = transform(unproject, buffered_projected)

            # Ensure validity and resolve any self-intersections
            valid_buffer = buffered.buffer(0)

            # Extract coordinates from the Shapely polygon
            if valid_buffer.geom_type == 'Polygon':
                # Single polygon
                coords_list = list(valid_buffer.exterior.coords)
                # Convert to the format expected by KML generation
                return [[lat, lon] for lon, lat in coords_list]
            elif valid_buffer.geom_type == 'MultiPolygon':
                # Multiple polygons - return the largest one
                largest_poly = max(valid_buffer.geoms, key=lambda p: p.area)
                coords_list = list(largest_poly.exterior.coords)
                return [[lat, lon] for lon, lat in coords_list]
            else:
                # Fallback to convex hull approach if buffering fails
                all_offset_points = []
                for lat, lon in coords:
                    all_offset_points.extend([
                        [lat + berth_deg_lat, lon],  # Approximate offset
                        [lat - berth_deg_lat, lon],
                        [lat, lon + berth_deg_lon],
                        [lat, lon - berth_deg_lon]
                    ])
                hull_points = _convex_hull(all_offset_points)
                if hull_points and hull_points[0] != hull_points[-1]:
                    hull_points.append(hull_points[0][:])
                return hull_points

        except ImportError:
            # Fallback if Shapely/pyproj not available
            all_offset_points = []
            for lat, lon in coords:
                all_offset_points.extend([
                    [lat + berth_deg_lat, lon],
                    [lat - berth_deg_lat, lon],
                    [lat, lon + berth_deg_lon],
                    [lat, lon - berth_deg_lon]
                ])
            hull_points = _convex_hull(all_offset_points)
            if hull_points and hull_points[0] != hull_points[-1]:
                hull_points.append(hull_points[0][:])
            return hull_points

    return None


def extract_berth_point_area(text: str) -> Optional[dict]:
    """Extract circular area for berth requests around point coordinates"""
    text_upper = text.upper()

    # Check if there's a berth request
    berth_match = re.search(r'([A-Z0-9]+)\s*MILE\s*BERTH\s*REQUESTED', text_upper, re.IGNORECASE)
    if not berth_match:
        return None

    # Parse the berth distance
    berth_str = berth_match.group(1)
    berth_nm = parse_distance_to_nautical_miles(berth_str + " MILE")
    if berth_nm is None or berth_nm <= 0:
        return None

    # Extract coordinates
    coords = extract_general_coordinates(text)
    if not coords or len(coords) != 1:
        # Only handle single point coordinates with berth
        return None

    center_lat, center_lon = coords[0]
    return {
        'center': [center_lat, center_lon],
        'radius_nm': berth_nm
    }


def extract_labeled_area_coordinates(text: str) -> List[List]:
    """Extract coordinates from text with labeled sections (TRACKLINES JOINING, AREAS BOUND BY)"""
    text_upper = text.upper()
    results = []

    # Find all labeled sections (A., B., etc.) and extract coordinates from each
    labeled_pattern = r'\b([A-Z])\.\s*([^A-Z]*?)(?=\b[A-Z]\.\s*|\s*$)'
    matches = re.findall(labeled_pattern, text_upper, re.DOTALL)

    for label, section_text in matches:
        coords = extract_general_coordinates(section_text.strip())
        if coords:
            results.append([f'TRACKLINE_{label}', coords])
    else:
        # Fall back to original patterns for unlabeled coordinate groups
        # First try a simple trackline pattern that captures all coordinates after "TRACKLINE JOINING"
        simple_trackline_match = re.search(r'TRACKLINE(?:S)?\s+JOINING\s+([\d\-NSWE\s.,]+)', text_upper)
        if simple_trackline_match:
            # Extract all coordinates from the trackline
            trackline_text = simple_trackline_match.group(1)
            coords = extract_general_coordinates(trackline_text)
            if coords and len(coords) > 1:
                # Check for berth requests - if present, create a berth area instead of linestring
                berth_nm = None

                # First check for explicit berth distance
                berth_match = re.search(r'([A-Z0-9]+)\s*MILE\s*BERTH\s*REQUESTED', text_upper, re.IGNORECASE)
                if berth_match:
                    berth_str = berth_match.group(1)
                    berth_nm = parse_distance_to_nautical_miles(berth_str + " MILE")

                # If no explicit distance but "wide berth" is mentioned, default to 1 NM
                if not berth_nm or berth_nm <= 0:
                    if 'WIDE BERTH' in text_upper or 'BERTH REQUESTED' in text_upper:
                        berth_nm = 1.0  # Default to 1 nautical mile

                if berth_nm and berth_nm > 0:
                    # Create a berth polygon around the trackline
                    berth_polygon = create_trackline_berth_polygon(coords, berth_nm)
                    if berth_polygon:
                        results.append(['TRACKLINE_BERTH_AREA', berth_polygon])
                    else:
                        results.append(['TRACKLINE_AREA', coords])
                else:
                    results.append(['TRACKLINE_AREA', coords])
        else:
            # Pattern for "TRACKLINES JOINING" with multiple segments (original logic)
            trackline_pattern = r'TRACKLINES?\s+JOINING\s+([\d\-NSWE\s.,]+?)(?:\s+(?:AND|TO|THEN)\s+([\d\-NSWE\s.,]+?))*\s+(?:AND|TO|THEN)\s+([\d\-NSWE\s.,]+)'

    # Pattern for "AREA BOUND BY" or "AREAS BOUND BY"
            # Handle both comma-separated and word-separated coordinates
            area_pattern = r'(?:IN\s+)?AREA(?:S)?\s+BOUND\s+BY\s+([\d\-NSWE\s.,]+?)(?:\s*[,&]?\s*(?:AND|TO|THEN)?\s+([\d\-NSWE\s.,]+?))*\s*(?:AND|TO|THEN)?\s+([\d\-NSWE\s.,]+)'

            # Pattern for circular areas "AREA WITHIN X METERS/MILES OF [coordinates]"
            circle_pattern = r'AREA\s+WITHIN\s+(\d+(?:\.\d+)?)\s+(METERS?|MILES?|NAUTICAL\s+MILES?|NM)\s+OF\s+([\d\-NSWE\s.,]+)'

            patterns = [trackline_pattern, circle_pattern, area_pattern]

    for pattern in patterns:
        match = re.search(pattern, text_upper)
        if match:
            # Extract all coordinate groups from the match
            coord_groups = []
            for i in range(1, len(match.groups()) + 1):
                if match.group(i):
                    coord_groups.append(match.group(i).strip())

            # Parse each coordinate group
            parsed_coords = []
            for group in coord_groups:
                coords = extract_general_coordinates(group)
                if coords:
                    parsed_coords.extend(coords)

            if parsed_coords:
                # Check for berth requests and expand boundary areas
                berth_nm = 0

                # First check for explicit berth distance
                berth_match = re.search(r'(\d+(?:\.\d+)?)\s*MILE\s*BERTH\s*REQUESTED', text_upper, re.IGNORECASE)
                if berth_match:
                    berth_str = berth_match.group(1)
                    berth_nm = parse_distance_to_nautical_miles(berth_str + " MILE") or 0

                # If no explicit distance but "wide berth" is mentioned, default to 1 NM
                if berth_nm <= 0 and ('WIDE BERTH' in text_upper or 'BERTH REQUESTED' in text_upper):
                    berth_nm = 1.0  # Default to 1 nautical mile

                # Use appropriate type based on the pattern
                if pattern == circle_pattern:
                    # Handle circular areas: "AREA WITHIN X METERS/MILES OF [coordinates]"
                    if len(match.groups()) >= 4:
                        radius_value = float(match.group(1))
                        unit = match.group(2).upper()
                        coord_text = match.group(4)
                        center_coords = extract_general_coordinates(coord_text)

                        if center_coords and len(center_coords) == 1:
                            center_lat, center_lon = center_coords[0]

                            # Convert radius to degrees based on unit
                            if 'MILE' in unit or 'NM' in unit:
                                # Convert nautical miles to degrees (1 NM ≈ 0.01667 degrees)
                                radius_deg = radius_value * 0.01667
                            else:
                                # Assume meters: 1° ≈ 111 km = 111,000 meters
                                radius_deg = radius_value / 111000

                            # Create circular polygon (approximated as a polygon with many points)
                            circle_polygon = create_circle_approximation(center_lat, center_lon, radius_deg)
                            if circle_polygon:
                                results.append(['CIRCLE_AREA', circle_polygon])
                                break  # Found a pattern, stop looking

                elif pattern == area_pattern:
                    if berth_nm > 0:
                        # Expand boundary area by berth distance
                        expanded_coords = expand_polygon_by_berth(parsed_coords, berth_nm)
                        results.append(['BOUNDARY_AREA_BERTH', expanded_coords])
                    else:
                        results.append(['BOUNDARY_AREA', parsed_coords])
                else:
                    results.append(['TRACKLINE_AREA', parsed_coords])
                    break  # Found one pattern, stop looking

    return results


def create_circle_approximation(center_lat: float, center_lon: float, radius_deg: float, num_points: int = 64) -> List[List[float]]:
    """Create a circle approximation using points on the circumference"""
    points = []

    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        # Convert radius from degrees to actual distance approximation
        # This is a rough approximation - for more accuracy, would need proper geodesic calculations
        # Use negative angle for counter-clockwise winding (required for KML outer boundaries)
        lat_offset = radius_deg * math.sin(-angle)
        lon_offset = radius_deg * math.cos(-angle) / math.cos(math.radians(center_lat))

        lat = center_lat + lat_offset
        lon = center_lon + lon_offset
        points.append([lat, lon])

    # Close the circle
    points.append(points[0].copy())
    return points


def extract_general_coordinates(text: str) -> List[List[float]]:
    """Extract coordinate pairs from text using various formats"""
    coordinates = []


    # Pattern for decimal minutes coordinates (degrees + decimal minutes)
    # Supports: 32-23.5N 117-14.5W (32° 23.5' N, 117° 14.5' W)
    # Also handles trailing punctuation like periods
    dm_pattern = r'(\d{1,3})[°\-](\d{1,2}(?:\.\d{1,2})?)\s*([NS])\s+(\d{1,3})[°\-](\d{1,2}(?:\.\d{1,2})?)\s*([EW])\s*[.,]?\s*'

    # Try decimal minutes first (more specific) - find all matches
    dm_matches = list(re.finditer(dm_pattern, text, re.IGNORECASE))

    for match in dm_matches:
        try:
            lat_deg = int(match.group(1))
            lat_min = float(match.group(2))  # Decimal minutes
            lat_hem = match.group(3).upper()

            lon_deg = int(match.group(4))
            lon_min = float(match.group(5))  # Decimal minutes
            lon_hem = match.group(6).upper()

            # Convert to decimal degrees
            lat_decimal = lat_deg + lat_min/60
            if lat_hem == 'S':
                lat_decimal = -lat_decimal

            lon_decimal = lon_deg + lon_min/60
            if lon_hem == 'W':
                lon_decimal = -lon_decimal

            coordinates.append([lat_decimal, lon_decimal])

        except (ValueError, IndexError):
            continue

    # Pattern for DMS coordinates with degrees, minutes, seconds
    # Supports: 41°42'30"N 070°30'30"W, 41-42-30N 070-30-30W, etc.
    # Uses multiple separators to distinguish from decimal minutes
    dms_pattern = r'(\d{1,3})[°\-](\d{1,2})[°\-\'](\d{1,2})\s*([NS])\s+(\d{1,3})[°\-](\d{1,2})[°\-\'](\d{1,2})\s*([EW])\s*[.,]?\s*'

    for match in re.finditer(dms_pattern, text, re.IGNORECASE):
        try:
            lat_deg = int(match.group(1))
            lat_min = int(match.group(2))
            lat_sec = int(match.group(3))
            lat_hem = match.group(4).upper()

            lon_deg = int(match.group(5))
            lon_min = int(match.group(6))
            lon_sec = int(match.group(7))
            lon_hem = match.group(8).upper()

            # Convert to decimal degrees
            lat_decimal = lat_deg + lat_min/60 + lat_sec/3600
            if lat_hem == 'S':
                lat_decimal = -lat_decimal

            lon_decimal = lon_deg + lon_min/60 + lon_sec/3600
            if lon_hem == 'W':
                lon_decimal = -lon_decimal

            coordinates.append([lat_decimal, lon_decimal])

        except (ValueError, IndexError):
            continue

    return coordinates


def extract_coordinates_from_text(text: str) -> List:
    """Extract coordinates from warning text with smart parsing"""
    import re
    # Check for warnings with multiple lettered sections (A., B., C., etc.) - PRIORITY
    # This takes precedence over general trackline detection
    if re.search(r'\b[A-Z]\.\s', text):
        section_coords = extract_sectioned_coordinates(text)
        if section_coords:
            return section_coords

    # Check if this warning has tracklines (unlabeled) - only if no sections found
    if ('TRACKLINE' in text.upper() or 'TRACKLINES' in text.upper()):
        # This is a warning with tracklines
        coords = extract_general_coordinates(text)
        if coords and len(coords) >= 2:
            # Check for berth requests
            berth_nm = None

            # Check for "WITHIN X MILES/METERS OF" pattern
            within_match = re.search(r'WITHIN\s+([A-Z0-9]+(?:\.\d+)?)\s+(MILES?|METERS?)', text.upper())
            if within_match:
                distance_str = within_match.group(1)
                unit = within_match.group(2).upper()
                berth_nm = parse_distance_to_nautical_miles(distance_str + " " + unit)

            # Also check for berth requests
            if not berth_nm:
                berth_match = re.search(r'([A-Z0-9]+)\s*MILE\s*BERTH\s*REQUESTED', text.upper(), re.IGNORECASE)
                if berth_match:
                    berth_str = berth_match.group(1)
                    berth_nm = parse_distance_to_nautical_miles(berth_str + " MILE")

            # If no explicit distance but "wide berth" is mentioned, default to 1 NM
            if not berth_nm and ('WIDE BERTH' in text.upper() or 'BERTH REQUESTED' in text.upper()):
                berth_nm = 1.0  # Default to 1 nautical mile

            if berth_nm and berth_nm > 0:
                # Create berth polygon for this trackline
                berth_polygon = create_trackline_berth_polygon(coords, berth_nm)
                if berth_polygon:
                    return [['TRACKLINE_BERTH_AREA', berth_polygon]]
                else:
                    return [['TRACKLINE', coords]]
            else:
                return [['TRACKLINE', coords]]

    # Check for bounded areas
    if ('AREAS BOUND BY' in text.upper() or 'AREA BOUND BY' in text.upper()):
        # This is a warning with bounded areas
        labeled_coords = extract_labeled_area_coordinates(text)
        if labeled_coords:
            return labeled_coords

    # Check for boundary areas (simpler case without labeled sections)
    if 'BOUND BY' in text.upper():
        coords = extract_general_coordinates(text)
        if coords and len(coords) >= 3:
            # Reverse coordinates to ensure counter-clockwise winding for KML compatibility
            coords_reversed = list(reversed(coords))
            # Return boundary area without berth expansion (berth only for points/lines)
            return [['BOUNDARY_AREA', coords_reversed]]

    # Check for circular areas with radius specifications
    circular_area = extract_circular_area(text)
    if circular_area:
        return [['CIRCULAR_AREA', circular_area]]

    # Check for berth requests with point coordinates
    berth_point_area = extract_berth_point_area(text)
    if berth_point_area:
        return [['CIRCULAR_AREA', berth_point_area]]

    # Check if this is a facility location warning
    if ('COMMUNICATION FACILITIES' in text.upper() or
        'WEATHER MESSAGE SERVICES UNRELIABLE' in text.upper() or
        'MOBILE OFFSHORE DRILLING UNITS' in text.upper() or
        'MODU' in text.upper() or
        'OCEAN BOTTOM MOORINGS' in text.upper() or
        'MOORINGS DEPLOYED' in text.upper()):
        coords = extract_general_coordinates(text)
        if coords:
            if len(coords) > 1:
                return [['FACILITY_LOCATIONS', coords]]
            else:
                return [['FACILITY_POINT', coords]]

    # Check for depth reports or similar point data that shouldn't be polygons
    if 'DEPTHS REPORTED' in text.upper() or 'METERS IN' in text.upper():
        # Extract coordinates but treat as individual points, not a boundary
        coords = extract_general_coordinates(text)
        if coords:
            # Return as individual points instead of a single boundary
            return [['DEPTH_POINT_' + str(i+1), [coord]] for i, coord in enumerate(coords)]

    # Default: extract all coordinates as one list
    coords = extract_general_coordinates(text)
    if coords:
        # Check if coordinates span an unreasonably large area
        if len(coords) > 3:
            lats = [pt[0] for pt in coords if isinstance(pt, list) and len(pt) >= 2]
            lons = [pt[1] for pt in coords if isinstance(pt, list) and len(pt) >= 2]

            if lats and lons:
                lat_range = max(lats) - min(lats)
                lon_range = max(lons) - min(lons)

                # If coordinates span more than 90 degrees lat/lon, treat as individual points
                # This prevents polygons that circle the globe
                if lat_range > 90 or lon_range > 180:
                    return [['SCATTERED_POINT_' + str(i+1), [coord]] for i, coord in enumerate(coords)]
                elif len(coords) > 10:
                    # Too many coordinates for a sensible polygon - treat as points
                    return [['POINT_' + str(i+1), [coord]] for i, coord in enumerate(coords)]
                else:
                    # Reasonable number of coordinates - treat as boundary area
                    coords_reversed = list(reversed(coords))
                    return [['BOUNDARY_AREA', coords_reversed]]

        # Default case: single point or small set of points
        if len(coords) == 1:
            return [['POINT', coords]]
        elif len(coords) > 1:
            return [['AREA', coords]]
        return []
    return []


def extract_complex_warning_coordinates(text: str) -> List:
    """Extract coordinates from complex warnings with multiple timestamped entries"""
    results = []

    # Split the text by timestamped entries (like "141418Z JUL 25 NAVAREA XII 422/25(16)")
    # Each entry represents a different sub-warning with its own geometry
    timestamp_pattern = r'(\d{6}Z\s+[A-Z]{3}\s+\d{2}\s+NAVAREA\s+XII\s+\d+/\d+\(\d+\)\.)'
    parts = re.split(timestamp_pattern, text)

    # Process each timestamped section
    for i in range(1, len(parts), 2):  # Skip first part, process pairs
        if i + 1 < len(parts):
            header = parts[i]
            content = parts[i + 1]

            # Extract warning number from header for naming
            warning_match = re.search(r'NAVAREA\s+XII\s+(\d+/\d+)', header)
            warning_num = warning_match.group(1) if warning_match else f"unknown_{i}"

            # Analyze the content to determine geometry type
            content_upper = content.upper()

            # Fish farm / bounded area
            if 'FISH FARM' in content_upper and 'BOUND BY' in content_upper:
                coords = extract_general_coordinates(content)
                if len(coords) >= 3:
                    results.append([f'FISH_FARM_{warning_num.replace("/", "_")}', coords])

            # Moorings (scientific)
            elif 'SCIENTIFIC MOORINGS' in content_upper:
                coords = extract_general_coordinates(content)
                for j, coord in enumerate(coords):
                    results.append([f'MOORING_{warning_num.replace("/", "_")}_{chr(65+j)}', [coord]])

            # Sunken vessel
            elif 'SANK IN' in content_upper or 'SUNKEN' in content_upper:
                coords = extract_general_coordinates(content)
                if coords:
                    results.append([f'SUNKEN_VESSEL_{warning_num.replace("/", "_")}', coords[:1]])

            # Communication facilities - check for lettered subsections first
            elif ('MESSAGING SERVICES UNRELIABLE' in content_upper or
                  'SERVICES UNRELIABLE' in content_upper or
                  'COMMUNICATION FACILITIES' in content_upper or
                  'REMOTE COMMUNICATION' in content_upper):
                # Check if it has lettered subsections (A., B., C., etc.)
                has_subsections = re.search(r'\b[A-Z]\.\s', content)
                if has_subsections:
                    # Use sectioned parsing for individual facilities
                    section_coords = extract_sectioned_coordinates(content)
                    if section_coords:
                        for coord_set in section_coords:
                            coord_type = coord_set[0].replace('POINT_', f'COMM_FACILITY_{warning_num.replace("/", "_")}_').replace('COORDINATES_', f'COMM_FACILITY_{warning_num.replace("/", "_")}_')
                            results.append([coord_type, coord_set[1]])
                    else:
                        # Fall back to general facility extraction
                        coords = extract_general_coordinates(content)
                        for j, coord in enumerate(coords):
                            results.append([f'COMM_FACILITY_{warning_num.replace("/", "_")}_{chr(65+j)}', [coord]])
                else:
                    # No subsections, extract all as facilities
                    coords = extract_general_coordinates(content)
                    for j, coord in enumerate(coords):
                        results.append([f'COMM_FACILITY_{warning_num.replace("/", "_")}_{chr(65+j)}', [coord]])

            # Cable operations / tracklines
            elif 'CABLE OPERATIONS' in content_upper and 'TRACKLINE' in content_upper:
                coords = extract_general_coordinates(content)
                if len(coords) >= 2:
                    results.append([f'CABLE_TRACKLINE_{warning_num.replace("/", "_")}', coords])

            # Lights (unlit, discontinued, etc.)
            elif ('LIGHT' in content_upper and ('UNLIT' in content_upper or 'DISCONTINUED' in content_upper)):
                coords = extract_general_coordinates(content)
                if coords:
                    results.append([f'LIGHT_{warning_num.replace("/", "_")}', coords[:1]])

            # Remote site/facility unreliability
            elif 'REMOTE SITE' in content_upper or 'REMOTE COMMUNICATION' in content_upper:
                coords = extract_general_coordinates(content)
                if coords:
                    results.append([f'REMOTE_FACILITY_{warning_num.replace("/", "_")}', coords[:1]])

            # Default: extract any coordinates found
            else:
                coords = extract_general_coordinates(content)
                if coords:
                    if len(coords) == 1:
                        results.append([f'POINT_{warning_num.replace("/", "_")}', coords])
                    elif len(coords) >= 3:
                        results.append([f'AREA_{warning_num.replace("/", "_")}', coords])
                    else:
                        results.append([f'COORDINATES_{warning_num.replace("/", "_")}', coords])

    return results if results else None


def extract_sectioned_coordinates(text: str) -> List:
    """Extract coordinates from warnings with multiple lettered sections (A., B., C., etc.)"""
    import re
    from downloaders.navigation_warnings import extract_warning_components

    results = []

    # Check if the overall text indicates bounded areas or tracklines
    text_upper = text.upper()
    is_bounded_areas = 'BOUND BY' in text_upper or 'AREAS BOUND BY' in text_upper or 'AREA BOUND BY' in text_upper
    is_trackline_areas = 'TRACKLINE' in text_upper or 'TRACKLINES' in text_upper

    # Check if this is a depth report
    if 'DEPTHS REPORTED' in text_upper:
        # Extract depth report coordinates - these should be individual points
        depth_matches = re.findall(r'\b([A-Z])\.\s*\d+(?:\.\d+)?\s+METERS\s+IN\s+[\d\-\.NSWE\s]+\.', text, re.IGNORECASE)
        if depth_matches:
            # Find the depth report section
            depth_start = text_upper.find('DEPTHS REPORTED')
            if depth_start >= 0:
                depth_section = text[depth_start:]
                # Extract all coordinates from the depth section
                depth_coords = extract_general_coordinates(depth_section)
                if depth_coords:
                    # Split into individual points
                    for i, coord in enumerate(depth_coords):
                        results.append([f'DEPTH_POINT_{i+1}', [coord]])
            return results

    # Use the new robust component extraction to get features with proper text
    try:
        prefix, feature_list, suffix = extract_warning_components(text)
    except Exception:
        # Fallback to old method if new extraction fails
        feature_list = []
        prefix = ""
        suffix = ""

    # If we have features from the new extraction, use them
    if feature_list:
        # Process each feature with its text
        for feature_idx, feature_text in enumerate(feature_list):
            # Extract coordinates from this specific feature
            section_coords = extract_general_coordinates(feature_text)

            # Extract label from feature text (handles A-Z, AA-ZZ, AAA+, etc.)
            import re
            label_match = re.match(r'^([A-Z]+)\.\s*', feature_text.strip())
            label = label_match.group(1) if label_match else chr(65 + feature_idx)

            if not section_coords:
                continue

            # Process the section based on coordinates and context
            feature_upper = feature_text.upper()

            if section_coords and 'WITHIN' in feature_upper and 'MILES OF' in feature_upper and len(section_coords) == 1:
                # Circular area - single point with radius
                center_lat, center_lon = section_coords[0]

                # Extract radius if possible
                radius_match = re.search(r'WITHIN\s+(\d+(?:\.\d+)?)\s+MILES', feature_upper)
                radius_nm = float(radius_match.group(1)) if radius_match else 5.0  # Default 5nm

                # Check for berth requests and add them to the radius
                berth_match = re.search(r'([A-Z0-9]+)\s*MILE\s*BERTH\s*REQUESTED', feature_upper, re.IGNORECASE)
                if berth_match:
                    berth_str = berth_match.group(1)
                    berth_nm = parse_distance_to_nautical_miles(berth_str + " MILE")
                    if berth_nm:
                        radius_nm += berth_nm

                # Convert nautical miles to degrees (1 NM ≈ 0.01667 degrees)
                radius_deg = radius_nm * 0.01667

                # Create circular area approximation with smooth 64-point circles
                circular_approx = create_circle_approximation(center_lat, center_lon, radius_deg, num_points=64)
                results.append([f'CIRCULAR_AREA_{label}', circular_approx, feature_text])

            elif 'BOUND BY' in feature_upper or 'AREA BOUND BY' in feature_upper:
                # Bounded area - use all coordinates as a polygon
                if len(section_coords) >= 3:  # Need at least 3 points for a polygon
                    # Reverse coordinates to ensure counter-clockwise winding for KML compatibility
                    section_coords_reversed = list(reversed(section_coords))
                    results.append([f'BOUNDARY_AREA_{label}', section_coords_reversed, feature_text])
                elif len(section_coords) == 1:
                    # Single point in a "bound by" context - treat as point
                    results.append([f'POINT_{label}', section_coords, feature_text])
                else:
                    results.append([f'BOUNDARY_AREA_{label}', section_coords, feature_text])
            elif is_trackline_areas and len(section_coords) >= 2:
                # Overall text mentions tracklines, treat sections as tracklines
                # Check for berth requests in the section content or overall text
                berth_nm = None

                # Check for "WITHIN X MILES/METERS OF" pattern in section content
                within_match = re.search(r'WITHIN\s+([A-Z0-9]+(?:\.\d+)?)\s+(MILES?|METERS?)', feature_upper)
                if within_match:
                    distance_str = within_match.group(1)
                    unit = within_match.group(2).upper()
                    # Parse the distance (handles both numeric and written numbers)
                    berth_nm = parse_distance_to_nautical_miles(distance_str + " " + unit)

                # Also check for berth requests in overall text as fallback
                if not berth_nm:
                    berth_match = re.search(r'([A-Z0-9]+)\s*MILE\s*BERTH\s*REQUESTED', text_upper, re.IGNORECASE)
                    if berth_match:
                        berth_str = berth_match.group(1)
                        berth_nm = parse_distance_to_nautical_miles(berth_str + " MILE")

                # If no explicit distance but "wide berth" is mentioned, default to 1 NM
                if not berth_nm and ('WIDE BERTH' in text_upper or 'BERTH REQUESTED' in feature_upper):
                    berth_nm = 1.0  # Default to 1 nautical mile

                if berth_nm and berth_nm > 0:
                    # Create berth polygon for this trackline section
                    berth_polygon = create_trackline_berth_polygon(section_coords, berth_nm)
                    if berth_polygon:
                        results.append([f'TRACKLINE_BERTH_AREA_{label}', berth_polygon, feature_text])
                    else:
                        results.append([f'TRACKLINE_{label}', section_coords, feature_text])
                else:
                    results.append([f'TRACKLINE_{label}', section_coords, feature_text])
            elif is_bounded_areas and len(section_coords) >= 3:
                # Overall text mentions bounded areas, and this section has multiple points
                results.append([f'BOUNDARY_AREA_{label}', section_coords, feature_text])
            elif is_bounded_areas and len(section_coords) == 1:
                # Overall text mentions bounded areas, but this section is just one point
                results.append([f'POINT_{label}', section_coords, feature_text])
            else:
                # Default: treat as points or areas
                if len(section_coords) == 1:
                    # Check if this point should have a berth buffer
                    berth_radius_nm = None

                    # Check for "WITHIN X MILES OF" pattern in overall text
                    within_match = re.search(r'WITHIN\s+([A-Z0-9]+(?:\.\d+)?)\s+MILES?\s+OF', text_upper)
                    if within_match:
                        distance_str = within_match.group(1)
                        berth_radius_nm = parse_distance_to_nautical_miles(distance_str + " MILE")
                    else:
                        # Check for berth requests in overall text
                        berth_match = re.search(r'([A-Z0-9]+)\s*MILE\s*BERTH\s*REQUESTED', text_upper, re.IGNORECASE)
                        if berth_match:
                            berth_str = berth_match.group(1)
                            berth_radius_nm = parse_distance_to_nautical_miles(berth_str + " MILE")

                    if berth_radius_nm and berth_radius_nm > 0:
                        # Create circular area around this point
                        center_lat, center_lon = section_coords[0]
                        radius_deg = berth_radius_nm * 0.01667  # Convert NM to degrees
                        circular_approx = create_circle_approximation(center_lat, center_lon, radius_deg, num_points=64)
                        results.append([f'CIRCULAR_AREA_{label}', circular_approx, feature_text])
                    else:
                        results.append([f'POINT_{label}', section_coords, feature_text])
                elif len(section_coords) >= 3:
                    results.append([f'AREA_{label}', section_coords, feature_text])
                else:
                    results.append([f'COORDINATES_{label}', section_coords, feature_text])

    else:
        # Fallback to old parsing method if new extraction failed or found no features
        # Parse sections by finding section markers and collecting all content until next marker
        results = []
        lines = text.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            # Look for section marker (enhanced format: one or more capital letters at beginning of line)
            section_match = re.match(r'^([A-Z]+)\.\s+(.+)?$', line)
            if section_match:
                label = section_match.group(1)
                section_content = [section_match.group(2) or ""]

                # Collect all subsequent lines until next section marker
                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()
                    if re.match(r'^[A-Z]+\.\s', next_line):
                        # Next section found, stop here
                        break
                    section_content.append(next_line)
                    i += 1

                # Join content and extract coordinates
                section_text = ' '.join(filter(None, section_content)).strip()
                section_coords = extract_general_coordinates(section_text)

                # For the last section, ensure it doesn't include post-coordinate info
                is_last_section = True
                for check_i in range(i, len(lines)):
                    check_line = lines[check_i].strip()
                    if re.match(r'^[A-Z]+\.\s', check_line):
                        is_last_section = False
                        break

                if is_last_section and section_coords:
                    # This is the last section - truncate at the last coordinate
                    coord_matches = list(re.finditer(r'\b\d{2,3}-\d{2}\.\d{1,2}[EW]\b', section_text))
                    if coord_matches:
                        last_coord = coord_matches[-1]
                        section_text = section_text[:last_coord.end()].strip()
                        section_coords = extract_general_coordinates(section_text)

                # Process the section with fallback logic
                content_upper = section_text.upper()

                if section_coords and 'WITHIN' in content_upper and 'MILES OF' in content_upper and len(section_coords) == 1:
                    center_lat, center_lon = section_coords[0]
                    radius_match = re.search(r'WITHIN\s+(\d+(?:\.\d+)?)\s+MILES', content_upper)
                    radius_nm = float(radius_match.group(1)) if radius_match else 5.0
                    berth_match = re.search(r'([A-Z0-9]+)\s*MILE\s*BERTH\s*REQUESTED', content_upper, re.IGNORECASE)
                    if berth_match:
                        berth_str = berth_match.group(1)
                        berth_nm = parse_distance_to_nautical_miles(berth_str + " MILE")
                        if berth_nm:
                            radius_nm += berth_nm
                    radius_deg = radius_nm * 0.01667
                    circular_approx = create_circle_approximation(center_lat, center_lon, radius_deg, num_points=64)
                    results.append([f'CIRCULAR_AREA_{label}', circular_approx, f"{label}. {section_text}"])

                elif 'BOUND BY' in content_upper or 'AREA BOUND BY' in content_upper:
                    if len(section_coords) >= 3:
                        section_coords_reversed = list(reversed(section_coords))
                        results.append([f'BOUNDARY_AREA_{label}', section_coords_reversed, f"{label}. {section_text}"])
                    elif len(section_coords) == 1:
                        results.append([f'POINT_{label}', section_coords, f"{label}. {section_text}"])
                    else:
                        results.append([f'BOUNDARY_AREA_{label}', section_coords, f"{label}. {section_text}"])

                elif is_trackline_areas and len(section_coords) >= 2:
                    berth_nm = None
                    within_match = re.search(r'WITHIN\s+([A-Z0-9]+(?:\.\d+)?)\s+(MILES?|METERS?)', content_upper)
                    if within_match:
                        distance_str = within_match.group(1)
                        unit = within_match.group(2).upper()
                        berth_nm = parse_distance_to_nautical_miles(distance_str + " " + unit)
                    if not berth_nm:
                        berth_match = re.search(r'([A-Z0-9]+)\s*MILE\s*BERTH\s*REQUESTED', text_upper, re.IGNORECASE)
                        if berth_match:
                            berth_str = berth_match.group(1)
                            berth_nm = parse_distance_to_nautical_miles(berth_str + " MILE")
                    if berth_nm and berth_nm > 0:
                        trackline_buffered = create_trackline_berth_polygon(section_coords, berth_nm)
                        if trackline_buffered:
                            results.append([f'TRACKLINE_BERTH_AREA_{label}', trackline_buffered, f"{label}. {section_text}"])
                        else:
                            results.append([f'TRACKLINE_{label}', section_coords, f"{label}. {section_text}"])
                    else:
                        results.append([f'TRACKLINE_{label}', section_coords, f"{label}. {section_text}"])

                else:
                    if len(section_coords) == 1:
                        berth_radius_nm = None
                        within_match = re.search(r'WITHIN\s+([A-Z0-9]+(?:\.\d+)?)\s+MILES?\s+OF', text_upper)
                        if within_match:
                            distance_str = within_match.group(1)
                            berth_radius_nm = parse_distance_to_nautical_miles(distance_str + " MILE")
                        else:
                            berth_match = re.search(r'([A-Z0-9]+)\s*MILE\s*BERTH\s*REQUESTED', text_upper, re.IGNORECASE)
                            if berth_match:
                                berth_str = berth_match.group(1)
                                berth_radius_nm = parse_distance_to_nautical_miles(berth_str + " MILE")
                        if berth_radius_nm and berth_radius_nm > 0:
                            center_lat, center_lon = section_coords[0]
                            radius_deg = berth_radius_nm * 0.01667
                            circular_approx = create_circle_approximation(center_lat, center_lon, radius_deg, num_points=64)
                            results.append([f'CIRCULAR_AREA_{label}', circular_approx, f"{label}. {section_text}"])
                        else:
                            results.append([f'POINT_{label}', section_coords, f"{label}. {section_text}"])
                    elif len(section_coords) >= 3:
                        results.append([f'AREA_{label}', section_coords, f"{label}. {section_text}"])
                    else:
                        results.append([f'COORDINATES_{label}', section_coords, f"{label}. {section_text}"])

            else:
                i += 1

    return results if results else None


def extract_coordinates_from_api_geometry(geometry) -> List:
    """Extract coordinates from API geometry data"""
    coords = []

    try:
        # Handle GeoJSON-style geometry
        geom_type = geometry.get('type', '').upper()
        coordinates = geometry.get('coordinates', [])

        if geom_type == 'POINT':
            # Single point: [longitude, latitude]
            if len(coordinates) >= 2:
                lon, lat = coordinates[0], coordinates[1]
                coords.append([lat, lon])

        elif geom_type == 'LINESTRING':
            # Line: [[lon, lat], [lon, lat], ...]
            for point in coordinates:
                if len(point) >= 2:
                    lon, lat = point[0], point[1]
                    coords.append([lat, lon])

        elif geom_type == 'POLYGON':
            # Polygon: [[[lon, lat], [lon, lat], ...]]
            if coordinates and len(coordinates) > 0:
                for point in coordinates[0]:  # Outer ring
                    if len(point) >= 2:
                        lon, lat = point[0], point[1]
                        coords.append([lat, lon])

        elif geom_type == 'MULTIPOLYGON':
            # MultiPolygon: [[[[lon, lat], ...]], [[[lon, lat], ...]]]
            for polygon in coordinates:
                if polygon and len(polygon) > 0:
                    for point in polygon[0]:  # Outer ring of each polygon
                        if len(point) >= 2:
                            lon, lat = point[0], point[1]
                            coords.append([lat, lon])

        # Handle simple coordinate arrays
        elif isinstance(coordinates, list):
            if len(coordinates) == 2 and isinstance(coordinates[0], (int, float)) and isinstance(coordinates[1], (int, float)):
                # Single point [lat, lon] or [lon, lat] - assume [lon, lat] for GeoJSON
                lon, lat = coordinates[0], coordinates[1]
                coords.append([lat, lon])
            elif coordinates and isinstance(coordinates[0], list):
                # Array of points
                for point in coordinates:
                    if isinstance(point, list) and len(point) >= 2:
                        lon, lat = point[0], point[1]
                        coords.append([lat, lon])

    except Exception:
        # If parsing fails, return empty list
        pass

    return coords


def parse_single_memorandum(content, memo_name):
    """Parse a single memorandum block into warning objects"""
    import re
    warnings = []

    # Split content into lines
    lines = content.split('\n')

    # Extract message series number from header (e.g., "NAVAREA XII 23/26(19)")
    message_series = None
    for line in lines[:10]:  # Check first 10 lines for header
        header_match = re.search(r'(?:NAVAREA|HYDRO)[A-Z]*\s+(\d{1,4}/\d{2,4})', line.strip())
        if header_match:
            message_series = header_match.group(1)
            break

    # Find the start of the warnings section (numbered list)
    warnings_section_start = -1
    for i, line in enumerate(lines):
        # Look for patterns that indicate the start of numbered warnings
        if re.match(r'^\s*\d+\.\s+.*(?:WARNING|IN\s+FORCE|CANCEL)', line.strip(), re.IGNORECASE):
            warnings_section_start = i
            break

    if warnings_section_start == -1:
        # Fallback: look for any numbered line
        for i, line in enumerate(lines):
            if re.match(r'^\s*\d+\.\s+', line.strip()):
                warnings_section_start = i
                break

    if warnings_section_start == -1:
        return warnings  # No warnings section found

    # Parse individual warnings from the numbered list
    current_warning_lines = []
    current_warning_number = None

    for i in range(warnings_section_start, len(lines)):
        line = lines[i].strip()

        # Check if this is a new warning (starts with number)
        warning_start_match = re.match(r'^\s*(\d+)\.\s+(.*)', line)
        if warning_start_match:
            # Save previous warning if we have one
            if current_warning_lines and current_warning_number:
                warning_text = '\n'.join(current_warning_lines)
                warning_info = parse_memorandum_warning_text(warning_text, memo_name, current_warning_number, message_series)
                if warning_info:
                    warnings.append(warning_info)

            # Start new warning
            current_warning_number = warning_start_match.group(1)
            current_warning_lines = [line]
        elif line and current_warning_lines:
            # Continue current warning
            current_warning_lines.append(line)
        elif not line and current_warning_lines:
            # Empty line - could be end of warning
            continue

    # Don't forget the last warning
    if current_warning_lines and current_warning_number:
        warning_text = '\n'.join(current_warning_lines)
        warning_info = parse_memorandum_warning_text(warning_text, memo_name, current_warning_number, message_series)
        if warning_info:
            warnings.append(warning_info)

    return warnings


def parse_daily_memorandum(content, source_url, memo_name):
    """Parse daily memorandum content into warning objects"""
    import re
    warnings = []

    # Split content into individual memorandums based on headers
    # Look for patterns like "NAVAREA XII 23/26(19)."
    memorandum_sections = []
    lines = content.split('\n')
    current_section = []
    current_series = None

    for line in lines:
        line = line.strip()

        # Check if this is a new memorandum header
        # Handle both NAVAREA XII 123/45 and HYDROLANT 123/45 formats
        header_match = re.search(r'(?:NAVAREA|HYDRO\w*)\s+(?:\w+\s+)?(\d{1,4}/\d{2,4})(?:\([^)]*\))?', line)
        if header_match:
            # Save previous section if it exists
            if current_section and current_series:
                memorandum_sections.append((current_series, current_section))
            # Start new section
            current_series = header_match.group(1)
            current_section = [line]  # Include the header line
        elif current_section:
            current_section.append(line)

    # Don't forget the last section
    if current_section and current_series:
        memorandum_sections.append((current_series, current_section))

    # Parse each memorandum section separately
    if memorandum_sections:
        for message_series, section_lines in memorandum_sections:
            section_warnings = parse_single_memorandum('\n'.join(section_lines), memo_name, message_series)
            warnings.extend(section_warnings)
    else:
        # No memorandum sections found - treat entire content as one memorandum
        # This handles HYDRO areas and other formats
        section_warnings = parse_single_memorandum(content, memo_name)
        warnings.extend(section_warnings)

    return warnings


def parse_single_memorandum(content, memo_name, message_series=None):
    """Parse a single memorandum block into warning objects using unified parsing logic"""
    import re
    warnings = []

    # Detect memorandum format and split into individual warnings
    warning_texts = detect_and_split_memorandum_warnings(content, memo_name)

    # For HYDROPAC memorandums, use "HYDROPAC" as memo_name for navarea extraction
    effective_memo_name = "HYDROPAC" if "HYDROPAC" in memo_name else memo_name

    # Parse each warning text
    for i, warning_text in enumerate(warning_texts, 1):
        warning_info = parse_memorandum_warning_text(warning_text, effective_memo_name, str(i), message_series)
        if warning_info:
            warnings.append(warning_info)

    return warnings


def detect_and_split_memorandum_warnings(content, memo_name):
    """Unified function to detect memorandum format and split into individual warning texts"""
    import re
    lines = content.split('\n')

    # Format detection logic
    format_type = detect_memorandum_format(content, memo_name)

    if format_type == "numbered_warnings":
        # Standard NAVAREA format with numbered warnings (1., 2., etc.)
        return split_numbered_warnings(lines)
    elif format_type == "hydropac_concatenated":
        # HYDROPAC format with concatenated warnings separated by warning numbers
        return split_hydropac_warnings(lines)
    elif format_type == "multiple_memorandums":
        # Multiple memorandum sections (HYDROLANT, etc.) - split by HYDRO headers
        return split_multiple_memorandums(content)
    elif format_type == "single_warning":
        # Single warning in the memorandum
        return [content.strip()]
    else:
        # Fallback: try numbered warnings first, then HYDROPAC
        warnings = split_numbered_warnings(lines)
        if warnings:
            return warnings
        warnings = split_hydropac_warnings(lines)
        if warnings:
            return warnings
        # Last resort: treat as single warning
        return [content.strip()]


def detect_memorandum_format(content, memo_name):
    """Detect the format of a memorandum based on its content structure"""
    import re

    # Check for HYDROPAC-specific patterns
    if "HYDROPAC" in memo_name or re.search(r'HYDROPAC\s+\d+/\d+', content):
        # Look for multiple HYDROPAC warning numbers - indicates concatenated format
        hydropac_matches = re.findall(r'^(?:CANCEL\s+)?HYDROPAC\s+\d+/\d+', content, re.MULTILINE)
        if len(hydropac_matches) > 1:
            return "hydropac_concatenated"
        elif len(hydropac_matches) == 1:
            return "single_warning"

    # Check for numbered warnings (1., 2., etc.)
    numbered_lines = [line for line in content.split('\n') if re.match(r'^\s*\d+\.\s+', line.strip())]
    if numbered_lines:
        return "numbered_warnings"

    # Check for NAVAREA/HYDRO headers indicating multiple memorandum sections
    header_matches = re.findall(r'(?:NAVAREA|HYDRO\w*)\s+\d+/\d+', content)
    if len(header_matches) > 1:
        return "multiple_memorandums"

    # Default to single warning
    return "single_warning"


def split_numbered_warnings(lines):
    """Split memorandum with numbered warnings (1., 2., etc.)"""
    import re
    warnings = []
    current_warning_lines = []
    current_warning_number = None

    # Find the start of the warnings section
    warnings_section_start = -1
    for i, line in enumerate(lines):
        if re.match(r'^\s*\d+\.\s+', line.strip()):
            warnings_section_start = i
            break

    if warnings_section_start == -1:
        return warnings

    # Parse warnings from the numbered section
    for i in range(warnings_section_start, len(lines)):
        line = lines[i].strip()

        # Check if this is a new warning (starts with number)
        warning_start_match = re.match(r'^\s*(\d+)\.\s+(.*)', line)
        if warning_start_match:
            # Save previous warning if we have one
            if current_warning_lines and current_warning_number:
                warnings.append('\n'.join(current_warning_lines))

            # Start new warning
            current_warning_number = warning_start_match.group(1)
            current_warning_lines = [line]
        elif line and current_warning_lines:
            # Continue current warning
            current_warning_lines.append(line)
        elif not line and current_warning_lines:
            # Empty line - could be end of warning
            continue

    # Don't forget the last warning
    if current_warning_lines and current_warning_number:
        warnings.append('\n'.join(current_warning_lines))

    return warnings


def split_hydropac_warnings(lines):
    """Split HYDROPAC memorandum with concatenated warnings"""
    import re
    warnings = []
    current_section = []

    for line in lines:
        line = line.strip()

        # Check if this line starts a new warning section
        if re.match(r'^(CANCEL\s+)?HYDROPAC\s+\d+/\d+', line):
            # Save previous section if it exists
            if current_section:
                warnings.append('\n'.join(current_section))
            # Start new section
            current_section = [line]
        elif current_section:
            # Continue current section
            current_section.append(line)
        elif not current_section and line:
            # If we haven't started a section yet, start one with any content
            current_section = [line]

    # Don't forget the last section
    if current_section:
        warnings.append('\n'.join(current_section))

    return warnings


def split_multiple_memorandums(content):
    """Split memorandum with multiple HYDRO sections (HYDROLANT, HYDROPAC, HYDROARC)"""
    import re

    # Split by HYDRO headers (HYDROLANT, HYDROPAC, HYDROARC, etc.)
    # Pattern matches: HYDROLANT 123/45, CANCEL HYDROLANT 123/45, etc.
    sections = re.split(r'((?:CANCEL\s+)?(?:NAVAREA|HYDRO\w*)\s+\d+/\d+)', content)

    warnings = []
    current_warning = ""

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Check if this is a header line
        if re.match(r'^(?:CANCEL\s+)?(?:NAVAREA|HYDRO\w*)\s+\d+/\d+', section):
            # If we have a previous warning, save it
            if current_warning.strip():
                warnings.append(current_warning.strip())
            current_warning = section
        else:
            # This is content for the current warning
            if current_warning:
                current_warning += "\n" + section
            else:
                current_warning = section

    # Add the last warning
    if current_warning.strip():
        warnings.append(current_warning.strip())

    return warnings if warnings else [content.strip()]


def parse_memorandum_warning_text(warning_text, memo_name, warning_number, message_series=None):
    """Parse individual memorandum warning text into structured data"""
    import re
    import requests
    from urllib.parse import quote

    # Extract NAVAREA from memo_name
    navarea = extract_navarea_from_memo_name(memo_name)

    # Look for warning numbers in the text (like "123/26" or "CANCEL HYDROPAC 3456/25")
    warning_numbers = re.findall(r'\b(\d{1,4}/\d{2,4})\b', warning_text)

    # Use the first warning number found, or create a synthetic one
    if warning_numbers:
        msg_number, msg_year = warning_numbers[0].split('/')
        # Message series information is already represented by NAVAREA - don't duplicate it
    else:
        # Create a synthetic warning number based on the memorandum and entry number
        msg_year = '26'  # Current year
        msg_number = f"{memo_name[:3].upper()}{warning_number.zfill(3)}"

    # TODO: Implement detailed warning content fetching
    # The NGA MSI website structure makes it challenging to fetch individual warning details:
    # 1. Individual warning URLs are not well-documented
    # 2. The website may require JavaScript or authentication for detailed views
    # 3. Rate limiting and bot detection may block automated requests
    #
    # For now, we use the memorandum summaries which provide good coverage.
    # To implement detailed fetching, we would need:
    # - Reverse engineer the correct URL patterns for individual warnings
    # - Implement proper browser automation (Selenium) or API discovery
    # - Add comprehensive error handling and rate limiting
    # - Possibly work with NGA MSI to get API access for detailed warnings

    detailed_content = None
    detailed_description = None

    # Use detailed content if available, otherwise fall back to memorandum text
    if detailed_content:
        content = detailed_content
        description = detailed_description or detailed_content
    else:
        # Clean up the description (remove the leading number)
        lines = warning_text.split('\n')
        description_lines = []

        for line in lines:
            # Remove leading number if it exists
            line = re.sub(r'^\s*\d+\.\s+', '', line)
            if line.strip():
                description_lines.append(line.strip())

        description = '\n'.join(description_lines)
        content = warning_text

    # Extract coordinates from the description
    coordinates = extract_coordinates_from_text(description)

    return {
        'navarea': navarea,
        'msg_number': msg_number,
        'msg_year': msg_year,
        'content': content,
        'description': description,
        'coordinates': coordinates,
        'source': memo_name,
        'timestamp': f"Entry {warning_number} from {memo_name}",
        'warning_type': 'detailed_warning' if detailed_content else 'memorandum_entry'
    }


def parse_warning_text(warning_text, memo_name):
    """Parse individual warning text into structured data (legacy function for broadcast warnings)"""
    import re
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
        'msg_number': msg_number,
        'msg_year': msg_year,
        'content': warning_text,
        'description': description,
        'source': memo_name,
        'timestamp': timestamp_line
    }