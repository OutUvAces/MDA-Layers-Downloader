"""
OSCAR ocean currents data downloader and processor.

This module handles downloading OSCAR (Ocean Surface Current Analysis Real-time)
data from NASA and converting it to KML format for visualization.
"""

import os
import json
import numpy as np
import xarray as xr
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import cftime
import ctypes
import base64
from datetime import datetime, timedelta
import time

from core.utils import add_data, hex_to_kml_abgr
from core.types import LayerTask
from core.config import OSCAR_CMR_URL, OSCAR_COLLECTION_ID
import geopandas as gpd
from pathlib import Path
from shapely.geometry import Point

def _create_arrowhead_line(doc, start_lon, start_lat, end_lon, end_lat):
    """Create a single arrowhead line element in the KML document."""
    pm = ET.SubElement(doc, 'Placemark')
    ET.SubElement(pm, 'name').text = ""  # Empty name for arrowhead

    line = ET.SubElement(pm, 'LineString')
    ET.SubElement(line, 'extrude').text = '1'
    ET.SubElement(line, 'tessellate').text = '1'
    ET.SubElement(line, 'altitudeMode').text = 'clampToGround'

    coords_text = f"{start_lon:.6f},{start_lat:.6f},100 {end_lon:.6f},{end_lat:.6f},100"
    coords = ET.SubElement(line, 'coordinates')
    coords.text = coords_text

    ET.SubElement(pm, 'styleUrl').text = '#arrowLine'

async def get_earthdata_token_async(session, username: str, password: str) -> str:
    """Async version of Earthdata token retrieval"""
    # Use find_or_create_token endpoint which is more reliable and handles existing tokens
    token_url = "https://urs.earthdata.nasa.gov/api/users/find_or_create_token"

    # Use basic auth with username:password
    auth_str = f"{username}:{password}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()

    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/json"
    }

    try:
        async with session.post(token_url, headers=headers) as response:
            response.raise_for_status()

            token_data = await response.json()
            if "access_token" not in token_data:
                raise Exception(f"Invalid token response: {token_data}")

            return token_data["access_token"]
    except Exception as e:
        if hasattr(e, 'status') and e.status == 403:
            raise Exception("403 Forbidden: Check your Earthdata credentials and account status. "
                          "Visit https://urs.earthdata.nasa.gov to verify your account is active and email is verified. "
                          "You may also have reached the 2-token limit - try revoking old tokens.")
        elif hasattr(e, 'status') and e.status == 401:
            raise Exception("401 Unauthorized: Invalid Earthdata username or password.")
        else:
            raise Exception(f"Network error connecting to Earthdata: {e}")

async def download_oscar_granule_async(session, granule_url: str, temp_nc: str, report_progress, access_token: str) -> None:
    """Async download of OSCAR NetCDF granule"""
    headers = {"Authorization": f"Bearer {access_token}"}

    # Attempt download with token
    async with session.get(granule_url, headers=headers) as response:
        # If token is expired (401), try getting a fresh token once
        if response.status == 401:
            raise Exception("Token expired - sync fallback needed for token refresh")

        response.raise_for_status()

        # Get total size for progress feedback
        total_size = int(response.headers.get('Content-Length', 0))

        try:
            from tqdm import tqdm
            use_tqdm = True
        except ImportError:
            use_tqdm = False

        if use_tqdm:
            with open(temp_nc, 'wb') as f, tqdm(
                total=total_size,
                desc="Downloading OSCAR ocean currents .nc",
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                bar_format='{desc}: {total_fmt} [{elapsed}, {rate_fmt}{postfix}]'
            ) as pbar:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)
                    pbar.update(len(chunk))
        else:
            with open(temp_nc, 'wb') as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)

