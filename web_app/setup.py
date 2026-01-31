#!/usr/bin/env python
"""
Setup script for MDA Layers Downloader Web Application
Handles dependency installation and environment setup.
"""

import subprocess
import sys
import os
import platform

def run_command(cmd, description):
    """Run a command and print status"""
    print(f"\n🔧 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"Error: {e.stderr}")
        return False

def main():
    print("🚀 Setting up MDA Layers Downloader Web Application")
    print("=" * 60)

    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)

    print(f"✅ Python {sys.version.split()[0]} detected")

    # Check if we're in the right directory
    if not os.path.exists('app.py'):
        print("❌ Please run this script from the web_app directory")
        print("Usage: cd web_app && python setup.py")
        sys.exit(1)

    # Create virtual environment if it doesn't exist
    if not os.path.exists('venv'):
        if not run_command('python -m venv venv', 'Creating virtual environment'):
            sys.exit(1)
    else:
        print("✅ Virtual environment already exists")

    # Activate virtual environment and install dependencies
    if platform.system() == 'Windows':
        activate_cmd = 'venv\\Scripts\\activate'
        pip_cmd = 'venv\\Scripts\\pip'
    else:
        activate_cmd = 'source venv/bin/activate'
        pip_cmd = 'venv/bin/pip'

    # Install Python dependencies
    if not run_command(f'{pip_cmd} install --upgrade pip', 'Upgrading pip'):
        sys.exit(1)

    if not run_command(f'{pip_cmd} install -r requirements.txt', 'Installing Python dependencies'):
        print("\n💡 If geopandas installation fails, you may need to install system dependencies:")
        if platform.system() == 'Windows':
            print("   - Install GDAL from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#gdal")
            print("   - Or use conda: conda install -c conda-forge geopandas")
        elif platform.system() == 'Linux':
            print("   - Ubuntu/Debian: sudo apt-get install libgdal-dev")
            print("   - CentOS/RHEL: sudo yum install gdal-devel")
        elif platform.system() == 'Darwin':  # macOS
            print("   - Install Homebrew: https://brew.sh/")
            print("   - Then: brew install gdal")
        sys.exit(1)

    print("\n🎉 Setup completed successfully!")
    print("\n🚀 To run the application:")
    print("   python run.py")
    print("\n📱 Then open your browser to: http://localhost:5000")

if __name__ == '__main__':
    main()