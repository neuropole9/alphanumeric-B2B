import {afterEach,describe,expect,it,vi} from 'vitest'
import {buildingBookPath,formatApiError,invoiceFilename,invoicePdfPath,projectBookPath,quotationFilename,quotationPdfPath,receiveServerFile} from './client'

afterEach(()=>vi.unstubAllGlobals())

describe('PDF previews',()=>{
  it('opens the tab before the report request completes',async()=>{
    let completeRequest!:(response:Response)=>void
    const fetchMock=vi.fn(()=>new Promise<Response>(resolve=>{completeRequest=resolve}))
    const previewWindow={opener:globalThis as unknown,closed:false,location:{replace:vi.fn()},close:vi.fn()}
    const open=vi.fn(()=>previewWindow)
    const revokeObjectURL=vi.fn()
    vi.stubGlobal('document',{cookie:''})
    vi.stubGlobal('window',{open,setTimeout:vi.fn()})
    vi.stubGlobal('fetch',fetchMock)
    vi.stubGlobal('URL',{createObjectURL:vi.fn(()=> 'blob:project-book'),revokeObjectURL})

    const pending=receiveServerFile(projectBookPath('project-1'))
    expect(open).toHaveBeenCalledWith('','_blank')
    expect(previewWindow.opener).toBeNull()
    expect(previewWindow.location.replace).not.toHaveBeenCalled()
    completeRequest({ok:true,blob:async()=>new Blob(['PDF']),headers:new Headers()} as Response)
    await pending

    expect(previewWindow.location.replace).toHaveBeenCalledWith('blob:project-book')
    expect(previewWindow.close).not.toHaveBeenCalled()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/projects/project-1/book.pdf',expect.any(Object))
  })

  it('closes the empty tab and reports the server error',async()=>{
    const previewWindow={opener:globalThis as unknown,closed:false,location:{replace:vi.fn()},close:vi.fn()}
    vi.stubGlobal('document',{cookie:''})
    vi.stubGlobal('window',{open:vi.fn(()=>previewWindow)})
    vi.stubGlobal('fetch',vi.fn(async()=>({ok:false,status:500,json:async()=>({detail:'Report could not be generated'})})))

    await expect(receiveServerFile(projectBookPath('project-1'))).rejects.toThrow('Report could not be generated')
    expect(previewWindow.close).toHaveBeenCalledOnce()
    expect(previewWindow.location.replace).not.toHaveBeenCalled()
  })
})

describe('commercial document routing',()=>{
  it('keeps quotation IDs on quotation-only endpoints',()=>{
    expect(quotationPdfPath('quote/id')).toBe('/api/v1/quotations/quote%2Fid/pdf')
    expect(quotationPdfPath('quote/id',true)).toBe('/api/v1/quotations/quote%2Fid/pdf?download=true')
    expect(quotationPdfPath('quote/id')).not.toContain('/invoices/')
  })

  it('keeps invoice IDs on invoice-only endpoints',()=>{
    expect(invoicePdfPath('invoice/id')).toBe('/api/v1/invoices/invoice%2Fid/pdf')
    expect(invoicePdfPath('invoice/id',true)).toBe('/api/v1/invoices/invoice%2Fid/pdf?download=true')
    expect(invoicePdfPath('invoice/id')).not.toContain('/quotations/')
  })

  it('uses distinct safe fallback filenames',()=>{
    expect(quotationFilename('QT-2026/0009')).toBe('Quotation_QT-2026-0009.pdf')
    expect(invoiceFilename('INV-2026/0004')).toBe('Invoice_INV-2026-0004.pdf')
    expect(quotationFilename('QT-1')).not.toBe(invoiceFilename('QT-1'))
  })

  it('keeps project and building books on their scoped report endpoints',()=>{
    expect(projectBookPath('project/id')).toBe('/api/v1/projects/project%2Fid/book.pdf')
    expect(projectBookPath('project/id',true)).toBe('/api/v1/projects/project%2Fid/book.pdf?download=true')
    expect(buildingBookPath('project/id','building/id')).toBe('/api/v1/projects/project%2Fid/buildings/building%2Fid/book.pdf')
    expect(buildingBookPath('project/id','building/id',true)).toBe('/api/v1/projects/project%2Fid/buildings/building%2Fid/book.pdf?download=true')
  })
})

describe('API error messages',()=>{
  it('formats FastAPI validation details with their field paths',()=>{
    expect(formatApiError([
      {loc:['body','customer','email'],msg:'value is not a valid email address'},
      {loc:['body','floors_data',0,'rooms',0,'requirements',0,'quantity'],msg:'Input should be greater than 0'},
    ],422)).toBe('customer.email: value is not a valid email address; floors_data.0.rooms.0.requirements.0.quantity: Input should be greater than 0')
  })

  it('keeps string API errors and provides a safe fallback',()=>{
    expect(formatApiError('Selected building does not belong to the selected project',422)).toBe('Selected building does not belong to the selected project')
    expect(formatApiError(undefined,500)).toBe('Request failed (500)')
  })
})