async def process_async(session, task: LayerTask, report_progress, output_dir: str, cache_dir: str, username: str, password: str) -> bool:
    """Async version of OSCAR processing"""
    report_progress(0, f"Fetching latest ocean surface currents from NOAA OSCAR V2.0 NRT...")
    try:
        # Data discovery is lightweight, keep it sync
        granule_url, latest_date = get_latest_oscar_nrt_granule_info()
        temp_nc = os.path.join(cache_dir, "oscar_latest.nc")

        use_cached = False
        if os.path.exists(temp_nc):
            with xr.open_dataset(temp_nc) as ds_temp:
                time_vals = ds_temp['time'].values
                # Extract scalar value from array
                if np.size(time_vals) > 0:
                    time_val = time_vals[-1] if np.size(time_vals) > 1 else time_vals.item()
                else:
                    time_val = None

                if time_val is not None:
                    try:
                        if isinstance(time_val, (cftime._cftime.DatetimeJulian, cftime._cftime.Datetime360Day, cftime._cftime.DatetimeNoLeap, cftime._cftime.DatetimeProlepticGregorian)):
                            time_dt = pd.Timestamp(time_val.isoformat())
                        else:
                            ref_date = pd.Timestamp('1990-01-01')
                            time_dt = ref_date + pd.to_timedelta(time_val, unit='D')
                        cached_date = time_dt.strftime("%Y-%m-%d")
                        if cached_date == latest_date:
                            use_cached = True
                            report_progress(0, "Using cached latest granule...")
                    except Exception as e:
                        report_progress(0, f"Cache date parsing warning: {e}")
                        pass

        if not use_cached:
            report_progress(0, "Downloading latest granule (~100-200 MB, may take a minute)...")
            # Get Earthdata access token
            access_token = await get_earthdata_token_async(session, username, password)

            # Download the NetCDF file
            await download_oscar_granule_async(session, granule_url, temp_nc, report_progress, access_token)

        # Continue with the rest of processing (CPU-bound operations)
        return process_oscar_core(task, report_progress, output_dir, cache_dir, temp_nc, latest_date)

    except Exception as e:
        error_msg = str(e)
        if "CERTIFICATE_VERIFY_FAILED" in error_msg:
            report_progress(0, f"Ocean currents SSL certificate error: Server certificate validation failed.")
        elif "timeout" in error_msg.lower():
            report_progress(0, f"Ocean currents timeout error: Request timed out.")
        elif "connection" in error_msg.lower():
            report_progress(0, f"Ocean currents connection error: Unable to connect to server.")
        elif "401" in error_msg or "403" in error_msg:
            report_progress(0, f"Ocean currents authentication error: {e}")
        else:
            report_progress(0, f"Ocean currents processing error: {type(e).__name__}: {repr(e)}")
        return False

