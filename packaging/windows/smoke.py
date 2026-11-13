"""Exercise an extracted ZIP. Default: execute its Windows runtime.
--python permits Linux checks of the same application, NOT Windows validation.
"""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import zipfile


def smoke(package, interpreter=None):
    with tempfile.TemporaryDirectory(prefix='HUGINN smoke with spaces ') as temp:
        with zipfile.ZipFile(package) as bundle:
            assert bundle.testzip() is None
            bundle.extractall(temp)
        root = Path(temp) / 'HUGINN-IA-Windows-x64'
        assert (root / 'runtime/python.exe').read_bytes()[:2] == b'MZ'
        assert (root / 'runtime/vcruntime140.dll').is_file()
        assert (root / 'runtime/vcruntime140_1.dll').is_file()
        assert not list(root.rglob('.env'))
        # Runtime pip includes public CA bundles, not database credentials.
        assert not list(root.rglob('*.key'))
        for module in ['oracledb', 'cryptography', 'pydantic_core', 'fastapi', 'uvicorn']:
            assert (root / 'runtime/Lib/site-packages' / module).is_dir()
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 8000))
        python = str(interpreter or root / 'runtime/python.exe')
        command = [python, '-I', str(root / 'launcher.py'), '--no-browser']
        with tempfile.TemporaryFile() as log:
            process = subprocess.Popen(command, cwd=temp, stdout=log, stderr=log)
            try:
                for _ in range(150):
                    if process.poll() is not None:
                        log.seek(0)
                        raise AssertionError(log.read().decode(errors='replace'))
                    try:
                        with urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=1) as response:
                            assert json.load(response)['status'] == 'ok'
                        break
                    except (OSError, urllib.error.URLError):
                        time.sleep(.1)
                else:
                    raise AssertionError('Servidor nao iniciou')
                base = 'http://127.0.0.1:8000'
                with urllib.request.urlopen(base) as response:
                    html = response.read().decode()
                    assert 'id="root"' in html and '/assets/' in html
                xml = (root / 'exemplos/nota-demo.xml').read_bytes()
                boundary = 'HUGINN_SMOKE_BOUNDARY'
                body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="demo.xml"\r\nContent-Type: application/xml\r\n\r\n'.encode()
                        + xml + f'\r\n--{boundary}--\r\n'.encode())
                request = urllib.request.Request(base + '/api/nfe/importar', data=body,
                    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
                with urllib.request.urlopen(request) as response:
                    invoice = json.load(response)
                    assert invoice['numero'] == '12'
                    assert invoice['itens'][0]['valor_total'] == '21.00'
                assert (root / 'backend/app/schema_diagnostic.py').is_file()
                for endpoint in ['/api/oracle/testar', '/api/oracle/diagnostico']:
                    request = urllib.request.Request(base + endpoint,
                        data=json.dumps(dict(host='127.0.0.1', port=1, service='SYNTHETIC', user='synthetic', password='synthetic-test-only')).encode(),
                        headers={'Content-Type': 'application/json', 'Origin': base})
                    try:
                        urllib.request.urlopen(request)
                        raise AssertionError('Porta sem Oracle nao deveria conectar')
                    except urllib.error.HTTPError as error:
                        assert error.code == 502
                        assert 'synthetic-test-only' not in error.read().decode()
                duplicate = subprocess.run(command, cwd=temp, capture_output=True, timeout=20)
                assert duplicate.returncode == 1
                assert b'8000' in duplicate.stdout
                print('PASS: ZIP, runtime layout, startup from path with spaces, production UI, API, XML, Oracle/metadata failure and occupied port')
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('package', type=Path)
    parser.add_argument('--python', type=Path)
    args = parser.parse_args()
    # Preserve a venv executable's symlink path; resolving it loses the venv.
    smoke(args.package.resolve(), args.python.absolute() if args.python else None)
