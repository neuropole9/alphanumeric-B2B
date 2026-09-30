import {useEffect,useState} from 'react'
import {useNavigate,useParams} from 'react-router-dom'
import {ArrowUpRight,Building2,Layers3,MapPin} from 'lucide-react'
import {api} from '../api/client'
import {Card,Empty,PageTitle,Status} from '../components/UI'
import {useAuth} from '../app/AuthContext'

export default function ProjectsPage(){
  const {workspace='lighting'}=useParams()
  const {user}=useAuth()
  const nav=useNavigate()
  const [rows,setRows]=useState<any[]>([])
  useEffect(()=>{api<any[]>(`/api/v1/projects?workspace=${workspace.toUpperCase()}`).then(setRows)},[workspace])

  return <>
    <PageTitle title={(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')?'Projects':'My Project'} subtitle={(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')?'Customer sites, buildings and project structure':'Projects explicitly assigned to your account'} badge={(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')?'Admin':'Project User'}/>
    {!rows.length?<Card><Empty text={(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')?'No projects found.':'No project has been assigned to your account.'}/></Card>:<div className="project-card-grid">
      {rows.map(p=><button type="button" className="project-card" key={p.id} onClick={()=>nav(p.customer?.id?`/app/${workspace}/customers/${p.customer.id}/projects/${p.id}`:`/app/${workspace}/projects/${p.id}`)}>
        <div className="project-card-head">
          <span className="project-card-icon"><Building2 size={21}/></span>
          <span className="project-card-title"><b>{p.name}</b><small>{p.customer.company_name}</small></span>
          <Status value={p.status}/>
        </div>
        <p className="project-location"><MapPin size={15}/><span>{[p.address,p.city,p.state].filter(Boolean).join(', ')||'Site location not added'}</span></p>
        <div className="project-card-stats">
          <span><b>{p.buildings}</b><small>Buildings</small></span>
          <span><b>{p.workspaces.length}</b><small>Systems</small></span>
          <span><Layers3 size={16}/><small>{p.workspaces.join(' + ')}</small></span>
        </div>
        <span className="project-card-open">Open project <ArrowUpRight size={16}/></span>
      </button>)}
    </div>}
  </>
}
