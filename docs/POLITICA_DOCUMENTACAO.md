# Política de documentação contínua — HUGINN IA

## Regra obrigatória

Nenhuma funcionalidade deve ser considerada concluída sem documentação proporcional à mudança. A documentação é mantida no mesmo repositório, revisada por PR e vinculada à versão do código.

## Para cada PR

O autor (humano ou agente) deve:
1. Identificar funcionalidades, APIs, tabelas, telas, dependências, requisitos de implantação e riscos afetados.
2. Atualizar o [Manual mestre](MANUAL_MESTRE.md) e guias especializados quando necessário; se não houver impacto documental, explicar por quê.
3. Documentar o comportamento **implementado**, distinguindo explicitamente de planejado e de demonstrado apenas por mocks.
4. Adicionar instruções reproduzíveis de testes, incluindo entradas, saídas esperadas e limites.
5. Registrar migração, compatibilidade, rollback e tratamento de credenciais quando aplicável.
6. Referenciar no PR os arquivos de documentação alterados e evidências de testes.

## Checklist para descrição de PR

- [ ] Resumo funcional e técnico
- [ ] Documentação alterada (links) ou justificativa de ausência
- [ ] Contratos de API, esquema e permissões atualizados, se afetados
- [ ] Testes executados e evidências (CI/Windows/Oracle real versus mocks)
- [ ] Segurança e dados sensíveis revisados
- [ ] Implantação, compatibilidade e rollback avaliados
- [ ] Pendências e limitações explicitadas

## Organização

- `README.md`: entrada rápida e estado do MVP.
- `docs/MANUAL_MESTRE.md`: visão funcional, arquitetura, API, regras, roadmap e mapa.
- `docs/CONEXAO_ORACLE.md`: configuração, limites e diagnósticos WinThor.
- `docs/ATUALIZACOES_WINDOWS.md`: supervisor, instalação, recuperação.
- `docs/DISTRIBUICAO_RELEASES.md`: chaves, assinaturas, aprovação, canais.
- `packaging/windows/README.md`: empacotamento e smoke tests.
- Novos módulos devem ter guias próprios, ligados ao manual mestre.

## Automação incremental

A CI deve, progressivamente, verificar links locais, estrutura Markdown, documentação de endpoints e checklist de PR. Não gerar documentação fictícia com IA: propostas automáticas precisam de revisão de precisão e de segurança. Não permitir que agentes modifiquem políticas de release ou habilitem produção silenciosamente.

## Histórico

- 2026-11-14: política inicial criada com o manual mestre, sem alterar código de aplicação nem configurar deploy.
