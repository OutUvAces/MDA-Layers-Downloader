# Installation Guide

This guide provides multiple ways to install and run the MDA Layers Downloader.

## 🚀 Quick Start (Recommended)

### Option 1: Anaconda/Miniconda (Most Reliable)
Anaconda provides pre-compiled geospatial packages and is the most reliable way to install this application. Geospatial libraries like GDAL, Fiona, and GeoPandas have complex C/C++ dependencies that are often difficult to install with pip but are pre-compiled and tested in Anaconda:

#### Prerequisites
- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda](https://www.anaconda.com/download) installed

#### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/OutUvAces/MDA-Layers-Downloader.git
   cd MDA-Layers-Downloader
   ```

2. **Create a new conda environment:**
   ```bash
   conda create -n mda-layers python=3.9 -y
   conda activate mda-layers
   ```

3. **Install geospatial dependencies via conda:**
   ```bash
   conda install -c conda-forge geopandas fiona pyproj shapely xarray netcdf4 aiohttp requests -y
   ```

4. **Install remaining dependencies:**
   ```bash
   pip install pyinstaller  # Only needed if building executables
   ```

5. **Run the application:**
   ```bash
   python main.py
   ```

### Option 2: Install from Source (pip)
For users who prefer pip over conda:

#### Prerequisites
- Python 3.8 or higher
- pip package manager

#### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/OutUvAces/MDA-Layers-Downloader.git
   cd MDA-Layers-Downloader
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python main.py
   ```

### Portable Executable (Experimental)
A portable executable is available for testing but may have compatibility issues with geospatial libraries:

1. Download `MDA_Layers_Downloader_v1.3_portable.zip` from [GitHub Releases](https://github.com/OutUvAces/MDA-Layers-Downloader/releases)
2. Unzip the downloaded file
3. Run `MDA_Layers_Downloader_v1.3_dir.exe` from the unzipped folder

## 📋 System Requirements

### Minimum Requirements
- **OS:** Windows 10/11, macOS 10.15+, or Linux
- **RAM:** 4GB minimum, 8GB recommended
- **Storage:** 2GB free space for data downloads
- **Internet:** Required for downloading marine data

### Dependencies
The application requires these Python packages:
- `geopandas` - Geospatial data processing
- `requests` - HTTP requests for data downloads
- `shapely` - Geometric operations
- `xarray` - Multi-dimensional data handling
- `netCDF4` - NetCDF file format support
- `aiohttp` - Asynchronous HTTP requests

## 🐛 Troubleshooting

### Common Issues

#### "GDAL DLL could not be found" or "No module named 'fiona'"
This occurs when geospatial libraries aren't properly installed. **Recommended solution:**

1. **Use Anaconda/Miniconda (best solution):**
   ```bash
   conda create -n mda-layers python=3.9 -y
   conda activate mda-layers
   conda install -c conda-forge geopandas fiona pyproj shapely xarray netcdf4 aiohttp requests -y
   ```

2. **Alternative pip troubleshooting:**
   - On Windows: Install GDAL from [GISInternals](https://www.gisinternals.com/release.php)
   - Try: `pip uninstall geopandas fiona pyogrio && pip install -r requirements.txt`
   - Consider using a virtual environment: `python -m venv mda_env`

3. **Use the portable executable** (may have limitations)

#### "Module not found" errors
1. Ensure you're using Python 3.8+
2. Try creating a new virtual environment:
   ```bash
   python -m venv mda_env
   mda_env\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```

#### Slow downloads or timeouts
- Check your internet connection
- Some marine datasets are large (100-200MB)
- The application will retry failed downloads automatically

### Getting Help
- Check existing [GitHub Issues](https://github.com/OutUvAces/MDA-Layers-Downloader/issues)
- Create a new issue with your error logs and system information

## 🔧 Development Setup

For contributors or advanced users:

1. **Install development dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install pyinstaller  # For building executables
   ```

2. **Run tests:**
   ```bash
   python -m pytest  # If test files exist
   ```

3. **Build executable:**
   ```bash
   pyinstaller single_file_executable.spec
   ```

## 📊 Data Sources

The application downloads data from these sources:
- **MarineRegions.org** - Maritime boundaries
- **Protected Planet** - Marine protected areas
- **NASA OSCAR** - Ocean currents (requires free account)
- **NGA MSI** - Navigation warnings
- **TeleGeography** - Submarine cables

Some data sources require free registration for access.

---

For the latest updates, visit the [GitHub repository](https://github.com/OutUvAces/MDA-Layers-Downloader).