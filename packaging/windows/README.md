# Pacote Windows x64

O pacote inclui CPython 3.12.10 da distribuição oficial NuGet, dependências
Windows x64 (wheels), backend e React compilado. Não utiliza PyInstaller:
a distribuição de runtime permite gerar o ZIP em Linux sem tentar compilar
um executável Windows com PyInstaller Linux. O runtime inclui as DLLs VC++.
Não é necessário instalar Python, Node ou Oracle Client no computador cliente.

Para gerar, com Python 3.12 e Node disponíveis na máquina de build:

```sh
python -m pip install -r backend/requirements.txt
npm ci --prefix frontend
npm run build --prefix frontend
python -m pytest -q
python packaging/windows/build.py
```

O resultado está em `release/HUGINN-IA-Windows-x64.zip`, com SHA256 ao lado.
O script valida o SHA256 fixo do runtime oficial e os hashes de todas as
wheels em `requirements.lock`. `requirements.txt` registra os alvos diretos;
o lock registra a resolução completa Windows/CPython 3.12. Atualizações exigem
nova resolução de wheels Windows e revisão de hashes; não desative verificações.
Não são copiados `.env`, arquivos de usuário, caches ou credenciais.
O ZIP inclui licenças do runtime e metadados/licenças das dependências.

Em Windows, o smoke test executa o runtime que está no ZIP, a partir de um
caminho com espaços, sem usar Python instalado para o servidor:

```sh
python packaging/windows/smoke.py release/HUGINN-IA-Windows-x64.zip
```

O workflow `Windows portable build` faz build e smoke test em Windows e
publica o ZIP como artefato do Actions. Um workflow salvo não prova que a
execução remota terminou: consulte o resultado no GitHub Actions.
Em Linux, `--python /caminho/da/venv/bin/python` permite validar o código e os
assets extraídos do ZIP, mas não executa nem valida os binários Windows.
Os testes Oracle usam simulação ou porta local fechada; não validam Oracle real.

No cliente: extrair tudo e abrir `INICIAR_HUGINN.bat`. Backend e interface
usam apenas `127.0.0.1:8000`; a janela fica aberta e Ctrl+C encerra o servidor.
Credenciais são usadas em memória durante uma tentativa e não persistidas.
Uma conta Oracle com somente leitura e rede até o listener 19c são requisitos.
Consulte `LEIA-ME.txt` e `docs/CONEXAO_ORACLE.md` para diagnóstico e limites.
