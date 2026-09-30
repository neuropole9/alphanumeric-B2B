import {useEffect,useState} from 'react'
import type {ReactNode} from 'react'
import {useNavigate,useParams,useSearchParams} from 'react-router-dom'
import {ArrowUpRight,Building2,Download,Mail,MapPin,Phone,Plus} from 'lucide-react'
import {api,receiveServerFile} from '../api/client'
import type {Activity,Customer,Inquiry,Invoice,Order,Partner,ProjectSummary,Quotation} from '../types'
import {Breadcrumbs,Button,Card,Empty,Notice,PageTitle,Status,money} from '../components/UI'

type Tab='overview'|'projects'|'inquiries'|'quotations'|'orders'|'invoices'|'activity'
type ProjectCard=ProjectSummary&{partner?:Partner|null;buildings:number;floors:number;rooms:number}
interface CustomerWorkspace {customer:Customer;summary:{projects:number;active_projects:number;buildings:number;floors:number;rooms:number;users:number;inquiries:number;quotations:number;orders:number;invoices:number;outstanding:number};projects:ProjectCard[];inquiries:Inquiry[];quotations:Quotation[];orders:Order[];invoices:Invoice[];activity:Activity[]}
const tabs:Tab[]=['overview','projects','inquiries','quotations','orders','invoices','activity']

