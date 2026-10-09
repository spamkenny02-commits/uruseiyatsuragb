from pathlib import Path
import json,hashlib,struct,re
from PIL import Image,ImageFont,ImageDraw
root=Path(__file__).parent;out=root.parent/'outputs';out.mkdir(exist_ok=True)
source=(root/'original.gb').read_bytes()
assert hashlib.sha256(source).hexdigest()=='65429bd2a36a33cd8ab696be2f485b647260b327039887931cec4775c718424f'
entries=json.loads((root/'texts.json').read_text('utf8'))
fr=dict(line.split('=',1) for line in (root/'translations.txt').read_text('utf8').splitlines())
assert len(fr)==len(entries) and all(e['id'] in fr for e in entries)
rom=bytearray(source)+bytearray([255])*(0x80000-len(source))
rom[0x147:0x14a]=bytes([0x1b,4,2]) # MBC5+RAM+battery, 512 KiB ROM, 8 KiB RAM
alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzéèêëàâäîïôöùûüçœÉÈÊÀÂÎÔÛÇ:;,\'()-+…'
assert len(alphabet)<=0x72-0x0b
codes={c:i+11 for i,c in enumerate(alphabet)}
codes.update({' ':0,**{str(i):i+1 for i in range(10)},'-':0x73,'.':0x75,'!':0x76,'?':0x77,'♥':0x79,'/':0x7c})
from pixel_font import glyph, tile as font_tile
sheet=Image.new('RGB',(16*40,8*40),'white');sd=ImageDraw.Draw(sheet)
for ch,code in codes.items():
 im=glyph(ch)
 data=font_tile(ch)
 rom[0x11000+code*16:0x11010+code*16]=data
 x=code%16*40;y=code//16*40;sd.text((x,y),f'{code:02X}',fill='red');sheet.paste(Image.eval(im,lambda p:255-p).resize((24,24)),(x,y+12))
sheet.save(out/'fonte_francaise.png')
# F2 prints the resource-11 colon rather than the ordinary alphabet tile.
rom[0x11800:0x11810]=font_tile(':')
# The startup menu is baked into background tiles, separate from dialogue fonts.
menu_glyphs=[0xd5,0xd8,0xdc,0xdd,0xdf,0xde,0xe0,0xe3,0xe6,0xe9,0xeb,0xf2,0xf3,0xf8,0xdb]
menu_chars=sorted(set('JouerSuiteChoix?')-{' '})
assert len(menu_chars)<=len(menu_glyphs)
menu_codes=dict(zip(menu_chars,menu_glyphs))
for ch,tile in menu_codes.items():
 data=font_tile(ch)
 rom[0x13000+tile*16:0x13010+tile*16]=data
menu_map=bytearray(source[0x34fe9:0x3504d]);available=[0x47,0x49,0x4c,0x53,0x56,0x4a,0x4d,0x4f,0x51,0x54]
blocks={};used=0
for y in (6,7):
 row=[0]*20
 for x,s in ([(3,'Jouer'),(12,'Suite')] if y==6 else [(6,'Choix ?')]):
  for j,ch in enumerate(s):row[x+j]=menu_codes.get(ch,0)
 for x in range(1,9):
  block=bytes([0,0,row[x*2],row[x*2+1]])
  if block==b'\0\0\0\0':idx=0x41
  else:
   if block not in blocks:
    idx=available[used];used+=1;blocks[block]=idx
    off=0x374c1+idx*4;rom[off:off+4]=block
   idx=blocks[block]
  menu_map[y*10+x]=idx
rom[0x34fe9:0x3504d]=menu_map
def encode(text):
 result=bytearray()
 for tok in re.findall(r'\[NL1\]|\[WAIT\]|<[0-9A-F]{2}>|.',text):
  if tok=='|':result.append(0xfe)
  elif tok=='[NL1]':result.append(0xfc)
  elif tok=='[WAIT]':result.append(0xf9)
  elif tok.startswith('<'):result.append(int(tok[1:3],16))
  else:result.append(codes[tok])
 return bytes(result)+b'\xff'
