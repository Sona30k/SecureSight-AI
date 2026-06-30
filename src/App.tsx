import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { Routes, Route, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Activity, AlertTriangle, ArrowRight, Banknote, Bell, Bot, Building2, Check,
  ChevronDown, CircleUserRound, Clock3, FileText, Fingerprint, Globe2, Grid2X2,
  Headphones, Landmark, LockKeyhole, Map, Menu, MessageSquareText, Network,
  PhoneCall, Radar, ScanFace, Search, Settings, Shield, ShieldCheck, Siren,
  SlidersHorizontal, Sparkles, UploadCloud, UsersRound, WalletCards, X, Zap
} from 'lucide-react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie,
  PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis
} from 'recharts'
import { Protected, useAuth } from './auth'
import { errorMessage, Report, services, websocketUrl } from './lib/api'
import { useApi } from './hooks/useApi'

const trend = [
  { t: '00:00', threats: 28, resolved: 20 }, { t: '04:00', threats: 36, resolved: 28 },
  { t: '08:00', threats: 31, resolved: 24 }, { t: '12:00', threats: 54, resolved: 43 },
  { t: '16:00', threats: 47, resolved: 39 }, { t: '20:00', threats: 67, resolved: 54 },
  { t: '24:00', threats: 58, resolved: 51 }
]
const districts = [
  { name: 'Central', value: 82 }, { name: 'North', value: 61 }, { name: 'East', value: 46 },
  { name: 'West', value: 35 }, { name: 'South', value: 58 }
]
const nav = [
  ['Overview', Grid2X2, '/dashboard'], ['Digital Arrest', PhoneCall, '/digital-arrest'],
  ['Counterfeit Detection', Banknote, '/counterfeit'], ['Fraud Network', Network, '/network'],
  ['Crime Map', Map, '/crime-map'], ['Citizen Reports', FileText, '/reports'],
  ['AI Assistant', Bot, '/assistant'], ['Analytics', Activity, '/analytics']
] as const

function Logo({compact=false}:{compact?:boolean}) {
  return <div className="logo"><div className="logo-mark"><ShieldCheck size={22}/></div>{!compact && <div><b>Sentinel<span>X</span></b><small>DIGITAL PUBLIC SAFETY</small></div>}</div>
}

function Landing() {
  const navigate = useNavigate()
  const features = [
    [PhoneCall, 'Digital Arrest Detection', 'Identify coercion patterns and spoofed calls in real time.'],
    [Banknote, 'Counterfeit Intelligence', 'Computer vision that inspects 14 currency security features.'],
    [Network, 'Fraud Network Intelligence', 'Connect devices, accounts and identities across reports.'],
    [Map, 'Predictive Crime Heatmaps', 'Anticipate emerging hotspots with responsible AI models.'],
    [Bot, 'AI Citizen Assistant', 'A multilingual, always-on shield for every citizen.']
  ] as const
  return <div className="landing">
    <div className="cyber-bg"><i/><i/><i/></div>
    <header className="landing-nav"><Logo/><div className="landing-links"><a href="#capabilities">Capabilities</a><a href="#process">How it works</a><a href="#impact">Impact</a></div><button className="text-btn" onClick={()=>navigate('/login')}>Agency sign in <ArrowRight size={16}/></button></header>
    <main>
      <section className="hero">
        <motion.div initial={{opacity:0,y:20}} animate={{opacity:1,y:0}} transition={{duration:.7}}>
          <div className="eyebrow"><span/> NATIONAL INTELLIGENCE GRID • ONLINE</div>
          <h1>Intelligence that<br/><em>protects everyone.</em></h1>
          <p>SentinelX unifies AI, public safety data and real-time signals to detect fraud earlier, connect threats faster, and help agencies act with confidence.</p>
          <div className="hero-actions"><button className="primary" onClick={()=>navigate('/dashboard')}><Radar size={18}/> Launch command center <ArrowRight size={17}/></button><button className="secondary" onClick={()=>navigate('/assistant')}><Siren size={18}/> Report fraud</button></div>
          <div className="trust"><div className="avatars"><span>IN</span><span><Landmark size={14}/></span><span><Shield size={14}/></span></div><p><b>Trusted response infrastructure</b><br/>Built for citizens, banks and law enforcement</p></div>
        </motion.div>
        <motion.div className="hero-visual" initial={{opacity:0,scale:.92}} animate={{opacity:1,scale:1}} transition={{delay:.2,duration:.8}}>
          <div className="radar-rings"><div/><div/><div/><span className="radar-core"><Fingerprint size={44}/></span><b className="blip b1"/><b className="blip b2"/><b className="blip b3"/></div>
          <div className="float-card fc1"><span className="alert-icon"><AlertTriangle size={16}/></span><div><small>HIGH-RISK CALL</small><b>Coercion pattern found</b></div><em>94%</em></div>
          <div className="float-card fc2"><span className="safe-icon"><ShieldCheck size={16}/></span><div><small>CITIZEN PROTECTED</small><b>₹2.4L transfer stopped</b></div></div>
          <div className="system-status"><i/><span>AI RESPONSE ENGINE</span><b>Active</b></div>
        </motion.div>
      </section>
      <section className="stats" id="impact">
        {[['18.4K','Fraud cases detected','+12.4%'],['₹284Cr','Citizen funds protected','+8.7%'],['96.8%','Threat detection accuracy','verified'],['2.1s','Average response time','real-time']].map((s,i)=><div key={s[1]}><small>{s[1]}</small><b>{s[0]}</b><em className={i===3?'cyan':''}>{s[2]}</em></div>)}
      </section>
      <section className="capabilities" id="capabilities"><div className="section-head"><div><span className="kicker">ONE INTELLIGENCE LAYER</span><h2>Every signal. Connected.</h2></div><p>From the first suspicious call to an actionable case file, SentinelX turns fragmented data into shared understanding.</p></div><div className="feature-grid">{features.map(([Icon,title,desc],i)=><motion.article whileHover={{y:-5}} key={title} className={i===0?'feature featured':'feature'}><div className="feature-icon"><Icon/></div><small>0{i+1}</small><h3>{title}</h3><p>{desc}</p><span>Explore capability <ArrowRight size={15}/></span></motion.article>)}</div></section>
      <section className="process" id="process"><span className="kicker">AUTONOMOUS RESPONSE PIPELINE</span><h2>From signal to action in seconds.</h2><div className="timeline">{['Threat detected','AI analysis','Priority alert','Agency dashboard','Action taken'].map((x,i)=><div key={x}><span>{i===4?<Check/>:i+1}</span><b>{x}</b><small>{['Multi-channel intake','Cross-signal reasoning','Risk-based routing','Unified intelligence','Verified resolution'][i]}</small></div>)}</div></section>
    </main>
    <footer><Logo/><p>Ministry-grade digital infrastructure for a safer, more resilient society.</p><div>Privacy by design <span>•</span> Responsible AI <span>•</span> © 2026 SentinelX</div></footer>
  </div>
}

