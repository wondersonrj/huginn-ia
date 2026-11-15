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


TOKEN = 'synthetic-browser-token-' + 'x' * 32


def scenario_navigation(page):
    from ui_flow import go, LABELS
    expect(page.get_by_role('heading', name='Visão geral', exact=True, level=1)).to_be_visible()
    for module in LABELS:
        go(page, module)
    go(page, 'visao-geral')
    expect(page.get_by_role('heading', name='Central de Conexões', exact=True)).to_have_count(0)
    assert page.get_by_label('Host da conexão', exact=True).count() == 0
    page.set_viewport_size(dict(width=390, height=844))
    for module in ('produtos','nfe','configuracoes','validacao','visao-geral'):
        go(page, module)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.set_viewport_size(dict(width=1440, height=1000))
    page.keyboard.press('Tab')
    assert page.evaluate('document.activeElement !== document.body')


def scenario_access(page):
    from ui_flow import go
    go(page, 'configuracoes')
    expect(page.get_by_role('heading', name='Conexão Oracle direta', exact=True)).to_have_count(0)
    expect(page.get_by_label('Host da conexão', exact=True)).to_have_count(0)  # list not yet loaded in legacy mode
    page.get_by_label('Token de acesso local', exact=True).fill('invalid')
    go(page, 'produtos')
    page.get_by_role('button', name='Verificar conexão WinThor', exact=True).click()
    expect(page.get_by_role('alert')).to_be_visible()
    go(page, 'configuracoes')
    page.get_by_label('Token de acesso local', exact=True).fill(TOKEN)
    page.get_by_role('button', name='Verificar conexão WinThor', exact=True).click()
    expect(page.get_by_text('Simulação ativa: dados fictícios, sem conexão Oracle.', exact=True)).to_be_visible()
    assert page.evaluate('localStorage.length + sessionStorage.length') == 0


def scenario_catalog_search(page):
    from ui_flow import go
    go(page, 'produtos')
    page.get_by_role('button', name='Buscar cadastros', exact=True).click()
    table = page.get_by_role('table', name='Cadastros WinThor')
    expect(table.get_by_role('row')).to_have_count(21)
    expect(table.get_by_text('Produto demonstrativo 001', exact=True)).to_be_visible()
    page.get_by_role('button', name='Próxima página', exact=True).click()
    expect(table.get_by_text('Produto demonstrativo 021', exact=True)).to_be_visible()
    page.get_by_role('button', name='Página anterior', exact=True).click()
    expect(table.get_by_text('Produto demonstrativo 001', exact=True)).to_be_visible()
    page.get_by_label('Nome ou descrição', exact=True).fill('055')
    page.get_by_role('button', name='Buscar cadastros', exact=True).click()
    expect(table.get_by_role('row')).to_have_count(2)
    go(page, 'fornecedores')
    page.get_by_label('Código do cadastro', exact=True).fill('3')
    page.get_by_role('button', name='Buscar cadastros', exact=True).click()
    expect(table.get_by_text('Fornecedor demonstrativo 003', exact=True)).to_be_visible()
    page.get_by_label('Código do cadastro', exact=True).fill('99999')
    page.get_by_role('button', name='Buscar cadastros', exact=True).click()
    expect(page.get_by_text('Nenhum cadastro encontrado para os filtros informados.', exact=True)).to_be_visible()
    go(page, 'produtos')
    page.route('**/api/winthor/produtos', lambda route: route.fulfill(status=502,json=dict(detail='Consulta indisponível simulada')))
    page.get_by_role('button', name='Buscar cadastros', exact=True).click()
    expect(page.get_by_role('alert')).to_have_text('Consulta indisponível simulada')
    page.unroute('**/api/winthor/produtos')
    page.get_by_role('button', name='Buscar cadastros', exact=True).click()
    expect(table.get_by_role('row')).to_have_count(21)


def scenario_schema(page):
    from ui_flow import go
    go(page, 'suporte')
    page.get_by_role('button', name='Diagnosticar estrutura', exact=True).click()
    expect(page.get_by_text('Estrutura simulada. Nenhuma coluna foi confirmada em Oracle real.', exact=True)).to_be_visible()


