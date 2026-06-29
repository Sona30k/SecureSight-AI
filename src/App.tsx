import { useState } from 'react'
import { Routes, Route, NavLink, useNavigate } from 'react-router-dom'
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
 return <aside className={`sidebar ${open?'open':''}`}><div className="side-top"><Logo/><button className="mobile-x" onClick={onClose}><X/></button></div><div className="agency"><span><Building2/></span><div><small>OPERATING AS</small><b>National Command</b></div><ChevronDown/></div><nav><small>COMMAND CENTER</small>{nav.map(([label,Icon,path])=><NavLink onClick={onClose} key={label} to={path}><Icon/>{label}{label==='Citizen Reports'&&<em>12</em>}</NavLink>)}<small>SYSTEM</small><NavLink onClick={onClose} to="/settings"><Settings/>Settings</NavLink></nav><div className="side-card"><div><Sparkles/> Sentinel AI</div><p>Ask about live incidents, patterns, or case intelligence.</p><NavLink to="/assistant">Open assistant <ArrowRight/></NavLink></div><div className="operator"><span>AK</span><div><b>Arjun Kapoor</b><small>Command Officer</small></div><button><ChevronDown/></button></div></aside>
}

function Topbar({toggle}:{toggle:()=>void}) {
 return <header className="topbar"><button className="menu-btn" onClick={toggle}><Menu/></button><div className="global-search"><Search/><input placeholder="Search cases, entities, phone numbers..."/><kbd>⌘ K</kbd></div><div className="top-actions"><div className="live"><i/> System live</div><button><Bell/><span/></button><button><Headphones/></button></div></header>
}

function Shell({children,title,subtitle}:{children:React.ReactNode,title:string,subtitle:string}) {
 const [open,setOpen]=useState(false)
 return <div className="shell"><Sidebar open={open} onClose={()=>setOpen(false)}/><div className="main"><Topbar toggle={()=>setOpen(true)}/><div className="page"><div className="page-title"><div><div className="breadcrumb">COMMAND CENTER <span>/</span> LIVE OVERVIEW</div><h1>{title}</h1><p>{subtitle}</p></div><div className="date-pill"><Clock3/> Live • Updated 4 sec ago <ChevronDown/></div></div>{children}</div></div><button className="ai-fab"><Sparkles/><span>Ask Sentinel</span></button></div>
}

function StatCard({label,value,delta,Icon,tone}:{label:string,value:string,delta:string,Icon:any,tone:string}) {
 return <motion.article whileHover={{y:-3}} className="stat-card"><div className={`stat-icon ${tone}`}><Icon/></div><div className="stat-label">{label}<span>•••</span></div><b>{value}</b><div className="stat-foot"><em className={delta.includes('-')?'down':''}>{delta}</em><span>vs yesterday</span><div className="mini-bars">{[3,5,4,7,6,9,8].map((n,i)=><i key={i} style={{height:n*2.2}}/>)}</div></div></motion.article>
}

