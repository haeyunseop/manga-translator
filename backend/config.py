"""Local paths and limits. Never log credentials."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env', override=False, interpolate=False,encoding='utf-8-sig')
DATA = Path(os.environ.get('MANGATRANS_DATA', ROOT / 'data'))
MODELS = Path(os.environ.get('MANGATRANS_MODELS', ROOT / 'models'))
DATA.mkdir(parents=True, exist_ok=True)
MAX_PAGES = 20
MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_TOTAL_BYTES = 100 * 1024 * 1024
MODEL_KIND = os.environ.get('MANGATRANS_MODEL','qwen')
if MODEL_KIND not in {'nllb','m2m100','qwen'}:
    raise ValueError('MANGATRANS_MODEL must be nllb, m2m100 or qwen')
MODEL_ID = {'nllb':'facebook/nllb-200-distilled-600M','m2m100':'facebook/m2m100_418M','qwen':'unsloth/Qwen3-4B-Instruct-2507-GGUF'}[MODEL_KIND]
# Pinned model revision; set by the verified model download, never a floating runtime download.
MODEL_PATH = MODELS / MODEL_ID.split('/')[-1]
FONT_PATH = os.environ.get('MANGATRANS_FONT', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
OCR_KIND=os.environ.get('MANGATRANS_OCR','manga')
if OCR_KIND not in {'tesseract','manga'}:
    raise ValueError('MANGATRANS_OCR must be tesseract or manga')
MANGA_OCR_ID='kha-white/manga-ocr-base'
MANGA_OCR_REVISION='aa6573bd10b0d446cbf622e29c3e084914df9741'
MANGA_OCR_PATH=MODELS/'manga-ocr-base'
QWEN_FILE='Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
QWEN_REVISION='a06e946bb6b655725eafa393f4a9745d460374c9'
QWEN_SHA256='3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
LLAMA_RELEASE='b11429'
LLAMA_PATH=MODELS/f'llama-{LLAMA_RELEASE}'