function Sidebar({open,onClose}:{open:boolean,onClose:()=>void}) {
 const {user,logout}=useAuth()
 const citizenPages=new Set(['/dashboard','/reports','/assistant','/settings'])
 const visible=user?.role==='citizen'?nav.filter(([, ,path])=>citizenPages.has(path)):nav
 const initials=(user?.full_name||'Sentinel User').split(' ').map(x=>x[0]).slice(0,2).join('').toUpperCase()
 return <aside className={`sidebar ${open?'open':''}`}><div className="side-top"><Logo/><button className="mobile-x" onClick={onClose} aria-label="Close navigation"><X/></button></div><div className="agency"><span><Building2/></span><div><small>OPERATING AS</small><b>{user?.role.replace('_',' ')}</b></div><ChevronDown/></div><nav><small>COMMAND CENTER</small>{visible.map(([label,Icon,path])=><NavLink onClick={onClose} key={label} to={path}><Icon/>{label}</NavLink>)}<small>SYSTEM</small><NavLink onClick={onClose} to="/settings"><Settings/>Settings</NavLink></nav><div className="side-card"><div><Sparkles/> Sentinel AI</div><p>Ask about live incidents, patterns, or case intelligence.</p><NavLink to="/assistant">Open assistant <ArrowRight/></NavLink></div><div className="operator"><span>{initials}</span><div><b>{user?.full_name}</b><small>{user?.role.replace('_',' ')}</small></div><button onClick={()=>void logout()} title="Sign out" aria-label="Sign out"><LockKeyhole/></button></div></aside>
}

function Topbar({toggle}:{toggle:()=>void}) {
 return <header className="topbar"><button className="menu-btn" onClick={toggle} aria-label="Open navigation"><Menu/></button><div className="global-search"><Search/><input aria-label="Global search" placeholder="Search cases, entities, phone numbers..."/><kbd>⌘ K</kbd></div><div className="top-actions"><div className="live"><i/> System live</div><button aria-label="Notifications"><Bell/><span/></button><button aria-label="Support"><Headphones/></button></div></header>
}

