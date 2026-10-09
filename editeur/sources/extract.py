from pathlib import Path
import json
from text_codec import decode,table
root=Path(__file__).parent;r=(root/'original.gb').read_bytes()
def ptr(a):return int.from_bytes(r[a:a+2],'little')+0x8000
def valid(a):
 if not 0xe300<=a<0xff00:return False
 e=r.find(b'\xff',a,min(a+200,0xff00))
 return e>=a and all(b<0x80 or b in (0xf2,0xf3,0xf9,0xfa,0xfb,0xfc,0xfd,0xfe) for b in r[a:e])
tables=[];occupied=set()
for a in range(0xe300,0xff00):
 if a in occupied:continue
 first=ptr(a)
 if not a+4<=first<=min(a+0x200,0xff00) or (first-a)%2:continue
 targets=[ptr(p) for p in range(a,first,2)]
 if not all(t>=first and valid(t) for t in targets):continue
 tables.append({'offset':a,'count':len(targets),'targets':targets})
 occupied.update(range(a,first))
entries={}
for t in tables:
 for i,a in enumerate(t['targets']):
  e=r.index(255,a)+1
  if a not in entries:entries[a]={'id':f'{a:06X}','offset':a,'end':e,'length':e-a,'jp':decode(r[a:e]),'fr':None,'references':[],'raw':r[a:e].hex(' ')}
  entries[a]['references'].append(t['offset']+i*2)
# Contiguous string pools delimited by their real pointer tables.
pools=[(0xe36b,0xe4fc),(0xe52c,0xe650),(0xe6b6,0xe93f),(0xe959,0xeb03),(0xeb17,0xec1f),(0xec7d,0xee31),(0xee83,0xf024),(0xf094,0xf4dc),(0xf5d2,0xfdce),(0xfdce,0xfefa)]
for start,end in pools:
 a=start
 while a<end:
  e=r.find(b'\xff',a,end)
  if e<0:print('Unterminated pool remainder',hex(a),hex(end));break
  e+=1
  if a not in entries:entries[a]={'id':f'{a:06X}','offset':a,'end':e,'length':e-a,'jp':decode(r[a:e]),'fr':None,'references':[],'raw':r[a:e].hex(' ')}
  a=e
for a,e in entries.items():
 needle=(a-0x8000).to_bytes(2,'little')
 for pos in range(0xf4dc,0xf5d2):
  if r[pos:pos+2]==needle and pos not in e['references']:e['references'].append(pos)
for e in entries.values():e['source_bank']=3
for a in [0x5287,0x5298,0x5bcf,0x75db,0x75f1,0x75fa]+[int.from_bytes(r[0x51c3+i*2:0x51c5+i*2],'little')+19 for i in range(1,98)]:
 if 0x58e0<=a<0x58ea:continue
 e=r.index(255,a)+1
 entries[a]={'id':f'{a:06X}','offset':a,'end':e,'length':e-a,'jp':decode(r[a:e]),'fr':None,'references':[],'raw':r[a:e].hex(' '),'source_bank':1}
(root/'tables.json').write_text(json.dumps(tables,ensure_ascii=False,indent=2),encoding='utf8')
(root/'texts.json').write_text(json.dumps(list(entries.values()),ensure_ascii=False,indent=2),encoding='utf8')
(root/'texts_readable.txt').write_text('\n\n'.join(f"{e['id']} ({e['length']} bytes)\n{e['jp']}" for e in sorted(entries.values(),key=lambda e:e['offset'])),encoding='utf8')
print('tables',[(hex(t['offset']),t['count']) for t in tables]);print('entries',len(entries));print('bytes',sum(e['length'] for e in entries.values()))
