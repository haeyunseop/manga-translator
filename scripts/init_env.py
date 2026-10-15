"""Create private local credentials without printing them or overwriting existing values."""
from pathlib import Path
import secrets
import argparse
import getpass
import json
parser=argparse.ArgumentParser()
parser.add_argument('--password-prompt',action='store_true')
parser.add_argument('--font')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
path=root/'.env'
if path.exists():
    print('Existing .env preserved.')
else:
    password=secrets.token_urlsafe(24)
    if args.password_prompt:
        while True:
            password=getpass.getpass('Choose your MangaTrans password (at least 16 characters): ')
            if len(password)>=16 and '\n' not in password and '\r' not in password:
                if password==getpass.getpass('Confirm password: '): break
            print('Use at least 16 characters, and enter the same password twice.')
    with path.open('x') as file:
        # Quoting preserves special characters; credentials are never echoed.
        file.write(f'MANGATRANS_PASSWORD={json.dumps(password,ensure_ascii=False)}\nMANGATRANS_SESSION_SECRET={secrets.token_urlsafe(48)}\nMANGATRANS_SECURE_COOKIE=false\nMANGATRANS_ALLOWED_HOSTS=\n')
        if args.font:
            file.write(f'MANGATRANS_FONT={json.dumps(Path(args.font).resolve().as_posix(),ensure_ascii=False)}\n')
    path.chmod(0o600)
    print('Created private .env. Read it locally to find your login password; never commit it.')
