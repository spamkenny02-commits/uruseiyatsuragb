from PIL import Image, ImageDraw, ImageFont
import json

def tile_bytes(im):
    return bytes(v for y in range(8) for v in [sum((im.getpixel((x,y))>=95)<<(7-x) for x in range(8))]*2)

def subtitle_image():
    from pixel_font import UPPER,OTHER
    # Display luminance: white paper, black lettering, light-gray shadow.
    subtitle=Image.new('L',(112,16),255)
    line='À LA RECHERCHE DE'
    micro={'A':'010 101 111 101 101','L':'100 100 100 100 111',
           'R':'110 101 110 101 101','E':'111 100 110 100 111',
           'C':'011 100 100 100 011','H':'101 101 111 101 101',
           'D':'110 101 101 101 110'}
    widths=[3 if ch==' ' else 4 for ch in line]
    x=(112-(sum(widths)-1))//2
    for ch,advance in zip(line,widths):
        if ch!=' ':
            rows=micro['A' if ch=='À' else ch].split()
            for y,row in enumerate(rows):
                for col,bit in enumerate(row):
                    if bit=='1':subtitle.putpixel((x+col,2+y),0)
            if ch=='À':
                subtitle.putpixel((x,0),0);subtitle.putpixel((x+1,1),0)
        x+=advance
    headline=Image.new('L',(112,16),0)
    line='MISS TOMOBIKI !'
    widths=[3 if ch==' ' else 7 for ch in line]
    x=8
    for ch,advance in zip(line,widths):
        if ch!=' ':
            rows=(UPPER|OTHER)[ch].split()
            for y,row in enumerate(rows):
                lean=1 if y<3 else 0
                for col,bit in enumerate(row):
                    if bit=='1':
                        for bold in (0,1):headline.putpixel((x+col+lean+bold,8+y),255)
        x+=advance
    subtitle.paste(170,(1,1),headline)
    subtitle.paste(0,(0,0),headline)
    # Small symmetric sparkles link the subtitle to the starry main logo.
    d=ImageDraw.Draw(subtitle)
    for cx in (2,106):
        d.point((cx,10),fill=85);d.line((cx-1,11,cx+1,11),fill=85)
        d.point((cx,12),fill=85)
    return subtitle

