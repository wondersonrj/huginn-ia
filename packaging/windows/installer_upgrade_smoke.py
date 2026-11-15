"""Real historical Inno EXEs -> current Setup, failure rollback and recovery.
Runs each history in a fresh Python process; no customer network/credentials.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import winreg
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from playwright.sync_api import expect, sync_playwright

KEY = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{1F07B592-9CB4-4937-B35B-4A197E9AB867}_is1'


def registration():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
        return {name: winreg.QueryValueEx(key, name)[0] for name in ('Inno Setup: App Path', 'DisplayVersion', 'UninstallString')}


def case(args):
    with tempfile.TemporaryDirectory(prefix='HUGINN historical migration ') as temp:
        temp = Path(temp); root = temp / 'Programa anterior com espacos'
        env = {k:v for k,v in os.environ.items() if not k.startswith('HUGINN_')}
        env['HUGINN_API_TOKEN'] = 'short-inherited-token'
        def setup(installer, explicit=True, success=True):
            command = [str(installer), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-']
            if explicit: command += ['/DIR=' + str(root)]
            result = subprocess.run(command, env=env, timeout=180)
            assert (result.returncode == 0) == success, f'Setup result {result.returncode}; expected success={success}'
        if args.case == 'portable':
            with zipfile.ZipFile(args.portable) as archive: archive.extractall(temp / 'portable extraction')
            shutil.move(str(temp / 'portable extraction/HUGINN-IA-Windows-x64'), root)
        else:
            setup(args.old)
            assert Path(registration()['Inno Setup: App Path']).resolve() == root.resolve()
        # An actual portable sibling is not a target for installed-family replacement.
        sibling = temp / 'Outra copia portatil'
        with zipfile.ZipFile(args.portable) as archive: archive.extractall(sibling)
        sentinel = sibling / 'HUGINN-IA-Windows-x64/customer.txt'; sentinel.write_text('portable user data')
        sibling_config = (sibling / 'HUGINN-IA-Windows-x64/bootstrap.json').read_bytes()
        (root / 'customer.txt').write_text('preserve user data')
        (root / 'state').mkdir(exist_ok=True)
        (root / 'state/preferences.json').write_text('{"theme":"custom"}')
        class Foreign(BaseHTTPRequestHandler):
            def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b'FOREIGN-SERVICE')
            def log_message(self, *args): pass
        foreign = HTTPServer(('127.0.0.1', 8000), Foreign)
        threading.Thread(target=foreign.serve_forever, daemon=True).start()
        primary = None
        def start():
            (root / 'state/instance.json').unlink(missing_ok=True)
            command = [str(root / 'HUGINN-IA.exe'), '--no-browser'] if (root / 'HUGINN-IA.exe').exists() else [str(root / 'runtime/python.exe'), '-I', str(root / 'launcher.py'), '--desktop', '--no-browser']
            process = subprocess.Popen(command, env=env)
            for _ in range(250):
                if process.poll() is not None: raise AssertionError('Own launcher exited before health')
                try:
                    info = json.loads((root / 'state/instance.json').read_text())
                    url = f'http://127.0.0.1:{info["port"]}'
                    with urllib.request.urlopen(url + '/api/version', timeout=.5) as response:
                        if json.load(response)['version'] == info['version']: return process, info, url
                except Exception: time.sleep(.1)
            raise AssertionError('Installed application failed to start')
        def snapshot(vault): return {p.name: p.read_bytes() for p in vault.iterdir() if p.name != 'connections.lock'}
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(); page = browser.new_page()
                primary, info, url = start(); old_version = info['version']
                assert old_version == ('0.2.0' if args.case == 'portable' else args.case)
                page.goto(url)
                expect(page.get_by_label('Nome da conexão', exact=True)).to_be_visible()
                for label, value in [('Nome da conexão','Instalador sintético'),('Host da conexão','127.0.0.1'),
                    ('Service Name da conexão','SYNTHETIC'),('Usuário da conexão','synthetic'),('Schema WinThor','WINT'),('Nova senha da conexão','synthetic-installer-only')]:
                    page.get_by_label(label, exact=True).fill(value)
                page.get_by_role('button', name='Salvar conexão', exact=True).click()
                expect(page.get_by_role('button', name='Editar Instalador sintético', exact=True)).to_be_visible()
                spec = importlib.util.spec_from_file_location('legacy_desktop', root / 'desktop.py')
                desktop = importlib.util.module_from_spec(spec); spec.loader.exec_module(desktop)
                token = desktop.access_token(root, old_version)
                from app.connection_store import current_store
                vault = current_store().root
                before = snapshot(vault)
                # A forged descriptor pointing to a foreign service must never trigger a stop/copy.
                descriptor = (root / 'state/instance.json').read_bytes()
                bootstrap_before = (root / 'bootstrap.json').read_bytes()
                (root / 'state/instance.json').write_text('{"port":8000}')
                setup(args.installer, explicit=args.case == 'portable', success=False)
                assert primary.poll() is None and (root / 'bootstrap.json').read_bytes() == bootstrap_before
                assert snapshot(vault) == before
                (root / 'state/instance.json').write_bytes(descriptor)
                # No /DIR for an installed family: registry detection must reuse it.
                setup(args.installer, explicit=args.case == 'portable')
                assert primary.wait(timeout=30) == 0  # authenticated graceful stop, never kill
                assert snapshot(vault) == before
                assert sentinel.read_text() == 'portable user data'
                assert (sibling / 'HUGINN-IA-Windows-x64/bootstrap.json').read_bytes() == sibling_config
                expected = json.loads((root / 'bootstrap.json').read_text())['version']
                assert expected == '0.3.1'
                assert registration()['DisplayVersion'] == expected
                assert (root / 'customer.txt').read_text() == 'preserve user data'
                assert (root / 'state/preferences.json').read_text() == '{"theme":"custom"}'
                # Inject driver double only into this disposable installed copy, after migration.
                shutil.copy2(Path(__file__).parent / 'test_fixtures/oracledb.py', root / 'versions' / expected / 'backend/oracledb.py')
                primary, info, url = start(); page.goto(url)
                expect(page.get_by_role('button', name='Editar Instalador sintético', exact=True)).to_be_visible()
                expect(page.get_by_text('Consultas direcionadas a:', exact=False)).to_have_count(0)
                assert desktop.access_token(root, expected) == token
                assert snapshot(vault) == before
                page.get_by_role('button', name='Selecionar Instalador sintético', exact=True).click()
                expect(page.get_by_text('Consultas direcionadas a: Instalador sintético — TESTE', exact=True)).to_be_visible()
                page.get_by_role('button', name='Verificar conexão WinThor', exact=True).click()
                expect(page.get_by_text('ORACLE — somente leitura', exact=True)).to_be_visible()
                for kind, code, label in [('produtos','101','Produto CI Oracle'),('fornecedores','202','Fornecedor CI Oracle')]:
                    page.get_by_label('Cadastro', exact=True).select_option(kind)
                    page.get_by_label('Código do cadastro', exact=True).fill(code)
                    page.get_by_role('button', name='Buscar cadastros', exact=True).click()
                    expect(page.get_by_role('table', name='Cadastros WinThor').get_by_text(label, exact=True)).to_be_visible()
                # Failure after copying NEW binaries must restore the original bootstrap/registry.
                old_bootstrap = (root / 'bootstrap.json').read_bytes()
                old_launcher = (root / 'HUGINN-IA.exe').read_bytes()
                old_registration = registration()
                setup(args.broken, explicit=False, success=False)
                assert primary.wait(timeout=30) == 0
                assert (root / 'bootstrap.json').read_bytes() == old_bootstrap
                assert (root / 'HUGINN-IA.exe').read_bytes() == old_launcher
                assert registration() == old_registration
                assert json.loads((root / 'state/current.json').read_text())['version'] == expected
                assert snapshot(vault) == before
                primary, info, url = start(); page.goto(url)
                expect(page.get_by_role('button', name='Editar Instalador sintético', exact=True)).to_be_visible()
                page.once('dialog', lambda d:d.accept()); page.get_by_role('button', name='Encerrar HUGINN', exact=True).click()
                assert primary.wait(timeout=30) == 0
                # Simulate interruption after backup/copy, then rerun actual Setup to recover.
                inventory = temp / 'inventory.json'; shutil.copy2(root / 'installer-inventory.json', inventory)
                assert subprocess.run([str(root / 'runtime/python.exe'), '-I', str(root / 'installer_migration.py'), 'prepare',
                    '--root', str(root), '--inventory', str(inventory)], env=env, timeout=60).returncode == 0
                (root / 'launcher.py').write_text('raise SystemExit(42)\n')
                (root / 'state/current.json').write_text('{"version":"99.0.0"}')
                setup(args.installer, explicit=False)
                assert snapshot(vault) == before
                primary, info, url = start(); page.goto(url)
                expect(page.get_by_role('button', name='Editar Instalador sintético', exact=True)).to_be_visible()
                # A normal reinstall with an ACTIVE instance is handled without operator commands.
                setup(args.installer, explicit=False)
                assert primary.wait(timeout=30) == 0
                assert snapshot(vault) == before
                # Start menu shortcut survives and points to the same family/directory.
                import ctypes
                buffer = ctypes.create_unicode_buffer(32768)
                assert ctypes.windll.shell32.SHGetFolderPathW(None, 2, None, 0, buffer) == 0
                assert (Path(buffer.value) / 'HUGINN IA/HUGINN IA.lnk').is_file()
                uninstall = Path(registration()['UninstallString'].strip('"'))
                assert uninstall.parent.resolve() == root.resolve() and re.fullmatch(r'unins\d{3}\.exe', uninstall.name)
                assert subprocess.run([str(uninstall), '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/_?='+str(root)], env=env, timeout=120).returncode == 0
                assert snapshot(vault) == before and (root / 'customer.txt').read_text() == 'preserve user data'
                setup(args.installer)
                primary, info, url = start(); page.goto(url)
                expect(page.get_by_role('button', name='Editar Instalador sintético', exact=True)).to_be_visible()
                page.once('dialog', lambda d:d.accept()); page.get_by_role('button', name='Encerrar HUGINN', exact=True).click()
                assert primary.wait(timeout=30) == 0
                uninstall = Path(registration()['UninstallString'].strip('"'))
                assert subprocess.run([str(uninstall),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/REMOVEDATA=1','/_?='+str(root)], env=env, timeout=120).returncode == 0
                assert not vault.exists() and not (root / '.installer-backup').exists()
                assert (root / 'customer.txt').read_text() == 'preserve user data'
                with urllib.request.urlopen('http://127.0.0.1:8000') as response: assert response.read() == b'FOREIGN-SERVICE'
                browser.close()
                print(f'PASS: historical {old_version} ({args.case}) -> 0.3.1 Setup registry/in-place, authenticated stop, DPAPI/token bytes, Oracle fake queries, broken EXE rollback, interrupted recovery, reinstall, shortcuts, uninstall keep/remove, portable coexistence, foreign-service/user-files preservation; no reboot')
        finally:
            if primary and primary.poll() is None:
                (root / 'state/shutdown').touch(); primary.wait(timeout=40)
            foreign.shutdown(); foreign.server_close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--installer', type=Path, required=True)
    parser.add_argument('--broken', type=Path, required=True)
    parser.add_argument('--old-020', type=Path)
    parser.add_argument('--old-030', type=Path)
    parser.add_argument('--portable', type=Path, required=True)
    parser.add_argument('--case', choices=['0.2.0','0.3.0','portable'])
    parser.add_argument('--old', type=Path)
    args = parser.parse_args()
    for name in ('installer','broken','old_020','old_030','portable','old'):
        value = getattr(args, name)
        if value: setattr(args, name, value.resolve())
    if args.case: case(args); return
    for label, old in [('0.2.0',args.old_020),('0.3.0',args.old_030),('portable',None)]:
        command = [sys.executable,__file__,'--installer',str(args.installer),'--broken',str(args.broken),'--portable',str(args.portable),'--case',label]
        if old: command += ['--old',str(old)]
        subprocess.run(command, check=True, timeout=900)


if __name__ == '__main__': main()
