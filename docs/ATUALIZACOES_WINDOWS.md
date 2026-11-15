# Atualização Windows — tarefa #1

## Estado e limites

Implementado um supervisor independente, validação de manifesto Ed25519/SHA256,
instalação em diretórios por versão, confirmação HTTP da versão e rollback.
O ZIP de desenvolvimento é um **bootstrap de teste com atualização desativada**.
Não há chave de distribuição real no repositório. Não houve validação de release
remota A→B ou aprovação nativa em computador Windows nesta sessão Linux.
Resultados Windows só devem ser afirmados com link de execução CI concluída;
o workflow salvo ou testes Linux não são essa evidência.

Nenhum deploy para clientes é feito por push em `main`. O ZIP de desenvolvimento
não é uma release aprovada nem é descoberto pelo atualizador. O mecanismo só
consulta releases semânticas aprovadas publicadas em GitHub Releases.

## Instalação inicial única

Extraia o bootstrap Windows x64 em uma pasta local gravável. Abra
`INICIAR_HUGINN.bat`; o supervisor inicia o aplicativo em `127.0.0.1:8000` e
prefere Chrome, depois Edge, com fallback para o protocolo Microsoft Edge.
Nunca usa Internet Explorer. Sem navegador compatível, mostra o endereço.

Estrutura:

- `runtime/`, `launcher.py`, `updater.py`, `bootstrap.json`: bootstrap confiável,
  não substituído automaticamente por releases.
- `versions/X.Y.Z/`: código e frontend por versão, sem dados/configurações locais.
- `state/`: apontador `current.json`, backup, journal, locks e status. Preferências
  não sensíveis podem ficar aqui; nunca guarde credenciais Oracle.

Os antigos ZIPs sem supervisor precisam desta instalação inicial; não há migração
silenciosa. Depois de um bootstrap aprovado e habilitado, novas versões compatíveis
não exigem extração manual. Mudanças de runtime/dependências ou do próprio bootstrap
exigem um novo bootstrap manual: o `runtime_id` fixa o hash do lock de dependências.

## Verificação, aprovação e recuperação

No canal `teste`, um bootstrap habilitado verifica releases ao iniciar. Em
`estavel`, use **Verificar atualização**. A interface mostra versão atual,
disponível, notas, status e necessidade de reinicialização. **Atualizar agora**
pede confirmação no navegador e abre confirmação nativa Windows, também no
canal estável. Não há instalação silenciosa nem aprovação por tempo decorrido.
Credenciais Oracle e documentos em memória são descartados na reinicialização.

O aplicativo só escreve mensagens fixas `check`/`apply` numa fila local. Não
executa processos, comandos, caminhos ou URLs recebidos via HTTP. A API de
solicitação exige loopback, Host e Origin exatos, JSON vazio e bootstrap ativo;
o supervisor valida um nonce por execução e solicita aprovação nativa. Não
exponha o servidor à rede nem coloque um proxy público na frente dele.

O supervisor valida assinatura Ed25519 com chave pública embarcada, HTTPS,
repositório/origem, tag `vX.Y.Z`, canal, versão crescente, identidade do runtime
e SHA256 do ZIP. Redirecionamentos são limitados a hosts HTTPS GitHub conhecidos.
Extração rejeita traversal, symlinks, caminhos Windows reservados/ADS, duplicados
e arquivos ZIP fora dos limites. Não há scripts de pós-instalação; só o entrypoint
fixo `server.py` da aplicação assinada é executado.

A nova versão é preparada em diretório separado. Um lock de SO impede atualizações
concorrentes. A versão antiga permanece como backup. Após fechar graciosamente
o processo filho, um `os.replace` troca o apontador da versão ativa; o supervisor
mantém o socket de escuta, evitando disputa de porta na reinicialização. A nova
versão deve responder `/api/version` com a versão esperada. Falha restaura o
apontador e reinicia a anterior. Journal interrompido é recuperado no próximo
início, antes de iniciar qualquer aplicação. Erros de arquivo em uso não
sobrescrevem código da versão em execução.

Se aparecer “recuperação pendente”, encerre todas as instâncias e abra novamente
o inicializador. Não exclua `versions/` ou `state/journal.json`: preservam a
recuperação. Se o backup estiver ausente ou disco/permissões impedirem recuperação,
restaure o bootstrap de origem verificada numa pasta nova e preserve a pasta antiga
para diagnóstico. Não copie arquivos de origem desconhecida nem execute scripts
enviados por terceiros. Versões antigas/falhas são retidas; limpeza é manual.