function Dashboard() {
 return <Shell title="Good morning, Arjun." subtitle="Here’s what’s happening across the network right now.">
   <div className="alert-banner"><div className="pulse-alert"><AlertTriangle/></div><div><b>Critical threat cluster detected</b><p>17 linked scam calls targeting senior citizens in Central District</p></div><span>High priority</span><button>Open investigation <ArrowRight/></button></div>
   <div className="stat-grid"><StatCard label="Live threat score" value="72 / 100" delta="+8.4%" Icon={Radar} tone="blue"/><StatCard label="Today's alerts" value="247" delta="+12.1%" Icon={Siren} tone="red"/><StatCard label="Counterfeit cases" value="38" delta="-4.2%" Icon={Banknote} tone="green"/><StatCard label="Scam calls blocked" value="1,284" delta="+18.7%" Icon={PhoneCall} tone="purple"/><StatCard label="Citizens protected" value="3,947" delta="+9.3%" Icon={UsersRound} tone="cyan"/></div>
   <div className="dash-grid">
    <article className="panel threat-chart"><div className="panel-head"><div><h3>Threat intelligence</h3><p>Detected vs resolved • Last 24 hours</p></div><select><option>Last 24 hours</option></select></div><div className="chart-legend"><span><i className="c-blue"/> Detected</span><span><i className="c-cyan"/> Resolved</span><b>87.4% <small>Resolution rate</small></b></div><ResponsiveContainer width="100%" height={230}><AreaChart data={trend}><defs><linearGradient id="bluefill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#3976ff" stopOpacity=".32"/><stop offset="1" stopColor="#3976ff" stopOpacity="0"/></linearGradient></defs><CartesianGrid stroke="#1a2940" vertical={false}/><XAxis dataKey="t" stroke="#63708a" tickLine={false} axisLine={false}/><YAxis stroke="#63708a" tickLine={false} axisLine={false}/><Tooltip contentStyle={{background:'#101b2e',border:'1px solid #263650',borderRadius:12}}/><Area dataKey="threats" stroke="#3976ff" strokeWidth={2} fill="url(#bluefill)"/><Line dataKey="resolved" stroke="#19c6d4" strokeWidth={2}/></AreaChart></ResponsiveContainer></article>
    <article className="panel risk-panel"><div className="panel-head"><div><h3>National risk index</h3><p>Real-time composite score</p></div><span className="trend-up">↗ 8.2%</span></div><div className="gauge"><div className="gauge-inner"><b>72</b><span>HIGH RISK</span></div></div><div className="risk-row"><span>Digital arrest <b>82</b></span><i><em style={{width:'82%'}}/></i></div><div className="risk-row"><span>Financial fraud <b>68</b></span><i><em style={{width:'68%'}}/></i></div><div className="risk-row"><span>Counterfeit <b>43</b></span><i><em style={{width:'43%'}}/></i></div></article>
    <article className="panel district-panel"><div className="panel-head"><div><h3>Alerts by district</h3><p>Active incidents today</p></div><button>View map <ArrowRight/></button></div><ResponsiveContainer width="100%" height={205}><BarChart data={districts} layout="vertical"><XAxis type="number" hide/><YAxis dataKey="name" type="category" stroke="#9aa6bc" width={62} axisLine={false} tickLine={false}/><Tooltip cursor={{fill:'#142136'}} contentStyle={{background:'#101b2e',border:'1px solid #263650',borderRadius:12}}/><Bar dataKey="value" radius={[0,6,6,0]} fill="#3776f6" barSize={13}/></BarChart></ResponsiveContainer></article>
    <ActivityPanel/>
   </div>
 </Shell>
}

function ActivityPanel(){
 const items=[[PhoneCall,'Scam call blocked','+91 98210 44•••','2m','red'],[ShieldCheck,'Citizen funds secured','₹2,40,000 transfer stopped','6m','green'],[Banknote,'Counterfeit note detected','Case #SX-88429 • Central','12m','cyan'],[Network,'Fraud network expanded','7 new entities connected','18m','purple'],[FileText,'Citizen report verified','Digital arrest attempt','24m','blue']]
 return <article className="panel activity-panel"><div className="panel-head"><div><h3>Live activity</h3><p>Cross-network event stream</p></div><button>View all</button></div><div className="activity-list">{items.map(([I,title,sub,time,tone]:any,i)=>{const Icon=I;return <div className="activity-item" key={i}><span className={`activity-icon ${tone}`}><Icon/></span><div><b>{title}</b><small>{sub}</small></div><time>{time}</time></div>})}</div></article>
}

const genericData = [{n:'Mon',v:44},{n:'Tue',v:57},{n:'Wed',v:48},{n:'Thu',v:71},{n:'Fri',v:63},{n:'Sat',v:82},{n:'Sun',v:76}]

