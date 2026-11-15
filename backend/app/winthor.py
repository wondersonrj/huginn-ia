"""Bound, bounded WinThor catalog queries. Real mode always validates metadata first."""
from dataclasses import dataclass
import os
import re
from app.connection_store import SelectionRequired, current_store
from app.oracle_connector import OracleConfig, check_connection, connect_readonly, connection_diagnostic

SPECS = {
    'produtos': ('PCPRODUT', 'CODPROD', 'DESCRICAO'),
    'fornecedores': ('PCFORNEC', 'CODFORNEC', 'FORNECEDOR'),
}
TEXT_TYPES = {'VARCHAR2', 'NVARCHAR2', 'CHAR', 'NCHAR'}
METADATA_SQL = '''SELECT c.column_name, c.data_type FROM all_tab_columns c
WHERE c.owner = :owner AND c.table_name = :table_name
AND c.column_name IN (:code_column, :name_column)'''


OWNER_SQL = """SELECT DISTINCT owner FROM all_tab_columns
WHERE table_name = :table_name AND column_name IN (:code_column, :name_column)
ORDER BY owner FETCH FIRST 21 ROWS ONLY"""
SYNONYM_SQL = """SELECT owner, table_owner, table_name, db_link FROM all_synonyms
WHERE synonym_name = :table_name AND owner IN (:owner, 'PUBLIC') AND ROWNUM <= 21"""
IDENTIFIER = re.compile(r'[A-Z][A-Z0-9_]{0,29}\Z')


class SchemaUnavailable(Exception):
    def __init__(self, message='Schema não confirmado: execute Diagnosticar estrutura; não é possível presumir falta de SELECT.', cause='colunas_incompativeis'):
        super().__init__(message)
        self.cause = cause


def identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError('Owner fora do formato suportado')
    return value


def probe(cursor, owner, kind):
    table, code, name = SPECS[kind]
    identifier(owner)
    # Parse/describe only: no commercial rows, SQL identifiers strictly allowlisted.
    cursor.execute(f'SELECT "{code}", "{name}" FROM "{owner}"."{table}" WHERE 1 = 0')
    types = {getattr(column[1], 'name', '') for column in (cursor.description or [])}
    if (len(cursor.description or []) != 2 or getattr(cursor.description[0][1], 'name', '') != 'DB_TYPE_NUMBER'
            or getattr(cursor.description[1][1], 'name', '') not in {'DB_TYPE_VARCHAR', 'DB_TYPE_NVARCHAR', 'DB_TYPE_CHAR', 'DB_TYPE_NCHAR'}):
        raise SchemaUnavailable('Colunas ausentes ou tipos incompatíveis; peça ao DBA somente os metadados esperados.')
    return types



@dataclass(frozen=True)
class Settings:
    mode: str
    owner: str | None = None
    oracle: OracleConfig | None = None
    profile: dict | None = None

    @classmethod
    def load(cls, connection_id=None, revision=None):
        store = current_store()
        resolved = store.selected(connection_id, revision) if store else None
        if resolved:
            return cls('oracle', resolved.profile['owner'], resolved.config, resolved.profile)
        if connection_id or revision:
            raise SelectionRequired('Connection no longer selected')
        mode = os.environ.get('HUGINN_WINTHOR_MODE', 'demo')
        if mode == 'demo':
            return cls(mode)
        if mode != 'oracle':
            raise ValueError('Invalid mode')
        owner = os.environ.get('HUGINN_ORACLE_OWNER', '')
        # Identifiers cannot be bound: only one explicit, conventional Oracle schema.
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,29}', owner):
            raise ValueError('Invalid owner')
        cfg = OracleConfig.from_env()
        cfg.validate()
        return cls(mode, owner, cfg)


def validate_schema(cursor, owner, kind):
    table, code, name = SPECS[kind]
    identifier(owner)
    try:
        cursor.execute(METADATA_SQL, dict(owner=owner, table_name=table,
                                         code_column=code, name_column=name))
        columns = dict(cursor.fetchmany(3))
    except Exception as exc:
        if getattr(exc.args[0], 'full_code', '') not in {'ORA-00942', 'ORA-01031'}:
            raise
        columns = {}
    if not columns:
        # No dictionary row does not prove a missing grant/table. Describe the exact
        # authorized SELECT without fetching data; DB still enforces all permissions.
        cursor.execute(SYNONYM_SQL, dict(owner=owner, table_name=table))
        if cursor.fetchmany(1):
            raise SchemaUnavailable('Sinônimo detectado: confirme explicitamente o owner da tabela base no perfil; nenhum destino foi escolhido.', cause='sinonimo_exige_destino_explicito')
        probe(cursor, owner, kind)
        return dict(tabela=table, colunas=[dict(nome=code, tipo='NUMBER'), dict(nome=name, tipo='TEXT')], validado=True, evidencia='select_sem_linhas')
    if columns.get(code) != 'NUMBER' or columns.get(name) not in TEXT_TYPES:
        raise SchemaUnavailable('Required table or columns not visible/compatible')
    return dict(tabela=table, colunas=[dict(nome=code, tipo=columns[code]),
                                     dict(nome=name, tipo=columns[name])], validado=True)


