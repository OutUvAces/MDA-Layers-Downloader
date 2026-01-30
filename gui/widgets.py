"""
GUI widget utilities and helper functions.

This module provides reusable GUI components and utility functions
for the application's user interface.
"""

import tkinter as tk
from tkinter import ttk, colorchooser
import webbrowser
from core.config import OPACITY_OPTIONS

def update_color_preview(label: tk.Label, hex_var):
    label.config(bg=hex_var.get())

def pick_color_and_update(color_var, preview_label):
    color = colorchooser.askcolor(title="Choose layer color", initialcolor=color_var.get())
    if color[1]:
        color_var.set(color[1])
        update_color_preview(preview_label, color_var)

def create_color_opacity_row(text, var, color_var, opacity_var, source_text=None, source_url=None, density_var=None, density_options=None):
    widgets = {}

    widgets['left_subframe'] = tk.Frame()
    widgets['left_subframe'].columnconfigure(0, weight=0)
    widgets['left_subframe'].columnconfigure(1, weight=0)

    widgets['checkbox'] = tk.Checkbutton(widgets['left_subframe'], text=text, variable=var, anchor="w")
    widgets['checkbox'].grid(row=0, column=0, sticky="w")

    if source_text and source_url:
        # No dash at all, just " Source: SourceName" (single space before "Source")
        source_text_full = " " + source_text
        widgets['source_label'] = tk.Label(widgets['left_subframe'], text=source_text_full, fg="blue", cursor="hand2", font=("Helvetica", 11), anchor="w")
        widgets['source_label'].grid(row=0, column=1, sticky="w", padx=(0, 0))
        widgets['source_label'].bind("<Button-1>", lambda e: webbrowser.open(source_url))

    widgets['color_subframe'] = tk.Frame()
    widgets['preview'] = tk.Label(widgets['color_subframe'], width=3, height=1, relief="solid", bd=1, bg=color_var.get())
    widgets['preview'].pack(side="left", padx=5)
    widgets['pick_button'] = tk.Button(widgets['color_subframe'], text="Pick", width=5, font=("Helvetica", 9),
                                       command=lambda: pick_color_and_update(color_var, widgets['preview']))
    widgets['pick_button'].pack(side="left")

    widgets['opacity_subframe'] = tk.Frame()
    widgets['opacity_label'] = tk.Label(widgets['opacity_subframe'], text="Opacity:", anchor="e")
    widgets['opacity_label'].pack(side="left", padx=5)
    widgets['opacity_combo'] = ttk.Combobox(widgets['opacity_subframe'], textvariable=opacity_var, values=OPACITY_OPTIONS, 
                                            width=3, state="readonly")
    widgets['opacity_combo'].pack(side="left")

    if density_var and density_options:
        widgets['density_subframe'] = tk.Frame()
        widgets['density_label'] = tk.Label(widgets['density_subframe'], text="Density", anchor="e")
        widgets['density_label'].pack(side="left", padx=2)
        widgets['density_combo'] = ttk.Combobox(widgets['density_subframe'], textvariable=density_var, values=density_options,
                                                width=4, state="readonly")
        widgets['density_combo'].pack(side="left")

    return widgets