function DigitalArrest(){
 return <Shell title="Digital Arrest Detection" subtitle="Live call analysis and coercion pattern detection."><div className="call-grid"><article className="panel incoming"><div className="incoming-head"><i/><span>LIVE CALL ANALYSIS</span><small>00:04:27</small></div><div className="caller"><div><PhoneCall/></div><small>INCOMING CALLER</small><h2>+91 88743 29104</h2><p>Caller ID spoofed • Origin masked</p></div><div className="call-actions"><button><PhoneCall/> Block number</button><button><Siren/> Notify police</button></div></article><article className="panel score-card"><span>SCAM PROBABILITY</span><div className="score-ring"><b>94%</b><small>CRITICAL</small></div><p>Voice stress, urgency and impersonation signals detected.</p></article><article className="panel recommendation"><div><Sparkles/> AI RECOMMENDATION</div><h3>Block and escalate immediately</h3><p>Caller is impersonating a Central Bureau investigator and requesting an urgent “verification transfer.”</p><div className="chips"><span>Authority impersonation</span><span>Urgency</span><span>Financial demand</span></div></article></div><div className="panel transcript"><div className="panel-head"><div><h3>Live transcript</h3><p>Speech-to-text • English + Hindi</p></div><button>Download evidence</button></div><div className="transcript-line"><span>00:02</span><p>This is Officer Sharma from the <mark>Central Investigation Bureau</mark>. Your Aadhaar has been linked to money laundering.</p></div><div className="transcript-line suspect"><span>00:18</span><p>You must remain on this call. Do not inform anyone. A <mark>digital arrest warrant</mark> has been issued in your name.</p></div><div className="transcript-line suspect"><span>00:41</span><p>Transfer ₹50,000 to our <mark>verification account immediately</mark> or the police will arrive.</p></div></div></Shell>
}

function Counterfeit(){
 const [uploaded,setUploaded]=useState(false)
 return <Shell title="Counterfeit Detection" subtitle="AI-powered currency authentication with forensic-grade precision."><div className="counter-grid"><article onClick={()=>setUploaded(true)} className={`upload-zone ${uploaded?'uploaded':''}`}>{uploaded?<><div className="note-preview"><Landmark/><b>₹ 500</b><span>5AF 291847</span></div><ShieldCheck/><h3>Note appears authentic</h3><p>98.7% confidence • 14/14 features verified</p></>:<><div className="upload-icon"><UploadCloud/></div><h3>Drop a currency image here</h3><p>or click to browse • JPG, PNG up to 10 MB</p><button>Choose image</button></>}</article><article className="panel inspection"><div className="panel-head"><div><h3>Feature inspection</h3><p>Computer vision security checks</p></div><span className="verified">14 VERIFIED</span></div>{[['Security thread',96],['Watermark',99],['Serial number',94],['Microprint',91],['Intaglio print',98]].map(([x,v]:any)=><div className="inspect-row" key={x}><span><Check/> {x}</span><i><em style={{width:`${v}%`}}/></i><b>{v}%</b></div>)}</article></div><article className="panel history"><div className="panel-head"><div><h3>Detection history</h3><p>Recent currency inspections</p></div><button>Export report</button></div><table><thead><tr><th>CASE ID</th><th>DENOMINATION</th><th>LOCATION</th><th>RESULT</th><th>CONFIDENCE</th><th>TIME</th></tr></thead><tbody>{[['SX-89241','₹500','New Delhi','Authentic','98.7%','2 min ago'],['SX-89238','₹2000','Jaipur','Counterfeit','96.2%','8 min ago'],['SX-89211','₹200','Mumbai','Authentic','99.1%','24 min ago']].map(r=><tr>{r.map((c,i)=><td>{i===3?<span className={c==='Authentic'?'tag-safe':'tag-risk'}>{c}</span>:c}</td>)}</tr>)}</tbody></table></article></Shell>
}

