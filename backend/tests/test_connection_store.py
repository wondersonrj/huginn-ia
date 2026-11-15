"""DPAPI integration is native on Windows; portable tests use an injected test-only cipher."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock, patch
import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi.testclient import TestClient
from app.main import app
from app import connection_store as module
from app.connection_store import Store, Conflict, SelectionRequired
from app.windows_secrets import DPAPI, VaultError, windows_identity
from app.winthor import Settings, search

PASSWORD = 'synthetic-only-password-21'
TOKEN = 'synthetic-token-' + 'x' * 40
FIELDS = dict(name='Homologação', environment='TESTE', host='synthetic.test', port=1521,
              service='SYNTHETIC', user='synthetic_reader', owner='WINT')


class FakeProtector:
    def __init__(self, key=b'a' * 32):
        self.cipher = AESGCM(key)

    def protect(self, value, entropy):
        nonce = os.urandom(12)
        return nonce + self.cipher.encrypt(nonce, value, entropy)

    def unprotect(self, value, entropy):
        try:
            return self.cipher.decrypt(value[:12], value[12:], entropy)
        except Exception:
            raise VaultError('Synthetic cipher rejected') from None


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / 'private', 'synthetic-installation', windows_identity() if os.name == 'nt' else 'synthetic-user', FakeProtector())


def reference(profile):
    return dict(identifier=profile['id'], revision=profile['revision'])


def selected(store):
    profile = store.save(FIELDS, PASSWORD)
    store.choose(**reference(profile), confirmed='TESTE')
    return profile


def test_save_restart_select_and_never_serialize_password(store):
    profile = selected(store)
    assert profile['password_saved'] and 'password' not in profile and 'secret_id' not in profile
    restarted = Store(store.root, store.installation, store.identity, store.protector)
    with pytest.raises(SelectionRequired):
        restarted.selected()
    listing = restarted.listing()
    assert listing['active'] is None and listing['profiles'][0]['password_saved']
    restarted.choose(**reference(profile), confirmed='TESTE')
    assert restarted.selected(profile['id'], profile['revision']).config.password == PASSWORD
    for path in store.root.iterdir():
        assert PASSWORD.encode() not in path.read_bytes()
    assert PASSWORD not in json.dumps(listing)
    assert (store.root / 'profiles.json').exists()
    assert len(list(store.root.glob('*.dpapi'))) == 1


def test_explicit_production_confirmation_and_no_connection_on_select(store):
    profile = store.save(FIELDS | dict(name='Produção fictícia', environment='PRODUCAO'), PASSWORD)
    with patch('oracledb.connect') as connect:
        with pytest.raises(Conflict):
            store.choose(**reference(profile), confirmed='TESTE')
        store.choose(**reference(profile), confirmed='PRODUCAO')
    connect.assert_not_called()
    assert store.listing()['active']['environment'] == 'PRODUCAO'


def test_no_password_cannot_select(store):
    profile = store.save(FIELDS)
    assert not profile['password_saved']
    with pytest.raises(VaultError):
        store.choose(**reference(profile), confirmed='TESTE')
    assert store.active is None


def test_edit_preserves_or_replaces_password_and_invalidates_selection(store):
    profile = selected(store)
    edited = store.save(FIELDS | dict(host='edited.test'), **reference(profile))
    assert store.active is None
    with pytest.raises(SelectionRequired): store.selected(profile['id'], profile['revision'])
    store.choose(**reference(edited), confirmed='TESTE')
    assert store.selected(edited['id'], edited['revision']).config.password == PASSWORD
    updated = store.save(FIELDS, 'replacement-synthetic', **reference(edited))
    assert len(list(store.root.glob('*.dpapi'))) == 1
    store.choose(**reference(updated), confirmed='TESTE')
    assert store.selected(updated['id'], updated['revision']).config.password == 'replacement-synthetic'


def test_stale_edit_delete_and_query_never_switch_target(store):
    first = selected(store)
    second = store.save(FIELDS | dict(name='Outra fictícia'), PASSWORD)
    store.choose(**reference(second), confirmed='TESTE')
    with pytest.raises(SelectionRequired): store.selected(first['id'], first['revision'])
    edited = store.save(FIELDS | dict(name='Nova'), **reference(first))
    with pytest.raises(Conflict): store.save(FIELDS, **reference(first))
    with pytest.raises(Conflict): store.remove(**reference(first))
    assert edited['revision'] != first['revision']


def test_password_removal_then_profile_removal_leave_no_fallback(store):
    profile = selected(store)
    store.remove(**reference(profile), password_only=True)
    assert not list(store.root.glob('*.dpapi'))
    profile = store.listing()['profiles'][0]
    assert not profile['password_saved']
    with pytest.raises(VaultError): store.choose(**reference(profile), confirmed='TESTE')
    store.remove(**reference(profile))
    assert store.listing()['profiles'] == []
    with pytest.raises(SelectionRequired): store.selected()
    restarted = Store(store.root, store.installation, store.identity, store.protector)
    with pytest.raises(SelectionRequired): restarted.selected()
    restarted.environment()
    assert restarted.selected() is None


@pytest.mark.parametrize('damage', ['blob_missing', 'blob_corrupt', 'json_corrupt', 'metadata_missing', 'foreign_identity', 'foreign_installation'])
def test_vault_corruption_and_foreign_identity_fail_closed(store, damage):
    profile = selected(store)
    blob = next(store.root.glob('*.dpapi')); metadata = store.root / 'profiles.json'
    if damage == 'blob_missing': blob.unlink()
    elif damage == 'blob_corrupt': blob.write_bytes(b'corrupted')
    elif damage == 'json_corrupt': metadata.write_text('{broken')
    elif damage == 'metadata_missing': metadata.unlink()
    else:
        data = json.loads(metadata.read_text())
        data['identity' if damage == 'foreign_identity' else 'installation'] = 'foreign'
        metadata.write_text(json.dumps(data))
    with pytest.raises(VaultError): store.selected(profile['id'], profile['revision'])


def test_wrong_user_cipher_and_install_entropy_cannot_decrypt(store):
    profile = selected(store)
    other = Store(store.root, store.installation, store.identity, FakeProtector(b'b' * 32))
    with pytest.raises(VaultError): other.for_test(**reference(profile), confirmed='TESTE')
    original = store.entropy
    store.entropy = lambda p: hashlib.sha256(original(p)).digest()
    with pytest.raises(VaultError): store.selected(profile['id'], profile['revision'])


def test_duplicates_and_identifier_injection_rejected(store):
    selected(store)
    with pytest.raises(ValueError): store.save(FIELDS | dict(name=' homologação '), PASSWORD)
    for change in [dict(owner='WINT;DROP'), dict(host='host;invalid'), dict(port=True)]:
        with pytest.raises(ValueError): store.save(FIELDS | change, PASSWORD)


def test_failed_atomic_metadata_write_preserves_original_credential(store, monkeypatch):
    profile = selected(store)
    original = (store.root / 'profiles.json').read_bytes()
    monkeypatch.setattr(store, 'write', lambda data: (_ for _ in ()).throw(OSError('synthetic failure')))
    with pytest.raises(OSError): store.save(FIELDS, 'new-synthetic', **reference(profile))
    assert (store.root / 'profiles.json').read_bytes() == original
    assert len(list(store.root.glob('*.dpapi'))) == 1
    assert store.selected(profile['id'], profile['revision']).config.password == PASSWORD


@pytest.mark.skipif(os.name == 'nt', reason='POSIX symlink scenario; Windows DACL/DPAPI tested separately')
def test_symlink_and_private_permissions(store, tmp_path):
    store.prepare()
    assert store.root.stat().st_mode & 0o777 == 0o700
    other = tmp_path / 'other'; other.write_text('unchanged')
    (store.root / 'profiles.json').symlink_to(other)
    with pytest.raises(VaultError): store.listing()
    assert other.read_text() == 'unchanged'


@pytest.fixture
def api_store(store, monkeypatch):
    monkeypatch.setattr('app.connections_api.current_store', lambda: store)
    monkeypatch.setattr('app.winthor.current_store', lambda: store)
    monkeypatch.setenv('HUGINN_API_TOKEN', TOKEN)
    monkeypatch.setenv('HUGINN_WINTHOR_MODE', 'demo')
    return store


def client(token=TOKEN, base='http://127.0.0.1:8000', host='127.0.0.1'):
    return TestClient(app, base_url=base, client=(host, 1234), headers={'Authorization': 'Bearer ' + token})


def test_api_create_edit_list_remove_never_returns_secrets(api_store):
    response = client().post('/api/connections/save', json=FIELDS | dict(password=PASSWORD))
    assert response.status_code == 200 and PASSWORD not in response.text
    profile = response.json()['profile']
    listing = client().post('/api/connections/list', json={})
    assert PASSWORD not in listing.text and 'secret_id' not in listing.text
    assert listing.headers['cache-control'] == 'no-store'
    ref = dict(id=profile['id'], revision=profile['revision'])
    assert client().post('/api/connections/remove-password', json=ref).status_code == 200
    profile = client().post('/api/connections/list', json={}).json()['profiles'][0]
    assert not profile['password_saved']
    assert client().post('/api/connections/delete', json=dict(id=profile['id'], revision=profile['revision'])).status_code == 200


@pytest.mark.parametrize('action', ['list', 'save', 'select', 'delete', 'remove-password', 'test', 'diagnostic', 'environment', 'import-environment'])
def test_all_config_operations_require_authorization(api_store, action):
    assert client(token='wrong').post('/api/connections/' + action, json={}).status_code == 401
    assert not api_store.root.exists()


@pytest.mark.parametrize('base,host,origin', [('http://evil.test:8000', '127.0.0.1', None),
    ('http://127.0.0.1:8000', '192.0.2.1', None), ('http://127.0.0.1:8000', '127.0.0.1', 'https://evil.test')])
def test_config_rejects_remote_origin_and_rebinding(api_store, base, host, origin):
    response = client(base=base, host=host).post('/api/connections/list', json={}, headers={'Origin': origin} if origin else {})
    assert response.status_code == 403 and not api_store.root.exists()


def test_point_check_uses_only_dual_and_does_not_select(api_store):
    profile = api_store.save(FIELDS, PASSWORD)
    con = MagicMock(); cur = con.cursor.return_value.__enter__.return_value; cur.fetchone.return_value = (1,)
    with patch('oracledb.connect', return_value=con):
        result = client().post('/api/connections/test', json=dict(id=profile['id'], revision=profile['revision'], confirm_environment='TESTE'))
    assert result.status_code == 200 and result.json()['persistent_session'] is False
    assert [c.args[0] for c in cur.execute.call_args_list] == ['SET TRANSACTION READ ONLY', 'SELECT 1 FROM DUAL']
    con.close.assert_called_once(); con.commit.assert_not_called()
    assert api_store.active is None


def test_query_uses_selected_saved_profile_with_readonly_metadata_and_binds(api_store):
    profile = selected(api_store)
    con = MagicMock(); cur = con.cursor.return_value.__enter__.return_value
    cur.fetchmany.side_effect = [[('CODPROD', 'NUMBER'), ('DESCRICAO', 'VARCHAR2')], [(1, 'Synthetic product')]]
    with patch('oracledb.connect', return_value=con) as connect:
        response = client().post('/api/winthor/produtos', json={'connection_id': profile['id'], 'connection_revision': profile['revision'], 'codigo': 1})
    assert response.status_code == 200 and response.json()['connection']['id'] == profile['id']
    assert connect.call_args.kwargs['user'] == FIELDS['user']
    assert connect.call_args.kwargs['password'] == PASSWORD
    assert PASSWORD not in response.text
    assert cur.execute.call_args_list[0].args[0] == 'SET TRANSACTION READ ONLY'
    assert cur.execute.call_args.args[1]['codigo'] == 1
    con.close.assert_called_once(); con.commit.assert_not_called()
    with patch('oracledb.connect') as connect:
        assert client().post('/api/winthor/health', json={}).status_code == 409
    connect.assert_not_called()


def test_corrupt_password_query_blocks_without_environment_fallback(api_store):
    profile = selected(api_store)
    next(api_store.root.glob('*.dpapi')).write_bytes(b'corrupt')
    response = client().post('/api/winthor/produtos', json={'connection_id': profile['id'], 'connection_revision': profile['revision']})
    assert response.status_code == 503
    assert 'simulado' not in response.text and PASSWORD not in response.text


def test_migration_reads_secret_only_on_server_and_requires_selection(api_store, monkeypatch):
    for key, value in {'MODE': 'oracle', 'HOST': FIELDS['host'], 'PORT': '1521', 'SERVICE': FIELDS['service'],
                       'USER': FIELDS['user'], 'PASSWORD': PASSWORD, 'OWNER': 'WINT'}.items():
        monkeypatch.setenv('HUGINN_WINTHOR_MODE' if key == 'MODE' else 'HUGINN_ORACLE_' + key, value)
    response = client().post('/api/connections/import-environment', json={'name': 'Migrada', 'environment': 'TESTE'})
    assert response.status_code == 200 and PASSWORD not in response.text
    assert api_store.active is None
    with pytest.raises(SelectionRequired): Settings.load()
    ref = response.json()['profile']
    api_store.choose(**reference(ref), confirmed='TESTE')
    assert Settings.load(ref['id'], ref['revision']).oracle.password == PASSWORD


def test_api_errors_and_audit_never_include_password(api_store, caplog):
    import logging
    with caplog.at_level(logging.INFO):
        a = client().post('/api/connections/save', json=FIELDS | {'password': PASSWORD, 'sql': 'DROP TABLE'})
        profile = api_store.save(FIELDS, PASSWORD)
        with patch('app.connections_api.check_connection', side_effect=RuntimeError(PASSWORD)):
            b = client().post('/api/connections/test', json=dict(id=profile['id'], revision=profile['revision'], confirm_environment='TESTE'))
    assert a.status_code == 422 and b.status_code == 502
    assert PASSWORD not in a.text + b.text + caplog.text
    assert FIELDS['host'] not in caplog.text and TOKEN not in caplog.text


@pytest.mark.skipif(os.name != 'nt', reason='Native DPAPI/Windows ACL proof requires Windows CI')
def test_native_dpapi_restart_acl_and_wrong_entropy(tmp_path):
    sid = windows_identity()
    store = Store(tmp_path / 'native-private', 'native-test-installation', sid, DPAPI())
    profile = selected(store)
    blob = next(store.root.glob('*.dpapi'))
    protected = blob.read_bytes()
    assert PASSWORD.encode() not in protected
    with pytest.raises(VaultError): DPAPI().unprotect(protected, b'wrong-installation')
    # Independent process, same Windows user, never prints a decrypted credential.
    script = '''import sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from app.connection_store import Store
from app.windows_secrets import DPAPI, windows_identity
s=Store(Path(sys.argv[2]), 'native-test-installation', windows_identity(), DPAPI())
p=s.listing()['profiles'][0]
assert s.listing()['active'] is None
s.choose(p['id'],p['revision'],'TESTE')
assert s.selected(p['id'],p['revision']).config.password == sys.stdin.read()
print('NATIVE-RESTART-OK')'''
    result = subprocess.run([sys.executable, '-I', '-c', script, str(Path(__file__).parents[1]), str(store.root)],
                            input=PASSWORD, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and result.stdout.strip() == 'NATIVE-RESTART-OK'
    # Inspect the live DACL through WinAPI, not locale/alias/BOM-dependent text.
    import ctypes
    from ctypes import wintypes
    advapi = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    advapi.GetNamedSecurityInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p)]
    advapi.GetNamedSecurityInfoW.restype = wintypes.DWORD
    advapi.GetSecurityDescriptorControl.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.WORD), ctypes.POINTER(wintypes.DWORD)]
    advapi.GetSecurityDescriptorControl.restype = wintypes.BOOL
    advapi.GetAclInformation.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD]
    advapi.GetAclInformation.restype = wintypes.BOOL
    advapi.GetAce.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)]
    advapi.GetAce.restype = wintypes.BOOL
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    class AclSize(ctypes.Structure):
        _fields_ = [('count', wintypes.DWORD), ('used', wintypes.DWORD), ('free', wintypes.DWORD)]
    for path in [store.root, *store.root.iterdir()]:
        descriptor, acl = ctypes.c_void_p(), ctypes.c_void_p()
        assert advapi.GetNamedSecurityInfoW(str(path), 1, 4, None, None, ctypes.byref(acl), None, ctypes.byref(descriptor)) == 0
        try:
            control, revision = wintypes.WORD(), wintypes.DWORD()
            assert advapi.GetSecurityDescriptorControl(descriptor, ctypes.byref(control), ctypes.byref(revision))
            assert control.value & 0x1000  # SE_DACL_PROTECTED
            info = AclSize()
            assert advapi.GetAclInformation(acl, ctypes.byref(info), ctypes.sizeof(info), 2)
            assert info.count == 2
            allowed = set()
            for index in range(info.count):
                ace = ctypes.c_void_p()
                assert advapi.GetAce(acl, index, ctypes.byref(ace))
                assert ctypes.c_ubyte.from_address(ace.value).value == 0  # ACCESS_ALLOWED_ACE_TYPE
                assert ctypes.c_uint32.from_address(ace.value + 4).value & 0x1f01ff == 0x1f01ff
                text = ctypes.c_void_p()
                assert advapi.ConvertSidToStringSidW(ace.value + 8, ctypes.byref(text))
                try:
                    allowed.add(ctypes.wstring_at(text))
                finally:
                    kernel.LocalFree(text)
            assert allowed == {sid, 'S-1-5-18'}
        finally:
            kernel.LocalFree(descriptor)


def test_credential_creation_failure_is_atomic(store, monkeypatch):
    store.save(FIELDS, PASSWORD)
    original = (store.root / 'profiles.json').read_bytes()
    monkeypatch.setattr(store.protector, 'protect', lambda *args: (_ for _ in ()).throw(VaultError('native rejected')))
    with pytest.raises(VaultError): store.save(FIELDS | dict(name='Another'), PASSWORD)
    assert (store.root / 'profiles.json').read_bytes() == original
    assert len(list(store.root.glob('*.dpapi'))) == 1


def test_no_windows_has_no_persistence_fallback(monkeypatch):
    monkeypatch.setattr('app.connections_api.current_store', lambda: None)
    monkeypatch.setenv('HUGINN_API_TOKEN', TOKEN)
    assert client().post('/api/connections/list', json={}).json()['supported'] is False
    assert client().post('/api/connections/save', json=FIELDS | dict(password=PASSWORD)).status_code == 503


def test_managed_store_does_not_silently_fallback_after_restart(api_store):
    profile = selected(api_store)
    restarted = Store(api_store.root, api_store.installation, api_store.identity, api_store.protector)
    with patch('app.winthor.current_store', return_value=restarted), patch('oracledb.connect') as connect:
        assert client().post('/api/winthor/health', json={}).status_code == 409
    connect.assert_not_called()


def test_point_check_failure_closes_and_does_not_select(api_store):
    profile = api_store.save(FIELDS, PASSWORD)
    con = MagicMock(); cur = con.cursor.return_value.__enter__.return_value
    cur.fetchone.side_effect = RuntimeError(PASSWORD)
    with patch('oracledb.connect', return_value=con):
        response = client().post('/api/connections/test', json=dict(id=profile['id'], revision=profile['revision'], confirm_environment='TESTE'))
    assert response.status_code == 502 and PASSWORD not in response.text
    con.close.assert_called_once(); con.commit.assert_not_called()
    assert api_store.active is None


def test_stale_point_test_result_is_not_attached_to_edited_profile(store):
    profile = selected(store)
    changed = store.save(FIELDS, **reference(profile))
    store.tests[profile['id']] = dict(ok=True, revision=profile['revision'], checked_at='synthetic')
    assert store.listing()['profiles'][0]['last_test'] is None
    assert changed['revision'] != profile['revision']


def test_store_rejects_password_inside_metadata(store):
    with pytest.raises(ValueError): store.save(FIELDS | {'password': PASSWORD})
    assert not store.root.exists()


def test_configuration_does_not_expose_export_or_password_route(api_store):
    profile = selected(api_store)
    response = client().post('/api/connections/export', json={})
    assert response.status_code in {404, 405} and PASSWORD not in response.text
    assert client().get('/api/connections/' + profile['id'] + '/password').status_code == 404


def test_bad_confirmation_does_not_enable_environment_fallback(api_store):
    selected(api_store)
    response = client().post('/api/connections/environment', json={'confirm': 'anything'})
    assert response.status_code == 422 and api_store.fallback is False


def test_saved_supplier_query_keeps_schema_validation_and_binds(api_store):
    profile = selected(api_store)
    con = MagicMock(); cur = con.cursor.return_value.__enter__.return_value
    cur.fetchmany.side_effect = [[('CODFORNEC', 'NUMBER'), ('FORNECEDOR', 'VARCHAR2')], [(3, 'Synthetic supplier')]]
    with patch('oracledb.connect', return_value=con):
        response = client().post('/api/winthor/fornecedores', json={'connection_id': profile['id'], 'connection_revision': profile['revision'], 'codigo': 3})
    assert response.status_code == 200 and response.json()['itens'][0]['codigo'] == '3'
    assert cur.execute.call_args_list[1].args[1]['table_name'] == 'PCFORNEC'
    assert cur.execute.call_args.args[1]['codigo'] == 3
    con.commit.assert_not_called(); con.close.assert_called_once()


def test_packaging_excludes_even_accidental_vault_copies(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location('connection_build', Path(__file__).parents[2] / 'packaging/windows/build.py')
    build = importlib.util.module_from_spec(spec); spec.loader.exec_module(build)
    source = tmp_path / 'source'; source.mkdir()
    (source / '__init__.py').write_text('# distributable application code')
    private = source / 'accidental-copy'; private.mkdir()
    for name in ['profiles.json', 'fixture.dpapi', '.env', 'interrupted.tmp']:
        (private / name).write_bytes(b'synthetic-private-marker')
    build.copy_backend(source, tmp_path / 'destination')
    assert (tmp_path / 'destination/__init__.py').is_file()
    assert not any(p.is_file() for p in (tmp_path / 'destination/accidental-copy').rglob('*'))


def test_saved_metadata_diagnostic_keeps_password_on_server(api_store):
    from app.schema_diagnostic import METADATA_SQL
    profile = api_store.save(FIELDS, PASSWORD)
    con = MagicMock(); cursor = con.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [('WINT', 'PCPRODUT', 'CODPROD', 'NUMBER')]
    with patch('oracledb.connect', return_value=con):
        result = client().post('/api/connections/diagnostic', json=dict(id=profile['id'], revision=profile['revision'], confirm_environment='TESTE'))
    assert result.status_code == 200 and PASSWORD not in result.text
    assert result.json()['tabelas'][0]['proprietario'] == 'WINT'
    assert [call.args[0] for call in cursor.execute.call_args_list] == ['SET TRANSACTION READ ONLY', METADATA_SQL]
    assert api_store.active is None
    con.close.assert_called_once(); con.commit.assert_not_called()


def test_saved_metadata_diagnostic_requires_production_confirmation_and_hides_errors(api_store):
    profile = api_store.save(FIELDS | dict(environment='PRODUCAO'), PASSWORD)
    ref = dict(id=profile['id'], revision=profile['revision'])
    with patch('app.connections_api.inspect_schema') as inspect:
        assert client().post('/api/connections/diagnostic', json=ref).status_code == 409
        inspect.assert_not_called()
    with patch('app.connections_api.inspect_schema', side_effect=RuntimeError(PASSWORD)):
        result = client().post('/api/connections/diagnostic', json=ref | dict(confirm_environment='PRODUCAO'))
    assert result.status_code == 502 and PASSWORD not in result.text
    assert client().post('/api/connections/diagnostic', json=ref | dict(sql='SELECT secrets')).status_code == 422