HYPHENATION={
 'accusations':'ac-cu-sa-tions','bandage':'ban-da-ge','compagnie':'com-pa-gnie',
 'divinatoire':'di-vi-na-toire','escaliers':'es-ca-liers','hahabushi':'ha-ha-bu-shi',
 'impardonnable':'im-par-don-na-ble','impossible':'im-pos-si-ble',
 "l'arracher":"l'ar-ra-cher",'pardonnerai':'par-don-ne-rai','pellicule':'pel-li-cu-le',
 'photographier':'pho-to-gra-phier','plaisante':'plai-san-te',
 'précieusement':'pré-cieu-se-ment','reprendre':'re-pren-dre',
 'réfléchirai':'ré-flé-chi-rai','shimenawa':'shi-me-na-wa','pipipipipi':'pi-pi-pi-pi-pi',
 'production':'pro-duc-tion','conception':'con-cep-tion','graphismes':'gra-phis-mes',
 'programmation':'pro-gram-ma-tion','remerciements':'re-mer-cie-ments',
 'shimoyama':'shi-mo-ya-ma','wakabayashi':'wa-ka-ba-ya-shi',
 'matsumura':'ma-tsu-mu-ra','toshitsugu':'to-shi-tsu-gu',
}
def wrapped_dialogue(text,width):
 # Keep punctuation with its preceding word, and do not fill spare columns
 # using a fragment of the next long word. The font also has an ellipsis.
 words=[]
 for word in text.replace('...','…').split():
  if words and re.fullmatch(r'[!?;:♥…]+',word):
   joined=words[-1]+' '+word
   words[-1]=joined if len(joined)<=width else words[-1]+word
  else:words.append(word)
 lines=[];line=''
 for word in words:
  if len(word)>width:
   if line:lines.append(line);line=''
   suffix=re.search(r'[.!?,;:♥…]+$',word)
   core=word[:suffix.start()] if suffix else word
   cuts=[]
   if core.lower() in HYPHENATION:
    position=0
    for part in HYPHENATION[core.lower()].split('-')[:-1]:
     position+=len(part);cuts.append(position)
   used=0
   while len(word)>width:
    existing=[i+1 for i,c in enumerate(word) if c=='-' and 2<=i+1<=width and len(core)-used-i-1>=2]
    choices=[i-used for i in cuts if 2<=i-used<=width-1 and len(core)-i>=2]
    if existing:cut=existing[-1];chunk=word[:cut]
    else:
     cut=choices[-1] if choices else min(width-1,len(core)-used-2)
     assert cut>=2,(word,width)
     chunk=word[:cut]+'-'
    lines.append(chunk);word=word[cut:];used+=cut
  if line and len(line)+1+len(word)>width:lines.append(line);line=''
  line=(line+' '+word).strip()
 if line:lines.append(line)
 punctuation_only=bool(re.fullmatch(r'[!?;:♥…]+',text.strip()))
 assert all(len(line)<=width and (punctuation_only or not re.fullmatch(r'[!?;:♥…]+',line)) for line in lines),(text,lines)
 # Formatting may add a line-end hyphen, but must retain every letter and
 # punctuation mark from the translation.
 normalized=lambda s:re.sub(r'[\s-]','',s.replace('…','...'))
 assert normalized(''.join(lines))==normalized(text),(text,lines)
 return lines or ['']
def paged(text,width=10,rows=3,indent=0):
 lines=wrapped_dialogue(text,width)
 pages=[]
 while lines:
  # Four remaining lines read better as two pages of two lines.
  take=rows-1 if len(lines)==rows+1 else rows
  pages.append('|'.join('<FB>'*indent+line for line in lines[:take]))
  lines=lines[take:]
 return '[WAIT]'.join(pages)
def paged_credit(text,width,indent):
 # Keep a person's given name and surname together on the same page,
 # and keep the original role/name sections separate when they do not fit.
 pages=[];current=[]
 for section in text.split('|'):
  lines=wrapped_dialogue(section,width)
  if current and len(current)+len(lines)>3:pages.append(current);current=[]
  while len(lines)>3:
   pages.append(lines[:3]);lines=lines[3:]
  current.extend(lines)
 if current:pages.append(current)
 return '[WAIT]'.join('|'.join('<FB>'*indent+line for line in page) for page in pages)
