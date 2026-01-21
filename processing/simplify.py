import geopandas as gpd
from typing import Optional

def simplify_geom(geom: Optional[gpd.Geometry], tol: float):
    if geom is None or not geom.is_valid:
        return geom
    return geom.simplify(tol, preserve_topology=True)