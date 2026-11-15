import { useEffect, useRef, useState } from 'react'
import { FileUp, FileCheck2, Trash2, ShieldCheck } from 'lucide-react'
export type Nfe = { modo:string; chave:string; numero:string; serie:string; emitente:{cnpj:string;nome:string}; itens:{numero:string;codigo:string;descricao:string;ncm:string;cfop:string;quantidade:string;valor_total:string;status:string}[];total_itens:number }
export function NfePage({nota,onChange}:{nota:Nfe|null;onChange:(value:Nfe|null)=>void}) {
  const [busy,setBusy]=useState(false), [error,setError]=useState('')
  const active=useRef<AbortController|null>(null)
  const generation=useRef(0)
  useEffect(()=>()=>{generation.current++;active.current?.abort()},[])
  async function send(file:File|undefined) {
    if(!file)return
    const id=++generation.current
    active.current?.abort();const controller=new AbortController();active.current=controller
    const timer=window.setTimeout(()=>controller.abort(),30000)
    setBusy(true);setError('');onChange(null)
    try {
      const form=new FormData();form.append('file',file)
      const response=await fetch('/api/nfe/importar',{method:'POST',body:form,signal:controller.signal,cache:'no-store'})
      const data=await response.json()
      if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Não foi possível ler o XML.')
      if(id===generation.current)onChange(data)
    }catch(e){if(id===generation.current)setError(e instanceof Error&&e.name==='AbortError'?'A leitura excedeu o tempo de espera. Tente novamente.':e instanceof Error?e.message:'Falha na importação.')}
    finally{window.clearTimeout(timer);if(id===generation.current)setBusy(false)}
  }
  return <div className="module-stack">
    <div className="info-banner"><ShieldCheck size={19}/><span>XML local · Nenhum envio à SEFAZ · Nenhuma alteração no ERP</span></div>
    <section className="panel"><div className="panel-head"><div><h2>Importar NF-e</h2><p>Leia os itens de um XML e confira as informações da nota.</p></div><span className="badge">Até 5 MB</span></div>
      <label className={`upload ${busy?'is-busy':''}`} htmlFor="nfe-file"><span className="upload-icon"><FileUp size={28}/></span><strong>{busy?'Analisando XML…':'Escolher arquivo XML'}</strong><span>NF-e ou nfeProc · Arquivo XML de até 5 MB</span><span className="button primary">Selecionar arquivo</span></label>
      <input className="sr-only" id="nfe-file" aria-label="Selecionar XML NF-e" type="file" disabled={busy} accept=".xml,text/xml,application/xml" onChange={e=>{void send(e.target.files?.[0]);e.target.value=''}}/>
      {error&&<p className="error" role="alert">{error}</p>}
      <p className="muted">Leitura preliminar dos dados do arquivo. A comparação fiscal com o WinThor e a integração SEFAZ ainda não estão disponíveis.</p>
    </section>
    {nota?<section className="panel"><div className="panel-head"><div><span className="eyebrow"><FileCheck2 size={16}/> XML lido</span><h2>Nota {nota.numero} · Série {nota.serie}</h2><p>{nota.emitente.nome} · CNPJ {nota.emitente.cnpj}</p></div><button className="button quiet" onClick={()=>onChange(null)}><Trash2 size={16}/>Limpar nota</button></div>
      <div className="note-summary"><span>{nota.total_itens} itens identificados</span><span className="badge neutral">Aguardando comparação cadastral</span></div>
      <div className="table-wrap"><table aria-label="Itens da NF-e"><thead><tr><th>Código</th><th>Descrição</th><th>NCM</th><th>CFOP</th><th>Quantidade</th><th>Valor (R$)</th></tr></thead><tbody>{nota.itens.map((item,i)=><tr key={i}><td>{item.codigo}</td><td>{item.descricao}</td><td>{item.ncm}</td><td>{item.cfop}</td><td>{item.quantidade}</td><td>{item.valor_total}</td></tr>)}</tbody></table></div>
      <p className="notice">Nenhuma divergência foi confirmada. Os dados ficam somente na memória desta sessão.</p>
    </section>:<div className="empty-state"><FileCheck2 size={32}/><h2>Nenhuma nota carregada</h2><p>Selecione um XML para visualizar os itens aqui.</p></div>}
  </div>
}