## Publicação aprovada

O procedimento atual completo, com chaves separadas por canal, custódia local,
secrets, revisores e ativação independente da publicação, está em
[Distribuição por Releases](DISTRIBUICAO_RELEASES.md). O padrão continua desativado.
Os environments atuais são `windows-release-teste` e `windows-release-estavel`.
O arquivo de confiança é `packaging/windows/release-public-keys.json`.

## Evidência de testes

`python -m pytest -q` inclui assinatura adulterada, release inválida, origem não
confiável, downgrade, canal/runtime incompatível, hash divergente, falta de rede,
recusa de aprovação, lock concorrente, arquivo em uso, recuperação de journal,
rollback e preservação de preferências. Um fixture global impede conexão Oracle
real em toda a suíte backend; mocks específicos validam as consultas de metadados.

`packaging/windows/update_smoke.py ZIP` executa o Python incluído no Windows,
inicia A, instala B sintética assinada com chave efêmera, confirma a versão HTTP,
inicia C propositalmente quebrada e confirma rollback para B. Não publica nem
baixa uma release real e não testa a caixa nativa de aprovação humana.

`browser_smoke.py ZIP` valida o frontend de produção, diagnóstico simulado,
proprietários separados, campos obrigatórios, limpeza da senha, XML e painel de
versão. `smoke.py ZIP` valida runtime/layout, inicialização, API, rejeição de
entrada inválida (sem conexão Oracle), XML e instância concorrente.

O parâmetro `--python /caminho/venv/bin/python` permite executar esses testes em
Linux usando código extraído do ZIP. Isso **não executa os binários Windows**.
O workflow usa `windows-latest` e não passa esse parâmetro.

## Preparação da próxima geração — #25 (0.3.0)

Auditoria: o bootstrap 0.2.0 distribuído e o novo instalador de homologação estão
com `updates_enabled=false`. Push/PR/main não habilitam distribuição. Não foi
publicada release ou usada chave privada de distribuição nesta tarefa.

Novo bootstrap exige `source_commit` SHA Git de 40 dígitos no manifesto assinado;
confere sua igualdade no version.json do payload antes de encerrar a versão atual.
A prova de identidade desktop usa o commit **da versão ativa**, não o BUILD-INFO
do instalador inicial. Corrige a identificação incorreta após update de outro
commit. Versão crescente, canal, runtime, Ed25519, SHA256, URL e rollback continuam
obrigatórios. Não existe downgrade nem aceitação de manifesto sem assinatura.

Bloqueio de ativação: requer release TESTE revisada, chave real em custódia/secret
do environment autorizado, assinatura válida com a chave pública embarcada e
aprovação Windows de distribuição/ativação, conforme DISTRIBUICAO_RELEASES.md.
Não criamos chave fictícia de distribuição e não habilitamos publicação. Chaves
efêmeras usadas somente em fixtures de CI não integram o artifact nem habilitam
confiança de cliente. Verificação pode ser automática; aplicação do update mantém
confirmação explícita/nativa, sem aceitar tempo decorrido como aprovação.

O cliente 0.2.0 já instalado **não passa a se atualizar por este PR**: seu supervisor
é imutável e está desativado. Para migrar o próprio bootstrap será necessário um
instalador de atualização aprovado (artifact 0.3.0 nesta tarefa, unsigned e apenas
homologação), na mesma pasta/usuário, com o HUGINN fechado pela interface. Ele
preserva o cofre DPAPI, conexões e senha; não exige reboot. Após bootstrap confiável
habilitado e releases assinadas aprovadas, updates compatíveis do código/UI chegam
pelo supervisor sem reinstalação; runtime/bootstrap incompatível continua exigindo
manutenção explícita. Não prometemos atualização silenciosa do cliente existente.

CI exercita no Windows processo desktop com DPAPI: versões de commits distintos,
falha de rede antes de parar a aplicação, update assinado, versão quebrada/rollback,
preferências e todos os bytes do perfil/token preservados. Instalador separado
exercita reinstalação/upgrade, app ativo bloqueando manutenção e serviço alheio
preservado. Estado e credenciais não integram o ZIP nem a extração do update.
