"""Bound, bounded WinThor catalog queries. Real mode always validates metadata first."""
from dataclasses import dataclass
import os
import re
from app.oracle_connector import OracleConfig, check_connection, connect_readonly

SPECS = {
    'produtos': ('PCPRODUT', 'CODPROD', 'DESCRICAO'),
    'fornecedores': ('PCFORNEC', 'CODFORNEC', 'FORNECEDOR'),
}
TEXT_TYPES = {'VARCHAR2', 'NVARCHAR2', 'CHAR', 'NCHAR'}
METADATA_SQL = '''SELECT c.column_name, c.data_type FROM all_tab_columns c
JOIN all_tables t ON t.owner = c.owner AND t.table_name = c.table_name
WHERE c.owner = :owner AND c.table_name = :table_name
AND c.column_name IN (:code_column, :name_column)'''


class SchemaUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    mode: str
    owner: str | None = None
    oracle: OracleConfig | None = None

    @classmethod
    def load(cls):
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
    cursor.execute(METADATA_SQL, dict(owner=owner, table_name=table,
                                     code_column=code, name_column=name))
    columns = dict(cursor.fetchmany(3))
    if columns.get(code) != 'NUMBER' or columns.get(name) not in TEXT_TYPES:
        raise SchemaUnavailable('Required table or columns not visible/compatible')
    return dict(tabela=table, colunas=[dict(nome=code, tipo=columns[code]),
                                     dict(nome=name, tipo=columns[name])], validado=True)


def diagnostic(settings):
    if settings.mode == 'demo':
        return dict(modo='simulado', validado_no_oracle=False, tabelas=[
            dict(tabela=t, colunas=[dict(nome=c, tipo='NUMBER'), dict(nome=n, tipo='VARCHAR2')],
                 validado=False) for t, c, n in SPECS.values()])
    con = connect_readonly(settings.oracle)
    try:
        with con.cursor() as cursor:
            tables = [validate_schema(cursor, settings.owner, k) for k in SPECS]
        return dict(modo='oracle', validado_no_oracle=True, tabelas=tables)
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
