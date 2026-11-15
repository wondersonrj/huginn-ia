"""Desktop auth and identity negative tests; Windows TCP/SID is proven in installer CI."""
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import local_session as session


def client(origin='http://127.0.0.1:8000'):
    return TestClient(app, base_url='http://127.0.0.1:8000', client=('127.0.0.1', 54321), headers={'Origin': origin})


@pytest.fixture
def desktop(monkeypatch):
    monkeypatch.setattr(session, 'automatic', lambda: True)
    monkeypatch.setattr(session, 'same_user_peer', lambda request: True)
    monkeypatch.setenv('HUGINN_API_TOKEN', 'a' * 64)
    monkeypatch.setenv('HUGINN_WINTHOR_MODE', 'demo')
    monkeypatch.setenv('HUGINN_INSTALLATION_ID', 'installer-fixture')
    monkeypatch.setenv('HUGINN_RUNNING_VERSION', '0.2.0')
    monkeypatch.setenv('HUGINN_RUNNING_BUILD', 'test-build')
    session._sessions.clear()
    yield
    session._sessions.clear()


def test_cookie_session_never_returns_persistent_token(desktop):
    c = client()
    response = c.post('/api/local-session', content='{}', headers={'Content-Type': 'application/json'})
    assert response.status_code == 200
    assert 'a' * 64 not in response.text + response.headers['set-cookie']
    assert 'HttpOnly' in response.headers['set-cookie'] and 'SameSite=strict' in response.headers['set-cookie']
    assert 'Max-Age' not in response.headers['set-cookie'] and 'expires=' not in response.headers['set-cookie'].lower()
    assert c.post('/api/winthor/health', json={}).status_code == 200
    again = c.post('/api/local-session', content='{}', headers={'Content-Type': 'application/json'})
    assert again.status_code == 200 and len(session._sessions) == 1


