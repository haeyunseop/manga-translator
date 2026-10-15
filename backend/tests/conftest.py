import os
import tempfile
from pathlib import Path

_directory=tempfile.TemporaryDirectory(prefix='mangatrans-tests-')
os.environ['MANGATRANS_DATA']=_directory.name
os.environ['MANGATRANS_PASSWORD']='test-only-password-not-for-deployment'
os.environ['MANGATRANS_SESSION_SECRET']='test-only-session-key-not-for-deployment-123456'
os.environ['MANGATRANS_SECURE_COOKIE']='false'
