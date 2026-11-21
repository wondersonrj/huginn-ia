"""Controle do NSU e das esperas obrigatorias por CNPJ (NT 2014.002).

- cStat 137 (nenhum documento) ou ultNSU == maxNSU: aguardar 1 hora.
- cStat 656 (consumo indevido): aguardar 1 hora; consultar antes zera a contagem.
- Limite local de consultas por hora, abaixo do limite da SEFAZ (20/h para consNSU/consChNFe).
O estado e gravado de forma atomica (arquivo temporario + replace).
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from .distribuicao import NSU_ZERO, normalizar_cnpj, normalizar_nsu

ESPERA = timedelta(hours=1)
LIMITE_CONSULTAS_HORA = 15   # margem abaixo de 20


@dataclass
class EstadoCNPJ:
    cnpj: str
    ult_nsu: str = NSU_ZERO
    max_nsu: str = NSU_ZERO
    aguardar_ate: str = ""            # ISO; vazio = livre
    motivo_espera: str = ""
    consultas: list[str] = field(default_factory=list)   # horarios ISO das consultas na ultima hora
    ultimo_c_stat: str = ""
    ultimo_x_motivo: str = ""

    def pode_consultar(self, agora: datetime) -> tuple[bool, str]:
        if self.aguardar_ate:
            limite = datetime.fromisoformat(self.aguardar_ate)
            if agora < limite:
                return False, f"Aguardar até {limite:%d/%m/%Y %H:%M} ({self.motivo_espera})."
        recentes = [c for c in self.consultas if datetime.fromisoformat(c) > agora - timedelta(hours=1)]
        if len(recentes) >= LIMITE_CONSULTAS_HORA:
            return False, f"Limite local de {LIMITE_CONSULTAS_HORA} consultas por hora atingido."
        return True, ""

    def registrar_consulta(self, agora: datetime) -> None:
        self.consultas = [c for c in self.consultas if datetime.fromisoformat(c) > agora - timedelta(hours=1)]
        self.consultas.append(agora.isoformat(timespec="seconds"))

    def aplicar_retorno(self, agora: datetime, c_stat: str, x_motivo: str, ult_nsu: str, max_nsu: str) -> None:
        self.ultimo_c_stat, self.ultimo_x_motivo = c_stat, x_motivo[:200]
        # A SEFAZ devolve ultNSU tambem na rejeicao 656 (NT v1.14): sempre seguir o que ela informa.
        if ult_nsu and int(ult_nsu) >= int(self.ult_nsu):
            self.ult_nsu = normalizar_nsu(ult_nsu)
        if max_nsu and int(max_nsu) > 0:
            self.max_nsu = normalizar_nsu(max_nsu)
        if c_stat == "656":
            self._esperar(agora, "consumo indevido (656)")
        elif c_stat == "137" or (c_stat == "138" and int(self.ult_nsu) >= int(self.max_nsu)):
            self._esperar(agora, "sem documentos novos")
        elif c_stat == "138":
            self.aguardar_ate, self.motivo_espera = "", ""

    def _esperar(self, agora: datetime, motivo: str) -> None:
        self.aguardar_ate = (agora + ESPERA).isoformat(timespec="seconds")
        self.motivo_espera = motivo


class RepositorioEstado:
    def __init__(self, arquivo: Path):
        self.arquivo = Path(arquivo)

    def _ler(self) -> dict:
        if not self.arquivo.exists():
            return {}
        return json.loads(self.arquivo.read_text(encoding="utf-8"))

    def obter(self, cnpj: str) -> EstadoCNPJ:
        cnpj = normalizar_cnpj(cnpj)
        dados = self._ler().get(cnpj)
        return EstadoCNPJ(**dados) if dados else EstadoCNPJ(cnpj=cnpj)

    def todos(self) -> list[EstadoCNPJ]:
        return [EstadoCNPJ(**v) for v in self._ler().values()]

    def salvar(self, estado: EstadoCNPJ) -> None:
        dados = self._ler()
        dados[estado.cnpj] = asdict(estado)
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.arquivo.parent, prefix=".estado-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as arq:
                json.dump(dados, arq, ensure_ascii=False, indent=2)
            os.replace(tmp, self.arquivo)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
