import {Boxes,Building2,DoorOpen,Handshake,Layers3,PackageCheck,UserRound} from 'lucide-react'
import {Card,ProductImage} from '../../components/UI'
import type {Customer,Product} from '../../types'
import type {WizardData} from './inquiryWizard.types'
import {aggregate} from './StepBOQ'

export default function StepReview({data,customers,products,inquiryNumber}:{data:WizardData;customers:Customer[];products:Product[];inquiryNumber?:string}){
  const rows=aggregate(data)
  const client=data.customerId==='__new__'?data.newCustomer:customers.find(x=>x.id===data.customerId)
  const qty=rows.reduce((s,x)=>s+x.quantity,0)
  const roomCount=data.floors.reduce((s,f)=>s+f.rooms.length,0)
  const product=(id:string)=>products.find(p=>p.id===id)
  return <div className="final-review">
    <div className="review-hero"><div><span className="eyebrow">Step 5 of 5</span><h2>Review Inquiry</h2><p>Confirm the complete project scope before creating the inquiry.</p></div><span className="ready-badge"><PackageCheck size={17}/> Ready for review</span></div>
    <div className="review-metrics">
      <Card><span className="metric-icon blue"><Boxes size={19}/></span><span><small>Unique Products</small><b>{rows.length}</b></span></Card>
      <Card><span className="metric-icon purple"><PackageCheck size={19}/></span><span><small>Total Quantity</small><b>{qty}</b></span></Card>
      <Card><span className="metric-icon green"><Layers3 size={19}/></span><span><small>Total Floors</small><b>{data.floors.length}</b></span></Card>
      <Card><span className="metric-icon orange"><DoorOpen size={19}/></span><span><small>Total Rooms</small><b>{roomCount}</b></span></Card>
    </div>
    <Card className="review-details-card">
      <div className="review-columns">
        <section className="review-section"><div className="review-section-title"><Building2 size={18}/><h3>Project Details</h3></div><dl className="info-list"><div><dt>Inquiry</dt><dd><span className="document-chip">{inquiryNumber||'Generated automatically'}</span></dd></div><div><dt>Project</dt><dd>{data.projectName}</dd></div><div><dt>Site</dt><dd>{[data.address,data.city,data.state].filter(Boolean).join(', ')}</dd></div><div><dt>Building</dt><dd>{data.buildingName}</dd></div></dl></section>
        <section className="review-section"><div className="review-section-title"><UserRound size={18}/><h3>Client Details</h3></div><dl className="info-list"><div><dt>Client</dt><dd>{client?.company_name||'—'}</dd></div><div><dt>Phone</dt><dd>{client?.phone||'—'}</dd></div><div><dt>Email</dt><dd>{client?.email||'—'}</dd></div></dl></section>
        <section className="review-section partner-review"><div className="review-section-title"><Handshake size={18}/><h3>Partner</h3></div>{data.partnerEnabled?<dl className="info-list"><div><dt>Business</dt><dd>{data.partner.business_name}</dd></div><div><dt>Mobile</dt><dd>{data.partner.mobile}</dd></div><div><dt>Email</dt><dd>{data.partner.email}</dd></div><div><dt>Address</dt><dd>{data.partner.address}</dd></div></dl>:<div className="no-partner"><Handshake size={18}/><span>No partner linked to this project</span></div>}</section>
      </div>
    </Card>
    <Card><div className="section-head"><div><h2>Floor Summary</h2><p>Rooms and total assigned quantities by floor.</p></div></div><div className="floor-summary-grid">{data.floors.map((f,i)=><div className="floor-summary-card" key={f.key}><span className="floor-summary-index">{i+1}</span><div><b>{f.name}</b><small>{f.rooms.length} {f.rooms.length===1?'room':'rooms'}</small></div><strong>{f.rooms.reduce((s,r)=>s+r.requirements.reduce((a,b)=>a+b.quantity,0),0)}<small>units</small></strong></div>)}</div></Card>
    <Card><div className="section-head"><div><h2>Room Product Overview</h2><p>Final room-by-room allocation.</p></div></div><div className="review-room-list">{data.floors.map(f=><section className="review-floor" key={f.key}><div className="review-floor-head"><Layers3 size={17}/><b>{f.name}</b><span>{f.rooms.length} rooms</span></div>{f.rooms.map(r=><div className="review-room-row" key={r.key}><span className="review-room-name"><DoorOpen size={15}/><b>{r.name}</b></span><div className="review-room-products">{r.requirements.length?r.requirements.map(q=><span key={q.product_id}><ProductImage product={product(q.product_id)} size={28}/><span>{product(q.product_id)?.name||'Product'} <b>× {q.quantity}</b></span></span>):<em>No products assigned</em>}</div></div>)}</section>)}</div></Card>
    <Card className="review-total-card"><div className="section-head"><div><h2>Product Total / BOQ</h2><p>Final aggregated quantities.</p></div><span className="unique-count">{qty} total units</span></div><div className="review-total-grid">{rows.map(r=>{const p=product(r.product_id);return <div className="review-total-row" key={r.product_id}><ProductImage product={p} size={36}/><span><b>{p?.name}</b><small>{p?.variant_name||p?.sku} · {p?.workspace}</small></span><strong>{r.quantity}<small>{p?.unit}</small></strong></div>})}</div></Card>
  </div>
}
