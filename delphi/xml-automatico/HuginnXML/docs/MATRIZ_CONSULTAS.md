# HUGINN XML Automático — matriz de consultas (somente leitura)

**Origem das colunas:** três traces da rotina 1301 (Statement Tracer for Oracle, 21/11/2026, WinThor 37.0.09.166):
1. importação de XML que parou na checagem de pré-entrada existente;
2. gravação de uma pré-entrada;
3. "Carregar arquivo" da pasta.

As consultas abaixo foram **escritas pela HUGINN** com essas colunas. Não são cópia do SQL da TOTVS. Os traces e XMLs reais **não** são versionados.

Legenda: ✅ coluna vista no trace · ⏳ pendente de confirmação

| # | Finalidade | Tabelas e colunas | Parâmetros | Filial | Status |
|---|---|---|---|---|---|
| Q1 | Filial pelo CNPJ do destinatário | `PCFILIAL.CODIGO, RAZAOSOCIAL, CGC` (CGC comparado sem `.` `/` `-`; ignora a filial 99) | `:CNPJ` | — | ✅ |
| Q2 | Fornecedor pelo CNPJ do emitente | `PCFORNEC.CODFORNEC, FORNECEDOR, CGC, BLOQUEIO, REVENDA` (mesmo critério de CGC da 1301; `REVENDA` em S/O/X) | `:CNPJ` | — | ✅ |
| Q3 | Produto por código de barras UN venda | `PCPRODUT.CODAUXILIAR` (numérico) | `:C0..:Cn`, `:FIL` | `PCPRODUT.CODFILIAL = :FIL` ou nulo/99 | ✅ |
| Q4 | Produto por código de barras UN master | `PCPRODUT.CODAUXILIAR2` (numérico) | idem | idem | ✅ |
| Q5 | Produto por código de fábrica (203) | `UPPER(PCPRODUT.CODFAB)` | `:C0..:Cn`, `:FIL` | idem | ✅ |
| Q6 | Produto por código de fábrica (253) | `PCCODFABRICA.CODPROD, CODFAB, CODFORNEC` → `PCPRODUT` | `:FORN`, `:C0..:Cn`, `:FIL` | idem | ✅ (fator ⏳) |
| Q7 | Travas da 1301 por produto e filial | `PCPRODUT.DTEXCLUSAO, OBS ('PV'), OBS2 ('FL'), PRECIFICESTRANGEIRA, CODFILIAL`; `PCEST` (existe); `PCPRODFILIAL.PROIBIDAVENDA, FORALINHA` | `:FIL1..3`, lista de CODPROD (inteiros validados) | sim | ✅ (tributação, preço e endereço ⏳) |
| Q8 | Custo da última entrada | `PCEST.CODPROD, CODFILIAL, PLIQULTENT, CUSTOULTENT, CUSTOULTENTFIN` | `:FIL`, lista de CODPROD | sim | ✅ (base do custo ⏳) |
| Q9a | Pré-entrada existente | `PCNFENTPREENT.CHAVENFE, NUMTRANSENT, STATUS` | `:CHAVE` | — | ✅ |
| Q9b | Nota já lançada | `PCNFENT.CODFORNEC, NUMNOTA, SERIE, VLTOTAL, NUMTRANSENT, CODFILIAL`; exclui `PCNFCAN.NUMTRANSENT` | `:FORN`, `:NUM`, `:SERIE` | — | ✅ |

Os campos comuns de produto são `PCPRODUT.CODPROD, DESCRICAO, UNIDADE, EMBALAGEM, CODNCMEX, QTUNITCX` ✅. O NCM é comparado pelos 8 primeiros dígitos, porque `CODNCMEX` pode trazer a exceção.

## Regras de segurança aplicadas

- Toda consulta passa pela trava `ExigirSomenteLeitura`: só começa com SELECT ou WITH.
- Textos sempre por bind. Listas de inteiros são geradas a partir de `Integer`. Os lotes têm no máximo 200 itens.
- O schema (owner) é validado como identificador Oracle antes de ser usado como prefixo.
- Uma falha de conexão ou de permissão vira "consulta indisponível" (falha técnica, bloqueia a liberação). Nunca vira "não encontrado".

