import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from dotenv import dotenv_values

def test_initializer_preserves_private_settings_and_quotes_new_values(tmp_path):
    scripts=tmp_path/'scripts';scripts.mkdir()
    original=Path(__file__).resolve().parents[2]/'scripts/init_env.py'
    shutil.copyfile(original,scripts/'init_env.py')
    subprocess.run([sys.executable,str(scripts/'init_env.py'),'--font',str(tmp_path/'font folder/font.ttc')],capture_output=True,check=True)
    path=tmp_path/'.env'
    values=dotenv_values(path,interpolate=False)
    assert len(values['MANGATRANS_PASSWORD'])>=16
    assert values['MANGATRANS_FONT']==str(tmp_path/'font folder/font.ttc')
    if os.name=='posix': assert stat.S_IMODE(path.stat().st_mode)==0o600
    before=path.read_bytes()
    subprocess.run([sys.executable,str(scripts/'init_env.py')],capture_output=True,check=True)
    assert path.read_bytes()==before

def test_phone_configuration_changes_only_non_secret_settings(tmp_path):
    scripts=tmp_path/'scripts';scripts.mkdir()
    original=Path(__file__).resolve().parents[2]/'scripts/configure_phone.py'
    shutil.copyfile(original,scripts/'configure_phone.py')
    path=tmp_path/'.env'
    path.write_text('MANGATRANS_PASSWORD="test-only-${HOME}-literal"\nMANGATRANS_SESSION_SECRET=test-only-key\n')
    subprocess.run([sys.executable,str(scripts/'configure_phone.py'),'https://pc.example.ts.net'],capture_output=True,check=True)
    values=dotenv_values(path,interpolate=False)
    assert values['MANGATRANS_PASSWORD']=='test-only-${HOME}-literal'
    assert values['MANGATRANS_SESSION_SECRET']=='test-only-key'
    assert values['MANGATRANS_SECURE_COOKIE']=='true'
    assert values['MANGATRANS_ORIGINS']=='https://pc.example.ts.net'
    before=path.read_bytes()
    result=subprocess.run([sys.executable,str(scripts/'configure_phone.py'),'http://unsafe.example'],capture_output=True)
    assert result.returncode!=0 and path.read_bytes()==before
