"""Fixed metadata-only inspection; never query business tables or accept SQL."""
from app.oracle_connector import OracleConfig, connect_readonly

TABLES = ("PCPRODUT", "PCFORNEC", "PCPRODFILIAL", "PCPRODFORNEC", "PCNFENT", "PCMOV", "PCPEDIDO")
METADATA_SQL = """
    SELECT c.owner, c.table_name, c.column_name, c.data_type
    FROM all_tab_columns c
    JOIN all_tables t ON t.owner = c.owner AND t.table_name = c.table_name
    WHERE c.table_name IN (:t1,:t2,:t3,:t4,:t5,:t6,:t7)
    ORDER BY c.table_name, c.owner, c.column_id
"""


def inspect_schema(cfg: OracleConfig):
    conn = connect_readonly(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(METADATA_SQL, {f"t{i}": name for i, name in enumerate(TABLES, 1)})
            rows = cur.fetchall()
        found = {name: {} for name in TABLES}
        for owner, table, col, datatype in rows:
            found[table].setdefault(owner, []).append({"coluna": col, "tipo": datatype})
        tables = []
        for name in TABLES:
            if not found[name]:
                tables.append({"nome": name, "proprietario": None, "visivel": False, "colunas": []})
            for owner, columns in sorted(found[name].items()):
                tables.append({"nome": name, "proprietario": owner, "visivel": True, "colunas": columns})
        return {
            "modo": "metadados somente leitura", "tabelas": tables,
            "aviso": "Somente tabelas da lista fixa visíveis ao usuário. Proprietários são separados; sinônimos não são resolvidos. Ausência de metadados pode indicar tabela inexistente ou falta de permissão. Nenhum registro comercial foi consultado.",
        }
    finally:
        conn.close()