function Shell({children,title,subtitle}:{children:React.ReactNode,title:string,subtitle:string}) {
 const [open,setOpen]=useState(false)
 return <div className="shell"><Sidebar open={open} onClose={()=>setOpen(false)}/><div className="main"><Topbar toggle={()=>setOpen(true)}/><div className="page"><div className="page-title"><div><div className="breadcrumb">COMMAND CENTER <span>/</span> LIVE OVERVIEW</div><h1>{title}</h1><p>{subtitle}</p></div><div className="date-pill"><Clock3/> Live • Updated 4 sec ago <ChevronDown/></div></div>{children}</div></div><button className="ai-fab"><Sparkles/><span>Ask Sentinel</span></button></div>
}

function StatCard({label,value,delta,Icon,tone}:{label:string,value:string,delta:string,Icon:any,tone:string}) {
 return <motion.article whileHover={{y:-3}} className="stat-card"><div className={`stat-icon ${tone}`}><Icon/></div><div className="stat-label">{label}<span>•••</span></div><b>{value}</b><div className="stat-foot"><em className={delta.includes('-')?'down':''}>{delta}</em><span>vs yesterday</span><div className="mini-bars">{[3,5,4,7,6,9,8].map((n,i)=><i key={i} style={{height:n*2.2}}/>)}</div></div></motion.article>
}

function LoadingPanel({label='Loading intelligence…'}:{label?:string}){return <div className="panel loading-panel"><span/><span/><span/><p>{label}</p></div>}
function ErrorPanel({message,retry}:{message:string;retry:()=>void}){return <div className="panel error-panel"><AlertTriangle/><div><b>Unable to load live intelligence</b><p>{message}</p></div><button onClick={retry}>Retry</button></div>}

function Dashboard() {
 const {user}=useAuth()
 const {data,loading,error,retry}=useApi(()=>services.analytics(),[])
 useEffect(()=>{if(!data)return;const socket=new WebSocket(websocketUrl('dashboard'));socket.onmessage=()=>void retry();return()=>socket.close()},[data,retry])
 if(loading&&!data)return <Shell title="Command center" subtitle="Connecting to the SentinelX intelligence network."><LoadingPanel/></Shell>
 if(error&&!data)return <Shell title="Command center" subtitle="Live operational intelligence."><ErrorPanel message={error} retry={retry}/></Shell>
 const d=data!
 const liveTrend=d.monthly_trends.length?d.monthly_trends.slice(-7).map(x=>({t:new Date(x.date).toLocaleDateString('en',{weekday:'short'}),threats:x.count,resolved:Math.round(x.count*.84)})):trend
 return <Shell title={`Good morning, ${user?.full_name.split(' ')[0]}.`} subtitle="Here’s what’s happening across the network right now.">
   {d.high_risk_calls>0&&<div className="alert-banner"><div className="pulse-alert"><AlertTriangle/></div><div><b>{d.high_risk_calls} high-risk call{d.high_risk_calls===1?'':'s'} detected</b><p>SentinelX recommends immediate review by the response team.</p></div><span>High priority</span><button onClick={()=>location.assign('/digital-arrest')}>Open investigation <ArrowRight/></button></div>}
   <div className="stat-grid"><StatCard label="Active investigations" value={String(d.active_investigations)} delta="Live" Icon={Radar} tone="blue"/><StatCard label="Today's fraud cases" value={String(d.today_frauds)} delta="Live" Icon={Siren} tone="red"/><StatCard label="Counterfeit alerts" value={String(d.counterfeit_detected)} delta="Verified" Icon={Banknote} tone="green"/><StatCard label="High-risk calls" value={String(d.high_risk_calls)} delta="AI scored" Icon={PhoneCall} tone="purple"/><StatCard label="Citizens protected" value={String(d.protected_citizens)} delta="Resolved" Icon={UsersRound} tone="cyan"/></div>
   <div className="dash-grid">
    <article className="panel threat-chart"><div className="panel-head"><div><h3>Threat intelligence</h3><p>Detected vs resolved • Last 30 days</p></div></div><div className="chart-legend"><span><i className="c-blue"/> Detected</span><span><i className="c-cyan"/> Estimated resolved</span><b>₹{d.money_saved.toLocaleString('en-IN')} <small>Money protected</small></b></div><ResponsiveContainer width="100%" height={230}><AreaChart data={liveTrend}><defs><linearGradient id="bluefill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#3976ff" stopOpacity=".32"/><stop offset="1" stopColor="#3976ff" stopOpacity="0"/></linearGradient></defs><CartesianGrid stroke="#1a2940" vertical={false}/><XAxis dataKey="t" stroke="#63708a" tickLine={false} axisLine={false}/><YAxis stroke="#63708a" tickLine={false} axisLine={false}/><Tooltip contentStyle={{background:'#101b2e',border:'1px solid #263650',borderRadius:12}}/><Area dataKey="threats" stroke="#3976ff" strokeWidth={2} fill="url(#bluefill)"/><Line dataKey="resolved" stroke="#19c6d4" strokeWidth={2}/></AreaChart></ResponsiveContainer></article>
    <article className="panel risk-panel"><div className="panel-head"><div><h3>Risk distribution</h3><p>Live report classification</p></div></div>{Object.entries(d.risk_distribution).map(([label,value])=>{const total=Object.values(d.risk_distribution).reduce((a,b)=>a+b,0)||1;const pct=Math.round(value/total*100);return <div className="risk-row" key={label}><span>{label[0].toUpperCase()+label.slice(1)} <b>{value}</b></span><i><em style={{width:`${pct}%`}}/></i></div>})}</article>
    <article className="panel district-panel"><div className="panel-head"><div><h3>Alerts by district</h3><p>Ranked live incidents</p></div><button onClick={()=>location.assign('/crime-map')}>View map <ArrowRight/></button></div><ResponsiveContainer width="100%" height={205}><BarChart data={d.district_rankings.map(x=>({name:x.district,value:x.incidents}))} layout="vertical"><XAxis type="number" hide/><YAxis dataKey="name" type="category" stroke="#9aa6bc" width={82} axisLine={false} tickLine={false}/><Tooltip cursor={{fill:'#142136'}} contentStyle={{background:'#101b2e',border:'1px solid #263650',borderRadius:12}}/><Bar dataKey="value" radius={[0,6,6,0]} fill="#3776f6" barSize={13}/></BarChart></ResponsiveContainer></article>
    <ActivityPanel reports={d.recent_reports}/>
   </div>
 </Shell>
}

