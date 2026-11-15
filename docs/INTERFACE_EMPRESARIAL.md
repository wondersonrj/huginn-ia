# Interface empresarial — 0.4.0 / issue #29

## Guia do operador

Abra pelo atalho Windows. O acesso por SID/cookie HttpOnly é automático; não
copie token do disco. O campo de token só aparece no modo legado de desenvolvimento
ou portátil. Um erro de autenticação Windows fecha o acesso: reabra pelo atalho.

A barra lateral leva a cada módulo em um clique; em telas pequenas, abra o menu e
selecione o módulo (dois cliques). A barra superior mostra o nome do destino e o
ambiente TESTE/PRODUÇÃO, sem host, usuário ou senha. “Selecionada” não significa
sessão permanente: cada consulta abre uma sessão de leitura e a encerra.

| Módulo | Uso |
| --- | --- |
| Visão geral | Status verdadeiro do destino, XML da sessão e atalhos de trabalho. Sem indicadores financeiros inventados. |
| Auditoria NF-e | Selecionar XML local de até 5 MB, conferir emitente, itens e valores; limpar a nota quando terminar. Não consulta SEFAZ e não compara com o ERP. |
| Produtos | Verificar destino, pesquisar por código/descrição, navegar pelas páginas. |
| Fornecedores | Mesmos controles, consulta independente a PCFORNEC. |
| Configurações | Única Central de Conexões: cadastrar, editar, testar, selecionar, retirar senha e excluir perfis. |
| Funcionalidades e Validação | Inventário versionado, passo a passo, limites, status, testes, última revisão e lacunas; filtros e relatórios Markdown/JSON. |
| Diagnóstico e Suporte | Diagnóstico de schema, owners/synonyms e tipos; atualização assinada e manutenção local. |

Na Central, salve o perfil, teste e selecione explicitamente o destino. PRODUÇÃO
exige confirmação própria ao testar/selecionar/diagnosticar; isso não habilita
escrita ou publicação. A senha salva nunca volta ao formulário. Edição sem nova
senha conserva o segredo; remoção de senha bloqueia seleção. O reinício conserva
perfis e token DPAPI, mas exige nova seleção do destino. A migração por ambiente
continua opcional e explícita; ambiente legado não classificado não recebe selo TESTE.

Os detalhes técnicos e metadados ampliados ficam recolhidos por perfil. O
**diagnóstico pontual** usa os mesmos campos da Central, não um segundo formulário.
Ele não salva credenciais nem troca o destino; a senha digitada é limpa após o
pedido. A ação de metadados de um perfil salvo resolve a senha no backend, exige
a confirmação do ambiente e devolve somente o relatório permitido. O relatório
pode conter nomes de owners/colunas: revise antes de compartilhar.

A consulta informa carregamento, resultado vazio e erro; depois de falhar, corrija
os filtros/destino e repita. Mudar módulo cancela pedidos pendentes; mudar perfil
ou revisão invalida resultados e a verificação anterior. O XML já carregado fica
só na memória enquanto navega e desaparece ao recarregar/encerrar acesso.

“Atualizar agora”, “Encerrar HUGINN” e “Recriar acesso local” continuam com
confirmação. Apenas o aplicativo local é encerrado; não há reinício do Windows.
Atualizações permanecem desabilitadas no pacote de homologação.

## Arquitetura e preservação de segurança

`main.tsx` concentra shell, navegação hash allowlist, estado volátil de sessão,
nota e destino. `NfePage`, `WinthorCatalog`, `ConnectionManager`, `UpdatePanel` e
`FeatureCatalog` implementam os módulos. Os links funcionam por teclado, o título
recebe foco na navegação, há skip link, foco visível, menu responsivo, regiões
aria-live e preferência por movimento reduzido. Tipografia local Segoe UI, sem
fontes externas. A identidade utiliza o Bird já existente no repositório; não foi
recebido outro arquivo de corvo oficial. Mantidos azul-marinho e ciano.

Não houve mudança no cofre DPAPI, SID/HttpOnly, autenticação, limites SQL,
allowlist de tabelas/colunas, binds, seleção com revisão ou auditoria. O único
adaptador backend novo é `POST /api/connections/diagnostic`, autenticado e limitado
pelo mesmo handler. Ele reutiliza `inspect_schema` e a resolução de segredo já
existentes, com transação somente leitura, fechamento e erros sanitizados. As
rotas pontuais `/api/oracle/testar` e `/api/oracle/diagnostico` foram preservadas.
Nenhuma migração de dados/conexões é necessária pelo redesign.

## Catálogo e rastreabilidade

Fonte: `frontend/src/data/features.json`; navegação: `navigation.json`. Há 17
recursos catalogados, não 17 testes nem 17 integrações implementadas. Cada recurso
contém finalidade, entrada, saída, passos, limites, status e validação
(escopo, última revisão, evidências `file`/`symbol`, lacuna). Os relatórios legível
e técnico são gerados desse catálogo estático; não incluem contexto da sessão,
perfis, token, XML ou credenciais. A data é revisão versionada, não monitoramento
ao vivo. SEFAZ e comparação ERP estão explicitamente planejadas.

`backend/tests/test_feature_catalog.py` verifica unicidade, módulos, estados,
datas, existência das rotas e símbolos de testes e execução efetiva dos cenários
browser citados. Ao acrescentar/retirar função, atualize catálogo e evidências no
mesmo PR. CI detecta referências inexistentes; revisão humana ainda deve conferir
se a descrição corresponde ao comportamento, não apenas ao nome do teste.

## Validação reproduzível e limites

- `python -m pytest -q`: backend, contratos de segurança, catálogo, DPAPI quando
  Windows, instalador, update, rollback e cenários negativos.
- `npm ci --prefix frontend` e `npm run build --prefix frontend`: TypeScript/bundle.
- `npm audit --prefix frontend --omit=dev --audit-level=high`: dependências produção.
- `python packaging/windows/browser_smoke.py release/HUGINN-IA-Windows-x64.zip`:
  oito cenários completos com APIs demo, fixtures Oracle e perfis DPAPI no Windows.
- Workflow **Windows installer homologation**: instala EXE, valida acesso sem token,
  atualização, EXEs históricos 0.2.0/0.3.0, portátil, falha/rollback, recuperação,
  reinstalação, atalhos, uninstall preservando/removendo dados e serviço estrangeiro.
- Workflow **Windows portable build**: runtime Windows, update assinado entre
  commits, rollback e browser; inclui snapshots sintéticos no artifact.

Capturas [antes/depois](screenshots/issue-29/README.md) usam dados sintéticos e
não comprovam Oracle real. Para reproduzir as imagens em uma instância **demo
isolada**, com token sintético `TOKEN` de `browser_smoke.py`, execute:

```sh
python packaging/windows/ui_snapshots.py --url http://127.0.0.1:8000 \
  --xml exemplos/nota-demo.xml --output ui-evidence
```

Não execute esse capturador em instância de cliente: intercepta somente a lista
por uma fixture vazia e foi desenhado para demo. Resultados locais: **325 aprovados,
2 ignorados** no Linux, build e oito cenários Chromium aprovados. As evidências do
HEAD Windows, links dos runs e instalador estão no PR da issue #29. Windows real
com driver Oracle sintético comprova a aplicação instalada/DPAPI/contratos;
**homologação Oracle real permanece pendente**, sem solicitação de credenciais no
GitHub. Nenhum teste invasivo, escrita, merge, release ou ativação de produção.
