# HUGINN IA — Windows portátil x64

[Baixar ZIP](https://github.com/wondersonrj/huginn-ia/raw/refs/heads/main/release/HUGINN-IA-Windows-x64.zip)

Extraia **todo o ZIP** e dê duplo clique em `INICIAR_HUGINN.bat`.
O navegador abre em `http://127.0.0.1:8000`; mantenha a janela do servidor aberta.
Requer Windows 10/11 x64. Inclui Python e dependências; não requer Node.js,
Python instalado nem Oracle Client. Consulte `LEIA-ME.txt` dentro do pacote.
A conta Oracle deve ser somente leitura, autorizada pelo DBA.

Gerado a partir do código `7757570`, com runtime oficial e wheels Windows
verificados por hash. SHA256 do ZIP no arquivo `.zip.sha256` ao lado.
O registro `BUILD-INFO.json` dentro do pacote identifica a origem.

Validações locais: 50 testes backend aprovados, TypeScript/build aprovados,
interface de produção e XML no Chromium aprovados, smoke test da aplicação
extraída do ZIP aprovado **usando Python Linux**. Falha de rede Oracle foi
exercitada com o driver real em uma porta local fechada; os casos de sucesso
Oracle são simulados. Nenhuma gravação no WinThor foi executada.

**Este artefato ainda não foi executado em Windows pelo autor deste build.
Não há validação de conexão com Oracle real.** Confira também o resultado do
workflow `Windows portable build` no GitHub Actions; a presença do workflow
não comprova sua execução bem-sucedida. Teste no computador Windows antes de
usar este pacote em qualquer fluxo operacional.

Scripts e reprodução: [packaging/windows](../packaging/windows/README.md).
