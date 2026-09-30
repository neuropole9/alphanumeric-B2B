// @vitest-environment jsdom
import {describe,expect,it,vi} from 'vitest'
import {render,screen,fireEvent} from '@testing-library/react'
import type {Product,ProductFamily} from '../types'
import {ModelGallery} from './ModelGallery'

const variant=(id:string,name:string,url:string|null):Product=>({
  id,sku:`SKU-${name}`,name,variant_name:name,model_number:name,workspace:'LIGHTING',category_id:'cat',
  category:'COB',brand:'Arcot',status:'ACTIVE',unit:'Nos',tax_rate:18,available:10,stock_status:'IN_STOCK',
  specs:{wattage:'20W',input_voltage:'220V',cct:'3000K'},images:[],
  media:url?[{id:`media-${id}`,url,alt_text:`${name} primary`,sort_order:0,is_primary:true,media_type:'image'}]:[],
  primary_image_url:url,
})
const family:ProductFamily={id:'family',workspace:'LIGHTING',category_id:'cat',category:'COB',name:'COB',slug:'cob',
  brand:'Arcot',features:[],applications:[],status:'ACTIVE',variant_count:3,available:30,availability:'IN_STOCK',
  media:[],primary_image_url:'/media/ca1',variants:[variant('ca1','CA1','/media/ca1'),variant('ca2','CA2','/media/ca2'),variant('ca10','CA10',null)]}

describe('model gallery',()=>{
  it('uses each exact model image, an explicit missing image, and keyboard selectable buttons',()=>{
    const onSelect=vi.fn()
    render(<ModelGallery family={family} selectedId="ca1" onSelect={onSelect}/>)
    const buttons=screen.getAllByRole('button')
    expect(buttons.map(button=>button.textContent?.match(/CA\d+/)?.[0])).toEqual(['CA1','CA2','CA10'])
    expect(screen.getByAltText('CA1 primary').getAttribute('src')).toBe('/media/ca1')
    expect(screen.getByAltText('CA2 primary').getAttribute('src')).toBe('/media/ca2')
    expect(screen.getByRole('img',{name:/Image unavailable for CA10/})).toBeTruthy()
    expect(buttons[0].getAttribute('aria-pressed')).toBe('true')
    buttons[1].focus();fireEvent.keyDown(buttons[1],{key:'Enter'});fireEvent.click(buttons[1])
    expect(onSelect).toHaveBeenCalledWith('ca2')
  })
})
