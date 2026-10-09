from PIL import Image,ImageDraw,ImageFont
import json,itertools

PAGES=[('Programmation','Shunichi Sekiguchi'),('Graphisme','Norikazu Shimizu'),('Musique','Yûsuke Takahama'),('Conception','Kuniharu Hosoda'),('Conception','Masanobu Fukasawa'),('Direction','Kuniharu Hosoda')]

def apply(rom,source,root):
    # The alternate credit sequence has six bitmap pages, not dialogue strings.
    rom[20*0x4000:21*0x4000]=source[7*0x4000:8*0x4000]
    rom[0x3ecbc+0x5a*7]=20
    from pixel_font import glyph, tile
    letters=sorted(set(''.join(a+b for a,b in PAGES))-{' '})
    codes={' ':0,**{c:i+2 for i,c in enumerate(letters)}}
    rom[20*0x4000+0x3000:20*0x4000+0x3020]=bytes(16)+bytes([255])*16
    for ch,code in codes.items():
        if code==0:continue
        data=tile(ch)
        off=20*0x4000+0x3000+code*16;rom[off:off+16]=data
    blocks={};frames=bytearray()
    # Choose one of two adjacent centering positions to reuse character pairs.
    # This keeps all six complete names within the original block table.
    lines=list(dict.fromkeys(line for page in PAGES for line in page))
    best=(999,None)
    for shifts in itertools.product([0,1],repeat=len(lines)):
        pairs=set()
        for line,shift in zip(lines,shifts):
            text=(' '*((20-len(line))//2+shift)+line).ljust(20)
            pairs.update(text[i:i+2] for i in range(0,20,2))
        if len(pairs)<best[0]:best=(len(pairs),dict(zip(lines,shifts)))
    for index,(role,name) in enumerate(PAGES):
        grid=[[1 if y<4 or y>=14 else 0 for x in range(20)] for y in range(20)]
        for y,line in [(6,role),(10,name)]:
            assert len(line)<=20
            x=(20-len(line))//2+best[1][line]
            for i,ch in enumerate(line):grid[y][x+i]=codes[ch]
        for y in range(10):
            for x in range(10):
                block=bytes(grid[y*2+dy][x*2+dx] for dy in range(2) for dx in range(2))
                if block not in blocks:blocks[block]=len(blocks)
                frames.append(blocks[block])
    assert len(blocks)*4<=0x7c19-0x7b41,('credit blocks',len(blocks))
    for block,index in blocks.items():rom[0x37b41+index*4:0x37b45+index*4]=block
    rom[0x355b1:0x35809]=frames
    (root.parent/'outputs'/'credits_graphiques_fr.json').write_text(json.dumps({'pages':PAGES,'block_count':len(blocks),'source_map':'355B1','source_resource':'5A','private_bank':20,'name_readings':'Phonetic credits in the original ROM; Masanobu Fukasawa additionally checked against https://www.mobygames.com/person/61220/masanobu-fukazawa/'},ensure_ascii=False,indent=2),encoding='utf8')
    print('alternate credits tiles',len(codes)+1,'blocks',len(blocks))
