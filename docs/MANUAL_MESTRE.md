# HUGINN IA — Manual mestre da aplicação

**Versão documental:** 0.1 — 14/11/2026  
**Fonte da verdade:** código e documentação versionados neste repositório.  
**Classificação:** documentação técnica e funcional do MVP; não constitui homologação de produção.

## 1. Objetivo e proposta de valor

HUGINN IA é uma plataforma de apoio à análise de NF-e e, futuramente, à auditoria de entradas e inteligência de compras integrada ao TOTVS WinThor. Slogan: **Seu ERP registra. HUGINN antecipa.** Assinatura: **Inteligência antes da decisão.**

Público: equipes de cadastro, compras, fiscal, recebimento, TI e gestão. O sistema **não substitui o ERP, o contador ou a validação tributária humana**.

## 2. Estado real do produto

| Recurso | Situação | Evidência / limitação |
| --- | --- | --- |
| Importação de XML NF-e | Implementado no MVP | `POST /api/nfe/importar`; aceita NFe/nfeProc, um documento por arquivo, limite de 5 MiB |
| Extração de emitente e itens | Implementado | Chave, número, série, data, CNPJ/nome, cProd, descrição, NCM, CFOP, quantidade e valores |
| Identificação de produto novo no WinThor | Planejado | XML marca itens pendentes; ainda não compara com cadastro real |
| Teste de conexão Oracle | Implementado para ambiente local | `POST /api/oracle/testar`; sem persistência de senha |
| Diagnóstico de metadados WinThor | Implementado | `POST /api/oracle/diagnostico`; consulta metadados autorizados, não dados comerciais |
| Comparação de custos, fornecedor e pedido | Planejado | Exige consultas fixas e validação do esquema no cliente |
| Captura automática DF-e/NSU SEFAZ | Planejado | Sem integração SEFAZ no MVP |
| Autenticação e multiempresa | Pendente | Não implantar em serviço compartilhado antes de implementar |
| Windows portátil | Implementado como bootstrap de desenvolvimento | Atualizações de cliente desativadas por padrão |
| Atualização assinada e rollback | Implementação documentada; homologação real condicionada | Exige validação Windows e aprovações de publicação |

## 3. Arquitetura

- **Frontend:** React + TypeScript + Vite, em `frontend/`.
- **API:** FastAPI/Python, ponto de entrada `backend/app/main.py`.
- **Conexão:** `python-oracledb` em modo Thin; sem OCI no cliente.
- **Banco do cliente:** Oracle WinThor, acesso somente leitura; o aplicativo não escreve dados fiscais ou comerciais.
- **Distribuição Windows:** `packaging/windows/`, Python embarcado, frontend compilado, supervisor independente, versões isoladas e rollback.
- **CI e publicação:** GitHub Actions; branch principal protegida; canal de testes separado de produção.

Fluxo atual: **operador → interface local → API FastAPI → parser XML ou diagnóstico Oracle → resposta à interface**. XML e credenciais não devem ser registrados em logs. A análise XML não consulta Oracle automaticamente.

## 4. Contratos da API atual

| Método e caminho | Finalidade | Observações |
| --- | --- | --- |
| `GET /api/health` | Estado da API | Resposta de saúde não comprova Oracle conectado |
| `POST /api/nfe/importar` | Recebe arquivo XML | multipart/form-data, campo `file`; erros 400, 413 e 422 |
| `POST /api/oracle/testar` | Teste Oracle | JSON host, port, service, user, password; somente loopback |
| `POST /api/oracle/diagnostico` | Metadados de tabelas | Mesma restrição de acesso local; não consulta registros comerciais |
| `GET /api/version` | Versão instalada | Usado na verificação de atualização |
| `GET /api/updates/status` | Estado do atualizador | Pode estar desativado |
| `POST /api/updates/check` e `/apply` | Solicitações locais ao supervisor | Exigem origem/host locais e atualizador habilitado; não são comandos remotos genéricos |

A documentação interativa da API de desenvolvimento está em `http://localhost:8000/docs`. Os contratos completos e as validações devem ser confirmados no código antes de alterar integrações.

## 5. Regras de negócio do MVP

