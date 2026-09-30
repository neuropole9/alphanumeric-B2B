import {describe,expect,it} from 'vitest'
import {applicationPath,productsForApplication,reportUrl,shouldDiscardApplicationState} from './application'
import type {Product} from '../types'

const product=(id:string,workspace:'LIGHTING'|'AUTOMATION')=>({id,workspace,category_id:'c',category:'Category',sku:id,name:id,brand:'AlphaNumeric',status:'ACTIVE',available:1,unit:'Nos',tax_rate:18,specs:{},images:[],stock_status:'IN_STOCK'} as Product)

describe('release 5 application isolation',()=>{
  it('returns the isolated admin landing route',()=>expect(applicationPath('AUTOMATION',true)).toBe('/app/automation/dashboard'))
  it('returns the isolated customer landing route',()=>expect(applicationPath('LIGHTING',false)).toBe('/app/lighting/projects'))
  it('filters the product picker to one application',()=>expect(productsForApplication([product('L','LIGHTING'),product('A','AUTOMATION')],'LIGHTING').map(x=>x.id)).toEqual(['L']))
  it('requires state discard only when application changes',()=>{expect(shouldDiscardApplicationState('LIGHTING','AUTOMATION')).toBe(true);expect(shouldDiscardApplicationState('LIGHTING','LIGHTING')).toBe(false)})
  it('adds application context to preview URLs',()=>expect(reportUrl('/api/v1/projects/p/book.pdf','LIGHTING')).toContain('workspace=LIGHTING'))
  it('keeps download and application context together',()=>expect(reportUrl('/api/v1/projects/p/book.pdf','AUTOMATION',true)).toBe('/api/v1/projects/p/book.pdf?workspace=AUTOMATION&download=true'))
})
