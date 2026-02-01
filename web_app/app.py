"""
MDA Layers Downloader - Web Application
=====================================

Web interface for the MDA Layers Downloader marine geospatial data tool.
Converts the desktop GUI application to a web-based service.

Features:
- Web form interface for layer selection
- Background processing for data downloads
- File download links for generated KML files
- Progress tracking and status updates
"""

import os
import sys
import asyncio
import tempfile
import shutil
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from werkzeug.utils import secure_filename
import threading
import queue
import json
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

# Add parent directory to path to import existing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import LayerSettings
from workers.download_worker import worker

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'mda-layers-downloader-web-secret-key')

# Configuration
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Global variables for progress tracking
progress_data = {}
current_tasks = {}

# Cache configuration
CACHE_DIR = Path(__file__).parent.parent / "cache"
STATIC_CACHE_DIR = CACHE_DIR / "static"
DYNAMIC_CACHE_DIR = CACHE_DIR / "dynamic"
CACHE_METADATA_FILE = CACHE_DIR / "cache_metadata.json"

# Ensure cache directories exist
STATIC_CACHE_DIR.mkdir(parents=True, exist_ok=True)
DYNAMIC_CACHE_DIR.mkdir(parents=True, exist_ok=True)

def load_cache_metadata():
    """Load cache metadata from JSON file"""
    if CACHE_METADATA_FILE.exists():
        try:
            with open(CACHE_METADATA_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading cache metadata: {e}")
    return {"last_refresh_static": None, "last_refresh_dynamic": None, "version": "1.0"}

def save_cache_metadata(metadata):
    """Save cache metadata to JSON file"""
    try:
        with open(CACHE_METADATA_FILE, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
    except Exception as e:
        print(f"Error saving cache metadata: {e}")

def get_cache_age(last_refresh, unit='hours'):
    """Get age of cache in specified unit"""
    if not last_refresh:
        return float('inf')
    try:
        if isinstance(last_refresh, str):
            last_refresh = datetime.fromisoformat(last_refresh.replace('Z', '+00:00'))
        age = datetime.now() - last_refresh.replace(tzinfo=None)
        if unit == 'hours':
            return age.total_seconds() / 3600
        elif unit == 'days':
            return age.total_seconds() / (3600 * 24)
    except Exception as e:
        print(f"Error calculating cache age: {e}")
        return float('inf')

def refresh_caches():
    """Refresh all caches (static and dynamic)"""
    print("CACHE REFRESH: Starting cache refresh...")

    metadata = load_cache_metadata()
    username = os.getenv('NASA_USERNAME')
    password = os.getenv('NASA_PASSWORD')

    # Refresh static caches (30 days)
    static_age_days = get_cache_age(metadata.get('last_refresh_static'), 'days')
    if static_age_days > 30 or metadata.get('last_refresh_static') is None:
        print("CACHE REFRESH: Refreshing static caches...")
        try:
            # Import downloaders here to avoid circular imports
            from downloaders.marineregions import refresh_static_caches
            from downloaders.wdpa import refresh_static_caches as refresh_wdpa
            from downloaders.submarine_cables import refresh_static_caches as refresh_cables

            # Call refresh functions
            try:
                refresh_static_caches()
                print("CACHE REFRESH: MarineRegions static refresh completed")
            except Exception as e:
                print(f"CACHE REFRESH: MarineRegions static refresh failed: {e}")

            try:
                refresh_wdpa()
                print("CACHE REFRESH: WDPA static refresh completed")
            except Exception as e:
                print(f"CACHE REFRESH: WDPA static refresh failed: {e}")

            try:
                refresh_cables()
                print("CACHE REFRESH: Cables static refresh completed")
            except Exception as e:
                print(f"CACHE REFRESH: Cables static refresh failed: {e}")

            metadata['last_refresh_static'] = datetime.now()
            print("CACHE REFRESH: Static caches refreshed successfully")
        except Exception as e:
            print(f"CACHE REFRESH: Error refreshing static caches: {e}")
    else:
        print(f"CACHE REFRESH: Static caches are fresh ({static_age_days:.1f} days old)")

    # Refresh dynamic caches (12 hours)
    dynamic_age_hours = get_cache_age(metadata.get('last_refresh_dynamic'), 'hours')
    if dynamic_age_hours > 12 or metadata.get('last_refresh_dynamic') is None:
        print("CACHE REFRESH: Refreshing dynamic caches...")
        try:
            from downloaders.oscar_currents import refresh_dynamic_caches
            from downloaders.navigation_warnings import refresh_dynamic_caches as refresh_nav

            try:
                refresh_dynamic_caches()
                print("CACHE REFRESH: OSCAR dynamic refresh completed")
            except Exception as e:
                print(f"CACHE REFRESH: OSCAR dynamic refresh failed: {e}")

            try:
                refresh_nav()
                print("CACHE REFRESH: Nav warnings dynamic refresh completed")
            except Exception as e:
                print(f"CACHE REFRESH: Nav warnings dynamic refresh failed: {e}")

            metadata['last_refresh_dynamic'] = datetime.now()
            print("CACHE REFRESH: Dynamic caches refreshed successfully")
        except Exception as e:
            print(f"CACHE REFRESH: Error refreshing dynamic caches: {e}")
    else:
        print(f"CACHE REFRESH: Dynamic caches are fresh ({dynamic_age_hours:.1f} hours old)")

    save_cache_metadata(metadata)
    print("CACHE REFRESH: Cache refresh completed")

# Initialize and start the scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(refresh_caches, 'interval', hours=12, id='cache_refresh')
scheduler.start()

# Initial cache check on startup
print("APP STARTUP: Checking cache status...")
refresh_caches()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def run_download_task(task_id, settings, country_path, global_path, cache_path, iso_code, country_name, progress_queue):
    """Run the download task in a separate thread"""
    try:
        def progress_callback(delta: float, message: str = ""):
            print(f"PROGRESS UPDATE SENT: delta={delta}, message='{message}'")
            if message:
                progress_queue.put({"type": "message", "content": message})
            if delta > 0:
                progress_queue.put({"type": "progress", "content": delta})

        # Run the processing
        success = worker(settings, username, password, str(country_path), str(global_path), cache_path, iso_code, country_name, progress_callback)

        if success:
            progress_queue.put({"type": "complete", "content": "Download completed successfully!"})
        else:
            progress_queue.put({"type": "error", "content": "Download failed. Check logs for details."})

    except Exception as e:
        progress_queue.put({"type": "error", "content": f"Task failed: {str(e)}"})

@app.route('/')
def index():
    """Main page with layer selection form"""
    # Get cache status for display
    metadata = load_cache_metadata()
    static_age = get_cache_age(metadata.get('last_refresh_static'), 'days')
    dynamic_age = get_cache_age(metadata.get('last_refresh_dynamic'), 'hours')

    cache_status = {
        'static_age_days': static_age,
        'dynamic_age_hours': dynamic_age,
        'static_never_refreshed': static_age == float('inf') or static_age > 999,
        'dynamic_never_refreshed': dynamic_age == float('inf') or dynamic_age > 999,
        'last_static': metadata.get('last_refresh_static'),
        'last_dynamic': metadata.get('last_refresh_dynamic')
    }
    return render_template('index.html', cache_status=cache_status)

@app.route('/cache_status')
def cache_status():
    """API endpoint for cache status"""
    metadata = load_cache_metadata()
    return jsonify({
        'static_age_days': get_cache_age(metadata.get('last_refresh_static'), 'days'),
        'dynamic_age_hours': get_cache_age(metadata.get('last_refresh_dynamic'), 'hours'),
        'last_refresh_static': metadata.get('last_refresh_static'),
        'last_refresh_dynamic': metadata.get('last_refresh_dynamic')
    })

@app.route('/start_download', methods=['POST'])
def start_download():
    """Handle the download request"""
    try:
        # Extract form data
        country = request.form.get('country', '')
        iso_code = request.form.get('iso_code', '')
        username = request.form.get('nasa_username', '')
        password = request.form.get('nasa_password', '')

        print(f"MAIN THREAD: Passing NASA creds - username='{username[:3] if username else ''}...', password length={len(password)}")

        # Parse layer selections
        layer_settings = LayerSettings(
            # Country-specific layers
            territorial=request.form.get('territorial') == 'on',
            contiguous=request.form.get('contiguous') == 'on',
            mpa=request.form.get('mpa') == 'on',
            eez=request.form.get('eez') == 'on',
            ecs=request.form.get('ecs') == 'on',

            # Global layers
            cables=request.form.get('cables') == 'on',
            seastate_global=request.form.get('seastate_global') == 'on',
            navwarnings=request.form.get('navwarnings') == 'on',

            # Settings
            territorial_color=request.form.get('territorial_color', '#ffff00'),
            contiguous_color=request.form.get('contiguous_color', '#00ff00'),
            mpa_color=request.form.get('mpa_color', '#ff0000'),
            eez_color=request.form.get('eez_color', '#0000ff'),
            ecs_color=request.form.get('ecs_color', '#8B4513'),
            cables_color=request.form.get('cables_color', '#ffffff'),
            seastate_color=request.form.get('seastate_color', '#000000'),
            navwarnings_color=request.form.get('navwarnings_color', '#ff0000'),

            # Opacity values (as strings)
            territorial_opacity=request.form.get('territorial_opacity', '20'),
            contiguous_opacity=request.form.get('contiguous_opacity', '20'),
            mpa_opacity=request.form.get('mpa_opacity', '20'),
            eez_opacity=request.form.get('eez_opacity', '20'),
            ecs_opacity=request.form.get('ecs_opacity', '20'),
            cables_opacity=request.form.get('cables_opacity', '50'),
            seastate_opacity=request.form.get('seastate_opacity', '20'),
            navwarnings_opacity=request.form.get('navwarnings_opacity', '80'),

            # Other settings
            seastate_country=request.form.get('seastate_country') == 'on',

            # Sea state density settings (defaults)
            seastate_density_country=1.0,
            seastate_density_global=0.5,

            # Other flags
            navwarnings_custom=False,
            cables_random=False
        )

        # Create unique task ID
        task_id = f"task_{len(current_tasks)}"

        # Set up directories
        base_dir = Path(app.config['OUTPUT_FOLDER']) / task_id
        base_dir.mkdir(exist_ok=True)

        country_dir = base_dir / "country" if country else None
        global_dir = base_dir / "global"
        cache_dir = base_dir / "cache"

        country_dir.mkdir(exist_ok=True)
        global_dir.mkdir(exist_ok=True)
        cache_dir.mkdir(exist_ok=True)

        # Set up progress tracking
        progress_queue = queue.Queue()
        progress_data[task_id] = {
            'messages': [],
            'progress': 0,
            'status': 'running',
            'country_dir': str(country_dir) if country_dir else None,
            'global_dir': str(global_dir),
            'queue': progress_queue
        }

        # Start the download task in a background thread
        print(f"MAIN THREAD: Launching worker for task {task_id} with iso_code={iso_code}")

        download_thread = threading.Thread(
            target=run_download_task,
            args=(task_id, layer_settings, country_dir, global_dir, cache_dir, iso_code, country, progress_queue)
        )
        download_thread.daemon = True
        download_thread.start()

        print(f"MAIN THREAD: Worker thread started, alive: {download_thread.is_alive()}")

        current_tasks[task_id] = download_thread

        return redirect(url_for('progress', task_id=task_id))

    except Exception as e:
        flash(f'Error starting download: {str(e)}')
        return redirect(url_for('index'))

@app.route('/progress/<task_id>')
def progress(task_id):
    """Show download progress"""
    if task_id not in progress_data:
        flash('Task not found')
        return redirect(url_for('index'))

    return render_template('progress.html', task_id=task_id)

@app.route('/progress_update/<task_id>')
def progress_update(task_id):
    """API endpoint for progress updates"""
    print(f"Progress poll requested for task {task_id} — current data: messages={len(progress_data.get(task_id, {}).get('messages', []))}, progress={progress_data.get(task_id, {}).get('progress', 0)}")

    if task_id not in progress_data:
        return jsonify({'error': 'Task not found'}), 404

    task_data = progress_data[task_id]
    progress_queue = task_data['queue']

    # Process new messages from the queue
    try:
        while True:
            update = progress_queue.get_nowait()
            print(f"PROCESSING QUEUE UPDATE: {update}")

            if update['type'] == 'message':
                task_data['messages'].append(update['content'])
            elif update['type'] == 'progress':
                task_data['progress'] = min(100, task_data['progress'] + update['content'])
            elif update['type'] == 'complete':
                task_data['status'] = 'completed'
                task_data['messages'].append(update['content'])
            elif update['type'] == 'error':
                task_data['status'] = 'error'
                task_data['messages'].append(update['content'])
    except queue.Empty:
        pass  # No more updates in queue

    return jsonify({
        'messages': task_data['messages'],
        'progress': task_data['progress'],
        'status': task_data['status']
    })

@app.route('/download/<task_id>/<path_type>')
def download(task_id, path_type):
    """Download generated files"""
    if task_id not in progress_data:
        flash('Task not found')
        return redirect(url_for('index'))

    task_data = progress_data[task_id]

    if path_type == 'country' and task_data['country_dir']:
        download_dir = task_data['country_dir']
    elif path_type == 'global':
        download_dir = task_data['global_dir']
    else:
        flash('Invalid download type')
        return redirect(url_for('progress', task_id=task_id))

    # Create a zip file of the output directory
    import zipfile
    zip_path = os.path.join(app.config['OUTPUT_FOLDER'], f'{task_id}_{path_type}.zip')

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(download_dir):
            for file in files:
                zipf.write(os.path.join(root, file),
                          os.path.relpath(os.path.join(root, file), download_dir))

    return send_file(zip_path, as_attachment=True, download_name=f'{task_id}_{path_type}.zip')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)