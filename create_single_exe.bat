@echo off
REM Create Single Executable using Conda + PyInstaller
REM This script creates a conda environment and builds a single executable

echo MDA Layers Downloader - Single Executable Builder
echo ==================================================

REM Check if conda is available
conda --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Conda is not installed!
    echo Please install Miniconda or Anaconda from:
    echo https://docs.conda.io/en/latest/miniconda.html
    pause
    exit /b 1
)

echo Creating conda environment with geospatial dependencies...

REM Create environment if it doesn't exist
conda env list | findstr "mda-single-exe" >nul 2>&1
if errorlevel 1 (
    echo Creating mda-single-exe environment...
    conda env create -f environment.yml --name mda-single-exe
    if errorlevel 1 (
        echo ERROR: Failed to create conda environment
        pause
        exit /b 1
    )
) else (
    echo Environment already exists.
)

echo Activating environment and building executable...

REM Activate environment and run PyInstaller
REM Using call to ensure the script continues after conda activate
call conda activate mda-single-exe

if errorlevel 1 (
    echo ERROR: Failed to activate conda environment
    pause
    exit /b 1
)

echo Building single executable with PyInstaller...

REM Clean previous builds
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM Run PyInstaller to create single executable
pyinstaller --onefile --windowed --icon=mda_layers_downloader.ico --name=MDA_Layers_SingleExe_v1.3 main.py

if errorlevel 1 (
    echo ERROR: PyInstaller failed
    pause
    exit /b 1
)

echo.
echo SUCCESS! Single executable created.
echo.
echo File location: dist\MDA_Layers_SingleExe_v1.3.exe
echo.
echo This is a standalone executable that can be distributed as a single file.
echo Users can download and run it without installing anything.
echo.

REM Create a simple zip of just the executable for easy distribution
if exist "dist\MDA_Layers_SingleExe_v1.3.exe" (
    echo Creating distribution zip...
    powershell "Compress-Archive -Path 'dist\MDA_Layers_SingleExe_v1.3.exe' -DestinationPath 'MDA_Layers_SingleExe_v1.3.zip' -Force"
    echo.
    echo Distribution zip created: MDA_Layers_SingleExe_v1.3.zip
)

echo.
echo Build complete! The executable is ready for distribution.
pause