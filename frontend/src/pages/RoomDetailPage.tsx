import {useEffect,useMemo,useState} from 'react'
import {Download,Plus,Search,SlidersHorizontal,X} from 'lucide-react'
import {useParams} from 'react-router-dom'
import {api,del,patch,post,receiveServerFile} from '../api/client'
import {useAuth} from '../app/AuthContext'
import {Breadcrumbs,Button,Card,Empty,Modal,Notice,PageTitle,ProductImage,Status} from '../components/UI'
import type {PaginatedFamilies,Product,ProductFamily,RoomDetail} from '../types'

type Pick={family:ProductFamily;variant:Product}

export default function RoomDetailPage(){
  const {customerId,id,buildingId,floorId,roomId,workspace='lighting'}=useParams()
  const {user}=useAuth()
  const [detail,setDetail]=useState<RoomDetail>()
  const [families,setFamilies]=useState<ProductFamily[]>([])
  const [picker,setPicker]=useState(false)
  const [selected,setSelected]=useState<Pick>()
  const [query,setQuery]=useState('')
  const [quantity,setQuantity]=useState(1)
  const [notes,setNotes]=useState('')
  const [notice,setNotice]=useState<{kind:'success'|'error';text:string}>()
  const [busy,setBusy]=useState(false)
  const [removeId,setRemoveId]=useState<string>()

  const load=()=>api<RoomDetail>(`/api/v1/rooms/${roomId}`).then(setDetail)
  useEffect(()=>{load().catch(e=>setNotice({kind:'error',text:e.message}))},[roomId])
  useEffect(()=>{if(!picker)return;api<PaginatedFamilies>(`/api/v1/product-families?workspace=${workspace.toUpperCase()}&page_size=100`).then(x=>setFamilies(x.items)).catch(e=>setNotice({kind:'error',text:e.message}))},[picker,workspace])
  const shown=useMemo(()=>families.filter(f=>!query||`${f.name} ${f.brand} ${f.category} ${f.variants?.map(v=>v.sku).join(' ')}`.toLowerCase().includes(query.toLowerCase())),[families,query])
  const revealVariants=async(family:ProductFamily)=>{
    if(family.variants?.length)return
    try{const detailed=await api<ProductFamily>(`/api/v1/product-families/${family.id}`);setFamilies(current=>current.map(item=>item.id===detailed.id?detailed:item))}
    catch(e:any){setNotice({kind:'error',text:e.message})}
  }

  if(!detail)return <div className="loading">Loading room workspace...</div>
  const customer=customerId||detail.customer.id
  const project=id||detail.project.id
  const building=buildingId||detail.building.id
  const floor=floorId||detail.floor.id
  const room=roomId||detail.room.id
  const base=`/app/${workspace}/customers/${customer}/projects/${project}`
  const closePicker=()=>{setPicker(false);setSelected(undefined);setQuantity(1);setNotes('');setQuery('')}
  const propose=async()=>{
    if(!selected||busy)return
    setBusy(true)
    try{
      await post(`/api/v1/rooms/${room}/product-proposals`,{product_id:selected.variant.id,quantity,notes:notes||undefined,recommendation:notes||undefined,send_to_customer:true})
      setNotice({kind:'success',text:`${selected.variant.name} was sent to the customer for approval.`})
      closePicker();await load()
    }catch(e:any){setNotice({kind:'error',text:e.message})}finally{setBusy(false)}
  }
  const remove=async(selectionId:string)=>{
    if(selectionId.startsWith('legacy:')){setNotice({kind:'error',text:'This product belongs to a submitted inquiry and must be edited from that inquiry.'});return}
    setRemoveId(selectionId)
  }
  const confirmRemove=async()=>{if(!removeId)return;try{await del(`/api/v1/rooms/${room}/products/${removeId}`);setNotice({kind:'success',text:'Room product removed.'});setRemoveId(undefined);await load()}catch(e:any){setNotice({kind:'error',text:e.message})}}
  const decide=async(proposalId:string,decision:'APPROVED'|'REJECTED')=>{setBusy(true);try{await patch(`/api/v1/product-proposals/${proposalId}/decision`,{decision});setNotice({kind:'success',text:decision==='APPROVED'?'Proposal approved and added to the room.':'Proposal rejected; room products were unchanged.'});await load()}catch(e:any){setNotice({kind:'error',text:e.message})}finally{setBusy(false)}}

  return <>
    <Breadcrumbs items={[
      {label:'Customers',to:`/app/${workspace}/customers`},
      {label:detail.customer.company_name,to:`/app/${workspace}/customers/${customer}`},
      {label:detail.project.name,to:base},
      {label:detail.building.name,to:`${base}/buildings/${building}`},
      {label:detail.floor.name,to:`${base}/buildings/${building}?tab=floors`},
      {label:detail.room.name},
    ]}/>
    <PageTitle title={detail.room.name} subtitle={`${detail.room.room_type||'Room'} · ${detail.floor.name} · ${detail.building.name}`} badge={detail.room.configuration_status.replaceAll('_',' ')} actions={<>
      <Button variant="secondary" onClick={()=>receiveServerFile(`/api/v1/projects/${project}/buildings/${building}/rooms/${room}/sheet.pdf?workspace=${workspace.toUpperCase()}`,'download').catch(e=>setNotice({kind:'error',text:e.message}))}><Download size={16}/> Room Sheet</Button>
      {(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')&&<Button onClick={()=>setPicker(true)}><Plus size={16}/> Propose Product</Button>}
    </>}/>
    {notice&&<Notice kind={notice.kind}>{notice.text}</Notice>}
    <div className="room-overview-grid">
      <Card><h3>Room information</h3><dl className="info-list"><div><dt>Type</dt><dd>{detail.room.room_type||'—'}</dd></div><div><dt>Area</dt><dd>{detail.room.area==null?'—':`${detail.room.area} m²`}</dd></div><div><dt>Occupancy</dt><dd>{detail.room.occupancy??'—'}</dd></div><div><dt>Notes</dt><dd>{detail.room.notes||'—'}</dd></div></dl></Card>
      <Card><h3>Configuration</h3><div className="room-metrics"><span><b>{detail.products.length}</b>product variants</span><span><b>{detail.products.reduce((sum,item)=>sum+item.quantity,0)}</b>total units</span><span><b>{detail.main_boards.reduce((sum,item)=>sum+item.quantity,0)}</b>main boards</span></div></Card>
      <Card><h3>Main boards</h3>{detail.main_boards.length?<div className="compact-list">{detail.main_boards.map(board=><div key={board.id}><span><b>{board.name}</b><small>{board.code||board.board_type} · {board.system}</small></span><strong>× {board.quantity}</strong></div>)}</div>:<p className="muted">No room- or floor-level board is assigned.</p>}</Card>
    </div>
    <Card>
      <div className="section-head"><div><h2>Room products</h2><p>Exact variants approved for this room.</p></div>{(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')&&<Button onClick={()=>setPicker(true)}><Plus size={16}/> Add proposal</Button>}</div>
      {!detail.products.length?<Empty text="No products have been approved for this room." action={(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')?<Button onClick={()=>setPicker(true)}>Browse catalogue</Button>:undefined}/>:<div className="room-product-grid">{detail.products.map(item=><article className="room-product-card" key={item.id}>
        <ProductImage product={item.product} size={112}/><div className="room-product-copy"><div><span className={`system-chip ${item.product.workspace.toLowerCase()}`}>{item.product.workspace}</span><Status value={item.approval_status}/></div><h3>{item.product.name}</h3><p>{item.product.variant_name||item.product.sku}</p><small>{item.product.category} · {item.product.sku}</small>{item.notes&&<em>{item.notes}</em>}</div><div className="room-product-qty"><strong>{item.quantity}</strong><span>{item.unit}</span>{(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')&&<Button variant="danger" onClick={()=>remove(item.id)}><X size={15}/> Remove</Button>}</div>
      </article>)}</div>}
    </Card>
    {!!detail.proposals.length&&<Card><div className="section-head"><div><h2>{(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')?'Proposal history':'Product approvals'}</h2><p>{(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')?'Auditable suitability decisions for this room.':'Approve or reject product recommendations sent by the project team.'}</p></div></div><div className="proposal-list">{detail.proposals.map(item=><div key={item.id}><ProductImage product={item.product} size={48}/><span><b>{item.product.name}</b><small>{item.product.variant_name||item.product.sku} · {new Date(item.proposed_at).toLocaleString()}</small></span><strong>{item.quantity} {item.unit}</strong><Status value={item.status}/>{user?.role!=='ADMIN'&&item.status==='PENDING_CUSTOMER'&&<span className="button-row"><Button variant="danger" disabled={busy} onClick={()=>decide(item.id,'REJECTED')}>Reject</Button><Button disabled={busy} onClick={()=>decide(item.id,'APPROVED')}>Approve</Button></span>}</div>)}</div></Card>}
    <Modal open={picker} title={selected?`${selected.family.name} · ${selected.variant.variant_name||selected.variant.sku}`:`Choose a product for ${detail.room.name}`} onClose={closePicker} className="room-proposal-modal" footer={selected?<><Button variant="secondary" onClick={()=>setSelected(undefined)}>Back to catalogue</Button><Button disabled={busy||quantity<1} onClick={propose}>Send for customer approval</Button></>:<Button variant="secondary" onClick={closePicker}>Cancel</Button>}>
      {!selected?<><label className="picker-search"><Search size={17}/><input autoFocus value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search name, brand, category, or SKU"/></label>{!shown.length?<Empty text="No catalogue products match your search."/>:<div className="family-picker-grid">{shown.map(f=><article key={f.id} className="family-picker-card"><ProductImage family={f} size={96}/><div><small>{f.brand} · {f.category}</small><h3>{f.name}</h3><p>{f.short_description||'Select an exact product variant.'}</p><div className="variant-buttons">{f.variants?.length?f.variants.map(v=><button type="button" key={v.id} disabled={v.status!=='ACTIVE'} onClick={()=>setSelected({family:f,variant:v})}><b>{v.variant_name||v.name}</b><span>{v.sku} · {v.available} {v.unit}</span></button>):<button type="button" onClick={()=>revealVariants(f)}><b>Choose a variant</b><span>{f.variant_count} available option{f.variant_count===1?'':'s'}</span></button>}</div></div></article>)}</div>}</>:<div className="proposal-confirm"><div className="proposal-preview"><ProductImage product={selected.variant} family={selected.family} size={220}/><div><span className={`system-chip ${selected.variant.workspace.toLowerCase()}`}>{selected.variant.workspace}</span><h2>{selected.family.name}</h2><h3>{selected.variant.variant_name||selected.variant.name}</h3><p>{selected.variant.description||selected.family.full_description||selected.family.short_description}</p><dl className="info-list"><div><dt>SKU</dt><dd>{selected.variant.sku}</dd></div><div><dt>Category</dt><dd>{selected.family.category}</dd></div><div><dt>Availability</dt><dd>{selected.variant.available} {selected.variant.unit}</dd></div></dl></div></div><div className="suitability-question"><SlidersHorizontal size={22}/><div><h3>Recommend this product?</h3><p>The customer project user will make the final approval decision. The room is unchanged until approval.</p></div></div><div className="form-grid two"><label>Quantity<input type="number" min="1" value={quantity} onChange={e=>setQuantity(Math.max(1,Number(e.target.value)))}/></label><label>Recommendation / placement notes<input value={notes} onChange={e=>setNotes(e.target.value)} placeholder="Why this variant suits the room"/></label></div></div>}
    </Modal>
    <Modal open={Boolean(removeId)} title="Remove room product?" onClose={()=>setRemoveId(undefined)} footer={<><Button variant="secondary" onClick={()=>setRemoveId(undefined)}>Cancel</Button><Button variant="danger" onClick={confirmRemove}>Remove product</Button></>}><p>This removes the selected room configuration. The action is recorded in the audit log.</p></Modal>
  </>
}
