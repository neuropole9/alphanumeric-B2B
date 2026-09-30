import {useEffect,useState} from 'react'
import {useNavigate,useParams} from 'react-router-dom'
import {ArrowUpRight,Building2,Mail,MapPin,Phone,Search,Users} from 'lucide-react'
import {api} from '../api/client'
import type {Customer} from '../types'
import {Button,Card,Empty,Notice,PageTitle,Status} from '../components/UI'

export default function CustomersPage(){
  const navigate=useNavigate()
  const {workspace='lighting'}=useParams()
  const [rows,setRows]=useState<Customer[]>([])
  const [query,setQuery]=useState('')
  const [status,setStatus]=useState('')
  const [loading,setLoading]=useState(true)
  const [error,setError]=useState<string>()
  const load=()=>{setLoading(true);setError(undefined);const params=new URLSearchParams({page_size:'200'});if(query.trim())params.set('q',query.trim());if(status)params.set('status',status);api<Customer[]>(`/api/v1/customers?${params}`).then(setRows).catch(reason=>setError(reason.message)).finally(()=>setLoading(false))}
  useEffect(()=>{const timer=setTimeout(load,250);return()=>clearTimeout(timer)},[query,status])
  const active=rows.filter(customer=>customer.status==='ACTIVE').length

  return <>
    <PageTitle title="Customers" subtitle="Customer accounts, projects, buildings, and commercial history" badge="Admin"/>
    <div className="directory-summary"><Card><span className="summary-icon blue"><Users size={20}/></span><div><small>Matching customers</small><b>{rows.length}</b></div></Card><Card><span className="summary-icon green"><Building2 size={20}/></span><div><small>Active relationships</small><b>{active}</b></div></Card></div>
    <Card className="customer-filter-bar"><label className="search-field"><Search size={17}/><input value={query} onChange={event=>setQuery(event.target.value)} placeholder="Search company, contact, phone, email, GSTIN, project, or city…" aria-label="Search customers"/></label><select value={status} onChange={event=>setStatus(event.target.value)} aria-label="Customer status"><option value="">All statuses</option><option value="ACTIVE">Active</option><option value="INACTIVE">Inactive</option></select>{(query||status)&&<Button variant="secondary" onClick={()=>{setQuery('');setStatus('')}}>Clear filters</Button>}</Card>
    {error&&<Notice kind="error">{error} <button className="link-button" type="button" onClick={load}>Retry</button></Notice>}
    {loading?<div className="skeleton-grid" aria-label="Loading customers">{[1,2,3,4,5,6].map(value=><div className="skeleton-card" key={value}/>)}</div>:!rows.length?<Card><Empty text="No customers match the current filters." action={<Button variant="secondary" onClick={()=>{setQuery('');setStatus('')}}>Clear filters</Button>}/></Card>:<div className="customer-card-grid">{rows.map(customer=><article className="customer-card" key={customer.id}>
      <div className="customer-card-head"><span className="customer-mark">{customer.company_name.slice(0,2).toUpperCase()}</span><div><h2>{customer.company_name}</h2><p>{customer.contact_person||'Primary contact not provided'}</p></div><Status value={customer.status}/></div>
      <div className="customer-contact-list"><span><Phone size={14}/>{customer.phone||'—'}</span><span><Mail size={14}/>{customer.email||'—'}</span><span><MapPin size={14}/>{[customer.city,customer.state].filter(Boolean).join(', ')||'Location not provided'}</span></div>
      <div className="customer-card-stats"><span><b>{customer.project_count||0}</b><small>Projects</small></span><span><b>{customer.active_project_count||0}</b><small>Active</small></span><span><b>{customer.last_activity?new Date(customer.last_activity).toLocaleDateString():'—'}</b><small>Last activity</small></span></div>
      <button type="button" className="customer-open" onClick={()=>navigate(`/app/${workspace}/customers/${customer.id}`)}>Open Customer <ArrowUpRight size={16}/></button>
    </article>)}</div>}
  </>
}
