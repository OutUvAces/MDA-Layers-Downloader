"""
Geometry simplification utilities.

This module contains functions for simplifying geospatial geometries to reduce
file sizes while preserving topological relationships.
"""

import geopandas as gpd
from typing import Optional
from shapely import Geometry

def simplify_geom(geom: Optional[Geometry], tol: float):
    """Simplify a geometry while preserving topology.

    Applies the Douglas-Peucker simplification algorithm to reduce the number
    of vertices in a geometry while maintaining its topological properties.

    Args:
        geom: Input geometry to simplify (can be None)
        tol: Tolerance value for simplification (higher values = more simplification)

    Returns:
        Simplified geometry, or original geometry if invalid/None
    """
    if geom is None or not geom.is_valid:
        return geom
    return geom.simplify(tol, preserve_topology=True)