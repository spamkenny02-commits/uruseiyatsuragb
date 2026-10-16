"""Insert the Latin title logo using only title-exclusive tiles and blocks."""
from PIL import Image,ImageDraw

def artwork(root):
    logo=Image.open(root/'title_logo.png').convert('L')
    assert logo.size==(152,44) and set(logo.getdata())<={0,85,170,255}
    foreground=Image.new('L',(160,48),255)
    foreground.paste(logo,(4,2))
    # Fill only exterior white pixels; enclosed white outlines, letter
    # counters and the star inside R remain opaque for legibility.
    exterior=foreground.copy()
    ImageDraw.floodfill(exterior,(0,0),128,thresh=0)
    mask=exterior.point(lambda value:0 if value==128 else 255)
    stars=Image.open(root/'title_background.png').convert('L')
    assert stars.size==(16,16) and set(stars.getdata())<={0,85,170,255}
    canvas=Image.new('L',(160,48),255)
    for y in range(0,48,16):
        for x in range(0,160,16):canvas.paste(stars,(x,y))
    canvas.paste(foreground,(0,0),mask)
    return canvas

def encode_tile(image):
    return bytes(sum(((int((255-image.getpixel((x,y)))//85)>>plane)&1)<<(7-x)
                     for x in range(8)) for y in range(8) for plane in range(2))

def apply(rom,root,subtitle):
    base=19*0x4000+0x3000;blocks=0x374c1;map_start=0x34f85
    maps=bytearray(rom[map_start:map_start+200])
    original_tiles=bytes(rom[base:base+0x1000])
    # Everything after the first eight tile rows is immutable, including
    # the complete second title page and its French start menu.
    protected_blocks=set(maps[40:])
    protected_tiles={rom[blocks+k*4+j] for k in protected_blocks for j in range(4)}
    # The menu writes this cursor dynamically, so it is absent from its map.
    protected_tiles.add(0xd5)
    available_tiles=iter(sorted(set(range(256))-protected_tiles))
    assigned={bytes(rom[base+t*16:base+(t+1)*16]):t for t in protected_tiles}
    initial_tiles=len(assigned)
    new_tiles=0
    logo=artwork(root)
    grid=[]
    for y in range(8):
        row=[]
        for x in range(20):
            if y<6:
                data=encode_tile(logo.crop((x*8,y*8,x*8+8,y*8+8)))
            elif 4<=x<18:
                data=encode_tile(subtitle.crop(((x-4)*8,(y-6)*8,(x-3)*8,(y-5)*8)))
            else:
                k=maps[y//2*10+x//2]
                t=rom[blocks+k*4+y%2*2+x%2]
                data=original_tiles[t*16:(t+1)*16]
            if data not in assigned:
                t=next(available_tiles,None)
                assert t is not None,'Title logo exceeds available tile capacity'
                assigned[data]=t;new_tiles+=1
                rom[base+t*16:base+(t+1)*16]=data
            row.append(assigned[data])
        grid.append(row)
    # Reuse a protected block only if its four tiles match exactly. Other
    # patterns use original block slots exclusive to the replaced region.
    patterns={bytes(rom[blocks+k*4:blocks+k*4+4]):k for k in protected_blocks}
    available_blocks=iter(sorted(set(maps[:40])-protected_blocks))
    new_blocks=0
    for by in range(4):
        for bx in range(10):
            data=bytes(grid[by*2+dy][bx*2+dx] for dy in range(2) for dx in range(2))
            if data not in patterns:
                k=next(available_blocks,None)
                assert k is not None,'Title logo exceeds available block capacity'
                patterns[data]=k;new_blocks+=1
                rom[blocks+k*4:blocks+k*4+4]=data
            maps[by*10+bx]=patterns[data]
    rom[map_start:map_start+200]=maps
    print('Latin title logo',new_tiles,'new tiles;',new_blocks,'exclusive blocks')
