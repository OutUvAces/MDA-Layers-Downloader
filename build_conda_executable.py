#!/usr/bin/env python3
"""
Build script for creating MDA Layers Downloader executable using conda.

This script provides multiple approaches for creating distributable executables:
1. PyInstaller within conda environment
2. Conda-pack for portable environment
3. Constructor for full installer
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(cmd, cwd=None):
    """Run a command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    return True

def create_pyinstaller_exe():
    """Create executable using PyInstaller within conda environment."""
    print("=== Building PyInstaller Executable ===")

    # Clean previous builds
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    if os.path.exists("build"):
        shutil.rmtree("build")

    # Run PyInstaller
    cmd = [
        "pyinstaller",
        "--onedir",
        "--windowed",
        "--icon=mda_layers_downloader.ico",
        "--name=MDA_Layers_Downloader_v1.3_Conda",
        "main.py"
    ]

    if run_command(cmd):
        print("✅ PyInstaller executable created successfully")
        return True
    else:
        print("❌ PyInstaller build failed")
        return False

def create_portable_env():
    """Create portable environment using conda-pack."""
    print("=== Creating Portable Environment ===")

    # Pack the current conda environment
    cmd = ["conda-pack", "-o", "mda-layers-downloader-env.tar.gz"]

    if run_command(cmd):
        print("✅ Portable environment created: mda-layers-downloader-env.tar.gz")

        # Create a simple launcher script
        launcher_script = '''#!/bin/bash
# MDA Layers Downloader Launcher
# This script sets up the portable conda environment and runs the application

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Extract environment if not already extracted
if [ ! -d "$DIR/env" ]; then
    echo "Extracting portable environment..."
    mkdir -p "$DIR/env"
    tar -xzf "$DIR/mda-layers-downloader-env.tar.gz" -C "$DIR/env"
fi

# Activate environment and run application
export PATH="$DIR/env/bin:$PATH"
export PYTHONPATH="$DIR/env/lib/python3.10/site-packages:$PYTHONPATH"

# Run the application
cd "$DIR"
python main.py
'''
        with open("run_mda.sh", "w") as f:
            f.write(launcher_script)

        # Make executable
        os.chmod("run_mda.sh", 0o755)

        print("✅ Launcher script created: run_mda.sh")
        return True
    else:
        print("❌ Portable environment creation failed")
        return False

def create_installer():
    """Create installer using constructor (if available)."""
    print("=== Creating Installer ===")

    # Check if constructor is available
    try:
        import constructor
        print("Constructor is available")
    except ImportError:
        print("Constructor not available, skipping installer creation")
        return False

    # Constructor would require a construct.yaml file
    construct_yaml = '''
name: MDA Layers Downloader
version: 1.3
company: MDA Tools

channels:
  - conda-forge
  - defaults

specs:
  - python=3.10
  - geopandas
  - fiona
  - pyogrio
  - shapely
  - pyproj
  - gdal
  - pandas
  - numpy
  - xarray
  - netcdf4
  - requests
  - aiohttp
  - tk

# Post-install commands
post_install: python -c "import mda_layers_downloader; print('Installation complete!')"

# Welcome message
welcome_text: |
    Welcome to MDA Layers Downloader v1.3

    This application downloads and processes marine geospatial data layers.

# License
license_file: LICENSE  # If you have one
'''

    with open("construct.yaml", "w") as f:
        f.write(construct_yaml)

    cmd = ["constructor", "construct.yaml"]
    if run_command(cmd):
        print("✅ Installer created")
        return True
    else:
        print("❌ Installer creation failed")
        return False

def main():
    """Main build function."""
    print("MDA Layers Downloader - Conda Build Script")
    print("=" * 50)

    # Check if we're in a conda environment
    conda_env = os.environ.get("CONDA_DEFAULT_ENV")
    if not conda_env:
        print("❌ Not running in a conda environment!")
        print("Please activate the mda-layers-downloader environment first:")
        print("  conda env create -f environment.yml")
        print("  conda activate mda-layers-downloader")
        sys.exit(1)

    print(f"✅ Running in conda environment: {conda_env}")

    # Create PyInstaller executable
    if create_pyinstaller_exe():
        # Create portable version of the executable
        exe_dir = Path("dist/MDA_Layers_Downloader_v1.3_Conda")
        if exe_dir.exists():
            print(f"✅ Executable created in: {exe_dir}")

            # Create zip file
            zip_name = "MDA_Layers_Downloader_v1.3_Conda_Portable"
            shutil.make_archive(zip_name, 'zip', exe_dir)
            print(f"✅ Portable zip created: {zip_name}.zip")

    # Create portable environment
    create_portable_env()

    # Try to create installer
    create_installer()

    print("\n" + "=" * 50)
    print("Build process complete!")
    print("\nAvailable outputs:")
    if Path("dist/MDA_Layers_Downloader_v1.3_Conda").exists():
        print("  - PyInstaller executable: dist/MDA_Layers_Downloader_v1.3_Conda/")
    if Path("mda-layers-downloader-env.tar.gz").exists():
        print("  - Portable environment: mda-layers-downloader-env.tar.gz + run_mda.sh")
    if Path("MDA_Layers_Downloader_v1.3_Conda_Portable.zip").exists():
        print("  - Portable zip: MDA_Layers_Downloader_v1.3_Conda_Portable.zip")

if __name__ == "__main__":
    main()