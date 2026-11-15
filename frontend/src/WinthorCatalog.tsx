import { useEffect, useRef, useState, type FormEvent } from 'react'
import { type Connection } from './ConnectionManager'

type Kind = 'produtos' | 'fornecedores'
export type Health = { modo: 'simulado' | 'oracle'; conectado: boolean; disponivel: boolean; mensagem: string }
type Result = { modo: 'simulado' | 'oracle'; itens: { codigo: string; nome: string }[]; pagina: number; tamanho: number; tem_proxima: boolean; limite_atingido: boolean }
type Schema = { modo: string; validado_no_oracle: boolean; mensagem?: string; owner_configurado?: string; contexto?: { schema_sessao?: string; usuario_sessao?: string }; tabelas: { tabela: string; validado: boolean; causa?: string; acao?: string; owners_candidatos?: string[]; sinonimos?: { owner: string; destino_owner: string; destino_tabela: string; remoto: boolean }[]; descoberta_limitada?: boolean; descoberta_indisponivel?: boolean; colunas: { nome: string; tipo: string }[] }[] }

export function WinthorCatalog({ token, automatic = false, connection, health, onVerify, kind }: { token: string; automatic?: boolean; connection: Connection | null; health: Health | null; onVerify: () => void; kind: Kind | 'diagnostico' }) {
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [size, setSize] = useState(20)
  const [result, setResult] = useState<Result | null>(null)
  const [schema, setSchema] = useState<Schema | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const active = useRef<AbortController | null>(null)
  const generation = useRef(0)

  function reset() {
    generation.current += 1
    active.current?.abort()
    setBusy(false); setResult(null); setSchema(null); setError('')
  }
  useEffect(() => { reset() }, [token, automatic, connection?.id, connection?.revision, kind])
  useEffect(() => () => { generation.current++; active.current?.abort() }, [])

  async function request(action: 'diagnostico' | Kind, page = 1) {
    const id = ++generation.current
    active.current?.abort()
    const controller = new AbortController()
    active.current = controller
    const timer = window.setTimeout(() => controller.abort(), 30000)
    setBusy(true); setError(''); setResult(null)
    setSchema(null)
    try {
      const response = await fetch(`/api/winthor/${action}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...(automatic ? {} : { Authorization: `Bearer ${token}` }) },
        body: JSON.stringify({ ...(connection ? { connection_id: connection.id, connection_revision: connection.revision } : {}),
          ...(action === 'diagnostico' ? {} : { codigo: code === '' ? null : Number(code), nome: name.trim(), pagina: page, tamanho: size }),
        }), signal: controller.signal, cache: 'no-store',
      })
      const data = await response.json()
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível concluir a consulta.')
      if (id !== generation.current) return
      if (action === 'diagnostico') setSchema(data as Schema)
      else setResult(data as Result)
    } catch (err) {
      if (id === generation.current) {
        setError(err instanceof Error && err.name === 'AbortError'
          ? 'Tempo de resposta excedido. Tente novamente com um filtro menor.'
          : err instanceof Error ? err.message : 'Falha na consulta.')
      }
    } finally {
      window.clearTimeout(timer)
      if (id === generation.current) setBusy(false)
    }
  }

  return <section className="panel" id="winthor" aria-labelledby="winthor-title">
    <div className="panel-head"><div><h2 id="winthor-title">{kind === 'diagnostico' ? 'Estrutura Oracle' : kind === 'produtos' ? 'Pesquisar produtos' : 'Pesquisar fornecedores'}</h2>
      <p>{kind === 'diagnostico' ? 'Diagnóstico por tabela, sem alterar owner ou permissões.' : 'Use código ou parte do nome. A consulta não altera dados do ERP.'}</p></div><span className="badge neutral">Somente leitura</span></div>
    {!health?.disponivel && <div className="inline-guide"><p>Verifique a conexão selecionada antes de continuar. As conexões ficam em Configurações.</p><button className="button primary" type="button" onClick={onVerify}>Verificar conexão WinThor</button><a className="button quiet" href="#configuracoes">Central de Conexões</a></div>}
    {health?.modo === 'simulado' && <p className="notice">SIMULAÇÃO — dados fictícios, sem Oracle.</p>}
    {connection && <p className="destination-label">Consultas direcionadas a: {connection.name} — {connection.environment === 'PRODUCAO' ? 'PRODUÇÃO' : 'TESTE'}</p>}
    <form onSubmit={(e: FormEvent) => { e.preventDefault(); void request(kind === 'diagnostico' ? 'diagnostico' : kind) }}>
      <fieldset className="oracle-fields query-filters" disabled={!health?.disponivel || busy} hidden={kind === 'diagnostico'}>
        <label>Registros por página<select aria-label="Registros por página" value={size} onChange={e => { reset(); setSize(Number(e.target.value)) }}>
          <option value={10}>10</option><option value={20}>20</option><option value={50}>50</option>
        </select></label>
        <label>Código do cadastro<input type="number" min={1} max={9999999999} step={1} value={code}
          onChange={e => { reset(); setCode(e.target.value) }} placeholder="Todos os códigos" /></label>
        <label>Nome ou descrição<input maxLength={80} value={name} onChange={e => { reset(); setName(e.target.value) }}
          placeholder="Parte do nome" autoComplete="off" /></label>
      </fieldset>
      <div className="catalog-actions">
        <button className="oracle-test primary" type="submit" hidden={kind === 'diagnostico'} disabled={!health?.disponivel || busy}>{busy ? 'Consultando…' : 'Buscar cadastros'}</button>
        {kind === 'diagnostico' && <button className="oracle-test primary" type="button" disabled={!health?.disponivel || busy} onClick={() => { void request('diagnostico') }}>Diagnosticar estrutura</button>}
      </div>
    </form>
    <div aria-live="polite">{busy && <p role="status">Aguarde a resposta do servidor local…</p>}{error && <p className="error" role="alert">{error}</p>}</div>
    {schema && <div className="catalog-schema"><h3>Estrutura para consulta</h3>
      <p>{schema.modo === 'simulado' ? 'Estrutura simulada. Nenhuma coluna foi confirmada em Oracle real.' : schema.validado_no_oracle ? 'Colunas e tipos confirmados nos metadados desta conexão.' : 'Diagnóstico Oracle parcial: confira a causa de cada tabela abaixo.'}</p>
      <p>{schema.mensagem}</p><p>{schema.contexto?.schema_sessao && `Schema da sessão: ${schema.contexto.schema_sessao} (perfil permanece explícito)`}</p><p>{schema.owner_configurado && `Owner configurado: ${schema.owner_configurado}`}</p>
      <ul>{schema.tabelas.map(t => <li key={t.tabela}><strong>{t.tabela}</strong>: {t.colunas.map(c => `${c.nome} (${c.tipo})`).join(', ')}
        <p>{t.causa} — {t.acao}</p>
        {!!t.owners_candidatos?.length && <p>Owners visíveis (não selecionados): {t.owners_candidatos.join(', ')}. Use Editar conexão para confirmar o destino; depois selecione e verifique novamente.</p>}
        {t.sinonimos?.map((s, i) => <p key={i}>Sinônimo {s.owner}: {s.destino_owner}.{s.destino_tabela}{s.remoto ? ' (remoto)' : ' (local)'}. Não seguido automaticamente; confirme o destino com o DBA.</p>)}
        {t.descoberta_limitada && <p>Lista limitada a 20 destinos. Solicite apenas metadados ao DBA.</p>}
        {t.descoberta_indisponivel && <p>Descoberta de metadados indisponível; isto não comprova ausência de permissão SELECT.</p>}
      </li>)}</ul></div>}
    {!result && !busy && !error && kind !== 'diagnostico' && <div className="empty-state compact"><h3>Pronto para pesquisar</h3><p>Informe um filtro ou busque os primeiros cadastros do destino selecionado.</p></div>}
    {result && <div className="catalog-results">
      <h3>{kind === 'produtos' ? 'Produtos encontrados' : 'Fornecedores encontrados'}</h3>
      <p>{result.modo === 'simulado' ? 'Resultados fictícios de demonstração.' : 'Dados consultados no Oracle, sem alterações no ERP.'}</p>
      {result.itens.length === 0 ? <p role="status">Nenhum cadastro encontrado para os filtros informados.</p> :
        <div className="table-wrap"><table aria-label="Cadastros WinThor"><thead><tr><th>Código</th><th>Nome / descrição</th></tr></thead>
          <tbody>{result.itens.map((item, index) => <tr key={`${item.codigo}-${index}`}><td>{item.codigo}</td><td>{item.nome}</td></tr>)}</tbody></table></div>}
      <div className="catalog-pagination">
        <button className="oracle-test" type="button" disabled={busy || result.pagina === 1} onClick={() => { void request(kind === 'diagnostico' ? 'diagnostico' : kind, result.pagina - 1) }}>Página anterior</button>
        <span>Página {result.pagina} • {result.itens.length} registros</span>
        <button className="oracle-test" type="button" disabled={busy || !result.tem_proxima} onClick={() => { void request(kind === 'diagnostico' ? 'diagnostico' : kind, result.pagina + 1) }}>Próxima página</button>
      </div>
      {result.limite_atingido && <p className="notice">Limite de 100 páginas atingido. Refine os filtros para continuar.</p>}
    </div>}
  </section>
}
