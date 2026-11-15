import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { ArrowRight, Bird, BookOpenCheck, Building2, ChevronRight, Database, FileCheck2, LayoutDashboard, LifeBuoy, LockKeyhole, Menu, PackageSearch, Power, Settings2, ShieldCheck, Truck, X, AlertTriangle } from 'lucide-react'
import './style.css'
import navigation from './data/navigation.json'
import { ConnectionManager, type Connection } from './ConnectionManager'
import { WinthorCatalog, type Health } from './WinthorCatalog'
import { NfePage, type Nfe } from './NfePage'
import { UpdatePanel } from './UpdatePanel'
import { FeatureCatalog } from './FeatureCatalog'

const icons = { 'visao-geral': LayoutDashboard, nfe: FileCheck2, produtos: PackageSearch, fornecedores: Truck, configuracoes: Settings2, validacao: BookOpenCheck, suporte: LifeBuoy }
const subtitles:Record<string,string> = {
 'visao-geral':'Seu ponto de partida para uma operação mais clara e segura.',
 nfe:'Leitura preliminar de XML local, com os dados da nota organizados em um só lugar.',
 produtos:'Encontre produtos do WinThor com filtros objetivos e consultas protegidas.',
 fornecedores:'Consulte o cadastro de fornecedores do destino selecionado.',
 configuracoes:'Uma única central para configurar, testar e selecionar suas conexões Oracle.',
 validacao:'O que está disponível, como usar e o que já foi validado.',
 suporte:'Diagnósticos avançados e manutenção da sua instalação local.'
}
function currentRoute(){const id=location.hash.slice(1);return navigation.some(n=>n.id===id)?id:'visao-geral'}
function App(){
 const [route,setRoute]=useState(currentRoute),[menu,setMenu]=useState(false)
 const [token,setToken]=useState(''),[automatic,setAutomatic]=useState(false),[checking,setChecking]=useState(true),[accessError,setAccessError]=useState(false)
 const [connection,setConnection]=useState<Connection|null>(null),[health,setHealth]=useState<Health|null>(null),[verifying,setVerifying]=useState(false),[error,setError]=useState('')
 const [nota,setNota]=useState<Nfe|null>(null),[version,setVersion]=useState('…'),[lifecycleBusy,setLifecycleBusy]=useState(false),[closed,setClosed]=useState('')
 const heading=useRef<HTMLHeadingElement>(null), generation=useRef(0), request=useRef<AbortController|null>(null)
 useEffect(()=>{const change=()=>{setRoute(currentRoute());setMenu(false)};window.addEventListener('hashchange',change);return()=>window.removeEventListener('hashchange',change)},[])
 useEffect(()=>{document.title=`${navigation.find(n=>n.id===route)?.label} · HUGINN IA`;heading.current?.focus({preventScroll:true});window.scrollTo(0,0)},[route,checking])
 useEffect(()=>{let alive=true;const controller=new AbortController()
  fetch('/api/local-session',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}',credentials:'same-origin',cache:'no-store',signal:controller.signal})
   .then(r=>{if(alive){setAutomatic(r.ok);setAccessError(!r.ok&&r.status!==404)}}).catch(e=>{if(alive&&e.name!=='AbortError')setAccessError(true)}).finally(()=>{if(alive)setChecking(false)})
  return()=>{alive=false;controller.abort()}
 },[])
 useEffect(()=>{let alive=true;fetch('/api/version',{cache:'no-store'}).then(r=>r.ok?r.json():null).then(v=>{if(alive&&v?.version)setVersion(v.version)}).catch(()=>{});return()=>{alive=false}},[])
 function choose(value:Connection|null){generation.current++;request.current?.abort();setVerifying(false);setConnection(value);setHealth(null);setError('')}
 useEffect(()=>{
  choose(null)
  if(!automatic&&token.length<32)return
  const epoch=generation.current, controller=new AbortController();let alive=true
  fetch('/api/connections/list',{method:'POST',headers:{'Content-Type':'application/json',...(automatic?{}:{Authorization:`Bearer ${token}`})},body:'{}',cache:'no-store',signal:controller.signal})
   .then(r=>r.ok?r.json():null).then(data=>{if(alive&&epoch===generation.current&&data)choose(data.active)}).catch(()=>{})
  return()=>{alive=false;controller.abort()}
 },[token,automatic])
 useEffect(()=>()=>{generation.current++;request.current?.abort()},[])
 async function verify(){
  const id=++generation.current;request.current?.abort();const controller=new AbortController();request.current=controller
  const timer=window.setTimeout(()=>controller.abort(),30000);setVerifying(true);setError('');setHealth(null)
  try{const response=await fetch('/api/winthor/health',{method:'POST',headers:{'Content-Type':'application/json',...(automatic?{}:{Authorization:`Bearer ${token}`})},body:JSON.stringify(connection?{connection_id:connection.id,connection_revision:connection.revision}:{}),signal:controller.signal,cache:'no-store'})
   const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Não foi possível verificar o destino.')
   if(id===generation.current)setHealth(data)
  }catch(e){if(id===generation.current)setError(e instanceof Error&&e.name==='AbortError'?'Tempo de verificação excedido. Verifique a disponibilidade e tente novamente.':e instanceof Error?e.message:'Falha na verificação.')}
  finally{window.clearTimeout(timer);if(id===generation.current)setVerifying(false)}
 }
 async function lifecycle(action:'local-stop'|'local-reset'){
  if(!window.confirm(action==='local-stop'?'Encerrar apenas o HUGINN? Nenhum outro serviço será alterado.':'Recriar o acesso local e encerrar o HUGINN? As conexões salvas serão preservadas. Depois abra pelo atalho.'))return
  setLifecycleBusy(true);setError('')
  try{const r=await fetch('/api/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}',credentials:'same-origin'});if(!r.ok)throw new Error('Não foi possível confirmar a operação. Tente novamente pelo acesso local autenticado.')
   setToken('');setNota(null);choose(null);setClosed(action==='local-stop'?'HUGINN encerrado. Feche esta aba; para abrir novamente use o atalho.':'Acesso será recriado ao abrir pelo atalho. Conexões preservadas.')
  }catch(e){setError(e instanceof Error?e.message:'Operação não confirmada.')}finally{setLifecycleBusy(false)}
 }
 if(checking)return <main className="boot"><Bird size={42}/><h1>HUGINN IA</h1><p>Preparando acesso local seguro…</p></main>
 if(accessError||closed)return <main className="boot"><Bird size={42}/><h1>HUGINN IA</h1><p role={accessError?'alert':'status'}>{closed||'Não foi possível confirmar o acesso Windows. Feche e reabra pelo atalho; não é necessário digitar token ou reiniciar o Windows.'}</p>{accessError&&<button className="button primary" onClick={()=>location.reload()}>Tentar acesso novamente</button>}</main>
 const title=navigation.find(n=>n.id===route)?.label
 const oracle=health?.modo==='oracle'&&health.conectado
 return <div className="shell" data-app-ready="true">
  <a className="skip-link" href="#conteudo" onClick={e=>{e.preventDefault();heading.current?.focus()}}>Ir para o conteúdo</a>
  <aside className="sidebar"><a className="brand" href="#visao-geral" aria-label="HUGINN IA · Início"><span className="brand-symbol"><Bird size={32}/></span><span>HUGINN <b>IA</b><small>INTELIGÊNCIA OPERACIONAL</small></span></a>
   <button className="mobile-menu button quiet" aria-label={menu?'Fechar navegação':'Abrir navegação'} aria-expanded={menu} aria-controls="primary-navigation" onClick={()=>setMenu(!menu)}>{menu?<X/>:<Menu/>}</button>
   <nav id="primary-navigation" aria-label="Navegação principal" className={menu?'is-open':''} onKeyDown={e=>{if(e.key==='Escape')setMenu(false)}}>
    {['workspace','management'].map(group=><React.Fragment key={group}><p className="nav-label">{group==='workspace'?'ÁREA DE TRABALHO':'GESTÃO E SUPORTE'}</p>{navigation.filter(n=>n.group===group).map(n=>{const Icon=icons[n.id as keyof typeof icons];return <a key={n.id} href={'#'+n.id} aria-current={route===n.id?'page':undefined}><Icon size={19}/><span>{n.label}</span>{route===n.id&&<ChevronRight className="nav-chevron" size={15}/>}</a>})}</React.Fragment>)}
   </nav>
   <div className="side-footer"><ShieldCheck size={18}/><div>Operação protegida<small>Local · Somente leitura</small></div></div><div className="side-version">HUGINN IA <span>{version}</span></div>
  </aside>
  <div className="workspace"><div className="topbar"><span>Workspace <ChevronRight size={14}/> <strong>{title}</strong></span><span className="local-indicator"><span/> Ambiente local</span></div>
   <main id="conteudo"><header className="page-header"><div><p className="eyebrow">HUGINN IA / OPERAÇÃO</p><h1 ref={heading} tabIndex={-1}>{title}</h1><p>{subtitles[route]}</p></div><span className="badge security"><ShieldCheck size={14}/> Somente leitura</span></header>
    <div className={`connection-bar ${connection?.environment==='PRODUCAO'?'production-bar':''}`} aria-label="Resumo da conexão"><span className="connection-icon"><Database size={20}/></span><div><strong>{connection?.name??(health?.modo==='oracle'?'Configuração local por ambiente':health?.modo==='simulado'?'Demonstração local':'Nenhuma conexão selecionada')}</strong><span>{oracle?'ORACLE — somente leitura':health?.modo==='simulado'?'SIMULAÇÃO — dados fictícios, sem Oracle':connection?'Destino selecionado · verificação pendente':'Configure o destino na Central de Conexões'}</span></div>{connection&&<span className={`badge ${connection.environment==='PRODUCAO'?'production':'test'}`}>{connection.environment==='PRODUCAO'?'PRODUÇÃO':'TESTE'}</span>}{!connection&&oracle&&<span className="badge neutral">Ambiente não classificado</span>}<a className="connection-action" href="#configuracoes">Gerenciar conexão <ArrowRight size={15}/></a></div>
    <div aria-live="polite">{verifying&&<p role="status" className="info-banner">Verificando conexão selecionada…</p>}{error&&<p role="alert" className="error">{error}</p>}</div>
    {route==='visao-geral'&&<div className="module-stack"><section className="welcome-card"><div><span className="eyebrow">CLAREZA PARA DECIDIR</span><h2>Sua operação,<br/>em perspectiva.</h2><p>Consulte cadastros e organize os dados das suas notas com segurança. O ERP permanece intacto.</p><div className="button-row"><a className="button cyan" href="#produtos">Consultar produtos <ArrowRight size={16}/></a><a className="button ghost" href="#configuracoes">Configurar conexão</a></div></div><Bird className="welcome-bird" size={170} strokeWidth={1.1}/></section>
     <section className="metrics" aria-label="Resumo operacional"><article><span className="metric-icon"><Database/></span><small>Conexão Oracle</small><strong>{oracle?'Verificada':connection?'Selecionada':'Não selecionada'}</strong><span>{oracle?'Teste pontual confirmado, sem sessão permanente':'Seleção e verificação explícitas'}</span></article><article><span className="metric-icon"><FileCheck2/></span><small>XML nesta sessão</small><strong>{nota?`${nota.total_itens} ${nota.total_itens===1?'item':'itens'}`:'Nenhuma nota'}</strong><span>{nota?`NF-e ${nota.numero} · Série ${nota.serie}`:'Importe um arquivo para começar'}</span></article><article><span className="metric-icon"><ShieldCheck/></span><small>Modo de operação</small><strong>Somente leitura</strong><span>Sem alterações no banco ou ERP</span></article></section>
     <section><div className="section-heading"><h2>Comece por aqui</h2><span>Seus módulos de trabalho</span></div><div className="work-grid">{[{id:'nfe',icon:FileCheck2,title:'Auditoria NF-e',text:'Leia o XML local e confira os itens da nota.',link:'Importar XML'},{id:'produtos',icon:PackageSearch,title:'Produtos',text:'Pesquise códigos e descrições no WinThor.',link:'Pesquisar produtos'},{id:'fornecedores',icon:Building2,title:'Fornecedores',text:'Encontre cadastros no destino selecionado.',link:'Pesquisar fornecedores'}].map(x=><a className="work-card" href={'#'+x.id} key={x.id}><x.icon size={25}/><h3>{x.title}</h3><p>{x.text}</p><span>{x.link}<ArrowRight size={16}/></span></a>)}</div></section>
     <section className="panel next-steps"><div><h2>Uma conexão, um destino claro</h2><p>Cadastre, teste e selecione o perfil em Configurações. A senha permanece protegida no Windows.</p></div><a className="button quiet" href="#validacao">Conhecer funcionalidades <ArrowRight size={16}/></a></section>
    </div>}
    {route==='nfe'&&<NfePage nota={nota} onChange={setNota}/>}
    {(route==='produtos'||route==='fornecedores')&&<WinthorCatalog key={route} kind={route} token={token} automatic={automatic} connection={connection} health={health} onVerify={()=>void verify()}/>}
    {route==='configuracoes'&&<div className="module-stack">
     <section className="panel"><div className="panel-head"><div><h2>Central de Conexões</h2><p>Este é o único lugar para gerenciar o acesso Oracle.</p></div><Database size={23}/></div>
      {!automatic&&<form className="catalog-auth" onSubmit={e=>{e.preventDefault();void verify()}}><label>Token de acesso local<input type="password" minLength={32} maxLength={512} required autoComplete="off" value={token} onChange={e=>setToken(e.target.value)}/></label><button className="button primary">Validar acesso</button><button className="button quiet" type="button" onClick={()=>{setToken('');setNota(null);choose(null)}}>Encerrar acesso</button><p className="muted">Modo de desenvolvimento/portátil. O token fica somente na memória desta página.</p></form>}
      {automatic&&<p className="info-banner"><LockKeyhole size={18}/> Acesso local Windows confirmado. Não é necessário digitar token.</p>}
      <ConnectionManager token={token} automatic={automatic} onChange={choose}/>
     </section><section className="panel"><h2>Verificar destino selecionado</h2><p>O teste é pontual e fecha a sessão Oracle. Não habilita escrita ou publicação em produção.</p><button className="button primary" disabled={verifying||(!automatic&&token.length<32)} onClick={()=>void verify()}>Verificar conexão WinThor</button>{health&&<p className={oracle?'success':'notice'} role="status">{health.mensagem}</p>}</section>
    </div>}
    {route==='suporte'&&<div className="module-stack"><div className="notice info-banner"><AlertTriangle size={18}/><span>Área avançada. Compartilhe apenas o relatório sanitizado; nunca envie senha, token, host ou dados de cliente.</span></div><WinthorCatalog kind="diagnostico" token={token} automatic={automatic} connection={connection} health={health} onVerify={()=>void verify()}/><UpdatePanel/>
      <section className="panel"><h2>Manutenção local</h2><p>As ações abaixo afetam somente esta instalação. Conexões salvas permanecem protegidas.</p>{automatic?<div className="button-row"><button className="button quiet" disabled={lifecycleBusy} onClick={()=>void lifecycle('local-stop')}><Power size={16}/>Encerrar HUGINN</button><button className="button quiet" disabled={lifecycleBusy} onClick={()=>void lifecycle('local-reset')}>Recriar acesso local</button></div>:<p className="muted">Use o inicializador da sua instalação para encerrar o aplicativo.</p>}</section>
    </div>}
    {route==='validacao'&&<FeatureCatalog/>}
    <footer><span>HUGINN IA · Inteligência operacional</span><span>Leitura protegida. Decisões com contexto.</span></footer>
   </main>
  </div>
 </div>
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>)
