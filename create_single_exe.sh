#!/bin/bash
# Create Single Executable using Conda + PyInstaller
# This script creates a conda environment and builds a single executable

echo "MDA Layers Downloader - Single Executable Builder"
echo "================================================="

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "ERROR: Conda is not installed!"
    echo "Please install Miniconda or Anaconda from:"
    echo "https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

echo "Creating conda environment with geospatial dependencies..."

# Create environment if it doesn't exist
if ! conda env list | grep -q "mda-single-exe"; then
    echo "Creating mda-single-exe environment..."
    conda env create -f environment.yml --name mda-single-exe
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create conda environment"
        exit 1
    fi
else
    echo "Environment already exists."
fi

echo "Activating environment and building executable..."

# Source conda activation script and activate environment
eval "$(conda shell.bash hook)"
conda activate mda-single-exe

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to activate conda environment"
    exit 1
fi

echo "Building single executable with PyInstaller..."

# Clean previous builds
rm -rf dist build

# Determine executable extension based on OS
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    ICON_FLAG="--icon=mda_layers_downloader.ico"
    EXE_NAME="MDA_Layers_SingleExe_v1.3.exe"
else
    ICON_FLAG=""  # No icon support on Linux/macOS
    EXE_NAME="MDA_Layers_SingleExe_v1.3"
fi

# Run PyInstaller to create single executable
pyinstaller --onefile --windowed $ICON_FLAG --name="$EXE_NAME" main.py

if [ $? -ne 0 ]; then
    echo "ERROR: PyInstaller failed"
    exit 1
fi

echo ""
echo "SUCCESS! Single executable created."
echo ""
echo "File location: dist/$EXE_NAME"
echo ""
echo "This is a standalone executable that can be distributed as a single file."
echo "Users can download and run it without installing anything."
echo ""

# Create a simple zip/tar of just the executable for easy distribution
if [[ -f "dist/$EXE_NAME" ]]; then
    echo "Creating distribution archive..."
    if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        # Windows - create zip
        powershell "Compress-Archive -Path 'dist/$EXE_NAME' -DestinationPath 'MDA_Layers_SingleExe_v1.3.zip' -Force"
        echo ""
        echo "Distribution zip created: MDA_Layers_SingleExe_v1.3.zip"
    else
        # Linux/macOS - create tar.gz
        tar -czf "MDA_Layers_SingleExe_v1.3.tar.gz" -C dist "$EXE_NAME"
        echo ""
        echo "Distribution tar.gz created: MDA_Layers_SingleExe_v1.3.tar.gz"
    fi
fi

echo ""
echo "Build complete! The executable is ready for distribution."