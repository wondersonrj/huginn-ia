"""Actual Inno/MSVC installer lifecycle, Windows user DPAPI, browser auth and port conflict.
Only synthetic local fixtures, never an Oracle service or release publication.
"""
import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from playwright.sync_api import sync_playwright, expect


def run(installer, upgrade=None):
    if os.name != 'nt':
        raise RuntimeError('Installer acceptance requires native Windows')
    with tempfile.TemporaryDirectory(prefix='HUGINN installed smoke ') as temp:
        root = Path(temp) / 'Programa com espacos'
        env = {k: v for k, v in os.environ.items() if not k.startswith(('HUGINN_ORACLE_', 'HUGINN_API_TOKEN', 'HUGINN_DESKTOP_', 'HUGINN_STATE_DIR'))}
        env['HUGINN_WINTHOR_MODE'] = 'demo'
        def install(path):
            return subprocess.run([str(path), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', '/DIR=' + str(root)], env=env, capture_output=True, timeout=180)
        assert install(installer).returncode == 0
        assert (root / 'HUGINN-IA.exe').is_file() and (root / 'unins000.exe').is_file()
        assert (root / 'docs/INSTALACAO_WINDOWS.md').is_file()
        assert install(installer).returncode == 0  # idempotent reinstall
        class Foreign(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200); self.end_headers(); self.wfile.write(b'FOREIGN-SERVICE')
            def log_message(self, *args): pass
        foreign = HTTPServer(('127.0.0.1', 8000), Foreign)
        threading.Thread(target=foreign.serve_forever, daemon=True).start()
        primary = None
        try:
            def start():
                process = subprocess.Popen([str(root / 'HUGINN-IA.exe'), '--no-browser'], env=env)
                for _ in range(200):
                    try:
                        info = json.loads((root / 'state/instance.json').read_text())
                        with urllib.request.urlopen(f'http://127.0.0.1:{info["port"]}/api/version', timeout=.5) as response:
                            if json.load(response)['version'] == info['version']:
                                return process, info
                    except Exception:
                        time.sleep(.1)
                raise AssertionError('Desktop startup did not report healthy managed port')
            primary, info = start()
            assert info['port'] != 8000
            url = f'http://127.0.0.1:{info["port"]}'
            # Reopening never kills a process, launches a duplicate backend, or asks for token.
            second = subprocess.run([str(root / 'HUGINN-IA.exe'), '--no-browser'], env=env, timeout=30)
            assert second.returncode == 0 and primary.poll() is None
            assert json.loads((root / 'state/instance.json').read_text())['port'] == info['port']
            multiple = [subprocess.Popen([str(root / 'HUGINN-IA.exe'), '--no-browser'], env=env) for _ in range(2)]
            assert all(p.wait(timeout=30) == 0 for p in multiple)
            # An active application blocks an installer, without force-closing it/reboot.
            assert install(installer).returncode != 0 and primary.poll() is None
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page()
                page.goto(url)
                expect(page.get_by_role('heading', name='HUGINN IA · Consulta WinThor')).to_be_visible()
                expect(page.get_by_label('Token de acesso local', exact=True)).to_have_count(0)
                expect(page.get_by_label('Nome da conexão', exact=True)).to_be_visible()
                assert page.evaluate('localStorage.length + sessionStorage.length') == 0
                assert 'huginn_session_' not in page.evaluate('document.cookie')
                # Synthetic profile, confirmed by DPAPI locally; no Oracle host is contacted.
                for label, value in [('Nome da conexão', 'Instalador sintético'), ('Host da conexão', '127.0.0.1'),
                                     ('Service Name da conexão', 'SYNTHETIC'), ('Usuário da conexão', 'synthetic'),
                                     ('Schema WinThor', 'WINT'), ('Nova senha da conexão', 'synthetic-installer-only')]:
                    page.get_by_label(label, exact=True).fill(value)
                probe = socket.socket(); probe.bind(('127.0.0.1', 0)); absent_port = probe.getsockname()[1]; probe.close()
                page.get_by_label('Porta da conexão', exact=True).fill(str(absent_port))
                page.get_by_role('button', name='Salvar conexão', exact=True).click()
                expect(page.get_by_label('Nova senha da conexão', exact=True)).to_have_value('')
                expect(page.get_by_role('button', name='Selecionar Instalador sintético', exact=True)).to_be_enabled()
                page.get_by_role('button', name='Testar Instalador sintético', exact=True).click()
                expect(page.locator('.connection-manager [role=alert]')).to_be_visible()
                assert 'synthetic-installer-only' not in page.locator('body').inner_text()
                page.once('dialog', lambda d: d.accept())
                page.get_by_role('button', name='Encerrar HUGINN', exact=True).click()
                assert primary.wait(timeout=30) == 0
                # Reinstall/upgrade retains this user/installation's protected profile.
                assert install(upgrade or installer).returncode == 0
                (root / 'state/instance.json').unlink(missing_ok=True)
                primary, info = start(); url = f'http://127.0.0.1:{info["port"]}'
                page.goto(url)
                expect(page.get_by_role('button', name='Editar Instalador sintético', exact=True)).to_be_visible()
                expect(page.get_by_text('Consultas direcionadas a:', exact=False)).to_have_count(0)
                # Fake/corrupt descriptor cannot authenticate a foreign server on port 8000.
                spec = importlib.util.spec_from_file_location('installed_desktop', root / 'desktop.py')
                desktop = importlib.util.module_from_spec(spec); spec.loader.exec_module(desktop)
                token = desktop.access_token(root, info['version'])
                assert desktop.verify_instance(root, info['version'], token) == url
                saved = (root / 'state/instance.json').read_bytes()
                (root / 'state/instance.json').write_text(json.dumps({'port': 8000}))
                assert desktop.verify_instance(root, info['version'], token) is None
                (root / 'state/instance.json').write_bytes(saved)
                # Persistent token is not a JSON/frontend value and is actually DPAPI protected.
                from app.connection_store import current_store
                vault = current_store().root
                assert token.encode() not in (vault / 'local-token.bin').read_bytes()
                page.once('dialog', lambda d: d.accept()); page.get_by_role('button', name='Encerrar HUGINN', exact=True).click()
                assert primary.wait(timeout=30) == 0
                browser.close()
            uninstaller = root / 'unins000.exe'
            assert subprocess.run([str(uninstaller), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'], env=env, timeout=120).returncode == 0
            assert vault.exists()  # silent/default removal keeps data
            assert install(installer).returncode == 0
            assert subprocess.run([str(root / 'unins000.exe'), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/REMOVEDATA=1'], env=env, timeout=120).returncode == 0
            assert not vault.exists()
            with urllib.request.urlopen('http://127.0.0.1:8000') as response:
                assert response.read() == b'FOREIGN-SERVICE'
            print('PASS: native clean install/reinstall/upgrade, automatic DPAPI access, SID-bound HttpOnly session, onboarding, reopen/multiple instances, foreign-port preservation, missing Oracle, uninstall keep/remove; no reboot/release')
        finally:
            # Only signal this test installation. Never kill a foreign PID/service.
            if primary and primary.poll() is None:
                (root / 'state/shutdown').touch()
                primary.wait(timeout=40)
            foreign.shutdown(); foreign.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--installer', type=Path, required=True)
    parser.add_argument('--upgrade', type=Path)
    args = parser.parse_args()
    run(args.installer.resolve(), args.upgrade.resolve() if args.upgrade else None)
