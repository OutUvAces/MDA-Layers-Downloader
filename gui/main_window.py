"""
Main GUI window for the MDA Layers Downloader application.

This module provides the primary user interface for configuring and running
marine data layer downloads, including layer selection, color customization,
and progress monitoring.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, colorchooser
import webbrowser
import threading
from queue import Queue
from pathlib import Path
import os
import shutil
from datetime import date, timedelta
import configparser
from functools import partial

from core.config import (
    OUTPUT_SUBFOLDER, CONFIG_SUBFOLDER, DEFAULT_COLORS, DEFAULT_OPACITIES,
    DENSITY_OPTIONS, DENSITY_MAPPING, OPACITY_OPTIONS,
    MARINEREGIONS_SOURCE_URL, PROTECTED_PLANET_SOURCE_URL, OSCAR_SOURCE_URL, NGA_MSI_SOURCE_URL
)
from core.types import LayerSettings
from core.utils import hex_to_kml_abgr
from gui.widgets import create_color_opacity_row, create_cables_row, create_navwarnings_row
from gui.gui_state import gui_state
from gui.controls import load_countries, toggle_country_layers, toggle_global_layers
from workers.download_worker import worker_async as worker

# Global widgets (kept only for GUI updates – worker uses queue)
log_text = None
start_button = None
country_combo = None
progress_bar = None
status_label = None
root = None

# All tkinter variables (created in create_gui)
territorial_var = None
contiguous_var = None
mpa_var = None
eez_var = None
ecs_var = None
cables_var = None
seastate_country_var = None
seastate_global_var = None
navwarnings_var = None

territorial_color_var = None
contiguous_color_var = None
mpa_color_var = None
eez_color_var = None
ecs_color_var = None
cables_color_var = None
seastate_color_var = None
navwarnings_color_var = None

territorial_opacity = None
contiguous_opacity = None
mpa_opacity = None
eez_opacity = None
ecs_opacity = None
cables_opacity = None
seastate_opacity = None
navwarnings_opacity = None

cables_random_var = None
# navwarnings_custom_var is now in gui_state
seastate_density_country = None
seastate_density_global = None

def log(message):
    """Add a message to the GUI log display.

    Args:
        message: Text message to display in the log
    """
    global log_text
    if log_text:
        log_text.config(state="normal")
        log_text.insert(tk.END, message + "\n")
        log_text.see(tk.END)
        log_text.config(state="disabled")

def center_dialog_on_screen(dialog, width, height):
    """Center a dialog window on the screen"""
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()

    x = (screen_width - width) // 2
    y = (screen_height - height) // 2

    dialog.geometry(f"{width}x{height}+{x}+{y}")

def show_wdpa_warning_once(output_dir: str) -> bool:
    # Use config directory in the output folder for user preferences
    config_dir = Path(output_dir) / CONFIG_SUBFOLDER
    config_dir.mkdir(parents=True, exist_ok=True)
    flag_file = config_dir / "wdpa_warning_dismissed"
    if flag_file.exists():
        return True

    dialog = tk.Toplevel(root)
    dialog.title("Large File Download – WDPA Marine Shapefile (~1 GB)")
    dialog.resizable(False, False)
    dialog.transient(root)
    dialog.grab_set()
    dialog.focus_force()

    # Center the dialog on screen
    center_dialog_on_screen(dialog, 560, 460)

    # Center-align the warning icon
    tk.Label(dialog, text="⚠", font=("Helvetica", 60), fg="#e67e22").pack(pady=(30, 10))

    # Center the main text block with better padding
    text_frame = tk.Frame(dialog)
    text_frame.pack(pady=(0, 10), padx=20)
    tk.Label(
        text_frame,
        text=(
            "The Marine Protected Areas layer requires downloading\n"
            "a large global shapefile (~1 GB compressed).\n\n"
            "• Download may take several minutes (or much longer on slow connections)\n"
            "• The file is saved in the _cache folder inside your output folder and will be reused automatically\n"
            "  in future runs — keep it there to avoid re-downloading every time!\n\n"
            "You can delete it later if you need space, but it will require re-downloading."
        ),
        justify="left",
        font=("Helvetica", 11),
        anchor="w",
        wraplength=480
    ).pack()

    dont_show_var = tk.BooleanVar(value=False)
    # Center the checkbox
    checkbox_frame = tk.Frame(dialog)
    checkbox_frame.pack(pady=(25, 30))
    tk.Checkbutton(
        checkbox_frame,
        text="Do not show this message again",
        variable=dont_show_var,
        font=("Helvetica", 11)
    ).pack()

    btn_frame = tk.Frame(dialog)
    btn_frame.pack(side="bottom", fill="x", pady=(0, 35), padx=60)

    result = [False]

    def proceed():
        result[0] = True
        if dont_show_var.get():
            try:
                flag_file.touch(exist_ok=True)
            except Exception as e:
                log(f"Could not save preference: {e}")
        dialog.destroy()

    def cancel():
        result[0] = False
        dialog.destroy()

    tk.Button(btn_frame, text="Cancel", width=15, height=2, font=("Helvetica", 11), command=cancel).pack(side="left", padx=40)
    tk.Button(btn_frame, text="Continue", width=15, height=2, font=("Helvetica", 11, "bold"),
              bg="#27ae60", fg="white", command=proceed).pack(side="right", padx=40)

    dialog.protocol("WM_DELETE_WINDOW", cancel)
    dialog.wait_window()
    return result[0]

def prompt_earthdata_credentials():
    msg = ("For the latest near real-time ocean currents (OSCAR V2.0 NRT), a free NASA Earthdata account is required.\n\n"
           "Register at https://urs.earthdata.nasa.gov (quick & free)\n\n"
           "Enter your credentials below (saved securely on your computer).")
    if not messagebox.askokcancel("Earthdata Login Required", msg):
        return None, None

    cred_dialog = tk.Toplevel(root)
    cred_dialog.title("Enter Earthdata Credentials")
    cred_dialog.transient(root)
    cred_dialog.grab_set()
    cred_dialog.resizable(False, False)

    # Center the dialog on screen
    center_dialog_on_screen(cred_dialog, 400, 260)

    tk.Label(cred_dialog, text="Username/Email:", anchor="w").pack(fill="x", padx=20, pady=(20,5))
    username_entry = tk.Entry(cred_dialog, width=50)
    username_entry.pack(padx=20, pady=5)
    username_entry.focus_set()

    tk.Label(cred_dialog, text="Password:", anchor="w").pack(fill="x", padx=20, pady=(10,5))
    password_entry = tk.Entry(cred_dialog, show="*", width=50)
    password_entry.pack(padx=20, pady=5)

    # Add clickable URL link
    url_label = tk.Label(cred_dialog, text="Register at https://urs.earthdata.nasa.gov",
                        fg="blue", cursor="hand2", font=("Helvetica", 10, "underline"))
    url_label.pack(pady=(10, 0))
    url_label.bind("<Button-1>", lambda e: webbrowser.open("https://urs.earthdata.nasa.gov"))

    result = {"username": None, "password": None}

    def ok():
        result["username"] = username_entry.get().strip()
        result["password"] = password_entry.get()
        cred_dialog.destroy()

    def cancel():
        result["username"] = None
        result["password"] = None
        cred_dialog.destroy()

    btn_frame = tk.Frame(cred_dialog)
    btn_frame.pack(pady=20)
    tk.Button(btn_frame, text="OK", command=ok, width=15).pack(side="left", padx=10)
    tk.Button(btn_frame, text="Cancel", command=cancel, width=15).pack(side="right", padx=10)

    cred_dialog.protocol("WM_DELETE_WINDOW", cancel)
    cred_dialog.wait_window()

    if not result["username"] or not result["password"]:
        return None, None

    log("Earthdata credentials received for this session.")
    return result["username"], result["password"]

def get_saved_earthdata_credentials(base_output_dir: Path) -> tuple[str | None, str | None]:
    config_dir = base_output_dir / "_config"
    config_dir.mkdir(exist_ok=True)
    
    cred_file = config_dir / "earthdata_credentials.txt"
    
    if not cred_file.exists():
        return None, None
    
    try:
        config = configparser.ConfigParser()
        config.read(cred_file)
        username = config.get("Earthdata", "username", fallback=None)
        password = config.get("Earthdata", "password", fallback=None)
        if username and password:
            log("Using saved Earthdata credentials from config file.")
            return username.strip(), password
    except Exception as e:
        log(f"Error reading saved credentials: {e}")
    
    return None, None

def save_earthdata_credentials(base_output_dir: Path, username: str, password: str):
    config_dir = base_output_dir / "_config"
    config_dir.mkdir(exist_ok=True)
    
    cred_file = config_dir / "earthdata_credentials.txt"
    
    config = configparser.ConfigParser()
    config["Earthdata"] = {
        "username": username.strip(),
        "password": password
    }
    
    try:
        with open(cred_file, "w", encoding="utf-8") as f:
            config.write(f)
        log(f"Saved Earthdata credentials to: {cred_file}")
    except Exception as e:
        log(f"Failed to save credentials: {e}")

def start_download():
    global start_button, status_label, progress_bar, log_text, root
    if start_button:
        start_button.config(state="disabled")
    if status_label:
        status_label.config(text="Processing...")
    if progress_bar:
        progress_bar['value'] = 0
        progress_bar['mode'] = 'determinate'

    log("Starting download...")

    selected = country_combo.get()
    if selected:
        country_name = selected.split(' (')[0]
        iso_code = selected.split(' (')[1].strip(')')
    else:
        country_name = None
        iso_code = None

    # Check if country-specific layers selected but no country
    country_layers_selected = (
        territorial_var.get() or contiguous_var.get() or mpa_var.get() or
        eez_var.get() or ecs_var.get() or seastate_country_var.get()
    )
    if country_layers_selected and not selected:
        messagebox.showerror("Selection Required", "Please select a country for the selected country-specific layers.")
        start_button.config(state="normal")
        status_label.config(text="")
        return

    log(f"Processing for {country_name} ({iso_code})" if selected else "Processing global layers only")

    # ────────────────────────────────────────────────
    # Output to Documents with organization by type
    # ────────────────────────────────────────────────
    documents_dir = Path.home() / "Documents"
    base_output_dir = documents_dir / OUTPUT_SUBFOLDER
    base_output_dir.mkdir(parents=True, exist_ok=True)

    # Country-specific folder: full country name (sanitized)
    if selected:
        country_folder_name = country_name.replace(" ", "_").replace("/", "-").replace(":", "-").replace(",", "").replace("'", "")
        country_output_dir = base_output_dir / country_folder_name
        country_output_dir.mkdir(exist_ok=True)
    else:
        country_output_dir = None  # No country folder if no country selected

    # Global folder
    global_output_dir = base_output_dir / "Global"
    global_output_dir.mkdir(exist_ok=True)

    # Cache folder for raw data
    cache_dir = base_output_dir / "_cache"
    cache_dir.mkdir(exist_ok=True)

    log(f"Output base folder: {base_output_dir}")
    log(f"→ Cache for raw data → {cache_dir}")
    if country_output_dir:
        log(f"→ Country-specific files → {country_output_dir}")
    log(f"→ Global files → {global_output_dir}")

    if mpa_var.get():
        if not show_wdpa_warning_once(str(base_output_dir)):
            log("Operation cancelled by user (large MPA file warning).")
            start_button.config(state="normal")
            status_label.config(text="")
            progress_bar['value'] = 0
            return

    seastate_selected = seastate_country_var.get() or seastate_global_var.get()
    username = password = None

    if seastate_selected:
        # Try to load saved credentials first
        username, password = get_saved_earthdata_credentials(base_output_dir)
        
        if not username or not password:
            # Prompt only if no valid saved credentials
            username, password = prompt_earthdata_credentials()
            if username and password:
                save_earthdata_credentials(base_output_dir, username, password)
            else:
                log("No Earthdata credentials provided — skipping ocean currents layers.")

    settings = LayerSettings(
        territorial=territorial_var.get(),
        contiguous=contiguous_var.get(),
        mpa=mpa_var.get(),
        eez=eez_var.get(),
        ecs=ecs_var.get(),
        cables=cables_var.get(),
        seastate_country=seastate_country_var.get(),
        seastate_global=seastate_global_var.get(),
        navwarnings=navwarnings_var.get(),
        territorial_color=territorial_color_var.get(),
        contiguous_color=contiguous_color_var.get(),
        mpa_color=mpa_color_var.get(),
        eez_color=eez_color_var.get(),
        ecs_color=ecs_color_var.get(),
        cables_color=cables_color_var.get(),
        seastate_color=seastate_color_var.get(),
        navwarnings_color=navwarnings_color_var.get(),
        territorial_opacity=territorial_opacity.get(),
        contiguous_opacity=contiguous_opacity.get(),
        mpa_opacity=mpa_opacity.get(),
        eez_opacity=eez_opacity.get(),
        ecs_opacity=ecs_opacity.get(),
        cables_opacity=cables_opacity.get(),
        seastate_opacity=seastate_opacity.get(),
        navwarnings_opacity=navwarnings_opacity.get(),
        navwarnings_custom=gui_state.navwarnings_custom_var.get(),
        cables_random=cables_random_var.get(),
        seastate_density_country=DENSITY_MAPPING.get(seastate_density_country.get(), 0.5),  # Default to high for country
        seastate_density_global=DENSITY_MAPPING.get(seastate_density_global.get(), 3.0)   # Default to low for global
    )

    progress_queue = Queue()

    def report_progress(delta: float, message: str = ""):
        if message:
            progress_queue.put(("log", message))
        if delta > 0:
            progress_queue.put(("progress", delta))

    def process_queue():
        updated = False
        while not progress_queue.empty():
            kind, value = progress_queue.get_nowait()
            if kind == "log":
                log(value)
            elif kind == "progress":
                if progress_bar:
                    current_value = progress_bar['value']
                    progress_bar['value'] = min(100, current_value + value)
                updated = True
        if updated:
            root.update_idletasks()
        root.after(150, process_queue)

    root.after(100, process_queue)

    def run_worker():
        try:
            import asyncio
            asyncio.run(worker(
                settings,
                username,
                password,
                str(country_output_dir) if country_output_dir else "",
                str(global_output_dir),
                str(cache_dir),
                iso_code,
                country_name,
                report_progress
            ))
        except Exception as e:
            log(f"Unexpected error: {e}")
        finally:
            root.after(0, _finish)

    threading.Thread(target=run_worker, daemon=True).start()

def _finish():
    global start_button, status_label
    if start_button:
        start_button.config(state="normal")
    if status_label:
        status_label.config(text="")
    # Open output folder
    documents_dir = Path.home() / "Documents"
    output_dir = documents_dir / OUTPUT_SUBFOLDER
    webbrowser.open(str(output_dir))

def create_gui():
    global start_button, log_text, country_combo, progress_bar, status_label, root
    global territorial_var, contiguous_var, mpa_var, eez_var, ecs_var, cables_var
    global seastate_country_var, seastate_global_var, navwarnings_var
    global territorial_color_var, contiguous_color_var, mpa_color_var, eez_color_var, ecs_color_var, cables_color_var, seastate_color_var, navwarnings_color_var
    global territorial_opacity, contiguous_opacity, mpa_opacity, eez_opacity, ecs_opacity, cables_opacity, seastate_opacity, navwarnings_opacity
    global cables_random_var, seastate_density_country, seastate_density_global

    root = tk.Tk()
    root.title("MDA Layers Downloader")
    root.state('zoomed')

    default_font = ("Helvetica", 11)
    root.option_add("*Font", default_font)

    # Initialize GUI state variables (after root window is created)
    gui_state.initialize_variables()

    territorial_color_var = tk.StringVar(value=DEFAULT_COLORS["territorial"])
    contiguous_color_var  = tk.StringVar(value=DEFAULT_COLORS["contiguous"])
    mpa_color_var         = tk.StringVar(value=DEFAULT_COLORS["mpa"])
    eez_color_var         = tk.StringVar(value=DEFAULT_COLORS["eez"])
    ecs_color_var         = tk.StringVar(value=DEFAULT_COLORS["ecs"])
    cables_color_var      = tk.StringVar(value=DEFAULT_COLORS["cables"])
    seastate_color_var    = tk.StringVar(value=DEFAULT_COLORS["seastate"])
    navwarnings_color_var = tk.StringVar(value=DEFAULT_COLORS["navwarnings"])

    territorial_opacity = tk.StringVar(value=DEFAULT_OPACITIES["territorial"])
    contiguous_opacity  = tk.StringVar(value=DEFAULT_OPACITIES["contiguous"])
    mpa_opacity         = tk.StringVar(value=DEFAULT_OPACITIES["mpa"])
    eez_opacity         = tk.StringVar(value=DEFAULT_OPACITIES["eez"])
    ecs_opacity         = tk.StringVar(value=DEFAULT_OPACITIES["ecs"])
    cables_opacity      = tk.StringVar(value=DEFAULT_OPACITIES["cables"])
    seastate_opacity    = tk.StringVar(value=DEFAULT_OPACITIES["seastate"])
    navwarnings_opacity = tk.StringVar(value=DEFAULT_OPACITIES["navwarnings"])

    territorial_var = tk.BooleanVar(value=False)
    contiguous_var  = tk.BooleanVar(value=False)
    eez_var         = tk.BooleanVar(value=False)
    ecs_var         = tk.BooleanVar(value=False)
    mpa_var         = tk.BooleanVar(value=False)
    cables_var      = tk.BooleanVar(value=False)
    seastate_country_var = tk.BooleanVar(value=False)
    seastate_global_var  = tk.BooleanVar(value=False)
    navwarnings_var = tk.BooleanVar(value=False)

    cables_random_var = tk.BooleanVar(value=True)
    seastate_density_country  = tk.StringVar(value=DENSITY_OPTIONS[2])  # high (0.5°)
    seastate_density_global   = tk.StringVar(value=DENSITY_OPTIONS[0])  # low (3.0°)

    vars_dict = {
        'territorial': territorial_var,
        'contiguous': contiguous_var,
        'eez': eez_var,
        'ecs': ecs_var,
        'mpa': mpa_var,
        'seastate_country': seastate_country_var,
        'cables': cables_var,
        'seastate_global': seastate_global_var,
        'navwarnings': navwarnings_var,
    }

    # Country header with title and select/deselect buttons
    country_header_frame = tk.Frame(root)
    country_header_frame.grid(row=0, column=0, columnspan=5, sticky="ew", padx=20, pady=(20, 5))
    tk.Label(country_header_frame, text="Country-specific layers", font=("Helvetica", 12, "bold")).pack(side="left")

    country_toggle_frame = tk.Frame(country_header_frame)
    country_toggle_frame.pack(side="left", padx=(30, 0))
    tk.Button(country_toggle_frame, text="Select All", width=10, padx=8, pady=0,
              font=("Helvetica", 9), command=partial(toggle_country_layers, True, vars_dict)).pack(side="left", padx=(0, 6))
    tk.Button(country_toggle_frame, text="Deselect All", width=10, padx=8, pady=0,
              font=("Helvetica", 9), command=partial(toggle_country_layers, False, vars_dict)).pack(side="left")

    root.columnconfigure(0, weight=0)  # Left subframe
    root.columnconfigure(1, weight=1)  # Spacer
    root.columnconfigure(2, minsize=150)  # Density/random
    root.columnconfigure(3, minsize=100)  # Color subframe
    root.columnconfigure(4, minsize=120)  # Opacity subframe
    root.rowconfigure(13, weight=1)  # Log frame should expand


    # Country selector row - contains label, select/deselect buttons, country picker, and reset button
    countries = load_countries()

    # Custom dropdown widget with full keyboard control
    class CustomCountrySelector(tk.Frame):
        def __init__(self, parent, countries_list, selection_callback=None, **kwargs):
            super().__init__(parent)
            self.countries = countries_list
            self.selected_index = -1
            self.dropdown_open = False
            self.dropdown_window = None
            self.selection_callback = selection_callback

            # Create the display entry (readonly appearance)
            self.display_entry = tk.Entry(self, width=45, state="readonly", **kwargs)
            self.display_entry.pack(side="left")

            # Create dropdown button (match entry height)
            self.dropdown_button = tk.Button(self, text="▼", width=3, height=1, pady=0, font=("TkDefaultFont", 8), command=self.toggle_dropdown)
            self.dropdown_button.pack(side="left")

            # Bind events
            self.display_entry.bind('<Button-1>', lambda e: self.toggle_dropdown())
            self.display_entry.bind('<KeyPress>', self.on_key_press)

        def toggle_dropdown(self):
            if self.dropdown_open:
                self.close_dropdown()
            else:
                self.open_dropdown()

        def open_dropdown(self):
            if not self.dropdown_open and not self.dropdown_window:
                # Create popup window for dropdown
                self.dropdown_window = tk.Toplevel(self)
                self.dropdown_window.overrideredirect(True)  # Remove window decorations
                self.dropdown_window.attributes("-topmost", True)  # Keep on top

                # Position the dropdown below the entry
                x = self.display_entry.winfo_rootx()
                y = self.display_entry.winfo_rooty() + self.display_entry.winfo_height()
                self.dropdown_window.geometry(f"+{x}+{y}")

                # Create listbox in the popup
                self.listbox = tk.Listbox(self.dropdown_window, height=10, width=45, selectmode="single")
                for country in self.countries:
                    self.listbox.insert("end", country)
                self.listbox.pack()

                # Bind listbox events
                self.listbox.bind('<ButtonRelease-1>', self.on_listbox_select)
                self.listbox.bind('<KeyPress>', self.on_listbox_key_press)
                self.listbox.bind('<FocusOut>', self.close_dropdown)

                # Set initial selection
                if self.selected_index >= 0:
                    self.listbox.selection_set(self.selected_index)
                    self.listbox.see(self.selected_index)

                self.dropdown_open = True
                self.listbox.focus_set()

                # Handle clicks outside the dropdown
                self.dropdown_window.bind('<FocusOut>', self.close_dropdown)

        def close_dropdown(self, event=None):
            if self.dropdown_open and self.dropdown_window:
                self.dropdown_window.destroy()
                self.dropdown_window = None
                self.dropdown_open = False
                self.display_entry.focus_set()

        def on_key_press(self, event):
            """Handle key presses when dropdown is closed"""
            if event.char.isalpha():
                self.jump_to_letter(event.char.lower())
                return "break"
            elif event.keysym == 'Down':
                self.open_dropdown()
                return "break"
            return None

        def on_listbox_key_press(self, event):
            """Handle key presses when dropdown is open"""
            if event.char.isalpha():
                self.jump_to_letter(event.char.lower())
                return "break"
            elif event.keysym in ('Return', 'space'):
                self.select_current()
                return "break"
            elif event.keysym == 'Escape':
                self.close_dropdown()
                return "break"
            return None

        def jump_to_letter(self, letter):
            """Jump to first country starting with the given letter"""
            for i, country in enumerate(self.countries):
                if country.lower().startswith(letter):
                    self.selected_index = i
                    if self.dropdown_open and self.dropdown_window:
                        self.listbox.selection_clear(0, 'end')
                        self.listbox.selection_set(i)
                        self.listbox.see(i)
                    else:
                        self.display_entry.config(state="normal")
                        self.display_entry.delete(0, 'end')
                        self.display_entry.insert(0, country)
                        self.display_entry.config(state="readonly")
                    if self.selection_callback:
                        self.selection_callback()
                    break

        def on_listbox_select(self, event):
            """Handle listbox selection"""
            selection = self.listbox.curselection()
            if selection:
                self.selected_index = selection[0]
                country = self.countries[self.selected_index]
                self.display_entry.config(state="normal")
                self.display_entry.delete(0, 'end')
                self.display_entry.insert(0, country)
                self.display_entry.config(state="readonly")
                self.close_dropdown()
                if self.selection_callback:
                    self.selection_callback()

        def select_current(self):
            """Select the currently highlighted item"""
            if self.dropdown_open and self.selected_index >= 0:
                self.on_listbox_select(None)

        def get(self):
            """Get the selected country in the same format as the original combobox"""
            if self.selected_index >= 0:
                country = self.countries[self.selected_index]
                return country
            return ""

    # Reset to defaults button
    def reset_to_defaults():
        """Reset all color, opacity, density, and random values to defaults"""
        from core.config import DEFAULT_COLORS, DEFAULT_OPACITIES, DENSITY_MAPPING

        # Reset layer colors and opacities
        territorial_color_var.set(DEFAULT_COLORS["territorial"])
        territorial_opacity.set(DEFAULT_OPACITIES["territorial"])
        contiguous_color_var.set(DEFAULT_COLORS["contiguous"])
        contiguous_opacity.set(DEFAULT_OPACITIES["contiguous"])
        eez_color_var.set(DEFAULT_COLORS["eez"])
        eez_opacity.set(DEFAULT_OPACITIES["eez"])
        ecs_color_var.set(DEFAULT_COLORS["ecs"])
        ecs_opacity.set(DEFAULT_OPACITIES["ecs"])
        mpa_color_var.set(DEFAULT_COLORS["mpa"])
        mpa_opacity.set(DEFAULT_OPACITIES["mpa"])
        cables_color_var.set(DEFAULT_COLORS["cables"])
        cables_opacity.set(DEFAULT_OPACITIES["cables"])

        # Reset ocean currents settings
        seastate_color_var.set(DEFAULT_COLORS["seastate"])
        seastate_opacity.set(DEFAULT_OPACITIES["seastate"])
        seastate_density_country.set("high")  # High density for country-specific (more detail)
        seastate_density_global.set("low")    # Low density for global (performance)

        # Reset navigation warnings settings
        navwarnings_color_var.set(DEFAULT_COLORS["navwarnings"])
        navwarnings_opacity.set(DEFAULT_OPACITIES["navwarnings"])
        gui_state.navwarnings_custom_var.set(True)  # Reset to custom colors/icons by default

        # Reset cables random toggle to True (default)
        cables_random_var.set(True)  # Enable random colors for cables by default

    # Country selector row - country picker only
    country_selector_row = tk.Frame(root)
    country_selector_row.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))
    
    # Country picker (far left)
    country_combo = CustomCountrySelector(country_selector_row, countries)
    country_combo.pack(side="left")
    # No default selection

    # Reset button positioned in columns 3-4 to align with color/opacity columns
    reset_button = tk.Button(root, text="Reset to Defaults", width=15, padx=8, pady=0,
                            font=("Helvetica", 9), command=reset_to_defaults)
    reset_button.grid(row=1, column=3, columnspan=2, sticky="e", padx=(0, 20))


    # Layer rows
    territorial_widgets = create_color_opacity_row("Territorial waters (12nm)", territorial_var, territorial_color_var, territorial_opacity,
                                                   "Marine Regions", MARINEREGIONS_SOURCE_URL)
    territorial_widgets['left_subframe'].grid(row=2, column=0, sticky="w", pady=1, padx=20)
    territorial_widgets['color_subframe'].grid(row=2, column=3, sticky="e", pady=1)
    territorial_widgets['opacity_subframe'].grid(row=2, column=4, sticky="e", pady=1, padx=(0, 20))

    contiguous_widgets = create_color_opacity_row("Contiguous zone (24nm)", contiguous_var, contiguous_color_var, contiguous_opacity,
                                                  "Marine Regions", MARINEREGIONS_SOURCE_URL)
    contiguous_widgets['left_subframe'].grid(row=3, column=0, sticky="w", pady=1, padx=20)
    contiguous_widgets['color_subframe'].grid(row=3, column=3, sticky="e", pady=1)
    contiguous_widgets['opacity_subframe'].grid(row=3, column=4, sticky="e", pady=1, padx=(0, 20))

    eez_widgets = create_color_opacity_row("Exclusive Economic Zone (200 nm)", eez_var, eez_color_var, eez_opacity,
                                           "Marine Regions", MARINEREGIONS_SOURCE_URL)
    eez_widgets['left_subframe'].grid(row=4, column=0, sticky="w", pady=1, padx=20)
    eez_widgets['color_subframe'].grid(row=4, column=3, sticky="e", pady=1)
    eez_widgets['opacity_subframe'].grid(row=4, column=4, sticky="e", pady=1, padx=(0, 20))

    ecs_widgets = create_color_opacity_row("Extended Continental Shelf", ecs_var, ecs_color_var, ecs_opacity,
                                           "Marine Regions", MARINEREGIONS_SOURCE_URL)
    ecs_widgets['left_subframe'].grid(row=5, column=0, sticky="w", pady=1, padx=20)
    ecs_widgets['color_subframe'].grid(row=5, column=3, sticky="e", pady=1)
    ecs_widgets['opacity_subframe'].grid(row=5, column=4, sticky="e", pady=1, padx=(0, 20))

    mpa_widgets = create_color_opacity_row("Marine Protected Areas", mpa_var, mpa_color_var, mpa_opacity,
                                           "Protected Planet", PROTECTED_PLANET_SOURCE_URL)
    mpa_widgets['left_subframe'].grid(row=6, column=0, sticky="w", pady=1, padx=20)
    mpa_widgets['color_subframe'].grid(row=6, column=3, sticky="e", pady=1)
    mpa_widgets['opacity_subframe'].grid(row=6, column=4, sticky="e", pady=1, padx=(0, 20))

    # Seastate country
    seastate_country_widgets = create_color_opacity_row("Ocean Currents (clipped to EEZ)", seastate_country_var, seastate_color_var, seastate_opacity,
                                                        "NASA", OSCAR_SOURCE_URL, seastate_density_country, DENSITY_OPTIONS)
    seastate_country_widgets['left_subframe'].grid(row=7, column=0, sticky="w", pady=1, padx=20)
    seastate_country_widgets['density_subframe'].grid(row=7, column=2, sticky="e", pady=1)
    seastate_country_widgets['color_subframe'].grid(row=7, column=3, sticky="e", pady=1)
    seastate_country_widgets['opacity_subframe'].grid(row=7, column=4, sticky="e", pady=1, padx=(0, 20))

    # Global header
    global_header_frame = tk.Frame(root)
    global_header_frame.grid(row=8, column=0, columnspan=5, sticky="ew", padx=20, pady=(20, 5))
    tk.Label(global_header_frame, text="Global data layers", font=("Helvetica", 12, "bold")).pack(side="left")

    global_toggle_frame = tk.Frame(global_header_frame)
    global_toggle_frame.pack(side="left", padx=(30, 0))
    tk.Button(global_toggle_frame, text="Select All", width=10, padx=8, pady=0,
              font=("Helvetica", 9), command=partial(toggle_global_layers, True, vars_dict)).pack(side="left", padx=(0, 6))
    tk.Button(global_toggle_frame, text="Deselect All", width=10, padx=8, pady=0,
              font=("Helvetica", 9), command=partial(toggle_global_layers, False, vars_dict)).pack(side="left")

    # Cables special row
    cables_widgets = create_cables_row(cables_var, cables_color_var, cables_opacity, cables_random_var)
    cables_widgets['left_subframe'].grid(row=9, column=0, sticky="w", pady=1, padx=20)
    cables_widgets['random_check'].grid(row=9, column=2, sticky="w", pady=1)
    cables_widgets['color_subframe'].grid(row=9, column=3, sticky="e", pady=1)
    cables_widgets['opacity_subframe'].grid(row=9, column=4, sticky="e", pady=1, padx=(0, 20))

    # Seastate global
    seastate_global_widgets = create_color_opacity_row("Ocean Currents (global)", seastate_global_var, seastate_color_var, seastate_opacity,
                                                       "NASA", OSCAR_SOURCE_URL, seastate_density_global, DENSITY_OPTIONS)
    seastate_global_widgets['left_subframe'].grid(row=10, column=0, sticky="w", pady=1, padx=20)
    seastate_global_widgets['density_subframe'].grid(row=10, column=2, sticky="e", pady=1)
    seastate_global_widgets['color_subframe'].grid(row=10, column=3, sticky="e", pady=1)
    seastate_global_widgets['opacity_subframe'].grid(row=10, column=4, sticky="e", pady=1, padx=(0, 20))

    # Navigation warnings
    navwarnings_widgets = create_navwarnings_row(navwarnings_var, navwarnings_color_var, navwarnings_opacity, gui_state.navwarnings_custom_var,
                                                  "NGA", NGA_MSI_SOURCE_URL)
    navwarnings_widgets['left_subframe'].grid(row=11, column=0, sticky="w", pady=1, padx=20)
    navwarnings_widgets['custom_check'].grid(row=11, column=2, sticky="w", pady=1)
    navwarnings_widgets['color_subframe'].grid(row=11, column=3, sticky="e", pady=1)
    navwarnings_widgets['opacity_subframe'].grid(row=11, column=4, sticky="e", pady=1, padx=(0, 20))

    # Button + progress
    button_progress_frame = tk.Frame(root)
    button_progress_frame.grid(row=12, column=0, columnspan=5, sticky="ew", padx=20, pady=(6, 6))
    button_progress_frame.columnconfigure(1, weight=1)

    start_button = tk.Button(button_progress_frame, text="Start Download", command=start_download,
                             padx=10, pady=0, font=("Helvetica", 9))
    start_button.grid(row=0, column=0, sticky="w", padx=(0,12), pady=0)
    start_button.config(state="disabled")  # Start disabled if no layers selected

    progress_bar = ttk.Progressbar(button_progress_frame, orient="horizontal", mode="determinate")
    progress_bar.grid(row=0, column=1, sticky="ew", pady=0)

    status_label = tk.Label(button_progress_frame, text="", fg="blue", font=("Helvetica", 9, "italic"))
    status_label.grid(row=0, column=2, padx=10, pady=0, sticky="w")

    # Log
    log_frame = tk.Frame(root)
    log_frame.grid(row=13, column=0, columnspan=5, sticky="nsew", padx=20, pady=(0,5))
    log_frame.columnconfigure(0, weight=1)
    log_frame.rowconfigure(0, weight=1)

    global log_text
    log_text = tk.Text(log_frame, height=18, width=90, state="normal", wrap="word")
    log_text.grid(row=0, column=0, sticky="nsew")

    scrollbar = tk.Scrollbar(log_frame, command=log_text.yview)
    scrollbar.grid(row=0, column=1, sticky="ns")
    log_text.config(yscrollcommand=scrollbar.set)

    log_text.insert(tk.END, "Select country/layers, adjust colors/opacity/density if needed, then click Start Download.\n\n")
    log_text.insert(tk.END, "Ocean Currents: NOAA OSCAR V2.0 NRT — latest near real-time data (~2-day delay).\n")
    log_text.insert(tk.END, "Requires one-time free NASA Earthdata login (prompted if needed).\n\n")
    log_text.insert(tk.END, "All files are output in .KML format.\n\n")
    log_text.config(state="disabled")

    # Function to enable/disable start button based on layer selections
    def update_start_button():
        # Check if any layers are selected
        any_layers_selected = (
            territorial_var.get() or contiguous_var.get() or mpa_var.get() or
            eez_var.get() or ecs_var.get() or cables_var.get() or
            seastate_country_var.get() or seastate_global_var.get() or
            navwarnings_var.get()
        )

        if any_layers_selected:
            # Check if country-specific layers are selected but no country chosen
            country_layers_selected = (
                territorial_var.get() or contiguous_var.get() or mpa_var.get() or
                eez_var.get() or ecs_var.get() or seastate_country_var.get()
            )
            country_selected = bool(country_combo.get().strip())

            if country_layers_selected and not country_selected:
                start_button.config(state="disabled")
            else:
                start_button.config(state="normal")
        else:
            start_button.config(state="disabled")

    # Set the callback for country selection changes
    country_combo.selection_callback = update_start_button

    # Trace all layer checkboxes to update button
    territorial_var.trace_add("write", lambda *args: update_start_button())
    contiguous_var.trace_add("write", lambda *args: update_start_button())
    mpa_var.trace_add("write", lambda *args: update_start_button())
    eez_var.trace_add("write", lambda *args: update_start_button())
    ecs_var.trace_add("write", lambda *args: update_start_button())
    cables_var.trace_add("write", lambda *args: update_start_button())
    seastate_country_var.trace_add("write", lambda *args: update_start_button())
    seastate_global_var.trace_add("write", lambda *args: update_start_button())
    navwarnings_var.trace_add("write", lambda *args: update_start_button())

    def on_closing():
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    footer_frame = tk.Frame(root)
    footer_frame.grid(row=14, column=0, columnspan=5, sticky="ew", padx=20, pady=(5, 5))
    footer_text = "Version 1.2 • January 2026 • Created by Chip"
    tk.Label(footer_frame, text=footer_text, font=("Helvetica", 9), fg="#666666", justify="center").pack(fill="x")

    root.mainloop()