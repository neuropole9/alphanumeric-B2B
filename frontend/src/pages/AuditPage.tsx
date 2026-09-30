import {useEffect,useState} from 'react'
import {ShieldCheck} from 'lucide-react'
import {api} from '../api/client'
import {Card,Empty,PageTitle} from '../components/UI'

export default function AuditPage(){
  const [rows,setRows]=useState<any[]>([])
  useEffect(()=>{api<any[]>('/api/v1/audit-logs?limit=200').then(setRows)},[])
  return <>
    <PageTitle title="Audit Log" subtitle="Immutable history of critical business and security actions" badge="Admin"/>
    <Card className="table-card data-surface audit-surface">
      <div className="section-head"><div><h2><ShieldCheck size={20}/> Security & Activity History</h2><p>Latest 200 recorded actions across projects and commercial documents.</p></div><span className="record-count">{rows.length} events</span></div>
      {!rows.length?<Empty text="No audit activity has been recorded."/>:<div className="table-wrap"><table><thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Entity</th><th>Reference</th><th>Metadata</th></tr></thead><tbody>{rows.map(r=><tr key={r.id}><td className="date-cell">{new Date(r.created_at).toLocaleString()}</td><td><b>{r.actor}</b></td><td><span className="audit-action">{r.action.replaceAll('.',' · ').replaceAll('_',' ')}</span></td><td>{r.entity_type}</td><td><code>{r.entity_id?.slice(0,8)||'—'}</code></td><td><small className="metadata-cell">{JSON.stringify(r.metadata)}</small></td></tr>)}</tbody></table></div>}
    </Card>
  </>
}
