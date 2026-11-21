# HUGINN XML Automático — roteiro de homologação

Execute na ordem. Anote o resultado de cada passo: **OK**, **falhou** (com a mensagem exata) ou **não se aplica**.

## 1. Compilação e testes (sem banco)

1. Abra `HuginnXML.dpr` → Build Win32. Anote erros com unidade e linha.
2. Abra `tests\TestesHuginnXML.dpr` → Build → execute. Todos os testes devem passar.
3. Copie XMLs reais para `fixtures\real\` (fora do Git) e rode de novo. O teste `LeXmlsReaisLocais` precisa ler todos.

## 2. Modo demonstração

| Arquivo (`fixtures\`) | Esperado |
|---|---|
| `nfe_valida_mista.xml` | 9 itens. Item 1 OK; 2 alerta de custo (+18,31%); 3 conflito (1004 × 1003); 4 produto novo; 5 OK com fator 20; 6 sem fator (FD × UN); 7 CEST e sem entrada anterior; 8 NCM e "fora de linha"; 9 GTIN inválido e novo. **Pode liberar.** |
| `nfe_ja_lancada.xml` | Liberação **bloqueada** (pré-entrada existente) |
| `nfe_filial_ambigua.xml` | Pede para escolher a filial (3 ou 4) e reanalisa |
| `nfe_filial_2.xml` | Usa o custo da filial 2 (30,00) e não o da filial 1 |
| `nfe_fornecedor_ausente.xml` | Fornecedor não cadastrado; item 2 depende do fornecedor |
| `nfe_fornecedor_duplicado.xml` | Alerta de CNPJ em 2 fornecedores |
| `nfe_destinatario_outra_empresa.xml` | Filial não encontrada |
| `nfe_mesma_chave_bytes_diferentes.xml` (abrir depois da mista) | Conflito de hash. Liberação **bloqueada** |
| `nfe_invalida.xml`, `nfe_com_dtd.xml`, `nfe_chave_dv_invalida.xml` | XML **não aceito**, com a mensagem |
| `evento_cancelamento.xml` | Fora do escopo (evento) |

Libere a mista e confira:
- o arquivo em `Liberados\` tem o **mesmo SHA-256** do original (`certutil -hashfile arquivo SHA256`);
- o Histórico mostra abrir, analisar e liberar.

## 3. Oracle somente leitura (base de homologação ou produção, só leitura)

1. Crie ou use um usuário só com as permissões da [matriz](MATRIZ_CONSULTAS.md). Configure e clique em **Testar conexão**.
2. Use o **mesmo modo de pesquisa** da 1301 (hoje: 5 - Pesquisa Automática).
3. **XML da LAR 2246108** (já tem pré-entrada): deve acusar "pré-entrada existente" e **bloquear**, igual à 1301.
4. **Uma nota nova, ainda não importada**:
   - confira se fornecedor, filial e produtos batem com o que a 1301 mostra na tela de itens;
   - confira o custo contra a última entrada de 2 produtos na rotina 1118 (histórico do produto);
   - libere o XML e importe na 1301 por "Arquivo em pasta". A 1301 não pode acusar nada que o HUGINN não tenha mostrado. Se acusar, anote: é uma regra que falta.
5. Desconecte a rede ou use um usuário sem permissão: deve aparecer **falha técnica** e a liberação deve ficar bloqueada.

## 4. Menu do WinThor

1. 529: crie a rotina apontando para o `HuginnXML.exe`. 530: dê permissão a um usuário.
2. Abra pelo menu e repita o passo 3.4.

## Critérios de aceite da v0.1

- A conferência do HUGINN e a validação da 1301 **não divergem** em pelo menos 3 notas reais.
- Nenhuma gravação no WinThor pelo HUGINN (o usuário Oracle só tem SELECT).
- O XML liberado tem o mesmo SHA-256 do recebido.
