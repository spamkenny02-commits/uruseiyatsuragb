from pathlib import Path
import json,hashlib
root=Path(__file__).parent;rom=(root/'original.gb').read_bytes();bank=rom[15*0x4000:16*0x4000]
assert bank[0]==ord('M')
floors=[];stairs=[];directions=[(0,-1),(1,0),(0,1),(-1,0)]
for floor in range(7):
 map_ptr=int.from_bytes(bank[1+floor*2:3+floor*2],'little')
 room_ptr=int.from_bytes(bank[0x70f+floor*2:0x711+floor*2],'little')
 cells=list(bank[map_ptr-0x4000:map_ptr-0x4000+256]);assert len(cells)==256
 floors.append({'floor_id':floor,'displayed_floor':floor+1,'map_address':f'{map_ptr:04X}','room_table_address':f'{room_ptr:04X}','cells':cells})
 for index,room in enumerate(cells):
  if room==255:continue
  assert room>=10
  record=bank[room_ptr-0x4000+(room-10)*12:room_ptr-0x4000+(room-10)*12+12]
  for heading,resource in enumerate(record[:4]):
   if resource not in (0xce,0xcf):continue
   destination_floor=floor+(1 if resource==0xcf else -1)
   dx,dy=directions[heading];x,y=index%16,index//16
   assert 0<=destination_floor<7
   stairs.append({'floor_id':floor,'east':x,'south':y,'heading_id':heading,'resource':f'{resource:02X}','destination_floor_id':destination_floor,'destination_east':x+2*dx,'destination_south':y+2*dy,'minimum_quest_stage':rom[0x5dbd+floor] if resource==0xcf else 0})
for stair in stairs:
 other=next((s for s in stairs if s['floor_id']==stair['destination_floor_id'] and s['east']==stair['destination_east'] and s['south']==stair['destination_south'] and s['heading_id']==(stair['heading_id']+2)%4 and s['destination_floor_id']==stair['floor_id']),None)
 assert other,stair
assert len(stairs)%2==0
report={'source_sha256':hashlib.sha256(rom).hexdigest(),'method':'bank 15 map pointers at $4001 and twelve-byte room records through $470F; resources CF/CE in the four heading fields select ascending/descending stairs; the original transition moves two cells in that heading','scope':'Static extraction and reciprocal-link checks. Runtime stair coverage is reported separately in escaliers_sakura_verification.json and parcours_continu_verification.json; it must not be inferred from this static table.','floors':floors,'stairs':stairs}
(root.parent/'outputs/structure_labyrinthe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'floors':len(floors),'stairs':stairs},ensure_ascii=False))
