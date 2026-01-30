@echo off
REM MDA Layers Downloader - Setup and Run Script
REM This script sets up the conda environment and runs the application

echo MDA Layers Downloader Setup
echo =============================

REM Check if conda is available
conda --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Conda is not installed or not in PATH
    echo Please install Miniconda or Anaconda from:
    echo https://docs.conda.io/en/latest/miniconda.html
    pause
    exit /b 1
)

echo Conda found. Setting up environment...

REM Create environment if it doesn't exist
conda env list | findstr "mda-layers-downloader" >nul 2>&1
if errorlevel 1 (
    echo Creating conda environment...
    conda env create -f environment.yml
    if errorlevel 1 (
        echo ERROR: Failed to create conda environment
        pause
        exit /b 1
    )
) else (
    echo Environment already exists.
)

REM Activate environment and run
echo Activating environment and starting application...
conda activate mda-layers-downloader && python main.py

pause