function NetworkPage(){
 const [selected,setSelected]=useState(true)
 return <Shell title="Fraud Network Intelligence" subtitle="Explore hidden relationships across cases, entities and transactions."><div className="network-wrap"><article className="panel graph"><div className="graph-controls"><span><SlidersHorizontal/> Filter graph</span><button>−</button><button>+</button></div><svg viewBox="0 0 800 460" className="network-svg">{[[400,220,160,100],[400,220,650,120],[400,220,630,350],[400,220,180,360],[160,100,80,250],[650,120,730,240],[180,360,360,400],[630,350,500,410]].map((l,i)=><line key={i} x1={l[0]} y1={l[1]} x2={l[2]} y2={l[3]}/>)}{[[400,220,46,'AK','victim'],[160,100,34,'+91','phone'],[650,120,38,'UPI','upi'],[630,350,34,'A/C','bank'],[180,360,32,'DV','device'],[80,250,24,'+91','phone'],[730,240,25,'UPI','upi'],[360,400,22,'A/C','bank'],[500,410,21,'DV','device']].map((n:any,i)=><g key={i} onClick={()=>setSelected(true)} className={n[5]}><circle cx={n[0]} cy={n[1]} r={n[2]}/><text x={n[0]} y={n[1]+5}>{n[3]}</text></g>)}</svg><div className="graph-legend"><span><i className="victim"/>Victim</span><span><i className="phone"/>Phone</span><span><i className="upi"/>UPI ID</span><span><i className="bank"/>Bank account</span><span><i className="device"/>Device</span></div></article>{selected&&<article className="panel entity"><button className="entity-close" onClick={()=>setSelected(false)}><X/></button><div className="entity-avatar">AK</div><small>ENTITY PROFILE</small><h2>Arun Kumar</h2><span className="tag-risk">HIGH-RISK VICTIM</span><div className="entity-score"><span>Risk score</span><b>87 / 100</b></div><h4>CONNECTED ENTITIES</h4><div className="connections"><span><PhoneCall/> 4 phone numbers</span><span><WalletCards/> 3 bank accounts</span><span><Network/> 2 UPI IDs</span></div><h4>RECENT TIMELINE</h4><div className="mini-timeline"><p><i/>₹84,000 transferred<small>Today • 11:42</small></p><p><i/>Scam call received<small>Today • 11:28</small></p><p><i/>First report linked<small>23 Jun • 16:04</small></p></div></article>}</div></Shell>
}

function CrimeMap(){
 return <Shell title="Crime Intelligence Map" subtitle="Live incidents, emerging hotspots and predictive risk."><div className="map-layout"><article className="map-canvas"><div className="map-grid"/>{[[20,25,80],[58,38,120],[72,70,90],[35,72,70],[48,52,150]].map((p,i)=><span key={i} className="hotspot" style={{left:`${p[0]}%`,top:`${p[1]}%`,width:p[2],height:p[2]}}/>)}<div className="map-label l1">CENTRAL DISTRICT</div><div className="map-label l2">NORTH ZONE</div><div className="map-toolbar"><button>+</button><button>−</button><button><Globe2/></button></div><div className="map-filters"><button><Clock3/> Last 24 hours <ChevronDown/></button><button><Siren/> All incident types <ChevronDown/></button></div></article><article className="panel hotspots"><h3>Top hotspots</h3><p>Ranked by predicted risk</p>{[['Connaught Place','Critical','94'],['Karol Bagh','High','82'],['Lajpat Nagar','High','76'],['Rohini Sector 9','Elevated','64']].map((x,i)=><div className="hot-row"><b>0{i+1}</b><span>{x[0]}<small>{12-i*2} active incidents</small></span><em>{x[2]}</em></div>)}<div className="prediction"><Sparkles/><div><b>Predicted hotspot</b><p>Risk likely to rise 27% near Chandni Chowk between 18:00–21:00.</p></div></div></article></div></Shell>
}

