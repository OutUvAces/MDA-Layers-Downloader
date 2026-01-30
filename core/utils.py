"""
Utility functions for the MDA Layers Downloader application.

This module contains helper functions for color conversion and XML manipulation
used throughout the application.
"""

import xml.etree.ElementTree as ET
from typing import Optional

def hex_to_kml_abgr(hex_color: str, opacity_percent: int | float) -> str:
    """Convert a hex color with opacity percentage to KML ABGR format.

    Args:
        hex_color: Hex color code (e.g., "#ff0000" for red)
        opacity_percent: Opacity as percentage (0-100)

    Returns:
        KML ABGR color string (e.g., "ff0000ff" for opaque red)

    Note:
        KML uses ABGR format where A=alpha, B=blue, G=green, R=red.
        Returns "ff000000" (transparent black) for invalid hex colors.
    """
    opacity = int(float(opacity_percent) * 2.55)
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        return "ff000000"
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"{opacity:02x}{b:02x}{g:02x}{r:02x}"

def add_data(parent, name: str, value):
    """Add a Data element to an XML parent element.

    This is a helper function for creating KML Data elements with name/value pairs.

    Args:
        parent: XML element to add the Data element to
        name: Name attribute for the Data element
        value: Value to set (will be converted to string)
    """
    data = ET.SubElement(parent, 'Data', {'name': name})
    ET.SubElement(data, 'value').text = str(value)