def apply(rom, source, root):
    # The title prompt shares source tiles with the ending. Use the private
    # title bank for its two resource records so neither screen corrupts the other.
    rom[19*0x4000:20*0x4000]=rom[4*0x4000:5*0x4000]
    for resource in (0x5e,0xd6):rom[0x3ecbc+resource*7]=19
    # Title prompt: eight 8x16 sprites replace the repeated PUSH START glyphs.
    prompt=Image.new('L',(64,16),0);pd=ImageDraw.Draw(prompt)
    pf=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',14)
    for y,line in [(0,'START !')]:
        pd.text(((64-pd.textlength(line,font=pf))/2,y),line,font=pf,fill=255,stroke_width=1,stroke_fill=85)
    prompt=prompt.point(lambda p:0 if p<45 else (85 if p<170 else 255))
    for i in range(8):
        data=bytes(sum(((round(prompt.getpixel((i*8+px,py))/85)>>plane)&1)<<(7-px) for px in range(8)) for py in range(16) for plane in range(2))
        rom[19*0x4000+0x2960+i*32:19*0x4000+0x2980+i*32]=data
        rom[0xe317+i*4:0xe31b+i*4]=bytes([0,8+i*8,2+i*2,1 if i==7 else 0])
    # Latin logo and French subtitle are isolated in the private title bank.
    for resource in (0x52,0x53):rom[0x3ecbc+resource*7]=19
    from title_logo import apply as apply_title
    apply_title(rom,root,subtitle_image())
    # Final photograph: resource D0 and sprite pattern FE, used by both
    # ending entry points. Six 8x16 sprites display a centered French FIN.
    assert source[0x3f26c:0x3f273]==bytes.fromhex('04 c0 69 20 80 00 01')
    assert source[0xa903:0xa91b]==bytes.fromhex('00 00 04 00 00 08 02 00 00 10 0c 00 00 20 0c 00 00 28 0e 00 00 30 10 01')
    rom[21*0x4000:22*0x4000]=source[4*0x4000:5*0x4000]
    rom[0x3f26c]=21
    end=Image.new('L',(48,16),0);ed=ImageDraw.Draw(end)
    ef=ImageFont.truetype('C:/Windows/Fonts/consolab.ttf',15)
    ed.text(((48-ed.textlength('FIN',font=ef))/2,-2),'FIN',font=ef,fill=255,stroke_width=1,stroke_fill=85)
    end=end.point(lambda p:0 if p<45 else (85 if p<170 else 255))
    rom[21*0x4000+0x29c0:21*0x4000+0x2ac0]=bytes(256)
    for i in range(6):
        data=bytes(sum(((round(end.getpixel((i*8+px,py))/85)>>plane)&1)<<(7-px) for px in range(8)) for py in range(16) for plane in range(2))
        off=21*0x4000+0x29c0+i*32;rom[off:off+32]=data
        rom[0xa903+i*4:0xa907+i*4]=bytes([0,4+i*8,2+i*2,1 if i==5 else 0])
    (root.parent/'outputs'/'carte_finale_fr.json').write_text(json.dumps({'text':'FIN','private_bank':21,'resource':'D0','sprite_pattern':'bank 2:$6903 / FE','source_resource':'129C0..12ABF','title_prompt_resources':'5E and D6 isolated in private bank 19'},ensure_ascii=False,indent=2),encoding='utf8')
    # Reception placard: four 8x16 sprites form a narrow 16x32 sign.
    sign=Image.new('L',(16,32),0)
    for off,x,y in [(0x30ce0,0,0),(0x30d00,0,16),(0x30d20,8,0),(0x30d40,8,16)]:
        data=source[off:off+32]
        for py in range(16):
            for px in range(8):
                c=((data[py*2]>>(7-px))&1)+2*((data[py*2+1]>>(7-px))&1)
                sign.putpixel((x+px,y+py),c*85)
    sd=ImageDraw.Draw(sign);sd.rectangle((2,2,13,29),fill=0)
    lettering=Image.new('L',(16,32),0);ld=ImageDraw.Draw(lettering)
    sf=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',9)
    for y,line in [(1,'AC'),(10,'CU'),(19,'EIL')]:
        ld.text(((16-ld.textlength(line,font=sf))/2,y),line,font=sf,fill=255)
    sign.paste(255,(0,0,16,32),lettering.point(lambda p:255 if p>=95 else 0))
    for off,x,y in [(0x30ce0,0,0),(0x30d00,0,16),(0x30d20,8,0),(0x30d40,8,16)]:
        data=bytes(sum(((round(sign.getpixel((x+px,y+py))/85)>>plane)&1)<<(7-px) for px in range(8)) for py in range(16) for plane in range(2))
        rom[off:off+32]=data
    Image.eval(sign,lambda p:255-p).resize((160,320)).save(root/'accueil_fr_preview.png')
    # Compass: Latin letters require a single sprite, without horizontal mirroring.
    font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',11)
    for i,ch in enumerate('NSEO'):
        im=Image.new('L',(8,16),0)
        ImageDraw.Draw(im).text((1,1),ch,font=font,fill=255)
        off=0x20020+i*32
        rom[off:off+32]=tile_bytes(im.crop((0,0,8,8)))+tile_bytes(im.crop((0,8,8,16)))
        pattern=0xc1fb+i*8
        rom[pattern+1]=4
        rom[pattern+6:pattern+8]=bytes([0,1])
    # Final poster frame uses thirty blocks absent from all preceding frames.
    # A private copy of the graphics bank keeps other uses of bank 5 intact.
    rom[18*0x4000:19*0x4000]=source[5*0x4000:6*0x4000]
    rom[0x3ecbc+0x59*7]=18
    maps=source[0x3518d:0x35511];last=maps[800:900]
    protected={source[0x37759+k*4+j] for k in set(maps[:800]) for j in range(4)}
    canvas=Image.new('L',(160,160),0)
    for y in range(20):
        for x in range(20):
            k=last[y//2*10+x//2]
            t=source[0x37759+k*4+y%2*2+x%2]
            if not (4<=x<16 and 4<=y<14):protected.add(t)
            off=0x16000+t*16 if t<128 else 0x16800+(t-128)*16
            data=source[off:off+16]
            for py in range(8):
                for px in range(8):
                    color=((data[py*2]>>(7-px))&1)+2*((data[py*2+1]>>(7-px))&1)
                    canvas.putpixel((x*8+px,y*8+py),85*color)
    d=ImageDraw.Draw(canvas);d.rectangle((34,44,125,105),fill=0)
    font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',9)
    lettering=Image.new('L',(160,160),0);ld=ImageDraw.Draw(lettering)
    for j,line in enumerate(['2e CONCOURS','MISS TOMOBIKI','Inscriptions','et épreuves','préliminaires',"aujourd'hui !"]):
        width=d.textlength(line,font=font)
        ld.text((80-width/2,44+j*10),line,font=font,fill=255)
    canvas.paste(255,(0,0,160,160),lettering.point(lambda p:255 if p>=95 else 0))
    available=iter(sorted(set(range(128,256))-protected));assigned={}
    originals={}
    for t in protected:
        off=0x16000+t*16 if t<128 else 0x16800+(t-128)*16
        originals[source[off:off+16]]=t
    for y in range(4,14):
        for x in range(4,16):
            crop=canvas.crop((x*8,y*8,x*8+8,y*8+8))
            data=bytes(sum(((round(crop.getpixel((px,py))/85)>>plane)&1)<<(7-px) for px in range(8)) for py in range(8) for plane in range(2))
            if data not in assigned:
                if data in originals:t=originals[data]
                else:
                    t=next(available)
                    off=18*0x4000+0x2800+(t-128)*16
                    rom[off:off+16]=data
                assigned[data]=t
            t=assigned[data];k=last[y//2*10+x//2]
            assert k not in maps[:800]
            rom[0x37759+k*4+y%2*2+x%2]=t
    Image.eval(canvas,lambda p:255-p).resize((480,480)).save(root/'poster_fr_preview.png')
    print('poster unique tiles',len(assigned))
