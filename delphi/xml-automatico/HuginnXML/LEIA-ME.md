# HUGINN XML Automático — v0.1.0 (+ envio para a 1321)

*Seu ERP registra. HUGINN antecipa.*

Rotina Delphi aberta pelo menu do WinThor que **confere a NF-e de entrada antes da importação na 1301**, usando as mesmas regras de pesquisa da 1301. Ela não grava nada no WinThor.

## Fluxo

1. **Abrir XML.** O arquivo é lido com segurança: DTD proibida, sem rede, até 5 MB. Os bytes originais ficam preservados e o SHA-256 é calculado.
2. **Analisar.** A conferência cobre:
   - filial, pelo CNPJ do destinatário;
   - fornecedor, pelo CNPJ;
   - produtos, pelo **mesmo modo de pesquisa da 1301**: barras UN venda, barras UN master, código de fábrica 203, código de fábrica 253, automática ou EAN dinâmico. As outras formas servem de evidência e para detectar conflito;
   - nota já lançada ou com pré-entrada (`PCNFENTPREENT` pela chave e `PCNFENT` por fornecedor, número e série);
   - travas que a 1301 aponta: sem PCEST/PCPRODFILIAL, excluído, proibido para venda, fora de linha, moeda estrangeira, produto de outra filial;
   - custo do XML na unidade do WinThor contra o **preço da última entrada** (`PCEST.PLIQULTENT` da filial);
   - NCM e CEST (orientativos).
3. **Revisar.** Grade com os status OK, Alerta, Pendência e Falha técnica. O detalhe de cada item mostra a evidência, o cálculo e a ação sugerida.
4. **Liberar XML original.** O arquivo é copiado byte a byte para a pasta de liberados e o SHA-256 é conferido depois de gravado. Na 1301, use **"Arquivo em pasta"** com esse arquivo. A 1301 faz a validação final e gera a pré-entrada.

### Envio para a pré-entrada automática (rotina 1321), opcional e DESLIGADO por padrão

Com **"Enviar para a fila da 1321"** ligado na Configuração, aparece o botão **Enviar p/ pré-entrada (1321)**. Depois da conferência, o HUGINN grava **somente duas linhas**, num único bloco PL/SQL (se qualquer checagem falhar, nada fica gravado):

- `PCNFENTXML`: o XML original, com situação `A`, matrícula (`CODFUNC`), número, série, emissão e CNPJ;
- `PCMANIFDESTINATARIO`: a identificação da nota, com `CODIGO` pela sequence oficial `DFSEQ_PCMANIFDESTINATARIO` e `PROGRAMA` = `HUGINN-XML`.

A **pré-entrada é gerada pela própria 1321**, no ciclo dela, com o motor fiscal do WinThor. O HUGINN não grava impostos, custos nem pré-entrada. O botão **Situação na 1321** mostra a situação, as tentativas, o `LOG_PROCESS` e a transação da pré-entrada quando ela sai.

Antes de gravar, o bloco confere se a chave já existe em `PCNFENTXML`, `PCMANIFDESTINATARIO`, `PCNFENTPREENT` ou `PCNFENT`. A análise também avisa quando a nota está fora da janela da 1321 (padrão 90 dias).

**Permissões a mais para esse modo:** `INSERT` em PCNFENTXML e PCMANIFDESTINATARIO e `SELECT` na sequence DFSEQ_PCMANIFDESTINATARIO. O trigger `TRG_PCMANIFDESTINATARIO` grava auditoria em `PCLOGFATURAMENTO`, então o usuário também precisa poder disparar esse INSERT.

**Status:** o mecanismo ainda está **pendente do teste manual** (script SQL de teste com uma nota nova). Só ligue esta opção depois que esse teste e o teste de equivalência com a 1301 passarem.

### O que bloqueia a liberação

| Situação | Liberação |
|---|---|
| Falha técnica (sem conexão ou permissão; consulta que não terminou) | **Bloqueada** |
| Nota já lançada ou com pré-entrada no WinThor | **Bloqueada** |
| Mesma chave já recebida com conteúdo diferente (outro SHA-256) | **Bloqueada** até revisar |
| Pendências (produto ou fornecedor novo, conflito de identificadores, travas da 1301) | Permitida com confirmação |
| Alertas (custo fora da tolerância, NCM/CEST, sem fator de conversão) | Permitida com confirmação |

## Licença HUGINN

O identificador do produto é **`HUGINN_XML_AUTOMATICO_WINTHOR`**. Cadastre-o na aba *Produtos* do Gerador de Licenças. A validação vem de `delphi/comum/uLicencaHUGINN.pas`, que traz só a chave pública.

