from pathlib import Path
chars=' 0123456789あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんゃゅょっアイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンィャュョッじ、どー・。！？ェ♥AC／LOV'
table={i:c for i,c in enumerate(chars)}
# Two extra font tiles are loaded separately from the base kana font.
# Confirmed in live VRAM at $9720 and $9730, including the voiced び tile.
table.update({0xf2:':',0xf3:'び'})
def decode(data):
 out='';i=0
 while i<len(data):
  b=data[i];i+=1
  if b==0xff:out+='[END]';break
  if b in (0xfd,0xfa):
   if i<len(data):
    c=table.get(data[i],f'<{data[i]:02X}>');i+=1
    import unicodedata
    out+=unicodedata.normalize('NFC',c+('\u3099' if b==0xfd else '\u309a'))
  elif b in (0xfe,0xfc):out+='\n' if b==0xfe else '[NL1]'
  elif b==0xfb:out+=' '
  elif b==0xf9:out+='[WAIT]'
  else:out+=table.get(b,f'<{b:02X}>')
 return out
if __name__=='__main__':
 import sys
 r=(Path(__file__).parent/'original.gb').read_bytes()
 start=int(sys.argv[1],16);end=int(sys.argv[2],16)
 for a in range(start,end,32):print(f'{a:06X} '+decode(r[a:min(a+32,end)]).replace('\n','[NL]'))
