import {describe,expect,it} from 'vitest'
import {aggregate} from './StepBOQ'
import {emptyWizard,newFloor,newRoom,validateWizard,type WizardData} from './inquiryWizard.types'

describe('inquiry wizard domain',()=>{
  it('defaults invitation payload to an accepted customer role',()=>{
    expect(emptyWizard().portalAccess.customer_role).toBe('CUSTOMER')
  })
  it('creates a ground floor followed by numbered floors',()=>{
    expect(newFloor(0).name).toBe('Ground Floor')
    expect(newFloor(2).name).toBe('Floor 2')
  })

  it('keeps each floor room list independent',()=>{
    const data=emptyWizard()
    const first=data.floors[0]
    const second=newFloor(1)
    first.rooms.push(newRoom('Conference Room'))

    expect(first.rooms.map(room=>room.name)).toEqual(['Room 1','Conference Room'])
    expect(second.rooms.map(room=>room.name)).toEqual(['Room 1'])
    expect(first.rooms).not.toBe(second.rooms)
  })

  it('aggregates the same product deterministically across rooms and floors',()=>{
    const data:WizardData={
      ...emptyWizard(),
      floors:[
        {...newFloor(0),rooms:[{...newRoom('Reception'),requirements:[{product_id:'lighting-1',quantity:8}]}]},
        {...newFloor(1),rooms:[
          {...newRoom('Room 101'),requirements:[{product_id:'lighting-1',quantity:4}]},
          {...newRoom('Room 102'),requirements:[{product_id:'automation-1',quantity:2}]},
        ]},
      ],
    }

    expect(aggregate(data)).toEqual([
      {
        product_id:'lighting-1',
        quantity:12,
        breakdown:[
          {floor:'Ground Floor',room:'Reception',quantity:8},
          {floor:'Floor 1',room:'Room 101',quantity:4},
        ],
      },
      {
        product_id:'automation-1',
        quantity:2,
        breakdown:[{floor:'Floor 1',room:'Room 102',quantity:2}],
      },
    ])
  })

  it('returns an empty BOQ until products are assigned',()=>{
    expect(aggregate(emptyWizard())).toEqual([])
  })

  it('reports invalid email and non-positive product quantities before submission',()=>{
    const data=emptyWizard()
    data.projectName='Arcot Tower'
    data.address='Hyderabad'
    data.customerId='__new__'
    data.newCustomer={company_name:'Arcot',contact_person:'',phone:'9000000000',email:'invalid-email',address:'',city:'',state:''}
    data.floors[0].rooms[0].requirements=[{product_id:'lighting-1',quantity:0}]

    expect(validateWizard(data)).toContain('Enter a valid client email address.')
    expect(validateWizard(data)).toContain('Product quantity in Room 1 must be greater than zero.')
  })

  it('accepts a complete minimally valid inquiry',()=>{
    const data=emptyWizard()
    data.projectName='Arcot Tower'
    data.address='Hyderabad'
    data.customerId='customer-1'
    data.floors[0].rooms[0].requirements=[{product_id:'lighting-1',quantity:1}]

    expect(validateWizard(data)).toEqual([])
  })
})
