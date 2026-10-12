"""Vercel website configuration. Environment variables take precedence over values here."""
import os
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name(".env"), override=False)
except ImportError:
    pass

def setting(name, default=""):
    return os.getenv(name, globals().get(name, default)).strip()

# Safe defaults; set RENDER_BACKEND_URL to the deployed Render web-service origin.
SITE_NAME = "AniZoneFlix FileStore"
RENDER_BACKEND_URL = "https://filestore-2-35dz.onrender.com"