def test_foreign_origin_cannot_bootstrap_or_use_cookie(desktop):
    c = client()
    c.post('/api/local-session', json={})
    assert c.post('/api/winthor/health', json={}, headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client('https://evil.example').post('/api/local-session', json={}).status_code == 403
    assert client().post('/api/winthor/health', json={}).status_code == 401


def test_different_windows_user_is_not_authorized_by_origin_only(desktop, monkeypatch):
    c = client()
    c.post('/api/local-session', json={})
    monkeypatch.setattr(session, 'same_user_peer', lambda request: False)
    assert c.post('/api/local-session', json={}).status_code == 403
    assert c.post('/api/winthor/health', json={}).status_code == 401


def test_tampered_cookie_and_expired_session_are_denied(desktop):
    c = client(); c.post('/api/local-session', json={})
    session._sessions.clear()
    assert c.post('/api/winthor/health', json={}).status_code == 401
    c.cookies.set(session.cookie_name(), 'forged')
    assert c.post('/api/winthor/health', json={}).status_code == 401


def test_identity_proof_binds_challenge_installation_version_port(desktop):
    challenge = 'c' * 64
    data = client().get('/api/local-instance?challenge=' + challenge).json()
    expected = hmac.new(b'a' * 64, f'{challenge}:installer-fixture:0.2.0:8000:test-build'.encode(), hashlib.sha256).hexdigest()
    assert data['proof'] == expected
    assert client().get('/api/local-instance?challenge=bad').status_code == 403


def test_stop_only_authenticates_this_supervisor(desktop, monkeypatch, tmp_path):
    monkeypatch.setenv('HUGINN_STATE_DIR', str(tmp_path))
    c = client()
    assert c.post('/api/local-stop', json={}).status_code == 403
    assert not (tmp_path / 'shutdown').exists()
    c.post('/api/local-session', json={})
    assert c.post('/api/local-stop', json={}).status_code == 200
    assert (tmp_path / 'shutdown').is_file()


def test_bootstrap_body_limit_and_no_secret_url(desktop):
    assert client().post('/api/local-session', content='x' * 4096, headers={'Content-Type': 'application/json'}).status_code == 422
    assert client().get('/api/local-session').status_code in {404, 405}


def load_desktop():
    spec = importlib.util.spec_from_file_location('desktop_fixture', Path(__file__).parents[2] / 'packaging/windows/desktop.py')
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def test_foreign_or_forged_service_never_opens_existing_instance(tmp_path):
    desktop = load_desktop()
    (tmp_path / 'state').mkdir()
    (tmp_path / 'state/instance.json').write_text(json.dumps({'port': 8000}))
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return json.dumps({'installation': desktop.installation_id(tmp_path), 'version': '0.2.0', 'port': 8000, 'proof': 'forged'}).encode()
    with patch.object(desktop.urllib.request, 'build_opener', return_value=SimpleNamespace(open=lambda *a, **k: Response())):
        assert desktop.verify_instance(tmp_path, '0.2.0', 'fixture-only-token') is None


def test_portable_legacy_does_not_enable_anonymous_session(monkeypatch):
    monkeypatch.setattr(session, 'automatic', lambda: False)
    assert client().post('/api/local-session', json={}).status_code == 404


@pytest.mark.parametrize('endpoint', ['testar', 'diagnostico'])
def test_legacy_diagnostic_valid_origin_is_not_a_server_error(desktop, endpoint):
    response = client().post('/api/oracle/' + endpoint, json={}, headers={'Authorization': 'Bearer ' + 'a' * 64})
    assert response.status_code == 422


@pytest.mark.parametrize('healthy', [True, False])
def test_installer_activation_preserves_previous_pointer_on_failure(tmp_path, healthy):
    spec = importlib.util.spec_from_file_location('installer_state_fixture', Path(__file__).parents[2] / 'packaging/windows/installer_state.py')
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    (tmp_path / 'state').mkdir()
    (tmp_path / 'bootstrap.json').write_text(json.dumps({'version': '0.2.1'}))
    pointer = tmp_path / 'state/current.json'; pointer.write_text(json.dumps({'version': '0.2.0'}))
    class Supervisor:
        def __init__(self, *args): self.socket = None
        def start(self, version):
            assert version == '0.2.1'
            if not healthy: raise RuntimeError('Synthetic unhealthy application')
        def stop(self): pass
    with patch('launcher.Supervisor', Supervisor):
        if healthy: value.activate(tmp_path)
        else:
            with pytest.raises(RuntimeError): value.activate(tmp_path)
    assert json.loads(pointer.read_text())['version'] == ('0.2.1' if healthy else '0.2.0')


def test_automatic_access_token_restart_corruption_rotation_without_profile_loss(tmp_path, monkeypatch):
    from app.connection_store import Store
    from app.windows_secrets import windows_identity, VaultError
    from test_connection_store import FakeProtector, FIELDS
    identity = windows_identity() if os.name == 'nt' else 'synthetic-user'
    store = Store(tmp_path / 'private', 'test-installation', identity, FakeProtector())
    profile = store.save(FIELDS, 'synthetic-oracle-credential')
    monkeypatch.setattr('app.connection_store.current_store', lambda: store)
    monkeypatch.setenv('HUGINN_STATE_DIR', 'test-original')
    desktop = load_desktop()
    token = desktop.access_token(tmp_path / 'installation', '0.2.0')
    assert len(token) == 64 and desktop.access_token(tmp_path / 'installation', '0.2.0') == token
    assert token.encode() not in (store.root / 'local-token.bin').read_bytes()
    (store.root / 'local-token.bin').write_bytes(b'corrupted')
    with pytest.raises(VaultError): desktop.access_token(tmp_path / 'installation', '0.2.0')
    replacement = desktop.access_token(tmp_path / 'installation', '0.2.0', reset=True)
    assert replacement != token
    assert store.listing()['profiles'][0]['id'] == profile['id']
    assert store.for_test(profile['id'], profile['revision'], 'TESTE').config.password == 'synthetic-oracle-credential'


def test_reset_requires_owned_session_and_preserves_profiles(desktop, monkeypatch, tmp_path):
    monkeypatch.setenv('HUGINN_STATE_DIR', str(tmp_path))
    assert client().post('/api/local-reset', json={}).status_code == 403
    c = client(); c.post('/api/local-session', json={})
    assert c.post('/api/local-reset', json={}).status_code == 200
    assert (tmp_path / 'reset-access').is_file() and (tmp_path / 'shutdown').is_file()
