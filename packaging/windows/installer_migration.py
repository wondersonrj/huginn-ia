"""Same-user, same-directory Inno migration. No shell, process kill, SQL or reboot.
Executed by the NEW Setup's temporary embedded runtime before installed files change.
The Setup holds supervisor.lock across backup, file copy, validation and rollback.
"""
import argparse
import hashlib
import hmac
import http.cookiejar
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import sys
import time
import urllib.request
import uuid
from functools import lru_cache

sys.path.insert(0, str(Path(__file__).resolve().parent))
from maintenance_windows import DPAPI, local_app_data, private_permissions, windows_identity

windows_identity = lru_cache(maxsize=1)(windows_identity)

APP_KEY = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{1F07B592-9CB4-4937-B35B-4A197E9AB867}_is1'
BACKUP = '.installer-backup'
VERSION = re.compile(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z')


class MigrationError(Exception):
    pass


def safe(path):
    path = Path(path).absolute()
    if any(ord(c) < 32 for c in str(path)) or str(path).startswith('\\\\'):
        raise MigrationError('unsafe_path')
    if os.name == 'nt' and path.anchor:
        import ctypes
        if ctypes.windll.kernel32.GetDriveTypeW(path.anchor) == 4:
            raise MigrationError('unsafe_path')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise MigrationError('unsafe_path')
    return path


def identity(root):
    return hashlib.sha256(str(safe(root).resolve()).casefold().encode()).hexdigest()


def read_json(path, limit=8 * 1024 * 1024):
    safe(path)
    if path.stat().st_size > limit:
        raise MigrationError('invalid_metadata')
    return json.loads(path.read_text(encoding='utf-8'))


def atomic(path, data, private=False):
    safe(path); safe(path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('xb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        if private:
            private_permissions(temp, windows_identity())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def journal(root):
    path = safe(root) / BACKUP / 'journal.json'
    data = read_json(path)
    if data.get('installation') != identity(root) or data.get('sid') != windows_identity() or data.get('format') != 1:
        raise MigrationError('foreign_backup')
    return data


def write_journal(root, data):
    atomic(root / BACKUP / 'journal.json', json.dumps(data, ensure_ascii=True).encode(), True)


def registered():
    if os.name != 'nt': return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_KEY, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            return Path(winreg.QueryValueEx(key, 'Inno Setup: App Path')[0])
    except FileNotFoundError:
        return None


def registry_snapshot():
    if os.name != 'nt': return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_KEY, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            values = []
            for index in range(winreg.QueryInfoKey(key)[1]):
                name, value, kind = winreg.EnumValue(key, index)
                if kind not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ, winreg.REG_DWORD):
                    raise MigrationError('unsupported_registry')
                values.append([name, value, kind])
            return values
    except FileNotFoundError:
        return []


def restore_registry(root, values):
    if os.name != 'nt': return
    import winreg
    current = registered()
    if current is not None and identity(current) != identity(root):
        raise MigrationError('registry_changed')
    if not values:
        try:
            winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, APP_KEY, winreg.KEY_WOW64_64KEY)
        except FileNotFoundError: pass
        return
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, APP_KEY, 0, winreg.KEY_ALL_ACCESS | winreg.KEY_WOW64_64KEY) as key:
        for name, _, _ in [winreg.EnumValue(key, i) for i in range(winreg.QueryInfoKey(key)[1])]:
            winreg.DeleteValue(key, name)
        for name, value, kind in values:
            winreg.SetValueEx(key, name, 0, kind, value)


def shortcuts():
    if os.name != 'nt': return {}
    import ctypes
    result = {}
    for label, csidl, tail in [('menu', 2, 'HUGINN IA/HUGINN IA.lnk'), ('desktop', 0x10, 'HUGINN IA.lnk')]:
        buffer = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buffer) != 0:
            raise MigrationError('windows_profile_unavailable')
        result[label] = safe(Path(buffer.value) / tail)
    return result


def vault(root):
    return safe(local_app_data() / 'HUGINN' / 'Connections' / identity(root))


