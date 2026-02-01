def refresh_static_caches():
    """Refresh all static caches for MarineRegions data using WFS shapefile download"""
    print("MARINEREGIONS: Refreshing static caches...")

    try:
        cache_dir = Path(__file__).parent.parent / "cache" / "static" / "marineregions"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Download EEZ data using WFS shapefile format
        print("MARINEREGIONS: Downloading EEZ shapefile via WFS...")
        eez_url = "https://geo.vliz.be/geoserver/MarineRegions/wfs?service=WFS&version=1.1.0&request=GetFeature&typeName=MarineRegions:eez&outputFormat=SHAPE-ZIP"
        eez_zip = cache_dir / "eez_global.zip"

        if not eez_zip.exists():
            # Force disable SSL verification for MarineRegions (as in original code)
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            response = requests.get(eez_url, timeout=120, verify=False)
            response.raise_for_status()

            with open(eez_zip, 'wb') as f:
                f.write(response.content)

            print(f"MARINEREGIONS: Downloaded EEZ data, size = {eez_zip.stat().st_size} bytes")

            # Extract the ZIP file
            print("MARINEREGIONS: Extracting EEZ data...")
            import zipfile
            with zipfile.ZipFile(eez_zip, 'r') as zip_ref:
                zip_ref.extractall(cache_dir)

            print("MARINEREGIONS: EEZ data extracted")
        else:
            print("MARINEREGIONS: EEZ data already downloaded")

        print("MARINEREGIONS: Static caches refreshed")
        return True
    except Exception as e:
        print(f"MARINEREGIONS: Static cache refresh failed: {e}")
        return False