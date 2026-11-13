"""Portable, loopback-only server. Never loads or saves database credentials."""
from pathlib import Path
import socket
import sys
import threading
import time
import webbrowser

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'backend'))


def main():
    import uvicorn
    from app.main import app

    address = ('127.0.0.1', 8000)
    if '--shared-socket' in sys.argv:
        import base64
        sock = socket.fromshare(base64.b64decode(sys.stdin.readline().strip()))
    elif '--socket-fd' in sys.argv:
        sock = socket.socket(fileno=int(sys.argv[sys.argv.index('--socket-fd') + 1]))
    else:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if sys.platform == 'win32':
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(address)
            sock.listen(128)
        except OSError:
            sock.close()
            print('Nao foi possivel abrir a porta 8000. Feche outra instancia do HUGINN ou o programa que usa essa porta.')
            return 1
    server = uvicorn.Server(uvicorn.Config(app, host=address[0], port=address[1], access_log=False, timeout_graceful_shutdown=10))
    if '--stop-file' in sys.argv:
        stop_file = Path(sys.argv[sys.argv.index('--stop-file') + 1])
        def watch_stop():
            while not server.should_exit:
                if stop_file.exists():
                    server.should_exit = True
                    return
                time.sleep(.2)
        threading.Thread(target=watch_stop, daemon=True).start()

    def open_when_ready():
        for _ in range(300):
            if server.started:
                if '--no-browser' not in sys.argv:
                    webbrowser.open('http://127.0.0.1:8000')
                return
            if server.should_exit:
                return
            time.sleep(0.1)

    print('HUGINN IA - http://127.0.0.1:8000')
    print('Mantenha esta janela aberta. Para encerrar, pressione Ctrl+C.')
    print('Oracle: teste somente leitura, sem salvar credenciais.')
    threading.Thread(target=open_when_ready, daemon=True).start()
    try:
        server.run(sockets=[sock])
    finally:
        sock.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