def relative(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise MigrationError('unsafe_inventory')
    parts = value.split('/')
    if any(p in ('', '.', '..') or p.endswith((' ', '.')) for p in parts):
        raise MigrationError('unsafe_inventory')
    return Path(*parts)


def inspect(root, inventory):
    root = safe(root)
    if not VERSION.fullmatch(inventory.get('version', '')) or not isinstance(inventory.get('files'), dict) or len(inventory['files']) > 20000:
        raise MigrationError('invalid_inventory')
    for name, digest in inventory['files'].items():
        path = relative(name)
        if path.parts[0] in {'runtime', 'state', BACKUP} or not re.fullmatch('[0-9a-f]{64}', digest):
            raise MigrationError('invalid_inventory')
    current = registered()
    if current and identity(current) != identity(root):
        raise MigrationError('use_registered_directory')
    recovery = root / BACKUP / 'journal.json'
    if recovery.exists():
        data = journal(root)
        if data['phase'] in ('prepared', 'validated'):
            return dict(kind='recovery', previous=data['previous'], target=inventory['version'])
    current = registered()
    if current and identity(current) != identity(root):
        raise MigrationError('use_registered_directory')
    cfg_path = root / 'bootstrap.json'
    if not cfg_path.exists():
        if recovery.exists():
            data = journal(root)
            if data['payload']['runtime_id'] != inventory['runtime_id'] or data['payload']['channel'] != inventory['channel']:
                raise MigrationError('incompatible_installation')
            return dict(kind='retained', previous=data['payload']['version'], target=inventory['version'])
        if root.exists() and any(p.name not in {'state', BACKUP} for p in root.iterdir()):
            raise MigrationError('unrecognized_directory')
        return dict(kind='fresh', previous='nenhuma', target=inventory['version'])
    cfg = read_json(cfg_path)
    if (root / 'state/journal.json').exists():
        raise MigrationError('updater_recovery_pending')
    if (cfg.get('runtime_id') != inventory['runtime_id'] or cfg.get('channel') != inventory['channel']
            or cfg.get('bootstrap_version') != 1 or not VERSION.fullmatch(cfg.get('version', ''))):
        raise MigrationError('incompatible_installation')
    active = cfg['version']
    if (root / 'state/current.json').exists():
        active = read_json(root / 'state/current.json')['version']
        if not isinstance(active, str) or not VERSION.fullmatch(active):
            raise MigrationError('incomplete_installation')
        metadata = read_json(root / 'versions' / active / 'version.json')
        if metadata.get('version') != active or metadata.get('runtime_id') != inventory['runtime_id'] or metadata.get('channel') != inventory['channel']:
            raise MigrationError('incompatible_installation')
    if tuple(map(int, active.split('.'))) > tuple(map(int, inventory['version'].split('.'))):
        raise MigrationError('downgrade_refused')
    for name in ('launcher.py', 'updater.py', 'runtime/python.exe'):
        if not safe(root / name).is_file():
            raise MigrationError('incomplete_installation')
    return dict(kind='installed' if current else 'portable', previous=active, target=inventory['version'])


def lock_available(root):
    path = safe(root) / 'state/supervisor.lock'
    if not path.exists(): return True
    with path.open('r+b') as stream:
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(stream, fcntl.LOCK_UN)
            return True
        except OSError:
            return False


def stop_owned(root):
    if lock_available(root):
        descriptor = root / 'state/instance.json'
        if not descriptor.exists(): return
        port = read_json(descriptor, 2048)['port']
        if type(port) is not int or not 1024 <= port <= 65535: raise MigrationError('identity_unconfirmed')
        try:
            connection = socket.create_connection(('127.0.0.1', port), timeout=.3)
        except ConnectionRefusedError:
            return
        else:
            connection.close()
        # A backend may outlive its supervisor. Still require proof before stopping it.
    # No arbitrary PID handling. A random challenge authenticates this exact installation.
    cfg = read_json(root / 'bootstrap.json')
    version = read_json(root / 'state/current.json')['version']
    if not VERSION.fullmatch(version): raise MigrationError('identity_unconfirmed')
    metadata = read_json(root / 'versions' / version / 'version.json')
    build = metadata.get('source_commit') or read_json(root / 'BUILD-INFO.json')['source_commit']
    token_file = vault(root) / 'local-token.bin'
    if not 1 <= token_file.stat().st_size <= 16384: raise MigrationError('identity_unconfirmed')
    entropy = hashlib.sha256(f'HUGINN:desktop:v1:{identity(root)}:{windows_identity()}'.encode()).digest()
    token = DPAPI().unprotect(token_file.read_bytes(), entropy).decode('ascii')
    if not re.fullmatch('[0-9a-f]{64}', token): raise MigrationError('identity_unconfirmed')
    port = read_json(root / 'state/instance.json', 2048)['port']
    if type(port) is not int or not 1024 <= port <= 65535: raise MigrationError('identity_unconfirmed')
    url = f'http://127.0.0.1:{port}'
    challenge = uuid.uuid4().hex + uuid.uuid4().hex
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs): return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    with opener.open(url + '/api/local-instance?challenge=' + challenge, timeout=2) as response:
        proof = json.loads(response.read(4096))
    payload = f'{challenge}:{identity(root)}:{version}:{port}'
    if 'build' in proof:
        if proof['build'] != build: raise MigrationError('identity_unconfirmed')
        payload += ':' + build
    elif not version.startswith('0.2.'):
        raise MigrationError('identity_unconfirmed')
    expected = hmac.new(token.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if (proof.get('installation') != identity(root) or proof.get('version') != version or proof.get('port') != port
            or not hmac.compare_digest(proof.get('proof', ''), expected)):
        raise MigrationError('identity_unconfirmed')
    for endpoint in ('local-session', 'local-stop'):
        request = urllib.request.Request(url + '/api/' + endpoint, data=b'{}', headers={'Content-Type': 'application/json', 'Origin': url})
        with opener.open(request, timeout=3) as response:
            if response.status != 200: raise MigrationError('shutdown_refused')
    atomic(root / 'state/stop', b'')  # graceful child watch, only after HMAC + SID-authenticated API
    for _ in range(150):
        if lock_available(root):
            try:
                # A released supervisor lock alone does not prove its child exited.
                try:
                    connection = socket.create_connection(('127.0.0.1', port), timeout=.3)
                except ConnectionRefusedError:
                    connection = None
                else:
                    connection.close()
                    time.sleep(.2)
                    continue
                executable = root / 'HUGINN-IA.exe'
                if executable.exists():
                    with executable.open('r+b'): pass  # wait for our native wrapper to unmap; never terminate it
                return
            except OSError:
                pass
        time.sleep(.2)
    raise MigrationError('shutdown_pending')


def target(root, key):
    if key.startswith('file:'): return safe(root / relative(key[5:]))
    if key.startswith('vault:'): return safe(vault(root) / relative(key[6:]))
    if key.startswith('shortcut:') and key[9:] in shortcuts(): return shortcuts()[key[9:]]
    raise MigrationError('unsafe_backup')


def clear_backup(root):
    backup = safe(root / BACKUP)
    if not backup.exists(): return
    if not (backup / 'journal.json').exists():
        if any(backup.iterdir()): raise MigrationError('unrecognized_backup')
        backup.rmdir(); return
    journal(root)
    for path in backup.iterdir():
        safe(path)
        if path.name == 'journal.json' and path.is_file(): continue
        if path.name != 'files' or not path.is_dir(): raise MigrationError('unrecognized_backup')
        for blob in path.iterdir():
            safe(blob)
            if not blob.is_file() or not re.fullmatch('[a-f0-9]{64}', blob.name):
                raise MigrationError('unrecognized_backup')
    shutil.rmtree(backup)


def prepare(root, inventory):
    root = safe(root)
    if (root / BACKUP / 'journal.json').exists():
        previous = journal(root)
        if previous['phase'] in ('prepared', 'validated'):
            rollback(root)
        if previous['phase'] not in ('backing_up', 'prepared', 'validated', 'committed', 'rolled_back'):
            raise MigrationError('invalid_journal')
    report = inspect(root, inventory)
    backup = safe(root / BACKUP)
    clear_backup(root)
    backup.mkdir(parents=True); private_permissions(backup, windows_identity())
    data = dict(format=1, installation=identity(root), sid=windows_identity(), phase='backing_up',
                previous=report['previous'], payload=inventory, entries={}, registry=registry_snapshot())
    write_journal(root, data)
    keys = ['file:' + name for name in inventory['files']]
    keys += ['file:' + name for name in ('state/current.json', 'state/preferences.json', 'state/status.json', 'state/installer-backup.json', 'state/backup.json', 'state/instance.json', 'installer-inventory.json')]
    if root.exists():
        keys += ['file:' + p.name for p in root.iterdir() if re.fullmatch(r'unins\d{3}\.(exe|dat|msg)', p.name)]
    keys += [f'file:unins{i:03d}.{suffix}' for i in range(20) for suffix in ('exe', 'dat', 'msg')]
    keys += ['shortcut:' + name for name in shortcuts()]
    v = vault(root)
    if v.exists():
        keys += ['vault:' + p.name for p in v.iterdir() if p.name == 'profiles.json' or p.name == 'local-token.bin' or re.fullmatch('[a-f0-9]{32}\\.dpapi', p.name)]
    total = 0
    for key in sorted(set(keys)):
        path = target(root, key)
        if not path.exists():
            data['entries'][key] = None
            continue
        if not path.is_file() or path.stat().st_size > 128 * 1024 * 1024: raise MigrationError('backup_limit')
        content = path.read_bytes(); total += len(content)
        if total > 512 * 1024 * 1024: raise MigrationError('backup_limit')
        name = hashlib.sha256(key.encode()).hexdigest()
        atomic(backup / 'files' / name, content, True)
        data['entries'][key] = dict(blob=name, sha256=hashlib.sha256(content).hexdigest())
    data['phase'] = 'prepared'; write_journal(root, data)
    return report


def verify_installed(root):
    data = journal(root)
    if data['phase'] not in ('prepared', 'validated'): raise MigrationError('maintenance_not_prepared')
    for name, digest in data['payload']['files'].items():
        path = safe(root / relative(name))
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise MigrationError('installed_hash_mismatch')
    for key, entry in data['entries'].items():
        if key.startswith('vault:') and entry:
            if hashlib.sha256(target(root, key).read_bytes()).hexdigest() != entry['sha256']:
                raise MigrationError('vault_changed')
    return data


def validated(root):
    data = verify_installed(root); data['phase'] = 'validated'; write_journal(root, data)


def commit(root):
    data = verify_installed(root)
    if data['phase'] != 'validated': raise MigrationError('health_not_confirmed')
    data['phase'] = 'committed'; write_journal(root, data)


def rollback(root):
    data = journal(root)
    if data['phase'] == 'backing_up':
        data['phase'] = 'rolled_back'; write_journal(root, data)
        return  # installed files have not been touched yet
    if data['phase'] == 'rolled_back': return
    if data['phase'] not in ('prepared', 'validated'): raise MigrationError('rollback_not_pending')
    # Verify ALL backup bytes before changing any installed file.
    contents = {}
    for key, entry in data['entries'].items():
        target(root, key)
        if entry:
            if not re.fullmatch('[a-f0-9]{64}', entry['blob']): raise MigrationError('unsafe_backup')
            content = safe(root / BACKUP / 'files' / entry['blob']).read_bytes()
            if hashlib.sha256(content).hexdigest() != entry['sha256']: raise MigrationError('damaged_backup')
            contents[key] = content
    for key, entry in data['entries'].items():
        path = target(root, key)
        if entry:
            atomic(path, contents[key], key.startswith('vault:') or key.startswith('file:state/'))
        elif path.is_file():
            path.unlink()
    restore_registry(root, data['registry'])
    data['phase'] = 'rolled_back'; write_journal(root, data)


def pending(root):
    path = Path(root) / BACKUP / 'journal.json'
    if not path.exists(): return False
    return journal(Path(root))['phase'] not in ('committed', 'rolled_back')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['inspect', 'stop-owned', 'prepare', 'rollback', 'commit'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--inventory', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    try:
        inventory = read_json(args.inventory) if args.inventory else None
        root = safe(args.root)
        if args.action == 'inspect': report = inspect(root, inventory)
        elif args.action == 'stop-owned': stop_owned(root); report = {}
        elif args.action == 'prepare': report = prepare(root, inventory)
        elif args.action == 'rollback': rollback(root); report = {}
        else: commit(root); report = {}
        if args.report:
            atomic(args.report, ('[Migration]\nstatus=ok\n' + ''.join(f'{k}={v}\n' for k, v in report.items())).encode())
        return 0
    except Exception as exc:
        if args.action == 'prepare':
            try:
                if journal(root)['phase'] == 'backing_up': rollback(root)
            except Exception: pass
        code = str(exc) if isinstance(exc, MigrationError) else ('identity_unconfirmed' if args.action == 'stop-owned' else 'operation_refused')
        if args.report:
            atomic(args.report, f'[Migration]\nstatus={code}\n'.encode())
        # Fixed public codes only. Never emit exception strings, credentials or driver data.
        return 1


if __name__ == '__main__': raise SystemExit(main())
