"""Read-only query/security contracts. The global fixture forbids real Oracle."""
import json
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import winthor
from app.oracle_connector import OracleConfig

TOKEN = 'synthetic-local-access-' + 'x' * 32
CFG = OracleConfig('db.test', 1521, 'TEST', 'reader', 'synthetic-db-secret')
REAL = winthor.Settings('oracle', 'WINT', CFG)


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv('HUGINN_API_TOKEN', TOKEN)
    monkeypatch.setenv('HUGINN_WINTHOR_MODE', 'demo')


def client(host='127.0.0.1', token=TOKEN, base='http://127.0.0.1:8000'):
    return TestClient(app, base_url=base, client=(host, 1234),
                      headers={'Authorization': 'Bearer ' + token})


@pytest.mark.parametrize('kind,columns', [
    ('produtos', [('CODPROD', 'NUMBER'), ('DESCRICAO', 'VARCHAR2')]),
    ('fornecedores', [('CODFORNEC', 'NUMBER'), ('FORNECEDOR', 'VARCHAR2')]),
])
def test_real_query_validates_metadata_and_binds_every_filter(kind, columns):
    con = MagicMock()
    cursor = con.cursor.return_value.__enter__.return_value
    cursor.fetchmany.side_effect = [columns, [(7, 'Synthetic')]]
    cursor.description = [('CODE', SimpleNamespace(name='DB_TYPE_NUMBER')), ('NAME', SimpleNamespace(name='DB_TYPE_VARCHAR'))]
    hostile_name = "x%' OR 1=1 --_\\"
    with patch('oracledb.connect', return_value=con):
        result = winthor.search(REAL, kind, code=7, name=hostile_name, page=2, page_size=10)
    calls = cursor.execute.call_args_list
    assert calls[0].args == ('SET TRANSACTION READ ONLY',)
    assert calls[1].args == (winthor.METADATA_SQL, dict(owner='WINT', table_name=winthor.SPECS[kind][0],
                           code_column=columns[0][0], name_column=columns[1][0]))
    assert calls[2].args[0].endswith('WHERE 1 = 0')
    sql, binds = calls[3].args
    assert hostile_name not in sql and '1=1' not in sql
    assert 'FETCH NEXT :limite ROWS ONLY' in sql and 'OFFSET :offset ROWS' in sql
    assert binds == dict(codigo=7, nome="%X\\%' OR 1=1 --\\_\\\\%", offset=10, limite=11)
    assert f'FROM "WINT"."{winthor.SPECS[kind][0]}"' in sql
    assert result['itens'] == [dict(codigo='7', nome='Synthetic')]
    assert result['modo'] == 'oracle'
    con.commit.assert_not_called()
    con.rollback.assert_not_called()
    con.close.assert_called_once()
    assert con.call_timeout == 5000
    assert cursor.fetchmany.call_args_list[-1].args == (11,)


@pytest.mark.parametrize('columns', [[], [('CODPROD', 'NUMBER')],
                                     [('CODPROD', 'VARCHAR2'), ('DESCRICAO', 'VARCHAR2')],
                                     [('CODPROD', 'NUMBER'), ('DESCRICAO', 'CLOB')]])
def test_missing_incompatible_columns_never_query_business_table(columns):
    con = MagicMock()
    cursor = con.cursor.return_value.__enter__.return_value
    cursor.fetchmany.return_value = columns
    with patch('app.winthor.connect_readonly', return_value=con), pytest.raises(winthor.SchemaUnavailable):
        winthor.search(REAL, 'produtos')
    assert len(cursor.execute.call_args_list) == (3 if not columns else 1)
    assert cursor.execute.call_args_list[0].args[0] == winthor.METADATA_SQL
    assert all('OFFSET' not in call.args[0] for call in cursor.execute.call_args_list)
    con.commit.assert_not_called()
    con.close.assert_called_once()


def test_connection_closes_on_business_query_error():
    con = MagicMock()
    cursor = con.cursor.return_value.__enter__.return_value
    cursor.fetchmany.return_value = [('CODPROD', 'NUMBER'), ('DESCRICAO', 'VARCHAR2')]
    cursor.execute.side_effect = [None, RuntimeError('synthetic-db-secret')]
    with patch('app.winthor.connect_readonly', return_value=con), pytest.raises(RuntimeError):
        winthor.search(REAL, 'produtos')
    con.close.assert_called_once()
    con.commit.assert_not_called()


