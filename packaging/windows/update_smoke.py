"""Real process A->B->failed C->B integration. Ephemeral signed fixtures only.
Windows: executes bundled python.exe. Linux --python validates Linux only.
No Oracle API or driver connection is invoked.
"""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from launcher import Supervisor
from updater import UpdateError, atomic_json


def run(package, python=None):
    with tempfile.TemporaryDirectory(prefix='HUGINN update recovery ') as temporary:
        with zipfile.ZipFile(package) as z:
            z.extractall(temporary)
        root = Path(temporary) / 'HUGINN-IA-Windows-x64'
        config = json.loads((root / 'bootstrap.json').read_text())
        key = Ed25519PrivateKey.generate()
        config['public_key'] = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
        config['updates_enabled'] = True  # test fixture only; shipped bootstrap stays disabled
        supervisor = Supervisor(root, config, python)
        engine = supervisor.updater
        old = config['version']
        major, minor, patch = map(int, old.split('.'))
        good = f'{major}.{minor}.{patch + 1}'
        bad = f'{major}.{minor}.{patch + 2}'
        atomic_json(engine.state / 'current.json', {'version': old})
        (engine.state / 'preferences.json').write_text('{"theme":"dark"}')
        def release(version, broken=False):
            buffer = io.BytesIO()
            prefix = f'HUGINN-IA-Windows-x64/versions/{version}/'
            with zipfile.ZipFile(buffer, 'w') as z:
                for path in (root / 'versions' / old).rglob('*'):
                    if path.is_file() and '__pycache__' not in path.parts:
                        relative = path.relative_to(root / 'versions' / old).as_posix()
                        if relative == 'version.json':
                            z.writestr(prefix + relative, json.dumps(config | {'version':version}))
                        elif relative == 'server.py' and broken:
                            z.writestr(prefix + relative, 'raise SystemExit(42)\n')
                        else:
                            z.writestr(prefix + relative, path.read_bytes())
            data = buffer.getvalue()
            signed = dict(version=version, channel=config['channel'], notes='Synthetic integration fixture',
                          url=f'https://github.com/wondersonrj/huginn-ia/releases/download/v{version}/HUGINN-IA-Windows-x64.zip',
                          sha256=hashlib.sha256(data).hexdigest(), runtime_id=config['runtime_id'], bootstrap_version=1)
            canonical = json.dumps(signed,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
            return dict(signed=signed,signature=base64.b64encode(key.sign(canonical)).decode()), data
        try:
            supervisor.start(old)
            manifest, payload = release(good)
            engine.apply(manifest, supervisor.stop, supervisor.start, lambda data: True, lambda url: payload)
            assert engine.current() == good
            manifest, payload = release(bad, broken=True)
            try:
                engine.apply(manifest, supervisor.stop, supervisor.start, lambda data: True, lambda url: payload)
                raise AssertionError('Broken version should fail')
            except UpdateError as error:
                assert 'anterior restaurada' in str(error)
            assert engine.current() == good
            assert supervisor.process.poll() is None
            assert (engine.state / 'preferences.json').read_text() == '{"theme":"dark"}'
            assert not (engine.state / 'journal.json').exists()
            print(f'PASS: real processes {old}->{good}, failed {bad}->{good} rollback, version health and preferences; platform={sys.platform}')
        finally:
            supervisor.stop()
            if supervisor.socket is not None:
                supervisor.socket.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('package',type=Path)
    p.add_argument('--python',type=Path)
    a=p.parse_args()
    run(a.package.resolve(), a.python.absolute() if a.python else None)
