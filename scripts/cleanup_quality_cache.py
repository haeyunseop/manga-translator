"""Remove only the stopped API process's private inference cache."""
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.config import DATA

if len(sys.argv)!=2 or not sys.argv[1].isdigit() or int(sys.argv[1])<=0:
    raise SystemExit('Expected the stopped MangaTrans API process ID.')
shutil.rmtree(DATA/'.llama-cache'/str(int(sys.argv[1])),ignore_errors=True)
