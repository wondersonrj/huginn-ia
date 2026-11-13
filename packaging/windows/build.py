"""Build a portable Windows x64 ZIP from Linux or Windows, without cross-compiling.
Run after npm ci && npm run build in frontend. Uses official NuGet CPython.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

REPO = Path(__file__).resolve().parents[2]
PYTHON_VERSION = '3.12.10'
RUNTIME_URL = f'https://api.nuget.org/v3-flatcontainer/python/{PYTHON_VERSION}/python.{PYTHON_VERSION}.nupkg'
RUNTIME_SHA256 = '0eb85c2dfccccf1b17352de4c397f69194035b7d37149eacc16f1147d93de3b8'


def build(output, version=None, channel=None, enable_updates=False):
    config = json.loads((REPO / "packaging/windows/version.json").read_text())
    config["version"] = version or config["version"]
    config["channel"] = channel or config["channel"]
    sys.path.insert(0, str(REPO / "packaging/windows"))
    from updater import version_tuple
    version_tuple(config["version"])
    if config["channel"] not in {"teste", "estavel"}:
        raise SystemExit("Canal inválido")
    config["runtime_id"] = hashlib.sha256((REPO / "packaging/windows/requirements.lock").read_bytes()).hexdigest()
    config["public_key"] = (REPO / "packaging/windows/release-public-key.txt").read_text().strip()
    if enable_updates and not config["public_key"]:
        raise SystemExit("Chave pública de release ausente; atualização desativada")
    config["updates_enabled"] = bool(enable_updates)
    if not (REPO / 'frontend/dist/index.html').is_file():
        raise SystemExit('Execute npm ci e npm run build em frontend antes de empacotar.')
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='huginn-windows-') as temp:
        work = Path(temp)
        root = work / 'HUGINN-IA-Windows-x64'
        root.mkdir()
        runtime = root / 'runtime'
        archive = work / 'python.nupkg'
        urllib.request.urlretrieve(RUNTIME_URL, archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != RUNTIME_SHA256:
            raise SystemExit('Checksum do runtime Python divergente; build interrompido.')
        with zipfile.ZipFile(archive) as package:
            for entry in package.infolist():
                if not entry.filename.startswith('tools/') or entry.is_dir():
                    continue
                relative = Path(entry.filename).relative_to('tools')
                if '..' in relative.parts:
                    raise SystemExit('Caminho inseguro no runtime')
                target = runtime / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(package.read(entry))
        subprocess.run([
            sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
            '--no-compile', '--only-binary=:all:', '--platform', 'win_amd64',
            '--python-version', '3.12', '--implementation', 'cp', '--abi', 'cp312',
            '--target', str(runtime / 'Lib/site-packages'), '--require-hashes',
            '-r', str(REPO / 'packaging/windows/requirements.lock'),
        ], check=True)
        payload = root / 'versions' / config['version']
        payload.mkdir(parents=True)
        shutil.copytree(REPO / 'backend/app', payload / 'backend/app',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copytree(REPO / 'frontend/dist', payload / 'frontend/dist')
        shutil.copy2(REPO / 'packaging/windows/server.py', payload / 'server.py')
        (payload / 'version.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
        (root / 'bootstrap.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
        for name in ['launcher.py', 'updater.py', 'INICIAR_HUGINN.bat', 'LEIA-ME.txt']:
            source = REPO / 'packaging/windows' / name
            if name.endswith(('.bat', '.txt')):
                (root / name).write_bytes(source.read_text().replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8'))
            else:
                shutil.copy2(source, root / name)
        (root / 'docs').mkdir()
        for doc in ['ATUALIZACOES_WINDOWS.md', 'CONEXAO_ORACLE.md']:
            shutil.copy2(REPO / 'docs' / doc, root / 'docs' / doc)
        (root / 'exemplos').mkdir()
        # Extract only the existing synthetic fixture; never include local config.
        import ast
        module = ast.parse((REPO / 'backend/tests/test_nfe.py').read_text())
        xml = next(ast.literal_eval(n.value) for n in module.body
                   if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'XML' for t in n.targets))
        (root / 'exemplos/nota-demo.xml').write_bytes(xml)
        info = {'python': PYTHON_VERSION, 'platform': 'Windows x64',
                'runtime_url': RUNTIME_URL, 'runtime_sha256': RUNTIME_SHA256,
                'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
                'oracle_real_validated': False, 'version': config['version'],
                'channel': config['channel'], 'updates_enabled': config['updates_enabled']}
        (root / 'BUILD-INFO.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
        destination = output / 'HUGINN-IA-Windows-x64.zip'
        with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
            for path in sorted(root.rglob('*')):
                if path.is_file():
                    bundle.write(path, path.relative_to(work))
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        destination.with_suffix('.zip.sha256').write_text(f'{digest}  {destination.name}\n')
        print(f'Pacote: {destination} ({destination.stat().st_size} bytes) SHA256 {digest}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=REPO / 'release')
    parser.add_argument('--version')
    parser.add_argument('--channel', choices=['teste', 'estavel'])
    parser.add_argument('--enable-updates', action='store_true')
    args = parser.parse_args()
    build(args.output.resolve(), args.version, args.channel, args.enable_updates)
