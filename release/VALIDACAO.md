# Evidência da tarefa #1 e diagnóstico de metadados

Código funcional: ab518de4e57cbb3a164081c931740a7b1eeb040f.

A execução [Windows portable build #9](https://github.com/wondersonrj/huginn-ia/actions/runs/43436410457)
terminou com **Success**. O job [portable](https://github.com/wondersonrj/huginn-ia/actions/runs/43436410457/job/131922559830)
mostra os passos efetivamente concluídos, registrados em WINDOWS-CI-EVIDENCE.json.
A publicação de release foi intencionalmente pulada: push em main só faz CI.

Passos Windows comprovados: instalação de dependências, npm ci/build, pytest,
build do ZIP, smoke usando runtime incluído, atualização com processos reais,
rollback por inicialização falha e testes Playwright/Chromium da interface.
O teste específico de arquivo em uso e os locks nativos são executados pela
suíte no Windows; em Linux esse caso real de compartilhamento é marcado skipped.

O teste de integração ativa 0.2.1 a partir de 0.2.0, confirma /api/version,
tenta 0.2.2 com servidor quebrado e confirma retorno a 0.2.1 e preservação de
preferências. Usa assinatura efêmera e downloads em memória. Não testa uma
release publicada B nem a confirmação humana via MessageBox em um cliente.

O diagnóstico valida uma consulta fixa parametrizada exclusivamente em views
de metadados, sem SQL livre, DML, DDL ou leitura de tabelas comerciais. Os testes
backend impedem conexões Oracle reais por fixture global; o navegador usa mocks.
Não houve validação de conectividade, schema real ou permissões em Oracle 19c.

Para ativar distribuição: revisar chave pública, configurar secret privado no
environment protegido windows-release-approval, aprovar uma tag semântica e
executar o workflow manual de release. Não inserir segredos no chat ou código.
O bootstrap manual de teste permanece desativado até essa preparação externa.
