# Automação opt-in de issues para Codex

A workflow `.github/workflows/codex-approved-issues.yml` usa `openai/codex-action@v1` e a API OpenAI para gerar **patches de proposta**, nunca para aplicar em main. Só aceita issues 31, 32, 29 e 27 e disparos do proprietário `wondersonrj`.

## Ativação necessária (pelo proprietário)
1. Revisar e integrar o PR da automação na main após os checks obrigatórios.
2. Criar uma chave de API OpenAI com orçamento/limites adequados na plataforma OpenAI. A assinatura ChatGPT não equivale automaticamente a crédito API.
3. Em GitHub > Settings > Secrets and variables > Actions > New repository secret, criar `OPENAI_API_KEY`. Nunca colocar valor em issue, chat, código ou logs.
4. GitHub > Actions > **Codex opt-in issue implementation** > Run workflow > escolher issue 31 ou 32. Alternativamente aplicar o label `codex-approved` à issue elegível (somente pelo dono).
5. Acompanhar execução e baixar artifact `codex-proposal-<run>`. Revisar o patch, rodar CI e abrir PR por fluxo humano separado. **Não há criação automática de PR nesta versão**, nem aplicação em cliente.

## Limites
- Uma execução de cada vez; timeout 45 min. O label só dispara no momento em que é aplicado, não retroativamente.
- A issue #25 já foi enviada manualmente e foi excluída para evitar duplicação.
- Sem tokens de escrita no job Codex; checkout sem credenciais persistidas; ambiente Linux com sudo removido; sem credenciais Oracle.
- O runner pode ter custo API. A automação só entra em operação após configuração do segredo e merge.
- O Codex lê o repositório; não recebe texto arbitrário de issues como instruções.
- Para transformar patches em PRs automáticos, implementar segundo job isolado sem chave API, com validação de caminhos, limite de diffs, branch dedicada, CI e revisão obrigatória.