def scenario_connections(page):
    from ui_flow import go
    go(page, 'configuracoes')
    page.get_by_role('button', name='Carregar conexões salvas', exact=True).click()
    if os.name != 'nt':
        expect(page.get_by_text('Proteção Windows indisponível neste sistema.', exact=False)).to_be_visible()
    else:
        def fill(name='Perfil sintético'):
            for label,value in [('Nome da conexão',name),('Host da conexão','synthetic.invalid'),('Porta da conexão','1521'),('Service Name da conexão','SYNTHETIC'),('Usuário da conexão','synthetic'),('Schema WinThor','WINT'),('Nova senha da conexão','synthetic-browser-password')]:
                page.get_by_label(label,exact=True).fill(value)
        fill();page.get_by_role('button',name='Salvar conexão',exact=True).click()
        expect(page.get_by_role('button',name='Editar Perfil sintético',exact=True)).to_be_visible()
        expect(page.get_by_label('Nova senha da conexão',exact=True)).to_have_value('')
        page.get_by_role('button',name='Editar Perfil sintético',exact=True).click()
        page.get_by_label('Nome da conexão',exact=True).fill('Perfil editado')
        page.get_by_role('button',name='Salvar conexão',exact=True).click()
        expect(page.get_by_role('button',name='Selecionar Perfil editado',exact=True)).to_be_enabled()
        page.get_by_role('button',name='Selecionar Perfil editado',exact=True).click()
        expect(page.get_by_text('Destino selecionado: Perfil editado',exact=False)).to_be_visible()
        # All Oracle success/failure calls in this browser scenario are fixtures, never a real host.
        page.route('**/api/connections/test',lambda route:route.fulfill(status=200,json=dict(conectado=True,mensagem='DUAL sintético confirmado')))
        page.get_by_role('button',name='Testar Perfil editado',exact=True).click()
        expect(page.get_by_text('DUAL sintético confirmado',exact=True)).to_be_visible()
        page.unroute('**/api/connections/test')
        page.route('**/api/connections/diagnostic',lambda route:route.fulfill(status=200,json=dict(aviso='Metadados sintéticos sem credenciais',tabelas=[dict(nome='PCPRODUT',proprietario='A',visivel=True,colunas=[dict(coluna='CODPROD',tipo='NUMBER')]),dict(nome='PCPRODUT',proprietario='B',visivel=True,colunas=[dict(coluna='DESCRICAO',tipo='VARCHAR2')])])) )
        page.locator('.saved-profile').get_by_text('Detalhes técnicos do perfil',exact=True).click()
        page.get_by_role('button',name='Metadados ampliados de Perfil editado',exact=True).click()
        expect(page.get_by_text('Metadados sintéticos sem credenciais',exact=True)).to_be_visible()
        expect(page.locator('.metadata-report summary')).to_have_count(2)
        page.unroute('**/api/connections/diagnostic')
        page.get_by_role('button',name='Limpar edição',exact=True).click()
        fill('Destino produção')
        page.get_by_label('Ambiente da conexão',exact=True).select_option('PRODUCAO')
        page.get_by_role('button',name='Salvar conexão',exact=True).click()
        expect(page.get_by_role('button',name='Selecionar Destino produção',exact=True)).to_be_enabled()
        # Any save invalidates selection by design; restore TESTE explicitly before canceling PROD.
        expect(page.get_by_text('Destino selecionado: Perfil editado',exact=False)).to_have_count(0)
        page.get_by_role('button',name='Selecionar Perfil editado',exact=True).click()
        expect(page.get_by_text('Destino selecionado: Perfil editado',exact=False)).to_be_visible()
        page.once('dialog',lambda d:d.dismiss());page.get_by_role('button',name='Selecionar Destino produção',exact=True).click()
        expect(page.get_by_text('Destino selecionado: Perfil editado',exact=False)).to_be_visible()
        page.once('dialog',lambda d:d.accept());page.get_by_role('button',name='Selecionar Destino produção',exact=True).click()
        expect(page.get_by_text('Destino selecionado: Destino produção',exact=False)).to_be_visible()
        go(page,'visao-geral')
        expect(page.locator('.connection-bar').get_by_text('PRODUÇÃO',exact=True)).to_be_visible()
        assert 'synthetic.invalid' not in page.locator('body').inner_text()
        go(page,'configuracoes')
        page.once('dialog',lambda d:d.accept());page.get_by_role('button',name='Remover senha de Perfil editado',exact=True).click()
        expect(page.get_by_role('button',name='Selecionar Perfil editado',exact=True)).to_be_disabled()
        for name in ('Perfil editado','Destino produção'):
            page.once('dialog',lambda d:d.accept());page.get_by_role('button',name='Excluir '+name,exact=True).click()
            expect(page.get_by_role('button',name='Editar '+name,exact=True)).to_have_count(0)
        page.get_by_text('Opções avançadas de migração',exact=True).click()
        page.once('dialog',lambda d:d.accept());page.get_by_role('button',name='Usar configuração por ambiente',exact=True).click()
        expect(page.get_by_text('Origem: configuração por ambiente',exact=False)).to_be_visible()
    # Ad-hoc legacy diagnosis is preserved in the SAME Central form, no second password flow.
    for label,value in [('Host da conexão','synthetic.invalid'),('Service Name da conexão','SYNTHETIC'),('Usuário da conexão','synthetic'),('Nova senha da conexão','synthetic-browser-password')]:
        page.get_by_label(label,exact=True).fill(value)
    page.get_by_text('Diagnóstico pontual com os campos acima',exact=True).click()
    calls=[]
    page.route('**/api/oracle/testar',lambda route:(calls.append(route.request.post_data_json),route.fulfill(status=200,json=dict(conectado=True)))[1])
    page.get_by_role('button',name='Testar dados sem salvar',exact=True).click()
    expect(page.get_by_text('Conexão pontual confirmada em somente leitura. Nenhum perfil ou destino foi alterado.',exact=True)).to_be_visible()
    expect(page.get_by_label('Nova senha da conexão',exact=True)).to_have_value('')
    assert set(calls[0])=={'host','port','service','user','password'}
    page.unroute('**/api/oracle/testar')
    page.route('**/api/oracle/diagnostico',lambda route:route.fulfill(status=200,json=dict(aviso='Metadados pontuais sintéticos',tabelas=[dict(nome='PCPRODUT',proprietario='A',visivel=True,colunas=[]),dict(nome='PCPRODUT',proprietario='B',visivel=True,colunas=[])])))
    page.get_by_label('Nova senha da conexão',exact=True).fill('synthetic-browser-password')
    page.get_by_role('button',name='Diagnosticar dados sem salvar',exact=True).click()
    expect(page.get_by_text('Metadados pontuais sintéticos',exact=True)).to_be_visible()
    expect(page.get_by_label('Nova senha da conexão',exact=True)).to_have_value('')
    page.unroute('**/api/oracle/diagnostico')
    page.get_by_role('button', name='Encerrar acesso', exact=True).click()
    expect(page.get_by_label('Token de acesso local', exact=True)).to_have_value('')
    go(page,'produtos');expect(page.get_by_role('button',name='Buscar cadastros',exact=True)).to_be_disabled()
    go(page,'configuracoes');page.get_by_label('Token de acesso local',exact=True).fill(TOKEN)


