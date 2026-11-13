"""Immutable supervisor: child lifecycle, native approval and updater queue."""
from pathlib import Path
import ctypes
import json
import os
import secrets
import signal
import socket
import base64
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from updater import Updater, UpdateError, atomic_json, discover, exclusive_lock


def open_browser(url):
    # Explicit Chromium browser preference; never use Internet Explorer.
    if sys.platform == 'win32':
        bases = [os.environ.get('PROGRAMFILES', ''), os.environ.get('PROGRAMFILES(X86)', ''), os.environ.get('LOCALAPPDATA', '')]
        for relative in ['Google/Chrome/Application/chrome.exe', 'Microsoft/Edge/Application/msedge.exe']:
            for base in bases:
                candidate = Path(base) / relative
                if candidate.is_file():
                    subprocess.Popen([str(candidate), url], close_fds=True)
                    return
        try:
            os.startfile('microsoft-edge:' + url)
            return
        except OSError:
            pass
    print('Abra em Chrome, Edge ou Firefox: ' + url)


def approve_release(data):
    if sys.platform != 'win32':
        return False  # Linux tests inject approval into the engine, never auto approve.
    message = f"Instalar HUGINN IA {data['version']} ({data['channel']})?\nO aplicativo será reiniciado.\n\n{data['notes']}"
    return ctypes.windll.user32.MessageBoxW(None, message, 'Aprovar atualização HUGINN IA', 0x24) == 6


class Supervisor:
    def __init__(self, root, config, python=None):
        self.root = Path(root)
        self.config = config
        self.updater = Updater(root, config)
        self.state = self.updater.state
        self.python = str(python or (self.root / 'runtime/python.exe' if sys.platform == 'win32' else sys.executable))
        self.process = None
        self.socket = None
        self.token = secrets.token_hex(32)
        self.available = None

    def status(self, message='Pronto'):
        data = self.available['signed'] if self.available else {}
        atomic_json(self.state / 'status.json', {
            'version': self.updater.current(), 'channel': self.config['channel'],
            'enabled': bool(self.config.get('updates_enabled') and self.config.get('public_key')),
            'available': data.get('version'), 'notes': data.get('notes', ''),
            'status': message, 'restart_required': bool(data),
        })

    def start(self, version):
        stop_file = self.state / 'stop'
        stop_file.unlink(missing_ok=True)
        env = os.environ.copy()
        env['HUGINN_STATE_DIR'] = str(self.state)
        env['HUGINN_UPDATE_TOKEN'] = self.token
        if self.socket is None:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if sys.platform == 'win32':
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(('127.0.0.1', 8000))
            self.socket.listen(128)
        command = [self.python, '-I', str(self.root / 'versions' / version / 'server.py'),
                   '--no-browser', '--stop-file', str(stop_file)]
        if sys.platform == 'win32':
            self.process = subprocess.Popen(command + ['--shared-socket'], cwd=self.root, env=env, stdin=subprocess.PIPE)
            self.process.stdin.write(base64.b64encode(self.socket.share(self.process.pid)) + b'\n')
            self.process.stdin.close()
        else:
            descriptor = self.socket.fileno()
            self.process = subprocess.Popen(command + ['--socket-fd', str(descriptor)], cwd=self.root,
                                            env=env, pass_fds=(descriptor,))
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise UpdateError('Servidor encerrou durante a inicialização.')
            try:
                with urllib.request.urlopen('http://127.0.0.1:8000/api/version', timeout=.5) as response:
                    if json.load(response)['version'] == version:
                        return
            except (OSError, ValueError, KeyError):
                pass
            time.sleep(.1)
        raise UpdateError('Servidor não confirmou a versão em tempo hábil.')

    def stop(self):
        if self.process is None or self.process.poll() is not None:
            return
        (self.state / 'stop').touch()
        try:
            self.process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            raise UpdateError('Servidor ainda em uso; aguarde encerrar as operações.') from None

    def check(self):
        self.status('Verificando releases aprovadas…')
        self.available = discover(self.config, self.updater.current())
        self.status('Atualização disponível; aguarda aprovação.' if self.available else 'Nenhuma atualização disponível.')

    def run(self, no_browser=False):
        with exclusive_lock(self.state / 'supervisor.lock'):
            recovered = self.updater.recover()
            pointer = self.state / 'current.json'
            if not pointer.exists():
                atomic_json(pointer, {'version': self.config['version']})
            self.status('Versão anterior recuperada.' if recovered else 'Pronto')
            (self.state / "shutdown").unlink(missing_ok=True)
            try:
                self.start(self.updater.current())
                if not no_browser:
                    open_browser('http://127.0.0.1:8000')
                if self.config.get('updates_enabled') and self.config['channel'] == 'teste':
                    try:
                        self.check()
                    except UpdateError as error:
                        self.status(str(error))
                request = self.state / 'request.json'
                while self.process.poll() is None and not (self.state / "shutdown").exists():
                    if request.exists():
                        try:
                            command = json.loads(request.read_text())
                            request.unlink()
                            if not secrets.compare_digest(command.get('token', ''), self.token):
                                continue
                            if command.get('action') == 'check':
                                self.check()
                            elif command.get('action') == 'apply' and self.available:
                                self.status('Atualização solicitada; confirme na janela do Windows. Haverá reinicialização.')
                                self.updater.apply(self.available, self.stop, self.start, approve_release)
                                self.available = None
                                self.status('Atualização instalada e versão confirmada.')
                                if not no_browser:
                                    open_browser('http://127.0.0.1:8000')
                        except UpdateError as error:
                            self.status(str(error))
                        except Exception:
                            self.status('Solicitação inválida; versão atual preservada.')
                    time.sleep(.2)
            finally:
                self.stop()
                if self.socket is not None:
                    self.socket.close()


def main():
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        config = json.loads((ROOT / 'bootstrap.json').read_text())
        Supervisor(ROOT, config).run('--no-browser' in sys.argv)
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception:
        print('Falha ao iniciar/recuperar HUGINN. Confira porta 8000, pasta extraída e documentação de recuperação.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