def get_latest_oscar_nrt_granule_info() -> tuple[str, str]:
    params = {
        "collection_concept_id": OSCAR_COLLECTION_ID,
        "page_size": 1,
        "sort_key": "-start_date"
    }
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(OSCAR_CMR_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            if 'items' not in data or not data['items']:
                raise Exception("No granules found")
            granule = data['items'][0]['umm']
            related_urls = granule['RelatedUrls']
            download_url = None
            for url_info in related_urls:
                if url_info['Type'] in ("GET DATA", "DOWNLOAD", "USE SERVICE API"):
                    download_url = url_info['URL']
                    break
            if not download_url:
                raise Exception("No download URL found")
            beginning_date = granule['TemporalExtent']['RangeDateTime']['BeginningDateTime'].split('T')[0]
            return download_url, beginning_date
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                continue
            raise Exception(f"CMR API failed after {max_retries} attempts: {e}")

def get_earthdata_token(username: str, password: str) -> str:
    """Get Earthdata access token using OAuth2 user token flow."""
    # Use find_or_create_token endpoint which is more reliable and handles existing tokens
    token_url = "https://urs.earthdata.nasa.gov/api/users/find_or_create_token"

    # Use basic auth with username:password
    auth_str = f"{username}:{password}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()

    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(token_url, headers=headers, timeout=30)
        response.raise_for_status()

        token_data = response.json()
        if "access_token" not in token_data:
            raise Exception(f"Invalid token response: {token_data}")

        return token_data["access_token"]
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            raise Exception("403 Forbidden: Check your Earthdata credentials and account status. "
                          "Visit https://urs.earthdata.nasa.gov to verify your account is active and email is verified. "
                          "You may also have reached the 2-token limit - try revoking old tokens.")
        elif e.response.status_code == 401:
            raise Exception("401 Unauthorized: Invalid Earthdata username or password.")
        else:
            raise Exception(f"HTTP {e.response.status_code}: {e.response.text}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Network error connecting to Earthdata: {e}")

def process_oscar_core(task: LayerTask, report_progress, output_dir: str, cache_dir: str, temp_nc: str, time_str: str) -> bool:
    """Core OSCAR processing logic (shared between sync and async versions)"""
    from shapely.geometry import Polygon, MultiPolygon
    try:
        ds = xr.open_dataset(temp_nc)

        # Time handling
        time_vals = ds['time'].values
        time_val = time_vals[-1] if np.size(time_vals) > 1 else time_vals if np.size(time_vals) > 0 else None
        if time_val is not None:
            try:
                if isinstance(time_val, (cftime._cftime.DatetimeJulian, cftime._cftime.Datetime360Day, cftime._cftime.DatetimeNoLeap, cftime._cftime.DatetimeProlepticGregorian)):
                    time_dt = pd.Timestamp(time_val.isoformat())
                else:
                    ref_date = pd.Timestamp('1990-01-01')
                    time_dt = ref_date + pd.to_timedelta(time_val, unit='D')
                time_str = time_dt.strftime("%Y-%m-%d %H:%M UTC")
            except:
                time_str = "Latest available UTC"
        else:
            time_str = "Latest available UTC"

        if 'time' in ds.dims and ds.dims['time'] > 0:
            ds = ds.isel(time=-1)

        # Determine coordinate names - OSCAR data may use 'lat'/'lon' or 'latitude'/'longitude'
        # Use dimension names for selection, coordinate names for accessing values
        dims_list = list(ds.sizes.keys())
        # More robust dimension detection - check coordinate names and sizes
        lat_dim_name = None
        lon_dim_name = None

        # First, try to find dimensions by name
        for dim_name in dims_list:
            if dim_name.lower() in ['latitude', 'lat']:
                lat_dim_name = dim_name
            elif dim_name.lower() in ['longitude', 'lon']:
                lon_dim_name = dim_name

        # If not found by name, assume first dim is latitude, second is longitude (common NetCDF convention)
        if lat_dim_name is None:
            lat_dim_name = dims_list[0]
        if lon_dim_name is None:
            lon_dim_name = dims_list[1] if len(dims_list) > 1 else dims_list[0]

        # Also detect coordinate names
        lat_coord_name = None
        lon_coord_name = None
        for coord_name in ds.coords:
            if coord_name.lower() in ['latitude', 'lat']:
                lat_coord_name = coord_name
            elif coord_name.lower() in ['longitude', 'lon']:
                lon_coord_name = coord_name

        # Fallback to dimension names for coordinates
        if lat_coord_name is None:
            lat_coord_name = lat_dim_name
        if lon_coord_name is None:
            lon_coord_name = lon_dim_name

        spacing_deg = task.density

        if task.clip_to_eez:
            eez_path = os.path.join(output_dir, f"{task.iso_code}_eez.kml")

            # Ensure EEZ file exists - download directly if concurrent task failed
            if not os.path.exists(eez_path):
                report_progress(0, f"EEZ file not found, downloading directly: {task.iso_code}")
                try:
                    import requests
                    from core.config import MARINEREGIONS_WFS_BASE

                    eez_url = f"{MARINEREGIONS_WFS_BASE}?service=WFS&version=1.1.0&request=GetFeature&typeName=MarineRegions:eez&outputFormat=KML&CQL_FILTER=iso_ter1='{task.iso_code}'"

                    report_progress(0, "Downloading EEZ boundary...")
                    response = requests.get(eez_url, timeout=30)
                    response.raise_for_status()

                    # Ensure directory exists and save KML
                    os.makedirs(os.path.dirname(eez_path), exist_ok=True)
                    with open(eez_path, 'wb') as f:
                        f.write(response.content)

                    report_progress(0, f"EEZ downloaded successfully")

                except Exception as e:
                    report_progress(0, f"EEZ download failed: {e}")
                    raise FileNotFoundError(f"Could not download EEZ file: {eez_path}")

            report_progress(0, "Using EEZ boundary for current clipping...")
            eez_gdf = gpd.read_file(eez_path, driver='KML')
            if not eez_gdf.empty:
                # Create buffered EEZ polygon (10 nautical miles = ~18.52 km)
                # Convert 10 nm to degrees (rough approximation for buffering)
                buffer_deg = 10 * 1.852 / 111.0  # 10 nm to km, then to degrees (111 km per degree)
                # Buffer the EEZ polygons (increase buffer size significantly for testing)
                buffer_deg = 50 * 1.852 / 111.0  # 50 nm to km, then to degrees (~0.825°)
                eez_buffered = eez_gdf.buffer(buffer_deg)

                bbox = eez_gdf.total_bounds
                minx, miny, maxx, maxy = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
                buffer_deg = 5.0  # Keep some buffer for the rectangular clip
                min_lat = miny - buffer_deg
                max_lat = maxy + buffer_deg

                # Find latitude indices manually instead of using sel()
                lats = ds.coords[lat_coord_name].values
                lat_indices = np.where((lats >= min_lat) & (lats <= max_lat))[0]
                if len(lat_indices) == 0:
                    # Fall back to nearest indices
                    lat_min_idx = np.argmin(np.abs(lats - min_lat))
                    lat_max_idx = np.argmin(np.abs(lats - max_lat))
                    lat_indices = np.arange(min(lat_min_idx, lat_max_idx), max(lat_min_idx, lat_max_idx) + 1)

                ds_lat = ds.isel({lat_dim_name: lat_indices})

                lons = ds.coords[lon_coord_name].values
                assume_0_360 = lons[0] >= 0 and lons[-1] <= 360
                min_lon = (minx - buffer_deg) % 360 if assume_0_360 else minx - buffer_deg
                max_lon = (maxx + buffer_deg) % 360 if assume_0_360 else maxx + buffer_deg

                # Find longitude indices manually
                lons_lat = ds_lat.coords[lon_coord_name].values
                if min_lon <= max_lon:
                    lon_indices = np.where((lons_lat >= min_lon) & (lons_lat <= max_lon))[0]
                    if len(lon_indices) == 0:
                        # Fall back to nearest indices
                        lon_min_idx = np.argmin(np.abs(lons_lat - min_lon))
                        lon_max_idx = np.argmin(np.abs(lons_lat - max_lon))
                        lon_indices = np.arange(min(lon_min_idx, lon_max_idx), max(lon_min_idx, lon_max_idx) + 1)

                    ds_clipped = ds_lat.isel({lon_dim_name: lon_indices})
                else:
                    # Handle wraparound case
                    lon_indices1 = np.where((lons_lat >= min_lon) & (lons_lat <= 360))[0]
                    lon_indices2 = np.where((lons_lat >= 0) & (lons_lat <= max_lon))[0]

                    if len(lon_indices1) == 0 and len(lon_indices2) == 0:
                        # Fall back to nearest
                        lon_min_idx = np.argmin(np.abs(lons_lat - min_lon))
                        lon_max_idx = np.argmin(np.abs(lons_lat - max_lon))
                        if lon_min_idx < lon_max_idx:
                            lon_indices = np.arange(lon_min_idx, lon_max_idx + 1)
                        else:
                            # Wraparound case
                            lon_indices = np.concatenate([np.arange(lon_min_idx, len(lons_lat)), np.arange(0, lon_max_idx + 1)])

                    all_lon_indices = np.concatenate([lon_indices1, lon_indices2])
                    all_lon_indices = np.unique(all_lon_indices)  # Remove duplicates
                    all_lon_indices = np.sort(all_lon_indices)

                    ds_clipped = ds_lat.isel({lon_dim_name: all_lon_indices})

                # Extract EEZ boundary coordinates for precise clipping
                all_coords = []
                for geom in eez_gdf.geometry:
                    if geom is not None:
                        if geom.geom_type == 'Polygon':
                            coords = list(geom.exterior.coords)
                        elif geom.geom_type == 'MultiPolygon':
                            for poly in geom.geoms:  # Iterate all polygons in MultiPolygon
                                coords = list(poly.exterior.coords)
                                all_coords.extend(coords)
                                break  # Use first polygon for bounds (sufficient)
                            continue
                        else:
                            continue
                        all_coords.extend(coords)

                # Get EEZ bounds (fallback to bounding box if no coordinates)
                if all_coords:
                    lons = [coord[0] for coord in all_coords]
                    lats = [coord[1] for coord in all_coords]
                    eez_min_lon, eez_max_lon = min(lons), max(lons)
                    eez_min_lat, eez_max_lat = min(lats), max(lats)
                else:
                    eez_min_lon, eez_min_lat, eez_max_lon, eez_max_lat = eez_gdf.total_bounds

                # Convert EEZ to 0-360 longitude system and create spatial mask
                eez_gdf_360 = eez_gdf.copy()
                for idx, geom in enumerate(eez_gdf_360.geometry):
                    if geom is not None:
                        if geom.geom_type == 'Polygon':
                            coords = list(geom.exterior.coords)
                            new_coords = [(lon + 360 if lon < 0 else lon, lat) for lon, lat in coords]
                            from shapely.geometry import Polygon
                            eez_gdf_360.geometry.iloc[idx] = Polygon(new_coords)
                        elif geom.geom_type == 'MultiPolygon':
                            polys = []
                            for poly in geom.geoms:
                                coords = list(poly.exterior.coords)
                                new_coords = [(lon + 360 if lon < 0 else lon, lat) for lon, lat in coords]
                                polys.append(Polygon(new_coords))
                            from shapely.geometry import MultiPolygon
                            eez_gdf_360.geometry.iloc[idx] = MultiPolygon(polys)
                        # Skip other types

                # Create mask: True for points inside EEZ boundary
                lats_clipped = ds_clipped.coords[lat_coord_name].values
                lons_clipped = ds_clipped.coords[lon_coord_name].values
                mask = np.zeros((len(lats_clipped), len(lons_clipped)), dtype=bool)

                for i, lat in enumerate(lats_clipped):
                    for j, lon in enumerate(lons_clipped):
                        point = Point(lon, lat)
                        mask[i, j] = any(geom.contains(point) for geom in eez_gdf_360.geometry if geom is not None)


                # Apply mask to data variables
                ds = ds_clipped.copy()
                for var_name in ds.data_vars:
                    if set(ds[var_name].dims) == set([lat_dim_name, lon_dim_name]):
                        data_array = ds[var_name].values
                        data_dims = ds[var_name].dims

                        # Find the indices of lat and lon dimensions in the data array
                        lat_dim_idx = data_dims.index(lat_dim_name)
                        lon_dim_idx = data_dims.index(lon_dim_name)

                        # Create mask with correct shape for this data array
                        if lat_dim_idx == 0 and lon_dim_idx == 1:  # (lat, lon)
                            data_mask = mask
                        elif lat_dim_idx == 1 and lon_dim_idx == 0:  # (lon, lat)
                            data_mask = mask.T
                        else:
                            continue

                        if data_array.shape == data_mask.shape:
                            masked_data = np.where(data_mask, data_array, np.nan)
                            ds = ds.assign({var_name: (data_dims, masked_data)})

        lat_len = len(ds.coords[lat_coord_name])
        lon_len = len(ds.coords[lon_coord_name])
        if lat_len == 0 or lon_len == 0:
            kml_root = ET.Element('kml', xmlns='http://www.opengis.net/kml/2.2')
            doc = ET.SubElement(kml_root, 'Document')
            ET.SubElement(doc, 'name').text = f"Ocean Currents (OSCAR V2.0 NRT) – {time_str} (no data in EEZ)"
            tree = ET.ElementTree(kml_root)
            tree.write(task.output_path, encoding='utf-8', xml_declaration=True)
            report_progress(task.weight, "Processing complete")
            return True

        # Coordinate names already determined above

        if lat_len < 2 or lon_len < 2:
            step_lat = step_lon = 1
        else:
            lat_res = abs(float(ds.coords[lat_coord_name][1].values - ds.coords[lat_coord_name][0].values))
            lon_res = abs(float(ds.coords[lon_coord_name][1].values - ds.coords[lon_coord_name][0].values))
            step_lat = max(1, int(np.ceil(spacing_deg / lat_res)))
            step_lon = max(1, int(np.ceil(spacing_deg / lon_res)))

        u = ds['u'].isel({lat_dim_name: slice(None, None, step_lat), lon_dim_name: slice(None, None, step_lon)})
        v = ds['v'].isel({lat_dim_name: slice(None, None, step_lat), lon_dim_name: slice(None, None, step_lon)})

        u_np = u.values.astype(np.float64)
        v_np = v.values.astype(np.float64)

        # Calculate speeds and directions
        mag_np = np.sqrt(u_np**2 + v_np**2)
        # Calculate direction in mathematical coordinates (0° = East)
        dir_math_np = np.degrees(np.arctan2(v_np, u_np)) % 360
        # Clean invalid values before casting (should be unnecessary but safe)
        dir_math_np = np.where(np.isfinite(dir_math_np), dir_math_np, 0)
        # Round to nearest integer, with 360 becoming 0
        with np.errstate(invalid='ignore'):
            dir_math_np = np.round(dir_math_np).astype(int) % 360
        # Convert to navigation coordinates (0° = North) for metadata
        dir_nav_np = (90 - dir_math_np) % 360
        # Get coordinates from the same subsampled data arrays
        lats_np = u.coords[lat_coord_name].values
        lons_np = u.coords[lon_coord_name].values


        # Determine which array index corresponds to which coordinate
        u_dims = u.dims
        lat_dim_idx = u_dims.index(lat_dim_name) if lat_dim_name in u_dims else 0
        lon_dim_idx = u_dims.index(lon_dim_name) if lon_dim_name in u_dims else 1

        # Convert longitude from 0-360 to -180/+180 range for KML compatibility
        lons_np = np.where(lons_np > 180, lons_np - 360, lons_np)



        max_mag = float(np.nanmax(mag_np)) or 1.0
        # Set arrow length limits based on spacing to prevent overlap
        # Maximum length is 80% of spacing to leave margin between arrows
        # Minimum length ensures visibility even for very low currents
        max_arrow_length = spacing_deg * 0.8
        min_arrow_length = 0.5  # Minimum visibility threshold - increased for better clickability
        arrow_length_deg = max(min_arrow_length, max_arrow_length)

        report_progress(task.weight * 0.3, "Generating arrow vectors...")

        kml_root = ET.Element('kml', xmlns='http://www.opengis.net/kml/2.2')
        doc = ET.SubElement(kml_root, 'Document')
        layer_name = f"Ocean Currents (OSCAR V2.0 NRT) – {time_str}"
        if task.clip_to_eez:
            layer_name += f" ({task.iso_code} EEZ clipped)"
        ET.SubElement(doc, 'name').text = layer_name

        # Style for line elements (shaft and arrowheads)
        line_style = ET.SubElement(doc, 'Style', id='arrowLine')
        ls = ET.SubElement(line_style, 'LineStyle')
        ET.SubElement(ls, 'color').text = task.color_abgr
        ET.SubElement(ls, 'width').text = '4'

        # Style for any polygon elements (not currently used)
        poly_style = ET.SubElement(doc, 'Style', id='arrowHead')
        ps = ET.SubElement(poly_style, 'PolyStyle')
        ET.SubElement(ps, 'color').text = task.color_abgr
        ET.SubElement(ps, 'fill').text = '1'
        ET.SubElement(ps, 'outline').text = '1'
        ET.SubElement(ps, 'outlineColor').text = 'ffffffff'

        count = 0

        for i in range(mag_np.shape[0]):
            for j in range(mag_np.shape[1]):

                # Access coordinates using the correct dimension indices
                if lat_dim_idx == 0:
                    lat = float(lats_np[i])
                    lon = float(lons_np[j])
                else:
                    lon = float(lons_np[i])
                    lat = float(lats_np[j])


                speed = mag_np[i, j]
                dir_nav = dir_nav_np[i, j]  # Navigation direction for metadata
                dir_math = dir_math_np[i, j]  # Mathematical direction for drawing


                # Only create markers for points with valid current data
                # Use a more reasonable speed threshold (0.01 m/s = ~0.02 knots, minimum detectable current)
                if np.isnan(speed) or speed <= 0.01 or np.isnan(dir_nav) or np.isnan(dir_math):
                    continue  # Skip points with no valid current data

                # Valid current data - create simple arrow marker
                pm = ET.SubElement(doc, 'Placemark')

                speed_knots = speed * 1.94384
                ET.SubElement(pm, 'name').text = "Ocean Current"  # Standard title
                desc_text = f"{speed_knots:.1f} kts ({speed:.1f} m/s) at {dir_nav:.0f} deg"  # Detailed description


                # Create arrow shaft as LineString
                line_string = ET.SubElement(pm, 'LineString')
                ET.SubElement(line_string, 'extrude').text = '1'
                ET.SubElement(line_string, 'tessellate').text = '1'
                ET.SubElement(line_string, 'altitudeMode').text = 'clampToGround'

                        # Scale arrow length based on current speed (0-5 knot standardized range)
                speed_knots = speed * 1.94384
                min_length = 0.25 * arrow_length_deg  # 25% for 0 knots
                if speed_knots <= 0:
                    length = min_length
                elif speed_knots >= 5.0:  # 5 knots = ~2.6 m/s
                    length = arrow_length_deg  # 100% for strong currents
                else:
                    # Linear interpolation: 0 knots → 25%, 5 knots → 100%
                    length = min_length + (speed_knots / 5.0) * (arrow_length_deg - min_length)

                # Calculate end point of arrow
                end_lat = lat + length * np.sin(np.radians(dir_math))
                end_lon = lon + length * np.cos(np.radians(dir_math))

                # Normalize end longitude
                end_lon_norm = ((end_lon + 180) % 360) - 180

                # Create arrow shaft as line from start to end
                coords_text = f"{lon:.6f},{lat:.6f},100 {end_lon_norm:.6f},{end_lat:.6f},100"
                coords = ET.SubElement(line_string, 'coordinates')
                coords.text = coords_text

                ET.SubElement(pm, 'styleUrl').text = '#arrowLine'

                # Create arrowhead as two lines forming a "V" shape
                head_size = 0.25 * (spacing_deg / 3.0)  # Scale with density

                # Calculate and create arrowhead lines
                head_left_lon = end_lon_norm + head_size * np.cos(np.radians(dir_math + 135))
                head_left_lat = end_lat + head_size * np.sin(np.radians(dir_math + 135))
                head_right_lon = end_lon_norm + head_size * np.cos(np.radians(dir_math - 135))
                head_right_lat = end_lat + head_size * np.sin(np.radians(dir_math - 135))

                # Create arrowhead lines with normalized coordinates
                _create_arrowhead_line(doc, end_lon_norm, end_lat,
                                     ((head_left_lon + 180) % 360) - 180, head_left_lat)
                _create_arrowhead_line(doc, end_lon_norm, end_lat,
                                     ((head_right_lon + 180) % 360) - 180, head_right_lat)

                # Add description to main arrow placemarks for clickability
                if pm.find('name') is not None and pm.find('name').text:
                    ET.SubElement(pm, 'description').text = desc_text
                count += 1


        tree = ET.ElementTree(kml_root)
        tree.write(task.output_path, encoding='utf-8', xml_declaration=True)
        # Write meta
        meta_dir = Path(output_dir) / "_metadata"
        meta_dir.mkdir(exist_ok=True)
        meta_path = meta_dir / (Path(task.output_path).name + ".meta")
        meta_settings = {
            "color": task.settings_color,
            "opacity": task.settings_opacity,
            "density": str(task.density)
        }
        try:
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta_settings, f, indent=2)
            if os.name == 'nt':
                try:
                    FILE_ATTRIBUTE_HIDDEN = 0x2
                    ctypes.windll.kernel32.SetFileAttributesW(str(meta_dir), FILE_ATTRIBUTE_HIDDEN)
                except Exception as e:
                    report_progress(0, f"Warning: Could not hide _metadata folder: {e}")
        except Exception as e:
            report_progress(0, f"Warning: Could not write meta file: {e}")
        report_progress(task.weight * 0.7, "KML generation complete")
        return True
    except Exception as e:
        report_progress(0, f"Ocean currents processing error: {str(e)}")
        return False
    finally:
        if 'ds' in locals():
            ds.close()

