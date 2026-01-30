"""
MDA Layers Downloader - Main Entry Point

This application downloads and processes marine geospatial data layers
including territorial waters, exclusive economic zones, marine protected areas,
submarine cables, ocean currents, and navigation warnings.

The application provides both a GUI interface and supports batch processing
of marine data for visualization in tools like Google Earth.
"""

import multiprocessing
from gui.main_window import create_gui

if __name__ == "__main__":
    multiprocessing.freeze_support()
    create_gui()