## Permissões mínimas para o usuário Oracle

`CREATE SESSION` + `SELECT` em: PCFILIAL, PCFORNEC, PCPRODUT, PCCODFABRICA, PCEST, PCPRODFILIAL, PCNFENT, PCNFCAN, PCNFENTPREENT.

## O que a 1301 grava (para referência, a HUGINN NÃO grava)

- **Ao gerar uma pré-entrada:** PCNFENTPREENT (~230 colunas), PCMOVPREENT (~230), PCMOVCOMPLEPREENT (~170, incluindo benefício fiscal e IBS/CBS), PCLANCPREENT, PCNFBASEPREENT, PCENTVEICULO e PCLOGALTERACAODADOS. Antes de gravar, a rotina lê cerca de 80 parâmetros de filial. Conclusão: a pré-entrada já é a entrada **calculada**, e por isso a HUGINN não a reproduz.
- **Ao gerar:** `UPDATE PCNFENTXML SET NUMTRANSENT…` numa linha que já existia. O INSERT nessa tabela não acontece no "Carregar arquivo" (trace 3). A origem está ⏳.
- **Efeitos automáticos da rotina:** `INSERT PCFORNECFILIAL` (completa fornecedor x filial), `PCCONSUM.PROXNUMTRANSENT` e `DELETE PCLISTAPROD_TMP`.

## Fluxo oficial DF-e do WinThor (traces das rotinas 1095, 1321 e 1309)

Registrado como referência. O cliente **não usa a 1095**, por isso esse fluxo não entra na v0.1.

- **1095 (manifestação):** lista `PCMANIFDESTINATARIO` (CODIGO, CHAVENFE, CODFILIAL, CNPJCPF, NOME, DATAEMISSAO, VLTOTALNFE, SITCONFIRMACAODEST, FEZDOWNLOADXML), grava a manifestação e pede o download (`IDREMESSADOWNLOAD`). O XML é baixado e gravado em `PCNFENTXML` por um serviço da TOTVS, fora da tela.
- **1321 (Importação XML Automático):** roda em ciclo (intervalo 15, janela de 90 dias). Pega `PCNFENTXML` com `SITUACAO` 'A' (ou 'P' depois do intervalo), `DADOSXML` preenchido, junção com `PCMANIFDESTINATARIO` pela chave e sem `PCNFENTPREENT`/`PCNFENT` na filial. Gera a pré-entrada automaticamente.
- **1309 (Analisar pré-entrada):** monitora a fila de `PCNFENTXML` por situação ('A', 'F'…), sem nota nem pré-entrada.
- **Colunas confirmadas de `PCNFENTXML`:** CHAVENFE, DADOSXML, CNPJ, CODFORNEC, NUMNOTA, SERIE, DTEMISSAO, NUMTRANSENT, DTCADASTRO, SITUACAO, TENTATIVAS, NATOPERNFE, LOG_PROCESS e ORDEM.
- **Conclusão:** a fila da 1321 **depende** de `PCMANIFDESTINATARIO`, que vem do processo da 1095. Gravar nas duas tabelas pelo HUGINN seria imitar o serviço da TOTVS, e isso não é recomendado.

## Pendências para fechar por trace ou dicionário

1. Coluna de fator de conversão em `PCCODFABRICA` (opção "Utilizar fator de conversão da rotina 253").
2. Ordem da Pesquisa Automática quando 203 e 253 não acham, e regra do EAN Dinâmico (253).
3. Coluna de CEST do produto.
4. Travas de tributação de entrada (`PCTABTRIBENT` / `PCTRIBENTRADA` / `PCTRIBENTPROD` conforme `PCCONSUM.USATRIBENTPORUF`), tabela de preço e endereçamento.
5. ~~Quem insere em `PCNFENTXML`~~: o serviço de download da DF-e (fluxo da 1095), confirmado. Não se aplica sem a 1095.
