import os
import tempfile
from pathlib import Path

_directory=tempfile.TemporaryDirectory(prefix='mangatrans-tests-')
os.environ['MANGATRANS_DATA']=_directory.name
os.environ['MANGATRANS_PASSWORD']='test-only-password-not-for-deployment'
os.environ['MANGATRANS_SESSION_SECRET']='test-only-session-key-not-for-deployment-123456'
os.environ['MANGATRANS_SECURE_COOKIE']='false'
# Fast scheduling/API regression tests explicitly retain the legacy engines.
# New default MangaOCR/Qwen inference is exercised by validate_quality.py and
# the browser tests against the actual app, without these test-only overrides.
os.environ['MANGATRANS_MODEL']='nllb'
os.environ['MANGATRANS_OCR']='tesseract'
