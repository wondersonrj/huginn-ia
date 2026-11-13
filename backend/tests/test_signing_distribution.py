import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import zipfile

import pytest
from cryptography.hazmat.primitives import serialization

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'packaging/windows'))
import signing_keys
import release_manifest
from updater import discover

PASSWORD='Test-only long random passphrase 92756!'


def test_generation_is_encrypted_and_never_under_repo(tmp_path):
    private, fingerprint=signing_keys.generate(tmp_path/'custody','teste',PASSWORD)
    content=private.read_bytes()
    assert b'ENCRYPTED PRIVATE KEY' in content
    with pytest.raises(TypeError):
        serialization.load_pem_private_key(content,password=None)
    key=serialization.load_pem_private_key(content,password=PASSWORD.encode())
    public=base64.b64decode((private.parent/'teste.pub').read_text())
    assert len(public)==32 and fingerprint==hashlib.sha256(public).hexdigest()
    with pytest.raises(ValueError,match='fora do repositório'):
        signing_keys.generate(signing_keys.REPO/'never-create-private','teste',PASSWORD)
    with pytest.raises(FileExistsError):
        signing_keys.generate(private.parent,'teste',PASSWORD)


def test_short_passphrase_does_not_create_directory(tmp_path):
    with pytest.raises(ValueError):signing_keys.generate(tmp_path/'short','teste','weak')
    assert not (tmp_path/'short').exists()


def test_upload_only_stdin_no_secret_argv_or_disk(tmp_path,monkeypatch):
    private,_=signing_keys.generate(tmp_path/'custody','teste',PASSWORD)
    public=(private.parent/'teste.pub').read_text().strip()
    with patch('signing_keys.public_key',return_value=public),patch('signing_keys.subprocess.run') as run:
        run.return_value.returncode=0
        signing_keys.upload(private,'teste',PASSWORD)
    args=run.call_args.args[0]
    secret=run.call_args.kwargs['input']
    assert len(base64.b64decode(secret))==32
    assert secret.decode() not in ' '.join(args)
    assert 'windows-release-teste' in args
    assert b'ENCRYPTED PRIVATE KEY' in private.read_bytes()


def test_wrong_channel_never_uploads(tmp_path):
    private,_=signing_keys.generate(tmp_path/'custody','teste',PASSWORD)
    with patch('signing_keys.public_key',return_value='different'),patch('signing_keys.subprocess.run') as run:
        with pytest.raises(ValueError):signing_keys.upload(private,'estavel',PASSWORD)
        run.assert_not_called()


def test_failed_secret_upload_does_not_echo_cli_output(tmp_path):
    private,_=signing_keys.generate(tmp_path/'custody','teste',PASSWORD)
    public=(private.parent/'teste.pub').read_text().strip()
    with patch('signing_keys.public_key',return_value=public),patch('signing_keys.subprocess.run') as run:
        run.return_value.returncode=1
        run.return_value.stderr=b'NEVER-ECHO-THIS'
        with pytest.raises(RuntimeError) as error:signing_keys.upload(private,'teste',PASSWORD)
    assert 'NEVER-ECHO-THIS' not in str(error.value)


@pytest.mark.parametrize('channel,prerelease',[('teste',False),('estavel',True)])
def test_channel_discovery_never_crosses_release_class(channel,prerelease):
    config=dict(channel=channel,updates_enabled=True,public_key='not-consumed')
    calls=[]
    def download(url,limit):
        calls.append(url)
        return json.dumps([dict(tag_name='v1.0.0',draft=False,prerelease=prerelease,assets=[dict(name='manifest.json',browser_download_url='untrusted')])]).encode()
    assert discover(config,'0.1.0',download) is None
    assert len(calls)==1


def test_manifest_signer_checks_zip_identity(tmp_path,monkeypatch):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    key=Ed25519PrivateKey.generate()
    public=base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()
    monkeypatch.setenv('HUGINN_RELEASE_SIGNING_KEY',base64.b64encode(key.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption())).decode())
    public_file=tmp_path/'test.pub';public_file.write_text(public)
    notes=tmp_path/'notes.md';notes.write_text('synthetic')
    archive=tmp_path/'package.zip'
    runtime=hashlib.sha256(Path('packaging/windows/requirements.lock').read_bytes()).hexdigest()
    cfg=dict(version='0.2.1',channel='teste',public_key=public,runtime_id=runtime)
    with zipfile.ZipFile(archive,'w') as z:z.writestr('HUGINN-IA-Windows-x64/bootstrap.json',json.dumps(cfg))
    args=['release_manifest.py','--version','0.2.1','--channel','teste','--notes',str(notes),'--zip',str(archive),'--public-key-file',str(public_file)]
    with patch.object(sys,'argv',args):release_manifest.main()
    envelope=json.loads((tmp_path/'manifest.json').read_text())
    from updater import signed_manifest
    assert signed_manifest(envelope,public,'0.2.0','teste',runtime)['sha256']==hashlib.sha256(archive.read_bytes()).hexdigest()
    cfg['channel']='estavel'
    with zipfile.ZipFile(archive,'w') as z:z.writestr('HUGINN-IA-Windows-x64/bootstrap.json',json.dumps(cfg))
    with patch.object(sys,'argv',args),pytest.raises(SystemExit,match='Identidade'):release_manifest.main()
