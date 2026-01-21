#!/usr/bin/env python3

import sys
sys.path.append('.')
from downloaders.navigation_warnings import scrape_global_navwarnings, create_kml_for_warnings
import os

def progress_callback(progress, msg):
    pass

cache_dir = os.path.join('output', '_cache')
os.makedirs(cache_dir, exist_ok=True)

print("Testing geocoding for warnings with no coordinates...")

warnings = scrape_global_navwarnings(cache_dir, progress_callback)

# Find a warning with no coordinates
no_coords_warning = None
for warning in warnings:
    coords = warning.get('coordinates')
    if not coords or not isinstance(coords, list) or len(coords) == 0:
        no_coords_warning = warning
        break

if no_coords_warning:
    print(f"Found warning with no coordinates: {no_coords_warning.get('navarea')} {no_coords_warning.get('msg_number')}")
    print(f"Description: {no_coords_warning.get('description', '')[:200]}...")

    class MockTask:
        def __init__(self):
            self.output_path = os.path.join('output', 'test_geocoding.kml')
            self.color_abgr = 'ff0000ff'
            self.use_custom_colors = False
            self.settings_color = 'ff0000ff'
            self.settings_opacity = 80
            self.weight = 1.0

    task = MockTask()
    result = create_kml_for_warnings(task, progress_callback, 'output', cache_dir, [no_coords_warning])

    if os.path.exists(task.output_path):
        with open(task.output_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Count placemarks and points
        placemarks = content.count('<Placemark>')
        points = content.count('<Point>')

        print(f"Created {placemarks} placemarks with {points} points")

        # Check for geocoded points (not at 0,0)
        if points > 0:
            # Find coordinates
            coord_start = content.find('<coordinates>')
            if coord_start != -1:
                coord_end = content.find('</coordinates>', coord_start)
                coords = content[coord_start+13:coord_end].strip()
                print(f"Point coordinates: {coords}")
                if coords != '0,0,0':
                    print("SUCCESS: Warning was geocoded!")
                else:
                    print("FAILED: Warning created point at 0,0 (geocoding failed)")
            else:
                print("No coordinates found")
        else:
            print("No points created")
else:
    print("No warning with no coordinates found")