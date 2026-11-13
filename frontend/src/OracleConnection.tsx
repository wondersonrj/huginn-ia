import { useState, type FormEvent } from 'react'

export function OracleConnection() {
  const [host, setHost] = useState('')
  const [port, setPort] = useState('1521')
  const [service, setService] = useState('')
  const [user, setUser] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null)

  async function testConnection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setResult(null)
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort(), 20000)
    try {
      const response = await fetch('/api/oracle/testar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ host: host.trim(), port: Number(port), service: service.trim(), user: user.trim(), password }),
        signal: controller.signal,
      })
      const data = await response.json()
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível testar a conexão.')
      if (!data.conectado) throw new Error('Oracle não confirmou o teste de leitura.')
      setResult({ ok: true, text: 'Conexão confirmada em somente leitura. Nenhum dado do WinThor foi alterado.' })
    } catch (error) {
      setResult({ ok: false, text: error instanceof Error && error.name === 'AbortError'
        ? 'Tempo de teste excedido. Verifique a rede e tente novamente.'
        : error instanceof Error ? error.message : 'Falha no teste de conexão.' })
    } finally {
      window.clearTimeout(timer)
      setPassword('')
      setBusy(false)
    }
  }

  return <section className="panel" id="oracle">
    <div className="panel-head"><div><h2>Conexão Oracle direta</h2>
      <p>Teste local com uma conta autorizada pelo DBA e com privilégios somente de leitura.</p></div></div>
    <p className="notice">O teste consulta apenas DUAL. Não consulta nem grava tabelas do WinThor. Os dados não são salvos e a senha é limpa após cada tentativa.</p>
    <form onSubmit={testConnection} onChange={() => setResult(null)}>
      <fieldset disabled={busy} className="oracle-fields">
        <label>Host ou IP<input required maxLength={253} value={host} onChange={e => setHost(e.target.value)} placeholder="servidor.interno" autoComplete="off" /></label>
        <label>Porta<input required type="number" min={1} max={65535} value={port} onChange={e => setPort(e.target.value)} /></label>
        <label>Service Name<input required maxLength={255} value={service} onChange={e => setService(e.target.value)} autoComplete="off" /></label>
        <label>Usuário de leitura<input required maxLength={128} value={user} onChange={e => setUser(e.target.value)} autoComplete="off" /></label>
        <label>Senha<input required type="password" maxLength={1024} value={password} onChange={e => setPassword(e.target.value)} autoComplete="off" /></label>
      </fieldset>
      <button className="oracle-test" disabled={busy} type="submit">{busy ? 'Testando conexão…' : 'Testar conexão Oracle'}</button>
      <div aria-live="polite">{result && <p role={result.ok ? 'status' : 'alert'} className={result.ok ? 'success' : 'error'}>{result.text}</p>}</div>
    </form>
  </section>
}
