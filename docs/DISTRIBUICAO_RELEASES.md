# Distribuição assinada e ativação sob aprovação

## Política

GitHub Releases é a origem das atualizações. `teste` usa prereleases; produção
é o canal `estavel` e usa releases não-prerelease. Cada canal tem sua própria
chave Ed25519 e environment GitHub. O manifesto assinado vincula versão, canal,
URL oficial, SHA256, notas e identidade do runtime. O aplicativo verifica
assinatura e hash antes de instalar e preserva a versão anterior para rollback.
Não confunda a assinatura do manifesto com **Authenticode**: executáveis não
estão assinados com certificado Windows nesta implementação.

Publicar uma release e ativar clientes são decisões separadas. O workflow
`Windows portable build` só publica por despacho manual com tag semântica
existente e `approve_release=true`. `enable_client_updates=false` é o padrão,
inclusive em releases aprovadas. Push em main não publica release ou ativa clientes.
Nenhuma instalação existente é reconfigurada remotamente. O bootstrap/runtime
permanecem imutáveis durante atualização; preserve toda a pasta `state/`.

## 1. Preparação administrativa (manual pelo mantenedor)

No GitHub, configure **Settings → Environments**:

- `windows-release-teste`: revisores de homologação e secret de teste.
- `windows-release-estavel`: revisores de produção, aprovação obrigatória e
  prevenção de autoaprovação. Escolha pelo menos um revisor diferente do operador.

Restrinja esses environments à branch protegida `main`: o workflow é disparado
em main e recebe a tag aprovada como entrada. Restringir apenas a tags bloquearia
esse workflow. Proteja main por revisão e restrinja criação/alteração/exclusão de
tags `v*` por ruleset. Preserve regras e environments já existentes; não os apague.
A autorização para publicação vem do despacho e da aprovação do environment.

O environment antigo `windows-release-approval` não é mais utilizado; não foi
excluído. O runner usa `GITHUB_TOKEN` com `contents:write` apenas no job de
publicação. Não é necessário armazenar PAT no código ou nos clientes.

## 2. Gerar chaves fora do repositório

Execute numa estação confiável do mantenedor, não no computador do cliente.
São necessários Python, cryptography e GitHub CLI para administração. A instalação
portátil do cliente continua sem exigir Python/Node instalados.

```powershell
python -m pip install cryptography
python packaging/windows/signing_keys.py generate --channel teste --path "$env:USERPROFILE\.huginn-signing\teste-2026"
python packaging/windows/signing_keys.py generate --channel estavel --path "$env:USERPROFILE\.huginn-signing\estavel-2026"
```

Cada diretório deve ser novo e estar fora do checkout. O comando pede uma
frase-senha exclusiva com pelo menos 16 caracteres, confirma sem exibir e grava
somente PKCS8 criptografado (`*.private.pem`) e chave pública (`*.pub`). No Windows,
o diretório recebe ACL apenas para o usuário atual e SYSTEM antes de gravar a
privada; em POSIX são usados diretório 0700 e arquivo 0600. Nunca sobrescreve chaves.

Guarde backup criptografado offline da privada e a frase-senha num gerenciador
separado. Teste a recuperação do backup antes da primeira release. Não guarde
privada/frase-senha no repositório, artefatos, tickets, chat ou logs. Não use
`Get-Content`/echo para exibir a privada. Não use a mesma chave nos dois canais.

## 3. Revisar somente as chaves públicas

```powershell
python packaging/windows/signing_keys.py import-public --channel teste --path "$env:USERPROFILE\.huginn-signing\teste-2026\teste.pub"
python packaging/windows/signing_keys.py import-public --channel estavel --path "$env:USERPROFILE\.huginn-signing\estavel-2026\estavel.pub"
```

Revise e publique **somente** `packaging/windows/release-public-keys.json`.
Confirme os fingerprints SHA256 das públicas por um canal independente com os
revisores. O antigo arquivo `release-public-key.txt` é legado e não é usado.
A chave pública fica embarcada no bootstrap do respectivo canal; uma chave de
outro canal não autentica atualizações. Rotação de chave ou runtime exige novo
bootstrap aprovado, sem trocar a confiança silenciosamente em clientes antigos.

