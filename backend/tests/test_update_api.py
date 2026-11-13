import json
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app.main import app


def client(host='127.0.0.1', base='http://127.0.0.1:8000'):
    return TestClient(app, client=(host,1234), base_url=base)


def headers(origin='http://127.0.0.1:8000'):
    return {'Origin':origin, 'Content-Type':'application/json'}


def test_updates_disabled_without_supervisor(monkeypatch):
    monkeypatch.delenv('HUGINN_STATE_DIR', raising=False)
    assert client().get('/api/updates/status').json()['enabled'] is False
    assert client().post('/api/updates/apply', json={}, headers=headers()).status_code == 503


@pytest.mark.parametrize('host,origin,base', [('192.0.2.1','http://127.0.0.1:8000','http://127.0.0.1:8000'),('127.0.0.1','https://evil.example','http://127.0.0.1:8000'),('127.0.0.1','http://127.0.0.1:8000','http://evil.example')])
def test_update_csrf_and_rebinding_rejected(host,origin,base):
    assert client(host,base).post('/api/updates/apply',json={},headers=headers(origin)).status_code == 403


def test_only_fixed_queue_requests_no_urls_or_commands(tmp_path,monkeypatch):
    monkeypatch.setenv('HUGINN_STATE_DIR',str(tmp_path))
    monkeypatch.setenv('HUGINN_UPDATE_TOKEN','test-only-nonce')
    (tmp_path/'status.json').write_text(json.dumps(dict(enabled=True)))
    assert client().post('/api/updates/apply',json={'url':'https://evil.example'},headers=headers()).status_code == 422
    assert client().post('/api/updates/shell',json={},headers=headers()).status_code == 422
    assert client().post('/api/updates/check',json={},headers=headers()).status_code == 200
    assert json.loads((tmp_path/'request.json').read_text()) == dict(action='check',token='test-only-nonce')
    assert client().post('/api/updates/apply',json={},headers=headers()).status_code == 409


def test_malformed_update_json_rejected():
    assert client().post('/api/updates/apply',content=b'{bad',headers=headers()).status_code == 422
