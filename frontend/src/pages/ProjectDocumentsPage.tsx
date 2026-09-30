import {useEffect,useState} from 'react'
import {Download,Eye,Trash2,Upload} from 'lucide-react'
import {useParams} from 'react-router-dom'
import {api,del,receiveServerFile} from '../api/client'
import {Breadcrumbs,Button,Card,Empty,Modal,Notice,PageTitle,Status} from '../components/UI'
import {useAuth} from '../app/AuthContext'

type DocumentRow={
  id:string
  title:string
  document_type:string
  revision:string
  file_name:string
  mime_type:string
  size_bytes:number
  status:string
  created_at:string
  preview_url:string
  download_url:string
}

export default function ProjectDocumentsPage(){
  const {workspace='lighting',id:projectId,buildingId}=useParams()
  const {user}=useAuth()
  const [rows,setRows]=useState<DocumentRow[]>([])
  const [file,setFile]=useState<File>()
  const [title,setTitle]=useState('')
  const [documentType,setDocumentType]=useState('FLOOR_PLAN')
  const [revision,setRevision]=useState('A')
  const [notice,setNotice]=useState<{kind:'success'|'error';text:string}>()
  const [busy,setBusy]=useState(false)
  const [deleteId,setDeleteId]=useState<string>()
  const [deleting,setDeleting]=useState(false)

  const load=()=>api<DocumentRow[]>(`/api/v1/projects/${projectId}/documents${buildingId?`?building_id=${buildingId}`:''}`).then(setRows)

  useEffect(()=>{
    load().catch(e=>setNotice({kind:'error',text:e.message}))
  },[projectId,buildingId])

  const upload=async()=>{
    if(!file||!title.trim())return
    const body=new FormData()
    body.append('file',file)
    body.append('title',title)
    body.append('document_type',documentType)
    body.append('revision',revision)
    if(buildingId)body.append('building_id',buildingId)
    setBusy(true)
    try{
      await api(`/api/v1/projects/${projectId}/documents`,{method:'POST',body})
      setFile(undefined)
      setTitle('')
      setNotice({kind:'success',text:'Project document uploaded.'})
      await load()
    }catch(e:any){
      setNotice({kind:'error',text:e.message})
    }finally{
      setBusy(false)
    }
  }

  const archive=async()=>{
    if(!deleteId)return
    setDeleting(true)
    try{
      await del(`/api/v1/project-documents/${deleteId}`)
      setDeleteId(undefined)
      setNotice({kind:'success',text:'Project document archived.'})
      await load()
    }catch(e:any){
      setNotice({kind:'error',text:e.message})
    }finally{
      setDeleting(false)
    }
  }

  const selected=rows.find(row=>row.id===deleteId)

  return <>
    <Breadcrumbs items={[{label:'Project',to:`/app/${workspace}/projects/${projectId}`},{label:'Documents'}]}/>
    <PageTitle title="Plans & Documents" subtitle="Revision-controlled project, building, floor, and room files" badge={buildingId?'Building scope':'Project scope'}/>
    {notice&&<Notice kind={notice.kind}>{notice.text}</Notice>}
    {(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')&&<Card>
      <h2>Upload document</h2>
      <div className="form-grid three">
        <label>Title *<input value={title} onChange={e=>setTitle(e.target.value)} placeholder="Ground floor lighting plan"/></label>
        <label>Document type<select value={documentType} onChange={e=>setDocumentType(e.target.value)}><option>FLOOR_PLAN</option><option>BUILDING_PLAN</option><option>SINGLE_LINE_DIAGRAM</option><option>SPECIFICATION</option><option>APPROVAL</option><option>OTHER</option></select></label>
        <label>Revision<input value={revision} onChange={e=>setRevision(e.target.value)}/></label>
        <label className="span-2">File *<input type="file" accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx" onChange={e=>setFile(e.target.files?.[0])}/></label>
        <Button disabled={busy||!file||!title.trim()} onClick={upload}><Upload size={16}/> {busy?'Uploading…':'Upload'}</Button>
      </div>
    </Card>}
    <Card className="table-card">
      <h2>Document register</h2>
      {!rows.length?<Empty text="No documents have been uploaded for this scope."/>:<div className="table-wrap"><table>
        <thead><tr><th>Type</th><th>Title</th><th>Revision</th><th>File</th><th>Uploaded</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>{rows.map(row=><tr key={row.id}>
          <td>{row.document_type.replaceAll('_',' ')}</td>
          <td><b>{row.title}</b></td>
          <td>{row.revision}</td>
          <td>{row.file_name}<small>{Math.ceil(row.size_bytes/1024)} KB</small></td>
          <td>{new Date(row.created_at).toLocaleDateString()}</td>
          <td><Status value={row.status}/></td>
          <td><span className="button-row">
            <Button variant="secondary" onClick={()=>receiveServerFile(row.preview_url,'preview')}><Eye size={14}/> Preview</Button>
            <Button variant="secondary" onClick={()=>receiveServerFile(row.download_url,'download')}><Download size={14}/> Download</Button>
            {(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')&&<Button variant="danger" onClick={()=>setDeleteId(row.id)}><Trash2 size={14}/> Archive</Button>}
          </span></td>
        </tr>)}</tbody>
      </table></div>}
    </Card>
    <Modal open={Boolean(deleteId)} title="Archive document?" onClose={()=>!deleting&&setDeleteId(undefined)} footer={<><Button variant="secondary" disabled={deleting} onClick={()=>setDeleteId(undefined)}>Cancel</Button><Button variant="danger" disabled={deleting} onClick={archive}>{deleting?'Archiving…':'Archive Document'}</Button></>}>
      <p>{selected?<>Archive <b>{selected.title}</b>? It will no longer appear in the active project document register.</>:'Archive this project document?'}</p>
    </Modal>
  </>
}
