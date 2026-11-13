"""Trusted bootstrap updater. No shell, remote scripts, SQL or credentials.
Only signed GitHub release payloads with this bootstrap/runtime identity.
"""
import base64
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import urllib.parse
import urllib.request
import uuid
import zipfile

REPO = 'wondersonrj/huginn-ia'
API = f'https://api.github.com/repos/{REPO}/releases?per_page=30'
MAX_DOWNLOAD = 100 * 1024 * 1024
SEMVER = re.compile(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z')


class UpdateError(Exception):
    pass


def version_tuple(value):
    if not isinstance(value, str) or not SEMVER.fullmatch(value):
        raise UpdateError('Versão inválida; esperado X.Y.Z sem pré-release.')
    return tuple(map(int, value.split('.')))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('x', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


@contextmanager
def exclusive_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open('a+b')
    try:
        if path.stat().st_size == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise UpdateError('Operação já em andamento.') from None
        yield
    finally:
        # Closing releases the OS lock even after a failed update/process crash.
        handle.close()


def trusted_url(url, redirects=False):
    u = urllib.parse.urlsplit(url)
    allowed = {'github.com', 'api.github.com'}
    if redirects:
        allowed |= {'release-assets.githubusercontent.com', 'objects.githubusercontent.com'}
    if (u.scheme != 'https' or u.hostname not in allowed or u.username or u.password
            or u.port not in (None, 443) or u.fragment):
        raise UpdateError('Origem de download não confiável.')
    return url


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        trusted_url(newurl, redirects=True)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, limit=MAX_DOWNLOAD):
    trusted_url(url)
    opener = urllib.request.build_opener(SafeRedirect())
    try:
        with opener.open(urllib.request.Request(url, headers={'User-Agent': 'HUGINN-Updater/1'}), timeout=20) as response:
            data = response.read(limit + 1)
        if len(data) > limit:
            raise UpdateError('Download excedeu o tamanho permitido.')
        return data
    except UpdateError:
        raise
    except Exception:
        raise UpdateError('Rede indisponível ou download recusado; versão atual preservada.') from None


def signed_manifest(envelope, public_key, current, channel, runtime_id):
    try:
        if set(envelope) != {'signed', 'signature'}:
            raise ValueError()
        data = envelope['signed']
        if set(data) != {'version', 'channel', 'url', 'sha256', 'notes', 'runtime_id', 'bootstrap_version'}:
            raise ValueError()
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key, validate=True))
        key.verify(base64.b64decode(envelope['signature'], validate=True), canonical)
        if version_tuple(data['version']) <= version_tuple(current):
            raise UpdateError('Versão não é mais recente; downgrade/replay recusado.')
        if channel not in {'teste', 'estavel'} or data['channel'] != channel:
            raise UpdateError('Canal de atualização incompatível.')
        expected = f"https://github.com/{REPO}/releases/download/v{data['version']}/HUGINN-IA-Windows-x64.zip"
        if data['url'] != expected:
            raise UpdateError('URL não pertence à release semântica autorizada.')
        trusted_url(data['url'])
        if not isinstance(data['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', data['sha256']):
            raise ValueError()
        if data['runtime_id'] != runtime_id or type(data['bootstrap_version']) is not int or data['bootstrap_version'] != 1:
            raise UpdateError('Novo bootstrap/runtime necessário; instalação manual requerida.')
        if not isinstance(data['notes'], str) or len(data['notes']) > 8000:
            raise ValueError()
        return data
    except UpdateError:
        raise
    except Exception:
        raise UpdateError('Manifesto inválido ou assinatura não confiável.') from None


def discover(config, current, download=fetch):
    if not config.get('updates_enabled') or not config.get('public_key'):
        raise UpdateError('Atualizador desativado: falta aprovação Windows/chave pública.')
    try:
        releases = json.loads(download(API, 1024 * 1024))
        candidates = []
        for release in releases:
            tag = release.get('tag_name', '')
            if release.get('draft') or not re.fullmatch(r'v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', tag):
                continue
            if version_tuple(tag[1:]) > version_tuple(current):
                candidates.append(release)
        for release in sorted(candidates, key=lambda r: version_tuple(r['tag_name'][1:]), reverse=True):
            url = f"https://github.com/{REPO}/releases/download/{release['tag_name']}/manifest.json"
            if not any(a.get('name') == 'manifest.json' and a.get('browser_download_url') == url for a in release.get('assets', [])):
                continue
            envelope = json.loads(download(url, 32768))
            # Channel is inside the signed data; verify even if it is not ours.
            candidate_channel = envelope.get('signed', {}).get('channel')
            data = signed_manifest(envelope, config['public_key'], current, candidate_channel, config['runtime_id'])
            if data['version'] != release['tag_name'][1:]:
                raise UpdateError('Tag e manifesto divergentes.')
            if data['channel'] == config['channel']:
                return envelope
        return None
    except UpdateError:
        raise
    except Exception:
        raise UpdateError('Catálogo de releases inválido ou indisponível.') from None


def extract_payload(archive, stage, version):
    """Validate the whole ZIP; install only a known version payload, never hooks."""
    prefix = f'HUGINN-IA-Windows-x64/versions/{version}/'
    count = total = 0
    seen = set()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            count += 1
            total += member.file_size
            name = member.filename
            parts = PurePosixPath(name).parts
            normalized = name.casefold().rstrip('/')
            if (not name.startswith('HUGINN-IA-Windows-x64/') or count > 20000 or total > 1024**3 or '\\' in name or name.startswith('/')
                    or any(p in {'..', '.'} or ':' in p or p.endswith((' ', '.')) or p.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))} for p in name.rstrip('/').split('/'))
                    or normalized in seen or stat.S_ISLNK(member.external_attr >> 16)
                    or member.flag_bits & 1):
                raise UpdateError('ZIP inseguro ou excedeu limites.')
            seen.add(normalized)
            if name.startswith(prefix) and not member.is_dir():
                relative = Path(*PurePosixPath(name[len(prefix):]).parts)
                if not relative.parts:
                    raise UpdateError('Caminho de payload inválido.')
                target = stage / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(bundle.read(member))
    for path in ['server.py', 'backend/app/main.py', 'frontend/dist/index.html', 'version.json']:
        if not (stage / path).is_file():
            raise UpdateError('Payload incompleto.')
    metadata = json.loads((stage / 'version.json').read_text())
    if metadata.get('version') != version:
        raise UpdateError('Versão do payload divergente.')


