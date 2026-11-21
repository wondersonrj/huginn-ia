"""Grava os documentos baixados.

<pasta>/Entrada/<chave>-procNFe.xml   XML completo (o HUGINN XML le daqui)
<pasta>/Resumos/<chave>-resNFe.xml    resumo (falta manifestacao para baixar o completo)
<pasta>/Eventos/<chave>-<tpEvento>-<nsu>.xml
<pasta>/Outros/<nsu>.xml
<pasta>/indice.jsonl                  uma linha por documento recebido (sem o XML)
Os bytes sao gravados exatamente como a SEFAZ entregou. Idempotente por nome+SHA-256.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path

from .distribuicao import Documento

_SEGURO = re.compile(r"[^0-9A-Za-z_-]")


def _nome(texto: str) -> str:
    return _SEGURO.sub("", texto)[:60] or "sem_nome"


class Armazenamento:
    def __init__(self, pasta: Path):
        self.pasta = Path(pasta)

    def caminho(self, doc: Documento) -> Path:
        if doc.tipo == "procNFe" and doc.chave:
            return self.pasta / "Entrada" / f"{_nome(doc.chave)}-procNFe.xml"
        if doc.tipo == "resNFe" and doc.chave:
            return self.pasta / "Resumos" / f"{_nome(doc.chave)}-resNFe.xml"
        if doc.tipo in ("procEventoNFe", "resEvento") and doc.chave:
            return self.pasta / "Eventos" / f"{_nome(doc.chave)}-{_nome(doc.evento)}-{doc.nsu}.xml"
        return self.pasta / "Outros" / f"{doc.nsu}.xml"

    def gravar(self, doc: Documento, cnpj: str) -> tuple[Path, str]:
        """Devolve (arquivo, situacao) com situacao em: novo | igual | conflito."""
        destino = self.caminho(doc)
        destino.parent.mkdir(parents=True, exist_ok=True)
        sha = hashlib.sha256(doc.conteudo).hexdigest()
        if destino.exists():
            if hashlib.sha256(destino.read_bytes()).hexdigest() == sha:
                return destino, "igual"
            destino = destino.with_name(f"{destino.stem}.{sha[:12]}{destino.suffix}")
            situacao = "conflito"
        else:
            situacao = "novo"
        tmp = destino.with_suffix(destino.suffix + ".tmp")
        tmp.write_bytes(doc.conteudo)
        os.replace(tmp, destino)
        if hashlib.sha256(destino.read_bytes()).hexdigest() != sha:
            raise OSError("Falha de integridade ao gravar o documento.")
        self._indexar(doc, cnpj, destino, sha, situacao)
        return destino, situacao

    def _indexar(self, doc: Documento, cnpj: str, destino: Path, sha: str, situacao: str) -> None:
        linha = {
            "recebido_em": datetime.now().isoformat(timespec="seconds"), "cnpj_interessado": cnpj,
            "nsu": doc.nsu, "tipo": doc.tipo, "chave": doc.chave, "emitente_cnpj": doc.emitente_cnpj,
            "emitente_nome": doc.emitente_nome, "emissao": doc.emissao, "valor": doc.valor,
            "situacao_nfe": doc.situacao, "evento": doc.evento, "arquivo": str(destino.relative_to(self.pasta)),
            "sha256": sha, "gravacao": situacao,
        }
        self.pasta.mkdir(parents=True, exist_ok=True)
        with open(self.pasta / "indice.jsonl", "a", encoding="utf-8") as arq:
            arq.write(json.dumps(linha, ensure_ascii=False) + "\n")

    def indice(self, limite: int = 500) -> list[dict]:
        arq = self.pasta / "indice.jsonl"
        if not arq.exists():
            return []
        linhas = arq.read_text(encoding="utf-8").splitlines()[-limite:]
        return [json.loads(l) for l in reversed(linhas) if l.strip()]

    def resumos_pendentes(self) -> list[dict]:
        """Resumos cujo XML completo ainda nao chegou (precisam de manifestacao)."""
        completos = {p.name.split("-")[0] for p in (self.pasta / "Entrada").glob("*-procNFe.xml")}
        vistos, pendentes = set(), []
        for item in self.indice(100000):
            if item["tipo"] == "resNFe" and item["chave"] not in completos and item["chave"] not in vistos:
                vistos.add(item["chave"])
                pendentes.append(item)
        return pendentes
