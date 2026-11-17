"""Truthful discovery: no financial operation is enabled without original SQL."""
REPORT_MODULES = ("vendas", "contas-a-receber", "contas-a-pagar", "livro-caixa", "evolucao-diaria")


def capabilities():
    return {
        "api_version": "1.0",
        "diagnostics": {"health": "/health", "oracle_test": "/oracle/test",
                        "oracle_server_time": "/oracle/server-time"},
        "reports": {name: {"available": False, "reason": "original_sql_and_business_rules_required"}
                    for name in REPORT_MODULES},
        "arbitrary_sql": False,
    }
