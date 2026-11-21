# HUGINN Força de Vendas — Diagnóstico v0.1

*Inteligência antes da decisão.*

## O que faz

Conecta no Oracle do WinThor **somente para leitura** e gera um ZIP com a estrutura que o Força de Vendas HUGINN vai usar:

- **Integradora:** PCPEDCFV, PCPEDIFV, PCCLIENTFV e qualquer outra tabela `PC*FV*` que existir no schema.
- **Tabelas que o app vai ler:** confirmadas (PCPEDC, PCPEDI, PCCLIENT, PCPRODUT, PCPRODFILIAL, PCEMBALAGEM, PCTABTRIB, PCEMPR, PCUSUARI, PCNFSAID) e **candidatas** (PCTABPR, PCEST, PCPREST, PCPRACA, PCREGIAO, PCFILIAL, PCPLPAG, PCCOB, PCMETA, PCMETARCA, PCSUPERV, PCATIVI, PCCIDADE, PCDEPTO, PCSECAO, PCMARCA, PCFORNEC). Para as candidatas, o diagnóstico só verifica se existem: nada é dado como certo.
- **Como o FV atual usa a integradora:** packages e procedures que dependem dela, as linhas de PL/SQL que a citam, jobs agendados, sequences, volume e período dos dados e os valores mais comuns das colunas de status e de erro (motivos de recusa).
- **Amostra opcional** dos últimos 50 pedidos da integradora. A amostra de PCCLIENTFV vem desligada porque contém dados pessoais (LGPD).

## Arquivos no ZIP

| Arquivo | Conteúdo |
|---|---|
| manifesto.txt | resumo, servidor, schema, erros, lista de arquivos |
| 00_* | sessão, versão do Oracle, NLS |
| 01_tabelas_alvo.csv | cada tabela: existe S/N, origem, nº de linhas (estatística) |
| 02–07 | colunas e comentários, constraints, índices, triggers, sequences |
| 08–10 | dependências, PL/SQL que cita a integradora, jobs |
| 11–12 | volumes e datas da integradora, valores de status/erro |
| 20_amostra_* | amostras (se marcadas) |

## Requisitos

- Delphi 12 (RAD Studio) com **UniDAC** e o provider Oracle instalados (units `Uni` e `OracleUniProvider` no Library Path).
- Um usuário Oracle com leitura nas tabelas do WinThor. Se puder, use um usuário só de leitura.
- O Oracle Client não é necessário: o programa usa o modo direto do UniDAC.

## Como abrir e rodar

1. Descompacte numa pasta sua, por exemplo `C:\HUGINN\HuginnFVDiag` (fora de *Arquivos de Programas*: o `.ini` fica ao lado do `.exe`).
2. No Delphi: **File > Open Project** → `HuginnFVDiag.dpr`. O IDE cria o `.dproj`.
3. Plataforma **Win32** ou **Win64** → **Build**.
4. Rode e preencha: servidor (IP), porta (1521), service name ou SID, usuário, senha e o schema do WinThor. Se o schema for o próprio usuário, deixe-o em branco.
5. Clique em **Testar conexão** e depois em **Gerar diagnóstico (ZIP)**.
6. Envie o ZIP para a HUGINN.

TOTVS Cloud: use o IP liberado e o service name fornecidos pela TOTVS.
Oracle Client/TNS em vez do modo direto: feche o programa, abra o `HuginnFVDiag.ini` e defina `ModoDireto=0` na seção `[Conexao]`. Depois coloque o alias TNS no campo Service name.

## Segurança

- Todas as instruções passam por uma trava que só aceita `SELECT`/`WITH`. O programa não executa `INSERT`, `UPDATE`, `DELETE` nem DDL.
- A senha só é salva se você marcar "Lembrar senha". Nesse caso ela fica protegida pela DPAPI do Windows e só abre no mesmo usuário e computador. Ela nunca vai para o log nem para o ZIP.
- Consultas pesadas: a varredura de `ALL_SOURCE` e as contagens leem tabelas inteiras. Para não pesar, rode fora do horário de pico (de preferência em homologação ou numa cópia).

## O que NÃO foi verificado

- **Nada foi compilado nem executado:** o ambiente da HUGINN IA não tem Delphi nem UniDAC.
- Ainda falta confirmar o nome da opção `SpecificOptions['Direct']` e o formato do servidor (`host:porta/service` e `host:porta:SID`) na sua versão do UniDAC. Se a conexão falhar, me mande a mensagem exata.
- Se o usuário não tiver privilégio em `V$VERSION`, `NLS_DATABASE_PARAMETERS` ou nos jobs, esses arquivos saem como erro no manifesto. Isso é esperado e o restante continua.

## Próxima versão

v0.2 — servidor de sincronização (serviço Windows, HTTPS): ativação por token, carga de produtos, preço, estoque e clientes e recebimento de pedido gravando na integradora. O desenho será feito a partir deste diagnóstico.
