import json
import socket
import pytest
from backend import sources

def dns(address):
    return lambda *a,**k:[(socket.AF_INET,socket.SOCK_STREAM,6,'',(address,443))]

@pytest.mark.parametrize('address',['127.0.0.1','10.0.0.1','169.254.169.254','192.168.1.1','::1','::ffff:127.0.0.1','100.64.0.1','0.0.0.0','224.0.0.1'])
def test_private_and_reserved_dns_denied(address):
    with pytest.raises(sources.SourceError):
        sources.validate_url('https://owned.example/page.png',{'owned.example'},dns(address))

@pytest.mark.parametrize('url',['http://owned.example/x','https://owned.example:8443/x','https://user:secret@owned.example/x','https://evil.example/x','https://owned.example/x#fragment','file:///etc/passwd','https://owned.example:bad/x'])
def test_unsupported_urls_denied(url):
    with pytest.raises(sources.SourceError): sources.validate_url(url,{'owned.example'},dns('93.184.216.34'))

def test_public_address_returned_for_connection_pinning():
    u,ip=sources.validate_url('https://owned.example/page.png',{'owned.example'},dns('93.184.216.34'))
    assert ip=='93.184.216.34' and u.hostname=='owned.example'

def test_mixed_public_and_private_records_denied():
    def mixed(*a,**k): return dns('93.184.216.34')()+dns('127.0.0.1')()
    with pytest.raises(sources.SourceError): sources.validate_url('https://owned.example/x',{'owned.example'},mixed)

def test_manifest_validates_every_page(monkeypatch):
    body={'title':'authorized original','license':'Self authored','pages':['https://owned.example/1.png','https://owned.example/2.png']}
    monkeypatch.setattr(sources,'fetch_public',lambda url:(json.dumps(body).encode(),'application/json'))
    seen=[]
    monkeypatch.setattr(sources,'validate_url',lambda url:seen.append(url))
    manifest,first=sources.resolve_source('https://owned.example/chapter.json')
    assert manifest['pages']==seen and len(seen)==2 and first is None

@pytest.mark.parametrize('body',[{},[],{'pages':[],'license':'CC0'},{'pages':['https://owned.example/x']},{'pages':['https://owned.example/x']*21,'license':'CC0'}])
def test_bad_manifest_denied(monkeypatch,body):
    monkeypatch.setattr(sources,'fetch_public',lambda url:(json.dumps(body).encode(),'application/json'))
    with pytest.raises(sources.SourceError): sources.resolve_source('https://owned.example/chapter.json')

def test_redirect_is_not_followed(monkeypatch):
    class Response:
        status=302
    class Connection:
        def __init__(self,*a): pass
        def request(self,*a,**k): pass
        def getresponse(self): return Response()
        def close(self): pass
    from urllib.parse import urlsplit
    monkeypatch.setattr(sources,'validate_url',lambda _: (urlsplit('https://owned.example/x'),'93.184.216.34'))
    monkeypatch.setattr(sources,'PinnedHTTPS',Connection)
    with pytest.raises(sources.SourceError,match='리디렉션'): sources.fetch_public('https://owned.example/x')
