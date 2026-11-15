"""UI/API acceptance against CI-only driver double in a disposable installed tree."""
import json
from playwright.sync_api import expect


def exercise(page, root, version):
    def post(path, body):
        return page.evaluate('''async ({path, body}) => {
          const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
          return {status:response.status, body:await response.json()};
        }''', dict(path=path, body=body))
    def listing():
        response = post('/api/connections/list', {})
        assert response['status'] == 200
        return response['body']['profiles']
    def ref(profile): return {k: profile[k] for k in ('id', 'revision')}
    def context(profile): return dict(connection_id=profile['id'], connection_revision=profile['revision'])

    page.get_by_role('button', name='Testar Instalador sintético', exact=True).click()
    expect(page.get_by_text('Último teste pontual confirmado:', exact=False)).to_be_visible()
    page.get_by_role('button', name='Selecionar Instalador sintético', exact=True).click()
    expect(page.get_by_text('Consultas direcionadas a: Instalador sintético — TESTE', exact=True)).to_be_visible()
    page.get_by_role('button', name='Verificar conexão WinThor', exact=True).click()
    expect(page.get_by_text('ORACLE — somente leitura', exact=True)).to_be_visible()
    page.get_by_role('button', name='Conferir estrutura de consulta', exact=True).click()
    expect(page.get_by_text('Colunas e tipos confirmados nos metadados desta conexão.', exact=True)).to_be_visible()
    for kind, code, label in [('produtos', '101', 'Produto CI Oracle'), ('fornecedores', '202', 'Fornecedor CI Oracle')]:
        page.get_by_label('Cadastro', exact=True).select_option(kind)
        page.get_by_label('Código do cadastro', exact=True).fill(code)
        page.get_by_role('button', name='Buscar cadastros', exact=True).click()
        expect(page.get_by_role('table', name='Cadastros WinThor').get_by_text(label, exact=True)).to_be_visible()
        expect(page.get_by_text('Resultados fictícios de demonstração.', exact=True)).to_have_count(0)
    profile = listing()[0]
    # Test errors through the installed backend, actual session cookie and DPAPI vault.
    fields = {key: profile[key] for key in ('name', 'environment', 'host', 'port', 'service', 'user', 'owner')}
    for overrides, action, status, message in [
        ({'password': 'invalid-synthetic'}, 'test', 502, 'senha inválidos'),
        ({'service': 'UNAVAILABLE'}, 'test', 502, 'listener'),
        ({'service': 'TIMEOUT'}, 'test', 502, 'Tempo de resposta'),
        ({'owner': 'WRONG'}, 'diagnostico', 409, 'Schema não confirmado'),
        ({'service': 'NOSELECT'}, 'produtos', 502, 'SELECT'),
        ({'service': 'QUERYTIMEOUT'}, 'produtos', 502, 'timeout'),
    ]:
        result = post('/api/connections/save', dict(fields, **ref(profile), password='synthetic-installer-only') | overrides)
        assert result['status'] == 200
        profile = result['body']['profile']
        if action == 'test': result = post('/api/connections/test', ref(profile) | dict(confirm_environment='TESTE'))
        else:
            assert post('/api/connections/select', ref(profile) | dict(confirm_environment='TESTE'))['status'] == 200
            result = post('/api/winthor/' + action, context(profile) | (dict(codigo=101) if action == 'produtos' else {}))
        assert result['status'] == status and message in result['body']['detail'], (action, result)
        assert 'invalid-synthetic' not in json.dumps(result)
    # Changing destination must reject an old context, even when mode was inherited as demo.
    old = context(profile)
    new = post('/api/connections/save', fields | dict(name='Outro destino', password='synthetic-installer-only'))['body']['profile']
    assert post('/api/connections/select', ref(new) | dict(confirm_environment='TESTE'))['status'] == 200
    assert post('/api/winthor/produtos', old | dict(codigo=101))['status'] == 409
    assert post('/api/connections/remove-password', ref(new))['status'] == 200
    new = next(p for p in listing() if p['id'] == new['id'])
    assert not new['password_saved']
    assert post('/api/connections/select', ref(new) | dict(confirm_environment='TESTE'))['status'] != 200
    assert post('/api/winthor/health', {})['status'] == 409  # never falls back to demo
    # Restore original connection for the next clean startup/retest.
    assert post('/api/connections/save', fields | ref(profile) | dict(password='synthetic-installer-only'))['status'] == 200
    events = {json.loads(line)['event'] for line in (root / 'versions' / version / 'backend/oracle-fixture-events.jsonl').read_text().splitlines()}
    assert {'dual', 'PCPRODUT_metadata', 'PCFORNEC_metadata', 'PCPRODUT_bound_query', 'PCFORNEC_bound_query'} <= events
    audit = (root / 'state/audit.jsonl').read_text()
    assert 'synthetic-installer-only' not in audit and 'invalid-synthetic' not in audit
    page.reload()
    expect(page.get_by_role('button', name='Editar Instalador sintético', exact=True)).to_be_visible()
    print('PASS: installed Oracle-mode synthetic driver: DUAL, metadata, CODPROD/CODFORNEC binds and UI rows; invalid password, unavailable service, timeouts, wrong owner, missing SELECT, switch/stale context, missing secret, sanitized audit')
