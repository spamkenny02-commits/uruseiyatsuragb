"""ROM extraction, isolated rebuilding and bitmap layout preview."""
from pathlib import Path
import hashlib, json, re, shutil, subprocess, sys, uuid, struct
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
SHA = '65429bd2a36a33cd8ab696be2f485b647260b327039887931cec4775c718424f'
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzéèêëàâäîïôöùûüçœÉÈÊÀÂÎÔÛÇ:;,'()-+…"
CODES = {c:i+11 for i,c in enumerate(ALPHABET)}
CODES.update({' ':0, **{str(i):i+1 for i in range(10)}, '-':0x73,'.':0x75,'!':0x76,'?':0x77,'♥':0x79,'/':0x7c})
TOKEN = re.compile(r'\[NL1\]|\[WAIT\]|<FB>|<F2>|.')

def seed():
    return json.loads((ROOT/'seed.json').read_text('utf8'))

def project(entries):
    return {'format':'miss-tomobiki-editor-1','source_sha256':SHA,
            'texts':{e['id']:e['fr'] for e in entries},
            'nine':{e['id']:e['fr_narrow_9'] for e in entries if 'fr_narrow_9' in e},
            'seven':{e['id']:e['fr_narrow_7'] for e in entries if 'fr_narrow_7' in e}}

def validate_project(data):
    expected = project(seed())
    if data.get('format') != expected['format'] or data.get('source_sha256') != SHA:
        raise ValueError('Projet incompatible avec cette révision du jeu.')
    for key in ('texts','nine','seven'):
        if not isinstance(data.get(key),dict) or set(data[key]) != set(expected[key]):
            raise ValueError(f'La rubrique {key} doit contenir tous les identifiants attendus.')
        if any(not isinstance(v,str) or '\n' in v or '\r' in v for v in data[key].values()):
            raise ValueError('Chaque texte doit être une chaîne sur une ligne ; utiliser | pour les retours.')
    # Projects from v1.5 used a blank tile over the left combat border.
    # Convert that first cell into the original renderer's skip command.
    lines=data['texts']['00E38D'].split('|')
    if len(lines)==3 and all(line.startswith('  ') for line in lines):
        data['texts']['00E38D']='|'.join('<FB>'+line[1:] for line in lines)
    return data

def validate_text(ident, text, width=None):
    if '\n' in text or '\r' in text: raise ValueError(f'{ident} : utiliser | pour les retours.')
    pos=0
    for match in TOKEN.finditer(text):
        tok=match.group()
        if tok not in ('|','[NL1]','[WAIT]','<FB>','<F2>') and tok not in CODES:
            raise ValueError(f'{ident} : caractère non disponible {tok!r}.')
        pos=match.end()
    if pos != len(text): raise ValueError(f'{ident} : texte invalide.')
    if width is not None and (len(text)>width or any(x in text for x in ('|','[','<'))):
        raise ValueError(f'{ident} : nom limité à {width} caractères, sur une ligne.')

def workspace():
    path=ROOT/'cache'/uuid.uuid4().hex
    (path/'sources').mkdir(parents=True)
    for f in (ROOT/'sources').iterdir():
        if f.is_file(): shutil.copy2(f,path/'sources'/f.name)
    return path

def check_rom(source):
    if hashlib.sha256(source).hexdigest()!=SHA:
        raise ValueError('ROM non reconnue. Choisir la ROM japonaise originale lamujp.gb (256 Ko), pas une ROM française.')

def extract(source):
    check_rom(source)
    job=workspace()
    try:
        (job/'sources/original.gb').write_bytes(source)
        run(job/'sources/extract.py')
        entries=json.loads((job/'sources/texts.json').read_text('utf8'))
        if len(entries)!=436: raise ValueError('Extraction incomplète.')
        return entries
    finally: shutil.rmtree(job)

