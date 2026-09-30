import type {Product, ProductFamily} from '../types'
import {ProductImage, Status} from '../components/UI'

function showValue(value: unknown): string {
  if (Array.isArray(value)) return value.map(String).join(', ')
  if (value && typeof value === 'object') {
    const measured=value as {amount?: unknown;unit?: unknown}
    return measured.amount == null ? '—' : `${measured.amount} ${measured.unit ?? ''}`.trim()
  }
  return value == null || value === '' ? '—' : String(value)
}

export function modelSpec(product: Product, ...aliases: string[]) {
  const wanted=aliases.map(value=>value.toLowerCase().replace(/[^a-z0-9]/g,''))
  const entry=Object.entries(product.specs||{}).find(([key])=>wanted.includes(key.toLowerCase().replace(/[^a-z0-9]/g,'')))
  return entry ? showValue(entry[1]) : '—'
}

export function ModelGallery({family,selectedId,onSelect}:{family:ProductFamily;selectedId?:string;onSelect:(id:string)=>void}) {
  return <div className="model-gallery" aria-label="Models in this family">
    {(family.variants||[]).map(item=><button type="button" key={item.id}
      className={`model-card ${selectedId===item.id?'active':''}`}
      onClick={()=>onSelect(item.id)} aria-pressed={selectedId===item.id}>
      <span className="model-card-image"><ProductImage product={item} family={family} size={180}/></span>
      <strong>{item.variant_name||item.name}</strong>
      <span>Model: {item.model_number||'Not assigned'}</span><small>SKU: {item.sku}</small>
      <span>Wattage: {modelSpec(item,'wattage','wattage_range','power')}</span>
      <span>Input voltage: {modelSpec(item,'input_voltage','voltage','operating_voltage')}</span>
      <span>CCT: {modelSpec(item,'cct','color_temperature','colour_temperature')}</span>
      <span>Beam angle: {modelSpec(item,'beam_angle','beam_angles')}</span>
      <span><Status value={item.stock_status}/></span><span className="model-card-link">View details →</span>
    </button>)}
  </div>
}
