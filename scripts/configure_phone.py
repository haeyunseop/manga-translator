"""Apply only non-secret HTTPS settings, preserving private credentials."""
import argparse
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import set_key

parser=argparse.ArgumentParser()
parser.add_argument('origin')
args=parser.parse_args()
u=urlsplit(args.origin)
if u.scheme!='https' or not u.hostname or u.username or u.password or u.port not in (None,443) or u.path or u.query or u.fragment:
    parser.error('Provide an HTTPS origin without path, credentials, or query.')
root=Path(__file__).resolve().parents[1]
path=root/'.env'
if not path.exists(): parser.error('Create private .env first.')
set_key(path,'MANGATRANS_SECURE_COOKIE','true')
set_key(path,'MANGATRANS_ORIGINS',args.origin)
print('HTTPS settings saved; credentials preserved. Restart MangaTrans to apply.')