def run(script):
    proc=subprocess.run([sys.executable,'-X','utf8',str(script)],capture_output=True,
                        encoding='utf8',timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if proc.returncode:
        error=proc.stderr.strip().splitlines()
        raise ValueError('Réinsertion refusée : '+(error[-1] if error else proc.stdout[-1000:]))

def compile_rom(source, data):
    check_rom(source);validate_project(data)
    for key,width in [('texts',None),('nine',9),('seven',7)]:
        for ident,text in data[key].items():
            validate_text(ident,text,18 if key=='texts' and ident in data['nine'] else width)
    # These strings share rows with numeric fields or multiple menu cursors.
    # Retain the verified cell positions, rather than relying on frame width.
    reference={e['id']:e['fr'] for e in seed()}
    for ident in ('00EB45','00EB6E','005BCF','00E38D','00E3B2','00E5CA','00E36B'):
        before=TOKEN.findall(reference[ident]);after=TOKEN.findall(data['texts'][ident])
        if len(before)!=len(after) or any(
            a!=b for a,b in zip(before,after)
            if a in (' ','|','[NL1]','[WAIT]','<FB>','<F2>') or ident=='005BCF' and a=='-'):
            raise ValueError(f'{ident} : positions fixes. Conserver les espaces, les commandes et le nombre de cases ; compléter les libellés courts avec des espaces.')
    job=workspace()
    try:
        target=job/'sources'
        (target/'original.gb').write_bytes(source)
        (target/'translations.txt').write_text('\n'.join(k+'='+v for k,v in data['texts'].items()),'utf8')
        (target/'ui_names.json').write_text(json.dumps({'nine':data['nine'],'seven':data['seven']},ensure_ascii=False),'utf8')
        run(target/'build.py')
        rom=(target/'fr_alpha.gb').read_bytes()
        entries=json.loads((job/'outputs/textes_japonais_francais.json').read_text('utf8'))
        problems=[]
        for e in entries:
            for context in contexts(e):
                _, warnings=preview(e,rom,context,scale=1)
                problems.extend(warnings)
        if problems: raise ValueError('\n'.join(problems[:12]))
        return rom,entries
    finally: shutil.rmtree(job)

def contexts(e):
    return ['Nom complet (18)','Commerce / combat (9)','Inventaire / équipement (7)'] if 'fr_narrow_9' in e else ['Texte']

def profile(e):
    a=e['offset'];ident=e['id']
    if e['source_bank']==1:
        if a in (0x75db,0x75f1,0x75fa): return 8,5,'Message dans le cadre portrait'
        return 18,5,'Nom / interface'
    if 0xe959<=a<0xeb03:return 14,13,'Cinématique : 14 cases par ligne'
    if 0xe6b6<=a<0xe93f:return 18,5,'Règles défilantes'
    if 0xec7d<=a<0xee31 or 0xee83<=a<0xf4dc or 0xf5d2<=a<0xfdac:
        return 10,5,'Dialogue : 3 lignes, marge comprise dans les 10 cases'
    limits={'00E490':(8,5),'00E4DD':(9,5),'00E4ED':(9,5),
            '00E5E2':(9,1),'00E5EC':(9,1),'00E5FF':(9,1),'00E62E':(9,1),'00E644':(12,1),
            '00E36B':(18,3),'00E49F':(13,1),'00E5C2':(18,1),'00E60A':(18,1),
            '00EBAD':(15,3),'00EBC9':(1,13),'00EBD7':(18,1),
            '00EBEF':(16,1),'00EBFB':(18,5)}
    if ident in limits:return *limits[ident],'Cadre fixe : préserver les espaces et les choix'
    if ident in ('00EB45','00EB6E'):return 7,15,'Colonne des statistiques : positions fixes et chiffres réservés'
    if ident in ('00E38D','00E3B2'):return 18,5,'Menu à deux colonnes : positions des curseurs à conserver'
    if 0xe3dc<=a<0xe49f:return 11,5,'Combat : emplacements de noms / valeurs à conserver'
    if 0xeb17<=a<0xeb45:return 10,1,'État : nom du personnage'
    if a==0xf8c5:return 10,5,'Dialogue portrait'
    return 18,16,'Interface / archives : positions des valeurs à conserver'

def payload(e,rom,context):
    if context.endswith('(9)') or context.endswith('(7)'):
        width=9 if context.endswith('(9)') else 7
        table=17*0x4000+(0x3500 if width==9 else 0x3700)
        for i in range(93):
            key,addr=struct.unpack_from('<HH',rom,table+i*4)
            if key==e['offset']:
                start=17*0x4000+addr-0x4000
                return rom[start:rom.index(255,start)]
        raise ValueError('Alias absent de la ROM.')
    start=e['target_bank']*0x4000+e['target_address']-0x4000
    return rom[start:start+e['target_length']-1]

def preview(e,rom,context='Texte',page=0,scale=4,grid=True):
    w,h,note=profile(e)
    if context.endswith('(9)'):w,h=9,1
    if context.endswith('(7)'):w,h=7,1
    if context.endswith('(18)'):w,h=18,1
    pages=payload(e,rom,context).split(b'\xf9')
    warnings=[];positions=[];maxrow=h;maxcol=w
    for pn,data in enumerate(pages):
        row=col=0;chars=[]
        for code in data:
            if code==0xfe:row+=2;col=0;continue
            if code==0xfc:row+=1;col=0;continue
            if code==0xfb:col+=1;continue
            if col>=w or row>=h:
                warnings.append(f"{e['id']} / {context} : page {pn+1}, case {col+1}, rangée {row+1} hors cadre ({w} × {h}).")
            chars.append((col,row,code));maxrow=max(maxrow,row+1);maxcol=max(maxcol,col+1);col+=1
        positions.append(chars)
    maxcol=min(maxcol,40);maxrow=min(maxrow,32)
    im=Image.new('RGB',((maxcol+2)*8,(maxrow+2)*8),'#e4ead3');d=ImageDraw.Draw(im)
    d.rectangle((7,7,w*8+8,h*8+8),outline='#35523c')
    for x,y,code in positions[min(page,len(pages)-1)]:
        offset=0x11800 if code==0xf2 else 0x11000+code*16
        tile=rom[offset:offset+16]
        if len(tile)!=16:continue
        for py in range(8):
            for px in range(8):
                color=((tile[py*2]>>(7-px))&1)+2*((tile[py*2+1]>>(7-px))&1)
                if color:d.point(((x+1)*8+px,(y+1)*8+py),fill='#182b1d' if x<w and y<h else '#d22c2c')
    im=im.resize((im.width*scale,im.height*scale),Image.Resampling.NEAREST)
    if grid:
        d=ImageDraw.Draw(im)
        for x in range(8,(w+1)*8+1,8):d.line((x*scale,8*scale,x*scale,(h+1)*8*scale),fill='#bcc8ac')
        for y in range(8,(h+1)*8+1,8):d.line((8*scale,y*scale,(w+1)*8*scale,y*scale),fill='#bcc8ac')
    return im,warnings

def ips(source,rom):
    result=bytearray(b'PATCH');i=0
    while i<len(rom):
        if i<len(source) and source[i]==rom[i]:i+=1;continue
        start=i;i+=1
        while i<len(rom) and i-start<65535 and (i>=len(source) or source[i]!=rom[i]):i+=1
        result+=start.to_bytes(3,'big')+(i-start).to_bytes(2,'big')+rom[start:i]
    return bytes(result)+b'EOF'
