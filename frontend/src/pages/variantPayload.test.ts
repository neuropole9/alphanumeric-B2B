import {describe,expect,it} from 'vitest'
import {buildVariantPayload} from './variantPayload'

const form={name:'CA1',sku:'ARCOT-COB-CA1',unit:'Nos',price:'1250.05',cost:'',mrp_price:'',
  project_price:'1000.25',dealer_price:'0',reseller_price:'',currency:'INR',
  minimum_order_quantity:'0.25',pricing_status:'DRAFT',tax_rate:'18.50',reorder_level:'0',
  lead_time_days:'0',search_tags:'COB, DALI',highlights:'First\nSecond',features:'',applications:'',
  specs:{control_protocols:'DALI DT8 / Zigbee / Wi-Fi'.repeat(8),legacy_key:'not configured',cct:''}}

describe('variant edit payload',()=>{
  it('preserves decimal text, null optional values, zeroes and configured specifications',()=>{
    const payload=buildVariantPayload(form,[{spec_key:'control_protocols',data_type:'long_text'},{spec_key:'cct',data_type:'single_select'}],true)
    expect(payload.cost).toBeNull()
    expect(payload.project_price).toBe('1000.25')
    expect(payload.dealer_price).toBe('0')
    expect(payload.minimum_order_quantity).toBe('0.25')
    expect(payload.lead_time_days).toBe(0)
    expect(payload.search_tags).toEqual(['COB','DALI'])
    expect(payload.highlights).toEqual(['First','Second'])
    expect(payload.specs).toEqual({control_protocols:form.specs.control_protocols})
  })
  it('rejects invalid required commercial values before requesting a PATCH',()=>{
    expect(()=>buildVariantPayload({...form,price:''},[],true)).toThrow('Price')
    expect(()=>buildVariantPayload({...form,minimum_order_quantity:'0'},[],true)).toThrow('Minimum order quantity')
  })
  it('does not submit imported source URL as a technical specification',()=>{
    const payload=buildVariantPayload(form,[],true)
    expect(payload.specs).not.toHaveProperty('source_url')
    const imported=buildVariantPayload({...form,specs:{source_url:'https://example.com/source'}},[],true)
    expect(imported.specs).toEqual({})
  })
})