function ActivityPanel({reports}:{reports:Report[]}){
 return <article className="panel activity-panel"><div className="panel-head"><div><h3>Live activity</h3><p>Recent verified reports</p></div><button onClick={()=>location.assign('/reports')}>View all</button></div><div className="activity-list">{reports.length?reports.map((item,i)=><div className="activity-item" key={item.id}><span className={`activity-icon ${item.risk_score>=75?'red':'blue'}`}><FileText/></span><div><b>{item.title}</b><small>{item.category.replace('_',' ')} • {item.status}</small></div><time>{new Date(item.created_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</time></div>):<div className="empty-inline">No reports yet. New activity will appear here.</div>}</div></article>
}

const genericData = [{n:'Mon',v:44},{n:'Tue',v:57},{n:'Wed',v:48},{n:'Thu',v:71},{n:'Fri',v:63},{n:'Sat',v:82},{n:'Sun',v:76}]

function DigitalArrest(){
 const [caller,setCaller]=useState('+919999900000')
 const [transcript,setTranscript]=useState('I am calling from CBI. Your Aadhaar is linked to money laundering. Do not disconnect. Transfer immediately to the verification account.')
 const [result,setResult]=useState<any>(null);const [loading,setLoading]=useState(false);const [error,setError]=useState('')
 const analyze=async(e:FormEvent)=>{e.preventDefault();setLoading(true);setError('');try{setResult(await services.scam({caller_number:caller,transcript,duration:267,video_call:true,previous_reports:2,spoof_detected:true}))}catch(err){setError(errorMessage(err))}finally{setLoading(false)}}
 const probability=result?Math.round((result.details?.scam_probability||result.scam_probability||0)*100):0
 return <Shell title="Digital Arrest Detection" subtitle="Live call analysis and coercion pattern detection."><form onSubmit={analyze} className="call-grid"><article className="panel incoming"><div className="incoming-head"><i/><span>CALL ANALYSIS</span><small>SECURE</small></div><div className="caller"><div><PhoneCall/></div><small>CALLER NUMBER</small><input aria-label="Caller number" value={caller} onChange={e=>setCaller(e.target.value)}/><p>Caller context is evaluated with the transcript.</p></div><div className="call-actions"><button disabled={loading} type="submit"><Radar/> {loading?'Analyzing…':'Analyze call'}</button></div></article><article className="panel score-card"><span>SCAM PROBABILITY</span><div className="score-ring"><b>{result?`${probability}%`:'—'}</b><small>{result?.prediction||'AWAITING INPUT'}</small></div><p>{result?.explanation?.[0]||'Submit the call transcript for explainable risk scoring.'}</p></article><article className="panel recommendation"><div><Sparkles/> AI RECOMMENDATION</div><h3>{result?(result.risk_score>=75?'Block and escalate immediately':'Verify independently'):'No analysis yet'}</h3><p>{error||result?.explanation?.join(' • ')||'SentinelX combines spoofing, scam-language, duration and report history.'}</p><div className="chips">{(result?.details?.detected_keywords||[]).map((x:string)=><span key={x}>{x}</span>)}</div></article></form><div className="panel transcript"><div className="panel-head"><div><h3>Call transcript</h3><p>Text or Whisper output</p></div></div><textarea aria-label="Call transcript" value={transcript} onChange={e=>setTranscript(e.target.value)}/></div></Shell>
}

function Counterfeit(){
 const input=useRef<HTMLInputElement>(null);const [preview,setPreview]=useState('');const [result,setResult]=useState<any>(null);const [loading,setLoading]=useState(false);const [error,setError]=useState('')
 const upload=async(file?:File)=>{if(!file)return;setPreview(URL.createObjectURL(file));setLoading(true);setError('');try{setResult(await services.currency(file))}catch(err){setError(errorMessage(err))}finally{setLoading(false)}}
 const details=result?.details||{}
 return <Shell title="Counterfeit Detection" subtitle="AI-powered currency authentication with forensic-grade precision."><div className="counter-grid"><article onClick={()=>input.current?.click()} className={`upload-zone ${result?'uploaded':''}`}><input ref={input} hidden type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>void upload(e.target.files?.[0])}/>{preview?<img className="uploaded-note" src={preview} alt="Uploaded currency note preview"/>:<div className="upload-icon"><UploadCloud/></div>}<h3>{loading?'Analyzing security features…':result?`${result.prediction} note detected`:'Drop a currency image here'}</h3><p>{error || (result?`${result.confidence}% confidence`:'Click to browse • verified JPG, PNG or WebP up to 10 MB')}</p><button type="button">Choose image</button></article><article className="panel inspection"><div className="panel-head"><div><h3>Feature inspection</h3><p>Computer vision security checks</p></div>{result&&<span className={result.prediction==='Real'?'verified':'tag-risk'}>{result.prediction.toUpperCase()}</span>}</div>{[['Security thread',details.security_thread],['Watermark',details.watermark],['Serial number',details.serial_valid]].map(([x,ok]:any)=><div className="inspect-row" key={x}><span>{ok?<Check/>:<X/>} {x}</span><i><em style={{width:ok?'100%':'12%'}}/></i><b>{ok?'PASS':'FAIL'}</b></div>)}{!result&&<div className="empty-inline">Upload a note to begin forensic inspection.</div>}</article></div></Shell>
}

function NetworkPage(){
 const {data,loading,error,retry}=useApi<any>(()=>services.graph(),[])
 const [selected,setSelected]=useState<any>(null)
 const nodes=useMemo(()=>{const source=(data?.nodes||[]).slice(0,28);return source.map((node:any,i:number)=>({...node,x:400+Math.cos(i/source.length*Math.PI*2)*(110+(i%3)*70),y:230+Math.sin(i/source.length*Math.PI*2)*(90+(i%3)*45)}))},[data])
 const byId=new globalThis.Map(nodes.map((n:any)=>[n.id,n]))
 if(loading)return <Shell title="Fraud Network Intelligence" subtitle="Analyzing cross-entity relationships."><LoadingPanel/></Shell>
 if(error)return <Shell title="Fraud Network Intelligence" subtitle="Explore hidden relationships."><ErrorPanel message={error} retry={retry}/></Shell>
 return <Shell title="Fraud Network Intelligence" subtitle="Explore hidden relationships across cases, entities and transactions."><div className="network-wrap"><article className="panel graph"><div className="graph-controls"><span><Network/> {data?.statistics?.nodes||0} nodes • {data?.statistics?.clusters||0} clusters</span></div><svg viewBox="0 0 800 460" className="network-svg">{(data?.edges||[]).slice(0,60).map((edge:any,i:number)=>{const a:any=byId.get(edge.source),b:any=byId.get(edge.target);return a&&b?<line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}/>:null})}{nodes.map((node:any)=><g key={node.id} onClick={()=>setSelected(node)} className={(node.type||node.label||'device').toLowerCase()}><circle cx={node.x} cy={node.y} r={16+Math.min((node.risk_score||0)/8,13)}/><text x={node.x} y={node.y+4}>{String(node.type||node.label||'?').slice(0,3)}</text></g>)}</svg><div className="graph-legend"><span><i className="victim"/>Citizen</span><span><i className="phone"/>Phone</span><span><i className="upi"/>UPI</span><span><i className="bank"/>Bank</span><span><i className="device"/>Device</span></div></article><article className="panel entity">{selected?<><button className="entity-close" onClick={()=>setSelected(null)}><X/></button><div className="entity-avatar">{String(selected.type||'EN').slice(0,2).toUpperCase()}</div><small>ENTITY PROFILE</small><h2>{selected.label||selected.id}</h2><span className={selected.risk_score>=70?'tag-risk':'tag-safe'}>{selected.risk_score>=70?'HIGH RISK':'MONITORED'}</span><div className="entity-score"><span>Risk score</span><b>{selected.risk_score||0} / 100</b></div><h4>GRAPH SIGNALS</h4><div className="connections"><span><Network/> PageRank {selected.pagerank||0}</span><span><Activity/> Centrality {selected.centrality||0}</span><span><FileText/> Cluster {selected.cluster_id||'—'}</span></div></>:<div className="empty-state"><Network/><h3>Select an entity</h3><p>Choose a node to inspect its live risk and relationships.</p></div>}</article></div></Shell>
}

