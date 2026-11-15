"""CI-only driver double. Copied into a disposable installed tree AFTER artifact build.
No switch in the shipped application can activate this fixture. No network access.
"""
import json
from pathlib import Path


def is_thin_mode(): return True

def makedsn(host, port, service_name):
    assert host == '127.0.0.1'
    return service_name


class ErrorInfo:
    def __init__(self, code): self.full_code = code


def fail(code): raise RuntimeError(ErrorInfo(code))


def connect(*, user, password, dsn, tcp_connect_timeout, retry_count):
    assert tcp_connect_timeout == 5 and retry_count == 0
    if password == 'invalid-synthetic': fail('ORA-01017')
    if dsn == 'UNAVAILABLE': fail('DPY-6005')
    if dsn == 'TIMEOUT': fail('DPY-4024')
    return Connection(dsn)


class Connection:
    def __init__(self, service):
        self.service = service
        self.readonly = False
    def cursor(self): return Cursor(self)
    def close(self): pass
    def commit(self): raise AssertionError('Commit is forbidden')


class Cursor:
    def __init__(self, connection): self.connection = connection; self.rows = []
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, sql, binds=None):
        connection = self.connection
        if sql == 'SET TRANSACTION READ ONLY':
            connection.readonly = True
            return
        assert connection.readonly and connection.call_timeout == 5000
        event = None
        if sql.startswith('SELECT SYS_CONTEXT('):
            self.rows = [('WINT', 'SYNTHETIC')]; event = 'session_context'
        elif sql == 'SELECT 1 FROM DUAL':
            self.rows = [(1,)]; event = 'dual'
        elif 'FROM all_synonyms' in sql:
            self.rows = []; event = 'synonyms'
        elif 'SELECT DISTINCT owner' in sql:
            self.rows = [('WINT',)]; event = 'owners'
        elif 'WHERE 1 = 0' in sql:
            if '"WRONG"' in sql: fail('ORA-00942')
            if connection.service == 'NOSELECT': fail('ORA-00942')
            from types import SimpleNamespace
            self.description = [('CODE', SimpleNamespace(name='DB_TYPE_NUMBER')), ('NAME', SimpleNamespace(name='DB_TYPE_VARCHAR'))]
            self.rows = []; event = 'select_projection'
        elif 'FROM all_tab_columns' in sql:
            assert set(binds) == {'owner', 'table_name', 'code_column', 'name_column'}
            assert binds['table_name'] in {'PCPRODUT', 'PCFORNEC'}
            self.rows = [] if binds['owner'] != 'WINT' else [(binds['code_column'], 'NUMBER'), (binds['name_column'], 'VARCHAR2')]
            event = binds['table_name'] + '_metadata'
        else:
            assert sql.startswith('SELECT ') and 'OFFSET :offset ROWS FETCH NEXT :limite ROWS ONLY' in sql
            assert set(binds) == {'codigo', 'nome', 'offset', 'limite'}
            assert binds['codigo'] in {101, 202} and binds['offset'] == 0 and binds['limite'] <= 51
            if connection.service == 'NOSELECT': fail('ORA-00942')
            if connection.service == 'QUERYTIMEOUT': fail('ORA-01013')
            table, code, name, expected, label = ('PCPRODUT', 'CODPROD', 'DESCRICAO', 101, 'Produto CI Oracle') if '"PCPRODUT"' in sql else ('PCFORNEC', 'CODFORNEC', 'FORNECEDOR', 202, 'Fornecedor CI Oracle')
            assert f'SELECT "{code}", "{name}" FROM "WINT"."{table}"' in sql
            assert f'"{code}" = :codigo' in sql and binds['codigo'] == expected
            self.rows = [(expected, label)]; event = table + '_bound_query'
        # Fixed event names only; never emit binds, passwords, DSN or row data.
        with (Path(__file__).parent / 'oracle-fixture-events.jsonl').open('a') as stream:
            stream.write(json.dumps({'event': event}) + '\n')
    def fetchone(self): return self.rows[0] if self.rows else None
    def fetchmany(self, count): return self.rows[:count]
