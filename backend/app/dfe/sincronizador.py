"""Ciclo de captura por CNPJ: distNSU a partir do ultimo NSU, ate esvaziar a fila
ou ate a SEFAZ mandar esperar. Nunca consulta antes do horario permitido."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from .armazenamento import Armazenamento
from .distribuicao import (URL_HOMOLOGACAO, URL_PRODUCAO, ErroDistribuicao, envelope_soap,
                           ler_retorno, montar_dist_nsu, normalizar_cnpj)
from .estado import RepositorioEstado
from .transporte import Transporte

MAX_LOTES_POR_CICLO = 10


@dataclass
class ResultadoCiclo:
    cnpj: str
    consultou: bool = False
    lotes: int = 0
    novos: int = 0
    completos: int = 0
    resumos: int = 0
    eventos: int = 0
    conflitos: int = 0
    ult_nsu: str = ""
    max_nsu: str = ""
    c_stat: str = ""
    mensagem: str = ""
    proxima: str = ""
    erros: list[str] = field(default_factory=list)


def sincronizar(cnpj: str, uf: str, tp_amb: int, transporte: Transporte, repositorio: RepositorioEstado,
                armazenamento: Armazenamento, agora: Callable[[], datetime] = datetime.now) -> ResultadoCiclo:
    cnpj = normalizar_cnpj(cnpj)
    url = URL_PRODUCAO if tp_amb == 1 else URL_HOMOLOGACAO
    estado = repositorio.obter(cnpj)
    res = ResultadoCiclo(cnpj=cnpj)
    for _ in range(MAX_LOTES_POR_CICLO):
        pode, motivo = estado.pode_consultar(agora())
        if not pode:
            res.mensagem = res.mensagem or motivo
            break
        momento = agora()
        estado.registrar_consulta(momento)
        repositorio.salvar(estado)          # registra a tentativa antes de chamar a SEFAZ
        res.consultou = True
        try:
            retorno = ler_retorno(transporte.enviar(url, envelope_soap(
                montar_dist_nsu(tp_amb, uf, cnpj, estado.ult_nsu))))
        except ErroDistribuicao as exc:
            res.erros.append(str(exc))
            res.mensagem = str(exc)
            break
        res.c_stat = retorno.c_stat
        if retorno.c_stat == "138":
            res.lotes += 1
            for doc in retorno.documentos:
                try:
                    _, situacao = armazenamento.gravar(doc, cnpj)
                except (OSError, ErroDistribuicao) as exc:
                    # Nao avanca o NSU se algum documento do lote nao foi gravado.
                    res.erros.append(f"NSU {doc.nsu}: {exc}")
                    res.mensagem = "Falha ao gravar documento: o NSU não foi avançado."
                    repositorio.salvar(estado)
                    return _fechar(res, estado)
                if situacao != "igual":
                    res.novos += 1
                res.conflitos += situacao == "conflito"
                res.completos += doc.tipo == "procNFe"
                res.resumos += doc.tipo == "resNFe"
                res.eventos += doc.tipo in ("procEventoNFe", "resEvento")
        estado.aplicar_retorno(momento, retorno.c_stat, retorno.x_motivo, retorno.ult_nsu, retorno.max_nsu)
        repositorio.salvar(estado)
        res.mensagem = f"{retorno.c_stat} - {retorno.x_motivo}"
        if retorno.c_stat != "138" or estado.aguardar_ate:
            break
    return _fechar(res, estado)


def _fechar(res: ResultadoCiclo, estado) -> ResultadoCiclo:
    res.ult_nsu, res.max_nsu, res.proxima = estado.ult_nsu, estado.max_nsu, estado.aguardar_ate
    return res
