"""Same suite runs on Windows CI and Linux. No Oracle connections."""
import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch
import zipfile

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'packaging/windows'))
from updater import (UpdateError, Updater, atomic_json, discover, exclusive_lock,
                     extract_payload, fetch, signed_manifest, trusted_url, version_tuple)


@pytest.fixture
def setup_update(tmp_path):
    key = Ed25519PrivateKey.generate()  # ephemeral test key, never distribution key
    public = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    config = dict(public_key=public, runtime_id='test-runtime', channel='teste', updates_enabled=True)
    engine = Updater(tmp_path, config)
    (tmp_path / 'versions/0.1.0').mkdir(parents=True)
    (tmp_path / 'versions/0.1.0/server.py').write_text('# synthetic old version')
    atomic_json(tmp_path / 'state/current.json', {'version': '0.1.0'})
    (tmp_path / 'state/preferences.json').write_text('{"theme":"dark"}')
    def artifact(version='0.2.0', bad=None):
        buffer = io.BytesIO()
        prefix = f'HUGINN-IA-Windows-x64/versions/{version}/'
        with zipfile.ZipFile(buffer, 'w') as z:
            for path in ['server.py', 'backend/app/main.py', 'frontend/dist/index.html']:
                z.writestr(prefix + path, '# synthetic test payload')
            z.writestr(prefix + 'version.json', json.dumps(dict(version=version, runtime_id='test-runtime', channel='teste')))
            if bad:
                info = zipfile.ZipInfo('placeholder')
                # Preserve adversarial raw names; Windows ZipInfo otherwise normalizes them on write.
                info.filename = bad
                info.orig_filename = bad
                z.writestr(info, 'unsafe')
        data = buffer.getvalue()
        signed = dict(version=version, channel='teste',
                      url=f'https://github.com/wondersonrj/huginn-ia/releases/download/v{version}/HUGINN-IA-Windows-x64.zip',
                      sha256=hashlib.sha256(data).hexdigest(), notes='Synthetic release', runtime_id='test-runtime', bootstrap_version=1)
        return sign(signed, key), data
    return engine, config, key, artifact


def sign(data, key):
    canonical = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
    return dict(signed=data, signature=base64.b64encode(key.sign(canonical)).decode())


def test_success_backup_and_preserves_configuration(setup_update):
    engine, _, _, artifact = setup_update
    manifest, data = artifact()
    events = []
    assert engine.apply(manifest, lambda: events.append('stop'), lambda v: events.append(v), lambda d: True, lambda url: data) == '0.2.0'
    assert events == ['stop', '0.2.0']
    assert engine.current() == '0.2.0'
    assert (engine.versions / '0.1.0/server.py').is_file()
    assert json.loads((engine.state / 'backup.json').read_text())['version'] == '0.1.0'
    assert (engine.state / 'preferences.json').read_text() == '{"theme":"dark"}'
    assert not (engine.state / 'journal.json').exists()


def test_failed_health_rolls_back(setup_update):
    engine, _, _, artifact = setup_update
    manifest, data = artifact()
    started = []
    def start(version):
        started.append(version)
        if version == '0.2.0':
            raise RuntimeError('health failed')
    with pytest.raises(UpdateError, match='anterior restaurada'):
        engine.apply(manifest, lambda: None, start, lambda d: True, lambda u: data)
    assert started == ['0.2.0', '0.1.0']
    assert engine.current() == '0.1.0'


def test_crash_journal_recovery(setup_update):
    engine, _, _, _ = setup_update
    atomic_json(engine.state / 'journal.json', {'old':'0.1.0', 'target':'0.2.0'})
    atomic_json(engine.state / 'current.json', {'version':'0.2.0'})
    assert engine.recover() is True
    assert engine.current() == '0.1.0'
    assert engine.recover() is False


def test_hash_mismatch_never_stops_app(setup_update):
    engine, _, _, artifact = setup_update
    manifest, _ = artifact()
    with patch('builtins.print'):
        with pytest.raises(UpdateError, match='SHA-256'):
            engine.apply(manifest, lambda: pytest.fail('must not stop'), lambda v: None, lambda d: True, lambda u: b'bad')
    assert engine.current() == '0.1.0'


def test_network_failure_preserves_app(setup_update):
    engine, _, _, artifact = setup_update
    manifest, _ = artifact()
    def unavailable(url):
        raise UpdateError('Rede indisponível')
    with pytest.raises(UpdateError, match='Rede'):
        engine.apply(manifest, lambda: pytest.fail('must not stop'), lambda v: None, lambda d: True, unavailable)
    assert engine.current() == '0.1.0'


def test_user_must_approve(setup_update):
    engine, _, _, artifact = setup_update
    manifest, _ = artifact()
    with pytest.raises(UpdateError, match='não aprovada'):
        engine.apply(manifest, lambda: None, lambda v: None, lambda d: False, lambda u: pytest.fail('must not download'))


def test_file_in_use_stops_activation(setup_update):
    engine, _, _, artifact = setup_update
    manifest, data = artifact()
    def busy():
        raise PermissionError('in use')
    with pytest.raises(UpdateError, match='em uso'):
        engine.apply(manifest, busy, lambda v: pytest.fail('must not start'), lambda d: True, lambda u: data)
    assert engine.current() == '0.1.0'


def test_concurrent_update_is_rejected(setup_update):
    engine, _, _, artifact = setup_update
    manifest, _ = artifact()
    with exclusive_lock(engine.state / 'update.lock'):
        with pytest.raises(UpdateError, match='andamento'):
            engine.apply(manifest, lambda: None, lambda v: None, lambda d: True)