function CrimeMap(){
 const {data,loading,error,retry}=useApi<any>(()=>services.hotspots(),[])
 const [district,setDistrict]=useState('All districts')
 if(loading)return <Shell title="Crime Intelligence Map" subtitle="Predicting emerging hotspots."><LoadingPanel/></Shell>
 if(error)return <Shell title="Crime Intelligence Map" subtitle="Live geospatial risk."><ErrorPanel message={error} retry={retry}/></Shell>
 const all=data?.hotspots||[];const shown=district==='All districts'?all:all.filter((x:any)=>x.district===district)
 return <Shell title="Crime Intelligence Map" subtitle="Live incidents, emerging hotspots and predictive risk."><div className="map-layout"><article className="map-canvas"><div className="map-grid"/>{shown.map((item:any,i:number)=><span key={item.district} className="hotspot" title={`${item.district}: ${item.predicted_risk}`} style={{left:`${18+(i*23)%70}%`,top:`${22+(i*31)%60}%`,width:45+item.predicted_risk,height:45+item.predicted_risk}}/>)}{shown.slice(0,4).map((item:any,i:number)=><div key={item.district} className="map-label" style={{left:`${15+(i*23)%70}%`,top:`${18+(i*31)%60}%`}}>{item.district.toUpperCase()}</div>)}<div className="map-toolbar"><button>+</button><button>−</button><button><Globe2/></button></div><div className="map-filters"><select value={district} onChange={e=>setDistrict(e.target.value)}><option>All districts</option>{all.map((x:any)=><option key={x.district}>{x.district}</option>)}</select></div></article><article className="panel hotspots"><h3>Top hotspots</h3><p>Ranked by predicted risk</p>{shown.slice(0,8).map((x:any,i:number)=><div className="hot-row" key={x.district}><b>{String(i+1).padStart(2,'0')}</b><span>{x.district}<small>{x.incident_count} synthetic incidents analyzed</small></span><em>{x.predicted_risk}</em></div>)}<div className="prediction"><Sparkles/><div><b>Model explanation</b><p>{data?.explanation?.join(' • ')}</p></div></div></article></div></Shell>
}