export default function CustomerDetailPage(){
  const {id,workspace='lighting'}=useParams()
  const navigate=useNavigate()
  const [params,setParams]=useSearchParams()
  const tab=(tabs.includes(params.get('tab') as Tab)?params.get('tab'):'overview') as Tab
  const [data,setData]=useState<CustomerWorkspace>()
  const [error,setError]=useState<string>()
  const [busy,setBusy]=useState<string>()
  const load=()=>{setError(undefined);api<CustomerWorkspace>(`/api/v1/customers/${id}`).then(setData).catch(reason=>setError(reason.message))}
  useEffect(load,[id])
  const setTab=(value:Tab)=>setParams({tab:value})
  const projectRoute=(projectId:string)=>`/app/${workspace}/customers/${id}/projects/${projectId}`
  const download=async(project:ProjectCard)=>{setBusy(project.id);setError(undefined);try{await receiveServerFile(`/api/v1/projects/${project.id}/book.pdf?workspace=${workspace.toUpperCase()}\&download=true`,'download')}catch(reason){setError(reason instanceof Error?reason.message:'Download failed.')}finally{setBusy(undefined)}}
  if(error&&!data)return <Card><Notice kind="error">{error}</Notice><Button onClick={load}>Retry</Button></Card>
  if(!data)return <div className="loading">Loading customer workspace…</div>
  const customer=data.customer
  return <>
    <Breadcrumbs items={[{label:'Customers',to:`/app/${workspace}/customers`},{label:customer.company_name}]}/>
    <PageTitle title={customer.company_name} subtitle={`${customer.contact_person||'No primary contact'} · ${[customer.city,customer.state].filter(Boolean).join(', ')||'Location not provided'}`} badge="Customer" actions={<Button onClick={()=>navigate(`/app/${workspace}/inquiries/new?customer_id=${customer.id}`)}><Plus size={16}/> Create Inquiry</Button>}/>
    {error&&<Notice kind="error">{error}</Notice>}
    <Card className="customer-identity-bar"><div><Status value={customer.status}/><span><Phone size={14}/>{customer.phone||'—'}</span><span><Mail size={14}/>{customer.email||'—'}</span><span><MapPin size={14}/>{customer.address||'Address not provided'}</span></div><dl><div><dt>GSTIN</dt><dd>{customer.gstin||'—'}</dd></div><div><dt>Customer since</dt><dd>{customer.created_at?new Date(customer.created_at).toLocaleDateString():'—'}</dd></div><div><dt>Last activity</dt><dd>{customer.updated_at?new Date(customer.updated_at).toLocaleString():'—'}</dd></div></dl></Card>
    <div className="detail-tabs" role="tablist">{tabs.map(value=><button type="button" role="tab" aria-selected={tab===value} key={value} className={tab===value?'active':''} onClick={()=>setTab(value)}>{value==='projects'?'Projects':value[0].toUpperCase()+value.slice(1)}</button>)}</div>

    {tab==='overview'&&<><div className="customer-summary-grid">{[['Projects',data.summary.projects],['Buildings',data.summary.buildings],['Floors',data.summary.floors],['Rooms',data.summary.rooms],['Assigned users',data.summary.users],['Inquiries',data.summary.inquiries],['Quotations',data.summary.quotations],['Orders',data.summary.orders],['Invoices',data.summary.invoices]].map(([label,value])=><Card key={String(label)}><small>{label}</small><h3>{value}</h3></Card>)}</div><div className="quote-top"><Card><h3>Customer Information</h3><dl className="info-list"><div><dt>Contact</dt><dd>{customer.contact_person||'—'}</dd></div><div><dt>Email</dt><dd>{customer.email||'—'}</dd></div><div><dt>Phone</dt><dd>{customer.phone||'—'}</dd></div><div><dt>GSTIN</dt><dd>{customer.gstin||'—'}</dd></div><div><dt>Full address</dt><dd>{[customer.address,customer.city,customer.state].filter(Boolean).join(', ')||'—'}</dd></div></dl></Card><Card><h3>Relationship Health</h3><dl className="info-list"><div><dt>Active projects</dt><dd>{data.summary.active_projects}</dd></div><div><dt>Project users</dt><dd>{data.summary.users}</dd></div><div><dt>Open inquiries</dt><dd>{data.inquiries.filter(item=>!['COMPLETED','CANCELLED'].includes(item.status)).length}</dd></div><div><dt>Outstanding</dt><dd>{money(data.summary.outstanding)}</dd></div></dl></Card><Card><h3>Latest Activity</h3>{!data.activity.length?<p className="muted">No recorded activity.</p>:<div className="mini-activity">{data.activity.slice(0,5).map(item=><div key={item.id}><b>{item.action.replaceAll('.',' · ').replaceAll('_',' ')}</b><small>{new Date(item.created_at).toLocaleString()}</small></div>)}</div>}</Card></div></>}
    {tab==='projects'&&(!data.projects.length?<Card><Empty text="No projects belong to this customer."/></Card>:<div className="project-card-grid customer-project-grid">{data.projects.map(project=><article className="project-card" key={project.id}><div className="project-card-head"><span className="project-card-icon"><Building2 size={21}/></span><span className="project-card-title"><b>{project.name}</b><small>{[project.address,project.city,project.state].filter(Boolean).join(', ')||'Site location not provided'}</small></span><Status value={project.status}/></div><div className="workspace-badges">{project.workspaces.map(value=><span key={value}>{value}</span>)}</div><div className="project-card-stats project-card-stats-compact"><span><b>{project.buildings}</b><small>Buildings</small></span><span><b>{project.floors}</b><small>Floors</small></span><span><b>{project.rooms}</b><small>Rooms</small></span></div><div className="project-card-actions"><Button variant="secondary" disabled={busy===project.id} onClick={()=>download(project)}><Download size={15}/>{busy===project.id?'Preparing…':'Project Book'}</Button><Button onClick={()=>navigate(projectRoute(project.id))}>Open Project <ArrowUpRight size={15}/></Button></div></article>)}</div>)}
    {tab==='inquiries'&&<Table headers={['Inquiry','Project / Building','Created','Status','Value']} rows={data.inquiries.map(item=>[item.number,`${item.project.name} · ${item.building_name||'Project-wide'}`,new Date(item.created_at).toLocaleDateString(),<Status value={item.status}/>,money(item.estimated_value)])} empty="No inquiries for this customer." onOpen={index=>navigate(`/app/${workspace}/inquiries/${data.inquiries[index].id}`)}/>} 
    {tab==='quotations'&&<Table headers={['Quotation','Project','Date','Status','Total','Valid until']} rows={data.quotations.map(item=>[item.number,item.project.name,item.quotation_date,<Status value={item.status}/>,money(item.grand_total),item.valid_until||'—'])} empty="No quotations for this customer." onOpen={index=>navigate(`/app/${workspace}/quotations/${data.quotations[index].id}`)}/>} 
    {tab==='orders'&&<Table headers={['Order','Project','Date','Delivery','Status','Total']} rows={data.orders.map(item=>[item.number,item.project.name,item.order_date,item.delivery_date||'—',<Status value={item.status}/>,money(item.grand_total)])} empty="No orders for this customer." onOpen={index=>navigate(`/app/${workspace}/orders/${data.orders[index].id}`)}/>} 
    {tab==='invoices'&&<Table headers={['Invoice','Project','Order','Date','Due','Status','Total']} rows={data.invoices.map(item=>[item.number,item.project?.name||'—',item.order_number,item.invoice_date,item.due_date||'—',<Status value={item.status}/>,money(item.grand_total)])} empty="No invoices for this customer." onOpen={index=>navigate(`/app/${workspace}/invoices/${data.invoices[index].id}`)}/>} 
    {tab==='activity'&&<Card><h2>Customer Activity</h2>{!data.activity.length?<Empty text="No activity has been recorded for this customer."/>:<div className="activity-timeline">{data.activity.map(item=><div key={item.id}><span><b>{item.action.replaceAll('.',' · ').replaceAll('_',' ')}</b><small>{item.actor} · {new Date(item.created_at).toLocaleString()}</small></span></div>)}</div>}</Card>}
  </>
}

function Table({headers,rows,empty,onOpen}:{headers:string[];rows:ReactNode[][];empty:string;onOpen:(index:number)=>void}){
  return <Card className="table-card">{!rows.length?<Empty text={empty}/>:<div className="table-wrap"><table><thead><tr>{headers.map(header=><th key={header}>{header}</th>)}</tr></thead><tbody>{rows.map((row,index)=><tr key={index} onClick={()=>onOpen(index)}>{row.map((value,column)=><td key={column}>{value}</td>)}</tr>)}</tbody></table></div>}</Card>
}
