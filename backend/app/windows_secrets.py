"""Windows CurrentUser DPAPI and exact private DACL. No portable encryption fallback."""
import csv
import ctypes
from ctypes import wintypes
import io
import os
from pathlib import Path
import re
import subprocess


class VaultError(Exception):
    """Safe public error type; native exceptions must never reach HTTP/logs."""


def windows_identity():
    if os.name != 'nt':
        raise VaultError('Windows protection unavailable')
    buffer = ctypes.create_unicode_buffer(32768)
    if not ctypes.windll.kernel32.GetSystemDirectoryW(buffer, len(buffer)):
        raise VaultError('Windows identity unavailable')
    result = subprocess.run([str(Path(buffer.value) / 'whoami.exe'), '/user', '/fo', 'csv', '/nh'],
                            capture_output=True, check=False)
    # Only the ASCII SID is used; ignore locale-specific encoding of the username.
    for row in csv.reader(io.StringIO(result.stdout.decode('utf-8', errors='replace'))):
        if result.returncode == 0 and len(row) == 2 and re.fullmatch(r'S-1-(?:\d+-)+\d+', row[1].strip()):
            return row[1].strip()
    raise VaultError('Windows identity unavailable')


def local_app_data():
    if os.name != 'nt':
        raise VaultError('Windows protection unavailable')
    buffer = ctypes.create_unicode_buffer(32768)
    # CSIDL_LOCAL_APPDATA, current user. Do not trust an arbitrary request/env path.
    if ctypes.windll.shell32.SHGetFolderPathW(None, 0x1c, None, 0, buffer) != 0:
        raise VaultError('Windows profile unavailable')
    return Path(buffer.value)


def private_permissions(path, sid):
    if os.name != 'nt':
        if path.stat().st_uid != os.getuid():
            raise VaultError('Foreign file owner')
        path.chmod(0o700 if path.is_dir() else 0o600)
        return
    advapi = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
    advapi.SetFileSecurityW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
    advapi.SetFileSecurityW.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    descriptor = ctypes.c_void_p()
    # Replace the DACL, including previous explicit ACEs; user + SYSTEM only.
    sddl = f'D:P(A;OICI;FA;;;{sid})(A;OICI;FA;;;SY)'
    if not advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, ctypes.byref(descriptor), None):
        raise VaultError('Private ACL unavailable')
    try:
        if not advapi.SetFileSecurityW(str(path), 0x80000004, descriptor):
            raise VaultError('Private ACL unavailable')
    finally:
        kernel.LocalFree(descriptor)


class DPAPI:
    def __init__(self):
        if os.name != 'nt':
            raise VaultError('Windows protection unavailable')

    def _crypt(self, value, entropy, decrypt):
        class Blob(ctypes.Structure):
            _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
        def blob(data):
            array = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
            return Blob(len(data), array), array
        crypt = ctypes.WinDLL('crypt32', use_last_error=True)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        source, source_buffer = blob(value)
        salt, salt_buffer = blob(entropy)
        target = Blob()
        if decrypt:
            function = crypt.CryptUnprotectData
            function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
            arguments = (ctypes.byref(source), None, ctypes.byref(salt), None, None, 1, ctypes.byref(target))
        else:
            function = crypt.CryptProtectData
            function.argtypes = [ctypes.POINTER(Blob), wintypes.LPCWSTR, ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
            arguments = (ctypes.byref(source), 'HUGINN Oracle credential v1', ctypes.byref(salt), None, None, 1, ctypes.byref(target))
        function.restype = wintypes.BOOL
        try:
            # UI_FORBIDDEN only. Never CRYPTPROTECT_LOCAL_MACHINE.
            if not function(*arguments):
                raise VaultError('Credential unavailable for this Windows user/installation')
            return ctypes.string_at(target.data, target.size)
        finally:
            ctypes.memset(source_buffer, 0, len(value))
            if target.data:
                ctypes.memset(target.data, 0, target.size)
                kernel.LocalFree(target.data)

    def protect(self, value, entropy):
        return self._crypt(value, entropy, False)

    def unprotect(self, value, entropy):
        return self._crypt(value, entropy, True)


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

