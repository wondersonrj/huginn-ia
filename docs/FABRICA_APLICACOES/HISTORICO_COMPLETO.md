# Histórico auditável da fábrica

Este registro consolida o que foi verificado na tarefa #14. Atende à manutenção
contínua pedida na [#10](https://github.com/wondersonrj/huginn-ia/issues/10), sem
considerar aquela issue integralmente concluída. [Inventário](MATRIZ_ISSUES_PRS.md)
contém datas UTC, branches, SHAs e merges consultados. Histórico anterior sem
registro de autorização humana não é reconstruído por suposição.

| Demanda | Decisão / ação | Resultado / evidência |
| --- | --- | --- |
| Pacote Windows e atualização #1 | runtime fixado, assinatura, confirmação e rollback | `release/VALIDACAO.md`, `docs/ATUALIZACOES_WINDOWS.md`; produção não é consequência de push |
| Diagnósticos e pública #2/#3 | preparar testes sob aprovação | PRs integrados; `docs/PREPARAR_TESTES_PELO_GITHUB.md` |
| Qualidade #5 | Python, frontend, audit isolados | PR integrado; workflow autodev-quality.yml |
| Triagem #7 | metadata-only workflow_run cria issue | integrado em 14/11/2026; ensaio #15 → run 43627014788 → issue #16 |
| Bloqueio #8 | política strict exige branch atualizada apesar de portable antigo aprovado | PR #11 integrado; diagnóstico em `docs/AUTODEV.md` |
| Aprovação #12 | action_required significa aprovação pendente comprovada na UI | PR #13 integrado; `docs/incidentes/ISSUE_12_EVIDENCIAS.json`; não inferir política inacessível |
| Integração #14 | escolher fila manual em vez de assumir API/configuração autônoma | código handoff.py, contrato v1 e ensaio com deduplicação na issue #16 |
| Documentação #10 | índice, inventário e guias mantidos em PR | esta coleta mantém lacunas explícitas; #10 segue aberta |

## Decisões desta execução

1. Fontes oficiais do Codex consultadas; review, tarefa e Action são mecanismos
   diferentes. Nenhuma atribuição a copilot foi feita e nenhuma chave nova criada.
2. PR #15 criado como draft com falha controlada sem I/O. O triage efetivo da main
   criou #16. Metadados foram usados para migrar #16 com o CLI novo, sem ler logs
   ou executar código do PR com escrita. Repetição retornou already_queued.
3. Branch de correção deriva do head com falha e remove o teste proposital. A
   solução é proposta em PR, não implantada. Contratos e validação local/remota
   são evidências distintas da execução de um agente novo.
4. Não houve merge, release, nova tag, escrita Oracle ou alteração de proteção.
   O callback novo da main só poderá ser validado após integração humana.

IDs, SHAs e passos de reprodução estão em [AutoDev](../AUTODEV.md#ensaio-observável-14).
Os resultados finais de CI do PR de correção são registrados na descrição do
próprio PR, evitando registrar um SHA anterior como se fosse o head final.
