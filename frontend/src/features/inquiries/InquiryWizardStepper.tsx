import {Check} from 'lucide-react'

const labels=[
  ['Project & Client','Client, site and partner'],
  ['Floors & Rooms','Build the project structure'],
  ['Room Products','Lighting and automation'],
  ['BOQ Review','Verify every quantity'],
  ['Final Review','Confirm and submit'],
]

export default function InquiryWizardStepper({step,onStep}:{step:number;onStep:(n:number)=>void}){
  return <nav className="wizard wizard-five" aria-label="Inquiry progress">
    {labels.map(([title,sub],i)=>{
      const n=i+1
      const done=n<step
      const active=n===step
      return <button
        type="button"
        key={title}
        className={`step ${active?'active':''} ${done?'done':''}`}
        onClick={()=>done&&onStep(n)}
        disabled={n>step}
        aria-current={active?'step':undefined}
      >
        <span className="step-index">{done?<Check size={16}/>:n}</span>
        <span className="step-copy"><b>{title}</b><small>{sub}</small></span>
      </button>
    })}
  </nav>
}
