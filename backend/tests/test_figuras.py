"""Figuras tributarias: valores ficticios no formato da PCTRIBUT."""
from decimal import Decimal as D

from app.fiscal.figuras import Figura, auditar, figura_sugerida


def fig(cod, msg, cst, icm, base, fecp, qt):
    return Figura(cod, msg, cst, D(icm) if icm else None, D(base) if base else None,
                  D(fecp) if fecp else None, qt_produtos=qt)


FIGS = [
    fig(1, "OUTROS COM ST", "70", "20", "54.5455", "2", 50),
    fig(2, "OUTROS COM ST B", "70", "20", "54.5500", "2", 5),
    fig(3, "SEM USO", "20", "37", "30.7700", None, 100),
    fig(4, "RECOLHIDO ANTERIORMENTE", "900", "0", "0", None, 3),
]


def test_carga_efetiva_com_fecp_e_padrao_rj():
    assert FIGS[0].carga_efetiva("RJ") == D("12.00")
    assert FIGS[2].carga_efetiva("RJ") == D("12.00")   # (37 + 2 padrao) x 30,77%


def test_auditoria_acha_sem_uso_csosn_e_fecp():
    cod = {(a.codst, a.codigo) for a in auditar(FIGS, "RJ")}
    assert (3, "FIGURA_SEM_USO_EM_USO") in cod
    assert (4, "CSOSN_EM_REGIME_NORMAL") in cod
    assert (3, "FECP_EM_BRANCO") in cod


def test_figura_sugerida_ignora_sem_uso():
    f = figura_sugerida(FIGS, "RJ", {"20", "70"}, D("12"))
    assert f is not None and f.codst == 1