function Assistant(){
 const [input,setInput]=useState('');const [loading,setLoading]=useState(false);const [messages,setMessages]=useState<any[]>([{role:'bot',text:'Namaste! I can analyze suspicious messages and explain the risk signals I find.'}])
 const send=async(text=input)=>{if(!text.trim()||loading)return;setMessages(m=>[...m,{role:'user',text}]);setInput('');setLoading(true);try{const result=await services.chat(text);setMessages(m=>[...m,{role:'bot',text:result.response,confidence:Math.round(result.confidence*100),risk:result.risk_level}])}catch(err){setMessages(m=>[...m,{role:'bot',text:errorMessage(err),error:true}])}finally{setLoading(false)}}
 return <Shell title="Citizen Fraud Shield" subtitle="Verify suspicious content and get trusted guidance instantly."><div className="chat-layout"><article className="panel chat"><div className="chat-status"><span><Bot/></span><div><b>Sentinel AI</b><small><i/> Connected to protected analysis</small></div><em>EN</em></div><div className="messages">{messages.map((msg,i)=>msg.role==='user'?<div className="user-msg" key={i}><p>{msg.text}</p></div>:<div className="bot-msg" key={i}><span><Bot/></span>{msg.confidence?<div className="analysis-msg"><b><ShieldCheck/> {msg.risk} risk</b><p>{msg.text}</p><div><span>AI confidence</span><b>{msg.confidence}%</b></div><i><em style={{width:`${msg.confidence}%`}}/></i></div>:<p className={msg.error?'message-error':''}>{msg.text}</p>}</div>)}{loading&&<div className="bot-msg"><span><Bot/></span><p>Analyzing risk signals…</p></div>}</div><div className="suggestions">{['Is this message fake?','Check this UPI payment request','Explain digital arrest fraud','Report a suspicious call'].map(x=><button key={x} onClick={()=>void send(x)}>{x}</button>)}</div><form className="chat-input" onSubmit={e=>{e.preventDefault();void send()}}><input value={input} onChange={e=>setInput(e.target.value)} placeholder="Describe or paste something suspicious..."/><button disabled={loading} aria-label="Send message"><ArrowRight/></button></form></article><aside className="shield-tips"><div className="panel"><ShieldCheck/><h3>Privacy-aware analysis</h3><p>Sentinel stores an auditable AI result. Avoid entering passwords, OTPs, or financial credentials.</p></div><div className="panel"><h3>Quick safety checks</h3>{['Never share OTP or PIN','Verify caller independently','Avoid unknown payment links','Report threats immediately'].map(x=><p key={x}><Check/> {x}</p>)}</div></aside></div></Shell>
}

