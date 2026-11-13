from app.oracle_connector import OracleConfig
import pytest

def test_missing_credentials():
    with pytest.raises(ValueError):
        OracleConfig("db.local", 1521, "ORCL", "reader", "").validate()

def test_invalid_port():
    with pytest.raises(ValueError):
        OracleConfig("db.local", 99999, "ORCL", "reader", "test").validate()

def test_invalid_host():
    with pytest.raises(ValueError):
        OracleConfig("db.local;DROP", 1521, "ORCL", "reader", "test").validate()

def test_valid_config():
    OracleConfig("db.local", 1521, "ORCL", "reader", "test").validate()

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.oracle_connector import check_connection, connect_readonly


def config():
    return OracleConfig('db.local', 1521, 'ORCL', 'reader', 'fake-test-password')


def mock_connection():
    con = MagicMock()
    con.cursor.return_value.__enter__.return_value.fetchone.return_value = (1,)
    return con


def test_password_not_in_repr():
    assert config().password not in repr(config())


def test_only_readonly_transaction_and_dual_are_executed():
    con = mock_connection()
    with patch('oracledb.connect', return_value=con) as connect:
        assert check_connection(config())['conectado'] is True
    connect.assert_called_once()
    assert connect.call_args.kwargs['tcp_connect_timeout'] == 5
    assert connect.call_args.kwargs['retry_count'] == 0
    assert con.call_timeout == 5000
    cur = con.cursor.return_value.__enter__.return_value
    assert [call.args[0] for call in cur.execute.call_args_list] == [
        'SET TRANSACTION READ ONLY', 'SELECT 1 FROM DUAL'
    ]
    con.commit.assert_not_called()
    con.close.assert_called_once()


def test_close_if_readonly_setup_fails():
    con = mock_connection()
    con.cursor.return_value.__enter__.return_value.execute.side_effect = RuntimeError('failure')
    with patch('oracledb.connect', return_value=con), pytest.raises(RuntimeError):
        connect_readonly(config())
    con.close.assert_called_once()


def test_close_if_query_fails():
    con = mock_connection()
    cur = con.cursor.return_value.__enter__.return_value
    cur.execute.side_effect = [None, RuntimeError('failure')]
    with patch('oracledb.connect', return_value=con), pytest.raises(RuntimeError):
        check_connection(config())
    con.close.assert_called_once()


def test_empty_result_is_not_success():
    con = mock_connection()
    con.cursor.return_value.__enter__.return_value.fetchone.return_value = None
    with patch('oracledb.connect', return_value=con):
        assert check_connection(config())['conectado'] is False
    con.close.assert_called_once()


def payload():
    return dict(host='db.local', port=1521, service='ORCL', user='reader', password='fake-test-password')


def test_oracle_endpoint_success():
    with patch('app.main.check_connection', return_value={
        'conectado': True, 'modo': 'somente leitura', 'driver': 'python-oracledb Thin'
    }) as check:
        response = TestClient(app, client=('127.0.0.1', 1234)).post('/api/oracle/testar', json=payload())
    assert response.status_code == 200
    assert response.json()['conectado'] is True
    assert check.call_args.args[0] == config()
    assert payload()['password'] not in response.text


@pytest.mark.parametrize('changes', [dict(port=0), dict(host='bad;host'), dict(password=''), dict(sql='DELETE FROM TABELA')])
def test_oracle_endpoint_validation_does_not_echo_secrets(changes):
    with patch('app.main.check_connection') as check:
        response = TestClient(app, client=('127.0.0.1', 1234)).post('/api/oracle/testar', json=payload() | changes)
    assert response.status_code == 422
    assert payload()['password'] not in response.text
    check.assert_not_called()


def test_oracle_endpoint_hides_driver_errors():
    with patch('app.main.check_connection', side_effect=RuntimeError('fake-test-password')):
        response = TestClient(app, client=('127.0.0.1', 1234)).post('/api/oracle/testar', json=payload())
    assert response.status_code == 502
    assert 'fake-test-password' not in response.text


def test_oracle_endpoint_rejects_foreign_origin():
    with patch('app.main.check_connection') as check:
        response = TestClient(app, client=('127.0.0.1', 1234)).post('/api/oracle/testar', json=payload(), headers={'Origin': 'https://other.example'})
    assert response.status_code == 403
    check.assert_not_called()


def test_oracle_endpoint_rejects_remote_client():
    with patch('app.main.check_connection') as check:
        response = TestClient(app, client=('192.0.2.1', 1234)).post('/api/oracle/testar', json=payload())
    assert response.status_code == 403
    check.assert_not_called()


def test_oracle_endpoint_malformed_json():
    with patch('app.main.check_connection') as check:
        response = TestClient(app, client=('127.0.0.1', 1234)).post(
            '/api/oracle/testar', content=b'{broken', headers={'Content-Type': 'application/json'}
        )
    assert response.status_code == 422
    check.assert_not_called()


def test_oracle_endpoint_unconfirmed_result():
    with patch('app.main.check_connection', return_value={'conectado': False}):
        response = TestClient(app, client=('127.0.0.1', 1234)).post('/api/oracle/testar', json=payload())
    assert response.status_code == 502
