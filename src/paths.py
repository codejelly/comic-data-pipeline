from pathlib import Path

# Repo root: price-predictor-be-comic/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = DATA_DIR / "logs"
CACHE_DIR = DATA_DIR / "cache"