def diagnostic(settings):
    if settings.mode == 'demo':
        return dict(modo='simulado', validado_no_oracle=False, tabelas=[
            dict(tabela=t, colunas=[dict(nome=c, tipo='NUMBER'), dict(nome=n, tipo='VARCHAR2')],
                 validado=False) for t, c, n in SPECS.values()])
    identifier(settings.owner)
    con = connect_readonly(settings.oracle)
    tables = []
    context = {}
    try:
        with con.cursor() as cursor:
            try:
                cursor.execute("SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA'), SYS_CONTEXT('USERENV', 'SESSION_USER') FROM DUAL")
                row = cursor.fetchone()
                if row and all(isinstance(v, str) and IDENTIFIER.fullmatch(v) for v in row[:2]):
                    context = dict(schema_sessao=row[0], usuario_sessao=row[1])
            except Exception:
                pass
            for kind, (table, code, name) in SPECS.items():
                item = dict(tabela=table, colunas=[], validado=False, owner=settings.owner,
                            owners_candidatos=[], sinonimos=[], descoberta_limitada=False)
                try:
                    item.update(validate_schema(cursor, settings.owner, kind))
                    # Metadata does not prove SELECT permission. Describe the exact projection.
                    probe(cursor, settings.owner, kind)
                    item.update(validado=True, causa='leitura_confirmada', acao='Estrutura e SELECT confirmados para este destino.')
                except SchemaUnavailable as exc:
                    item.update(validado=False, causa=exc.cause, acao='Confira owner, nomes e tipos; nenhuma alteração foi feita.')
                except Exception as exc:
                    error = getattr(exc.args[0], 'full_code', '') if exc.args else ''
                    causes = {'ORA-00942': 'objeto_ausente_ou_nao_visivel', 'ORA-01031': 'select_negado',
                              'ORA-00904': 'coluna_ausente'}
                    item.update(validado=False, causa=causes.get(error, 'erro_oracle'), acao=connection_diagnostic(exc))
                # Discovery is informative only. Never select or persist an owner here.
                try:
                    cursor.execute(OWNER_SQL, dict(table_name=table, code_column=code, name_column=name))
                    owners = cursor.fetchmany(21)
                    item['owners_candidatos'] = [row[0] for row in owners[:20] if isinstance(row[0], str) and IDENTIFIER.fullmatch(row[0])]
                    item['descoberta_limitada'] = len(owners) > 20
                    cursor.execute(SYNONYM_SQL, dict(owner=settings.owner, table_name=table))
                    synonyms = cursor.fetchmany(21)
                    item['sinonimos'] = [dict(owner=row[0], destino_owner=row[1], destino_tabela=row[2], remoto=bool(row[3]))
                        for row in synonyms[:20] if all(isinstance(v, str) and IDENTIFIER.fullmatch(v) for v in row[:3])]
                    item['descoberta_limitada'] |= len(synonyms) > 20
                except Exception:
                    item['descoberta_indisponivel'] = True
                tables.append(item)
        return dict(modo='oracle', validado_no_oracle=all(t['validado'] for t in tables),
                    owner_configurado=settings.owner, contexto=context, tabelas=tables,
                    mensagem='DUAL não comprova acesso ao catálogo. Diagnóstico não altera owner, ambiente ou permissões; escolha explicitamente o owner em Editar conexão.')
    finally:
        con.close()


def health(settings):
    if settings.mode == 'demo':
        return dict(modo='simulado', conectado=False, disponivel=True,
                    mensagem='Simulação ativa: dados fictícios, sem conexão Oracle.')
    result = check_connection(settings.oracle)
    return dict(modo='oracle', conectado=result['conectado'], disponivel=result['conectado'],
                mensagem='Oracle confirmou SELECT em somente leitura.' if result['conectado']
                else 'Oracle não confirmou o teste de leitura.')


def search(settings, kind, code=None, name='', page=1, page_size=20):
    # Also enforce limits for internal callers, independently of API validation.
    if kind not in SPECS or not 1 <= page <= 100 or not 1 <= page_size <= 50:
        raise ValueError('Invalid query bounds')
    if code is not None and (type(code) is not int or not 1 <= code <= 9999999999):
        raise ValueError('Invalid code')
    if not isinstance(name, str) or len(name) > 80:
        raise ValueError('Invalid name')
    name = name.strip()
    offset = (page - 1) * page_size
    if settings.mode == 'demo':
        prefix, count = ('Produto demonstrativo', 55) if kind == 'produtos' else ('Fornecedor demonstrativo', 27)
        records = [dict(codigo=str(i), nome=f'{prefix} {i:03d}') for i in range(1, count + 1)]
        records = [r for r in records if (code is None or r['codigo'] == str(code))
                   and name.upper() in r['nome'].upper()]
        rows = records[offset:offset + page_size + 1]
    else:
        con = connect_readonly(settings.oracle)
        try:
            with con.cursor() as cursor:
                validate_schema(cursor, settings.owner, kind)
                table, code_col, name_col = SPECS[kind]
                # Every identifier is a fixed mapping or a validated server configuration.
                if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,29}', settings.owner or ''):
                    raise ValueError('Invalid owner')
                sql = f'''SELECT "{code_col}", "{name_col}" FROM "{settings.owner}"."{table}"
WHERE (:codigo IS NULL OR "{code_col}" = :codigo)
AND (:nome IS NULL OR UPPER("{name_col}") LIKE :nome ESCAPE '\\')
ORDER BY "{code_col}", "{name_col}" OFFSET :offset ROWS FETCH NEXT :limite ROWS ONLY'''
                escaped = name.upper().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
                cursor.arraysize = page_size + 1
                cursor.execute(sql, dict(codigo=code, nome=f'%{escaped}%' if name else None,
                                         offset=offset, limite=page_size + 1))
                rows = [dict(codigo=str(c), nome=n or '') for c, n in cursor.fetchmany(page_size + 1)]
        finally:
            con.close()
    return dict(modo='simulado' if settings.mode == 'demo' else 'oracle',
                itens=rows[:page_size], pagina=page, tamanho=page_size,
                tem_proxima=len(rows) > page_size and page < 100,
                limite_atingido=page == 100 and len(rows) > page_size)
