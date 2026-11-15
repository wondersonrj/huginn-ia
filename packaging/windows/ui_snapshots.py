"""Non-secret visual evidence against an already running DEMO instance only.
Never use against a customer's instance. Synthetic list fixture avoids real profiles.
"""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from browser_smoke import TOKEN
from ui_flow import go


def capture(page, output, xml):
    output.mkdir(parents=True, exist_ok=True)
    page.route('**/api/connections/list', lambda r:r.fulfill(json=dict(supported=True,profiles=[],active=None,source='environment')))
    go(page,'configuracoes')
    page.get_by_label('Token de acesso local',exact=True).fill(TOKEN)
    page.get_by_role('button',name='Carregar conexões salvas',exact=True).click()
    page.get_by_role('button',name='Verificar conexão WinThor',exact=True).click()
    expect(page.get_by_text('Simulação ativa: dados fictícios, sem conexão Oracle.',exact=True)).to_be_visible()
    for module in ('visao-geral','produtos','fornecedores','nfe','configuracoes','validacao','suporte'):
        go(page,module)
        if module in ('produtos','fornecedores'):
            page.get_by_role('button',name='Buscar cadastros',exact=True).click()
            expect(page.get_by_role('table',name='Cadastros WinThor')).to_be_visible()
        if module=='configuracoes':
            page.get_by_role('button',name='Carregar conexões salvas',exact=True).click()
            expect(page.get_by_role('button',name='Salvar conexão',exact=True)).to_be_visible()
            page.get_by_role('button',name='Verificar conexão WinThor',exact=True).click()
            expect(page.get_by_text('Simulação ativa: dados fictícios, sem conexão Oracle.',exact=True)).to_be_visible()
        if module=='nfe':
            page.get_by_label('Selecionar XML NF-e',exact=True).set_input_files(str(xml))
            expect(page.get_by_role('heading',name='Nota 12 · Série 1',exact=True)).to_be_visible()
        if module=='suporte':
            page.get_by_role('button',name='Diagnosticar estrutura',exact=True).click()
            expect(page.get_by_text('Estrutura simulada. Nenhuma coluna foi confirmada em Oracle real.',exact=True)).to_be_visible()
        page.screenshot(path=str(output/(module+'.png')),full_page=True,animations='disabled')
    go(page,'visao-geral');page.set_viewport_size(dict(width=390,height=844))
    page.screenshot(path=str(output/'mobile.png'),full_page=True,animations='disabled')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',required=True)
    parser.add_argument('--xml',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--browser-path')
    args=parser.parse_args()
    with sync_playwright() as p:
        browser=p.chromium.launch(**({'executable_path':args.browser_path} if args.browser_path else {}))
        page=browser.new_page(viewport=dict(width=1440,height=1000))
        page.goto(args.url)
        capture(page,args.output,args.xml)
        browser.close()
