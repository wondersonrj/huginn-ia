"""Fixed, metadata-only WinThor schema inspection. No arbitrary SQL or business rows."""
from app.oracle_connector import OracleConfig, connect_readonly

TABLES = ("PCPRODUT", "PCFORNEC", "PCPRODFILIAL", "PCPRODFORNEC", "PCNFENT", "PCMOV", "PCPEDIDO")
# Names are candidates only; presence and structure are verified against actual schema.
def inspect_schema(cfg: OracleConfig):
    conn = connect_readonly(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name, column_name, data_type
                FROM all_tab_columns
                WHERE table_name IN (:t1,:t2,:t3,:t4,:t5,:t6,:t7)
                ORDER BY table_name, column_id
            """, dict(zip(("t1","t2","t3","t4","t5","t6","t7"), TABLES)))
            rows = cur.fetchall()
        found = {name: [] for name in TABLES}
        for table, col, datatype in rows:
            found[table].append({"coluna": col, "tipo": datatype})
        return {"modo": "metadados somente leitura", "tabelas": [
            {"nome": name, "visivel": bool(found[name]), "colunas": found[name]}
            for name in TABLES
        ], "aviso": "Ausência de metadados pode indicar tabela inexistente ou falta de permissão. Nenhum registro comercial foi consultado."}
    finally:
        conn.close()
