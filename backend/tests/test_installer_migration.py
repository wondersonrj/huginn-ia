"""Transactional ownership, backup integrity, encrypted state and failure recovery."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from app import windows_secrets


@pytest.fixture
def migration(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[2] / 'packaging/windows/installer_migration.py'
    spec = importlib.util.spec_from_file_location('migration_test', path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'maintenance_windows': windows_secrets}): spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'windows_identity', lambda: 'S-1-5-21-TEST')
    monkeypatch.setattr(module, 'private_permissions', lambda path, sid: None)
    monkeypatch.setattr(module, 'registered', lambda: None)
    monkeypatch.setattr(module, 'registry_snapshot', lambda: [])
    monkeypatch.setattr(module, 'restore_registry', lambda root, values: None)
    monkeypatch.setattr(module, 'shortcuts', lambda: {'menu': tmp_path / 'user/Menu/HUGINN.lnk'})
    monkeypatch.setattr(module, 'vault', lambda root: tmp_path / 'user/encrypted-vault')
    root = tmp_path / 'Program with spaces'
    root.mkdir()
    original = dict(version='0.2.0', channel='teste', runtime_id='runtime', bootstrap_version=1)
    for name, content in {'bootstrap.json': json.dumps(original).encode(), 'launcher.py': b'old launcher', 'updater.py': b'old updater',
                          'runtime/python.exe': b'untouched runtime', 'state/current.json': b'{"version":"0.2.0"}',
                          'state/preferences.json': b'{"theme":"dark"}', 'customer.txt': b'never delete user data',
                          'versions/0.2.0/version.json': json.dumps(original).encode(), 'unins000.exe': b'old uninstaller'}.items():
        dest = root / name; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(content)
    module.vault(root).mkdir(parents=True)
    for name, content in {'profiles.json': b'profile metadata', 'local-token.bin': b'ciphertext token', 'a'*32+'.dpapi': b'ciphertext password'}.items():
        (module.vault(root) / name).write_bytes(content)
    new = {'launcher.py': b'new launcher', 'bootstrap.json': json.dumps(original | {'version': '0.3.1'}).encode(),
           'versions/0.3.1/server.py': b'new worker'}
    inventory = dict(version='0.3.1', channel='teste', runtime_id='runtime', files={name: hashlib.sha256(data).hexdigest() for name, data in new.items()})
    def install():
        for name, content in new.items():
            target = root / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(content)
    return module, root, inventory, install


def test_upgrade_commits_only_after_health_and_preserves_private_bytes(migration):
    m, root, inv, install = migration
    before = {p.name: p.read_bytes() for p in m.vault(root).iterdir()}
    m.prepare(root, inv); install()
    with pytest.raises(m.MigrationError, match='health_not_confirmed'): m.commit(root)
    m.validated(root); m.commit(root)
    assert not m.pending(root)
    assert before == {p.name: p.read_bytes() for p in m.vault(root).iterdir()}
    assert (root / 'state/preferences.json').read_bytes() == b'{"theme":"dark"}'
    assert (root / 'customer.txt').read_bytes() == b'never delete user data'
    assert (root / 'runtime/python.exe').read_bytes() == b'untouched runtime'


def test_failure_restores_bootstrap_pointer_uninstaller_shortcut_and_vault(migration):
    m, root, inv, install = migration
    shortcut = m.shortcuts()['menu']; shortcut.parent.mkdir(parents=True); shortcut.write_bytes(b'old shortcut')
    m.prepare(root, inv); install()
    (root / 'state/current.json').write_text('{"version":"0.3.1"}')
    shortcut.write_bytes(b'new shortcut')
    (m.vault(root) / 'local-token.bin').write_bytes(b'bad change')
    with pytest.raises(m.MigrationError, match='vault_changed'): m.verify_installed(root)
    m.rollback(root)
    assert (root / 'launcher.py').read_bytes() == b'old launcher'
    assert json.loads((root / 'state/current.json').read_text())['version'] == '0.2.0'
    assert shortcut.read_bytes() == b'old shortcut'
    assert (m.vault(root) / 'local-token.bin').read_bytes() == b'ciphertext token'
    assert (root / 'unins000.exe').read_bytes() == b'old uninstaller'
    assert not (root / 'versions/0.3.1/server.py').exists()
    assert not m.pending(root)


def test_interrupted_copy_is_restored_before_next_install_backup(migration):
    m, root, inv, install = migration
    m.prepare(root, inv); install()
    assert m.inspect(root, inv)['kind'] == 'recovery'
    m.prepare(root, inv)
    assert (root / 'launcher.py').read_bytes() == b'old launcher'
    assert json.loads((root / 'state/current.json').read_text())['version'] == '0.2.0'
    install(); m.validated(root); m.commit(root)
    assert m.journal(root)['previous'] == '0.2.0'


def test_damaged_backup_fails_closed_before_restoring_any_file(migration):
    m, root, inv, install = migration
    m.prepare(root, inv); install()
    entry = next(e for e in m.journal(root)['entries'].values() if e)
    (root / m.BACKUP / 'files' / entry['blob']).write_bytes(b'tampered')
    with pytest.raises(m.MigrationError, match='damaged_backup'): m.rollback(root)
    assert (root / 'launcher.py').read_bytes() == b'new launcher'
    assert m.pending(root)


@pytest.mark.parametrize('mutation,code', [({'runtime_id':'other'}, 'incompatible_installation'), ({'channel':'estavel'}, 'incompatible_installation'), ({'version':'0.1.0'}, 'downgrade_refused')])
def test_incompatible_installation_never_modified(migration, mutation, code):
    m, root, inv, install = migration
    with pytest.raises(m.MigrationError, match=code): m.prepare(root, inv | mutation)
    assert (root / 'launcher.py').read_bytes() == b'old launcher'
    assert not (root / m.BACKUP).exists()


def test_registered_directory_cannot_be_silently_changed(migration, monkeypatch):
    m, root, inv, install = migration
    monkeypatch.setattr(m, 'registered', lambda: root.parent / 'other installation')
    with pytest.raises(m.MigrationError, match='use_registered_directory'): m.inspect(root, inv)


def test_symlinks_and_inventory_traversal_are_refused(migration):
    m, root, inv, install = migration
    with pytest.raises(m.MigrationError): m.prepare(root, inv | {'files': {'../outside': 'a'*64}})
    outside = root.parent / 'outside'; outside.mkdir()
    (root / 'linked').symlink_to(outside, target_is_directory=True)
    with pytest.raises(m.MigrationError, match='unsafe_path'): m.safe(root / 'linked/file')
    assert not list(outside.iterdir())


@pytest.mark.parametrize('forged', [True, False])
def test_shutdown_requires_hmac_then_authenticated_session_never_a_pid(migration, monkeypatch, forged):
    m, root, inv, install = migration
    (root / 'versions/0.2.0').mkdir(parents=True, exist_ok=True)
    (root / 'versions/0.2.0/version.json').write_text('{"source_commit":"old-build"}')
    (root / 'state/instance.json').write_text('{"port":8123}')
    token = 'a' * 64
    monkeypatch.setattr(m, 'DPAPI', lambda: SimpleNamespace(unprotect=lambda data, entropy: token.encode()))
    checks = iter([False, True]); monkeypatch.setattr(m, 'lock_available', lambda root: next(checks))
    calls = []
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size):
            challenge = calls[0].split('=')[-1]
            payload = f'{challenge}:{m.identity(root)}:0.2.0:8123:old-build'
            proof = m.hmac.new(token.encode(), payload.encode(), hashlib.sha256).hexdigest()
            return json.dumps(dict(installation=m.identity(root), version='0.2.0', port=8123, build='old-build', proof='invalid' if forged else proof)).encode()
    def open_request(request, **kwargs):
        calls.append(request if isinstance(request, str) else request.full_url)
        if not isinstance(request, str): assert request.data == b'{}' and request.headers['Origin'] == 'http://127.0.0.1:8123'
        return Response()
    def refused(*args, **kwargs): raise ConnectionRefusedError()
    monkeypatch.setattr(m.socket, 'create_connection', refused)
    monkeypatch.setattr(m.urllib.request, 'build_opener', lambda *args: SimpleNamespace(open=open_request))
    if forged:
        with pytest.raises(m.MigrationError, match='identity_unconfirmed'): m.stop_owned(root)
        assert len(calls) == 1
    else:
        m.stop_owned(root)
        assert [c.split('/')[-1] for c in calls[1:]] == ['local-session', 'local-stop']


def test_preserved_uninstall_data_is_recognized_without_deleting_user_files(migration):
    m, root, inv, install = migration
    m.prepare(root, inv); install(); m.validated(root); m.commit(root)
    (root / 'bootstrap.json').unlink()
    (root / 'launcher.py').unlink()
    assert m.inspect(root, inv)['kind'] == 'retained'
    m.prepare(root, inv); install(); m.validated(root); m.commit(root)
    assert (root / 'customer.txt').read_bytes() == b'never delete user data'


def test_effective_active_version_prevents_downgrading_a_signed_update(migration):
    m, root, inv, install = migration
    (root / 'versions/0.4.0').mkdir()
    (root / 'versions/0.4.0/version.json').write_text(json.dumps(dict(version='0.4.0', runtime_id='runtime', channel='teste')))
    (root / 'state/current.json').write_text('{"version":"0.4.0"}')
    with pytest.raises(m.MigrationError, match='downgrade_refused'): m.inspect(root, inv)


def test_failure_fixture_only_breaks_the_versioned_entrypoint(tmp_path):
    import zipfile
    path = Path(__file__).resolve().parents[2] / 'packaging/windows/make_failure_fixture.py'
    spec = importlib.util.spec_from_file_location('failure_fixture_test', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    original = tmp_path / 'original.zip'; failed = tmp_path / 'failed.zip'
    with zipfile.ZipFile(original, 'w') as archive:
        archive.writestr('HUGINN-IA-Windows-x64/bootstrap.json', '{"version":"0.3.2"}')
        archive.writestr('HUGINN-IA-Windows-x64/versions/0.3.2/server.py', '# healthy')
        archive.writestr('HUGINN-IA-Windows-x64/runtime/Lib/http/server.py', '# standard library unchanged')
    module.make(original, failed)
    with zipfile.ZipFile(failed) as archive:
        assert archive.read('HUGINN-IA-Windows-x64/versions/0.3.2/server.py') == b'raise SystemExit(42)\n'
        assert archive.read('HUGINN-IA-Windows-x64/runtime/Lib/http/server.py') == b'# standard library unchanged'


def test_unrecognized_backup_folder_is_never_deleted(migration):
    m, root, inv, install = migration
    folder = root / m.BACKUP; folder.mkdir()
    (folder / 'customer.txt').write_text('user backup data')
    with pytest.raises(m.MigrationError, match='unrecognized_backup'): m.prepare(root, inv)
    assert (folder / 'customer.txt').read_text() == 'user backup data'
    assert (root / 'launcher.py').read_bytes() == b'old launcher'


def test_extra_user_file_in_prior_backup_blocks_rotation_without_data_loss(migration):
    m, root, inv, install = migration
    m.prepare(root, inv); install(); m.validated(root); m.commit(root)
    extra = root / m.BACKUP / 'customer.txt'; extra.write_text('never erase unknown files')
    with pytest.raises(m.MigrationError, match='unrecognized_backup'): m.prepare(root, inv)
    assert extra.read_text() == 'never erase unknown files'


def test_explicit_data_removal_validates_unknown_backup_before_erasing_vault(migration, monkeypatch):
    m, root, inv, install = migration
    from app import connection_store
    monkeypatch.setattr(connection_store, 'current_store', lambda: SimpleNamespace(root=m.vault(root)))
    path = Path(__file__).resolve().parents[2] / 'packaging/windows/installer_state.py'
    spec = importlib.util.spec_from_file_location('installer_removal_test', path)
    state = importlib.util.module_from_spec(spec); spec.loader.exec_module(state)
    folder = root / m.BACKUP; folder.mkdir(); (folder / 'customer.txt').write_text('unknown private data')
    with patch.dict(sys.modules, {'installer_migration': m}), pytest.raises(m.MigrationError, match='unrecognized_backup'):
        state.remove_data(root)
    assert (m.vault(root) / 'local-token.bin').read_bytes() == b'ciphertext token'
    assert (folder / 'customer.txt').read_text() == 'unknown private data'


def test_explicit_removal_erases_only_recognized_private_state(migration, monkeypatch):
    m, root, inv, install = migration
    m.prepare(root, inv); install(); m.validated(root); m.commit(root)
    from app import connection_store
    monkeypatch.setattr(connection_store, 'current_store', lambda: SimpleNamespace(root=m.vault(root)))
    path = Path(__file__).resolve().parents[2] / 'packaging/windows/installer_state.py'
    spec = importlib.util.spec_from_file_location('installer_removal_ok_test', path)
    state = importlib.util.module_from_spec(spec); spec.loader.exec_module(state)
    with patch.dict(sys.modules, {'installer_migration': m}): state.remove_data(root)
    assert not m.vault(root).exists() and not (root / m.BACKUP).exists() and not (root / 'state').exists()
    assert (root / 'customer.txt').read_text() == 'never delete user data'
