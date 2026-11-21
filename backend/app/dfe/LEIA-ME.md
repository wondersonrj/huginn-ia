# HUGINN Web — captura de NF-e de entrada pela SEFAZ (v0.1)

Baixa da SEFAZ, sem passar pela rotina 1095, os documentos emitidos contra o CNPJ da empresa. Usa o web service oficial **NFeDistribuicaoDFe** do Ambiente Nacional (NT 2014.002), com o **certificado A1** da empresa. Não grava nada no WinThor.

## Estrutura

| Módulo | Faz |
|---|---|
| `distribuicao.py` | Monta `distDFeInt` 1.01 (distNSU, consNSU, consChNFe) e o envelope SOAP 1.2. Lê `retDistDFeInt`, descompacta o `docZip` e classifica o documento (procNFe, resNFe ou evento). XML seguro (sem DTD), com limite de tamanho. Aceita CNPJ alfanumérico. |
| `estado.py` | Guarda por CNPJ o NSU e as esperas obrigatórias: **1 hora** depois de cStat 137, de ultNSU = maxNSU ou de cStat 656. Também limita localmente a 15 consultas por hora. A gravação é atômica. |
| `armazenamento.py` | Grava `Entrada/<chave>-procNFe.xml` (lido pelo HUGINN XML), `Resumos/`, `Eventos/` e `indice.jsonl`. Os bytes ficam exatamente como vieram, e a gravação é idempotente por SHA-256: se chegar um conteúdo diferente para a mesma chave, ele é gravado ao lado como conflito. |
| `transporte.py` | Envia por SOAP com o A1: o `.pfx` é aberto em memória e a chave só passa por uma pasta temporária privada, cifrada, que é apagada em seguida. Recusa certificado vencido e só envia para `*.fazenda.gov.br`. |
| `sincronizador.py` | Ciclo distNSU até esvaziar a fila ou até a SEFAZ mandar esperar. Só avança o NSU depois de gravar o lote. |
| `cli.py` | Teste manual pelo terminal. A senha é pedida na hora e não é guardada. |

## Teste manual (no servidor, com o A1)

```
cd backend
python -m app.dfe.cli --cnpj <CNPJ> --uf RJ --pfx C:\certs\empresa.pfx --ambiente 1 --pasta C:\HUGINN\dfe
python -m app.dfe.cli --cnpj <CNPJ> --pasta C:\HUGINN\dfe --estado
```

A primeira consulta começa do NSU zero e traz o que a SEFAZ ainda guarda para o CNPJ (os últimos 90 dias, segundo os fornecedores do mercado).

## Pendente (decisões do responsável)

- [ ] Certificado **A1** e onde ele fica: guardar protegido por DPAPI, como as conexões Oracle.
- [ ] **Manifestação "ciência da operação"** (evento 210210), sem a qual a SEFAZ só entrega o resumo. Precisa de assinatura XML e da decisão: automática ou nota a nota.
- [ ] CNPJs a consultar (matriz e filiais com a mesma raiz) e o agendamento (serviço do HUGINN Web).
- [ ] Endpoints e tela no HUGINN Web, depois das decisões acima.
- [ ] HUGINN XML (Delphi): aceitar CNPJ alfanumérico (NT 2014.002 v1.40).

## Status

- [x] Escrito
- [x] Testado com respostas simuladas da SEFAZ e certificado de teste (`tests/test_dfe.py`, 11 testes)
- [ ] Testado contra a SEFAZ real (depende do A1)
