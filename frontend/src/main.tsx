import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Activity, FileUp, ShieldCheck, Database, Bird, AlertTriangle } from 'lucide-react'
import './style.css'
import { WinthorCatalog } from './WinthorCatalog'
import { OracleConnection } from './OracleConnection'
import { UpdatePanel } from './UpdatePanel'

type Item = { numero:string; codigo:string; descricao:string; ncm:string; cfop:string; quantidade:string; valor_total:string; status:string }
type Nfe = { modo:string; chave:string; numero:string; serie:string; emitente:{cnpj:string;nome:string}; itens:Item[]; total_itens:number }
function App(){
  const [token,setToken] = useState('')
  const [automatic,setAutomatic] = useState(false)
  const [checking,setChecking] = useState(true)
  const [accessError,setAccessError] = useState(false)
  useEffect(() => {
    let alive = true
    fetch('/api/local-session', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}', credentials: 'same-origin', cache: 'no-store' })
      .then(r => { if (alive) { setAutomatic(r.ok); setAccessError(!r.ok && r.status !== 404) } }).catch(() => { if (alive) setAccessError(true) }).finally(() => { if (alive) setChecking(false) })
    return () => { alive = false }
  }, [])
  const [nota,setNota] = useState<Nfe|null>(null)
  const [erro,setErro] = useState('')
  const [busy,setBusy] = useState(false)
  async function enviar(e:React.ChangeEvent<HTMLInputElement>){
    const f=e.target.files?.[0]; if(!f)return
    setBusy(true);setErro('');setNota(null)
    try{
      const fd=new FormData();fd.append('file',f)
      const r=await fetch('/api/nfe/importar',{method:'POST',body:fd})
      const data=await r.json()
      if(!r.ok)throw new Error(data.detail||'Erro ao importar XML')
      setNota(data)
    }catch(ex){setErro(ex instanceof Error?ex.message:'Falha na importação')}
    finally{setBusy(false);e.target.value=''}
  }
  if (checking) return <main><h1>HUGINN IA</h1><p>Preparando acesso local seguro…</p></main>
  if (accessError) return <main><h1>HUGINN IA</h1><p role="alert">Não foi possível confirmar o acesso Windows. Feche e reabra pelo atalho; não é necessário digitar token ou reiniciar o Windows.</p><button onClick={() => location.reload()}>Tentar acesso novamente</button></main>
  return <div className="shell">
    <aside><div className="brand"><Bird size={35}/><span>HUGINN <b>IA</b></span></div><div className="side-title">PLATAFORMA INTELIGENTE</div><nav><div className="active"><Activity size={19}/> Visão geral</div><div><FileUp size={19}/> Entrada NF-e</div><div><Database size={19}/> <a href="#winthor">Consultas WinThor</a></div><div><ShieldCheck size={19}/> Auditoria (em breve)</div></nav><div className="side-footer">MVP · Operação local e somente leitura</div></aside>
    <main><header><div><div className="eyebrow">INTELIGÊNCIA OPERACIONAL</div><h1>HUGINN IA · Consulta WinThor</h1><p>Produtos e fornecedores em somente leitura, na sua operação local.</p></div><span className="status">● AMBIENTE LOCAL</span></header>
    <section className="metrics"><article><small>Cadastros WinThor</small><strong>Produtos e fornecedores</strong><span>Consulte o status autenticado abaixo</span></article><article><small>Serviço SEFAZ</small><strong>Não conectado</strong><span>Integração futura</span></article><article><small>XML carregado</small><strong>{nota?'1 nota':'Nenhum'}</strong><span>{nota?nota.total_itens+' itens identificados':'Aguardando importação'}</span></article></section>
    <WinthorCatalog token={token} onTokenChange={setToken} automatic={automatic}/>
    <section className="panel"><div className="panel-head"><div><h2>Importar NF-e</h2><p>Selecione um XML de NF-e para analisar seus produtos.</p></div><FileUp color="#3dd8ff"/></div><label className="upload"><FileUp size={30}/><strong>{busy?'Analisando...':'Escolher arquivo XML'}</strong><span>Arquivo de até 5 MB · Sem envio à SEFAZ</span><input disabled={busy} type="file" accept=".xml,text/xml,application/xml" onChange={enviar}/></label>{erro&&<p className="error"><AlertTriangle size={16}/>{erro}</p>}</section>
    {nota&&<section className="panel"><div className="panel-head"><div><h2>Nota {nota.numero} · Série {nota.serie}</h2><p>{nota.emitente.nome} · CNPJ {nota.emitente.cnpj}</p></div><span className="pill">{nota.total_itens} itens</span></div><div className="table-wrap"><table><thead><tr><th>Código</th><th>Descrição</th><th>NCM</th><th>CFOP</th><th>Qtd.</th><th>Valor (R$)</th></tr></thead><tbody>{nota.itens.map((i,j)=><tr key={j}><td>{i.codigo}</td><td>{i.descricao}</td><td>{i.ncm}</td><td>{i.cfop}</td><td>{i.quantidade}</td><td>{i.valor_total}</td></tr>)}</tbody></table></div><p className="notice">Produtos aguardam comparação com cadastro WinThor. Nenhuma divergência foi confirmada.</p></section>}
    <OracleConnection token={token} automatic={automatic}/>
    <UpdatePanel/>
    {automatic && <button className="oracle-test" onClick={() => { if (window.confirm('Encerrar apenas o HUGINN? Nenhum outro serviço será alterado.')) void fetch('/api/local-stop', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}', credentials: 'same-origin' }).then(r => { if (r.ok) document.body.textContent = 'HUGINN encerrado. Feche esta aba; para abrir novamente use o atalho.' }) }}>Encerrar HUGINN</button>}
    {automatic && <button className="oracle-test" onClick={() => { if (window.confirm('Recriar o acesso local e encerrar o HUGINN? As conexões salvas serão preservadas. Depois abra pelo atalho.')) void fetch('/api/local-reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}', credentials: 'same-origin' }).then(r => { if (r.ok) document.body.textContent = 'Acesso será recriado ao abrir pelo atalho. Conexões preservadas.' }) }}>Recriar acesso local</button>}
    <footer>HUGINN IA · Análise preliminar · Nenhuma alteração no ERP</footer></main>
  </div>
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>)
