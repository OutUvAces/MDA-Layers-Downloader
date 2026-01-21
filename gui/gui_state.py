"""
GUI State Management
Centralizes all GUI state variables and provides a clean interface for managing UI state.
"""
import tkinter as tk
from core.config import DEFAULT_COLORS, DEFAULT_OPACITIES, DENSITY_OPTIONS


class GUIState:
    """Manages all GUI widget references and state variables"""

    def __init__(self):
        # Main widgets
        self.root = None
        self.log_text = None
        self.start_button = None
        self.country_combo = None
        self.progress_bar = None
        self.status_label = None

        # Layer selection variables
        self.territorial_var = None
        self.contiguous_var = None
        self.mpa_var = None
        self.eez_var = None
        self.ecs_var = None
        self.cables_var = None
        self.seastate_country_var = None
        self.seastate_global_var = None
        self.navwarnings_var = None

        # Color variables
        self.territorial_color_var = None
        self.contiguous_color_var = None
        self.mpa_color_var = None
        self.eez_color_var = None
        self.ecs_color_var = None
        self.cables_color_var = None
        self.seastate_color_var = None
        self.navwarnings_color_var = None

        # Opacity variables
        self.territorial_opacity = None
        self.contiguous_opacity = None
        self.mpa_opacity = None
        self.eez_opacity = None
        self.ecs_opacity = None
        self.cables_opacity = None
        self.seastate_opacity = None
        self.navwarnings_opacity = None

        # Special variables
        self.cables_random_var = None
        self.navwarnings_custom_var = None
        self.seastate_density_country = None
        self.seastate_density_global = None

    def initialize_variables(self):
        """Initialize all tkinter variables with default values"""
        # Layer selection variables
        self.territorial_var = tk.BooleanVar(value=False)
        self.contiguous_var = tk.BooleanVar(value=False)
        self.eez_var = tk.BooleanVar(value=False)
        self.ecs_var = tk.BooleanVar(value=False)
        self.mpa_var = tk.BooleanVar(value=False)
        self.cables_var = tk.BooleanVar(value=False)
        self.seastate_country_var = tk.BooleanVar(value=False)
        self.seastate_global_var = tk.BooleanVar(value=False)
        self.navwarnings_var = tk.BooleanVar(value=False)

        # Color variables
        self.territorial_color_var = tk.StringVar(value=DEFAULT_COLORS["territorial"])
        self.contiguous_color_var = tk.StringVar(value=DEFAULT_COLORS["contiguous"])
        self.mpa_color_var = tk.StringVar(value=DEFAULT_COLORS["mpa"])
        self.eez_color_var = tk.StringVar(value=DEFAULT_COLORS["eez"])
        self.ecs_color_var = tk.StringVar(value=DEFAULT_COLORS["ecs"])
        self.cables_color_var = tk.StringVar(value=DEFAULT_COLORS["cables"])
        self.seastate_color_var = tk.StringVar(value=DEFAULT_COLORS["seastate"])
        self.navwarnings_color_var = tk.StringVar(value=DEFAULT_COLORS["navwarnings"])

        # Opacity variables
        self.territorial_opacity = tk.StringVar(value=DEFAULT_OPACITIES["territorial"])
        self.contiguous_opacity = tk.StringVar(value=DEFAULT_OPACITIES["contiguous"])
        self.mpa_opacity = tk.StringVar(value=DEFAULT_OPACITIES["mpa"])
        self.eez_opacity = tk.StringVar(value=DEFAULT_OPACITIES["eez"])
        self.ecs_opacity = tk.StringVar(value=DEFAULT_OPACITIES["ecs"])
        self.cables_opacity = tk.StringVar(value=DEFAULT_OPACITIES["cables"])
        self.seastate_opacity = tk.StringVar(value=DEFAULT_OPACITIES["seastate"])
        self.navwarnings_opacity = tk.StringVar(value=DEFAULT_OPACITIES["navwarnings"])

        # Special variables
        self.cables_random_var = tk.BooleanVar(value=True)
        self.navwarnings_custom_var = tk.BooleanVar(value=True)
        self.seastate_density_country = tk.StringVar(value=DENSITY_OPTIONS[2])  # high (0.5°)
        self.seastate_density_global = tk.StringVar(value=DENSITY_OPTIONS[0])   # low (3.0°)

    def get_layer_variables(self):
        """Get all layer selection variables as a dict"""
        return {
            'territorial': self.territorial_var,
            'contiguous': self.contiguous_var,
            'eez': self.eez_var,
            'ecs': self.ecs_var,
            'mpa': self.mpa_var,
            'seastate_country': self.seastate_country_var,
            'cables': self.cables_var,
            'seastate_global': self.seastate_global_var,
            'navwarnings': self.navwarnings_var,
        }

    def reset_to_defaults(self):
        """Reset all color, opacity, density, and random values to defaults"""
        from core.config import DEFAULT_COLORS, DEFAULT_OPACITIES

        # Reset layer colors and opacities
        self.territorial_color_var.set(DEFAULT_COLORS["territorial"])
        self.territorial_opacity.set(DEFAULT_OPACITIES["territorial"])
        self.contiguous_color_var.set(DEFAULT_COLORS["contiguous"])
        self.contiguous_opacity.set(DEFAULT_OPACITIES["contiguous"])
        self.eez_color_var.set(DEFAULT_COLORS["eez"])
        self.eez_opacity.set(DEFAULT_OPACITIES["eez"])
        self.ecs_color_var.set(DEFAULT_COLORS["ecs"])
        self.ecs_opacity.set(DEFAULT_OPACITIES["ecs"])
        self.mpa_color_var.set(DEFAULT_COLORS["mpa"])
        self.mpa_opacity.set(DEFAULT_OPACITIES["mpa"])
        self.cables_color_var.set(DEFAULT_COLORS["cables"])
        self.cables_opacity.set(DEFAULT_OPACITIES["cables"])

        # Reset ocean currents settings
        self.seastate_color_var.set(DEFAULT_COLORS["seastate"])
        self.seastate_opacity.set(DEFAULT_OPACITIES["seastate"])
        self.seastate_density_country.set("high")  # High density for country-specific (more detail)
        self.seastate_density_global.set("low")    # Low density for global (performance)

        # Reset navigation warnings settings
        self.navwarnings_color_var.set(DEFAULT_COLORS["navwarnings"])
        self.navwarnings_opacity.set(DEFAULT_OPACITIES["navwarnings"])
        self.navwarnings_custom_var.set(True)  # Reset to custom colors/icons by default

        # Reset cables random toggle to True (default)
        self.cables_random_var.set(True)  # Enable random colors for cables by default


# Global instance
gui_state = GUIState()