"""
Navigation warnings data downloader and processor.

This module handles downloading navigation warning data and converting it to KML format.
"""

import os
import json
import datetime
from pathlib import Path
from core.types import LayerTask