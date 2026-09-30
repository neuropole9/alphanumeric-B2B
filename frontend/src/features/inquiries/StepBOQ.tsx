import {Boxes,ClipboardCheck} from 'lucide-react'
import {Card,Empty,ProductImage} from '../../components/UI'
import type {Product} from '../../types'
import type {WizardData} from './inquiryWizard.types'

export function aggregate(data:WizardData){const map=new Map<string,{product_id:string;quantity:number;breakdown:Array<{floor:string;room:string;quantity:number}>}>();for(const f of data.floors)for(const r of f.rooms)for(const q of r.requirements){const x=map.get(q.product_id)||{product_id:q.product_id,quantity:0,breakdown:[]};x.quantity+=q.quantity;x.breakdown.push({floor:f.name,room:r.name,quantity:q.quantity});map.set(q.product_id,x)}return [...map.values()]}

export default function StepBOQ({data,products}:{data:WizardData;products:Product[]}){
  const rows=aggregate(data)
  const product=(id:string)=>products.find(x=>x.id===id)
  const total=rows.reduce((s,x)=>s+x.quantity,0)
  return <div className="boq-review">
    <Card className="wizard-surface">
      <div className="wizard-surface-head"><div><span className="eyebrow">Step 4 of 5</span><h2>BOQ Review</h2><p>Verify the room-level source data before submitting.</p></div><div className="boq-total-pill"><Boxes size={18}/><span><b>{total}</b><small>Total units</small></span></div></div>
      <div className="boq-floor-list">{data.floors.map(f=><section className="boq-floor" key={f.key}><div className="boq-floor-head"><div><h3>{f.name}</h3><small>{f.rooms.length} {f.rooms.length===1?'room':'rooms'}</small></div><b>{f.rooms.reduce((s,r)=>s+r.requirements.reduce((a,b)=>a+b.quantity,0),0)} units</b></div>{f.rooms.map(r=><div className="boq-room" key={r.key}><div className="boq-room-title"><b>{r.name}</b><small>{r.requirements.length} unique products</small></div>{!r.requirements.length?<span className="empty-room-copy">No products assigned</span>:<div className="boq-room-products">{r.requirements.map(q=>{const p=product(q.product_id);return <div className="boq-product-row" key={q.product_id}><ProductImage product={p} size={38}/><span><b>{p?.name}</b><small>{p?.variant_name||p?.sku} · {p?.workspace} · {p?.category}</small></span><strong>{q.quantity} <small>{p?.unit}</small></strong></div>})}</div>}</div>)}</section>)}</div>
    </Card>
    <Card className="aggregated-boq-card">
      <div className="section-head"><div><h2><ClipboardCheck size={21}/> Aggregated BOQ</h2><p>Combined quantities across every floor and room.</p></div><span className="unique-count">{rows.length} unique products</span></div>
      {!rows.length?<Empty text="Add products before submitting this inquiry."/>:<div className="table-wrap premium-table"><table><thead><tr><th>Product</th><th>SKU</th><th>System</th><th>Category</th><th>Total Quantity</th><th>Unit</th></tr></thead><tbody>{rows.map(r=>{const p=product(r.product_id);return <tr key={r.product_id}><td><div className="table-product"><ProductImage product={p} size={34}/><b>{p?.name}</b></div></td><td>{p?.sku}</td><td><span className={`system-chip ${(p?.workspace||'').toLowerCase()}`}>{p?.workspace}</span></td><td>{p?.category}</td><td><b className="quantity-total">{r.quantity}</b></td><td>{p?.unit}</td></tr>})}</tbody></table></div>}
    </Card>
  </div>
}
