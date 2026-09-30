import {Copy,DoorOpen,Layers3,Plus,Trash2} from 'lucide-react'
import {Button,Card,Modal} from '../../components/UI'
import {useState} from 'react'
import type {WizardData,WizardFloor} from './inquiryWizard.types'
import {key,newRoom} from './inquiryWizard.types'

export default function StepProjectStructure({data,setData}:{data:WizardData;setData:(d:WizardData)=>void}){
  const [deleteFloor,setDeleteFloor]=useState<number|null>(null)
  const setFloors=(floors:WizardFloor[])=>setData({...data,floors})
  const patchFloor=(fi:number,patch:Partial<WizardFloor>)=>setFloors(data.floors.map((f,i)=>i===fi?{...f,...patch}:f))
  const patchRoom=(fi:number,ri:number,patch:Record<string,unknown>)=>patchFloor(fi,{rooms:data.floors[fi].rooms.map((r,i)=>i===ri?{...r,...patch}:r)})
  const addFloor=()=>setFloors([...data.floors,{key:key(),name:`Floor ${data.floors.length}`,rooms:[newRoom('Room 1')]}])
  const removeRoom=(fi:number,ri:number)=>{const floor=data.floors[fi];if(floor.rooms.length<=1)return;patchFloor(fi,{rooms:floor.rooms.filter((_,i)=>i!==ri)})}

  return <>
    <Card className="wizard-surface structure-surface">
      <div className="wizard-surface-head">
        <div><span className="eyebrow">Step 2 of 5</span><h2>Project Structure</h2><p>Configure every floor independently and add the exact rooms required.</p></div>
        <Button onClick={addFloor}><Plus size={17}/> Add Floor</Button>
      </div>
      <div className="floor-editor-list">
        {data.floors.map((floor,fi)=><section className="floor-editor" key={floor.key}>
          <div className="floor-editor-head">
            <div className="floor-order"><Layers3 size={19}/><span>Floor {fi+1}</span></div>
            <label className="floor-name-field"><span>Floor Name</span><input value={floor.name} onChange={e=>patchFloor(fi,{name:e.target.value})}/></label>
            <span className="count-badge"><DoorOpen size={15}/>{floor.rooms.length} {floor.rooms.length===1?'Room':'Rooms'}</span>
            {data.floors.length>1&&<Button variant="danger" className="compact-button" onClick={()=>setDeleteFloor(fi)}><Trash2 size={15}/> Delete Floor</Button>}
          </div>
          <div className="room-editor-grid">
            {floor.rooms.map((room,ri)=><article className="room-editor" key={room.key}>
              <div className="room-editor-title">
                <div className="room-title-icon"><DoorOpen size={17}/></div><div><small>Room {ri+1}</small><b>{room.name||'Unnamed room'}</b></div>
                <div className="room-card-actions">
                  <button type="button" title="Duplicate room" onClick={()=>patchFloor(fi,{rooms:[...floor.rooms.slice(0,ri+1),{...room,key:key(),name:`${room.name} Copy`,requirements:room.requirements.map(r=>({...r}))},...floor.rooms.slice(ri+1)]})}><Copy size={15}/></button>
                  {floor.rooms.length>1&&<button type="button" title="Delete room" className="danger-icon" onClick={()=>removeRoom(fi,ri)}><Trash2 size={15}/></button>}
                </div>
              </div>
              <div className="form-grid two room-fields">
                <label>Room Name *<input value={room.name} onChange={e=>patchRoom(fi,ri,{name:e.target.value})}/></label>
                <label>Room Type<input placeholder="Office, lobby, meeting room…" value={room.room_type||''} onChange={e=>patchRoom(fi,ri,{room_type:e.target.value})}/></label>
                <label>Area (sq. ft.)<input type="number" min="0" placeholder="0" value={room.area??''} onChange={e=>patchRoom(fi,ri,{area:e.target.value?Number(e.target.value):undefined})}/></label>
                <label>Occupancy<input type="number" min="0" placeholder="0" value={room.occupancy??''} onChange={e=>patchRoom(fi,ri,{occupancy:e.target.value?Number(e.target.value):undefined})}/></label>
                <label className="span-2">Notes<textarea placeholder="Optional room notes" value={room.notes||''} onChange={e=>patchRoom(fi,ri,{notes:e.target.value})}/></label>
              </div>
            </article>)}
            <button type="button" className="add-room-card" onClick={()=>patchFloor(fi,{rooms:[...floor.rooms,newRoom(`Room ${floor.rooms.length+1}`)]})}><span><Plus size={21}/></span><b>Add Room</b><small>Create another room on {floor.name}</small></button>
          </div>
        </section>)}
      </div>
    </Card>
    <Modal open={deleteFloor!==null} title="Remove floor?" onClose={()=>setDeleteFloor(null)} footer={<><Button variant="secondary" onClick={()=>setDeleteFloor(null)}>Cancel</Button><Button variant="danger" onClick={()=>{if(deleteFloor!==null)setFloors(data.floors.filter((_,i)=>i!==deleteFloor));setDeleteFloor(null)}}>Remove Floor</Button></>}>
      {deleteFloor!==null&&<p>Removing <b>{data.floors[deleteFloor]?.name}</b> will also remove {data.floors[deleteFloor]?.rooms.length||0} rooms and all product requirements assigned to them.</p>}
    </Modal>
  </>
}