## 4. Enviar privadas ao cofre GitHub, sem exibir valores

Autentique `gh` localmente com a conta administrativa autorizada (`gh auth login`).
Depois de configurar os environments e revisar as públicas:

```powershell
python packaging/windows/signing_keys.py upload --channel teste --path "$env:USERPROFILE\.huginn-signing\teste-2026\teste.private.pem"
python packaging/windows/signing_keys.py upload --channel estavel --path "$env:USERPROFILE\.huginn-signing\estavel-2026\estavel.private.pem"
```

O utilitário pede a frase-senha, verifica correspondência da pública revisada,
descriptografa só em memória e envia base64 da privada pelo **stdin** de
`gh secret set`, nunca por argumentos/console/arquivo temporário em claro.
O nome é `HUGINN_RELEASE_SIGNING_KEY` em cada environment; os valores são distintos.
O GitHub protege secrets em repouso e os injeta somente no passo de assinatura.
Uma cópia em memória não tem garantia de apagamento criptográfico em Python.

O job de publicação usa o assinador da branch main revisada, verifica identidade
do ZIP contra versão/canal/runtime/pública e falha sem chave correspondente.
A privada não é incluída no ZIP, manifesto ou artefatos.

## 5. Homologar release real sem ativar clientes

Crie uma tag `vX.Y.Z` no código revisado e testado. Execute manualmente
`Windows portable build` em main com essa tag, canal `teste`,
`approve_release=true`, **enable_client_updates=false**. Aprove o environment.
O CI executa testes Windows e só depois assina/publica como prerelease.
Instale o bootstrap homologado numa pasta temporária de uma estação Windows,
confira pública/fingerprint e teste a atualização ali, preservando o cliente real.

A tarefa inclui um fluxo separado `Real GitHub release validation`, acionado
somente por tags intencionalmente criadas `v0.0.2`, `v0.0.3`, etc. Ele gera uma
chave efêmera exclusiva no runner, cria A=0.0.1 e B=tag com bootstraps desativados,
publica uma prerelease real (nunca latest), destrói a privada, baixa/verifica o
manifesto e ZIP reais por HTTPS e executa atualização e rollback no Windows.
O teste só aprova a operação em memória em duas instalações temporárias, usando
o runtime Windows incluído. A instalação do cliente não é tocada. O relatório
`real-release-proof.json` é anexado somente se a validação passou.

Essas versões 0.0.x ficam abaixo do cliente atual 0.2.0, usam outra chave e não
são atualizações de cliente. A chave efêmera não serve à distribuição futura.
O teste não substitui a confirmação humana nativa nem um ensaio no ambiente do
cliente. Não acessa Oracle; Oracle continua apenas leitura de DUAL/metadados.

## 6. Aprovar produção e ativar explicitamente

Somente depois da homologação e aprovação formal, escolha a versão de produção,
publique por tag/canal `estavel` e aprove o environment de produção. Para gerar
um **novo bootstrap habilitado**, marque separadamente `enable_client_updates=true`.
Não altere esse padrão por commits em main. Instale esse bootstrap numa nova
pasta apenas nos clientes aprovados; preserve a instalação antiga para retorno.
Se houver preferências locais não sensíveis, migre-as após revisão; nunca copie
senhas Oracle. `state/current.json` de uma instalação antiga não deve ser copiado
cegamente para uma nova árvore de versões.

Em clientes habilitados, cada instalação ainda exige aprovação do operador na
interface e na janela Windows; o supervisor verifica assinatura/hash, para o
processo, ativa a versão e restaura a anterior se a saúde não for confirmada.
Rede externa para GitHub API/HTTPS e hosts de assets é requisito para atualização;
sem rede, mantém a instalação atual. A rede Oracle é um requisito independente.

## Pendências que código não pode aprovar sozinho

Criar/proteger environments e tags; escolher revisores; gerar e custodiar as
chaves duráveis; revisar/publicar suas públicas; cadastrar secrets de cada canal;
aprovar tags/releases de homologação/produção; aprovar bootstrap/ativação de cada
cliente; testar confirmação humana; e, se exigido para distribuição comercial,
obter certificado Authenticode e integrar assinatura de executáveis.
