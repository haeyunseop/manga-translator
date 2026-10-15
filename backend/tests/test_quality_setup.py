"""Credential preservation and local-process protocol tests, not model-quality tests."""
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import pytest
from dotenv import dotenv_values

def activation_module():
    path=Path(__file__).resolve().parents[2]/'scripts/activate_quality.py'
    spec=importlib.util.spec_from_file_location('activate_quality',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def test_activation_preserves_credentials_font_acl_and_bom(tmp_path):
    path=tmp_path/'.env'
    path.write_text('MANGATRANS_PASSWORD="검사용-비밀번호-${HOME}"\nMANGATRANS_SESSION_SECRET=private-test-key\nMANGATRANS_FONT="C:/한글/폰트.ttc"\nMANGATRANS_MODEL=nllb\nMANGATRANS_SECURE_COOKIE=true\n',encoding='utf-8-sig')
    path.chmod(0o600);inode=path.stat().st_ino
    before=dotenv_values(path,encoding='utf-8-sig',interpolate=False)
    activation_module().activate(path)
    after=dotenv_values(path,encoding='utf-8-sig',interpolate=False)
    assert after=={**before,'MANGATRANS_MODEL':'qwen','MANGATRANS_OCR':'manga'}
    assert path.read_bytes().startswith(b'\xef\xbb\xbf') and path.stat().st_ino==inode
    if os.name=='posix': assert stat.S_IMODE(path.stat().st_mode)==0o600

def test_incomplete_private_settings_are_not_activated(tmp_path):
    path=tmp_path/'.env';original=b'MANGATRANS_MODEL=nllb\n';path.write_bytes(original)
    with pytest.raises(RuntimeError):activation_module().activate(path)
    assert path.read_bytes()==original

@pytest.fixture
def local_protocol(tmp_path,monkeypatch):
    from backend import llama_translate as module
    model=tmp_path/'model';model.mkdir();(model/module.QWEN_FILE).write_bytes(b'protocol-test-only-not-real-weights')
    monkeypatch.setattr(module,'MODEL_PATH',model)
    monkeypatch.setattr(module,'DATA',tmp_path)
    monkeypatch.setattr(module,'runtime_binary',lambda:tmp_path/'test-executable')
    return module

def test_local_model_protocol_does_not_receive_app_secrets(local_protocol,monkeypatch):
    module=local_protocol
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY','test-only-cloud-secret')
    observed=[]
    def fake_run(args,**kwargs):
        observed.append(Path(args[args.index('-f')+1]))
        assert '明日は晴れる。' in observed[0].read_text(encoding='utf-8')
        assert 'MANGATRANS_PASSWORD' not in kwargs['env']
        assert 'AWS_SECRET_ACCESS_KEY' not in kwargs['env']
        assert '--offline' in args and '--no-conversation' in args
        return subprocess.CompletedProcess(args,0,'{"translation":"내일은 맑아."} [end of text]\n'.encode(),b'')
    monkeypatch.setattr(module.subprocess,'run',fake_run)
    assert module.translate('明日は晴れる。')=='내일은 맑아.'
    assert not observed[0].exists()

def test_incomplete_local_model_output_is_rejected(local_protocol,monkeypatch):
    monkeypatch.setattr(local_protocol.subprocess,'run',lambda args,**kwargs:subprocess.CompletedProcess(args,0,b'{"translation":"incomplete',b''))
    with pytest.raises(ValueError,match='원문을 유지'):
        local_protocol.translate('明日は晴れる。')
