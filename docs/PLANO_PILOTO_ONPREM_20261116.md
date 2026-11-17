# HUGINN IA — Plano de implementação do piloto on-premises (16–22/11/2026)

## Objetivo
Entregar no mesmo aplicativo Windows dois módulos funcionais: Auditor XML/NF-e (#31) e Revisor Inteligente de Cadastros (#32). Conexão Oracle WinThor on-premises compartilhada. TOTVS Cloud, Compras e BI fora do escopo desta versão.

## Ordem de implementação para Codex
1. Reproduzir e corrigir falha de descoberta de schema da PCPRODUT (#25): diferenciar owner, synonyms, ALL_TAB_COLUMNS, grants e ausência de colunas. Somente SELECT com bind e allowlist. Testes de regressão; não presumir falta de permissões.
2. Integrar XML/NF-e à aplicação existente (#31): upload de XML, validação, identificação de fornecedor/produto, confronto de custos/cadastro, divergências, detalhes e relatório. Integração SEFAZ/NSU não é pré-requisito do piloto.
3. Implementar Revisor de Cadastros (#32): PCPRODUT, PCCLIENT e fornecedores conforme schema confirmado; validação objetiva, heurísticas identificadas, severidade, valor atual, sugestão, justificativa e exportação. Sem UPDATE.
4. Consolidar Central de Conexões e UX (#29), preservar perfis e segurança.
5. Instalador Windows com upgrade seguro (#27), testes de regressão, artefato de homologação e manual.

## Contrato de segurança
- Não alterar Oracle: proibir INSERT/UPDATE/DELETE/MERGE/DDL, grants e execução arbitrária de SQL.
- Ambiente produtivo do cliente somente leitura, com autorização explícita.
- Não registrar credenciais, XMLs reais, CNPJ/CPF ou dados sensíveis em PR/logs.
- Não ativar conexão em produção ou publicar release silenciosamente.
- Nenhum merge na main sem CI e revisão.

## Critérios de aceite
- Oracle local: conexão, descoberta de esquema e consulta paginada a PCPRODUT comprovadas em homologação real.
- XML de teste: ingestão, comparação e relatório reproduzíveis.
- Revisor: amostra de produtos/clientes/fornecedores com erros objetivos e sugestões, inclusive falsos positivos documentados.
- Frontend: navegação entre módulos, conexão única e estados de erro/carregamento.
- CI Windows + backend + frontend; instalador gerado e testado; evidências no PR e MANUAL_MESTRE atualizado.
- Piloto até 22/11/2026 somente se os critérios forem atendidos.

## Estratégia de PRs
Codex deve criar PRs de implementação separados para #25, #31 e #32, com testes; integrar após revisão. Este documento de planejamento não constitui implementação nem inicia automaticamente o Codex.