def scenario_nfe(page,root):
    from ui_flow import go
    go(page,'nfe')
    page.get_by_label('Selecionar XML NF-e',exact=True).set_input_files(dict(name='invalid.xml',mimeType='application/xml',buffer=b'not XML'))
    expect(page.get_by_role('alert')).to_be_visible()
    page.get_by_label('Selecionar XML NF-e',exact=True).set_input_files(str(root/'exemplos/nota-demo.xml'))
    expect(page.get_by_role('heading',name='Nota 12 · Série 1',exact=True)).to_be_visible()
    expect(page.get_by_text('Nenhuma divergência foi confirmada.',exact=False)).to_be_visible()
    go(page,'visao-geral');go(page,'nfe')
    expect(page.get_by_role('heading',name='Nota 12 · Série 1',exact=True)).to_be_visible()
    page.get_by_role('button',name='Limpar nota',exact=True).click()
    expect(page.get_by_role('heading',name='Nenhuma nota carregada',exact=True)).to_be_visible()


def scenario_features(page,root):
    from ui_flow import go
    go(page,'validacao')
    page.get_by_label('Status',exact=True).select_option('planejado')
    expect(page.locator('[data-feature]')).to_have_count(2)
    expect(page.get_by_role('heading',name='Integração SEFAZ',exact=True)).to_be_visible()
    page.get_by_label('Status',exact=True).select_option('todos')
    page.get_by_label('Módulo',exact=True).select_option('produtos')
    expect(page.locator('[data-feature]')).to_have_count(1)
    page.get_by_label('Módulo',exact=True).select_option('todos')
    page.get_by_label('Buscar funcionalidade',exact=True).fill('not-a-feature')
    expect(page.get_by_role('heading',name='Nenhuma funcionalidade encontrada',exact=True)).to_be_visible()
    page.get_by_label('Buscar funcionalidade',exact=True).fill('')
    for button,suffix in [('Relatório técnico JSON','json'),('Relatório legível','md')]:
        with page.expect_download() as event: page.get_by_role('button',name=button,exact=True).click()
        download=event.value;target=root/('report.'+suffix);download.save_as(str(target));content=target.read_text(encoding='utf-8')
        assert TOKEN not in content and 'synthetic-browser-password' not in content and 'synthetic.invalid' not in content
        if suffix=='json': assert json.loads(content)['schema_version']==1
        else: assert 'homologação Oracle real' in content


