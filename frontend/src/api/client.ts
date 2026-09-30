const readCookie=(name:string)=>document.cookie.split('; ').find(x=>x.startsWith(name+'='))?.split('=')[1]

let refreshPromise:Promise<boolean>|null=null

function refreshSession(){
  if(!refreshPromise){
    const headers=new Headers()
    const csrf=readCookie('csrf_token')
    if(csrf) headers.set('X-CSRF-Token',decodeURIComponent(csrf))
    refreshPromise=fetch('/api/v1/auth/refresh',{method:'POST',headers,credentials:'include'})
      .then(response=>response.ok)
      .catch(()=>false)
      .finally(()=>{refreshPromise=null})
  }
  return refreshPromise
}

async function raw(path:string, init:RequestInit={}, retry=true){
  const headers=new Headers(init.headers||{})
  if(init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type','application/json')
  const method=(init.method||'GET').toUpperCase()
  if(!['GET','HEAD','OPTIONS'].includes(method)){
    const csrf=readCookie('csrf_token'); if(csrf) headers.set('X-CSRF-Token',decodeURIComponent(csrf))
  }
  const res=await fetch(path,{...init,headers,credentials:'include'})
  if(res.status===401 && retry && !path.includes('/auth/login') && !path.includes('/auth/refresh')){
    if(await refreshSession()) return raw(path,init,false)
  }
  return res
}

type ApiValidationError={loc?:Array<string|number>;msg?:string}

export function formatApiError(detail:unknown,status:number){
  if(typeof detail==='string' && detail.trim()) return detail
  if(Array.isArray(detail)){
    const messages=detail.map((item:ApiValidationError)=>{
      const location=item?.loc?.filter(part=>part!=='body').join('.')
      const message=item?.msg||'Invalid value'
      return location?`${location}: ${message}`:message
    }).filter(Boolean)
    if(messages.length) return messages.join('; ')
  }
  return `Request failed (${status})`
}

export async function api<T>(path:string, init:RequestInit={}):Promise<T>{
  const res=await raw(path,init)
  if(!res.ok){let detail:unknown;try{detail=(await res.json()).detail}catch{}throw new Error(formatApiError(detail,res.status))}
  if(res.status===204) return undefined as T
  return res.json()
}
export const post=<T>(path:string,body?:unknown)=>api<T>(path,{method:'POST',body:body===undefined?undefined:JSON.stringify(body)})
export const patch=<T>(path:string,body?:unknown)=>api<T>(path,{method:'PATCH',body:body===undefined?undefined:JSON.stringify(body)})
export const del=<T>(path:string)=>api<T>(path,{method:'DELETE'})
export function openServerFile(path:string){ window.open(path,'_blank','noopener,noreferrer') }
export async function receiveServerFile(path:string,mode:'preview'|'download'='preview',fallbackFilename='download'){
  // Open the tab while the user's click is still active; browsers block it after an await.
  const previewWindow=mode==='preview'?window.open('','_blank'):null
  if(mode==='preview' && !previewWindow) throw new Error('Your browser blocked the preview window.')
  if(previewWindow) previewWindow.opener=null
  try{
    const response=await raw(path)
    if(!response.ok){let message=`Download failed (${response.status})`;try{const value=await response.json();message=value.detail||message}catch{}throw new Error(message)}
    const blob=await response.blob()
    const url=URL.createObjectURL(blob)
    if(mode==='preview'){
      if(previewWindow!.closed){URL.revokeObjectURL(url);throw new Error('The preview window was closed before the PDF was ready.')}
      try{previewWindow!.location.replace(url)}
      catch(error){URL.revokeObjectURL(url);throw error}
      window.setTimeout(()=>URL.revokeObjectURL(url),60_000)
      return
    }
    const disposition=response.headers.get('Content-Disposition')||''
    const match=/filename="?([^";]+)"?/i.exec(disposition)
    const anchor=document.createElement('a')
    anchor.href=url;anchor.download=match?.[1]||fallbackFilename;document.body.appendChild(anchor);anchor.click();anchor.remove()
    URL.revokeObjectURL(url)
  }catch(error){
    previewWindow?.close()
    throw error
  }
}

const safeFilenamePart=(value:string)=>value.replace(/[^A-Za-z0-9._-]+/g,'-').replace(/^-+|-+$/g,'')||'Document'

export const quotationFilename=(quotationNumber:string)=>`Quotation_${safeFilenamePart(quotationNumber)}.pdf`
export const invoiceFilename=(invoiceNumber:string)=>`Invoice_${safeFilenamePart(invoiceNumber)}.pdf`

export const quotationPdfPath=(quotationId:string,download=false)=>
  `/api/v1/quotations/${encodeURIComponent(quotationId)}/pdf${download?'?download=true':''}`

export const invoicePdfPath=(invoiceId:string,download=false)=>
  `/api/v1/invoices/${encodeURIComponent(invoiceId)}/pdf${download?'?download=true':''}`

export const projectBookPath=(projectId:string,download=false)=>
  `/api/v1/projects/${encodeURIComponent(projectId)}/book.pdf${download?'?download=true':''}`

export const buildingBookPath=(projectId:string,buildingId:string,download=false)=>
  `/api/v1/projects/${encodeURIComponent(projectId)}/buildings/${encodeURIComponent(buildingId)}/book.pdf${download?'?download=true':''}`

export const viewQuotation=(quotationId:string,quotationNumber:string)=>
  receiveServerFile(quotationPdfPath(quotationId),'preview',quotationFilename(quotationNumber))

export const downloadQuotation=(quotationId:string,quotationNumber:string)=>
  receiveServerFile(quotationPdfPath(quotationId,true),'download',quotationFilename(quotationNumber))

export const viewInvoice=(invoiceId:string,invoiceNumber:string)=>
  receiveServerFile(invoicePdfPath(invoiceId),'preview',invoiceFilename(invoiceNumber))

export const downloadInvoice=(invoiceId:string,invoiceNumber:string)=>
  receiveServerFile(invoicePdfPath(invoiceId,true),'download',invoiceFilename(invoiceNumber))
