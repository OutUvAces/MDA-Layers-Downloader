# MDA Layers Downloader

A comprehensive Python application for downloading and processing marine geospatial data layers. This tool provides both a user-friendly GUI interface and supports batch processing of marine data for visualization in tools like Google Earth.

## 🌊 Features

### Supported Data Layers
- **Territorial Waters** - National territorial sea boundaries
- **Contiguous Zones** - 24nm contiguous zone boundaries
- **Exclusive Economic Zones (EEZ)** - 200nm economic zone boundaries
- **Extended Continental Shelf (ECS)** - Extended continental shelf claims
- **Marine Protected Areas (MPA)** - Protected marine areas from WDPA database
- **Submarine Cables** - Global submarine cable infrastructure
- **Ocean Currents** - Real-time ocean surface current data (OSCAR)
- **Navigation Warnings** - Maritime safety warnings from NGA MSI

### Key Capabilities
- **GUI Interface** - User-friendly desktop application built with Tkinter
- **Batch Processing** - Automated downloading and processing
- **KML Output** - Google Earth compatible format
- **Custom Styling** - Configurable colors, opacity, and density settings
- **Concurrent Downloads** - Multi-threaded processing for faster downloads
- **Caching System** - Intelligent caching to avoid redundant downloads
- **Progress Monitoring** - Real-time progress updates during processing

## 📊 Data Sources

The application integrates data from authoritative marine geospatial sources:

- **MarineRegions.org** - Territorial waters, EEZ, ECS boundaries
- **Protected Planet (WDPA)** - Marine protected areas
- **NASA OSCAR** - Ocean surface current analysis
- **Submarine Cable Map** - Global submarine cable infrastructure
- **NGA MSI** - Navigation warnings and maritime safety information

## 🛠️ Installation

### Prerequisites
- Python 3.8 or higher
- Required Python packages:
  ```
  geopandas>=0.12.0
  requests>=2.28.0
  shapely>=1.8.0
  xarray>=2022.06.0
  netCDF4>=1.6.0
  ```

### Setup Instructions

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

## 🚀 Usage

### GUI Mode (Recommended)
Simply run `python main.py` to launch the graphical interface where you can:
- Select which marine data layers to download
- Configure colors, opacity, and density settings
- Choose output directory and processing options
- Monitor download progress in real-time

### Command Line Processing
The application can also be used programmatically for batch processing by importing the worker functions.

## ⚙️ Configuration

### Layer Types and Settings

Each data layer supports customization:

- **Color**: Hex color codes for visual distinction
- **Opacity**: Transparency levels (0-100%)
- **Density**: Geometry simplification levels (Low/Medium/High)

### Default Settings

| Layer Type | Default Color | Default Opacity |
|------------|---------------|-----------------|
| Territorial | Yellow (#ffff00) | 20% |
| Contiguous | Green (#00ff00) | 20% |
| EEZ | Blue (#0000ff) | 20% |
| ECS | Brown (#8B4513) | 20% |
| MPA | Red (#ff0000) | 20% |
| Cables | White (#ffffff) | 50% |
| Sea State | Black (#000000) | 100% |
| Nav Warnings | Red (#ff0000) | 80% |

### Authentication
Some data sources require authentication:
- **NASA OSCAR**: Requires Earthdata login credentials
- **NGA MSI**: Uses public APIs (no authentication required)

## 📁 Project Structure

```
MDA-Layers-Downloader/
├── core/                    # Core application modules
│   ├── __init__.py
│   ├── config.py           # Configuration constants and URLs
│   ├── types.py            # Type definitions and data classes
│   └── utils.py            # Utility functions
├── downloaders/            # Data source downloaders
│   ├── __init__.py
│   ├── marineregions.py    # MarineRegions data downloader
│   ├── navigation_warnings.py  # NGA MSI warnings downloader
│   ├── navwarnings_fetcher.py  # Warning data fetching
│   ├── navwarnings_parser.py   # Warning text parsing
│   ├── oscar_currents.py   # OSCAR ocean currents downloader
│   ├── submarine_cables.py # Cable infrastructure downloader
│   └── wdpa.py             # WDPA protected areas downloader
├── gui/                    # Graphical user interface
│   ├── __init__.py
│   ├── controls.py         # GUI control utilities
│   ├── gui_state.py        # GUI state management
│   ├── main_window.py      # Main application window
│   └── widgets.py          # Custom GUI widgets
├── processing/             # Data processing utilities
│   ├── __init__.py
│   ├── kml_style.py        # KML styling and conversion
│   └── simplify.py         # Geometry simplification
├── workers/                # Processing workers
│   ├── __init__.py
│   └── download_worker.py  # Main processing coordinator
├── main.py                 # Application entry point
├── .gitignore             # Git ignore rules
└── README.md              # This file
```

## 🔧 Development

### Code Quality
- Comprehensive docstrings for all functions and classes
- Type hints throughout the codebase
- Modular architecture with clear separation of concerns
- Extensive error handling and logging

### Testing
The project includes comprehensive testing capabilities for data parsing and extraction functions. Test scripts are maintained separately from the main codebase.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines
- Follow PEP 8 style guidelines
- Add docstrings to all new functions and classes
- Include type hints for function parameters and return values
- Test changes thoroughly before submitting

## 📄 License

This project is open source. Please check the license file for specific terms and conditions.

## 🙏 Acknowledgments

- **MarineRegions.org** for providing comprehensive marine boundary data
- **Protected Planet** for the World Database on Protected Areas
- **NASA PO.DAAC** for OSCAR ocean current data
- **NGA MSI** for navigation warning services
- **Submarine Cable Map** for cable infrastructure data

## 📞 Support

For issues, questions, or contributions, please use the GitHub issue tracker or submit pull requests.

---

**Built with ❤️ for the marine geospatial community**