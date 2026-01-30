# Installation Guide

This guide provides multiple ways to install and run the MDA Layers Downloader.

## 🚀 Quick Start (Recommended)

### Option 1: Conda Installation (Most Reliable)
For the best experience with geospatial libraries, use conda:

#### Prerequisites
- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda](https://www.anaconda.com/)
- Git

#### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/OutUvAces/MDA-Layers-Downloader.git
   cd MDA-Layers-Downloader
   ```

2. **Create conda environment:**
   ```bash
   conda env create -f environment.yml
   conda activate mda-layers-downloader
   ```

3. **Run the application:**
   ```bash
   python main.py
   ```

### Option 2: Pip Installation
If you prefer pip over conda:

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

**Note:** Pip installation may have issues with geospatial libraries on some systems. Conda is recommended for better compatibility.

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

#### "GDAL DLL could not be found"
This occurs when geospatial libraries aren't properly installed. Try:
1. Reinstall dependencies: `pip uninstall geopandas fiona pyogrio && pip install -r requirements.txt`
2. On Windows: Install GDAL from [GISInternals](https://www.gisinternals.com/release.php)
3. Use the portable executable version instead

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