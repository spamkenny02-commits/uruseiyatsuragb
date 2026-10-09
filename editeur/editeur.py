"""Desktop editor for the supported Japanese ROM. All work stays local."""
import argparse, copy, json, queue, threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import ImageTk
import core

class Editor:
    def __init__(self, root, rom_path=None):
        self.root=root;self.entries=core.seed();self.data=core.project(self.entries)
        self.original=None;self.rom=None;self.compiled={};self.selected=None
        self.busy=False;self.dirty=False;self.revision=0;self.preview_revision=-1
        self.build_error=''
        self.messages=queue.Queue();self.loading=False;self.timer=None;self.page=0
        root.title('Miss Tomobiki — Atelier de traduction');root.geometry('1240x850')
        root.minsize(1020,720)
        style=ttk.Style();style.theme_use('clam')
        style.configure('TButton',padding=7);style.configure('TLabel',padding=3)
        bar=ttk.Frame(root,padding=8);bar.pack(fill='x')
        for label,command in [('Charger ROM japonaise',self.load_rom),('Ouvrir projet',self.load_project),
                              ('Sauver projet',self.save_project),('Importer TXT',self.import_txt),
                              ('Exporter textes',self.export_texts),('Créer ROM + IPS',self.export_rom)]:
            ttk.Button(bar,text=label,command=command).pack(side='left',padx=2)
        self.status=tk.StringVar(value='Charger la ROM japonaise pour extraire les 436 textes et activer les aperçus.')
        ttk.Label(root,textvariable=self.status,wraplength=1200).pack(fill='x',padx=10)
        pane=ttk.Panedwindow(root,orient='horizontal');pane.pack(fill='both',expand=True,padx=10,pady=8)
        left=ttk.Frame(pane,width=280);pane.add(left,weight=1)
        self.search=tk.StringVar();ttk.Entry(left,textvariable=self.search).pack(fill='x',pady=5)
        self.search.trace_add('write',lambda *_:self.populate())
        listframe=ttk.Frame(left);listframe.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(listframe,columns=('fr',),show='tree headings',selectmode='browse')
        self.tree.heading('#0',text='Adresse');self.tree.column('#0',width=78,stretch=False)
        self.tree.heading('fr',text='Français');self.tree.column('fr',width=205)
        scroll=ttk.Scrollbar(listframe,command=self.tree.yview);self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        self.tree.bind('<<TreeviewSelect>>',self.select)
        right=ttk.Frame(pane);pane.add(right,weight=3)
        self.title=tk.StringVar();ttk.Label(right,textvariable=self.title,font=('Segoe UI',12,'bold')).pack(anchor='w')
        body=ttk.Panedwindow(right,orient='horizontal');body.pack(fill='both',expand=True)
        edit=ttk.Frame(body);body.add(edit,weight=1)
        ttk.Label(edit,text='Japonais extrait (lecture seule)').pack(anchor='w')
        self.jp=tk.Text(edit,height=7,wrap='word',font=('Yu Gothic',11),background='#f1f3f5')
        self.jp.pack(fill='x');self.jp.configure(state='disabled')
        ttk.Label(edit,text='Français — les retours à la ligne correspondent à |').pack(anchor='w')
        self.fr=tk.Text(edit,height=9,wrap='word',font=('Consolas',12),undo=True)
        self.fr.pack(fill='both',expand=True);self.fr.bind('<<Modified>>',self.changed)
        self.aliasframe=ttk.LabelFrame(edit,text='Noms courts utilisés par le jeu',padding=8)
        self.aliases={}
        for key,label in [('nine','Commerce / combat : 9 caractères'),('seven','Inventaire / équipement : 7 caractères')]:
            ttk.Label(self.aliasframe,text=label).pack(anchor='w')
            var=tk.StringVar();ttk.Entry(self.aliasframe,textvariable=var).pack(fill='x')
            var.trace_add('write',lambda *_,k=key:self.alias_changed(k));self.aliases[key]=var
        ttk.Label(edit,text='| : saut de 2 rangées   [NL1] : 1 rangée\n[WAIT] : page suivante   <FB> : marge   <F2> : deux-points\nLes espaces des menus réservent les curseurs et les valeurs.',wraplength=450).pack(fill='x',pady=10)
        view=ttk.Frame(body,padding=8);body.add(view,weight=1)
        ttk.Label(view,text='Aperçu avec la police réellement réinsérée',font=('Segoe UI',10,'bold')).pack(anchor='w')
        self.context=tk.StringVar(value='Texte');self.contextbox=ttk.Combobox(view,textvariable=self.context,state='readonly')
        self.contextbox.pack(fill='x');self.contextbox.bind('<<ComboboxSelected>>',lambda _:self.render(reset=True))
        controls=ttk.Frame(view);controls.pack(fill='x')
        ttk.Button(controls,text='◀',command=lambda:self.turn(-1)).pack(side='left')
        self.page_label=tk.StringVar();ttk.Label(controls,textvariable=self.page_label).pack(side='left')
        ttk.Button(controls,text='▶',command=lambda:self.turn(1)).pack(side='left')
        self.grid=tk.BooleanVar(value=True);ttk.Checkbutton(controls,text='Grille',variable=self.grid,command=self.render).pack(side='left')
        self.picture=ttk.Label(view);self.picture.pack(anchor='nw',pady=5)
        self.note=tk.StringVar();ttk.Label(view,textvariable=self.note,wraplength=430).pack(fill='x')
        self.diagnostic=tk.StringVar(value='Les débordements empêchent la création de la ROM.')
        ttk.Label(view,textvariable=self.diagnostic,wraplength=430,foreground='#a13322').pack(fill='x',pady=8)
        ttk.Button(view,text='Recalculer / vérifier les 436 textes',command=self.build).pack(fill='x')
        ttk.Button(view,text='Sauver cet aperçu PNG',command=self.save_preview).pack(fill='x',pady=4)
        self.populate();self.tree.selection_set(self.entries[0]['id'])
        root.after(100,self.poll);root.protocol('WM_DELETE_WINDOW',self.close)
        if rom_path:root.after(200,lambda:self.load_rom(rom_path))

    def populate(self):
        wanted=self.search.get().casefold();current=self.selected
        self.tree.delete(*self.tree.get_children())
        for e in self.entries:
            ident=e['id'];text=self.data['texts'][ident]
            if wanted in (ident+' '+text+' '+e['jp']).casefold():
                self.tree.insert('', 'end',iid=ident,text=ident,values=(text[:65],))
        if current and self.tree.exists(current):self.tree.selection_set(current)

    def select(self,_=None):
        selection=self.tree.selection()
        if not selection:return
        ident=selection[0]
        if ident==self.selected:return
        self.selected=ident;self.loading=True
        e=next(e for e in self.entries if e['id']==ident)
        self.title.set(f"{ident} • banque source {e['source_bank']} • {e['length']} octets JP")
        self.jp.configure(state='normal');self.jp.delete('1.0','end');self.jp.insert('1.0',e['jp']);self.jp.configure(state='disabled')
        self.fr.delete('1.0','end');self.fr.insert('1.0',self.data['texts'][ident].replace('|','\n'));self.fr.edit_modified(False)
        for key,var in self.aliases.items():var.set(self.data[key].get(ident,''))
        self.aliasframe.pack_forget()
        if ident in self.data['nine']:self.aliasframe.pack(fill='x',pady=5)
        self.contextbox['values']=core.contexts(e);self.context.set(core.contexts(e)[0]);self.loading=False
        self.render(reset=True)

    def changed(self,_=None):
        if self.fr.edit_modified():
            if not self.loading and self.selected:
                self.data['texts'][self.selected]=self.fr.get('1.0','end-1c').replace('\n','|')
                self.mark_dirty()
            self.fr.edit_modified(False)

    def alias_changed(self,key):
        if not self.loading and self.selected in self.data[key]:
            self.data[key][self.selected]=self.aliases[key].get();self.mark_dirty()

    def mark_dirty(self):
        self.dirty=True;self.revision+=1
        self.diagnostic.set('Aperçu précédent : modification en attente de vérification.')
        if self.timer:self.root.after_cancel(self.timer)
        self.timer=self.root.after(700,self.build)
        if self.tree.exists(self.selected):self.tree.set(self.selected,'fr',self.data['texts'][self.selected][:65])

    def load_rom(self,path=None):
        if self.busy:return
        path=path or filedialog.askopenfilename(title='ROM japonaise originale',filetypes=[('ROM Game Boy','*.gb'),('Tous','*.*')])
        if not path:return
        try:
            source=Path(path).read_bytes();extracted=core.extract(source)
            for e in extracted:
                expected=next(x for x in self.entries if x['id']==e['id'])
                if e['raw']!=expected['raw']:raise ValueError('Extraction différente de la révision prise en charge.')
            self.original=source;self.status.set('436 textes extraits. Construction de l’aperçu…');self.build()
        except Exception as exc:messagebox.showerror('Chargement',str(exc))

    def build(self):
        self.timer=None
        if not self.original:return
        if self.busy:
            self.timer=self.root.after(500,self.build);return
        data=copy.deepcopy(self.data);revision=self.revision;source=self.original
        self.busy=True;self.status.set('Vérification / réinsertion des 436 textes…')
        def worker():
            try:self.messages.put(('ok',revision,core.compile_rom(source,data)))
            except Exception as exc:self.messages.put(('error',revision,str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def poll(self):
        try:
            while True:
                kind,revision,result=self.messages.get_nowait();self.busy=False
                if revision!=self.revision:
                    self.build();continue
                if kind=='error':
                    self.preview_revision=-1;self.build_error=result;self.diagnostic.set(result)
                    self.status.set('Correction requise. Le projet reste enregistrable ; la ROM n’est pas exportable.')
                else:
                    self.build_error=''
                    self.rom,entries=result;self.compiled={e['id']:e for e in entries};self.preview_revision=revision
                    used={b:max(e['target_address']+e['target_length'] for e in entries if e['target_bank']==b)-0x4000 for b in (16,17)}
                    # Include both compact-name pools in bank 17.
                    used[17]+=sum(len(v)+1 for k in ('nine','seven') for v in self.data[k].values())
                    self.status.set(f"436 textes vérifiés • banque 16 : {used[16]} / 9066 octets • banque 17 : {used[17]} / 12287 octets")
                    self.render()
        except queue.Empty:pass
        self.root.after(100,self.poll)

    def render(self,reset=False):
        if reset:self.page=0
        if not self.rom or self.selected not in self.compiled:return
        e=self.compiled[self.selected];context=self.context.get()
        total=1+core.payload(e,self.rom,context).count(0xf9);self.page=max(0,min(self.page,total-1))
        self.page_label.set(f'Page {self.page+1} / {total}')
        self.preview_image,warnings=core.preview(e,self.rom,context,self.page,scale=3,grid=self.grid.get())
        self.photo=ImageTk.PhotoImage(self.preview_image);self.picture.configure(image=self.photo)
        w,h,note=core.profile(e);self.note.set(note+'\nRendu du texte et du cadre ; les portraits et les valeurs dynamiques ne sont pas simulés.')
        self.diagnostic.set('\n'.join(warnings) if warnings else ('Aperçu vérifié — aucun débordement.' if self.preview_revision==self.revision else self.build_error or 'Aperçu précédent : les modifications ne sont pas encore validées.'))

    def turn(self,delta):self.page+=delta;self.render()

    def save_preview(self):
        if not hasattr(self,'preview_image'):return
        path=filedialog.asksaveasfilename(defaultextension='.png',initialfile=self.selected+'_apercu.png')
        if path:self.preview_image.save(path)

    def save_project(self):
        path=filedialog.asksaveasfilename(defaultextension='.json',initialfile='Tomobiki_mon_projet.json')
        if path:Path(path).write_text(json.dumps(self.data,ensure_ascii=False,indent=2),'utf8');self.dirty=False

    def load_project(self):
        if self.busy:return
        path=filedialog.askopenfilename(filetypes=[('Projet','*.json')])
        if not path:return
        if self.dirty and not messagebox.askyesno('Projet modifié','Remplacer les modifications non enregistrées ?'):return
        try:
            data=core.validate_project(json.loads(Path(path).read_text('utf-8-sig')))
            self.data=data;self.revision+=1;self.selected=None;self.search.set('');self.populate();self.tree.selection_set(self.tree.get_children()[0]);self.dirty=False;self.build()
        except Exception as exc:messagebox.showerror('Projet',str(exc))

    def import_txt(self):
        if self.busy:return
        path=filedialog.askopenfilename(filetypes=[('Traductions','*.txt')])
        if not path:return
        try:
            lines=Path(path).read_text('utf-8-sig').splitlines();values={}
            for line in lines:
                ident,text=line.split('=',1)
                if ident in values:raise ValueError('Identifiant répété : '+ident)
                values[ident]=text
            data=copy.deepcopy(self.data);data['texts']=values;core.validate_project(data)
            if self.dirty and not messagebox.askyesno('Textes modifiés','Remplacer les textes non enregistrés ?'):return
            self.data=data;self.revision+=1;self.dirty=True;self.selected=None;self.search.set('');self.populate();self.tree.selection_set(self.tree.get_children()[0]);self.build()
        except Exception as exc:messagebox.showerror('Import TXT',str(exc))

    def export_texts(self):
        path=filedialog.askdirectory(title='Dossier des textes extraits et traduits')
        if not path:return
        target=Path(path)
        files={'traductions.txt':'\n'.join(k+'='+v for k,v in self.data['texts'].items()),
               'extraction_japonaise.json':json.dumps([{k:v for k,v in e.items() if k in ('id','offset','jp','raw','source_bank','references')} for e in self.entries],ensure_ascii=False,indent=2),
               'noms_courts.json':json.dumps({k:self.data[k] for k in ('nine','seven')},ensure_ascii=False,indent=2)}
        if any((target/name).exists() for name in files) and not messagebox.askyesno('Export','Remplacer les fichiers de textes existants dans ce dossier ?'):return
        for name,content in files.items():(target/name).write_text(content,'utf8')
        self.status.set('Textes japonais, traductions TXT et noms courts exportés.')

    def export_rom(self):
        if self.busy or not self.rom or self.preview_revision!=self.revision:
            messagebox.showinfo('Création de ROM','Charger la ROM originale et attendre une vérification sans erreur.');return
        path=filedialog.asksaveasfilename(defaultextension='.gb',initialfile='Miss_Tomobiki_personnalise.gb')
        if not path:return
        target=Path(path);patch=target.with_suffix('.ips')
        if target.exists() and target.read_bytes()==self.original:
            messagebox.showerror('ROM originale','Choisir un nouveau fichier pour préserver la ROM originale.');return
        if patch.exists() and not messagebox.askyesno('Patch','Remplacer le patch IPS existant ?'):return
        target.write_bytes(self.rom);patch.write_bytes(core.ips(self.original,self.rom))
        self.status.set('ROM de 512 Ko et patch IPS créés. Tester les textes modifiés dans un émulateur.')

    def close(self):
        if self.dirty and not messagebox.askyesno('Projet modifié','Fermer sans enregistrer les modifications ?'):return
        self.root.destroy()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--rom',type=Path);args=parser.parse_args()
    root=tk.Tk();Editor(root,args.rom);root.mainloop()
