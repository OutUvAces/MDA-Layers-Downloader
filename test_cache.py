#!/usr/bin/env python3
"""
Test script to run the cache refresh pipeline without Flask dependencies.
"""

import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock minimal Flask components
class MockModule:
    pass

# Mock flask and its components
flask_mock = MockModule()
flask_mock.Flask = lambda *args, **kwargs: MockModule()
flask_mock.render_template = lambda *args, **kwargs: ""
flask_mock.request = MockModule()
flask_mock.redirect = lambda *args, **kwargs: None
flask_mock.url_for = lambda *args, **kwargs: ""
flask_mock.flash = lambda *args, **kwargs: None
flask_mock.send_file = lambda *args, **kwargs: None
flask_mock.jsonify = lambda *args, **kwargs: None

sys.modules['flask'] = flask_mock

# Now try to import the refresh functions
try:
    from downloaders.marineregions import refresh_static_caches
    from downloaders.wdpa import refresh_static_caches as refresh_wdpa
    from downloaders.submarine_cables import refresh_static_caches as refresh_cables
    from downloaders.oscar_currents import refresh_dynamic_caches
    from downloaders.navigation_warnings import refresh_dynamic_caches as refresh_nav

    print("Testing MDA Layers Downloader cache refresh...")
    print("Testing MarineRegions download...")
    try:
        mr_success = refresh_static_caches()
        print(f"MarineRegions: {'Success' if mr_success else 'Failed'}")
    except Exception as e:
        print(f"MarineRegions crashed: {e}")

    print("Testing WDPA download...")
    try:
        wdpa_success = refresh_wdpa()
        print(f"WDPA: {'Success' if wdpa_success else 'Failed'}")
    except Exception as e:
        print(f"WDPA crashed: {e}")

    print("Testing Cables download...")
    try:
        cables_success = refresh_cables()
        print(f"Cables: {'Success' if cables_success else 'Failed'}")
    except Exception as e:
        print(f"Cables crashed: {e}")

    print("Testing OSCAR download...")
    try:
        oscar_success = refresh_dynamic_caches()
        print(f"OSCAR: {'Success' if oscar_success else 'Failed'}")
    except Exception as e:
        print(f"OSCAR crashed: {e}")

    print("Testing Navigation Warnings...")
    try:
        nav_success = refresh_nav()
        print(f"Nav Warnings: {'Success' if nav_success else 'Failed'}")
    except Exception as e:
        print(f"Nav Warnings crashed: {e}")

    print("Cache refresh testing completed!")

    # Test KML generation
    print("\nTesting KML generation...")
    try:
        from web_app.app import pregenerate_default_kmls
        print("Running pregenerate_default_kmls...")
        pregenerate_default_kmls(force_regeneration=True)
        print("KML generation completed!")
    except Exception as e:
        print(f"KML generation failed: {e}")
        import traceback
        traceback.print_exc()

except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()