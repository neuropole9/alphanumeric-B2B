import {readFileSync} from 'node:fs'
import {describe,expect,it} from 'vitest'

const source=(name:string)=>readFileSync(new URL(`./${name}`,import.meta.url),'utf8')

describe('project workspace information architecture',()=>{
  it('keeps the customer project card compact and uses direct order routes',()=>{
    const text=source('CustomerDetailPage.tsx')
    expect(text).toContain("value==='projects'?'Projects'")
    expect(text).toContain('project-card-stats project-card-stats-compact')
    expect(text).not.toContain('/orders?selected=')
  })

  it('exposes only the eight required project tabs and actionable workflow states',()=>{
    const text=source('ProjectDetailPage.tsx')
    expect(text).toContain("const tabs:Tab[]=['overview','buildings','products','inquiries','quotations','orders','invoices','documents']")
    expect(text).toContain('Commercial Progress')
    expect(text).toContain('Generate Draft Quotation')
    expect(text).toContain('Convert Accepted Quotation to Order')
    expect(text).toContain('An invoice can be generated after an order is created.')
    expect(text).toContain('await load()')
  })

  it('limits the building workspace to physical configuration',()=>{
    const text=source('BuildingDetailPage.tsx')
    expect(text).toContain("const tabs:Tab[]=['overview','floors','products','mainboards','documents']")
    expect(text).toContain('Plans & Documents')
    expect(text).toContain('Building Products / BOQ')
  })

  it('preselects project and building query context and navigates directly after conversion',()=>{
    const wizard=source('CreateInquiryPage.tsx')
    const quotation=source('QuotationDetailPage.tsx')
    expect(wizard).toMatch(/search\.get\(["']project_id["']\)/)
    expect(wizard).toMatch(/search\.get\(["']building_id["']\)/)
    expect(wizard).toContain('This will create a')
    expect(quotation).toContain('`/app/${workspace}/orders/${o.id}`')
    expect(quotation).not.toContain('/orders?selected=')
  })
})
