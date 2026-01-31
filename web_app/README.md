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

```bash
cd web_app

# Activate virtual environment (if not using setup.py)
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Run the development server
python run.py
# Or directly:
python app.py
```

The application will be available at `http://localhost:5000`

### Quick Test

1. Open http://localhost:5000 in your browser
2. Select "Japan" as country and "JPN" as ISO code
3. Check 1-2 layers (e.g., "Territorial Waters", "Exclusive Economic Zone")
4. Click "Start Download"
5. Watch progress updates in the log area
6. When complete, download the generated ZIP files

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