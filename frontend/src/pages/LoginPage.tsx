import {useState} from 'react'
import type {FormEvent} from 'react'
import {Navigate,useNavigate} from 'react-router-dom'
import {Building2,Eye,EyeOff,LockKeyhole,Mail} from 'lucide-react'
import {useAuth} from '../app/AuthContext'
import {Button} from '../components/UI'

export default function LoginPage(){
  const {user,login}=useAuth()
  const navigate=useNavigate()
  const [email,setEmail]=useState('')
  const [password,setPassword]=useState('')
  const [show,setShow]=useState(false)
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(false)
  if(user)return <Navigate to={`/app/${(user.workspaces[0]||'LIGHTING').toLowerCase()}/${(user.role==='ADMIN'||user.role==='SUPER_ADMIN')?'dashboard':'projects'}`} replace/>
  const submit=async(event:FormEvent)=>{event.preventDefault();setBusy(true);setError('');try{await login(email,password);navigate('/app/lighting/dashboard')}catch(reason){setError(reason instanceof Error?reason.message:'Sign in failed.')}finally{setBusy(false)}}
  return <div className="login-page"><div className="login-visual"><div className="login-overlay"><Building2 size={48}/><h1>AlphaNumeric</h1><p>Smart Solutions.<br/>Brighter Spaces.</p><small>Lighting · Automation · B2B Project Management</small></div></div><div className="login-panel"><form onSubmit={submit} className="login-card"><h2>Welcome Back</h2><p>Sign in to your AlphaNumeric business workspace.</p><label>Email<div className="input-icon"><Mail size={17}/><input value={email} onChange={event=>setEmail(event.target.value)} autoComplete="username" type="email" required/></div></label><label>Password<div className="input-icon"><LockKeyhole size={17}/><input value={password} onChange={event=>setPassword(event.target.value)} autoComplete="current-password" type={show?'text':'password'} required/><button type="button" aria-label={show?'Hide password':'Show password'} onClick={()=>setShow(!show)}>{show?<EyeOff size={17}/>:<Eye size={17}/>}</button></div></label>{error&&<div className="form-error" role="alert">{error}</div>}<Button type="submit" disabled={busy}>{busy?'Signing in…':'Sign In'}</Button></form></div></div>
}
