#!/usr/bin/env python3
"""
Test script for ocean currents processing
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from downloaders.oscar_currents import process
from core.types import LayerTask

# Configuration
BASE_OUTPUT_DIR = r"C:\Users\mccar\Documents\MDA_Layers_Output"
CONFIG_FILE = os.path.join(BASE_OUTPUT_DIR, "_config", "earthdata_credentials.txt")

# Test parameters - modify these for different test scenarios
TEST_TYPE = "global"  # "global" or "country"
TEST_COUNTRY = "Tonga"
TEST_ISO_CODE = "TON"
DENSITY = 3.0  # Low density

def load_credentials():
    """Load Earthdata credentials."""
    try:
        import configparser
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        username = config.get("Earthdata", "username")
        password = config.get("Earthdata", "password")
        if not username or not password:
            raise ValueError("Credentials not found in config file")
        return username, password
    except Exception as e:
        print(f"ERROR: Could not load credentials: {e}")
        sys.exit(1)

def create_test_task():
    """Create test task based on configuration."""
    cache_dir = os.path.join(BASE_OUTPUT_DIR, "_cache")

    if TEST_TYPE == "global":
        return LayerTask(
            type="seastate",
            name="Ocean Currents (global)",
            output_path=os.path.join(BASE_OUTPUT_DIR, "ocean_currents_global_test.kml"),
            color_abgr="ff0000ff",
            weight=1.0,
            density=DENSITY
        ), BASE_OUTPUT_DIR
    else:  # country-specific
        country_folder = TEST_COUNTRY.replace(" ", "_").replace("/", "-").replace(":", "-").replace(",", "").replace("'", "")
        country_dir = os.path.join(BASE_OUTPUT_DIR, country_folder)
        os.makedirs(country_dir, exist_ok=True)

        return LayerTask(
            type="seastate",
            name=f"Ocean Currents ({TEST_COUNTRY} EEZ clipped)",
            output_path=os.path.join(country_dir, f"{TEST_ISO_CODE}_ocean_currents_eez_test.kml"),
            color_abgr="ff0000ff",
            weight=1.0,
            density=DENSITY,
            iso_code=TEST_ISO_CODE,
            clip_to_eez=True
        ), country_dir

def main():
    """Run the test."""
    username, password = load_credentials()
    task, output_dir = create_test_task()
    cache_dir = os.path.join(BASE_OUTPUT_DIR, "_cache")

    def progress_callback(weight, message):
        print(f"Progress ({weight:.1f}): {message}")

    print(f"Starting {TEST_TYPE} ocean currents processing...")
    success = process(task, progress_callback, output_dir, cache_dir, username, password)

    if success:
        print("SUCCESS: Ocean currents processing completed")
        if os.path.exists(task.output_path):
            size = os.path.getsize(task.output_path)
            print(f"Output file: {task.output_path} ({size:,} bytes)")
        else:
            print("ERROR: Output file not created")
    else:
        print("ERROR: Processing failed")

if __name__ == "__main__":
    main()