- **Sem licença válida:** funciona o modo **demonstração**. O Oracle e o envio para a 1321 ficam bloqueados.
- **Com licença válida:** a barra superior mostra "Licenciado para <cliente> até <data>", com aviso a partir de 15 dias do vencimento.
- **Botões na barra superior:** **Copiar ID** e **Licença…**, que instala o `.dat` ao lado do `.exe`.

## Identidade visual

A paleta é a mesma do Gerador de Licenças: barra azul-marinho `#0B223D`, ciano `#22D3EE`, fundo claro `#F1F6FB`, faixa azul elétrico `#1E90FF` e a fonte Segoe UI. Para a logomarca aparecer, coloque **`huginn_logo.png`** (fundo transparente) ao lado do `.exe`. Sem esse arquivo, a barra mostra só o nome HUGINN.

## Log de operações

Fica em `<Pasta do HUGINN>\logs\AAAA-MM-DD.jsonl`, com uma linha por ação: abrir, analisar, reanalisar, escolher filial, liberar, cancelar e erros. Cada linha traz data e hora, usuário e máquina do Windows, versão, regra, chave, SHA-256, filial, resultado e detalhe. **Não registra o XML, senhas nem valores fiscais.** A aba **Histórico** mostra os últimos 500 registros.

As versões recebidas ficam em `<Pasta do HUGINN>\Recebidos\<chave>\<sha256>.xml`, como evidência.

## Requisitos

- Delphi 12 (RAD Studio) com **UniDAC** e o provider Oracle, igual ao HuginnFVDiag.
- MSXML 6, que já vem no Windows.
- Usuário Oracle **somente com SELECT** nas tabelas da [matriz de consultas](docs/MATRIZ_CONSULTAS.md).

## Como abrir e compilar

1. No Delphi: **File > Open Project** → `HuginnXML.dpr`. O IDE cria o `.dproj`.
2. **Win32** (ou a mesma plataforma das suas rotinas) → **Build**.
3. Testes: abra `tests\TestesHuginnXML.dpr` (precisa do DUnitX, que vem com o Delphi) → Build → execute. Os testes usam o provedor de demonstração e as notas fictícias de `fixtures\`. **Não acessam banco.**
4. XMLs reais para teste local vão em `fixtures\real\`. Essa pasta fica **fora do Git** (o repositório é público). O teste `LeXmlsReaisLocais` lê todos os arquivos dela.

## Primeira execução

- Ao abrir, o programa usa o modo **DEMONSTRAÇÃO** (dados fictícios). Teste com `fixtures\nfe_valida_mista.xml`.
- Em **Configuração**: marque "Usar o Oracle do WinThor" e informe servidor, porta, service name, usuário e schema. Clique em **Testar conexão**. A senha só é salva se você marcar a opção, e fica protegida pelo Windows (DPAPI).
- Em **Pesquisa (igual à 1301)**, escolha o mesmo modo que o operador usa na 1301.

## Instalação no menu do WinThor

Siga o mesmo padrão das suas rotinas Delphi:
1. Copie `HuginnXML.exe` para a pasta das rotinas HUGINN.
2. Rotina **529**: crie a rotina apontando para o executável.
3. Rotina **530**: dê permissão aos usuários.
4. O `HuginnXML.ini` fica ao lado do `.exe`. Deixe a pasta fora de *Arquivos de Programas*.

## O que NÃO foi verificado (status honesto)

- [x] **Escrito**
- [ ] **Compilado**: o ambiente da IA não tem Delphi nem UniDAC
- [ ] **Testado** (DUnitX)
- [ ] **Homologado** com o Oracle do cliente

Pendências conhecidas, todas marcadas no código:
- Ordem exata da **Pesquisa Automática** quando o código de fábrica não acha (cai no EAN?) e o comportamento do **EAN Dinâmico (253)**: confirmar por trace.
- Coluna do **fator de conversão da 253** (`PCCODFABRICA`). Até confirmar, o fator vem só da unidade igual ou do código de barras master.
- Coluna de **CEST** do produto no WinThor. Até confirmar, o CEST só é comparado no modo demonstração.
- Travas da 1301 ainda não cobertas: **tributação de entrada, tabela de preço e endereçamento**.
- Componentes do custo: a v0.1 compara (vProd − vDesc) ÷ (qCom × fator) contra `PLIQULTENT`. É preciso confirmar com um caso real se `PLIQULTENT` está nessa mesma base.
- Entregar o XML direto na `PCNFENTXML`, para a 1301 listar em "Arquivo no banco de dados". Falta descobrir quem faz o INSERT nessa tabela (o "Carregar arquivo" da pasta não faz).

## Próxima versão (0.2)

Homologar as consultas na base do cliente, resolver as pendências acima, exportar a conferência em PDF/Excel e, se aprovado, entregar o XML pelo banco.
