import {useEffect,useMemo,useState} from 'react'
import type {ReactNode} from 'react'
import {useNavigate,useParams,useSearchParams} from 'react-router-dom'
import {ChevronDown,ChevronRight,Download,Eye,FileSpreadsheet,Layers3,MapPin} from 'lucide-react'
import {api,receiveServerFile} from '../api/client'
import type {BuildingDetail,ProjectDetail} from '../types'
import {Breadcrumbs,Button,Card,Empty,Notice,PageTitle,Status,money} from '../components/UI'
import {useAuth} from '../app/AuthContext'

type Tab='overview'|'floors'|'products'|'mainboards'|'documents'|'users'|'inquiries'|'quotations'|'orders'|'invoices'|'activity'|'downloads'
const tabs:Tab[]=['overview','floors','products','mainboards','documents']

export default function BuildingDetailPage(){
  const {workspace='lighting',customerId,id:projectId,buildingId}=useParams()
  const {user}=useAuth()
  const navigate=useNavigate()
  const [search,setSearch]=useSearchParams()
  const tab=(tabs.includes(search.get('tab') as Tab)?search.get('tab'):'overview') as Tab
  const [data,setData]=useState<BuildingDetail>()
  const [project,setProject]=useState<ProjectDetail>()
  const [openFloors,setOpenFloors]=useState<Record<string,boolean>>({})
  const [busy,setBusy]=useState<string>()
  const [error,setError]=useState<string>()
  useEffect(()=>{
    Promise.all([
      api<BuildingDetail>(`/api/v1/projects/${projectId}/buildings/${buildingId}?workspace=${workspace.toUpperCase()}`),
      api<ProjectDetail>(`/api/v1/projects/${projectId}?workspace=${workspace.toUpperCase()}`),
    ]).then(([building,projectData])=>{setData(building);setProject(projectData)}).catch(reason=>setError(reason.message))
  },[buildingId,projectId,workspace])
  const customerRoute=customerId||data?.customer.id
  const projectBase=customerRoute?`/app/${workspace}/customers/${customerRoute}/projects/${projectId}`:`/app/${workspace}/projects/${projectId}`
  const roomRoute=(floorId:string,roomId:string)=>`${projectBase}/buildings/${buildingId}/floors/${floorId}/rooms/${roomId}`
  const runFile=async(action:string,path:string,mode:'preview'|'download')=>{const scoped=`${path}${path.includes('?')?'&':'?'}workspace=${workspace.toUpperCase()}`;setBusy(action);setError(undefined);try{await receiveServerFile(scoped,mode)}catch(reason){setError(reason instanceof Error?reason.message:'The file could not be generated.')}finally{setBusy(undefined)}}
  const roomTotals=useMemo(()=>data?.floors.flatMap(floor=>floor.rooms)||[],[data])
  const boq=useMemo(()=>{
    const rows=new Map<string,{id:string;name:string;sku:string;workspace:string;category:string;unit:string;quantity:number;rate?:number;tax:number;breakdown:string[]}>()
    const building=project?.buildings.find(item=>item.id===buildingId)
    for(const floor of building?.floors||[])for(const room of floor.rooms)for(const req of room.requirements){const p=req.product;const row=rows.get(p.id)||{id:p.id,name:p.name,sku:p.sku,workspace:p.workspace,category:p.category,unit:req.unit||p.unit,quantity:0,rate:p.price,tax:p.tax_rate,breakdown:[]};row.quantity+=Number(req.quantity);row.breakdown.push(`${floor.name} / ${room.name}: ${req.quantity} ${row.unit}`);rows.set(p.id,row)}
    return [...rows.values()]
  },[project,buildingId])
  if(error&&!data)return <Card><Notice kind="error">{error}</Notice><Button onClick={()=>location.reload()}>Retry</Button></Card>
  if(!data||!project)return <div className="loading">Loading building workspace…</div>
  const b=data.building
  const setTab=(next:Tab)=>setSearch({tab:next},{replace:false})
  const path=`/api/v1/projects/${projectId}/buildings/${buildingId}`

  return <>
    <Breadcrumbs items={[
      {label:'Customers',to:`/app/${workspace}/customers`},
      {label:data.customer.company_name,to:`/app/${workspace}/customers/${data.customer.id}`},
      {label:data.project.name,to:projectBase},
      {label:b.name},
    ]}/>
    <PageTitle title={b.name} subtitle={`${data.project.name} · ${b.building_type||'Building'} · ${b.code||'No building code'}`} badge={(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')?'Admin':'Project User'} actions={<>
      <Button variant="secondary" onClick={()=>navigate(`${projectBase}/buildings/${buildingId}/documents`)}>Plans & Documents</Button>
      <Button variant="secondary" disabled={Boolean(busy)} onClick={()=>runFile('preview',`${path}/book.pdf`,'preview')}><Eye size={16}/>{busy==='preview'?'Preparing…':'Preview Book'}</Button>
      <Button variant="secondary" disabled={Boolean(busy)} onClick={()=>runFile('pdf',`${path}/book.pdf?download=true`,'download')}><Download size={16}/>{busy==='pdf'?'Preparing…':'Download PDF'}</Button>
      <Button disabled={Boolean(busy)} onClick={()=>runFile('excel',`${path}/boq.xlsx`,'download')}><FileSpreadsheet size={16}/>{busy==='excel'?'Preparing…':'Download BOQ'}</Button>
    </>}/>
    {error&&<Notice kind="error">{error}</Notice>}
    <div className="detail-kpis three">
      <Card><small>Floors</small><h3>{data.stats.floors}</h3></Card><Card><small>Rooms</small><h3>{data.stats.rooms}</h3></Card><Card><small>Main Boards</small><h3>{data.stats.main_boards}</h3></Card>
    </div>
    <div className="detail-tabs" role="tablist" aria-label="Building sections">{tabs.map(value=><button type="button" role="tab" aria-selected={tab===value} key={value} className={tab===value?'active':''} onClick={()=>setTab(value)}>{value==='floors'?'Floors & Rooms':value==='products'?'Products / BOQ':value==='mainboards'?'Main Boards':value==='documents'?'Plans & Documents':value[0].toUpperCase()+value.slice(1)}</button>)}</div>

    {tab==='overview'&&<div className="building-overview-grid">
      <Card><h3>Building Information</h3><dl className="info-list"><div><dt>Customer</dt><dd>{data.customer.company_name}</dd></div><div><dt>Project</dt><dd>{data.project.name}</dd></div><div><dt>Building</dt><dd>{b.name}</dd></div><div><dt>Code</dt><dd>{b.code||'—'}</dd></div><div><dt>Type</dt><dd>{b.building_type||'—'}</dd></div><div><dt>Status</dt><dd><Status value={b.status}/></dd></div><div><dt>Location</dt><dd>{b.address||data.project.address||'—'}</dd></div></dl></Card>
      <Card><h3>Physical Configuration</h3><dl className="info-list"><div><dt>Floors</dt><dd>{data.stats.floors}</dd></div><div><dt>Rooms</dt><dd>{data.stats.rooms}</dd></div><div><dt>Main boards</dt><dd>{data.stats.main_boards}</dd></div><div><dt>Unique products</dt><dd>{data.stats.unique_products}</dd></div><div><dt>Total quantity</dt><dd>{data.stats.product_quantity}</dd></div></dl></Card>
      <Card><h3>Ownership & Scope</h3><dl className="info-list"><div><dt>Internal owner</dt><dd>{data.project.owner?.name||'Not assigned'}</dd></div><div><dt>Partner</dt><dd>{data.project.partner?.business_name||'No Partner'}</dd></div><div><dt>Systems</dt><dd>{data.project.workspaces.join(' · ')||'—'}</dd></div><div><dt>Last updated</dt><dd>{b.updated_at?new Date(b.updated_at).toLocaleString():'—'}</dd></div></dl></Card>
      <Card className="building-progress-card"><h3>Configuration Coverage</h3><div className="coverage-ring"><strong>{data.stats.rooms?Math.round(roomTotals.filter(room=>room.configuration_status==='CONFIGURED').length/data.stats.rooms*100):0}%</strong><span>rooms configured</span></div><p className="muted">A room is configured after at least one exact product variant has been selected.</p></Card>
    </div>}

    {tab==='floors'&&<Card><div className="section-head"><div><h2><Layers3 size={20}/> Floors & Rooms</h2><p>Expand a floor to see every room, product quantity, board count, and configuration state.</p></div></div>{!data.floors.length?<Empty text="No floors are configured for this building."/>:<div className="building-floor-list">{data.floors.map(floor=><section className="building-floor" key={floor.id}><button type="button" className="building-floor-head" onClick={()=>setOpenFloors(value=>({...value,[floor.id]:!value[floor.id]}))}>{openFloors[floor.id]?<ChevronDown size={18}/>:<ChevronRight size={18}/>}<span><b>{floor.name}</b><small>Floor {floor.sort_order+1}</small></span><div className="floor-stat-strip"><span><b>{floor.room_count}</b><small>Rooms</small></span><span><b>{floor.main_board_count}</b><small>Boards</small></span><span><b>{floor.unique_product_count}</b><small>Products</small></span><span><b>{floor.product_quantity}</b><small>Quantity</small></span></div><Status value={floor.configuration_status}/></button>{openFloors[floor.id]&&<div className="building-room-grid">{floor.rooms.map(room=><button type="button" className="building-room-card" key={room.id} onClick={()=>navigate(roomRoute(floor.id,room.id))}><div className="room-card-title"><span><b>{room.name}</b><small>{room.room_type||'Room'}</small></span><ChevronRight size={17}/></div><div className="room-card-meta"><span>{room.main_board_count||0}<small>Main boards</small></span><span>{room.unique_product_count||0}<small>Products</small></span><span>{room.product_quantity}<small>Quantity</small></span></div><div className="room-card-footer"><Status value={room.configuration_status||'NOT_CONFIGURED'}/><span>Open Room</span></div></button>)}</div>}</section>)}</div>}</Card>}

    {tab==='products'&&<Card className="table-card"><div className="section-head"><div><h2>Building Products / BOQ</h2><p>Aggregated by exact variant and SKU from persisted room selections in this building.</p></div><Button onClick={()=>runFile('excel',`${path}/boq.xlsx`,'download')} disabled={Boolean(busy)}><FileSpreadsheet size={16}/> Export Excel</Button></div><div className="boq-callout"><span><b>{boq.length}</b><small>Unique variants</small></span><span><b>{boq.reduce((sum,row)=>sum+row.quantity,0)}</b><small>Total units</small></span><span><b>{data.stats.rooms}</b><small>Rooms in scope</small></span></div>{!boq.length?<Empty text="No products are assigned to rooms in this building. Add them through the inquiry wizard or room configuration."/>:<div className="table-wrap"><table><thead><tr><th>Product</th><th>SKU</th><th>System</th><th>Category</th><th>Unit</th>{(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')&&<><th>Rate</th><th>Tax</th></>}<th>Quantity</th><th>Floor / room breakdown</th></tr></thead><tbody>{boq.map(row=><tr key={row.id}><td><b>{row.name}</b></td><td>{row.sku}</td><td><Status value={row.workspace}/></td><td>{row.category}</td><td>{row.unit}</td>{(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')&&<><td>{money(row.rate)}</td><td>{row.tax}%</td></>}<td>{row.quantity}</td><td>{row.breakdown.map(value=><small className="breakdown-line" key={value}>{value}</small>)}</td></tr>)}</tbody></table></div>}</Card>}

    {tab==='mainboards'&&<Card className="table-card"><div className="section-head"><div><h2>Main Boards</h2><p>Electrical boards physically configured inside this building.</p></div></div>{!data.main_boards.length?<Empty text="No main boards are configured for this building."/>:<div className="table-wrap"><table><thead><tr><th>Name</th><th>Code</th><th>Type</th><th>System</th><th>Quantity</th><th>Notes</th></tr></thead><tbody>{data.main_boards.map(board=><tr key={board.id}><td><b>{board.name}</b></td><td>{board.code||'—'}</td><td>{board.board_type}</td><td>{board.system}</td><td>{board.quantity}</td><td>{board.notes||'—'}</td></tr>)}</tbody></table></div>}</Card>}

    {tab==='documents'&&<div className="download-grid"><DownloadCard title="Plans & Documents" text="Upload and review project, building and floor plan files in one place." preview={()=>navigate(`${projectBase}/buildings/${buildingId}/documents`)} download={()=>navigate(`${projectBase}/buildings/${buildingId}/documents`)}/><DownloadCard title="Building Book" text="Building, floor, room, board and product configuration." preview={()=>runFile('preview',`${path}/book.pdf`,'preview')} download={()=>runFile('pdf',`${path}/book.pdf?download=true`,'download')}/><DownloadCard title="Building BOQ" text="Exact product-variant quantities in Excel format." download={()=>runFile('excel',`${path}/boq.xlsx`,'download')}/></div>}

    {tab==='users'&&<Card className="table-card"><div className="section-head"><div><h2>Project Users</h2><p>Access applies to the full project, including this building.</p></div></div>{!project.users.length?<Empty text="No customer users are assigned to this project."/>:<div className="table-wrap"><table><thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Role</th><th>Status</th><th>Last Login</th></tr></thead><tbody>{project.users.map(item=><tr key={item.id}><td><b>{item.user.name}</b></td><td>{item.user.email}</td><td>{item.user.phone||'—'}</td><td>{item.role}</td><td><Status value={item.status}/></td><td>{item.user.last_login?new Date(item.user.last_login).toLocaleString():'Never'}</td></tr>)}</tbody></table></div>}</Card>}

    {tab==='inquiries'&&<RecordTable empty="No inquiries cover this building." headers={['Inquiry','Building scope','Created','Status']} rows={data.inquiries.map(item=>[item.number,item.building_scope,new Date(item.created_at).toLocaleDateString(),<Status value={item.status}/>])} onOpen={index=>navigate(`/app/${workspace}/inquiries/${data.inquiries[index].id}`)}/>} 
    {tab==='quotations'&&<RecordTable empty="No quotations cover this building." headers={['Quotation','Inquiry','Date','Status','Total']} rows={data.quotations.map(item=>[item.number,project.inquiries.find(value=>value.id===item.inquiry_id)?.number||'—',item.quotation_date,<Status value={item.status}/>,(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')?money(item.grand_total):'Available in document'])} onOpen={index=>navigate(`/app/${workspace}/quotations/${data.quotations[index].id}`)}/>} 
    {tab==='orders'&&<RecordTable empty="No orders cover this building." headers={['Order','Date','Delivery','Status','Total']} rows={data.orders.map(item=>[item.number,item.order_date,item.delivery_date||'—',<Status value={item.status}/>,(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')?money(item.grand_total):'Available in document'])} onOpen={index=>navigate(`/app/${workspace}/orders/${data.orders[index].id}`)}/>} 
    {tab==='invoices'&&<RecordTable empty="No invoices cover this building." headers={['Invoice','Order','Date','Due','Status','Total']} rows={data.invoices.map(item=>[item.number,item.order_number,item.invoice_date,item.due_date||'—',<Status value={item.status}/>,(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')?money(item.grand_total):'Available in document'])} onOpen={index=>navigate(`/app/${workspace}/invoices/${data.invoices[index].id}`)}/>} 
    {tab==='activity'&&<Card><h2>Recent Project Activity</h2>{!project.activity?.length?<Empty text="No activity has been recorded."/>:<div className="activity-timeline">{project.activity.map(item=><div key={item.id}><span><b>{item.action.replaceAll('.',' · ').replaceAll('_',' ')}</b><small>{item.actor} · {new Date(item.created_at).toLocaleString()}</small></span></div>)}</div>}</Card>}
    {tab==='downloads'&&<div className="download-grid"><DownloadCard title="Building Book" text="Branded customer, project, floor, room, product, BOQ, board, and commercial summary." preview={()=>runFile('preview',`${path}/book.pdf`,'preview')} download={()=>runFile('pdf',`${path}/book.pdf?download=true`,'download')}/><DownloadCard title="Building BOQ" text="Exact product-variant quantities in a filterable Excel workbook." download={()=>runFile('excel',`${path}/boq.xlsx`,'download')}/><DownloadCard title="Project Book" text="All buildings and current project configuration in one authorized PDF." preview={()=>runFile('project-preview',`/api/v1/projects/${projectId}/book.pdf`,'preview')} download={()=>runFile('project-pdf',`/api/v1/projects/${projectId}/book.pdf?download=true`,'download')}/></div>}
  </>
}

function RecordTable({headers,rows,empty,onOpen}:{headers:string[];rows:ReactNode[][];empty:string;onOpen:(index:number)=>void}){
  return <Card className="table-card">{!rows.length?<Empty text={empty}/>:<div className="table-wrap"><table><thead><tr>{headers.map(header=><th key={header}>{header}</th>)}</tr></thead><tbody>{rows.map((row,index)=><tr key={index} onClick={()=>onOpen(index)}>{row.map((value,column)=><td key={column}>{value}</td>)}</tr>)}</tbody></table></div>}</Card>
}

function DownloadCard({title,text,preview,download}:{title:string;text:string;preview?:()=>void;download:()=>void}){
  return <Card className="download-card"><span className="download-card-icon"><Download size={22}/></span><h3>{title}</h3><p>{text}</p><div className="button-row">{preview&&<Button variant="secondary" onClick={preview}><Eye size={15}/> Preview</Button>}<Button onClick={download}><Download size={15}/> Download</Button></div></Card>
}
