"""
Type definitions and data classes for the MDA Layers Downloader application.

This module contains type aliases and data structures used throughout the application
for representing layer configurations and processing tasks.
"""

from dataclasses import dataclass
from typing import Optional, Literal

LayerType = Literal["territorial", "contiguous", "eez", "ecs", "mpa", "cables", "seastate", "navwarnings"]
"""Type alias for valid layer types in the application."""

@dataclass
class LayerSettings:
    """Configuration settings for all layer types in the application.

    This class contains boolean flags for enabling/disabling layers and their
    associated color and opacity settings.
    """

    def __post_init__(self):
        """Post-initialization hook for diagnostics"""
        print("LayerSettings __post_init__: Checking fields...")

        # Check all fields that might be used with len()
        fields_to_check = ['layers', 'territorial_color', 'eez_color', 'contiguous_color', 'mpa_color',
                          'ecs_color', 'cables_color', 'seastate_color', 'navwarnings_color',
                          'territorial_opacity', 'eez_opacity', 'contiguous_opacity', 'mpa_opacity',
                          'ecs_opacity', 'cables_opacity', 'seastate_opacity', 'navwarnings_opacity']

        for field_name in fields_to_check:
            if hasattr(self, field_name):
                value = getattr(self, field_name)
                print(f"LayerSettings field {field_name} = {value}, type = {type(value)}")
                if value is None:
                    print(f"LayerSettings WARNING: {field_name} field is None")
                    # Fix None values that might cause len() errors
                    if field_name == 'layers':
                        print("LayerSettings: Fixing layers = None to []")
                        self.layers = []
                    elif 'color' in field_name:
                        print(f"LayerSettings: Fixing {field_name} = None to '#ffffff'")
                        setattr(self, field_name, '#ffffff')
                    elif 'opacity' in field_name:
                        print(f"LayerSettings: Fixing {field_name} = None to '20'")
                        setattr(self, field_name, '20')
                elif hasattr(value, '__len__'):  # Check if it has len()
                    try:
                        length = len(value)
                        print(f"LayerSettings {field_name} len = {length}")
                    except TypeError as e:
                        print(f"LayerSettings ERROR: len() failed on {field_name}: {e}")
                        # Fix the problematic field
                        if field_name == 'layers':
                            print("LayerSettings: Fixing layers with len() error to []")
                            self.layers = []
            else:
                print(f"LayerSettings field {field_name} does not exist")

    # Layer enable/disable flags
    territorial: bool
    """Enable territorial waters layer."""

    contiguous: bool
    """Enable contiguous zone layer."""

    mpa: bool
    """Enable marine protected areas layer."""

    eez: bool
    """Enable exclusive economic zone layer."""

    ecs: bool
    """Enable extended continental shelf layer."""

    cables: bool
    """Enable submarine cables layer."""

    seastate_country: bool
    """Enable country-level sea state layer."""

    seastate_global: bool
    """Enable global sea state layer."""

    navwarnings: bool
    """Enable navigation warnings layer."""

    # Color settings (hex color codes)
    territorial_color: str
    """Color for territorial waters layer."""

    contiguous_color: str
    """Color for contiguous zone layer."""

    mpa_color: str
    """Color for marine protected areas layer."""

    eez_color: str
    """Color for exclusive economic zone layer."""

    ecs_color: str
    """Color for extended continental shelf layer."""

    cables_color: str
    """Color for submarine cables layer."""

    seastate_color: str
    """Color for sea state layers."""

    navwarnings_color: str
    """Color for navigation warnings layer."""

    # Opacity settings (0-100 as string)
    territorial_opacity: str
    """Opacity for territorial waters layer."""

    contiguous_opacity: str
    """Opacity for contiguous zone layer."""

    mpa_opacity: str
    """Opacity for marine protected areas layer."""

    eez_opacity: str
    """Opacity for exclusive economic zone layer."""

    ecs_opacity: str
    """Opacity for extended continental shelf layer."""

    cables_opacity: str
    """Opacity for submarine cables layer."""

    seastate_opacity: str
    """Opacity for sea state layers."""

    navwarnings_opacity: str
    """Opacity for navigation warnings layer."""

    # Special flags
    navwarnings_custom: bool
    """Use custom navigation warnings settings."""

    cables_random: bool
    """Use random colors for individual cables."""

    seastate_density_country: float
    """Density/simplification factor for country-level sea state data."""

    seastate_density_global: float
    """Density/simplification factor for global sea state data."""
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
    """Represents a single layer processing task.

    This class encapsulates all the information needed to process and generate
    a KML layer, including its type, styling, and optional parameters.
    """

    type: LayerType
    """The type of layer to process."""

    name: str
    """Display name for the layer."""

    output_path: str
    """File path where the processed layer will be saved."""

    color_abgr: str
    """KML ABGR color code for the layer."""

    weight: float
    """Layer weight/priority for ordering in the output."""

    url: Optional[str] = None
    """Optional URL for data source."""

    iso_code: Optional[str] = None
    """Optional ISO country code for country-specific layers."""

    density: Optional[float] = None
    """Optional density/simplification factor for geometry processing."""

    clip_to_eez: bool = False
    """Whether to clip the layer to EEZ boundaries."""

    use_random_colors: bool = False
    """Whether to use random colors for individual features."""

    use_custom_colors: bool = True
    """Whether to use custom user-defined colors."""

    user_color_hex: Optional[str] = None
    """User-defined hex color code."""

    user_opacity: Optional[str] = None
    """User-defined opacity value."""

    settings_color: Optional[str] = None
    """General color setting from configuration."""

    settings_opacity: Optional[str] = None
    """General opacity setting from configuration."""