def test_demo_never_accesses_oracle_and_paginates():
    with patch('app.winthor.connect_readonly') as connect:
        a = client().post('/api/winthor/produtos', json={'tamanho': 10}).json()
        b = client().post('/api/winthor/produtos', json={'tamanho': 10, 'pagina': 2}).json()
        found = client().post('/api/winthor/fornecedores', json={'nome': '003'}).json()
    connect.assert_not_called()
    assert a['modo'] == 'simulado' and a['tem_proxima']
    assert len(a['itens']) == 10 and b['itens'][0]['codigo'] == '11'
    assert found['itens'] == [dict(codigo='3', nome='Fornecedor demonstrativo 003')]


def test_health_does_not_claim_real_oracle_in_demo():
    response = client().post('/api/winthor/health', json={})
    assert response.status_code == 200
    assert response.json()['conectado'] is False
    assert response.json()['modo'] == 'simulado'
    assert response.headers['cache-control'] == 'no-store'
    diagnostic = client().post('/api/winthor/diagnostico', json={}).json()
    assert diagnostic['validado_no_oracle'] is False
    assert all(not table['validado'] for table in diagnostic['tabelas'])


@pytest.mark.parametrize('endpoint', ['health', 'diagnostico', 'produtos', 'fornecedores'])
def test_all_catalog_endpoints_require_authentication(endpoint):
    with patch('app.winthor.search') as search, patch('app.winthor.health') as health:
        response = client(token='wrong').post('/api/winthor/' + endpoint, json={})
    assert response.status_code == 401
    assert response.headers['WWW-Authenticate'] == 'Bearer'
    search.assert_not_called(); health.assert_not_called()


@pytest.mark.parametrize('endpoint', ['testar', 'diagnostico'])
def test_legacy_oracle_also_requires_authentication(endpoint):
    response = client(token='wrong').post('/api/oracle/' + endpoint, json={})
    assert response.status_code == 401


def test_unconfigured_token_fails_closed(monkeypatch):
    monkeypatch.delenv('HUGINN_API_TOKEN')
    assert client().post('/api/winthor/health', json={}).status_code == 503


@pytest.mark.parametrize('host,base,origin', [('192.0.2.1', 'http://127.0.0.1:8000', None),
    ('127.0.0.1', 'http://rebinding.example:8000', None),
    ('127.0.0.1', 'http://127.0.0.1:8000', 'https://evil.example')])
def test_remote_foreign_origin_and_dns_rebinding_denied(host, base, origin):
    response = client(host=host, base=base).post('/api/winthor/health', json={},
                                               headers={'Origin': origin} if origin else {})
    assert response.status_code == 403


@pytest.mark.parametrize('data', [{'codigo': "1 OR 1=1"}, {'codigo': 1.2}, {'codigo': True},
    {'codigo': 0}, {'pagina': 101}, {'pagina': 0}, {'tamanho': 51}, {'tamanho': 0},
    {'nome': 'a' * 81}, {'sql': 'DROP TABLE PCPRODUT'}, {'owner': 'OTHER'}, {'tabela': 'PCMOV'}])
def test_invalid_filters_and_arbitrary_sql_rejected_without_driver(data):
    with patch('app.winthor.search') as search:
        response = client().post('/api/winthor/produtos', json=data)
    assert response.status_code == 422
    assert 'DROP TABLE' not in response.text
    search.assert_not_called()


def test_body_size_json_and_media_type_limits():
    c = client()
    assert c.post('/api/winthor/produtos', content='x' * 2049, headers={'Content-Type': 'application/json'}).status_code == 413
    assert c.post('/api/winthor/produtos', content='{', headers={'Content-Type': 'application/json'}).status_code == 422
    assert c.post('/api/winthor/produtos', content='{}', headers={'Content-Type': 'text/plain'}).status_code == 415
    assert c.post('/api/winthor/health', json={'sql': 'anything'}).status_code == 422


def test_settings_real_owner_and_configuration_fail_closed(monkeypatch):
    monkeypatch.setenv('HUGINN_WINTHOR_MODE', 'oracle')
    monkeypatch.setenv('HUGINN_ORACLE_OWNER', 'WINT;DROP')
    assert client().post('/api/winthor/health', json={}).status_code == 503
    monkeypatch.setenv('HUGINN_WINTHOR_MODE', 'invalid')
    assert client().post('/api/winthor/health', json={}).status_code == 503


def test_schema_error_is_actionable_without_disclosing_details():
    with patch('app.winthor.search', side_effect=winthor.SchemaUnavailable('synthetic-db-secret')):
        response = client().post('/api/winthor/produtos', json={})
    assert response.status_code == 409
    assert 'schema' in response.text.lower() and 'synthetic-db-secret' not in response.text