class Updater:
    def __init__(self, root, config):
        self.root = Path(root)
        self.state = self.root / 'state'
        self.versions = self.root / 'versions'
        self.config = config
        self.state.mkdir(parents=True, exist_ok=True)

    def current(self):
        version = json.loads((self.state / 'current.json').read_text())['version']
        version_tuple(version)
        return version

    def recover(self):
        with exclusive_lock(self.state / 'update.lock'):
            journal = self.state / 'journal.json'
            if journal.exists():
                old = json.loads(journal.read_text())['old']
                version_tuple(old)
                if not (self.versions / old / 'server.py').is_file():
                    raise UpdateError('Backup ausente; recuperação manual necessária.')
                atomic_json(self.state / 'current.json', {'version': old})
                journal.unlink()
                return True
        return False

    def apply(self, envelope, stop, start, approve, download=fetch):
        with exclusive_lock(self.state / 'update.lock'):
            if not self.config.get('updates_enabled'):
                raise UpdateError('Atualizador desativado.')
            old = self.current()
            data = signed_manifest(envelope, self.config['public_key'], old,
                                   self.config['channel'], self.config['runtime_id'])
            if not approve(data):
                raise UpdateError('Atualização não aprovada; versão atual preservada.')
            archive_data = download(data['url'])
            if len(archive_data) > MAX_DOWNLOAD or hashlib.sha256(archive_data).hexdigest() != data['sha256']:
                raise UpdateError('SHA-256 divergente; download descartado.')
            target = self.versions / data['version']
            if target.exists():
                raise UpdateError('Versão de destino já existe; verifique recuperação antes de tentar.')
            self.versions.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.stage-', dir=self.versions) as temp:
                stage = Path(temp)
                archive = stage / 'download.zip'
                archive.write_bytes(archive_data)
                payload = stage / 'payload'
                payload.mkdir()
                try:
                    extract_payload(archive, payload, data['version'])
                except UpdateError:
                    raise
                except Exception:
                    raise UpdateError('ZIP inválido; versão atual preservada.') from None
                metadata = json.loads((payload / 'version.json').read_text())
                if metadata.get('runtime_id') != self.config['runtime_id'] or metadata.get('channel') != self.config['channel']:
                    raise UpdateError('Identidade do payload divergente.')
                os.replace(payload, target)
            journal = self.state / 'journal.json'
            atomic_json(self.state / 'backup.json', {'version': old})
            atomic_json(journal, {'old': old, 'target': data['version']})
            try:
                # Stop must confirm that the child exited; never overwrite in-use files.
                stop()
            except Exception:
                journal.unlink(missing_ok=True)
                raise UpdateError('Aplicativo ainda em uso; atualização não ativada.') from None
            try:
                atomic_json(self.state / 'current.json', {'version': data['version']})
                start(data['version'])  # Must confirm version-specific HTTP readiness.
            except Exception:
                try:
                    stop()
                    atomic_json(self.state / 'current.json', {'version': old})
                    start(old)
                    journal.unlink()
                except Exception:
                    raise UpdateError('Recuperação pendente; feche o app e reinicie o inicializador.') from None
                raise UpdateError('Falha de atualização; versão anterior restaurada.') from None
            journal.unlink()
            return data['version']