def process(task: LayerTask, report_progress, output_dir: str, cache_dir: str, username: str, password: str) -> bool:
    """Process OSCAR ocean currents data.

    Downloads the latest OSCAR ocean surface current data and converts it to KML format.

    Args:
        task: Layer task configuration
        report_progress: Progress reporting function
        output_dir: Output directory for generated files
        cache_dir: Cache directory for downloaded data
        username: NASA Earthdata username
        password: NASA Earthdata password

    Returns:
        True if processing successful, False otherwise
    """
    report_progress(0, f"Fetching latest ocean surface currents from NOAA OSCAR V2.0 NRT...")
    try:
        granule_url, latest_date = get_latest_oscar_nrt_granule_info()
        temp_nc = os.path.join(cache_dir, "oscar_latest.nc")

        use_cached = False
        if os.path.exists(temp_nc):
            with xr.open_dataset(temp_nc) as ds_temp:
                time_vals = ds_temp['time'].values
                # Extract scalar value from array
                if np.size(time_vals) > 0:
                    time_val = time_vals[-1] if np.size(time_vals) > 1 else time_vals.item()
                else:
                    time_val = None

                if time_val is not None:
                    try:
                        if isinstance(time_val, (cftime._cftime.DatetimeJulian, cftime._cftime.Datetime360Day, cftime._cftime.DatetimeNoLeap, cftime._cftime.DatetimeProlepticGregorian)):
                            time_dt = pd.Timestamp(time_val.isoformat())
                        else:
                            ref_date = pd.Timestamp('1990-01-01')
                            time_dt = ref_date + pd.to_timedelta(time_val, unit='D')
                        cached_date = time_dt.strftime("%Y-%m-%d")
                        if cached_date == latest_date:
                            use_cached = True
                            report_progress(0, "Using cached latest granule...")
                    except Exception as e:
                        report_progress(0, f"Cache date parsing warning: {e}")
                        pass

        if not use_cached:
            report_progress(0, "Downloading latest granule (~100-200 MB, may take a minute)...")
            # Get Earthdata access token
            access_token = get_earthdata_token(username, password)
            headers = {"Authorization": f"Bearer {access_token}"}

            # Attempt download with token
            with requests.get(granule_url, headers=headers, stream=True, timeout=120) as r:
                # If token is expired (401), try getting a fresh token once
                if r.status_code == 401:
                    report_progress(0, "Token expired, getting fresh token...")
                    access_token = get_earthdata_token(username, password)
                    headers = {"Authorization": f"Bearer {access_token}"}
                    r = requests.get(granule_url, headers=headers, stream=True, timeout=120)

                r.raise_for_status()

                # Get total size for progress feedback
                total_size = int(r.headers.get('Content-Length', 0))

                try:
                    from tqdm import tqdm
                    use_tqdm = True
                except ImportError:
                    use_tqdm = False

                if use_tqdm:
                    with open(temp_nc, 'wb') as f, tqdm(
                        total=total_size,
                        desc="Downloading OSCAR ocean currents .nc",
                        unit='B',
                        unit_scale=True,
                        unit_divisor=1024,
                        bar_format='{desc}: {total_fmt} [{elapsed}, {rate_fmt}{postfix}]'
                    ) as pbar:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                pbar.update(len(chunk))
                else:
                    with open(temp_nc, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

        return process_oscar_core(task, report_progress, output_dir, cache_dir, temp_nc, latest_date)

    except Exception as e:
        report_progress(0, f"Ocean currents processing error: {str(e)}")
        return False

def refresh_dynamic_caches():
    """Refresh OSCAR ocean currents dynamic cache"""
    print("OSCAR: Refreshing dynamic cache...")

    try:
        # Load environment variables from .env file if it exists
        try:
            # Try multiple possible locations for .env file
            env_paths = [
                Path(__file__).parent.parent / '.env',  # downloaders/../.env
                Path.cwd() / '.env',  # Current working directory
                Path.home() / '.env',  # Home directory (fallback)
            ]

            env_loaded = False
            for env_path in env_paths:
                print(f"OSCAR: Trying .env at: {env_path}")
                if env_path.exists():
                    # Read .env file directly and set environment variables
                    try:
                        with open(env_path, 'r', encoding='utf-8') as f:
                            for line in f:
                                line = line.strip()
                                if line and not line.startswith('#') and '=' in line:
                                    key, value = line.split('=', 1)
                                    key = key.strip()
                                    value = value.strip()
                                    os.environ[key] = value
                                    print(f"OSCAR: Set {key} from .env file")
                        env_loaded = True
                        print(f"OSCAR: Successfully loaded credentials from {env_path}")
                        break
                    except Exception as e:
                        print(f"OSCAR: Error reading .env file at {env_path}: {e}")

            if not env_loaded:
                print("OSCAR: No .env file found in any expected location")

        except Exception as e:
            print(f"OSCAR: Error loading environment variables: {e}")

        # Get NASA credentials from environment
        username = os.getenv('NASA_USERNAME')
        password = os.getenv('NASA_PASSWORD')

        if not username or not password:
            print("OSCAR: NASA_USERNAME and NASA_PASSWORD environment variables not set")
            return False

        # Create cache directory if it doesn't exist
        cache_dir = Path(__file__).parent.parent / "cache" / "raw_source_data" / "dynamic" / "oscar_currents"
        cache_dir.mkdir(parents=True, exist_ok=True)

        print("OSCAR: Authenticating with NASA Earthdata...")

        # Get Earthdata token
        token = get_earthdata_token(username, password)
        if not token:
            print("OSCAR: Failed to authenticate with NASA Earthdata")
            return False

        # Find latest OSCAR data using CMR
        print("OSCAR: Searching for latest OSCAR data...")

        # Use the known OSCAR collection ID directly
        oscar_collection_id = 'C2102958977-POCLOUD'
        print(f"OSCAR: Using collection ID: {oscar_collection_id}")

        headers = {"Authorization": f"Bearer {token}"}
        granules_url = "https://cmr.earthdata.nasa.gov/search/granules.json"
        granules_params = {
            'collection_concept_id': oscar_collection_id,
            'sort_key': '-start_date',
            'page_size': '1'
        }

        response = requests.get(granules_url, params=granules_params, headers=headers, timeout=30)

        if response.status_code == 401:
            print("OSCAR: Authentication failed for granules search")
            return False

        if response.status_code != 200:
            print(f"OSCAR: Granules search failed with status {response.status_code}")
            print(f"OSCAR: Response: {response.text[:500]}")
            return False

        granules_data = response.json()

        if 'feed' in granules_data and 'entry' in granules_data['feed'] and len(granules_data['feed']['entry']) > 0:
            granule = granules_data['feed']['entry'][0]
            granule_url = None

            # Find the download URL for the NetCDF file
            for link in granule.get('links', []):
                href = link.get('href', '')
                if href.endswith('.nc') and ('data#' in link.get('rel', '') or link.get('rel') == 'enclosure'):
                    granule_url = href
                    break

            if granule_url:
                print(f"OSCAR: Downloading OSCAR data from {granule_url}")
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
                cache_file = cache_dir / f"oscar_currents_{timestamp}.nc"

                # Download the NetCDF file
                response = requests.get(granule_url, headers=headers, stream=True, timeout=300)

                if response.status_code == 401:
                    print("OSCAR: Download authentication failed")
                    return False

                if response.status_code != 200:
                    print(f"OSCAR: Download failed with status {response.status_code}")
                    print(f"OSCAR: Response: {response.text[:500]}")
                    return False

                response.raise_for_status()

                # Get total size for progress feedback
                total_size = int(response.headers.get('Content-Length', 0))

                try:
                    from tqdm import tqdm
                    use_tqdm = True
                except ImportError:
                    use_tqdm = False

                if use_tqdm:
                    with open(cache_file, 'wb') as f, tqdm(
                        total=total_size,
                        desc="Downloading OSCAR ocean currents .nc",
                        unit='B',
                        unit_scale=True,
                        unit_divisor=1024,
                        bar_format='{desc}: {total_fmt} [{elapsed}, {rate_fmt}{postfix}]'
                    ) as pbar:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                pbar.update(len(chunk))
                else:
                    with open(cache_file, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

                print(f"OSCAR: Downloaded OSCAR data, size = {cache_file.stat().st_size} bytes")
                print("OSCAR: Dynamic cache refreshed successfully")
                return True
            else:
                print("OSCAR: No suitable download URL found")
                available_nc_links = [link.get('href') for link in granule.get('links', []) if link.get('href', '').endswith('.nc')]
                print(f"OSCAR: Available .nc links: {available_nc_links}")
                return False
        else:
            print("OSCAR: No OSCAR granules found")
            print(f"OSCAR: Granules response keys: {list(granules_data.keys()) if isinstance(granules_data, dict) else type(granules_data)}")
            return False
    except Exception as e:
        print(f"OSCAR: Dynamic cache refresh failed: {e}")
        return False