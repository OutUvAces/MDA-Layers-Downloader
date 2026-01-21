import os
import requests
import xml.etree.ElementTree as ET
import geopandas as gpd
from core.utils import hex_to_kml_abgr

NS_KML = {'kml': 'http://www.opengis.net/kml/2.2'}

def download_kml(url: str, temp_kml: str) -> bool:
    # Disable SSL verification for marine data downloads (certificate issues with some servers)
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.get(url, timeout=45, verify=False)
        response.raise_for_status()
        with open(temp_kml, 'w', encoding='utf-8') as f:
            f.write(response.text)
        return True
    except Exception:
        return False

def process_kml(temp_kml: str, output_kml: str, fill_color: str) -> bool:
    ET.register_namespace('', 'http://www.opengis.net/kml/2.2')
    try:
        tree = ET.parse(temp_kml)
        root = tree.getroot()
    except Exception:
        return False

    doc = root.find('kml:Document', NS_KML)
    if doc is None:
        return False

    style = doc.find('kml:Style', NS_KML)
    if style is None:
        style = ET.SubElement(doc, 'Style')
        style.set('id', 'customStyle')

    # LineStyle
    line_style = style.find('kml:LineStyle', NS_KML) or ET.SubElement(style, 'LineStyle')
    (line_style.find('kml:width', NS_KML) or ET.SubElement(line_style, 'width')).text = '0.1'

    # PolyStyle
    poly_style = style.find('kml:PolyStyle', NS_KML) or ET.SubElement(style, 'PolyStyle')
    (poly_style.find('kml:fill', NS_KML) or ET.SubElement(poly_style, 'fill')).text = '1'
    (poly_style.find('kml:color', NS_KML) or ET.SubElement(poly_style, 'color')).text = fill_color

    for pm in doc.findall('.//kml:Placemark', NS_KML):
        style_url = pm.find('kml:styleUrl', NS_KML) or ET.SubElement(pm, 'styleUrl')
        style_url.text = '#customStyle'

    tree.write(output_kml, encoding='utf-8', xml_declaration=True)
    return True

def process_line_kml(temp_geojson: str, output_kml: str, user_color_hex: str, user_opacity: str, use_random: bool) -> bool:
    try:
        gdf = gpd.read_file(temp_geojson)
        if gdf.empty:
            return False

        temp_temp_kml = output_kml + ".temp.kml"
        gdf.to_file(temp_temp_kml, driver='KML')

        ET.register_namespace('', 'http://www.opengis.net/kml/2.2')
        ET.register_namespace('gx', 'http://www.google.com/kml/ext/2.2')

        tree = ET.parse(temp_temp_kml)
        root = tree.getroot()
        doc = root.find('kml:Document', NS_KML) or ET.SubElement(root, '{http://www.opengis.net/kml/2.2}Document')

        # Remove existing styles
        for pm in doc.findall('.//kml:Placemark', NS_KML):
            inline = pm.find('kml:Style', NS_KML)
            while inline is not None:
                pm.remove(inline)
                inline = pm.find('kml:Style', NS_KML)
        for style in doc.findall('kml:Style', NS_KML):
            doc.remove(style)

        opacity_int = int(int(user_opacity) * 2.55)
        opacity_hex = f"{opacity_int:02x}"

        if use_random:
            cable_palette = [
                (242, 12, 12), (242, 81, 12), (242, 150, 12), (242, 219, 12),
                (196, 242, 12), (127, 242, 12), (58, 242, 12), (12, 242, 35),
                (12, 242, 104), (12, 242, 173), (12, 242, 242), (12, 173, 242),
                (12, 104, 242), (12, 35, 242), (58, 12, 242), (127, 12, 242),
                (196, 12, 242), (242, 12, 219), (242, 12, 150), (242, 12, 81),
            ]
            num_styles = len(cable_palette)
            style_ids = []
            for s in range(num_styles):
                style_id = f"cableStyle{s}"
                style_ids.append(style_id)
                style = ET.SubElement(doc, 'Style')
                style.set('id', style_id)
                line_style = ET.SubElement(style, 'LineStyle')
                ET.SubElement(line_style, 'width').text = '3.5'
                r, g, b = cable_palette[s]
                color_hex = f"{opacity_hex}{b:02x}{g:02x}{r:02x}"
                ET.SubElement(line_style, 'color').text = color_hex
                gx_line_style = ET.SubElement(style, '{http://www.google.com/kml/ext/2.2}LineStyle')
                ET.SubElement(gx_line_style, '{http://www.google.com/kml/ext/2.2}outerColor').text = 'ff000000'
                ET.SubElement(gx_line_style, '{http://www.google.com/kml/ext/2.2}outerWidth').text = '2'

            for idx, pm in enumerate(doc.findall('.//kml:Placemark', NS_KML)):
                style_url = pm.find('kml:styleUrl', NS_KML) or ET.SubElement(pm, 'styleUrl')
                style_url.text = f"#{style_ids[idx % num_styles]}"
        else:
            style = ET.SubElement(doc, 'Style')
            style.set('id', 'uniformCableStyle')
            line_style = ET.SubElement(style, 'LineStyle')
            ET.SubElement(line_style, 'width').text = '3.5'
            color_hex = hex_to_kml_abgr(user_color_hex, int(user_opacity))
            ET.SubElement(line_style, 'color').text = color_hex
            gx_line_style = ET.SubElement(style, '{http://www.google.com/kml/ext/2.2}LineStyle')
            ET.SubElement(gx_line_style, '{http://www.google.com/kml/ext/2.2}outerColor').text = 'ff000000'
            ET.SubElement(gx_line_style, '{http://www.google.com/kml/ext/2.2}outerWidth').text = '2'
            for pm in doc.findall('.//kml:Placemark', NS_KML):
                style_url = pm.find('kml:styleUrl', NS_KML) or ET.SubElement(pm, 'styleUrl')
                style_url.text = '#uniformCableStyle'

        tree.write(output_kml, encoding='utf-8', xml_declaration=True)
        return True
    except Exception:
        return False
    finally:
        temp = output_kml + ".temp.kml"
        if os.path.exists(temp):
            try:
                os.remove(temp)
            except:
                pass