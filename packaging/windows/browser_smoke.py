"""Production UI tests from ZIP. Mock Oracle responses: never call Oracle.
Windows CI uses bundled runtime. --python is Linux-only evidence.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
import zipfile
from playwright.sync_api import sync_playwright, expect


def run(package, python=None, browser_path=None):
    with tempfile.TemporaryDirectory(prefix='HUGINN browser test ') as temp:
        with zipfile.ZipFile(package) as z:
            z.extractall(temp)
        root = Path(temp) / 'HUGINN-IA-Windows-x64'
        cfg = json.loads((root / 'bootstrap.json').read_text())
        cfg['updates_enabled'] = False
        (root / 'bootstrap.json').write_text(json.dumps(cfg))
        with tempfile.TemporaryFile() as log:
            proc = subprocess.Popen([str(python or root / 'runtime/python.exe'), '-I', str(root/'launcher.py'), '--no-browser'], stdout=log, stderr=log)
            try:
                with sync_playwright() as p:
                    options = dict(headless=True)
                    if browser_path:
                        options['executable_path'] = str(browser_path)
                        options['args'] = ['--no-sandbox']
                    browser = p.chromium.launch(**options)
                    page = browser.new_page()
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    for _ in range(100):
                        try:
                            page.goto('http://127.0.0.1:8000', timeout=1000)
                            break
                        except Exception:
                            if proc.poll() is not None:
                                log.seek(0)
                                raise AssertionError(log.read().decode(errors='replace'))
                            time.sleep(.1)
                    expect(page.get_by_role('heading', name='Painel de entrada NF-e')).to_be_visible()
                    expect(page.get_by_role('button', name='Atualizar agora')).to_be_disabled()
                    expect(page.get_by_text('Versão atual: '+cfg['version'], exact=False)).to_be_visible()
                    calls = []
                    def diagnostic(route):
                        calls.append(route.request.post_data_json)
                        route.fulfill(status=200,json=dict(modo='metadados somente leitura',tabelas=[
                            dict(nome='PCPRODUT',proprietario='A',visivel=True,colunas=[dict(coluna='CODPROD',tipo='NUMBER')]),
                            dict(nome='PCPRODUT',proprietario='B',visivel=True,colunas=[dict(coluna='DESCRICAO',tipo='VARCHAR2')]),
                            dict(nome='PCMOV',proprietario=None,visivel=False,colunas=[])]))
                    page.route('**/api/oracle/diagnostico', diagnostic)
                    page.route('**/api/oracle/testar',lambda route:route.fulfill(status=200,json=dict(conectado=True)))
                    button = page.get_by_role('button',name='Diagnosticar tabelas WinThor')
                    button.click()
                    assert not calls
                    def fill():
                        for label,value in [('Host ou IP','synthetic.local'),('Service Name','SYNTHETIC'),('Usuário de leitura','synthetic'),('Senha','synthetic-test-only')]:
                            page.get_by_label(label,exact=True).fill(value)
                    fill(); button.click()
                    expect(page.get_by_label('Senha',exact=True)).to_have_value('')
                    page.locator('summary').filter(has_text='A.PCPRODUT').click()
                    expect(page.get_by_role('cell',name='CODPROD',exact=True)).to_be_visible()
                    page.locator('summary').filter(has_text='B.PCPRODUT').click()
                    expect(page.get_by_role('cell',name='DESCRICAO',exact=True)).to_be_visible()
                    expect(page.locator('summary').filter(has_text='PCMOV — não visível')).to_be_visible()
                    page.get_by_label('Host ou IP').fill('changed.local')
                    expect(page.locator('summary')).to_have_count(0)
                    page.get_by_label('Senha',exact=True).fill('synthetic-test-only')
                    page.get_by_role('button',name='Testar conexão Oracle').click()
                    expect(page.get_by_text('Conexão confirmada em somente leitura.',exact=False)).to_be_visible()
                    expect(page.get_by_label('Senha',exact=True)).to_have_value('')
                    page.unroute('**/api/oracle/diagnostico')
                    page.route('**/api/oracle/diagnostico',lambda route:route.fulfill(status=502,json=dict(detail='Falha Oracle simulada')))
                    fill(); button.click()
                    expect(page.get_by_role('alert')).to_have_text('Falha Oracle simulada')
                    page.locator('input[type=file]').set_input_files(str(root/'exemplos/nota-demo.xml'))
                    expect(page.get_by_role('heading',name='Nota 12 · Série 1')).to_be_visible()
                    update_requests = []
                    page.route('**/api/updates/status',lambda route:route.fulfill(status=200,json=dict(
                        version=cfg['version'],channel='estavel',enabled=True,available='99.0.0',
                        notes='Release sintética para teste de aprovação',status='Atualização disponível',restart_required=True)))
                    def queue(route):
                        update_requests.append((route.request.url,route.request.post_data_json))
                        route.fulfill(status=200,json=dict(status='solicitado',restart_required=True))
                    page.route('**/api/updates/apply',queue)
                    page.on('dialog',lambda dialog:dialog.accept())
                    expect(page.get_by_role('button',name='Atualizar agora')).to_be_enabled(timeout=6000)
                    with page.expect_response(lambda response:response.url.endswith('/api/updates/apply')):
                        page.get_by_role('button',name='Atualizar agora').click()
                    assert update_requests[-1][1] == {}
                    expect(page.get_by_text('Versão disponível: 99.0.0',exact=True)).to_be_visible()
                    page.get_by_label('Senha',exact=True).fill('synthetic-test-only')
                    page.unroute('**/api/updates/status')
                    page.route('**/api/updates/status',lambda route:route.fulfill(status=200,json=dict(
                        version='99.0.0',channel='estavel',enabled=True,available=None,notes='',status='Instalada',restart_required=False)))
                    with page.expect_navigation(wait_until='load'):
                        page.wait_for_timeout(2500)
                    expect(page.get_by_label('Senha',exact=True)).to_have_value('')
                    page.set_viewport_size(dict(width=390,height=844))
                    button.scroll_into_view_if_needed()
                    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                    assert page.evaluate('localStorage.length') == 0
                    assert not errors,errors
                    print('PASS: production panel, metadata owners/columns/missing, field validation, credential clearing, connection mocked, failure mocked, XML, updates disabled/enabled approval UI/reload (mocked), mobile, no JS errors')
                    browser.close()
            finally:
                if (root/'state').exists():
                    (root/'state/shutdown').touch()
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait()


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('package',type=Path)
    p.add_argument('--python',type=Path)
    p.add_argument('--browser-path',type=Path)
    a=p.parse_args()
    run(a.package.resolve(),a.python.absolute() if a.python else None,a.browser_path)
