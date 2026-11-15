"""DUAL success never implies WinThor permission; only allowlisted read-only SQL."""
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from app import winthor
from app.oracle_connector import OracleConfig

SETTINGS = winthor.Settings('oracle', 'WRONG', OracleConfig('synthetic.test', 1521, 'TEST', 'reader', 'never-log-this'))


class Cursor:
    def __init__(self, failure=None, hidden=False, synonym=False, incompatible=False):
        self.failure, self.hidden, self.synonym, self.incompatible = failure, hidden, synonym, incompatible
        self.calls = []; self.rows = []
        self.description = [('CODE', SimpleNamespace(name='DB_TYPE_NUMBER')), ('NAME', SimpleNamespace(name='DB_TYPE_VARCHAR'))]
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, sql, binds=None):
        self.calls.append((sql, binds))
        assert sql.startswith('SELECT ') and all(word not in sql for word in ('GRANT ', 'ALTER ', 'UPDATE ', 'DELETE ', 'INSERT '))
        if sql == winthor.METADATA_SQL:
            assert 'all_tables' not in sql.lower()
            self.rows = [] if self.hidden else [(binds['code_column'], 'VARCHAR2' if self.incompatible else 'NUMBER'), (binds['name_column'], 'VARCHAR2')]
        elif sql == winthor.OWNER_SQL: self.rows = [('WINT',), ('OTHER',)]
        elif sql == winthor.SYNONYM_SQL: self.rows = [('PUBLIC', 'WINT', binds['table_name'], 'REMOTE' if self.synonym == 'remote' else None)] if self.synonym else []
        elif 'SYS_CONTEXT' in sql: self.rows = [('SESSION_OWNER', 'READER')]
        elif 'WHERE 1 = 0' in sql:
            if self.failure: raise RuntimeError(SimpleNamespace(full_code=self.failure, message='never-log-this'))
            self.rows = []
        else:
            assert 'OFFSET :offset' in sql and binds['codigo'] == 7
            self.rows = [(7, 'Allowed record')]
    def fetchmany(self, size): return self.rows[:size]
    def fetchone(self): return self.rows[0] if self.rows else None


class Connection:
    def __init__(self, cursor): self.value = cursor; self.closed = False
    def cursor(self): return self.value
    def close(self): self.closed = True
    def commit(self): raise AssertionError('No commit allowed')


@pytest.mark.parametrize('error,cause', [('ORA-00942', 'objeto_ausente_ou_nao_visivel'), ('ORA-01031', 'select_negado'), ('ORA-00904', 'coluna_ausente'), ('ORA-01013', 'erro_oracle')])
def test_dual_ok_schema_failure_is_per_table_actionable_and_secret_free(error, cause):
    cursor = Cursor(failure=error); con = Connection(cursor)
    with patch('app.winthor.check_connection', return_value={'conectado': True}), patch('app.winthor.connect_readonly', return_value=con):
        assert winthor.health(SETTINGS)['conectado'] is True
        result = winthor.diagnostic(SETTINGS)
    assert not result['validado_no_oracle'] and con.closed
    assert len(result['tabelas']) == 2
    assert all(t['causa'] == cause and t['owners_candidatos'] == ['WINT', 'OTHER'] for t in result['tabelas'])
    assert SETTINGS.owner == 'WRONG' and 'never-log-this' not in str(result)
    assert result['contexto']['schema_sessao'] == 'SESSION_OWNER'


@pytest.mark.parametrize('kind', ['produtos', 'fornecedores'])
def test_dictionary_hidden_but_safe_projection_describes_then_bound_query_succeeds(kind):
    cursor = Cursor(hidden=True); con = Connection(cursor)
    with patch('app.winthor.connect_readonly', return_value=con):
        result = winthor.search(SETTINGS, kind, code=7)
    assert result['itens'] == [{'codigo': '7', 'nome': 'Allowed record'}] and con.closed
    assert cursor.calls[-2][0].endswith('WHERE 1 = 0')
    assert cursor.calls[-1][1]['codigo'] == 7


@pytest.mark.parametrize('synonym', [True, 'remote'])
def test_synonym_discovery_never_follows_or_changes_destination(synonym):
    cursor = Cursor(hidden=True, synonym=synonym); con = Connection(cursor)
    with patch('app.winthor.connect_readonly', return_value=con):
        result = winthor.diagnostic(SETTINGS)
    assert not result['validado_no_oracle']
    assert result['tabelas'][0]['sinonimos'][0]['destino_owner'] == 'WINT'
    assert result['tabelas'][0]['sinonimos'][0]['remoto'] == (synonym == 'remote')
    assert not any('WHERE 1 = 0' in sql for sql, _ in cursor.calls)
    assert SETTINGS.owner == 'WRONG'


def test_incompatible_columns_do_not_get_business_query_or_false_grant_diagnosis():
    cursor = Cursor(incompatible=True); con = Connection(cursor)
    with patch('app.winthor.connect_readonly', return_value=con):
        result = winthor.diagnostic(SETTINGS)
    assert result['tabelas'][0]['causa'] == 'colunas_incompativeis'
    assert not any('OFFSET' in sql for sql, _ in cursor.calls)


def test_owner_injection_rejected_before_any_sql():
    cursor = Cursor()
    with pytest.raises(ValueError): winthor.validate_schema(cursor, 'WINT".PCMOV--', 'produtos')
    assert not cursor.calls