class Asm:
 def __init__(self,start):self.start=start;self.data=bytearray();self.labels={};self.fix=[]
 @property
 def pc(self):return self.start+len(self.data)
 def emit(self,*values):self.data.extend(values);return self
 def raw(self,s):self.data.extend(bytes.fromhex(s));return self
 def label(self,s):self.labels[s]=self.pc;return self
 def jr(self,opcode,target):self.emit(opcode,0);self.fix.append((len(self.data)-1,target,False));return self
 def jp(self,opcode,target):self.emit(opcode,0,0);self.fix.append((len(self.data)-2,target,True));return self
 def finish(self):
  for i,t,absolute in self.fix:
   dest=self.labels[t]
   if absolute:self.data[i:i+2]=dest.to_bytes(2,'little')
   else:
    v=dest-(self.start+i+1);assert -128<=v<=127;self.data[i]=v&255
  return self.data
def mapper(n,shop=False):
 a=Asm(0x7000)
 a.raw('c5 d5 fa ff df b7').jp(0xc2,'done')
 a.raw('fa e3 d0 ea f8 df fa e4 d0 ea f9 df')
 a.raw('fa 8e d1 5f fa 8f d1 57')
 if shop:
  # SP+6 is the original caller of $3B28 after its CALL $00F7 and our
  # two pushes. Call sites distinguish a full-width name, a priced row,
  # or a narrow inventory cell without depending on transient menu flags.
  a.raw('f8 06 4e 23 46 21 00 79')
  a.label('context').raw('2a fe ff').jr(0x28,'full_names')
  a.raw('b9').jr(0x20,'context_skip_hi').raw('2a b8').jr(0x20,'context_skip_id')
  a.raw('7e fe 01').jr(0x28,'nine_names').raw('21 00 77').jr(0x18,'lookup')
  a.label('context_skip_hi').raw('23')
  a.label('context_skip_id').raw('23').jr(0x18,'context')
  a.label('nine_names').raw('21 00 75').jr(0x18,'lookup')
  a.label('full_names').raw('21 00 73')
  a.label('lookup')
 else:a.raw('21 00 71')
 a.raw('01').emit(n&255,n>>8)
 a.label('loop').raw('2a bb').jr(0x20,'skip_hi').raw('2a ba').jr(0x20,'skip_new')
 a.raw('2a ea 8e d1 7e ea 8f d1').jr(0x18,'found')
 a.label('skip_hi').raw('23').label('skip_new').raw('23 23 0b 78 b1').jr(0x20,'loop')
 a.label('found').raw('3e 01 ea ff df')
 a.label('done').raw('fa 8e d1 d1 c1 c9')
 return a.finish()
manifest=[]
shop_names=json.loads((root/'shop_names.json').read_text('utf8'))
ui_names=json.loads((root/'ui_names.json').read_text('utf8'))
name_callers={
 **{address+3:1 for address in [0x23c8,0x2410,0x2458,0x24a0,0x24e8,0x61e0,0x6282]},
 **{address+3:2 for address in [0x20a3,0x20b7,0x20cb,0x20df,0x20f3,0x2107,0x211b,0x212f,0x6eb8,0x6ed6,0x6ef4,0x6f11,0x6f54,0x6f72,0x6f90,0x6fad,0x6fe7,0x7005,0x7023,0x7041]},
}
assert all(source[address-3:address]==bytes.fromhex('cd 28 3b') and address&255!=255 for address in name_callers)
ending_layout={}
for stage in range(25,56):
 pointer=int.from_bytes(source[0xf024+stage*2:0xf026+stage*2],'little')+0x8000
 ending_layout[pointer]=(stage,1 if stage<=29 or stage%2 else 2)
