"""Teste manual da captura DF-e pela linha de comando (sem API e sem guardar senha).

  python -m app.dfe.cli --cnpj 11222333000181 --uf RJ --pfx C:\\certs\\empresa.pfx --ambiente 1
  python -m app.dfe.cli --cnpj 11222333000181 --estado

A senha do certificado e pedida no terminal (getpass) e nao e gravada.
Respeita a espera de 1 hora da SEFAZ: se nao puder consultar, so mostra quando podera.
"""
from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from .armazenamento import Armazenamento
from .distribuicao import ErroDistribuicao, normalizar_cnpj
from .estado import RepositorioEstado
from .sincronizador import sincronizar
from .ciencia import manifestar_pendentes
from .transporte import TransporteSefaz, contexto_tls, info_certificado, ler_certificado


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="HUGINN - captura de NF-e de entrada (NFeDistribuicaoDFe)")
    p.add_argument("--cnpj", required=True)
    p.add_argument("--uf", help="UF do interessado (ex.: RJ)")
    p.add_argument("--pfx", help="certificado A1 (.pfx)")
    p.add_argument("--ambiente", type=int, choices=(1, 2), help="1 = produção, 2 = homologação")
    p.add_argument("--pasta", default="dfe_dados", help="pasta de dados (Entrada, Resumos, Eventos, estado)")
    p.add_argument("--cafile", help="cadeia ICP-Brasil, se o Windows não confiar no servidor da SEFAZ")
    p.add_argument("--estado", action="store_true", help="só mostra o estado do CNPJ, sem consultar")
    p.add_argument("--manifestar", action="store_true",
                   help="OPCIONAL: envia 'Ciência da Operação' para os resumos pendentes (até 20)")
    a = p.parse_args(argv)
    pasta = Path(a.pasta)
    repo = RepositorioEstado(pasta / "estado_nsu.json")
    try:
        cnpj = normalizar_cnpj(a.cnpj)
        if a.estado:
            e = repo.obter(cnpj)
            print(f"CNPJ {cnpj}: ultNSU {e.ult_nsu} / maxNSU {e.max_nsu}; último cStat {e.ultimo_c_stat} "
                  f"{e.ultimo_x_motivo}; aguardar até: {e.aguardar_ate or 'livre'}")
            return 0
        if not (a.uf and a.pfx and a.ambiente):
            p.error("--uf, --pfx e --ambiente são obrigatórios para consultar")
        pfx = Path(a.pfx).read_bytes()
        senha = getpass.getpass("Senha do certificado: ")
        info = info_certificado(ler_certificado(pfx, senha)[1])
        print(f"Certificado: {info.titular} (válido até {info.validade:%d/%m/%Y})")
        if info.cnpj and info.cnpj[:8] != cnpj[:8]:
            print("ATENÇÃO: a raiz do CNPJ consultado é diferente da do certificado; a SEFAZ vai rejeitar.")
            return 2
        transporte = TransporteSefaz(contexto_tls(pfx, senha), a.cafile)
        armazenamento = Armazenamento(pasta)
        res = sincronizar(cnpj, a.uf.upper(), a.ambiente, transporte, repo, armazenamento)
        if a.manifestar:
            chave_priv, cert, _ = ler_certificado(pfx, senha)
            for item in manifestar_pendentes(cnpj, a.ambiente, transporte, chave_priv, cert, armazenamento):
                print(f"Ciência {item['chave']}: {'OK' if item['ok'] else 'FALHOU'} {item['c_stat']} {item['x_motivo']}")
    except (ErroDistribuicao, OSError) as exc:
        print(f"Erro: {exc}")
        return 1
    print(f"Consultou: {'sim' if res.consultou else 'não'} | lotes {res.lotes} | novos {res.novos} "
          f"(completos {res.completos}, resumos {res.resumos}, eventos {res.eventos}, conflitos {res.conflitos})")
    print(f"NSU {res.ult_nsu} de {res.max_nsu} | {res.mensagem}")
    if res.proxima:
        print(f"Próxima consulta permitida: {res.proxima}")
    for erro in res.erros:
        print(f"  erro: {erro}")
    return 0 if not res.erros else 1


if __name__ == "__main__":
    raise SystemExit(main())
