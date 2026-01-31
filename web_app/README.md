# MDA Layers Downloader - Web Application

This is a web-based interface for the MDA Layers Downloader marine geospatial data tool. It converts the desktop GUI application to a web service that can be deployed on a server.

## Features

- **Web Form Interface**: Easy-to-use web form for selecting marine data layers
- **Background Processing**: Downloads run in the background with progress tracking
- **File Downloads**: Generated KML files can be downloaded as ZIP archives
- **Multi-user Support**: Each user gets their own workspace and download queue
- **Responsive Design**: Works on desktop and mobile devices

## Installation

1. **Clone the repository and switch to web deployment branch:**
   ```bash
   git clone https://github.com/OutUvAces/MDA-Layers-Downloader.git
   cd MDA-Layers-Downloader
   git checkout web-deployment
   ```

2. **Set up the web application:**
   ```bash
   cd web_app

   # Option 1: Automated setup (recommended)
   python setup.py

   # Option 2: Manual setup
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Linux/Mac:
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Environment variables (optional):**
   ```bash
   export FLASK_ENV=development  # For development
   export FLASK_SECRET_KEY=your-secret-key-here
   ```

## Usage

### Development

#### Quick Start (macOS/Linux)

```bash
# 1. Navigate to web app directory
cd web_app

# 2. Install system dependencies (macOS)
brew install gdal geos proj

# Ubuntu/Debian alternative:
# sudo apt-get update && sudo apt-get install libgdal-dev gdal-bin libgeos-dev libproj-dev proj-data

# 3. Create virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 4. Install Python dependencies
pip install -r requirements.txt

# 5. If geopandas installation fails:
pip install --no-binary :all: geopandas
# Or use conda: conda install -c conda-forge geopandas gdal

# 6. Set environment variables (optional)
export FLASK_SECRET_KEY="dev-secret-key"
export FLASK_DEBUG=1

# 7. Run the development server
python run.py

# Alternative direct Flask run:
# python app.py
```

The application will be available at `http://localhost:5000`

### Quick Test

1. **Open browser**: Go to `http://localhost:5000`
2. **Fill form**:
   - Country: "Japan"
   - ISO Code: "JPN"
   - Check: "Territorial Waters" and "Exclusive Economic Zone"
3. **Click "Start Download"**
4. **Monitor progress**:
   - Browser shows progress page with real-time updates
   - Terminal shows detailed processing logs
5. **On completion**: Download buttons appear for country/global ZIP files
6. **Verify**: Downloaded ZIP contains KML marine data layers

### Expected Server Output

```
Starting MDA Layers Downloader Web Application on port 5000
Debug mode: True
 * Running on http://127.0.0.1:5000 (Press CTRL+C to quit)
```

### Troubleshooting

#### Import Errors ("No module named core.types")
- Ensure you're running from the `web_app` directory
- Virtual environment must be activated
- All dependencies must be installed

#### cftime Import Error ("No module named 'cftime'")
- Required for OSCAR currents NetCDF processing
- Install via conda: `conda install -c conda-forge cftime`
- Or via pip: `pip install cftime`

#### Conda Environment Setup Issues
- Ensure conda environment is activated: `conda activate mda-web`
- If geopandas fails, try: `conda install -c conda-forge geopandas`
- For NetCDF support: `conda install -c conda-forge netcdf4 cftime xarray`

#### Port 5000 Already in Use
```bash
# Use different port
export FLASK_RUN_PORT=5001
python run.py
```

#### GDAL/GeoPandas Installation Issues
```bash
# Try without binary packages
pip install --no-binary :all: geopandas

# Or use conda (recommended)
conda install -c conda-forge geopandas gdal
```

#### Permission Errors
- Ensure write access to `web_app/uploads/` and `web_app/outputs/` directories
- The app creates these automatically on startup

### Local Development Setup

#### Option 1: Conda Environment (Recommended for Windows/Linux)

For users with conda/miniconda installed:

