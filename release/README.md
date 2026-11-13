# HUGINN IA — bootstrap Windows x64 de teste, versão 0.2.0

[Baixar ZIP](https://github.com/wondersonrj/huginn-ia/raw/refs/heads/main/release/HUGINN-IA-Windows-x64.zip)

Extraia **todo o ZIP** e dê duplo clique em `INICIAR_HUGINN.bat`.
Interface e API abrem juntas em `http://127.0.0.1:8000`. Mantenha a janela
aberta; Ctrl+C encerra o supervisor e o aplicativo. Windows 10/11 x64,
sem instalar Python, Node.js ou Oracle Client. Veja `LEIA-ME.txt` no pacote.

Inclui diagnóstico WinThor **exclusivamente de metadados** para a lista fixa
PCPRODUT, PCFORNEC, PCPRODFILIAL, PCPRODFORNEC, PCNFENT, PCMOV e PCPEDIDO.
Só consulta ALL_TAB_COLUMNS/ALL_TABLES; separa proprietários, não resolve
sinônimos e não lê registros comerciais. Credenciais não são persistidas.

Inclui supervisor de atualização com assinatura Ed25519, SHA256, origens fixas,
backup, troca atômica da versão, confirmação HTTP e rollback. **A atualização
permanece desativada neste bootstrap**: faltam chave pública de distribuição,
secret de assinatura e aprovação de uma release real pelo mantenedor.
O ZIP de main não é uma release aprovada nem fonte do atualizador. Não houve
deploy para clientes nem criação de tag nesta tarefa.

Código do pacote: `ab518de4e57cbb3a164081c931740a7b1eeb040f`. O ZIP deste diretório
foi gerado em Linux desse código, com runtime oficial e wheels Windows x64
fixados por hash. SHA256 no arquivo `.zip.sha256` ao lado; `BUILD-INFO.json`
identifica a origem. Não contém credenciais reais.

## Testes e limites

- Linux: 106 testes passaram; 1 teste exclusivo de compartilhamento de arquivo
  Windows foi pulado. Build/TypeScript, smoke do ZIP e Chromium aprovados.
- **Windows CI:** suíte backend, build, runtime incluído, inicialização em pasta
  com espaços, porta ocupada, interface/diagnóstico simulado/XML no Chromium,
  atualização A→B e rollback de C quebrada→B com processos reais aprovados.
- O teste de atualização usa pacotes sintéticos e chave efêmera de teste,
  sem Oracle e sem baixar/publicar release real. A aprovação humana nativa
  não é exercitada no CI. Não foi confirmada conexão com Oracle real.

[Evidência Windows CI](https://github.com/wondersonrj/huginn-ia/actions/runs/43436410457)
e [registro dos passos](WINDOWS-CI-EVIDENCE.json). O CI reconstruiu e executou
seu próprio ZIP em Windows; o ZIP deste diretório foi reproduzido em Linux
do mesmo código e lock, não é o arquivo binário baixado do artefato CI.
O artefato exato testado no Windows também está no run acima (download do
Actions pode exigir login no GitHub).

Distribuição, instalação inicial, ativação, recuperação e limites de segurança:
[Atualizações Windows](../docs/ATUALIZACOES_WINDOWS.md).
