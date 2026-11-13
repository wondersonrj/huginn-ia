import { useState, type FormEvent } from 'react'

export function OracleConnection() {
  const [host, setHost] = useState('')
  const [port, setPort] = useState('1521')
  const [service, setService] = useState('')
  const [user, setUser] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [schema, setSchema] = useState<{ tabelas: {nome:string; proprietario:string|null; visivel:boolean; colunas:{coluna:string;tipo:string}[]}[] } | null>(null)
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null)

  async function testConnection(diagnostic = false) {
    setBusy(true)
    setResult(null)
    setSchema(null)
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort(), 20000)
    try {
      const response = await fetch(diagnostic ? '/api/oracle/diagnostico' : '/api/oracle/testar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ host: host.trim(), port: Number(port), service: service.trim(), user: user.trim(), password }),
        signal: controller.signal,
      })
      const data = await response.json()
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível testar a conexão.')
      if (diagnostic) {
        setSchema(data)
        setResult({ok:true,text:'Diagnóstico de metadados concluído. Nenhum registro comercial foi consultado.'})
      } else {
        if (!data.conectado) throw new Error('Oracle não confirmou o teste de leitura.')
        setResult({ ok: true, text: 'Conexão confirmada em somente leitura. Nenhum dado do WinThor foi alterado.' })
      }
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
    <p className="notice">O teste de conexão consulta apenas DUAL; o diagnóstico consulta somente metadados das tabelas autorizadas. Nenhum registro comercial é lido ou alterado. Os dados não são salvos e a senha é limpa após cada tentativa.</p>
    <form onSubmit={(e: FormEvent<HTMLFormElement>) => { e.preventDefault(); const diagnostic = (e.nativeEvent as SubmitEvent).submitter?.getAttribute("value") === "diagnostic"; void testConnection(diagnostic) }} onChange={() => { setResult(null); setSchema(null) }}>
      <fieldset disabled={busy} className="oracle-fields">
        <label>Host ou IP<input required maxLength={253} value={host} onChange={e => setHost(e.target.value)} placeholder="servidor.interno" autoComplete="off" /></label>
        <label>Porta<input required type="number" min={1} max={65535} value={port} onChange={e => setPort(e.target.value)} /></label>
        <label>Service Name<input required maxLength={255} value={service} onChange={e => setService(e.target.value)} autoComplete="off" /></label>
        <label>Usuário de leitura<input required maxLength={128} value={user} onChange={e => setUser(e.target.value)} autoComplete="off" /></label>
        <label>Senha<input required type="password" maxLength={1024} value={password} onChange={e => setPassword(e.target.value)} autoComplete="off" /></label>
      </fieldset>
      <button className="oracle-test" disabled={busy} type="submit" value="connection">{busy ? 'Aguarde…' : 'Testar conexão Oracle'}</button>
      <button className="oracle-test" disabled={busy} type="submit" value="diagnostic">Diagnosticar tabelas WinThor</button>
      <div aria-live="polite">{result && <p role={result.ok ? 'status' : 'alert'} className={result.ok ? 'success' : 'error'}>{result.text}</p>}</div>
    </form>
    {schema && <div className="panel"><h3>Estrutura identificada (somente metadados)</h3><p>Uma tabela não visível pode não existir ou não estar acessível ao usuário. Proprietários são mostrados separadamente; sinônimos não são resolvidos. Nenhum dado comercial foi lido.</p>{schema.tabelas.map(t=><details key={`${t.proprietario ?? ""}.${t.nome}`}><summary>{t.proprietario ? `${t.proprietario}.${t.nome}` : t.nome} — {t.visivel ? `${t.colunas.length} colunas visíveis` : 'não visível'}</summary><div className="table-wrap"><table><thead><tr><th>Coluna</th><th>Tipo</th></tr></thead><tbody>{t.colunas.map(col=><tr key={col.coluna}><td>{col.coluna}</td><td>{col.tipo}</td></tr>)}</tbody></table></div></details>)}</div>}
  </section>
}