function Reports(){
 const [search,setSearch]=useState('');const {data,loading,error,retry}=useApi(()=>services.reports(search?{search}:undefined),[search])
 return <Shell title="Citizen Reports" subtitle="Review, triage and investigate public safety submissions."><article className="panel reports"><div className="report-tools"><div className="global-search"><Search/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search reports..."/></div><button onClick={retry}><SlidersHorizontal/> Refresh</button></div>{loading?<LoadingPanel label="Loading reports…"/>:error?<ErrorPanel message={error} retry={retry}/>:<div className="table-scroll"><table><thead><tr><th>REPORT ID</th><th>REPORT</th><th>CATEGORY</th><th>LOCATION</th><th>RISK</th><th>STATUS</th><th>SUBMITTED</th></tr></thead><tbody>{data?.items.map(item=><tr key={item.id}><td>#{item.id.slice(0,8)}</td><td>{item.title}</td><td>{item.category.replace('_',' ')}</td><td>{item.location||'—'}</td><td><span className={`risk-${item.risk_score>=80?'critical':item.risk_score>=60?'high':item.risk_score>=30?'medium':'low'}`}>{item.risk_score}</span></td><td><span className="status">{item.status}</span></td><td>{new Date(item.created_at).toLocaleDateString()}</td></tr>)}</tbody></table>{!data?.items.length&&<div className="empty-inline">No reports match this search.</div>}</div>}</article></Shell>
}

function Analytics(){
 const {data,loading,error,retry}=useApi(()=>services.analytics(),[])
 if(loading)return <Shell title="Intelligence Analytics" subtitle="Calculating operational impact."><LoadingPanel/></Shell>
 if(error)return <Shell title="Intelligence Analytics" subtitle="Cross-network performance."><ErrorPanel message={error} retry={retry}/></Shell>
 const d=data!;const chart=d.monthly_trends.map(x=>({n:new Date(x.date).toLocaleDateString(undefined,{month:'short',day:'numeric'}),v:x.count}));const risk=Object.entries(d.risk_distribution).map(([name,v])=>({name,v}))
 return <Shell title="Intelligence Analytics" subtitle="Cross-network performance, trends and operational impact."><div className="analytics-kpis">{[[`₹${d.money_saved.toLocaleString('en-IN')}`,'Citizen money saved'],[String(d.protected_citizens),'Citizens protected'],[String(d.digital_arrest_cases),'Calls analyzed'],[String(d.active_investigations),'Active investigations']].map(x=><div className="panel" key={x[1]}><small>{x[1]}</small><b>{x[0]}</b><em>LIVE</em></div>)}</div><div className="analytics-grid"><article className="panel wide"><div className="panel-head"><div><h3>Fraud growth</h3><p>30-day verified report volume</p></div></div><ResponsiveContainer width="100%" height={260}><AreaChart data={chart}><CartesianGrid stroke="#1a2940" vertical={false}/><XAxis dataKey="n" stroke="#63708a"/><YAxis stroke="#63708a"/><Tooltip/><Area dataKey="v" stroke="#3976ff" fill="#3976ff33"/></AreaChart></ResponsiveContainer></article><article className="panel"><div className="panel-head"><div><h3>Risk distribution</h3><p>Current report portfolio</p></div></div><ResponsiveContainer width="100%" height={210}><PieChart><Pie data={risk} dataKey="v" nameKey="name" innerRadius={60} outerRadius={85}>{['#3976ff','#19c6d4','#9b6cff','#f05b67'].map(c=><Cell key={c} fill={c}/>)}</Pie></PieChart></ResponsiveContainer><div className="pie-labels">{risk.map(x=><span key={x.name}><i/>{x.name} {x.v}</span>)}</div></article></div></Shell>
}

