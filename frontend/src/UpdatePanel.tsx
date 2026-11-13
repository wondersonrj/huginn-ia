import { useEffect, useRef, useState } from 'react'

type UpdateState = { version:string; channel:string; enabled:boolean; available:string|null; notes:string; status:string; restart_required:boolean }
export function UpdatePanel() {
  const [state, setState] = useState<UpdateState|null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const previousVersion = useRef<string|null>(null)
  useEffect(() => {
    let active = true
    const refresh = async () => {
      try {
        const r = await fetch('/api/updates/status')
        if (r.ok && active) {
          const next: UpdateState = await r.json()
          if (previousVersion.current && previousVersion.current !== next.version) {
            window.location.reload() // Drop old assets and all in-memory Oracle credentials.
            return
          }
          previousVersion.current = next.version
          setState(next)
        }
      } catch { /* Expected while restarting; keep the last status visible. */ }
    }
    void refresh()
    const timer = window.setInterval(refresh, 2000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])
  async function request(action:'check'|'apply') {
    if (action === 'apply' && !window.confirm('A atualização reiniciará o HUGINN IA e limpará a sessão atual. Continuar?')) return
    setBusy(true); setError('')
    try {
      const r = await fetch('/api/updates/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
      const data = await r.json()
      if (!r.ok) throw new Error(data.detail || 'Solicitação recusada')
    } catch (e) { setError(e instanceof Error ? e.message : 'Falha na solicitação') }
    finally { setBusy(false) }
  }
  return <section className="panel" id="updates"><h2>Versão e atualizações</h2>
    <p>Versão atual: {state?.version ?? '…'} · Canal: {state?.channel ?? '…'}</p>
    <p role="status">{state?.status ?? 'Consultando versão local…'}</p>
    {state?.available && <><p>Versão disponível: {state.available}</p><p>{state.notes}</p></>}
    {state?.restart_required && <p className="notice">Reinicialização necessária. Confirme também na janela do Windows.</p>}
    {!state?.enabled && <p className="notice">Atualização desativada. Requer bootstrap aprovado, chave de distribuição e validação em Windows.</p>}
    <button className="oracle-test" disabled={!state?.enabled || busy} onClick={()=>void request('check')}>Verificar atualização</button>
    <button className="oracle-test" disabled={!state?.enabled || !state.available || busy} onClick={()=>void request('apply')}>Atualizar agora</button>
    {error && <p role="alert" className="error">{error}</p>}
  </section>
}
