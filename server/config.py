from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'
STATIC_DIR = BASE_DIR / 'static'

DEBUG = True
SECRET_KEY = 'geomine3d-dev-secret-key-not-for-production'
