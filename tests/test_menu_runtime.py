"""Menu regressions: real startup inputs and an isolated combat-renderer fixture."""
from pathlib import Path
import argparse,shutil,sys,uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'editeur'))
import core

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--rom',type=Path,required=True)
    parser.add_argument('--pyboy-deps',type=Path)
    args=parser.parse_args()
    if args.pyboy_deps:sys.path.insert(0,str(args.pyboy_deps))
    from pyboy import PyBoy
    source=args.rom.read_bytes();rom,entries=core.compile_rom(source,core.project(core.seed()))
    folder=core.ROOT/'cache'/uuid.uuid4().hex;folder.mkdir(parents=True)
    target=folder/'test.gb';target.write_bytes(rom)
    p=None
    try:
        p=PyBoy(str(target),window='null',sound_emulated=False);p.set_emulation_speed(0)
        def press(key):
            p.button_release(key);p.tick(2);p.button_press(key);p.tick(10);p.button_release(key);p.tick(180)
        p.tick(600);press('start')
        codes=dict(zip(sorted(set('JouerSuiteChoix?')-{' '}),
            [0xd8,0xdc,0xdd,0xdf,0xde,0xe0,0xe3,0xe6,0xe9,0xeb,0xf2,0xf3,0xf8,0xdb]))
        cursor=0x8800+(0xd5-128)*16
        assert bytes(p.memory[cursor:cursor+16])==source[0x13d50:0x13d60]
        for key in [None,'right','left','right','left','right','left']:
            if key:press(key)
            assert bytes(p.memory[0x99ad:0x99b2])==bytes(codes[c] for c in 'Suite')
            assert bytes(p.memory[0x99a3:0x99a8])==bytes(codes[c] for c in 'Jouer')
        # Explicit renderer fixture: prepare the original portrait frame,
        # then invoke the unmodified menu drawing entry point with E38D.
        menu=next(e for e in entries if e['id']=='00E38D')
        for a in range(0x9a00,0x9b80):p.memory[a]=0x80
        for y in range(5):p.memory[0x9a89+y*32]=0x7e
        for a,v in [(0xd18e,0x8d),(0xd18f,0x63),(0xdfff,0),
                    (0xd0e3,0x89),(0xd0e4,0x9a),(0xd0e5,0x89),(0xd0e6,0x9a),(0xd01b,0)]:
            p.memory[a]=v
        finished=[]
        def done(_):
            assert p.register_file.HL==menu['target_address']+menu['target_length']
            finished.append(True)
        p.hook_register(0,0x399b,done,None);p.register_file.PC=0x3920
        for _ in range(150):
            p.tick(1)
            if finished:break
        assert finished
        assert [p.memory[0x9a89+y*32] for y in range(5)]==[0x7e]*5
        for y,text in enumerate(['Att.','Ruse','Fuir']):
            expected=bytes((core.CODES[c]+128)&255 for c in text)
            assert bytes(p.memory[0x9a8b+y*64:0x9a8b+y*64+len(text)])==expected
    finally:
        if p:p.stop(save=False)
        shutil.rmtree(folder)
    print('OK: Suite/Jouer cursor transitions and original arrow; combat-renderer border and labels.')

if __name__=='__main__':main()
