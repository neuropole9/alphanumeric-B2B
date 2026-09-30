import {useEffect,useRef,useState} from 'react'
import type {CSSProperties,ReactNode} from 'react'
import {Link} from 'react-router-dom'
import type {Product,ProductFamily} from '../types'
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Fan,
  FileText,
  Lightbulb,
  Package,
  PackageCheck,
  Radar,
  Router,
  ShoppingCart,
  X,
} from 'lucide-react'

export const money=(n:number|null|undefined)=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0}).format(n||0)

export function Card({children,className=''}:{children:ReactNode;className?:string}){
  return <div className={`card ${className}`}>{children}</div>
}

export function PageTitle({title,subtitle,badge,actions}:{title:string;subtitle?:string;badge?:string;actions?:ReactNode}){
  return <header className="page-title">
    <div className="page-title-copy">
      <span className="page-title-accent" aria-hidden="true"/>
      <div className="title-line"><h1>{title}</h1>{badge&&<span className="role-badge">{badge}</span>}</div>
      {subtitle&&<p>{subtitle}</p>}
    </div>
    {actions&&<div className="page-actions">{actions}</div>}
  </header>
}

export function Breadcrumbs({items}:{items:Array<{label:string;to?:string}>}){
  return <nav className="breadcrumbs" aria-label="Breadcrumb">{items.map((item,index)=><span key={`${item.label}-${index}`}>{index>0&&<span aria-hidden="true">/</span>}{item.to?<Link to={item.to}>{item.label}</Link>:<b aria-current="page">{item.label}</b>}</span>)}</nav>
}

export function Button({children,onClick,variant='primary',type='button',disabled=false,className=''}:{children:ReactNode;onClick?:()=>void;variant?:'primary'|'secondary'|'success'|'danger';type?:'button'|'submit';disabled?:boolean;className?:string}){
  return <button type={type} disabled={disabled} onClick={onClick} className={`btn btn-${variant} ${className}`}>{children}</button>
}

export function Status({value}:{value:string}){
  const key=value.toUpperCase()
  const cls=key.includes('OUT')||key==='CANCELLED'||key==='REJECTED'||key==='DISABLED'?'danger':key.includes('LOW')||key==='PROCESSING'||key==='SENT'?'warning':key==='DELIVERED'||key==='COMPLETED'||key==='ACCEPTED'||key==='IN_STOCK'||key==='ACTIVE'?'success':'info'
  return <span className={`status status-${cls}`}><i aria-hidden="true"/>{value.replaceAll('_',' ')}</span>
}

export function StatCard({label,value,kind='blue',sub}:{label:string;value:string|number;kind?:string;sub?:string}){
  const Icon=kind==='green'?PackageCheck:kind==='orange'?Clock3:kind==='purple'?FileText:ShoppingCart
  return <Card className={`stat-card stat-${kind}`}><div className={`stat-icon ${kind}`}><Icon size={23}/></div><div><div className="stat-label">{label}</div><div className="stat-value">{value}</div>{sub&&<div className="stat-sub">{sub}</div>}</div></Card>
}

export function Empty({text='No records found',action}:{text?:string;action?:ReactNode}){
  return <div className="empty"><span className="empty-icon"><FileText size={26}/></span><strong>{text}</strong>{action}</div>
}

export function ProductThumb({name,size=48}:{name:string;size?:number}){
  const value=name.toLowerCase()
  const Icon=value.includes('fan')?Fan:value.includes('sensor')?Radar:value.includes('gateway')||value.includes('controller')?Router:value.includes('light')||value.includes('lamp')?Lightbulb:Package
  const style={width:size,height:size,'--thumb':`${size}px`} as CSSProperties
  return <div className="product-thumb" style={style}><Icon size={Math.max(18,Math.round(size*.38))}/></div>
}

export function ProductImage({product,family,size=96,className=''}:{product?:Product;family?:ProductFamily;size?:number;className?:string}){
  const source=product ? (product.primary_image_url||product.media?.find(x=>x.is_primary)?.url||family?.media?.find(x=>x.is_primary)?.url) : (family?.primary_image_url||family?.media?.find(x=>x.is_primary)?.url)
  const alt=product?.media?.find(x=>x.url===source)?.alt_text||family?.media?.find(x=>x.url===source)?.alt_text||product?.name||family?.name||'Product image'
  const [failed,setFailed]=useState(false)
  useEffect(()=>setFailed(false),[source])
  if(!source||failed)return <div className={`product-image-unavailable ${className}`} role="img" aria-label={`Image unavailable for ${product?.name||family?.name||'product'}`}>Image unavailable</div>
  return <div className={`product-image ${className}`} style={{width:size,height:size}}><img src={source} alt={alt} loading="lazy" onError={()=>setFailed(true)}/></div>
}

export function ConfirmLine({ok,text}:{ok:boolean;text:string}){
  return <div className={`confirm-line ${ok?'ok':'warn'}`}>{ok?<CheckCircle2 size={17}/>:<AlertTriangle size={17}/>}<span>{text}</span></div>
}

export function Modal({open,title,children,onClose,footer,className=''}:{open:boolean;title:string;children:ReactNode;onClose:()=>void;footer?:ReactNode;className?:string}){
  const dialogRef=useRef<HTMLDivElement>(null)
  const returnFocus=useRef<HTMLElement|null>(null)
  const onCloseRef=useRef(onClose)
  onCloseRef.current=onClose
  useEffect(()=>{
    if(!open)return
    returnFocus.current=document.activeElement as HTMLElement|null
    const dialog=dialogRef.current
    const focusable=dialog?.querySelector<HTMLElement>('button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),a[href]')
    focusable?.focus()
    const key=(event:KeyboardEvent)=>{
      if(event.key==='Escape'){event.preventDefault();onCloseRef.current();return}
      if(event.key!=='Tab'||!dialog)return
      const nodes=[...dialog.querySelectorAll<HTMLElement>('button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),a[href]')]
      if(!nodes.length)return
      const first=nodes[0],last=nodes[nodes.length-1]
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}
    }
    document.addEventListener('keydown',key)
    return()=>{document.removeEventListener('keydown',key);returnFocus.current?.focus()}
  },[open])
  if(!open)return null
  return <div className="modal-backdrop" role="presentation" onMouseDown={e=>{if(e.currentTarget===e.target)onClose()}}>
    <div ref={dialogRef} className={`modal ${className}`} role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div className="modal-head"><h2 id="modal-title">{title}</h2><button type="button" className="icon-btn plain" onClick={onClose} aria-label="Close"><X size={18}/></button></div>
      <div className="modal-body">{children}</div>
      {footer&&<div className="modal-footer">{footer}</div>}
    </div>
  </div>
}

export function Notice({kind='info',children}:{kind?:'info'|'success'|'error'|'warning';children:ReactNode}){
  return <div className={`notice notice-${kind}`}>{children}</div>
}
