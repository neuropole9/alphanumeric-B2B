import {useEffect,useState} from 'react'
import {Building2,FileDigit,ShieldCheck} from 'lucide-react'
import {api} from '../api/client'
import {Card,PageTitle} from '../components/UI'

export default function SettingsPage(){
  const [s,setS]=useState<any>()
  useEffect(()=>{api('/api/v1/settings').then(setS)},[])
  if(!s)return <div className="loading">Loading settings...</div>
  return <>
    <PageTitle title="Settings" subtitle="Company, tax, document numbering and business defaults" badge="Admin"/>
    <div className="settings-grid">
      <Card className="settings-card"><div className="settings-card-head"><span><Building2 size={21}/></span><div><h3>Company Information</h3><p>Legal and contact identity</p></div></div><dl className="info-list"><div><dt>Company</dt><dd>{s.company_name}</dd></div><div><dt>GSTIN</dt><dd>{s.company_gstin}</dd></div><div><dt>PAN</dt><dd>{s.company_pan}</dd></div><div><dt>Address</dt><dd>{s.company_address}</dd></div><div><dt>Email</dt><dd>{s.company_email}</dd></div></dl></Card>
      <Card className="settings-card"><div className="settings-card-head"><span><FileDigit size={21}/></span><div><h3>Document Numbering</h3><p>Server-managed number sequences</p></div></div><dl className="info-list"><div><dt>Inquiry</dt><dd>ANIPL0001</dd></div><div><dt>Quotation</dt><dd>{s.quotation_prefix}-YYYY-0001</dd></div><div><dt>Order</dt><dd>{s.order_prefix}-YYYY-0001</dd></div><div><dt>Invoice</dt><dd>{s.invoice_prefix}-YYYY-0001</dd></div></dl></Card>
      <Card className="settings-card security-card"><div className="settings-card-head"><span><ShieldCheck size={21}/></span><div><h3>Security & Deployment</h3><p>Production configuration policy</p></div></div><p className="muted">Sensitive values remain environment-driven. Configure production secrets, tax data, bank details and TLS in the deployment environment.</p><div className="security-checks"><span>Environment secrets</span><span>HTTP-only sessions</span><span>CSRF protection</span><span>Role-based permissions</span></div></Card>
    </div>
  </>
}
