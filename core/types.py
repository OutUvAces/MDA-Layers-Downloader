from dataclasses import dataclass
from typing import Optional, Literal

LayerType = Literal["territorial", "contiguous", "eez", "ecs", "mpa", "cables", "seastate", "navwarnings"]

@dataclass
class LayerSettings:
    territorial: bool
    contiguous: bool
    mpa: bool
    eez: bool
    ecs: bool
    cables: bool
    seastate_country: bool
    seastate_global: bool
    navwarnings: bool
    territorial_color: str
    contiguous_color: str
    mpa_color: str
    eez_color: str
    ecs_color: str
    cables_color: str
    seastate_color: str
    navwarnings_color: str
    territorial_opacity: str
    contiguous_opacity: str
    mpa_opacity: str
    eez_opacity: str
    ecs_opacity: str
    cables_opacity: str
    seastate_opacity: str
    navwarnings_opacity: str
    navwarnings_custom: bool
    cables_random: bool
    seastate_density_country: float
    seastate_density_global: float

@dataclass
class LayerTask:
    type: LayerType
    name: str
    output_path: str
    color_abgr: str
    weight: float
    url: Optional[str] = None
    iso_code: Optional[str] = None
    density: Optional[float] = None
    clip_to_eez: bool = False
    use_random_colors: bool = False
    use_custom_colors: bool = True
    user_color_hex: Optional[str] = None
    user_opacity: Optional[str] = None
    settings_color: Optional[str] = None  # Renamed for general color
    settings_opacity: Optional[str] = None  # Renamed for general opacity