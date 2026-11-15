"""Native-desktop bootstrap utilities. Tokens stay in CurrentUser DPAPI and server memory."""
from contextlib import contextmanager
import ctypes
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import urllib.request

MUTEX = r'Local\HUGINN-IA-Installed'


def backend_path(root, version):
    import sys
    sys.path.insert(0, str(Path(root) / 'versions' / version / 'backend'))


def installation_id(root):
    return hashlib.sha256(str(Path(root).resolve()).casefold().encode()).hexdigest()


def access_token(root, version, reset=False):
    import time
    backend_path(root, version)
    from app.connection_store import Conflict
    for attempt in range(40):
        try:
            return _access_token(root, version, reset)
        except Conflict:
            if attempt == 39:
                raise
            time.sleep(.25)


def _access_token(root, version, reset=False):
    backend_path(root, version)
    from app.connection_store import current_store, safe_path
    from app.windows_secrets import VaultError, private_permissions
    os.environ['HUGINN_STATE_DIR'] = str(Path(root) / 'state')
    store = current_store()
    if store is None:
        raise VaultError('Desktop requires Windows user protection')
    with store.locked():
        path = store.root / 'local-token.bin'
        safe_path(path)
        entropy = hashlib.sha256(f'HUGINN:desktop:v1:{store.installation}:{store.identity}'.encode()).digest()
        if path.exists() and not reset:
            private_permissions(path, store.identity)
            if not 1 <= path.stat().st_size <= 16384:
                raise VaultError('Invalid access vault')
            value = store.protector.unprotect(path.read_bytes(), entropy).decode('ascii')
            if len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
                raise VaultError('Invalid access vault')
            return value
        value = secrets.token_hex(32)
        store.atomic(path, store.protector.protect(value.encode(), entropy))
        return value


def verify_instance(root, expected_version, token):
    """Untrusted descriptor/service is never opened in the browser without HMAC proof."""
    try:
        path = Path(root) / 'state' / 'instance.json'
        if path.stat().st_size > 2048:
            return None
        data = json.loads(path.read_text())
        port = data['port']
        if type(port) is not int or not 1024 <= port <= 65535:
            return None
        challenge = secrets.token_hex(32)
        url = f'http://127.0.0.1:{port}'
        # Do not follow redirects or inherit a user-configured network proxy.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs): return None
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(url + '/api/local-instance?challenge=' + challenge, timeout=1) as response:
            value = json.loads(response.read(2049))
        identity = installation_id(root)
        payload = f'{challenge}:{identity}:{expected_version}:{port}'
        expected = hmac.new(token.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if (value['installation'] == identity and value['version'] == expected_version
                and value['port'] == port and hmac.compare_digest(value['proof'], expected)):
            return url
    except Exception:
        return None
    return None


@contextmanager
def app_mutex():
    if os.name != 'nt':
        yield
        return
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateMutexW(None, False, MUTEX)
    if not handle:
        raise RuntimeError('Application mutex unavailable')
    try:
        yield
    finally:
        kernel.CloseHandle(handle)


def show_error():
    if os.name == 'nt':
        ctypes.windll.user32.MessageBoxW(None,
            'Nao foi possivel iniciar o HUGINN com seguranca. Se a janela ja esta aberta, use Encerrar HUGINN e tente novamente. Nao reinicie o Windows nem finalize outros servicos. Se persistir, consulte o guia de instalacao/recuperacao.',
            'HUGINN IA - inicializacao', 0x10)


def recovery_confirmed():
    return os.name == 'nt' and ctypes.windll.user32.MessageBoxW(None,
        'O acesso local protegido esta indisponivel. Recriar somente o token? As conexoes salvas serao preservadas. Feche o HUGINN antigo antes; nenhum outro processo sera encerrado.',
        'HUGINN IA - recuperar acesso', 0x24) == 6


def diagnostic(root, event):
    # Whitelist fixed event codes: never serialize exception text, URLs or arguments.
    if event not in {'desktop_start_requested', 'desktop_start_failed', 'instance_reused', 'server_ready'}:
        return
    from datetime import datetime, timezone
    try:
        path = Path(root) / 'state' / 'diagnostics.jsonl'
        if path.exists() and path.stat().st_size > 65536:
            path.unlink()
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'event': event, 'at_utc': datetime.now(timezone.utc).isoformat()}) + '\n')
    except OSError:
        pass  # Startup error dialog remains available; never expose an exception.
