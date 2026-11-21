# HUGINN — units comuns (Delphi)

## uLicencaHUGINN.pas: licença de todas as aplicações HUGINN

Valida o `.dat` emitido pelo **Gerador de Licenças HUGINN v1.1**, uso interno. Contém **só a chave pública**: a chave privada fica apenas no Gerador e **nunca** entra neste repositório.

- Formato: `Base64(PRODUTO|Cliente|ID|aaaa-mm-dd)` + `.` + `Base64(assinatura RSA-2048/SHA-256 CryptoAPI)`.
- `IdInstalacao` gera `XXXX-XXXX-XXXX-XXXX` a partir do `MachineGuid` do Windows. No WinThor Cloud/RDP, todos os usuários do mesmo servidor compartilham o ID, ou seja, a licença vale para o servidor.
- `VerificarArquivo(arquivo, PRODUTO)` devolve um destes status: `slValida`, `slVencida`, `slOutraInstalacao`, `slOutroProduto`, `slInvalida` (assinatura não confere) ou `slAusente`.
- `InstalarLicenca(origem, PRODUTO)` valida e copia para `licenca_<produto>.dat`, ao lado do `.exe`.

### Como usar numa aplicação nova

1. Inclua `..\..\comum\uLicencaHUGINN.pas` no `.dpr`.
2. Defina o identificador do produto, por exemplo `HUGINN_XML_AUTOMATICO_WINTHOR`, e **cadastre o mesmo identificador** na aba *Produtos* do Gerador.
3. Na tela, coloque os botões **Copiar ID** (`IdInstalacao`) e **Licença…** (`InstalarLicenca`), e mostre `Licenciado para <cliente> até <data>`.
4. Decida o que a falta de licença bloqueia. No XML Automático, sem licença o programa funciona só em modo demonstração.

### Fluxo com o cliente

O cliente clica em **Copiar ID** e envia o ID. No Gerador, você escolhe o produto, o cliente, cola o ID, escolhe a validade e gera o `.dat`. O cliente clica em **Licença…** e seleciona o arquivo.

### Limitações conhecidas

- Não há proteção contra o relógio do Windows voltado para trás.
- Trocar de servidor, ou reinstalar o Windows, gera outro `MachineGuid`. Nesse caso é preciso reemitir a licença, o que o Gerador já faz em "Reemitir / renovar".
