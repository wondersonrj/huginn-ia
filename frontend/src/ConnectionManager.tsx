import { useEffect, useRef, useState, type FormEvent } from 'react'

export type Connection = { id: string; revision: string; name: string; environment: 'TESTE' | 'PRODUCAO'; host: string; port: number; service: string; user: string; owner: string; password_saved: boolean; last_test: { ok: boolean; checked_at: string } | null }
type Fields = { name: string; environment: 'TESTE' | 'PRODUCAO'; host: string; port: string; service: string; user: string; owner: string }
const empty: Fields = { name: '', environment: 'TESTE', host: '', port: '1521', service: '', user: '', owner: '' }

export function ConnectionManager({ token, onChange }: { token: string; onChange: (connection: Connection | null) => void }) {
  const [profiles, setProfiles] = useState<Connection[]>([])
  const [supported, setSupported] = useState<boolean | null>(null)
  const [active, setActive] = useState<Connection | null>(null)
  const [source, setSource] = useState('')
  const [fields, setFields] = useState<Fields>(empty)
  const [editing, setEditing] = useState<Connection | null>(null)
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const epoch = useRef(0)
  const controller = useRef<AbortController | null>(null)
  useEffect(() => {
    epoch.current += 1; controller.current?.abort()
    setProfiles([]); setSupported(null); setActive(null); setSource(''); setFields(empty)
    setEditing(null); setPassword(''); setMessage(''); setError(''); setBusy(false)
  }, [token])
  useEffect(() => () => { controller.current?.abort() }, [])

  async function execute(action: string, body: object = {}) {
    const id = ++epoch.current
    controller.current?.abort()
    const operation = new AbortController()
    controller.current = operation
    const signal = operation.signal
    const timer = window.setTimeout(() => operation.abort(), 30000)
    setBusy(true); setError(''); setMessage('')
    async function post(path: string, data: object) {
      const response = await fetch(`/api/connections/${path}`, { method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(data), cache: 'no-store', signal })
      const result = await response.json()
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Operação indisponível.')
      return result
    }
    try {
      const result = await post(action, body)
      const listing = action === 'list' ? result : await post('list', {})
      if (id !== epoch.current) return
      setProfiles(listing.profiles); setSupported(listing.supported); setActive(listing.active); setSource(listing.source)
      onChange(listing.active)
      if (action === 'save' || action === 'import-environment') { setEditing(null); setFields(empty) }
      setMessage(action === 'test' ? result.mensagem : action === 'select'
        ? 'Destino selecionado explicitamente. Verifique a conexão antes de buscar.'
        : action === 'environment' ? 'Configuração por ambiente escolhida explicitamente; destino não classificado.'
        : 'Lista atualizada. Cada operação Oracle abre e encerra sua própria sessão.')
    } catch (err) {
      if (id === epoch.current) {
        // Do not leave old query context usable after an uncertain mutation/failure.
        onChange(null); setActive(null)
        setError(err instanceof Error && err.name === 'AbortError' ? 'Operação interrompida. Recarregue a lista antes de repetir.'
          : err instanceof Error ? err.message : 'Operação indisponível.')
      }
    } finally {
      window.clearTimeout(timer)
      if (id === epoch.current) { setBusy(false); setPassword('') }
    }
  }

  function ref(profile: Connection) { return { id: profile.id, revision: profile.revision } }
  function confirmed(profile: Connection) {
    return profile.environment !== 'PRODUCAO' || window.confirm(`Confirmar destino PRODUÇÃO: ${profile.name}? Somente leitura. Não é autorização de release ou escrita no ERP.`)
  }
  function edit(profile: Connection) {
    setEditing(profile); setPassword(''); setFields({ name: profile.name, environment: profile.environment,
      host: profile.host, port: String(profile.port), service: profile.service, user: profile.user, owner: profile.owner })
    setError(''); setMessage('Senha nunca é carregada no formulário. Deixe em branco para manter a salva.')
  }

  return <section className="connection-manager" aria-labelledby="connection-manager-title">
    <h3 id="connection-manager-title">Conexões Oracle salvas</h3>
    <p>Windows: senha protegida para este usuário e instalação. Seleção obrigatória após reiniciar. O teste é pontual e não mantém conexão aberta.</p>
    <button className="oracle-test" type="button" disabled={busy || token.length < 32} onClick={() => { void execute('list') }}>Carregar conexões salvas</button>
    {supported === false && <p className="notice">Proteção Windows indisponível neste sistema. Nenhuma senha será persistida; use a configuração local por ambiente.</p>}
    {supported && <>
      <p className={active?.environment === 'PRODUCAO' ? 'production-destination' : 'notice'} role="status">
        {active ? `Destino selecionado: ${active.name} — ${active.environment === 'PRODUCAO' ? 'PRODUÇÃO' : 'TESTE'} (sem sessão permanente)`
          : source === 'environment' ? 'Origem: configuração por ambiente, destino não classificado.' : 'Desconectado: selecione explicitamente uma conexão salva.'}
      </p>
      <div className="saved-connections">{profiles.map(profile => <article key={profile.id} className={profile.environment === 'PRODUCAO' ? 'saved-profile production-destination' : 'saved-profile'}>
        <h4>{profile.name} <span>{profile.environment === 'PRODUCAO' ? 'PRODUÇÃO' : 'TESTE'}</span></h4>
        <p>{profile.host}:{profile.port} · {profile.service} · {profile.user} · Schema {profile.owner}</p>
        <p>{profile.password_saved ? 'Senha armazenada com proteção Windows; não exibida.' : 'Senha ausente: informe uma nova antes de selecionar.'}</p>
        <p>{profile.last_test ? `${profile.last_test.ok ? 'Último teste pontual confirmado' : 'Último teste falhou'}: ${new Date(profile.last_test.checked_at).toLocaleString()}` : 'Conectividade não testada nesta sessão.'}</p>
        <div className="catalog-actions">
          <button className="oracle-test" type="button" disabled={busy || !profile.password_saved} onClick={() => { if (confirmed(profile)) void execute('select', { ...ref(profile), confirm_environment: profile.environment }) }}>Selecionar {profile.name}</button>
          <button className="oracle-test" type="button" disabled={busy || !profile.password_saved} onClick={() => { if (confirmed(profile)) void execute('test', { ...ref(profile), confirm_environment: profile.environment }) }}>Testar {profile.name}</button>
          <button className="oracle-test" type="button" disabled={busy} onClick={() => edit(profile)}>Editar {profile.name}</button>
          <button className="oracle-test" type="button" disabled={busy || !profile.password_saved} onClick={() => { if (window.confirm(`Remover a senha salva de ${profile.name}? Será preciso informá-la novamente.`)) void execute('remove-password', ref(profile)) }}>Remover senha de {profile.name}</button>
          <button className="oracle-test" type="button" disabled={busy} onClick={() => { if (window.confirm(`Excluir ${profile.name} e sua senha salva? Nenhum dado Oracle será alterado.`)) void execute('delete', ref(profile)) }}>Excluir {profile.name}</button>
        </div>
      </article>)}</div>
      <form onSubmit={(e: FormEvent) => { e.preventDefault(); void execute('save', {
        ...fields, port: Number(fields.port), ...(editing ? ref(editing) : {}), ...(password ? { password } : {}),
      }) }}>
        <h4>{editing ? 'Editar conexão salva' : 'Cadastrar conexão Oracle'}</h4>
        <fieldset className="oracle-fields" disabled={busy}>
          <label>Nome da conexão<input required maxLength={80} value={fields.name} onChange={e => setFields({ ...fields, name: e.target.value })} autoComplete="off" /></label>
          <label>Ambiente da conexão<select aria-label="Ambiente da conexão" value={fields.environment} onChange={e => setFields({ ...fields, environment: e.target.value as Fields['environment'] })}><option value="TESTE">TESTE</option><option value="PRODUCAO">PRODUÇÃO</option></select></label>
          <label>Host da conexão<input required maxLength={253} value={fields.host} onChange={e => setFields({ ...fields, host: e.target.value })} autoComplete="off" /></label>
          <label>Porta da conexão<input required type="number" min={1} max={65535} value={fields.port} onChange={e => setFields({ ...fields, port: e.target.value })} /></label>
          <label>Service Name da conexão<input required maxLength={255} value={fields.service} onChange={e => setFields({ ...fields, service: e.target.value })} autoComplete="off" /></label>
          <label>Usuário da conexão<input required maxLength={128} value={fields.user} onChange={e => setFields({ ...fields, user: e.target.value })} autoComplete="off" /></label>
          <label>Schema WinThor<input required pattern="[A-Z][A-Z0-9_]{0,29}" maxLength={30} value={fields.owner} onChange={e => setFields({ ...fields, owner: e.target.value })} autoComplete="off" /></label>
          <label>Nova senha da conexão<input type="password" maxLength={1024} value={password} onChange={e => setPassword(e.target.value)} autoComplete="off" /></label>
        </fieldset>
        <div className="catalog-actions"><button className="oracle-test" disabled={busy} type="submit">Salvar conexão</button>
          <button className="oracle-test" type="button" disabled={busy} onClick={() => { setEditing(null); setFields(empty); setPassword('') }}>Limpar edição</button></div>
        <p>Senha em branco mantém a existente; em cadastro novo, salva apenas os metadados. Editar invalida a seleção e exige nova confirmação.</p>
      </form>
      <div className="catalog-actions">
        <button className="oracle-test" type="button" disabled={busy} onClick={() => { if (window.confirm('Usar explicitamente a configuração por ambiente deste servidor? O destino não é classificado automaticamente como TESTE.')) void execute('environment', { confirm: 'USAR CONFIGURACAO DO AMBIENTE' }) }}>Usar configuração por ambiente</button>
        <button className="oracle-test" type="button" disabled={busy || !fields.name} onClick={() => { if (window.confirm('Salvar a configuração Oracle atual do servidor neste usuário Windows? Isso não seleciona a conexão.')) void execute('import-environment', { name: fields.name, environment: fields.environment }) }}>Salvar configuração do ambiente</button>
      </div>
    </>}
    <div aria-live="polite">{busy && <p role="status">Aguarde a operação local…</p>}{message && <p role="status">{message}</p>}{error && <p role="alert" className="error">{error}</p>}</div>
  </section>
}
