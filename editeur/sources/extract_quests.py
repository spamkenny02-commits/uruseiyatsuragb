from pathlib import Path
import json,hashlib
root=Path(__file__).parent;rom=(root/'original.gb').read_bytes()
fr=dict(line.split('=',1) for line in (root/'translations.txt').read_text('utf8').splitlines())
texts={e['id']:e for e in json.loads((root/'texts.json').read_text('utf8'))}
def u16(pos):return int.from_bytes(rom[pos:pos+2],'little')
stages=[]
for stage in range(25):
    address=u16(0x5cd5+stage*2)
    assert address==0x5d07+stage*6
    heading,floor,east,south,selector,kind=rom[address:address+6]
    actor_address=u16(0x420c+selector*2)
    actor_id=rom[actor_address]
    name_address=u16(0xec1f+actor_id*2)+0x8000
    ident=f'{name_address:06X}'
    stages.append({'stage':stage,'descriptor_address':f'{address:04X}','heading_id':heading,'heading':['Nord','Est','Sud','Ouest'][heading],'floor_id':floor,'displayed_floor':floor+1,'east':east,'south':south,'actor_selector':selector,'actor_record_address':f'{actor_address:04X}','actor_id':actor_id,'actor_name_text_id':ident,'actor_fr':fr[ident].strip().replace('|',' '),'script_kind':kind})
    # $3AD8 resolves bank 3:$74DC, then the descending script counter.
    # $5F1A alternates Ataru ($072D, left) and the NPC ($0786, right).
    script_address=u16(0xf4dc+stage*2)+0x8000
    lines=[]
    for order,index in enumerate(range(kind,-1,-1)):
        text_address=u16(script_address+index*2)+0x8000
        text_id=f'{text_address:06X}'
        assert text_id in texts and text_id in fr
        raw=bytes.fromhex(texts[text_id]['raw'])
        indent=len(raw)-len(raw.lstrip(b'\xfb'))
        assert indent==(2 if order%2==0 else 1),(stage,index,text_id,indent)
        lines.append({'order':order,'counter':index,'speaker':'Ataru' if order%2==0 else stages[-1]['actor_fr'],'side':'left' if order%2==0 else 'right','text_id':text_id,'jp':texts[text_id]['jp'],'fr':fr[text_id]})
    stages[-1]['script_pointer_table']=f'{script_address:06X}'
    stages[-1]['dialogue']=lines
assert stages[0]['actor_fr']=='Ran'
assert stages[1]['actor_fr']=='Ten'
assert (stages[1]['heading'],stages[1]['east'],stages[1]['south'])==('Ouest',8,3)
assert [e['text_id'] for e in stages[0]['dialogue']]==['00F5D2','00F68C','00F660','00F7AA']
assert [e['text_id'] for e in stages[1]['dialogue']]==['00F5EB','00F623']
result={'source_sha256':hashlib.sha256(rom).hexdigest(),'method':'Static decoding of the 25-entry table at bank 1:$5CD5. Fields are compared by routine $5C69 before dispatch. Actor records resolve through $420C and name pointers through bank 3:$6C1F.','scope':'Static quest location and dialogue conditions before the ending. Runtime quest, travel and combat evidence is reported separately in verification_alpha.json and parcours_continu_verification.json. This table alone does not verify gameplay progression.','stages':stages}
out=root.parent/'outputs';out.mkdir(exist_ok=True)
(out/'structure_quetes.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
review=['# Dialogues des 25 étapes de quête','',
        'Ordre extrait des tables de la ROM japonaise. Répliques relues dans leur contexte ; ceci ne prouve pas que les 25 étapes ont été jouées.',
        'Les conditions de victoire, de remise des objets et d’ouverture des escaliers restent à vérifier dans le jeu.',
        'Le terme japonais ははぶし est conservé sous la transcription hahabushi, sans voyelle longue ajoutée.','']
for stage in stages:
    review.extend([f"## Étape {stage['stage']+1} — {stage['actor_fr']}",'',f"Étage {stage['displayed_floor']}, E{stage['east']}/S{stage['south']}, face {stage['heading'].lower()}.",''])
    for line in stage['dialogue']:
        review.extend([f"**{line['speaker']}** · `{line['text_id']}`",'',line['jp'].replace('[END]','').strip().replace('\n',' / '),'',line['fr'],''])
(out/'dialogues_quetes_relus.md').write_text('\n'.join(review),encoding='utf8')
print('\n'.join(f"{e['stage']:02} : étage {e['displayed_floor']}, E{e['east']}/S{e['south']}, {e['heading']} — {e['actor_fr']}" for e in stages))
