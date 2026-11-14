# Operação e manutenção

## Desenvolvimento e diagnóstico

Abra uma issue com objetivo e critérios observáveis, sem dados de clientes.
Inicie o Codex explicitamente com acesso ao repo e limites: branch, PR, testes e
documentação; sem merge/publicação. A mera existência ou atribuição da issue não
é despacho. Revise o PR e links de CI no SHA atual.

Falha de quality gates gera handoff elegível, não um agente. Confira assinatura,
SHA e run; use o pedido pronto após revisão. Registre a tarefa real e depois o
PR. Um único início humano é permitido por contrato; falha ou tentativa adicional
exigem nova decisão. Mantenha o registro fechado para deduplicação e não apague
marcadores/contrato para forçar retry. PRs de correção com autodev/fix/key não
são delegados de novo. Para novo SHA, avalie se é continuação do incidente antes
de iniciar outra tarefa.

## Estados e incidentes

| Observação | Ação |
| --- | --- |
| awaiting_human_start | revisar origem e iniciar tarefa explicitamente; não afirmar que está rodando |
| already_queued | usar a issue existente; nenhum novo encaminhamento |
| budget_exhausted | revisar assinatura/causa no mesmo head; não reenfileirar automaticamente |
| ineligible | verificar evento, repo, SHA, workflow e namespace; não ampliar escopo para contornar |
| action_required | mantenedor revisa e aprova o workflow quando apropriado; agente interrompe essa etapa |
| API recusada | consultar permissões e metadados; não usar PAT/bypass ou reduzir regras |
| portable esperado com branch BEHIND | investigar policy/SHA/App e seguir refresh com lease, não fabricar status |
| falha de correção | intervenção humana; sem loop de agentes ou merge automático |

## Entrega, recuperação e evidência

Backend, frontend, audit e portable reais devem passar no head do PR. A política
GitHub observada exige portable; revisão e outros critérios não são eliminados
por um relatório do agente. Os IDs finais ficam na descrição do PR. Toda mudança
de fluxo atualiza AUTODEV, MANUAL_MESTRE e histórico/inventário vinculados à #10.

Release, chaves, atualização de clientes e rollback seguem os manuais próprios.
Um PR verde não autoriza deployment ou escrita Oracle. O MVP só usa DUAL e views
de metadados em conta autorizada de leitura; consultas comerciais reais da #9
não foram implementadas aqui. Não reproduzir incidentes com XML/credenciais reais.

Custos da conta e plano Codex não foram consultados. A fila consome Actions/REST;
a Action oficial do Codex, se adotada futuramente, exige orçamento e credencial
protegida autorizados. Não expor valores de secrets, transcripts ou logs brutos
em evidências. Rotação de confiança/distribuição é procedimento humano separado.
