import {useState,type FormEvent} from 'react'
import {KeyRound,ShieldCheck} from 'lucide-react'
import {useNavigate,useParams} from 'react-router-dom'
import {post} from '../api/client'
import {useAuth} from '../app/AuthContext'
import {Button,Card,Notice,PageTitle} from '../components/UI'

export default function ChangePasswordPage(){
  const {user,refresh}=useAuth()
  const {workspace='lighting'}=useParams()
  const navigate=useNavigate()
  const [currentPassword,setCurrentPassword]=useState('')
  const [newPassword,setNewPassword]=useState('')
  const [confirmPassword,setConfirmPassword]=useState('')
  const [busy,setBusy]=useState(false)
  const [notice,setNotice]=useState<{kind:'success'|'error';text:string}>()

  const submit=async(event:FormEvent)=>{
    event.preventDefault()
    if(newPassword.length<12){setNotice({kind:'error',text:'New password must contain at least 12 characters.'});return}
    if(newPassword!==confirmPassword){setNotice({kind:'error',text:'New password and confirmation do not match.'});return}
    setBusy(true);setNotice(undefined)
    try{
      await post('/api/v1/auth/change-password',{current_password:currentPassword,new_password:newPassword})
      await refresh()
      setNotice({kind:'success',text:'Password changed successfully.'})
      navigate(`/app/${workspace}/${(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')?'dashboard':'projects'}`,{replace:true})
    }catch(error){setNotice({kind:'error',text:error instanceof Error?error.message:'Password change failed.'})}
    finally{setBusy(false)}
  }

  return <>
    <PageTitle title="Change Password" subtitle={user?.must_change_password?'A password change is required before continuing.':'Update your account password.'} badge="Account"/>
    {notice&&<Notice kind={notice.kind}>{notice.text}</Notice>}
    <Card className="settings-card">
      <div className="settings-card-head"><span><ShieldCheck size={21}/></span><div><h3>Account Security</h3><p>Use a unique password with at least 12 characters.</p></div></div>
      <form onSubmit={submit} className="form-grid two">
        <label className="span-2">Current Password<input type="password" autoComplete="current-password" value={currentPassword} onChange={e=>setCurrentPassword(e.target.value)} required/></label>
        <label>New Password<input type="password" autoComplete="new-password" minLength={12} value={newPassword} onChange={e=>setNewPassword(e.target.value)} required/></label>
        <label>Confirm New Password<input type="password" autoComplete="new-password" minLength={12} value={confirmPassword} onChange={e=>setConfirmPassword(e.target.value)} required/></label>
        <div className="span-2"><Button type="submit" disabled={busy}><KeyRound size={16}/> {busy?'Changing Password…':'Change Password'}</Button></div>
      </form>
    </Card>
  </>
}
