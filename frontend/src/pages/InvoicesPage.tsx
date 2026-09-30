import {useEffect,useState} from 'react'
import {useNavigate,useParams} from 'react-router-dom'
import {ReceiptText} from 'lucide-react'
import {api} from '../api/client'
import type {Invoice} from '../types'
import {Card,Empty,PageTitle,Status,money} from '../components/UI'
import {useAuth} from '../app/AuthContext'

export default function InvoicesPage(){
  const {workspace='lighting'}=useParams()
  const {user}=useAuth()
  const nav=useNavigate()
  const [rows,setRows]=useState<Invoice[]>([])
  useEffect(()=>{api<Invoice[]>(`/api/v1/invoices?workspace=${workspace.toUpperCase()}`).then(setRows)},[workspace])
  return <>
    <PageTitle title="Invoices" subtitle="Tax invoices generated from customer orders" badge={(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')?'Admin':'User'}/>
    <Card className="table-card data-surface">
      <div className="section-head"><div><h2><ReceiptText size={20}/> Invoice Register</h2><p>Review issued invoices, due dates and payment status.</p></div><span className="record-count">{rows.length} records</span></div>
      {!rows.length?<Empty text="No invoices have been generated."/>:<div className="table-wrap"><table><thead><tr><th>Invoice No.</th><th>Customer</th><th>Order</th><th>Date</th><th>Due Date</th><th>Status</th><th>Grand Total</th></tr></thead><tbody>{rows.map(i=><tr key={i.id} onClick={()=>nav(`/app/${workspace}/invoices/${i.id}`)}><td className="linkish">{i.number}</td><td><b>{i.customer.company_name}</b></td><td>{i.order_number}</td><td>{i.invoice_date}</td><td>{i.due_date||'—'}</td><td><Status value={i.status}/></td><td className="amount-cell">{money(i.grand_total)}</td></tr>)}</tbody></table></div>}
    </Card>
  </>
}
