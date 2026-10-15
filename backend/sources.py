"""Explicit opt-in direct-image/manifest adapter, with DNS pinning and no redirects."""
import http.client
import ipaddress
import json
import os
import socket
import ssl
from urllib.parse import urlsplit
from .config import MAX_IMAGE_BYTES, MAX_PAGES

class SourceError(ValueError):
    pass

def allowed_hosts():
    return {h.strip().lower() for h in os.getenv('MANGATRANS_ALLOWED_HOSTS','').split(',') if h.strip()}

def validate_url(url,hosts=None,resolver=socket.getaddrinfo):
    try:
        u=urlsplit(url)
        port=u.port
    except ValueError as exc:
        raise SourceError('올바른 HTTPS 주소를 입력하세요.') from exc
    if u.scheme!='https' or not u.hostname or u.username or u.password or port not in (None,443) or u.fragment:
        raise SourceError('인증정보가 없는 HTTPS 주소(443 포트)만 지원합니다.')
    host=u.hostname.lower()
    if host not in (allowed_hosts() if hosts is None else hosts):
        raise SourceError('지원하지 않는 사이트입니다. 본인 소유 또는 이용 허락을 받은 이미지/매니페스트 호스트를 설정에 등록하세요. 일반 만화 사이트·로그인 페이지는 지원하지 않습니다.')
    try:
        addresses={r[4][0] for r in resolver(host,443,type=socket.SOCK_STREAM)}
    except OSError as exc:
        raise SourceError('사이트의 DNS 주소를 확인할 수 없습니다.') from exc
    if not addresses or any(not ipaddress.ip_address(a).is_global or ipaddress.ip_address(a).is_multicast or ipaddress.ip_address(a).is_reserved for a in addresses):
        raise SourceError('내부망·로컬·예약 주소에는 접근할 수 없습니다.')
    return u,sorted(addresses)[0]

class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self,host,address):
        super().__init__(host,timeout=25,context=ssl.create_default_context())
        self.address=address
    def connect(self):
        # Connect to the already validated IP while validating TLS/SNI for original hostname.
        sock=socket.create_connection((self.address,443),timeout=self.timeout)
        try: self.sock=self._context.wrap_socket(sock,server_hostname=self.host)
        except Exception:
            sock.close(); raise

def fetch_public(url,limit=MAX_IMAGE_BYTES):
    u,address=validate_url(url)
    conn=PinnedHTTPS(u.hostname,address)
    try:
        path=u.path or '/'
        if u.query: path+='?'+u.query
        conn.request('GET',path,headers={'User-Agent':'MangaTrans/0.1 (personal authorized-image reader)','Accept':'image/png,image/jpeg,image/webp,application/json','Accept-Encoding':'identity'})
        response=conn.getresponse()
        if response.status in (301,302,303,307,308):
            raise SourceError('리디렉션은 지원하지 않습니다. 허가된 파일의 최종 HTTPS 주소를 사용하세요.')
        if response.status!=200:
            raise SourceError(f'원본 서버가 HTTP {response.status}를 반환했습니다. 로그인·접근 제한을 우회하지 않습니다.')
        data=response.read(limit+1)
        if len(data)>limit: raise SourceError('원격 파일이 크기 제한을 초과했습니다.')
        return data,response.getheader('Content-Type','').split(';')[0]
    except (OSError, http.client.HTTPException) as exc:
        raise SourceError('원본 서버에 안전하게 연결하지 못했습니다.') from exc
    finally: conn.close()

def resolve_source(url):
    data,kind=fetch_public(url)
    if kind in {'image/jpeg','image/png','image/webp'}:
        return {'title':'URL에서 불러온 페이지','pages':[url]},data
    if kind!='application/json':
        raise SourceError('지원 형식은 이미지 직접 URL 또는 MangaTrans JSON 매니페스트입니다. 웹페이지 HTML은 지원하지 않습니다.')
    try: manifest=json.loads(data)
    except (ValueError,UnicodeDecodeError) as exc:
        raise SourceError('JSON 매니페스트를 읽을 수 없습니다.') from exc
    if not isinstance(manifest,dict): raise SourceError('매니페스트는 JSON 객체여야 합니다.')
    pages=manifest.get('pages')
    if not isinstance(pages,list) or not 1<=len(pages)<=MAX_PAGES or not all(isinstance(p,str) for p in pages):
        raise SourceError(f'매니페스트 pages에는 1~{MAX_PAGES}개의 이미지 URL이 필요합니다.')
    if not isinstance(manifest.get('license'),str) or not manifest['license'].strip():
        raise SourceError('매니페스트에 license(이용 허락·권리 정보)가 필요합니다.')
    for page in pages: validate_url(page)
    return {'title':str(manifest.get('title','불러온 작품'))[:100],'pages':pages},None