def create_navwarnings_row(var, color_var, opacity_var, custom_var, source_text, source_url):
    """Create navigation warnings row with custom colors checkbox"""
    widgets = {}

    widgets['left_subframe'] = tk.Frame()
    widgets['left_subframe'].columnconfigure(0, weight=0)
    widgets['left_subframe'].columnconfigure(1, weight=0)

    widgets['checkbox'] = tk.Checkbutton(widgets['left_subframe'], text="Maritime Navigation Warnings", variable=var, anchor="w")
    widgets['checkbox'].grid(row=0, column=0, sticky="w")

    if source_text and source_url:
        source_text_full = " " + source_text
        widgets['source_label'] = tk.Label(widgets['left_subframe'], text=source_text_full, fg="blue", cursor="hand2", font=("Helvetica", 11), anchor="w")
        widgets['source_label'].grid(row=0, column=1, sticky="w", padx=(0, 0))
        widgets['source_label'].bind("<Button-1>", lambda e: webbrowser.open(source_url))

    # Custom colors checkbox (returned separately for main grid placement)
    widgets['custom_check'] = tk.Checkbutton(text="Use custom colors and icons (recommended)",
                                             variable=custom_var, font=("Helvetica", 9), anchor="w")

    widgets['color_subframe'] = tk.Frame()
    widgets['preview'] = tk.Label(widgets['color_subframe'], width=3, height=1, relief="solid", bd=1, bg=color_var.get())
    widgets['preview'].pack(side="left", padx=5)
    widgets['pick_button'] = tk.Button(widgets['color_subframe'], text="Pick", width=5, font=("Helvetica", 9),
                                       command=lambda: pick_color_and_update(color_var, widgets['preview']))
    widgets['pick_button'].pack(side="left")

    widgets['opacity_subframe'] = tk.Frame()
    widgets['opacity_label'] = tk.Label(widgets['opacity_subframe'], text="Opacity:", anchor="e")
    widgets['opacity_label'].pack(side="left", padx=5)
    widgets['opacity_combo'] = ttk.Combobox(widgets['opacity_subframe'], textvariable=opacity_var, values=OPACITY_OPTIONS,
                                            width=3, state="readonly")
    widgets['opacity_combo'].pack(side="left")

    def update_controls_state(*args):
        """Update color picker based on custom checkbox state (opacity always enabled)"""
        if custom_var.get():  # Custom colors enabled
            widgets['pick_button'].config(state="disabled")
            widgets['preview'].config(relief="flat", bg="#e0e0e0")
        else:  # Manual color override enabled
            widgets['pick_button'].config(state="normal")
            widgets['preview'].config(relief="solid", bd=1, bg=color_var.get())

        # Opacity is always enabled regardless of custom checkbox state
        widgets['opacity_combo'].config(state="readonly")

    custom_var.trace_add("write", update_controls_state)
    update_controls_state()  # Initial state

    return widgets

def create_cables_row(var, color_var, opacity_var, random_var):
    widgets = {}

    widgets['left_subframe'] = tk.Frame()
    widgets['left_subframe'].columnconfigure(0, weight=0)
    widgets['left_subframe'].columnconfigure(1, weight=0)

    widgets['checkbox'] = tk.Checkbutton(widgets['left_subframe'], text="Submarine Cables", variable=var, anchor="w")
    widgets['checkbox'].grid(row=0, column=0, sticky="w")

    source_text_full = " TeleGeography"  # No dash, single space before source
    widgets['source_label'] = tk.Label(widgets['left_subframe'], text=source_text_full, fg="blue", cursor="hand2", font=("Helvetica", 11), anchor="w")
    widgets['source_label'].grid(row=0, column=1, sticky="w", padx=(0, 0))
    widgets['source_label'].bind("<Button-1>", lambda e: webbrowser.open("https://www.submarinecablemap.com/"))

    widgets['random_check'] = tk.Checkbutton(text="Varied colors per cable (recommended)", variable=random_var, font=("Helvetica", 9), anchor="w")

    widgets['color_subframe'] = tk.Frame()
    widgets['preview'] = tk.Label(widgets['color_subframe'], width=3, height=1, relief="solid", bd=1, bg=color_var.get())
    widgets['preview'].pack(side="left", padx=5)
    widgets['pick_button'] = tk.Button(widgets['color_subframe'], text="Pick", width=5, font=("Helvetica", 9),
                                       command=lambda: pick_color_and_update(color_var, widgets['preview']))
    widgets['pick_button'].pack(side="left")

    widgets['opacity_subframe'] = tk.Frame()
    widgets['opacity_label'] = tk.Label(widgets['opacity_subframe'], text="Opacity:", anchor="e")
    widgets['opacity_label'].pack(side="left", padx=5)
    widgets['opacity_combo'] = ttk.Combobox(widgets['opacity_subframe'], textvariable=opacity_var, values=OPACITY_OPTIONS, 
                                            width=3, state="readonly")
    widgets['opacity_combo'].pack(side="left")

    def update_pick_state(*args):
        if random_var.get():
            widgets['pick_button'].config(state="disabled")
            widgets['preview'].config(relief="flat", bg="#e0e0e0")
        else:
            widgets['pick_button'].config(state="normal")
            widgets['preview'].config(relief="solid", bd=1, bg=color_var.get())

    random_var.trace_add("write", update_pick_state)
    update_pick_state()
    return widgets