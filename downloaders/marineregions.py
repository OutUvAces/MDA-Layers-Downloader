
def refresh_static_caches():
    """Refresh all static caches for MarineRegions data using WFS GeoJSON download"""
    print("MARINEREGIONS: Refreshing static caches...")

    try:
        cache_dir = Path(__file__).parent.parent / "cache" / "static" / "marineregions"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Use WFS to download EEZ data as GeoJSON (similar to main branch approach)
        print("MARINEREGIONS: Downloading EEZ data via WFS...")
        eez_url = "https://geo.vliz.be/geoserver/MarineRegions/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=MarineRegions:eez&outputFormat=application/json"
        eez_file = cache_dir / "eez_global.geojson"

        if not eez_file.exists():
            # Force disable SSL verification for MarineRegions (as in original code)
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            response = requests.get(eez_url, timeout=120, verify=False)
            response.raise_for_status()

            with open(eez_file, 'w', encoding='utf-8') as f:
                f.write(response.text)

            print(f"MARINEREGIONS: Downloaded EEZ data, size = {eez_file.stat().st_size} bytes")
        else:
            print("MARINEREGIONS: EEZ data already downloaded")

        print("MARINEREGIONS: Static caches refreshed")
        return True
    except Exception as e:
        print(f"MARINEREGIONS: Static cache refresh failed: {e}")
        return False