assert len(ending_layout)==31
for bank,srcbank in [(16,3),(17,1)]:
 subset=sorted([e for e in entries if e['source_bank']==srcbank],key=lambda e:e['offset'])
 cursor=0x4000;mapping=bytearray()
 for e in subset:
  text=fr[e['id']]
  if e['id'] in ['00E5E2','00E5EC','00E5FF','00E62E','00E644']:
   assert '|' not in text and len(text)<=({'00E5E2':9,'00E5EC':9,'00E5FF':9,'00E62E':9,'00E644':12}[e['id']]),(e['id'],text,'reserve box overlap')
  if e['id']=='00E5EC':assert text[0]==text[4]==' ',('shop confirmation cursors',text)
  if e['id']=='00E635':assert text[3]==text[9]==' ',('sale confirmation cursors',text)
  if e['id'] in ['00E582','00E620']:assert len(text)<=17 and text[4]==text[9]==' ' and text[5:8]=='Oui' and text[10:13]=='Non',('lobby confirmation cursors',text)
  if e['id']=='00EBAD':assert len(text.split('|')[0])<=15 and text.split('|')[1]==' Oui     Non',('exit frame and cursors',text)
  if e['id'] in ['00E4DD','00E4ED']:
   assert len(text.split('|'))==3 and all(len(line)<=9 for line in text.split('|')),(e['id'],text)
  if e['id']=='00E490':
   assert len(text.split('|'))<=3 and all(len(line)<=8 for line in text.split('|')),(e['id'],text)
  if srcbank==3 and 0xec7d<=e['offset']<0xee31:
   lines=[line.strip() for line in text.split('|')]
   assert len(lines)<=2 and all(len(line)<=10 for line in lines),(e['id'],lines)
   text='|'.join('<FB>'*((10-len(line))//2)+line for line in lines)
  if srcbank==3 and 0xee83<=e['offset']<0xf234:text=paged(text,width=9,indent=1)
  if srcbank==3 and e['offset'] in ending_layout:
   stage,indent=ending_layout[e['offset']]
   text=(paged_credit(text,10-indent,indent) if e['offset']>=0xf2f5 else paged(text,width=10-indent,indent=indent))
  if srcbank==3 and 0xf5d2<=e['offset']<0xfdac:
   raw=bytes.fromhex(e['raw']);indent=len(raw)-len(raw.lstrip(b'\xfb'))
   text=paged(text,width=10-indent,indent=indent)
  data=encode(text)
  assert 0xfa not in data and 0xfd not in data,'French uses dedicated accent glyphs, not voicing commands'
  assert cursor+len(data)<0x7000,(e['id'],hex(cursor))
  off=bank*0x4000+cursor-0x4000;rom[off:off+len(data)]=data
  orig=e['offset']-0x8000 if srcbank==3 else e['offset']
  mapping+=struct.pack('<HH',orig,cursor)
  manifest.append({**e,'fr':fr[e['id']],'fr_encoded_layout':text,'target_bank':bank,'target_address':cursor,'target_length':len(data)})
  cursor+=len(data)
 # Paginated dialogue restarts the setter with a French address. Keep its
 # address range disjoint from the Japanese pointer keys so it cannot remap.
 if srcbank==3:assert cursor<min(e['offset']-0x8000 for e in subset)
 if srcbank==1:
  for width,address in [(9,0x7500),(7,0x7700)]:
   compact_mapping=bytearray()
   for e in subset:
    original=e['offset'];full=next(m for m in manifest if m['id']==e['id']);target=full['target_address']
    if 0x52bc<=original<=0x5bc5:
     compact=ui_names['nine'].get(e['id'],shop_names.get(e['id'],fr[e['id']]))
     if width==7:compact=ui_names['seven'].get(e['id'],compact)
     assert len(compact)<=width,(e['id'],width,compact)
     assert len(fr[e['id']])<=18,(e['id'],fr[e['id']])
     data=encode(compact);target=cursor
     off=bank*0x4000+cursor-0x4000;rom[off:off+len(data)]=data
     cursor+=len(data);full['fr_narrow_9' if width==9 else 'fr_narrow_7']=compact
     if width==9:full['fr_shop']=compact
    compact_mapping+=struct.pack('<HH',original,target)
   off=bank*0x4000+address-0x4000;rom[off:off+len(compact_mapping)]=compact_mapping
  assert cursor<0x7000
  contexts=b''.join(struct.pack('<HB',address,kind) for address,kind in sorted(name_callers.items()))+b'\xff'
  off=bank*0x4000+0x3900;rom[off:off+len(contexts)]=contexts
  (out/'contextes_noms_fr.json').write_text(json.dumps({'caller_return_addresses':{f'{a:04X}':kind for a,kind in name_callers.items()},'kinds':{'0':'full name, up to 18 tiles','1':'priced list or combat, up to 9 tiles','2':'inventory/equipment cells, up to 7 tiles'},'selection':'original caller of the bank-1 name renderer; full names retained in expanded confirmation windows'},ensure_ascii=False,indent=2),encoding='utf8')
 off=bank*0x4000+0x3000;code=mapper(len(subset),shop=srcbank==1);rom[off:off+len(code)]=code
 assert len(code)<(0x300 if srcbank==1 else 0x100)
 off=bank*0x4000+(0x3300 if srcbank==1 else 0x3100);rom[off:off+len(mapping)]=mapping
 print('bank',bank,'entries',len(subset),'text bytes',cursor-0x4000,'map bytes',len(mapping))
def patch(a,old,new):
 expected=bytes.fromhex(old);value=bytes.fromhex(new);assert len(value)==len(expected);assert source[a:a+len(expected)]==expected,(hex(a),source[a:a+len(expected)].hex())
 rom[a:a+len(value)]=value
# Fixed-bank trampolines live exclusively in unused padding between vectors.
patch(0x00ef,'00 '*16,'3e 10 ea 00 21 c3 00 70 3e 11 ea 00 21 c3 00 70')
patch(0x0051,'00 '*7,'f3 af ea ff df 18 01')
patch(0x0059,'00 '*5,'7d ea 8e d1 c9')
patch(0x0042,'00 '*6,'ea e6 d0 c3 4a 00')
patch(0x004a,'00 '*6,'3c ea 00 21 af c9')
patch(0x3a72,'f3 7d ea 8e d1','cd 51 00 00 00')
patch(0x42c7,'f3 7d ea 8e d1','cd 51 00 00 00')
patch(0x0b02,'11 46 99','11 42 99')
patch(0x0bdb,'11 47 9c','11 42 9c')
patch(0x714c,'11 47 9c','11 61 9c') # Full status name on the free row below État/NV.
patch(0x15d7,'e3 9d','e1 9d') # Achat cursor in the blank before its full label.
patch(0x15d9,'e8 9d','e7 9d') # Vente cursor in the following separator.
patch(0x1251,'11 47 9c','11 42 9c')
patch(0x3921,'cd 71 32','cd ef 00')
# The original F9 branch waits with interrupts disabled, clears rows 1..6,
# and reuses the last line origin. Enable VBlank and establish the next page.
patch(0x39b3,'cd 39 16 fa ce d0 cb 47','fb cd 39 16 fa ce d0 0f')
patch(0x39bb,'ca 24 39','d2 20 39')
# Reuse the obsolete Japanese voicing routines for a clear/reset routine.
# The captured page origin works in either portrait window as well as the
# central dialogue box. French accents are standalone tiles (asserted above).
page_reset=Asm(0x7800)
# Preserve the Japanese skip commands: drawing blank glyphs over the
# skipped columns erases the frame. Clear only the inner text rectangle.
page_reset.raw('fa 8e d1 6f fa 8f d1 67 23 06 00')
page_reset.label('indent').raw('2a fe fb').jr(0x20,'clear').raw('04').jr(0x18,'indent')
page_reset.label('clear').raw('fa f8 df 6f fa f9 df 67 e5 11 e0 ff 19 78 85 6f 3e 00 8c 67 3e 0a 90 57 0e 05 cd 8b 3a e1 7d ea e3 d0 ea e5 d0 7c ea e4 d0 ea e6 d0 c9')
page_reset=page_reset.finish()
rom[16*0x4000+0x3800:16*0x4000+0x3800+len(page_reset)]=page_reset
trampoline=bytes.fromhex('3e 10 ea 00 21 c3 00 78')
rom[0x39f3:0x3a1b]=trampoline+bytes(0x3a1b-0x39f3-len(trampoline))
patch(0x39be,'21 49 9a 0e 06 16 0a cd 8b 3a','cd f3 39 00 00 00 00 00 00 00')
patch(0x39d9,'fa e5 d0 ea e3 d0 fa e6 d0 ea e4 d0','00 '*12)
patch(0x39e5,'c3 24 39','c3 20 39')
patch(0x3b28,'f3 fa 8e d1','f3 cd f7 00')
patch(0x3b8a,'ea e6 d0','cd 42 00')
from localize_graphics import apply
apply(rom,source,root)
from credits_graphics import apply as apply_credits
apply_credits(rom,source,root)
rom[0x14d]=(-sum(rom[0x134:0x14d])-25)&255
rom[0x14e:0x150]=b'\0\0';rom[0x14e:0x150]=(sum(rom)&65535).to_bytes(2,'big')
(root/'fr_alpha.gb').write_bytes(rom)
(out/'textes_japonais_francais.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
(out/'traduction.txt').write_text((root/'translations.txt').read_text('utf8'),encoding='utf8')
(out/'table_francaise.tbl').write_text('\n'.join(f'{code:02X}={ch}' for ch,code in codes.items()),encoding='utf8')
print('ROM sha256',hashlib.sha256(rom).hexdigest())
