"""Production UI tests from ZIP. Mock Oracle responses: never call Oracle.
Windows CI uses bundled runtime. --python is Linux-only evidence.
"""
import os
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
            proc = subprocess.Popen([str(python or root / 'runtime/python.exe'), '-I', str(root/'launcher.py'), '--no-browser'], stdout=log, stderr=log,
                                    env={**os.environ, 'HUGINN_WINTHOR_MODE': 'demo', 'HUGINN_API_TOKEN': 'synthetic-browser-token-' + 'x' * 32})
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
                    expect(page.get_by_role('heading', name='HUGINN IA · Consulta WinThor')).to_be_visible()
                    expect(page.get_by_role('button', name='Atualizar agora')).to_be_disabled()
                    expect(page.get_by_text('Versão atual: '+cfg['version'], exact=False)).to_be_visible()
                    # Exercise the real authenticated demo API, not route mocks/Oracle.
                    page.get_by_label('Token de acesso local', exact=True).fill('synthetic-browser-token-' + 'x' * 32)
                    page.get_by_role('button', name='Verificar conexão WinThor').click()
                    expect(page.get_by_text('SIMULAÇÃO — dados fictícios, sem Oracle', exact=True)).to_be_visible()
                    page.get_by_role('button', name='Buscar cadastros').click()
                    table = page.get_by_role('table', name='Cadastros WinThor')
                    expect(table.get_by_role('row')).to_have_count(21)
                    expect(table.get_by_role('cell', name='Produto demonstrativo 001', exact=True)).to_be_visible()
                    page.get_by_role('button', name='Próxima página').click()
                    expect(table.get_by_role('cell', name='Produto demonstrativo 021', exact=True)).to_be_visible()
                    page.get_by_role('button', name='Página anterior').click()
                    expect(table.get_by_role('cell', name='Produto demonstrativo 001', exact=True)).to_be_visible()
                    page.get_by_label('Nome ou descrição', exact=True).fill('055')
                    page.get_by_role('button', name='Buscar cadastros').click()
                    expect(table.get_by_role('row')).to_have_count(2)
                    expect(table.get_by_role('cell', name='Produto demonstrativo 055', exact=True)).to_be_visible()
                    page.get_by_label('Cadastro', exact=True).select_option('fornecedores')
                    page.get_by_label('Código do cadastro', exact=True).fill('3')
                    page.get_by_role('button', name='Buscar cadastros').click()
                    expect(table.get_by_role('cell', name='Fornecedor demonstrativo 003', exact=True)).to_be_visible()
                    page.get_by_label('Código do cadastro', exact=True).fill('99999')
                    page.get_by_role('button', name='Buscar cadastros').click()
                    expect(page.get_by_text('Nenhum cadastro encontrado para os filtros informados.', exact=True)).to_be_visible()
                    page.get_by_role('button', name='Conferir estrutura de consulta').click()
                    expect(page.get_by_text('Estrutura simulada. Nenhuma coluna foi confirmada em Oracle real.', exact=True)).to_be_visible()
                    page.get_by_label('Cadastro', exact=True).select_option('produtos')
                    page.route('**/api/winthor/produtos', lambda route: route.fulfill(status=502, json=dict(detail='Consulta indisponível simulada')))
                    page.get_by_role('button', name='Buscar cadastros').click()
                    expect(page.get_by_role('alert')).to_have_text('Consulta indisponível simulada')
                    page.unroute('**/api/winthor/produtos')
                    page.get_by_role('button', name='Buscar cadastros').click()
                    expect(table.get_by_role('row')).to_have_count(21)
                    page.get_by_role('button', name='Carregar conexões salvas').click()
                    if os.name == 'nt':
                        def fill_profile(name='Perfil sintético'):
                            for label, value in [('Nome da conexão', name), ('Host da conexão', 'synthetic.invalid'),
                                    ('Porta da conexão', '1521'), ('Service Name da conexão', 'SYNTHETIC'),
                                    ('Usuário da conexão', 'synthetic'), ('Schema WinThor', 'WINT'),
                                    ('Nova senha da conexão', 'synthetic-password-never-oracle')]:
                                page.get_by_label(label, exact=True).fill(value)
                        fill_profile()
                        page.get_by_role('button', name='Salvar conexão', exact=True).click()
                        expect(page.get_by_label('Nova senha da conexão', exact=True)).to_have_value('')
                        expect(page.get_by_role('button', name='Selecionar Perfil sintético', exact=True)).to_be_enabled()
                        page.get_by_role('button', name='Selecionar Perfil sintético', exact=True).click()
                        expect(page.get_by_text('Consultas direcionadas a: Perfil sintético — TESTE', exact=True)).to_be_visible()
                        # Reload proves that the browser does not persist secrets or connection forms.
                        page.reload()
                        expect(page.get_by_label('Token de acesso local', exact=True)).to_have_value('')
                        page.get_by_label('Token de acesso local', exact=True).fill('synthetic-browser-token-' + 'x' * 32)
                        page.get_by_role('button', name='Carregar conexões salvas').click()
                        expect(page.get_by_role('button', name='Editar Perfil sintético', exact=True)).to_be_visible()
                        page.get_by_role('button', name='Editar Perfil sintético', exact=True).click()
                        expect(page.get_by_label('Nova senha da conexão', exact=True)).to_have_value('')
                        page.get_by_label('Ambiente da conexão', exact=True).select_option('PRODUCAO')
                        page.get_by_label('Nova senha da conexão', exact=True).fill('replacement-synthetic-only')
                        page.get_by_role('button', name='Salvar conexão', exact=True).click()
                        expect(page.get_by_text('Consultas direcionadas a:', exact=False)).to_have_count(0)
                        page.once('dialog', lambda dialog: dialog.dismiss())
                        page.get_by_role('button', name='Selecionar Perfil sintético', exact=True).click()
                        expect(page.get_by_text('Consultas direcionadas a:', exact=False)).to_have_count(0)
                        page.once('dialog', lambda dialog: dialog.accept())
                        page.get_by_role('button', name='Selecionar Perfil sintético', exact=True).click()
                        expect(page.get_by_text('Consultas direcionadas a: Perfil sintético — PRODUÇÃO', exact=True)).to_be_visible()
                        page.once('dialog', lambda dialog: dialog.accept())
                        page.get_by_role('button', name='Remover senha de Perfil sintético', exact=True).click()
                        expect(page.get_by_role('button', name='Selecionar Perfil sintético', exact=True)).to_be_disabled()
                        page.once('dialog', lambda dialog: dialog.accept())
                        page.get_by_role('button', name='Excluir Perfil sintético', exact=True).click()
                        expect(page.get_by_role('button', name='Editar Perfil sintético', exact=True)).to_have_count(0)
                        page.once('dialog', lambda dialog: dialog.accept())
                        page.get_by_role('button', name='Usar configuração por ambiente', exact=True).click()
                        expect(page.get_by_text('Origem: configuração por ambiente, destino não classificado.', exact=True)).to_be_visible()
                        # No real Oracle operation is invoked for saved test profiles in this suite.
                    else:
                        expect(page.get_by_text('Proteção Windows indisponível neste sistema.', exact=False)).to_be_visible()
                    page.get_by_role('button', name='Encerrar acesso').click()
                    expect(page.get_by_label('Token de acesso local', exact=True)).to_have_value('')
                    expect(table).to_have_count(0)
                    expect(page.get_by_role('button', name='Buscar cadastros')).to_be_disabled()
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
                    print('PASS: Windows saved-connection CRUD/reload/secret clearing/environment confirmation (native on Windows, no Oracle); authenticated catalog demo real API, products/suppliers, pagination, filters, empty/error/recovery, schema demo, logout, production panel, metadata owners/columns/missing, field validation, credential clearing, connection mocked, failure mocked, XML, updates disabled/enabled approval UI/reload (mocked), mobile, no JS errors')
                    browser.close()
            finally:
                if (root/'state').exists():
                    (root/'state/shutdown').touch()
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait()
                if os.name == 'nt':
                    import ctypes
                    import hashlib
                    import shutil
                    buffer = ctypes.create_unicode_buffer(32768)
                    if ctypes.windll.shell32.SHGetFolderPathW(None, 0x1c, None, 0, buffer) == 0:
                        installation = hashlib.sha256(str(root.resolve()).casefold().encode()).hexdigest()
                        shutil.rmtree(Path(buffer.value) / 'HUGINN' / 'Connections' / installation, ignore_errors=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('package',type=Path)
    p.add_argument('--python',type=Path)
    p.add_argument('--browser-path',type=Path)
    a=p.parse_args()
    run(a.package.resolve(),a.python.absolute() if a.python else None,a.browser_path)
