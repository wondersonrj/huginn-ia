"""Build an unsigned homologation installer, never publish or claim Authenticode."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def build(package, destination):
    destination = Path(destination).resolve(); destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='HUGINN installer ') as temp:
        temp = Path(temp)
        with zipfile.ZipFile(package) as archive:
            archive.extractall(temp)
        payload = temp / 'HUGINN-IA-Windows-x64'
        info = json.loads((payload / 'BUILD-INFO.json').read_text())
        if info['channel'] != 'teste':
            raise RuntimeError('Installer MVP supports homologation/test channel only')
        source = ROOT / 'packaging/windows'
        for name in ['installer_state.py', 'installer_migration.py']:
            shutil.copy2(source / name, payload / name)
        shutil.copy2(payload / 'versions' / info['version'] / 'backend/app/windows_secrets.py', payload / 'maintenance_windows.py')
        vswhere = Path(r'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe')
        visual = subprocess.check_output([str(vswhere), '-latest', '-products', '*', '-requires',
            'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-property', 'installationPath'], text=True).strip()
        compiler = Path(r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe')
        if not visual or not compiler.is_file():
            raise RuntimeError('Windows CI requires MSVC and Inno Setup 6')
        script = temp / 'compile.cmd'
        script.write_text(f'@echo off\ncall "{visual}\\Common7\\Tools\\VsDevCmd.bat" -arch=x64\n'
                          f'cl /nologo /O2 /W4 /MT /DUNICODE /D_UNICODE /Fe:"{payload / "HUGINN-IA.exe"}" "{source / "installer/launch.c"}" user32.lib /link /SUBSYSTEM:WINDOWS\n', encoding='utf-8')
        subprocess.run(['cmd.exe', '/d', '/c', str(script)], check=True, cwd=temp)
        cfg = json.loads((payload / 'bootstrap.json').read_text())
        files = {p.relative_to(payload).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in payload.rglob('*') if p.is_file() and p.relative_to(payload).parts[0] not in {'runtime', 'state'}
                 and '__pycache__' not in p.parts}
        (payload / 'installer-inventory.json').write_text(json.dumps(dict(format=1, version=info['version'],
            runtime_id=cfg['runtime_id'], channel=cfg['channel'], source_commit=info['source_commit'], files=files)))
        recipe = temp / 'installer.iss'
        shutil.copy2(source / 'installer/HUGINN.iss', recipe)
        runtime_delete = []
        for path in sorted((payload / 'runtime').rglob('*')):
            if path.is_file():
                name = path.relative_to(payload).as_posix().replace('/', '\\')
                if any(c in name for c in '"{}\r\n'):
                    raise RuntimeError('Unsupported runtime filename')
                runtime_delete.append('Type: files; Name: "{app}\\' + name + '"')
        (temp / 'runtime-uninstall.iss').write_text('\n'.join(runtime_delete) + '\n', encoding='utf-8')
        subprocess.run([str(compiler), f'/DPayload={payload}', f'/DOutput={destination}',
            f'/DAppVersion={info["version"]}', f'/DSourceCommit={info["source_commit"][:12]}', f'/DRuntimeId={json.loads((payload / "bootstrap.json").read_text())["runtime_id"]}',
            str(recipe)], check=True)
    installer = destination / 'HUGINN-IA-Setup.exe'
    digest = hashlib.sha256(installer.read_bytes()).hexdigest()
    (destination / 'HUGINN-IA-Setup.exe.sha256').write_text(f'{digest}  {installer.name}\n')
    (destination / 'INSTALLER-INFO.json').write_text(json.dumps(dict(info, installer_sha256=digest,
        authenticode_signed=False, distribution='CI homologation only; not a published release'), indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.package, args.output)
