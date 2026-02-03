#!/usr/bin/env python
"""
Run script for MDA Layers Downloader Web Application
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web_app.app import app, refresh_caches

if __name__ == '__main__':
    # Get port from environment variable or default to 5000
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    print(f"Starting MDA Layers Downloader Web Application on port {port}")
    print(f"Debug mode: {debug}")

    # Start cache refresh in background before starting Flask app
    print("APP STARTUP: Starting initial cache refresh in background...")
    import threading
    print("DEBUG: Imported threading module")
    cache_thread = threading.Thread(target=refresh_caches, daemon=True)
    print("DEBUG: Created thread object")
    cache_thread.start()
    print("DEBUG: Started thread, thread is alive:", cache_thread.is_alive())

    # Only print startup message in main process (not reloader child)
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        threaded=True
    )