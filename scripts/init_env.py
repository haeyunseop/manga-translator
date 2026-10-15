"""Create private local credentials without printing them or overwriting existing values."""
from pathlib import Path
import secrets
import argparse
import getpass
import json
import os
parser=argparse.ArgumentParser()
parser.add_argument('--password-prompt',action='store_true')
parser.add_argument('--font')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
path=root/'.env'
if path.exists():
    raw=path.read_bytes()
    try:
        raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        try:
            text=raw.decode('cp949')
        except UnicodeDecodeError:
            raise SystemExit('Existing .env encoding is not recognized. The file was left unchanged; do not share its contents.') from None
        if not all(name+'=' in text for name in ['MANGATRANS_PASSWORD','MANGATRANS_SESSION_SECRET']):
            raise SystemExit('Existing .env is not a complete settings file. The file was left unchanged.')
        # Repair the old Windows locale encoding without replacing the file or its ACL.
        # No credential values are logged, changed, or copied to a second file.
        with path.open('r+b') as file:
            if file.read()!=raw:
                raise SystemExit('Settings changed during repair. Retry setup; no changes were made.')
            file.seek(0)
            file.write(text.encode('utf-8'))
            file.truncate()
            file.flush()
            os.fsync(file.fileno())
        print('Repaired legacy Windows settings encoding to UTF-8. Existing values preserved.')
    print('Existing .env preserved.')
else:
    password=secrets.token_urlsafe(24)
    if args.password_prompt:
        while True:
            password=getpass.getpass('Choose your MangaTrans password (at least 16 characters): ')
            if len(password)>=16 and '\n' not in password and '\r' not in password:
                if password==getpass.getpass('Confirm password: '): break
            print('Use at least 16 characters, and enter the same password twice.')
    with path.open('x',encoding='utf-8',newline='\n') as file:
        # Quoting preserves special characters; credentials are never echoed.
        file.write(f'MANGATRANS_PASSWORD={json.dumps(password,ensure_ascii=False)}\nMANGATRANS_SESSION_SECRET={secrets.token_urlsafe(48)}\nMANGATRANS_SECURE_COOKIE=false\nMANGATRANS_ALLOWED_HOSTS=\n')
        if args.font:
            file.write(f'MANGATRANS_FONT={json.dumps(Path(args.font).resolve().as_posix(),ensure_ascii=False)}\n')
    path.chmod(0o600)
    print('Created private .env. Read it locally to find your login password; never commit it.')