function Assistant(){
 return <Shell title="Citizen Fraud Shield" subtitle="Verify suspicious content and get trusted guidance instantly."><div className="chat-layout"><article className="panel chat"><div className="chat-status"><span><Bot/></span><div><b>Sentinel AI</b><small><i/> Online • Replies instantly</small></div><em>EN <ChevronDown/></em></div><div className="messages"><div className="bot-msg"><span><Bot/></span><p>Namaste! I can help you check suspicious messages, QR codes, UPI IDs, calls or documents. What would you like me to verify?</p></div><div className="user-msg"><p>I received a WhatsApp message saying my bank account will be blocked. Is it real?</p></div><div className="bot-msg"><span><Bot/></span><div className="analysis-msg"><b><ShieldCheck/> Likely fraudulent</b><p>Banks do not ask customers to verify accounts through unsolicited WhatsApp links. Do not click the link or share your OTP.</p><div><span>AI confidence</span><b>96%</b></div><i><em style={{width:'96%'}}/></i></div></div></div><div className="suggestions">{['Is this message fake?','Verify this QR code','Check this UPI ID','Report suspicious call'].map(x=><button>{x}</button>)}</div><div className="chat-input"><button><UploadCloud/></button><input placeholder="Describe or paste something suspicious..."/><button><ArrowRight/></button></div></article><aside className="shield-tips"><div className="panel"><ShieldCheck/><h3>You’re protected</h3><p>Sentinel does not store your conversations or uploaded content after verification.</p></div><div className="panel"><h3>Quick safety checks</h3>{['Never share OTP or PIN','Verify caller independently','Avoid unknown payment links','Report threats immediately'].map(x=><p><Check/> {x}</p>)}</div></aside></div></Shell>
}

function Reports(){
 return <Shell title="Citizen Reports" subtitle="Review, triage and investigate public safety submissions."><article className="panel reports"><div className="report-tools"><div className="global-search"><Search/><input placeholder="Search reports..."/></div><button><SlidersHorizontal/> Filters</button><button>Export CSV</button><button>Export PDF</button></div><table><thead><tr><th>REPORT ID</th><th>CATEGORY</th><th>LOCATION</th><th>RISK</th><th>STATUS</th><th>SUBMITTED</th></tr></thead><tbody>{[['#SX-10482','Digital arrest','Central Delhi','Critical','Investigating','4 min ago'],['#SX-10481','UPI fraud','Jaipur','High','Verified','12 min ago'],['#SX-10480','Counterfeit','Mumbai','Medium','Assigned','24 min ago'],['#SX-10479','Phishing','Pune','High','Investigating','31 min ago'],['#SX-10478','Scam call','Lucknow','Low','Resolved','42 min ago']].map(r=><tr>{r.map((c,i)=><td>{i===3?<span className={`risk-${c.toLowerCase()}`}>{c}</span>:i===4?<span className="status">{c}</span>:c}</td>)}</tr>)}</tbody></table></article></Shell>
}

function Analytics(){
 return <Shell title="Intelligence Analytics" subtitle="Cross-network performance, trends and operational impact."><div className="analytics-kpis">{[['₹284Cr','Citizen money saved'],['96.8%','Detection accuracy'],['18,428','Threats neutralized'],['2.1 sec','Median response']].map(x=><div className="panel"><small>{x[1]}</small><b>{x[0]}</b><em>↗ 12.4%</em></div>)}</div><div className="analytics-grid"><article className="panel wide"><div className="panel-head"><div><h3>Fraud growth & intervention</h3><p>12-week threat volume</p></div></div><ResponsiveContainer width="100%" height={260}><AreaChart data={genericData}><CartesianGrid stroke="#1a2940" vertical={false}/><XAxis dataKey="n" stroke="#63708a"/><YAxis stroke="#63708a"/><Tooltip/><Area dataKey="v" stroke="#3976ff" fill="#3976ff33"/></AreaChart></ResponsiveContainer></article><article className="panel"><div className="panel-head"><div><h3>Top scam types</h3><p>Share of verified cases</p></div></div><ResponsiveContainer width="100%" height={210}><PieChart><Pie data={[{v:38},{v:27},{v:21},{v:14}]} dataKey="v" innerRadius={60} outerRadius={85}>{['#3976ff','#19c6d4','#9b6cff','#f05b67'].map(c=><Cell fill={c}/>)}</Pie></PieChart></ResponsiveContainer><div className="pie-labels"><span><i/>Digital arrest 38%</span><span><i/>UPI fraud 27%</span><span><i/>Phishing 21%</span></div></article><article className="panel wide"><div className="panel-head"><div><h3>Digital arrest trend</h3><p>Detected attempts by day</p></div></div><ResponsiveContainer width="100%" height={220}><LineChart data={genericData}><CartesianGrid stroke="#1a2940" vertical={false}/><XAxis dataKey="n" stroke="#63708a"/><YAxis stroke="#63708a"/><Line dataKey="v" stroke="#19c6d4" strokeWidth={3}/></LineChart></ResponsiveContainer></article></div></Shell>
}