@pytest.mark.parametrize('bad', ['https://evil.example/file.zip', 'http://github.com/a', 'https://github.com@evil.example/a', 'https://github.com:8443/a'])
def test_untrusted_origin(bad):
    with pytest.raises(UpdateError):
        trusted_url(bad)


@pytest.mark.parametrize('bad', ['1.2', 'v1.2.3', '../1.0.0', '01.2.3', '1.0.0-beta', '', None])
def test_semver_rejects_invalid_versions(bad):
    with pytest.raises(UpdateError):
        version_tuple(bad)


@pytest.mark.parametrize('field,value', [('url','https://evil.example/app.zip'), ('version','0.0.1'), ('channel','estavel'), ('runtime_id','other'), ('bootstrap_version',2)])
def test_signed_but_incompatible_release(setup_update, field, value):
    _, config, key, artifact = setup_update
    manifest, _ = artifact()
    manifest['signed'][field] = value
    envelope = sign(manifest['signed'], key)
    with pytest.raises(UpdateError):
        signed_manifest(envelope, config['public_key'], '0.1.0', 'teste', config['runtime_id'])


def test_tampered_manifest(setup_update):
    _, config, _, artifact = setup_update
    manifest, _ = artifact()
    manifest['signed']['notes'] = 'tampered'
    with pytest.raises(UpdateError, match='assinatura'):
        signed_manifest(manifest, config['public_key'], '0.1.0', 'teste', config['runtime_id'])


@pytest.mark.parametrize('bad', ['HUGINN-IA-Windows-x64/versions/0.2.0/../../evil', 'HUGINN-IA-Windows-x64/versions/0.2.0/CON', 'HUGINN-IA-Windows-x64/versions/0.2.0/file:stream', '/outside', 'HUGINN-IA-Windows-x64/versions/0.2.0/a\\evil'])
def test_unsafe_zip_rejected(setup_update, bad):
    engine, _, _, artifact = setup_update
    manifest, data = artifact(bad=bad)
    with pytest.raises(UpdateError, match='ZIP'):
        engine.apply(manifest, lambda: pytest.fail('must not stop'), lambda v: None, lambda d: True, lambda u: data)
    assert engine.current() == '0.1.0'


def test_disabled_by_default(setup_update):
    engine, config, _, artifact = setup_update
    config['updates_enabled'] = False
    with pytest.raises(UpdateError, match='desativado'):
        discover(config, '0.1.0')
    with pytest.raises(UpdateError, match='desativado'):
        engine.apply(artifact()[0], lambda: None, lambda v: None, lambda d: True)


def test_discovery_requires_signed_semantic_release(setup_update):
    _, config, _, artifact = setup_update
    manifest, _ = artifact()
    url='https://github.com/wondersonrj/huginn-ia/releases/download/v0.2.0/manifest.json'
    releases=[dict(tag_name='main',assets=[]),dict(tag_name='v0.2.0',draft=False,prerelease=True,assets=[dict(name='manifest.json',browser_download_url=url)])]
    def download(target, limit):
        return json.dumps(manifest if target == url else releases).encode()
    assert discover(config, '0.1.0', download) == manifest


def test_atomic_pointer_error_restores_old_version(setup_update):
    engine, _, _, artifact = setup_update
    manifest, data = artifact()
    from updater import atomic_json as original
    def fail_new_pointer(path, value):
        if Path(path).name == 'current.json' and value['version'] == '0.2.0':
            raise PermissionError('in use')
        original(path, value)
    with patch('updater.atomic_json', side_effect=fail_new_pointer):
        with pytest.raises(UpdateError, match='anterior restaurada'):
            engine.apply(manifest, lambda: None, lambda v: None, lambda d: True, lambda u: data)
    assert engine.current() == '0.1.0'


def test_download_network_error_is_sanitized():
    with patch('urllib.request.build_opener') as opener:
        opener.return_value.open.side_effect = OSError('sensitive-network-detail')
        with pytest.raises(UpdateError, match='Rede indisponível') as error:
            fetch('https://github.com/wondersonrj/huginn-ia/releases/download/v0.2.0/manifest.json')
    assert 'sensitive-network-detail' not in str(error.value)


def test_failed_rollback_keeps_journal_for_next_boot(setup_update):
    engine, _, _, artifact = setup_update
    manifest, data = artifact()
    def failed_start(version):
        raise RuntimeError('failed')
    with pytest.raises(UpdateError, match='Recuperação pendente'):
        engine.apply(manifest, lambda: None, failed_start, lambda d: True, lambda u: data)
    assert (engine.state/'journal.json').exists()
    assert engine.recover() is True
    assert engine.current() == '0.1.0'


@pytest.mark.skipif(sys.platform != 'win32', reason='Real Windows file-sharing test; Linux is not Windows evidence')
def test_windows_in_use_pointer_and_recovery(setup_update):
    import ctypes
    from ctypes import wintypes
    engine, _, _, artifact = setup_update
    manifest, data = artifact()
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    # Read-sharing allowed, deletion/replacement forbidden by a real OS handle.
    handle = create(str(engine.state/'current.json'),0x80000000,3,None,3,0,None)
    assert handle not in (None,ctypes.c_void_p(-1).value)
    try:
        with pytest.raises(UpdateError,match='Recuperação pendente'):
            engine.apply(manifest,lambda:None,lambda v:None,lambda d:True,lambda u:data)
        assert engine.current() == '0.1.0'
    finally:
        kernel.CloseHandle(handle)
    assert engine.recover() is True
    assert engine.current() == '0.1.0'
