"""Local paths and limits. Never log credentials."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env', override=False, interpolate=False)
DATA = Path(os.environ.get('MANGATRANS_DATA', ROOT / 'data'))
MODELS = Path(os.environ.get('MANGATRANS_MODELS', ROOT / 'models'))
DATA.mkdir(parents=True, exist_ok=True)
MAX_PAGES = 20
MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_TOTAL_BYTES = 100 * 1024 * 1024
MODEL_KIND = os.environ.get('MANGATRANS_MODEL','nllb')
if MODEL_KIND not in {'nllb','m2m100'}:
    raise ValueError('MANGATRANS_MODEL must be nllb or m2m100')
MODEL_ID = 'facebook/nllb-200-distilled-600M' if MODEL_KIND=='nllb' else 'facebook/m2m100_418M'
# Pinned model revision; set by the verified model download, never a floating runtime download.
MODEL_PATH = MODELS / MODEL_ID.split('/')[-1]
FONT_PATH = os.environ.get('MANGATRANS_FONT', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
