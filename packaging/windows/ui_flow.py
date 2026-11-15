"""Accessible navigation shared by current UI tests and historical Setup fixtures."""
from playwright.sync_api import expect

LABELS = {'configuracoes':'Configurações','produtos':'Produtos','fornecedores':'Fornecedores','suporte':'Diagnóstico e Suporte','nfe':'Auditoria NF-e','validacao':'Funcionalidades e Validação','visao-geral':'Visão geral'}


def go(page, module):
    page.locator('.shell').wait_for()
    nav = page.get_by_role('navigation', name='Navegação principal', exact=True, include_hidden=True)
    if nav.count():
        if not nav.is_visible(): page.get_by_role('button', name='Abrir navegação', exact=True).click()
        nav.get_by_role('link', name=LABELS[module], exact=True).click()
        expect(page.get_by_role('heading', name=LABELS[module], exact=True, level=1)).to_be_visible()
    elif module in ('produtos','fornecedores'):
        # Historical 0.2.x/0.3.0 fixtures deliberately retain the original frontend.
        page.get_by_label('Cadastro', exact=True).select_option(module)


def verify(page):
    go(page, 'configuracoes')
    page.get_by_role('button', name='Verificar conexão WinThor', exact=True).click()
    page.get_by_role('status').filter(has_text='Verificando conexão selecionada').wait_for(state='hidden')
