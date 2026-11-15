"""Per-user/installation metadata + separate DPAPI blobs. Selection is process-local."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
import uuid
from app.oracle_connector import OracleConfig
from app.windows_secrets import DPAPI, VaultError, local_app_data, private_permissions, windows_identity


class SelectionRequired(Exception):
    pass


class Conflict(Exception):
    pass


def safe_path(path):
    for part in [*reversed(path.parents), path]:
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise VaultError('Reparse points are not allowed')


@dataclass(frozen=True)
class Resolved:
    profile: dict
    config: OracleConfig


class Store:
    def __init__(self, root, installation, identity, protector):
        self.root, self.installation, self.identity = Path(root).absolute(), installation, identity
        self.protector = protector
        self.active = None
        self.fallback = False
        self.tests = {}
        self.mutex = threading.RLock()

    def prepare(self):
        safe_path(self.root)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        private_permissions(self.root, self.identity)

    @contextmanager
    def locked(self):
        with self.mutex:
            self.prepare()
            path = self.root / 'connections.lock'
            safe_path(path)
            descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                private_permissions(path, self.identity)
                if os.fstat(descriptor).st_size == 0:
                    os.write(descriptor, b'\0')
                os.lseek(descriptor, 0, os.SEEK_SET)
                try:
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    raise Conflict('Another operation is in progress') from None
                try:
                    yield
                finally:
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    if os.name == 'nt':
                        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)

    def read(self):
        path = self.root / 'profiles.json'
        safe_path(path)
        if not path.exists():
            if list(self.root.glob('*.dpapi')):
                raise VaultError('Metadata missing; protected credentials remain')
            return {'version': 1, 'installation': self.installation, 'identity': self.identity, 'profiles': [], 'managed': False}
        try:
            private_permissions(path, self.identity)
            if path.stat().st_size > 256_000:
                raise ValueError()
            data = json.loads(path.read_text(encoding='utf-8'))
            if (set(data) != {'version', 'installation', 'identity', 'profiles', 'managed'} or data['version'] != 1 or data['installation'] != self.installation
                    or data['identity'] != self.identity or data['managed'] is not True
                    or len(data['profiles']) > 50):
                raise ValueError()
            ids = set()
            for profile in data['profiles']:
                self.validate(profile)
                for key in ('id', 'revision'):
                    if not re.fullmatch('[a-f0-9]{32}', profile[key]):
                        raise ValueError()
                if profile.get('secret_id') is not None and not re.fullmatch('[a-f0-9]{32}', profile['secret_id']):
                    raise ValueError()
                if profile['id'] in ids or set(profile) != {'id', 'revision', 'secret_id', 'name', 'environment', 'host', 'port', 'service', 'user', 'owner'}:
                    raise ValueError()
                ids.add(profile['id'])
            return data
        except (ValueError, KeyError, TypeError, AttributeError, OSError):
            raise VaultError('Connection metadata corrupted or inaccessible') from None

    @staticmethod
    def validate(profile):
        if not isinstance(profile['name'], str) or not isinstance(profile['host'], str) or not isinstance(profile['service'], str) or not isinstance(profile['user'], str):
            raise ValueError('Invalid profile')
        if len(profile['host']) > 253:
            raise ValueError('Invalid host')
        if profile['environment'] not in {'TESTE', 'PRODUCAO'} or not 1 <= len(profile['name'].strip()) <= 80:
            raise ValueError('Invalid profile')
        if not re.fullmatch('[A-Z][A-Z0-9_]{0,29}', profile['owner']):
            raise ValueError('Invalid owner')
        if type(profile['port']) is not int or len(profile['service']) > 255 or len(profile['user']) > 128:
            raise ValueError('Invalid profile')
        OracleConfig(profile['host'], profile['port'], profile['service'], profile['user'], 'validation-only').validate()

    def atomic(self, path, data):
        safe_path(path)
        temp = self.root / (uuid.uuid4().hex + '.tmp')
        descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            private_permissions(temp, self.identity)
            with os.fdopen(descriptor, 'wb') as stream:
                descriptor = None
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
            os.replace(temp, path)
        finally:
            if descriptor is not None:
                os.close(descriptor)
            temp.unlink(missing_ok=True)

    def write(self, data):
        data['managed'] = True
        self.atomic(self.root / 'profiles.json', json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def entropy(self, profile):
        return hashlib.sha256(f'HUGINN:oracle:v1:{self.identity}:{self.installation}:{profile["id"]}:{profile["secret_id"]}'.encode()).digest()

    def secret_path(self, profile):
        path = self.root / f'{profile["secret_id"]}.dpapi'
        safe_path(path)
        return path

    def password(self, profile):
        if not profile.get('secret_id'):
            raise VaultError('No saved password')
        path = self.secret_path(profile)
        try:
            private_permissions(path, self.identity)
            if not 1 <= path.stat().st_size <= 16384:
                raise VaultError('Invalid protected credential')
            value = self.protector.unprotect(path.read_bytes(), self.entropy(profile)).decode('utf-8')
            if not 1 <= len(value) <= 1024:
                raise VaultError('Invalid protected credential')
            return value
        except (OSError, ValueError, UnicodeError):
            raise VaultError('Protected credential missing, corrupted or belongs to another user') from None

    def public(self, profile):
        return {k: v for k, v in profile.items() if k != 'secret_id'} | {
            'password_saved': bool(profile.get('secret_id') and self.secret_path(profile).is_file()),
            'last_test': self.tests.get(profile['id']) if self.tests.get(profile['id'], {}).get('revision') == profile['revision'] else None,
        }

    def listing(self):
        with self.locked():
            data = self.read()
            active = next((p for p in data['profiles'] if self.active == (p['id'], p['revision'])), None)
            return {'supported': True, 'profiles': [self.public(p) for p in data['profiles']],
                    'active': self.public(active) if active else None,
                    'source': 'saved' if active else ('environment' if self.fallback or not data['managed'] else 'selection_required')}

    def find(self, data, identifier, revision):
        profile = next((p for p in data['profiles'] if p['id'] == identifier), None)
        if profile is None or profile['revision'] != revision:
            raise Conflict('Connection changed; reload before continuing')
        return profile

    def save(self, fields, password=None, identifier=None, revision=None):
        if set(fields) != {'name', 'environment', 'host', 'port', 'service', 'user', 'owner'}:
            raise ValueError('Only non-secret metadata fields are accepted')
        self.validate(fields)
        if password is not None and not 1 <= len(password) <= 1024:
            raise ValueError('Invalid password')
        with self.locked():
            data = self.read()
            old = self.find(data, identifier, revision) if identifier else None
            if any(p['id'] != identifier and p['name'].strip().casefold() == fields['name'].strip().casefold() for p in data['profiles']):
                raise ValueError('Connection name already exists')
            if old is None and len(data['profiles']) >= 50:
                raise ValueError('Connection limit reached')
            new = dict(fields, id=old['id'] if old else uuid.uuid4().hex,
                       revision=uuid.uuid4().hex, secret_id=old['secret_id'] if old else None)
            if password is not None:
                new['secret_id'] = uuid.uuid4().hex
                protected = self.protector.protect(password.encode('utf-8'), self.entropy(new))
                self.atomic(self.secret_path(new), protected)
            data['profiles'] = [p for p in data['profiles'] if p['id'] != new['id']] + [new]
            try:
                self.write(data)
            except Exception:
                if password is not None:
                    self.secret_path(new).unlink(missing_ok=True)
                raise
            self.active, self.fallback = None, False
            self.tests.pop(new['id'], None)
            if old and password is not None and old.get('secret_id'):
                self.secret_path(old).unlink(missing_ok=True)
            return self.public(new)

    def remove(self, identifier, revision, password_only=False):
        with self.locked():
            data = self.read(); profile = self.find(data, identifier, revision)
            # Invalidate before deletion: partial I/O failure cannot retain an active destination.
            self.active, self.fallback = None, False
            # Removing a secret first fails closed even if the subsequent metadata write fails.
            if profile.get('secret_id'):
                self.secret_path(profile).unlink(missing_ok=True)
            if password_only:
                profile['secret_id'], profile['revision'] = None, uuid.uuid4().hex
            else:
                data['profiles'].remove(profile)
            self.write(data)
            self.active, self.fallback = None, False
            self.tests.pop(identifier, None)

    def resolve_profile(self, profile):
        return Resolved(self.public(profile), OracleConfig(profile['host'], profile['port'], profile['service'], profile['user'], self.password(profile)))

    def selected(self, identifier=None, revision=None):
        if self.fallback:
            if identifier or revision:
                raise SelectionRequired('Saved connection no longer selected')
            return None
        with self.locked():
            data = self.read()
            if not data['managed']:
                if identifier or revision:
                    raise SelectionRequired('Saved connection no longer selected')
                return None
            if self.active is None or self.active != (identifier, revision):
                raise SelectionRequired('Explicit connection selection required')
            return self.resolve_profile(self.find(data, identifier, revision))

    def choose(self, identifier, revision, confirmed):
        with self.locked():
            data = self.read(); profile = self.find(data, identifier, revision)
            if confirmed != profile['environment']:
                raise Conflict('Confirm the destination environment explicitly')
            self.resolve_profile(profile)  # Never select a missing/corrupt secret.
            self.active, self.fallback = (identifier, revision), False
            return self.public(profile)

    def for_test(self, identifier, revision, confirmed):
        with self.locked():
            profile = self.find(self.read(), identifier, revision)
            if confirmed != profile['environment']:
                raise Conflict('Confirm the destination environment explicitly')
            return self.resolve_profile(profile)

    def environment(self):
        with self.mutex:
            self.active, self.fallback = None, True


_store = None
_store_lock = threading.Lock()


def current_store():
    global _store
    if os.name != 'nt':
        return None
    with _store_lock:
        if _store is None:
            installation_path = Path(os.environ['HUGINN_STATE_DIR']).parent if os.environ.get('HUGINN_STATE_DIR') else Path(__file__).resolve().parents[2]
            installation = hashlib.sha256(str(installation_path.resolve()).casefold().encode()).hexdigest()
            sid = windows_identity()
            _store = Store(local_app_data() / 'HUGINN' / 'Connections' / installation, installation, sid, DPAPI())
        return _store
