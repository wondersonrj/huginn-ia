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
   privados no owner configurado sem metadados da base não são seguidos
   (inclusive remotos); PUBLIC não resolve nomes qualificados por owner.
   Confirme o owner da tabela base com o DBA. Cadeias,
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

## Complemento P0 do plano #33

A busca e o diagnóstico agora usam a mesma validação: mesmo com metadados
visíveis, a projeção exata é descrita com `WHERE 1 = 0` antes de ler registros.
Isso confirma o SELECT efetivo da sessão, incluindo permissões herdadas de roles,
sem exigir acesso a DBA_TAB_PRIVS nem inferir grants pelo dicionário. A evidência
retornada é `metadados_e_select_sem_linhas` ou `select_sem_linhas`. Coluna ausente
e tipo incompatível têm causas distintas. O diagnóstico avulso também deixa de
exigir o JOIN com ALL_TABLES; sua lista de colunas continua sendo apenas
visibilidade de metadados, sem comprovação de SELECT comercial.

Uma referência qualificada `OWNER.PCPRODUT` não usa sinônimo público. Assim, um
sinônimo PUBLIC informado no relatório não impede validar o owner explicitamente
configurado, mesmo quando ALL_TAB_COLUMNS está vazio. Um sinônimo **privado do
owner configurado**, sem metadados da tabela base, continua bloqueado: é preciso
confirmar explicitamente o owner base no perfil. Destinos remotos, cadeias e
nomes fora da allowlist não são seguidos. Se ALL_SYNONYMS não puder ser consultado
nesse fallback, a causa é `sinonimos_nao_verificados`; nenhuma consulta comercial
é feita nem se presume falta de SELECT na PCPRODUT.

### Matriz de compatibilidade e homologação on-premises

| Cenário | Verificação automatizada | Limite / aceite no cliente |
| --- | --- | --- |
| Oracle 19c + python-oracledb Thin | SQL Oracle com binds, descrição dos tipos NUMBER/texto e paginação OFFSET/FETCH; driver fake recusa escrita | Baseline do pacote; versão e autenticação reais devem ser confirmadas no cliente |
| DUAL OK, owner errado, owner ambíguo | Falha por tabela, contexto da sessão e candidatos; perfil não alterado | Operador escolhe explicitamente o owner base |
| Colunas visíveis, SELECT negado | Projeção falha e bloqueia busca antes de ler registros | ORA-01031 confirma insuficiência; ORA-00942 continua ambíguo |
| Dicionário vazio / acesso restrito | Descrição sem linhas valida tipos quando não há sinônimo privado | Não exige novos grants ao dicionário; fallback indisponível falha fechado |
| Sinônimos PUBLIC / privados / remotos | PUBLIC não bloqueia owner qualificado; privados não redirecionam a busca | Confirmar owner base, sem DB link automático |
| Colunas ausentes / tipos incompatíveis | Diagnóstico por causa; sem consulta comercial | Somente projeções fixas CODPROD/DESCRICAO e CODFORNEC/FORNECEDOR |
| Perfil Windows existente | Regressões de seleção, credencial protegida e contexto na API; CI Windows com DPAPI nativo | Sem migração ou regravação de credenciais neste complemento |

Oracle 11g, driver Thick/Instant Client e TOTVS Cloud não fazem parte desta
homologação: Thin, autenticação e OFFSET/FETCH precisam ser compatíveis com o
servidor escolhido. Não habilitar Thick nem mudar a conexão para contornar erro.
O conector mantém a proteção existente `SET TRANSACTION READ ONLY`; o restante
do fluxo executa somente SELECT e nunca commit, DML, DDL ou GRANT.

Para concluir o aceite real, no Windows autorizado do cliente: selecionar o
perfil existente, verificar DUAL, executar **Diagnosticar estrutura**, confirmar
PCPRODUT, pesquisar código conhecido com tamanho de página pequeno e verificar
a próxima página. Repetir com PCFORNEC se autorizado. Registrar versão do
servidor/driver, resultado por tabela e paginação sem publicar registros,
credenciais, host ou DSN. Confirmar que o perfil/DPAPI foi preservado. Sem acesso
específico autorizado, esse aceite permanece **pendente**, mesmo com CI verde.

Este PR cobre a correção Oracle P0; módulos #31/#32 e ativação do updater não
são implementados aqui. O bloqueio de publicação/assinatura do updater continua
documentado em [Atualizações Windows](ATUALIZACOES_WINDOWS.md).
