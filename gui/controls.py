import requests
import json
from core.config import COUNTRIES_JSON_URL

def load_countries():
    try:
        response = requests.get(COUNTRIES_JSON_URL, timeout=20)
        response.raise_for_status()
        data = json.loads(response.text)
        country_list = []
        for feature in data.get('features', []):
            props = feature.get('properties', {})
            territory = props.get('territory1')
            iso = props.get('iso_ter1')
            if territory and iso:
                country_list.append(f"{territory} ({iso})")
        country_list.sort()
        return country_list
    except Exception as e:
        print(f"Error loading countries: {e}")
        return ["No countries loaded (check internet)"]

def toggle_country_layers(state, vars_dict):
    for key in ['territorial', 'contiguous', 'eez', 'ecs', 'mpa', 'seastate_country']:
        vars_dict[key].set(state)

def toggle_global_layers(state, vars_dict):
    for key in ['cables', 'seastate_global', 'navwarnings']:
        vars_dict[key].set(state)