function SettingsPage(){
 return <Shell title="Settings" subtitle="Manage your command profile, security and platform preferences."><div className="settings-layout"><nav>{['Profile','Security','Notifications','Language & region','Appearance','API configuration'].map((x,i)=><button className={i===0?'active':''}>{x}</button>)}</nav><article className="panel settings-form"><h3>Command profile</h3><p>Manage the information shown across your agency workspace.</p><div className="avatar-edit"><span>AK</span><button>Change photo</button></div><div className="form-grid"><label>Full name<input defaultValue="Arjun Kapoor"/></label><label>Role<input defaultValue="Command Officer"/></label><label>Email address<input defaultValue="arjun.kapoor@sentinel.gov.in"/></label><label>Agency<input defaultValue="National Command Center"/></label></div><hr/><div className="setting-row"><div><b>Multi-factor authentication</b><p>Require an authenticator for every new device.</p></div><button className="toggle on"><i/></button></div><div className="setting-row"><div><b>Critical alert notifications</b><p>Receive high-priority alerts on this device.</p></div><button className="toggle on"><i/></button></div><button className="primary">Save changes</button></article></div></Shell>
}

function Login(){
 const [role,setRole]=useState('Police Officer');const navigate=useNavigate();const roles=[[CircleUserRound,'Citizen'],[Shield,'Police Officer'],[Landmark,'Bank'],[Globe2,'Telecom Provider'],[LockKeyhole,'Administrator']] as const
 return <div className="login"><div className="login-art"><Logo/><div><span className="kicker">SECURE ACCESS GATEWAY</span><h1>One platform.<br/><em>Every defender.</em></h1><p>Access real-time intelligence across India's digital public safety network.</p></div><small>256-BIT ENCRYPTED • ZERO TRUST ARCHITECTURE</small></div><div className="login-form"><div className="login-box"><span className="mobile-logo"><Logo/></span><h2>Welcome to SentinelX</h2><p>Select your role to continue securely.</p><div className="role-grid">{roles.map(([Icon,r])=><button onClick={()=>setRole(r)} className={role===r?'active':''}><Icon/><span>{r}</span>{role===r&&<Check/>}</button>)}</div><label>Official email or ID<input placeholder="name@agency.gov.in"/></label><label>Password<div className="password"><input type="password" placeholder="Enter your password"/><button>Show</button></div></label><div className="remember"><label><input type="checkbox"/> Keep me signed in</label><a>Forgot password?</a></div><button className="primary login-button" onClick={()=>navigate('/dashboard')}>Sign in securely <ArrowRight/></button><div className="sso"><span>OR CONTINUE WITH</span><button><Landmark/> Government SSO</button></div><p className="support">Need secure access? <a>Contact your administrator</a></p></div></div></div>
}

export default function App(){
 return <Routes><Route path="/" element={<Landing/>}/><Route path="/login" element={<Login/>}/><Route path="/dashboard" element={<Dashboard/>}/><Route path="/digital-arrest" element={<DigitalArrest/>}/><Route path="/counterfeit" element={<Counterfeit/>}/><Route path="/network" element={<NetworkPage/>}/><Route path="/crime-map" element={<CrimeMap/>}/><Route path="/assistant" element={<Assistant/>}/><Route path="/reports" element={<Reports/>}/><Route path="/analytics" element={<Analytics/>}/><Route path="/settings" element={<SettingsPage/>}/></Routes>
}
