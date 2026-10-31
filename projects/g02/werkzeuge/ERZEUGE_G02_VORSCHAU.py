# -*- coding: utf-8 -*-
"""Offline CAD preview from existing house polygons and exact source grid nodes.
It is not a NX rendering or a physical survey. Bilinear cells are triangulated
for browser display only; the NX import retains the original surfaces.
"""
import json,re,sys
from pathlib import Path
B=Path(__file__).absolute().parents[1];sys.path.insert(0,str(B))
from g02.height import height_plan
from gesamt.core import read_json,write_json
s=(B/'haus/VORSCHAU_HAUS.html').read_text(encoding='utf-8')
start=s.index('const meshes=')+len('const meshes=')
meshes,length=json.JSONDecoder().raw_decode(s[start:])
old_end=start+length
plan=height_plan(B,read_json(B/'data/EINSTELLUNGEN_GESAMT.json'));dz=plan['translation_mm'][2]
job=read_json(B/'umgebung/data/IMPORTAUFTRAG_R09.json')
selection=['DGM','V01','V02','V03','V05']
for spec in job['parts']:
    if spec['id'] not in selection:continue
    faces=[]
    for row in spec['geometry_reference']['sheets']:
        nu,nv=row['grid_shape'];nodes=[[p[0],p[1],p[2]+dz] for p in row['samples_mm'][:nu*nv]]
        for i in range(nu-1):
            for j in range(nv-1):
                a,b,c,d=[nodes[idx] for idx in [i*nv+j,(i+1)*nv+j,(i+1)*nv+j+1,i*nv+j+1]]
                faces.extend([[a,b,c],[a,c,d]])
    meshes.append({'id':spec['id']+'_QUELLFLAECHEN','part':spec['id'],
        'kind':'GELAENDE' if spec['id']=='DGM' else 'VEGETATION','parent':spec['id'],
        'collision':False,'faces':faces,'sources':[{'document':spec['id'],'page':1,
            'location':str(spec['source'])}],
        'quantity_excluded':True,'material':'Quellenoberfläche, kein Boden-/Pflanzenvolumen',
        'note':'Vorläufige PLANANNAHME. Einheitlicher Z-Versatz '+format(dz,'.9f')+' mm; '
               'Anker (0, -500 mm) auf -300 mm relativ EG. Nicht vermessen; Vorschauzellen trianguliert.'})
s=s[:start]+json.dumps(meshes,ensure_ascii=False,separators=(',',':'))+s[old_end:]
ns=s.index('const names=')+len('const names=');names,nl=json.JSONDecoder().raw_decode(s[ns:])
names.update(DGM='Gelände · gemeinsamer Planbezug',V01='Stellplatzhecke V01',V02='Stellplatzhecke V02',
             V03='Gehölzbereich V03',V05='Strauchbereich V05')
s=s[:ns]+json.dumps(names,ensure_ascii=False)+s[ns+nl:]
s=re.sub(r'<header>.*?</header>', '<header><div class="flag">G02 · INTEGRIERTE HÖHENMONTAGE · KEIN NX-SCREENSHOT</div>'
 '<h1>Haus und Umgebung auf gemeinsamem Planbezug</h1>'
 '<p>Haus MAIN01-A01 · Gelände und vier Vegetationsgruppen · Höhenanschluss vorläufig, nicht vermessen</p></header>',s,flags=re.S)
s=s.replace('<title>Haus MAIN01-A01 | Dachprüfung</title>','<title>G02 – Haus, Gelände und Vegetation</title>')
s=re.sub(r'<div class="notice">.*?</div>', '<div class="notice"><strong>Gemeinsame Arbeitsmontage – keine Bestandsvermessung.</strong><br><br>'
 'Umgebung gemeinsam um <strong>31.362,499 mm nach unten</strong> versetzt. Haus unverändert bei EG ±0,00.<br><br>'
 'Der Anker (0 / −500 mm) liegt dadurch auf −0,300 m. Die Übertragung dieser historischen Außenkote auf den gewählten Punkt '
 'ist nicht aufgemessen. Geländeform und Pflanzenhöhen bleiben relativ zueinander erhalten.<br><br>'
 'Flächen laufen unter dem Haus weiter; Keller zur Ansicht über den Gelände-Schalter freilegen. '
 'Bilineare Rasterzellen sind nur für diese Vorschau trianguliert.<br><br>'
 'Statik, reale Anschlussdetails, Leitungstiefen und bekannte Hauskonflikte bleiben offen.</div>',s,count=1,flags=re.S)
s=s.replace('PRUEFBERICHT_DACH_A01.html','PRUEFBERICHT_G02.html')
s=s.replace('1418 Körper · Nur Haus','1418 Hauskörper · Umgebung als Flächenreferenz')
s=s.replace('`${count} Körper sichtbar · MAIN01-A01 · offene Konstruktionen, keine Bestandsfreigabe`',
 '`G02 · ${count} sichtbare Modellbereiche · Planbezug, keine Bestandsvermessung`')
s=s.replace("k==='GRUNDSTUECK'||k.endsWith('_PLAN')||k.includes('KG')", "k==='DGM'||k.startsWith('V0')||k==='GRUNDSTUECK'||k.endsWith('_PLAN')||k.includes('KG')")
s=s.replace('<button id="all">Alles</button>', '<button id="all">Gesamtausschnitt</button><button id="site">Haus + Gelände</button>')
s=s.replace("function shade(face,kind){", "function shade(face,kind){")
s=s.replace("return `rgb(${g},${g},${g})`", "return kind==='GELAENDE'?`rgb(${Math.round(g*.91)},${Math.round(g*.95)},${Math.round(g*.86)})`:kind==='VEGETATION'?`rgb(${Math.round(g*.62)},${Math.round(g*.77)},${Math.round(g*.60)})`:`rgb(${g},${g},${g})`")
s=s.replace("ctx.lineWidth=.38;ctx.stroke();", "ctx.lineWidth=.38;if(!['GELAENDE','VEGETATION'].includes(f.m.kind))ctx.stroke();")
s=s.replace("window.addEventListener('resize',resize);resize();fitVisible();", "document.getElementById('site').onclick=()=>{Object.keys(shown).forEach(k=>shown[k]=!k.includes('KG'));center=[10000,13500,1700];extent=62000;zoom=1;pan=[0,0];az=-2.2;el=.6;sync()};window.addEventListener('resize',resize);resize();document.getElementById('site').onclick();")
s=s.replace('Geometrie aus haus.json und demselben Bauauftrag wie das NX-Skript.',
 'Hausgeometrie aus MAIN01-A01; Umgebung aus den Importreferenzknoten. Der Höhenversatz wird aus derselben G02-Einstellung berechnet.')
(B/'VORSCHAU_GESAMT_G02.html').write_text(s,encoding='utf-8')
write_json(B/'berichte/HOEHENANSATZ_G02.json',plan)
print('Preview model polygons written',len(meshes),'regions; environment dz',dz)
