"""Integration checks using a user-supplied supported original ROM."""
from pathlib import Path
import argparse,copy,hashlib,json,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'editeur'))
import core

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--rom',type=Path,required=True)
    args=parser.parse_args()
    source=args.rom.read_bytes();core.check_rom(source)
    seed=core.seed();data=core.project(seed);expected={e['id']:e for e in seed}
    extracted=core.extract(source)
    assert len(extracted)==436
    assert all(e['raw']==expected[e['id']]['raw'] and e['jp']==expected[e['id']]['jp'] for e in extracted)
    rom,manifest=core.compile_rom(source,data)
    metadata=json.loads((ROOT/'version.json').read_text('utf8'))
    assert hashlib.sha256(rom).hexdigest()==metadata['french_rom_sha256']
    assert core.validate_project(json.loads(json.dumps(data)))==data
    legacy=copy.deepcopy(data)
    legacy['texts']['00E38D']='  Att. Objet|  Ruse État|  Fuir Parle'
    assert core.validate_project(legacy)['texts']['00E38D']==data['texts']['00E38D']
    menu=next(e for e in manifest if e['id']=='00E38D')
    assert all(line.startswith(b'\xfb\x00') for line in core.payload(menu,rom,'Texte').split(b'\xfe'))
    edited=copy.deepcopy(data)
    edited['texts']['00F5D2']='Jouez ! Choix : x, k et z. Élève, à bientôt !'
    name=next(iter(edited['nine']))
    edited['nine'][name]='Zazou';edited['seven'][name]='Zazou'
    modified,entries=core.compile_rom(source,edited)
    lookup={e['id']:e for e in entries}
    assert modified!=rom and lookup['00F5D2']['fr']==edited['texts']['00F5D2']
    for context in core.contexts(lookup[name])[1:]:
        assert core.payload(lookup[name],modified,context)==bytes(core.CODES[c] for c in 'Zazou')
    for ident,key,value in [('00E959','texts','A'*15),(name,'nine','A'*10),
                            ('00E5EC','texts','Achat ?'),('00F5D2','texts','€'),
                            ('00EB45','texts','État :|PV 999')]:
        bad=copy.deepcopy(data);bad[key][ident]=value
        try:core.compile_rom(source,bad)
        except ValueError:pass
        else:raise AssertionError(f'Invalid modification accepted: {ident}')
    patch=core.ips(source,modified);pos=5;patched=bytearray(source)
    while patch[pos:pos+3]!=b'EOF':
        address=int.from_bytes(patch[pos:pos+3],'big')
        length=int.from_bytes(patch[pos+3:pos+5],'big');pos+=5
        assert length
        if len(patched)<address+length:patched.extend(bytes(address+length-len(patched)))
        patched[address:address+length]=patch[pos:pos+length];pos+=length
    assert bytes(patched)==modified
    assert int.from_bytes(modified[0x14e:0x150],'big')==(sum(modified)-sum(modified[0x14e:0x150]))&65535
    print('OK: 436 entries; current ROM SHA-256; combat margins and legacy projects; dialogue and aliases; invalid edits; IPS roundtrip.')

if __name__=='__main__':main()