function SettingsPage(){
 const {user}=useAuth();const [name,setName]=useState(user?.full_name||'');const [status,setStatus]=useState('')
 const save=async()=>{setStatus('Saving…');try{await services.auth.updateMe(name);setStatus('Profile saved')}catch(err){setStatus(errorMessage(err))}}
 return <Shell title="Settings" subtitle="Manage your command profile, security and platform preferences."><div className="settings-layout"><nav>{['Profile','Security','Notifications','Language & region','Appearance'].map((x,i)=><button key={x} className={i===0?'active':''}>{x}</button>)}</nav><article className="panel settings-form"><h3>Command profile</h3><p>Manage the identity shown across your agency workspace.</p><div className="avatar-edit"><span>{name.split(' ').map(x=>x[0]).slice(0,2).join('').toUpperCase()}</span></div><div className="form-grid"><label>Full name<input value={name} onChange={e=>setName(e.target.value)}/></label><label>Role<input disabled value={user?.role.replace('_',' ')}/></label><label>Email address<input disabled value={user?.email}/></label><label>Account state<input disabled value={user?.is_active?'Active':'Inactive'}/></label></div><hr/><div className="setting-row"><div><b>Critical alert notifications</b><p>Receive high-priority alerts through the live channel.</p></div><button className="toggle on"><i/></button></div><button onClick={()=>void save()} className="primary">Save changes</button>{status&&<span className="save-status">{status}</span>}</article></div></Shell>
}

function Login(){
 const [role,setRole]=useState('Police Officer');const [email,setEmail]=useState('admin@sentinelx.gov.in');const [password,setPassword]=useState('SentinelX!2026');const [show,setShow]=useState(false);const [loading,setLoading]=useState(false);const [error,setError]=useState('');const navigate=useNavigate();const location=useLocation();const {login,user}=useAuth();const roles=[[CircleUserRound,'Citizen'],[Shield,'Police Officer'],[Landmark,'Bank'],[Globe2,'Telecom Provider'],[LockKeyhole,'Administrator']] as const
 useEffect(()=>{if(user)navigate('/dashboard',{replace:true})},[user,navigate])
 const submit=async(e:FormEvent)=>{e.preventDefault();setLoading(true);setError('');try{await login(email,password);navigate((location.state as any)?.from||'/dashboard',{replace:true})}catch(err){setError(errorMessage(err))}finally{setLoading(false)}}
 return <div className="login"><div className="login-art"><Logo/><div><span className="kicker">SECURE ACCESS GATEWAY</span><h1>One platform.<br/><em>Every defender.</em></h1><p>Access real-time intelligence across India's digital public safety network.</p></div><small>ENCRYPTED • ROLE-BASED ACCESS • AUDIT LOGGED</small></div><div className="login-form"><form className="login-box" onSubmit={submit}><span className="mobile-logo"><Logo/></span><h2>Welcome to SentinelX</h2><p>Select your workspace and sign in securely.</p><div className="role-grid">{roles.map(([Icon,r])=><button type="button" key={r} onClick={()=>setRole(r)} className={role===r?'active':''}><Icon/><span>{r}</span>{role===r&&<Check/>}</button>)}</div><label>Official email or ID<input required type="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="name@agency.gov.in"/></label><label>Password<div className="password"><input required type={show?'text':'password'} value={password} onChange={e=>setPassword(e.target.value)} placeholder="Enter your password"/><button type="button" onClick={()=>setShow(!show)}>{show?'Hide':'Show'}</button></div></label>{error&&<div className="login-error"><AlertTriangle/>{error}</div>}<button disabled={loading} className="primary login-button" type="submit">{loading?'Establishing secure session…':'Sign in securely'} <ArrowRight/></button><p className="support">Demo credentials are created by <code>scripts/seed.py</code>.</p></form></div></div>
}

export default function App(){
 const all=['police','bank','telecom_provider','administrator'] as const
 return <Routes><Route path="/" element={<Landing/>}/><Route path="/login" element={<Login/>}/><Route path="/dashboard" element={<Protected><Dashboard/></Protected>}/><Route path="/digital-arrest" element={<Protected roles={['police','telecom_provider','administrator']}><DigitalArrest/></Protected>}/><Route path="/counterfeit" element={<Protected roles={['police','bank','administrator']}><Counterfeit/></Protected>}/><Route path="/network" element={<Protected roles={[...all]}><NetworkPage/></Protected>}/><Route path="/crime-map" element={<Protected roles={['police','telecom_provider','administrator']}><CrimeMap/></Protected>}/><Route path="/assistant" element={<Protected><Assistant/></Protected>}/><Route path="/reports" element={<Protected><Reports/></Protected>}/><Route path="/analytics" element={<Protected roles={[...all]}><Analytics/></Protected>}/><Route path="/settings" element={<Protected><SettingsPage/></Protected>}/><Route path="*" element={<Landing/>}/></Routes>
}
