import {useEffect,useMemo,useState} from 'react'
import {ChevronLeft,ChevronRight,Filter,PackagePlus,Plus,Search} from 'lucide-react'
import {useNavigate,useParams} from 'react-router-dom'
import {api,post} from '../api/client'
import {useAuth} from '../app/AuthContext'
import {Button,Card,Empty,Modal,Notice,PageTitle,ProductImage,Status,money} from '../components/UI'
import type {PaginatedFamilies,ProductFamily} from '../types'

type Category={id:string;name:string;count:number}
const initialForm={category_id:'',name:'',brand:'AlphaNumeric',short_description:'',features:'',applications:'',sku:'',variant_name:'',price:0,on_hand:0,unit:'Nos',tax_rate:18}

export default function ProductsPage(){
  const {workspace='lighting'}=useParams()
  const {user}=useAuth()
  const nav=useNavigate()
  const [result,setResult]=useState<PaginatedFamilies>({items:[],page:1,page_size:24,total:0,pages:1,brands:[]})
  const [categories,setCategories]=useState<Category[]>([])
  const [query,setQuery]=useState('')
  const [category,setCategory]=useState('')
  const [brand,setBrand]=useState('')
  const [availability,setAvailability]=useState('')
  const [sort,setSort]=useState('name')
  const [page,setPage]=useState(1)
  const [loading,setLoading]=useState(true)
  const [createOpen,setCreateOpen]=useState(false)
  const [categoryOpen,setCategoryOpen]=useState(false)
  const [categoryForm,setCategoryForm]=useState({name:'',parent_id:'',short_description:''})
  const [form,setForm]=useState(initialForm)
  const [notice,setNotice]=useState<{kind:'success'|'error';text:string}>()

  const params=useMemo(()=>{const value=new URLSearchParams({workspace:workspace.toUpperCase(),page:String(page),page_size:'24',sort});if(query.trim())value.set('q',query.trim());if(category)value.set('category_id',category);if(brand)value.set('brand',brand);if(availability)value.set('availability',availability);return value.toString()},[workspace,page,sort,query,category,brand,availability])
  const load=()=>{setLoading(true);return Promise.all([api<PaginatedFamilies>(`/api/v1/product-families?${params}`),api<Category[]>(`/api/v1/categories?workspace=${workspace.toUpperCase()}`)]).then(([families,cats])=>{setResult(families);setCategories(cats);if(!form.category_id&&cats[0])setForm(current=>({...current,category_id:cats[0].id}))}).catch(e=>setNotice({kind:'error',text:e.message})).finally(()=>setLoading(false))}
  useEffect(()=>{const timer=window.setTimeout(load,query?250:0);return()=>window.clearTimeout(timer)},[params])
  useEffect(()=>setPage(1),[query,category,brand,availability,sort,workspace])
  const brands=Array.from(new Set([...result.brands,...result.items.map(item=>item.brand)])).sort()
  const createFamily=async()=>{
    try{
      const family=await post<ProductFamily>('/api/v1/product-families',{workspace:workspace.toUpperCase(),category_id:form.category_id,name:form.name,brand:form.brand,short_description:form.short_description||undefined,features:form.features.split(',').map(x=>x.trim()).filter(Boolean),applications:form.applications.split(',').map(x=>x.trim()).filter(Boolean)})
      if(form.sku.trim())await post(`/api/v1/product-families/${family.id}/variants`,{sku:form.sku,name:form.name,variant_name:form.variant_name||undefined,price:form.price,on_hand:form.on_hand,unit:form.unit,tax_rate:form.tax_rate,specs:{}})
      setCreateOpen(false);setForm({...initialForm,category_id:categories[0]?.id||''});setNotice({kind:'success',text:`${form.name} was created${form.sku?' with its first variant':''}.`});await load();nav(`/app/${workspace}/products/${family.id}`)
    }catch(e:any){setNotice({kind:'error',text:e.message})}
  }
  const createCategory=async()=>{
    try{
      const created=await post<{id:string;name:string}>('/api/v1/catalogue/categories',{workspace:workspace.toUpperCase(),name:categoryForm.name,parent_id:categoryForm.parent_id||null,short_description:categoryForm.short_description,status:'ACTIVE',sort_order:0})
      const refreshed=await api<Category[]>(`/api/v1/categories?workspace=${workspace.toUpperCase()}`)
      setCategories(refreshed);setForm(current=>({...current,category_id:created.id}));setCategoryForm({name:'',parent_id:'',short_description:''});setCategoryOpen(false);setNotice({kind:'success',text:`Category ${created.name} was created and selected. Your product draft was preserved.`})
    }catch(e:any){setNotice({kind:'error',text:e.message})}
  }

  return <>
    <PageTitle title="Product Catalogue" subtitle={`${workspace[0].toUpperCase()+workspace.slice(1)} families, media, specifications, and exact variants`} badge={(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')?'Admin':'Project User'} actions={(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')?<Button onClick={()=>setCreateOpen(true)}><Plus size={17}/> New Product Family</Button>:undefined}/>
    {notice&&<Notice kind={notice.kind}>{notice.text}</Notice>}
    <Card className="catalogue-toolbar">
      <label className="catalogue-search"><Search size={18}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search family, brand, or SKU"/></label>
      <label><Filter size={16}/><select aria-label="Category" value={category} onChange={e=>setCategory(e.target.value)}><option value="">All categories</option>{categories.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <select aria-label="Brand" value={brand} onChange={e=>setBrand(e.target.value)}><option value="">All brands</option>{brands.map(item=><option key={item}>{item}</option>)}</select>
      <select aria-label="Availability" value={availability} onChange={e=>setAvailability(e.target.value)}><option value="">Any availability</option><option value="IN_STOCK">In stock</option><option value="OUT_OF_STOCK">Out of stock</option></select>
      <select aria-label="Sort catalogue" value={sort} onChange={e=>setSort(e.target.value)}><option value="name">Name A–Z</option><option value="newest">Newest</option><option value="brand">Brand</option></select>
    </Card>
    <div className="catalogue-meta"><p><b>{result.total}</b> product {result.total===1?'family':'families'}</p>{(query||category||brand||availability)&&<button type="button" onClick={()=>{setQuery('');setCategory('');setBrand('');setAvailability('')}}>Clear filters</button>}</div>
    {loading?<div className="catalogue-grid" aria-label="Loading catalogue">{Array.from({length:8},(_,index)=><Card className="catalogue-card skeleton-card" key={index}><i/><i/><i/></Card>)}</div>:!result.items.length?<Card><Empty text="No product families match these filters."/></Card>:<div className="catalogue-grid">{result.items.map(family=><Card className="catalogue-card" key={family.id}>
      <button type="button" className="catalogue-image-button" onClick={()=>nav(`/app/${workspace}/products/${family.id}`)} aria-label={`View ${family.name}`}><ProductImage family={family} size={240}/></button>
      <div className="catalogue-card-body"><div className="catalogue-eyebrow"><span>{family.brand}</span><Status value={family.availability}/></div><h2>{family.name}</h2><p>{family.short_description||'View the family to compare exact product variants and specifications.'}</p><div className="catalogue-facts"><span><b>{family.variant_count}</b> variant{family.variant_count===1?'':'s'}</span><span><b>{family.available}</b> units available</span>{(user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')&&family.starting_price!=null&&<span>From <b>{money(family.starting_price)}</b></span>}</div><Button onClick={()=>nav(`/app/${workspace}/products/${family.id}`)}>View family <ChevronRight size={16}/></Button></div>
    </Card>)}</div>}
    {result.pages>1&&<nav className="pagination" aria-label="Catalogue pages"><Button variant="secondary" disabled={page<=1} onClick={()=>setPage(value=>value-1)}><ChevronLeft size={16}/> Previous</Button><span>Page <b>{page}</b> of {result.pages}</span><Button variant="secondary" disabled={page>=result.pages} onClick={()=>setPage(value=>value+1)}>Next <ChevronRight size={16}/></Button></nav>}
    <Modal open={createOpen} title="Create Product Family" onClose={()=>setCreateOpen(false)} className="catalogue-form-modal" footer={<><Button variant="secondary" onClick={()=>setCreateOpen(false)}>Cancel</Button><Button disabled={!form.name.trim()||!form.category_id||!form.brand.trim()} onClick={createFamily}><PackagePlus size={16}/> Create Family</Button></>}>
      <p className="muted">Create the shared family first. Add an optional first sellable variant now; more variants and images can be added from the detail page.</p>
      <div className="form-grid two"><label>Family name *<input value={form.name} onChange={e=>setForm(current=>({...current,name:e.target.value}))}/></label><label>Brand *<input value={form.brand} onChange={e=>setForm(current=>({...current,brand:e.target.value}))}/></label><label>Category *<select value={form.category_id} onChange={e=>setForm(current=>({...current,category_id:e.target.value}))}><option value="">Select category</option>{categories.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select><button type="button" className="inline-action" onClick={()=>setCategoryOpen(true)}>+ Create category</button></label><label className="span-2">Short description<textarea value={form.short_description} onChange={e=>setForm(current=>({...current,short_description:e.target.value}))}/></label><label>Features <small>(comma separated)</small><input value={form.features} onChange={e=>setForm(current=>({...current,features:e.target.value}))}/></label><label>Applications <small>(comma separated)</small><input value={form.applications} onChange={e=>setForm(current=>({...current,applications:e.target.value}))}/></label></div>
      <h3 className="modal-section-title">Optional first variant</h3>
      <div className="form-grid two"><label>SKU<input value={form.sku} onChange={e=>setForm({...form,sku:e.target.value})}/></label><label>Variant name<input value={form.variant_name} onChange={e=>setForm({...form,variant_name:e.target.value})}/></label><label>Price<input type="number" min="0" value={form.price} onChange={e=>setForm({...form,price:Number(e.target.value)})}/></label><label>Opening stock<input type="number" min="0" value={form.on_hand} onChange={e=>setForm({...form,on_hand:Number(e.target.value)})}/></label><label>Unit<input value={form.unit} onChange={e=>setForm({...form,unit:e.target.value})}/></label><label>Tax %<input type="number" min="0" max="100" value={form.tax_rate} onChange={e=>setForm({...form,tax_rate:Number(e.target.value)})}/></label></div>
    </Modal>
    <Modal open={categoryOpen} title="Create category" onClose={()=>setCategoryOpen(false)} footer={<><Button variant="secondary" onClick={()=>setCategoryOpen(false)}>Cancel</Button><Button disabled={!categoryForm.name.trim()} onClick={createCategory}>Create and select</Button></>}>
      <p className="muted">The new category is locked to {workspace}. Your current product values will not be reset.</p><div className="form-grid"><label>Category name *<input value={categoryForm.name} onChange={e=>setCategoryForm(current=>({...current,name:e.target.value}))}/></label><label>Parent category<select value={categoryForm.parent_id} onChange={e=>setCategoryForm(current=>({...current,parent_id:e.target.value}))}><option value="">Root category</option>{categories.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Short description<textarea value={categoryForm.short_description} onChange={e=>setCategoryForm(current=>({...current,short_description:e.target.value}))}/></label></div>
    </Modal>
  </>
}