```bash
# 1. Navigate to web app
cd web_app

# 2. Create conda environment with geospatial dependencies
conda create -n mda-web python=3.10 -y
conda activate mda-web

# 3. Install core geospatial packages via conda-forge
conda install -c conda-forge geopandas shapely fiona pyproj gdal geos proj -y

# 4. Install remaining Python packages via pip
pip install -r requirements.txt

# 5. For additional NetCDF support (OSCAR currents)
conda install -c conda-forge netcdf4 cftime xarray -y
```

#### Option 2: Virtual Environment (macOS/Linux)

For the first time setup on macOS/Linux:

```bash
# 1. Navigate to web app
cd web_app

# 2. Install system dependencies (if needed)
# macOS:
brew install gdal geos proj

# Ubuntu/Debian:
sudo apt-get update
sudo apt-get install libgdal-dev gdal-bin libgeos-dev libproj-dev proj-data

# 3. Create virtual environment and install
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. If geopandas fails, try:
pip install --no-binary :all: geopandas
# or use conda:
# conda install -c conda-forge geopandas gdal

# 5. Run the app
python run.py

# 6. Alternative direct Flask run
export FLASK_APP=app.py
export FLASK_DEBUG=1
flask run --host=0.0.0.0 --port=5000
```

### Production Deployment

For production deployment, use a WSGI server like Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

### Docker Deployment (Recommended)

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["python", "app.py"]
```

## Configuration

The web application uses the following configuration:

- **UPLOAD_FOLDER**: Directory for temporary file uploads (default: `uploads/`)
- **OUTPUT_FOLDER**: Directory for generated output files (default: `outputs/`)
- **MAX_CONTENT_LENGTH**: Maximum file upload size (default: 16MB)

## API Endpoints

- `GET /`: Main form page
- `POST /start_download`: Start a download task
- `GET /progress/<task_id>`: Progress page for a task
- `GET /progress_update/<task_id>`: JSON API for progress updates
- `GET /download/<task_id>/<path_type>`: Download generated files

## Architecture

The web application consists of:

- **Flask Web Framework**: Provides the web interface and routing
- **Background Processing**: Uses Python threading for background download tasks
- **Progress Tracking**: Real-time progress updates via AJAX calls
- **File Management**: Automatic cleanup of temporary files and downloads

## Security Considerations

- File uploads are restricted to specific types and sizes
- Temporary directories are created per task to isolate user data
- Background processes run with limited privileges
- Secret key should be set for production deployments

## Troubleshooting

### Common Issues

1. **Permission Errors**: Ensure the web application has write access to the output directories
2. **Memory Usage**: Large datasets may require increasing server memory limits
3. **Timeout Issues**: Network timeouts can occur with large downloads - consider increasing timeout values
4. **GDAL/GEOS Errors**: Ensure GEOS and GDAL libraries are properly installed

### Dependency Installation Issues

If `pip install -r requirements.txt` fails:

**Windows:**
```bash
# Option 1: Use conda (recommended)
conda install -c conda-forge geopandas gdal

# Option 2: Manual GDAL installation
# Download GDAL wheel from https://www.lfd.uci.edu/~gohlke/pythonlibs/#gdal
# pip install GDAL-*.whl
# Then: pip install geopandas
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install libgdal-dev gdal-bin
pip install -r requirements.txt
```

**macOS:**
```bash
# Install Homebrew if not installed: https://brew.sh/
brew install gdal
pip install -r requirements.txt
```

### Module Import Errors

If you get "ModuleNotFoundError" when running the app:
1. Ensure you're in the virtual environment: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Linux/Mac)
2. The app imports modules from the parent directory - ensure you're running from the `web_app` folder
3. Check that all dependencies are installed: `pip list | grep -E "(flask|geopandas|xarray)"`

### Port Already in Use

If port 5000 is busy:
```bash
# Run on different port
FLASK_RUN_PORT=5001 python run.py
```

### Large File Downloads

For very large downloads, you may need to:
- Increase Flask's `MAX_CONTENT_LENGTH` in `app.py`
- Add more memory to your system
- Consider using a cloud deployment with more resources

### Logs

Check the Flask application logs for detailed error messages. The web interface also displays progress messages and error notifications.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is open source. See the main repository for license information.