def test_driver_errors_and_audit_do_not_echo_secrets_filters_or_dsn(caplog):
    with caplog.at_level(logging.INFO), patch('app.winthor.search', side_effect=RuntimeError(
            SimpleNamespace(full_code='ORA-01017', message='synthetic-db-secret dsn.test'))):
        response = client().post('/api/winthor/produtos', json={'nome': 'private-filter'})
    assert response.status_code == 502 and 'inválidos' in response.json()['detail']
    captured = response.text + caplog.text
    assert all(x not in captured for x in [TOKEN, 'synthetic-db-secret', 'private-filter', 'dsn.test'])
    events = [json.loads(r.message) for r in caplog.records if r.name == 'huginn.audit']
    assert events[-1]['status'] == 502
    assert events[-1]['request_id'] == response.headers['X-Request-ID']


def test_both_reads_are_audited_without_result_contents(caplog):
    with caplog.at_level(logging.INFO):
        a = client().post('/api/winthor/produtos', json={'codigo': 2})
        b = client().post('/api/winthor/fornecedores', json={'codigo': 2})
    events = [json.loads(r.message) for r in caplog.records if r.name == 'huginn.audit']
    assert [e['acao'] for e in events] == ['produtos', 'fornecedores']
    assert all(e['registros'] == 1 for e in events)
    assert a.json()['request_id'] != b.json()['request_id']
    assert 'Produto demonstrativo' not in caplog.text


def test_real_health_and_diagnostic_close_connections_and_never_commit():
    con = MagicMock()
    cursor = con.cursor.return_value.__enter__.return_value
    cursor.fetchmany.side_effect = [[('CODPROD', 'NUMBER'), ('DESCRICAO', 'VARCHAR2')], [('WINT',)], [],
                                   [('CODFORNEC', 'NUMBER'), ('FORNECEDOR', 'VARCHAR2')], [('WINT',)], []]
    cursor.description = [('CODE', SimpleNamespace(name='DB_TYPE_NUMBER')), ('NAME', SimpleNamespace(name='DB_TYPE_VARCHAR'))]
    with patch('app.winthor.connect_readonly', return_value=con):
        result = winthor.diagnostic(REAL)
    assert result['validado_no_oracle'] is True
    con.close.assert_called_once(); con.commit.assert_not_called()
    with patch('app.winthor.check_connection', return_value={'conectado': False}):
        assert winthor.health(REAL)['disponivel'] is False


def test_thick_mode_is_rejected_before_connecting():
    from app.oracle_connector import connect_readonly
    with patch('oracledb.is_thin_mode', return_value=False), patch('oracledb.connect') as connect:
        with pytest.raises(ValueError, match='Thin'):
            connect_readonly(CFG)
    connect.assert_not_called()


def test_real_authenticated_flow_keeps_credentials_on_server():
    with patch('app.winthor.Settings.load', return_value=REAL), patch('app.winthor.check_connection', return_value={'conectado': True}):
        response = client().post('/api/winthor/health', json={})
    assert response.status_code == 200 and response.json()['conectado'] is True
    assert response.json()['modo'] == 'oracle'
    assert all(value not in response.text for value in [CFG.host, CFG.user, CFG.password, CFG.service])


def test_real_unconfirmed_health_is_not_claimed_as_connected():
    with patch('app.winthor.Settings.load', return_value=REAL), patch('app.winthor.check_connection', return_value={'conectado': False}):
        response = client().post('/api/winthor/health', json={})
    assert response.status_code == 502


def test_real_page_has_hard_fetch_limit_and_last_page_flag():
    con = MagicMock()
    cursor = con.cursor.return_value.__enter__.return_value
    cursor.fetchmany.side_effect = [[('CODPROD', 'NUMBER'), ('DESCRICAO', 'VARCHAR2')], [(i, 'Synthetic') for i in range(51)]]
    cursor.description = [('CODE', SimpleNamespace(name='DB_TYPE_NUMBER')), ('NAME', SimpleNamespace(name='DB_TYPE_VARCHAR'))]
    with patch('app.winthor.connect_readonly', return_value=con):
        result = winthor.search(REAL, 'produtos', page=100, page_size=50)
    assert len(result['itens']) == 50 and result['limite_atingido'] and not result['tem_proxima']
    assert cursor.execute.call_args.args[1] == dict(codigo=None, nome=None, offset=4950, limite=51)
    assert cursor.fetchmany.call_args.args == (51,)


def test_successful_empty_query_is_audited(caplog):
    with caplog.at_level(logging.INFO):
        response = client().post('/api/winthor/produtos', json={'codigo': 99999})
    assert response.status_code == 200 and response.json()['itens'] == []
    event = next(json.loads(r.message) for r in caplog.records if r.name == 'huginn.audit')
    assert event['status'] == 200 and event['registros'] == 0
    assert event['request_id'] == response.json()['request_id']