1. Importação exige extensão `.xml` e tamanho máximo de 5 MiB.
2. Documento deve conter exatamente uma NFe e estrutura de identificação/emitente válida.
3. Valores monetários e quantitativos são tratados com `Decimal` e números não finitos são rejeitados.
4. Todo item extraído permanece **pendente de comparação com WinThor** até existir integração real; nunca mostrar cadastro confirmado com base em dados de demonstração.
5. Diagnóstico Oracle consulta apenas metadados predefinidos, sem SQL livre, gravação ou concessão de privilégios.
6. Análises fiscais futuras são alertas e orientações; nenhuma tributação automática ou escrita fiscal sem escopo e aprovação próprios.

## 6. Implantação e operação

**Desenvolvimento:** Python 3.12+, Node 20+. Consulte [README](../README.md) para comandos de instalação e execução. Interface Vite em `localhost:5173`; API em `localhost:8000`.

**Windows portátil:** consulte [guia de empacotamento](../packaging/windows/README.md). Extrair o ZIP inteiro e executar `INICIAR_HUGINN.bat`; interface e API usam loopback. Não exige instalar Python/Node/Oracle Client no computador cliente.

**Oracle:** usar conta de banco com privilégios mínimos de SELECT e conectividade autorizada ao listener. Consulte [Conexão Oracle](CONEXAO_ORACLE.md). Nunca incluir senhas em tickets, commits, screenshots, logs ou documentação.

**Atualização e recuperação:** [Atualizações Windows](ATUALIZACOES_WINDOWS.md) e [Distribuição assinada](DISTRIBUICAO_RELEASES.md). Publicar release **não** ativa clientes; atualização exige as confirmações previstas e pode realizar rollback. Nunca apagar o estado de recuperação durante um incidente.

## 7. Segurança e limitações de produção

- Aplicação atual é **MVP local**, sem autenticação e isolamento multi-tenant; não expor a API à Internet.
- Senhas Oracle devem permanecer transitórias; não registrar nem transmitir para serviços externos.
- Não disponibilizar endpoint de SQL arbitrário, DML/DDL ou execução de comandos.
- A conta Oracle somente leitura e a rede de acesso são responsabilidade da implantação autorizada.
- Certificados SEFAZ, manifestação, armazenamento de XML e dados pessoais exigirão desenho de segurança, retenção, segregação e trilha de auditoria antes da implementação.
- Não alegar homologação de conexão Oracle real, SEFAZ ou Windows apenas com testes simulados.

## 8. Qualidade e evidências

- Backend: `python -m pytest -q` na raiz com dependências instaladas.
- Frontend: `npm ci` e `npm run build` em `frontend/`.
- Windows: `packaging/windows/smoke.py`, `browser_smoke.py` e `update_smoke.py` com pacote gerado, conforme instruções.
- Evidência de execução Windows deve vir de job concluído em runner Windows; mocks não comprovam conexão Oracle real.
- Cada alteração deve incluir testes e documentação correspondente; PRs não devem ser integrados com verificações obrigatórias falhando.

## 9. Roadmap e critérios de aceite

### M1 — Demonstração funcional
- XML real de teste importado e itens exibidos com identificação clara de pendências.
- Conexão Oracle real validada em ambiente autorizado, sem escrita.
- Diagnóstico das tabelas e permissões registrado sem expor dados sensíveis.

### M2 — Auditoria de entradas
- Mapeamento de fornecedor/produto com consultas parametrizadas.
- Divergência de custo e novos produtos/fornecedores claramente identificados.
- Vínculo opcional com pedido de compra, respeitando regras do cliente.

### M3 — Distribuição DF-e
- Integração SEFAZ por certificado autorizado, NSU, deduplicação e controle de erros.
- Regras de manifestação, armazenamento e auditoria formalmente aprovadas.

### M4 — Operação comercial
- Autenticação, isolamento por cliente, observabilidade, licenciamento e procedimentos de suporte.
- Homologação de atualizações assinadas em Windows e política de ativação por cliente.

## 10. Mapa da documentação

- [Política de documentação contínua](POLITICA_DOCUMENTACAO.md)
- [Conexão Oracle](CONEXAO_ORACLE.md)
- [Atualizações Windows](ATUALIZACOES_WINDOWS.md)
- [Distribuição por Releases](DISTRIBUICAO_RELEASES.md)
- [Preparação de testes no GitHub](PREPARAR_TESTES_PELO_GITHUB.md)
- [Empacotamento Windows](../packaging/windows/README.md)

**Responsável pela manutenção:** toda pessoa/agente que altera código ou comportamento. Atualizar este manual quando a alteração afetar funcionalidade, arquitetura, contrato, segurança ou implantação.
