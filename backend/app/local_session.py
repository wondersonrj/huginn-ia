"""Desktop session bootstrap: no long-lived token is sent to JavaScript/URLs.
Windows verifies the owner SID of the peer TCP process before minting a cookie.
"""
import ctypes
from ctypes import wintypes
from functools import lru_cache
import hashlib
import hmac
import os
import re
import secrets
import socket
import time
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import JSONResponse
from app.windows_secrets import windows_identity

router = APIRouter()
_sessions = {}


def app_port():
    value = int(os.environ.get('HUGINN_APP_PORT', '8000'))
    if not 1024 <= value <= 65535:
        raise ValueError('Invalid local port')
    return value


def origin():
    return f'http://127.0.0.1:{app_port()}'


def automatic():
    return os.name == 'nt' and os.environ.get('HUGINN_DESKTOP_SESSION') == '1'


@lru_cache(maxsize=1)
def current_sid():
    return windows_identity()


def process_sid(pid):
    advapi = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    process = kernel.OpenProcess(0x1000, False, pid)
    if not process:
        return None
    token = wintypes.HANDLE()
    try:
        if not advapi.OpenProcessToken(process, 8, ctypes.byref(token)):
            return None
        size = wintypes.DWORD()
        advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        if not 0 < size.value < 65536:
            return None
        buffer = ctypes.create_string_buffer(size.value)
        if not advapi.GetTokenInformation(token, 1, buffer, size, ctypes.byref(size)):
            return None
        sid = ctypes.c_void_p.from_buffer(buffer).value
        text = ctypes.c_void_p()
        if not advapi.ConvertSidToStringSidW(sid, ctypes.byref(text)):
            return None
        try:
            return ctypes.wstring_at(text)
        finally:
            kernel.LocalFree(text)
    finally:
        if token:
            kernel.CloseHandle(token)
        kernel.CloseHandle(process)


def same_user_peer(request):
    if not automatic() or not request.client or request.client.host != '127.0.0.1':
        return False
    try:
        class Row(ctypes.Structure):
            _fields_ = [(name, wintypes.DWORD) for name in ('state', 'local_addr', 'local_port', 'remote_addr', 'remote_port', 'pid')]
        library = ctypes.WinDLL('iphlpapi', use_last_error=True)
        function = library.GetExtendedTcpTable
        function.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), wintypes.BOOL, wintypes.ULONG, ctypes.c_int, wintypes.ULONG]
        function.restype = wintypes.DWORD
        for _ in range(3):
            size = wintypes.DWORD()
            function(None, ctypes.byref(size), False, 2, 5, 0)
            if not 4 <= size.value <= 8 * 1024 * 1024:
                return False
            buffer = ctypes.create_string_buffer(size.value)
            if function(buffer, ctypes.byref(size), False, 2, 5, 0) != 0:
                continue
            count = wintypes.DWORD.from_buffer(buffer).value
            if 4 + count * ctypes.sizeof(Row) > size.value:
                return False
            for index in range(count):
                row = Row.from_buffer(buffer, 4 + index * ctypes.sizeof(Row))
                if (row.state == 5 and socket.ntohs(row.local_port & 0xffff) == request.client.port
                        and socket.ntohs(row.remote_port & 0xffff) == app_port()
                        and row.local_addr == 0x0100007f and row.remote_addr == 0x0100007f):
                    return process_sid(row.pid) == current_sid()
            return False
    except Exception:
        return False  # No Origin-only or anonymous fallback when SID lookup fails.
    return False


def cookie_name():
    installation = os.environ.get('HUGINN_INSTALLATION_ID', '')
    return 'huginn_session_' + hashlib.sha256(f'{installation}:{app_port()}'.encode()).hexdigest()[:16]


def local_request(request, require_origin=True):
    return (request.client and request.client.host == '127.0.0.1'
            and request.headers.get('host') == f'127.0.0.1:{app_port()}'
            and (request.headers.get('origin') == origin() if require_origin else True))


def session_authorized(request):
    if not automatic() or not local_request(request):
        return False
    value = request.cookies.get(cookie_name(), '')
    expires = _sessions.get(hashlib.sha256(value.encode()).hexdigest(), 0)
    return expires > time.monotonic() and same_user_peer(request)


@router.post('/api/local-session')
async def bootstrap(request: Request):
    if not automatic():
        raise HTTPException(404, 'Modo desktop indisponível')
    if (not local_request(request) or request.headers.get('content-type', '').split(';')[0] != 'application/json'
            or not same_user_peer(request)):
        raise HTTPException(403, 'Navegador não pertence ao usuário Windows desta aplicação')
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > 2:
            raise HTTPException(422, 'Solicitação local inválida')
        body.extend(chunk)
    if body != b'{}':
        raise HTTPException(422, 'Solicitação local inválida')
    now = time.monotonic()
    for key in list(_sessions):
        if _sessions[key] <= now:
            _sessions.pop(key, None)
    existing = request.cookies.get(cookie_name(), '')
    if _sessions.get(hashlib.sha256(existing.encode()).hexdigest(), 0) > now:
        return JSONResponse({'automatic': True}, headers={'Cache-Control': 'no-store'})
    if len(_sessions) >= 16:
        raise HTTPException(429, 'Encerre e reabra o HUGINN pelo atalho para renovar as sessões')
    value = secrets.token_urlsafe(32)
    _sessions[hashlib.sha256(value.encode()).hexdigest()] = now + 12 * 60 * 60
    response = JSONResponse({'automatic': True, 'message': 'Acesso local Windows confirmado'}, headers={'Cache-Control': 'no-store'})
    response.set_cookie(cookie_name(), value, httponly=True, samesite='strict', path='/api')
    return response


@router.get('/api/local-instance')
async def identity(request: Request, challenge: str = ''):
    if not automatic() or not local_request(request, False) or not re.fullmatch('[a-f0-9]{64}', challenge):
        raise HTTPException(403, 'Identidade local indisponível')
    version = os.environ.get('HUGINN_RUNNING_VERSION', '')
    installation = os.environ.get('HUGINN_INSTALLATION_ID', '')
    payload = f'{challenge}:{installation}:{version}:{app_port()}'
    proof = hmac.new(os.environ['HUGINN_API_TOKEN'].encode(), payload.encode(), hashlib.sha256).hexdigest()
    return JSONResponse(dict(installation=installation, version=version, port=app_port(), proof=proof), headers={'Cache-Control': 'no-store'})


@router.post('/api/local-stop')
async def stop(request: Request):
    if not session_authorized(request) or await request.body() != b'{}':
        raise HTTPException(403, 'Use a sessão local autenticada')
    from pathlib import Path
    state = os.environ.get('HUGINN_STATE_DIR')
    if not state:
        raise HTTPException(503, 'Supervisor indisponível')
    (Path(state) / 'shutdown').touch()
    return JSONResponse({'message': 'Aplicativo sendo encerrado; outros serviços não serão alterados.'}, headers={'Cache-Control': 'no-store'})


@router.post('/api/local-reset')
async def reset_access(request: Request):
    if not session_authorized(request) or await request.body() != b'{}':
        raise HTTPException(403, 'Use a sessão local autenticada')
    from pathlib import Path
    state = os.environ.get('HUGINN_STATE_DIR')
    if not state:
        raise HTTPException(503, 'Supervisor indisponível')
    (Path(state) / 'reset-access').touch()
    (Path(state) / 'shutdown').touch()
    return JSONResponse({'message': 'Acesso será recriado na próxima abertura; conexões preservadas.'}, headers={'Cache-Control': 'no-store'})
