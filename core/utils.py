import xml.etree.ElementTree as ET
from typing import Optional

def hex_to_kml_abgr(hex_color: str, opacity_percent: int | float) -> str:
    opacity = int(float(opacity_percent) * 2.55)
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        return "ff000000"
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"{opacity:02x}{b:02x}{g:02x}{r:02x}"

def add_data(parent, name: str, value):
    data = ET.SubElement(parent, 'Data', {'name': name})
    ET.SubElement(data, 'value').text = str(value)