"""Activate installed quality models without replacing credentials or file ACLs."""
from pathlib import Path
import io
import os
import re
import sys
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]

def activate(path):
    original=path.read_bytes()
    text=original.decode('utf-8-sig')
    before=dotenv_values(stream=io.StringIO(text),interpolate=False)
    if not before.get('MANGATRANS_PASSWORD') or not before.get('MANGATRANS_SESSION_SECRET'):
        raise RuntimeError('Existing private settings are incomplete. Run setup first.')
    updates={'MANGATRANS_MODEL':'qwen','MANGATRANS_OCR':'manga'}
    lines=text.splitlines(keepends=True)
    seen=set();output=[]
    for line in lines:
        match=re.match(r'^\s*(?:export\s+)?(MANGATRANS_MODEL|MANGATRANS_OCR)\s*=',line)
        if match:
            key=match.group(1)
            if key not in seen: output.append(f'{key}={updates[key]}\n')
            seen.add(key)
        else:
            output.append(line)
    if output and not output[-1].endswith(('\n','\r')): output[-1]+='\n'
    for key,value in updates.items():
        if key not in seen: output.append(f'{key}={value}\n')
    updated=''.join(output)
    after=dotenv_values(stream=io.StringIO(updated),interpolate=False)
    if {k:v for k,v in before.items() if k not in updates}!={k:v for k,v in after.items() if k not in updates}:
        raise RuntimeError('Settings could not be updated safely. File left unchanged.')
    raw=updated.encode('utf-8-sig' if original.startswith(b'\xef\xbb\xbf') else 'utf-8')
    with path.open('r+b') as file:
        if file.read()!=original:
            raise RuntimeError('Settings changed during update. Retry; no changes were made.')
        file.seek(0);file.write(raw);file.truncate();file.flush();os.fsync(file.fileno())

if __name__=='__main__':
    sys.path.insert(0,str(ROOT))
    from backend.config import MODELS,QWEN_FILE,MANGA_OCR_PATH
    from backend.manga_ocr import manga_reader
    from backend.llama_translate import runtime_binary
    if not manga_reader.ready() or not (MODELS/'Qwen3-4B-Instruct-2507-GGUF'/QWEN_FILE).is_file() or runtime_binary() is None:
        raise SystemExit('Models are incomplete. Download and verify quality models before activation. Existing settings unchanged.')
    activate(ROOT/'.env')
    print('Activated local MangaOCR and Qwen3 4B. Existing password, session key, font and access settings preserved. Restart MangaTrans.')
