import {useEffect,useState} from 'react'
import {useNavigate,useParams} from 'react-router-dom'
import {FileCheck2} from 'lucide-react'
import {api} from '../api/client'
import type {Quotation} from '../types'
import {Card,Empty,PageTitle,Status,money} from '../components/UI'
import {useAuth} from '../app/AuthContext'

export default function QuotationsPage(){
  const {workspace='lighting'}=useParams()
  const {user}=useAuth()
  const nav=useNavigate()
  const [rows,setRows]=useState<Quotation[]>([])
  useEffect(()=>{api<Quotation[]>(`/api/v1/quotations?workspace=${workspace.toUpperCase()}`).then(setRows)},[workspace])
  return <>
    <PageTitle title="Quotations" subtitle="Prepare, review and manage commercial quotations" badge={(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')?'Admin':'User'}/>
    <Card className="table-card data-surface">
      <div className="section-head"><div><h2><FileCheck2 size={20}/> Commercial Quotations</h2><p>Pricing documents generated from project inquiries.</p></div><span className="record-count">{rows.length} records</span></div>
      {!rows.length?<Empty text="No quotations have been generated."/>:<div className="table-wrap"><table><thead><tr><th>Quotation</th><th>Customer</th><th>Project</th><th>Date</th><th>Valid Until</th><th>Status</th><th>Grand Total</th></tr></thead><tbody>{rows.map(q=><tr key={q.id} onClick={()=>nav(`/app/${workspace}/quotations/${q.id}`)}><td className="linkish">{q.number}</td><td><b>{q.customer.company_name}</b></td><td>{q.project.name}</td><td>{q.quotation_date}</td><td>{q.valid_until||'—'}</td><td><Status value={q.status}/></td><td className="amount-cell">{money(q.grand_total)}</td></tr>)}</tbody></table></div>}
    </Card>
  </>
}
