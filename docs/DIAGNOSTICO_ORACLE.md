# Diagnóstico e recuperação Oracle — #25

O incidente relatado confirmou DUAL, mas não confirmou SELECT em PCPRODUT ou
PCFORNEC. Codex não tem acesso ao Windows/Oracle do cliente. A causa naquele
ambiente continua pendente do relatório de metadados; não presumimos grants.

Limitação comprovada no código anterior: ALL_TAB_COLUMNS era combinado com
ALL_TABLES, excluindo views, e todo resultado vazio/incompatível virava a mesma
mensagem de falta de SELECT. DUAL verifica somente a sessão e não o catálogo.

## Fluxo sem comandos ou alterações no banco

1. Selecione explicitamente a conexão salva e confirme PRODUÇÃO se esse for o
   destino autorizado para leitura. Verifique a conexão e use **Diagnosticar
   estrutura** em Consultas WinThor; o formulário avulso legado é independente.
2. O relatório informa owner configurado, schema da sessão quando visível e
   resultado separado para as duas tabelas. Consulta ALL_TAB_COLUMNS sem exigir
   ALL_TABLES e confirma a projeção autorizada com SELECT ... WHERE 1 = 0.
   Quando não há metadados, usa a descrição dos tipos retornada pelo driver,
   sem buscar registros, antes de permitir a consulta parametrizada.
3. ORA-00942 significa objeto ausente OU não visível; não prova falta de grant.
   ORA-01031 identifica privilégio insuficiente, ORA-00904 coluna incompatível;
   demais erros conhecidos são traduzidos sem reproduzir mensagem bruta/DSN.
4. Owners candidatos vêm de metadados visíveis, limitados a 20; podem ser
   parciais e não comprovam SELECT. Sinônimos privados/públicos são informados;
   se detectados como substituto sem metadados, não são seguidos automaticamente
   (inclusive remotos). Confirme o owner da tabela base com o DBA. Cadeias,
   DB links e identificadores Oracle entre aspas não são resolvidos automaticamente.
5. Se houver owner errado/ambíguo, use **Editar conexão**, confirme o owner em
   maiúsculas, salve mantendo a senha em branco, selecione novamente e verifique.
   Nenhum owner, ambiente ou perfil é modificado pelo diagnóstico. Editar invalida
   o contexto anterior e exige seleção/confirmacão; não existe fallback de destino.
6. Após confirmação, filtre por código ou nome e busque produtos/fornecedores.
   Só PCPRODUT/CODPROD/DESCRICAO e PCFORNEC/CODFORNEC/FORNECEDOR são permitidos,
   com owner validado, valores em binds, paginação limitada e sessão read-only.

Não há GRANT, DDL, DML, SQL livre nem tentativa de contornar permissões.
Ausência/incompatibilidade de colunas bloqueia leitura comercial. Descoberta
indisponível não impede informar as evidências já obtidas de cada tabela.

## Evidência real que pode ser compartilhada

Compartilhe somente o resultado de **Diagnosticar estrutura**: tabela, causa,
owner/schema da sessão e owners/sinônimos visíveis que puderem ser divulgados.
Não envie senha, token, cookie, arquivo DPAPI, host/DSN nem registros comerciais.
Se o relatório continuar inconclusivo, o DBA pode fornecer apenas nomes e tipos
das duas projeções e confirmação de SELECT; o aplicativo não cria permissões.

## Testes e limites

Testes reproduzem DUAL OK + catálogo inválido, owner incorreto, metadados
restritos, views, sinônimos locais/remotos, ambiguidade, colunas incompatíveis,
erros Oracle, queries parametrizadas e ausência de commits. O smoke Windows
instalado usa DPAPI/SID reais e um driver double apenas na cópia descartável,
nunca no instalador distribuído. Isso não comprova o schema de cliente real.
Evidências finais e artifact de homologação são registrados no PR da #25.
