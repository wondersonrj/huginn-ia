from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.oracle_connector import OracleConfig
from app.schema_diagnostic import METADATA_SQL, TABLES, inspect_schema

PAYLOAD = dict(host='db.local', port=1521, service='ORCL', user='reader', password='synthetic-password')
CONFIG = OracleConfig(**PAYLOAD)


def connection(rows):
    con = MagicMock()
    con.cursor.return_value.__enter__.return_value.fetchall.return_value = rows
    return con


def test_only_fixed_bound_metadata_and_readonly_transaction():
    con = connection([('WINT', 'PCPRODUT', 'CODPROD', 'NUMBER')])
    with patch('oracledb.connect', return_value=con):
        result = inspect_schema(CONFIG)
    calls = con.cursor.return_value.__enter__.return_value.execute.call_args_list
    assert len(calls) == 2
    assert calls[0].args == ('SET TRANSACTION READ ONLY',)
    assert calls[1].args == (METADATA_SQL, {f't{i}': n for i, n in enumerate(TABLES, 1)})
    normalized = ' '.join(METADATA_SQL.upper().split())
    assert 'FROM ALL_TAB_COLUMNS C JOIN ALL_TABLES T' in normalized
    assert set(TABLES) == {'PCPRODUT', 'PCFORNEC', 'PCPRODFILIAL', 'PCPRODFORNEC', 'PCNFENT', 'PCMOV', 'PCPEDIDO'}
    # Business names are bound values; none appears as an SQL source.
    assert all(name not in normalized for name in TABLES)
    con.commit.assert_not_called()
    con.close.assert_called_once()
    assert result['modo'] == 'metadados somente leitura'
    assert result['tabelas'][0]['proprietario'] == 'WINT'


def test_separates_owners_and_marks_missing_tables():
    con = connection([
        ('A', 'PCPRODUT', 'CODPROD', 'NUMBER'),
        ('A', 'PCPRODUT', 'DESCRICAO', 'VARCHAR2'),
        ('B', 'PCPRODUT', 'OTHER', 'VARCHAR2'),
    ])
    with patch('app.schema_diagnostic.connect_readonly', return_value=con):
        tables = inspect_schema(CONFIG)['tabelas']
    products = [t for t in tables if t['nome'] == 'PCPRODUT']
    assert [t['proprietario'] for t in products] == ['A', 'B']
    assert [len(t['colunas']) for t in products] == [2, 1]
    missing = next(t for t in tables if t['nome'] == 'PCMOV')
    assert missing == dict(nome='PCMOV', proprietario=None, visivel=False, colunas=[])
    assert {t['nome'] for t in tables} == set(TABLES)


def test_empty_metadata_is_not_claimed_as_missing_table():
    with patch('app.schema_diagnostic.connect_readonly', return_value=connection([])):
        result = inspect_schema(CONFIG)
    assert len(result['tabelas']) == 7
    assert all(not t['visivel'] for t in result['tabelas'])
    assert 'falta de permissão' in result['aviso']


@pytest.mark.parametrize('stage', ['execute', 'fetchall'])
def test_diagnostic_closes_connection_on_failure(stage):
    con = connection([])
    getattr(con.cursor.return_value.__enter__.return_value, stage).side_effect = RuntimeError('failure')
    with patch('app.schema_diagnostic.connect_readonly', return_value=con), pytest.raises(RuntimeError):
        inspect_schema(CONFIG)
    con.close.assert_called_once()
    con.commit.assert_not_called()


def client(host='127.0.0.1'):
    return TestClient(app, client=(host, 1234))


def test_endpoint_passes_only_validated_connection_config():
    expected = dict(modo='metadados somente leitura', tabelas=[], aviso='synthetic')
    with patch('app.main.inspect_schema', return_value=expected) as inspect:
        response = client().post('/api/oracle/diagnostico', json=PAYLOAD)
    assert response.status_code == 200
    assert response.json() == expected
    inspect.assert_called_once_with(CONFIG)
    assert PAYLOAD['password'] not in response.text


@pytest.mark.parametrize('changes', [dict(sql='SELECT * FROM PCMOV'), dict(tables=['UNAUTHORIZED']), dict(port=0), dict(password=''), dict(host='x;invalid')])
def test_endpoint_rejects_arbitrary_queries_tables_and_invalid_input(changes):
    with patch('app.main.inspect_schema') as inspect:
        response = client().post('/api/oracle/diagnostico', json=PAYLOAD | changes)
    assert response.status_code == 422
    assert PAYLOAD['password'] not in response.text
    inspect.assert_not_called()


@pytest.mark.parametrize('host,origin', [('192.0.2.1', None), ('127.0.0.1', 'https://foreign.example')])
def test_endpoint_enforces_local_access(host, origin):
    with patch('app.main.inspect_schema') as inspect:
        response = client(host).post('/api/oracle/diagnostico', json=PAYLOAD, headers={'Origin': origin} if origin else {})
    assert response.status_code == 403
    inspect.assert_not_called()


def test_endpoint_hides_driver_errors():
    with patch('app.main.inspect_schema', side_effect=RuntimeError('synthetic-password')):
        response = client().post('/api/oracle/diagnostico', json=PAYLOAD)
    assert response.status_code == 502
    assert PAYLOAD['password'] not in response.text


def test_endpoint_rejects_malformed_json():
    with patch('app.main.inspect_schema') as inspect:
        response = client().post('/api/oracle/diagnostico', content=b'{broken', headers={'Content-Type': 'application/json'})
    assert response.status_code == 422
    inspect.assert_not_called()