def scenario_updates(page,cfg):
    from ui_flow import go
    go(page,'suporte')
    expect(page.get_by_role('button',name='Atualizar agora',exact=True)).to_be_disabled()
    requests=[]
    page.route('**/api/updates/status',lambda route:route.fulfill(status=200,json=dict(version=cfg['version'],channel='teste',enabled=True,available='99.0.0',notes='Synthetic update',status='Atualização disponível',restart_required=True)))
    page.route('**/api/updates/apply',lambda route:(requests.append(route.request.post_data_json),route.fulfill(status=200,json=dict(status='solicitado')))[1])
    page.once('dialog',lambda d:d.dismiss())
    expect(page.get_by_role('button',name='Atualizar agora',exact=True)).to_be_enabled(timeout=6000)
    page.get_by_role('button',name='Atualizar agora',exact=True).click();assert not requests
    page.once('dialog',lambda d:d.accept());page.get_by_role('button',name='Atualizar agora',exact=True).click()
    expect(page.get_by_text('Versão disponível: 99.0.0',exact=True)).to_be_visible();assert requests==[{}]
    page.unroute('**/api/updates/status')
    page.route('**/api/updates/status',lambda route:route.fulfill(status=200,json=dict(version='99.0.0',channel='teste',enabled=True,available=None,notes='',status='Instalada',restart_required=False)))
    with page.expect_navigation(wait_until='load'): page.wait_for_timeout(2500)
    go(page,'configuracoes');expect(page.get_by_label('Token de acesso local',exact=True)).to_have_value('')
    assert page.evaluate('localStorage.length + sessionStorage.length') == 0


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
                    scenario_navigation(page)
                    scenario_access(page)
                    scenario_catalog_search(page)
                    scenario_schema(page)
                    scenario_connections(page)
                    scenario_nfe(page, root)
                    scenario_features(page, root)
                    if os.environ.get("HUGINN_UI_EVIDENCE_DIR"):
                        from ui_snapshots import capture
                        capture(page, Path(os.environ["HUGINN_UI_EVIDENCE_DIR"]), root / "exemplos/nota-demo.xml")
                        page.set_viewport_size(dict(width=1440, height=1000))
                    scenario_updates(page, cfg)
                    assert not errors, errors
                    print('PASS: enterprise navigation/one Oracle central, keyboard/mobile, access and no WebStorage, products/suppliers filters/pages/error/recovery, saved TESTE/PRODUCAO confirmation and CRUD, schema/extended metadata, XML local, catalog filters/sanitized reports, update approval/reload; Oracle synthetic only')
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
