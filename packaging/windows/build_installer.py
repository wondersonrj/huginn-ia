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
        shutil.copy2(source / 'installer_state.py', payload / 'installer_state.py')
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
        subprocess.run([str(compiler), f'/DPayload={payload}', f'/DOutput={destination}',
            f'/DAppVersion={info["version"]}', f'/DSourceCommit={info["source_commit"][:12]}', f'/DRuntimeId={json.loads((payload / "bootstrap.json").read_text())["runtime_id"]}',
            str(source / 'installer/HUGINN.iss')], check=True)
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
