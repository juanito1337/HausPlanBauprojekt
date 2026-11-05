"""Render one measured K02 plan sheet; no NX and no geometry regeneration.

Usage: python tools/render_m01_lageplan.py [--plan reports/local/m02/PLAN.json]
Requires Pillow. The input is the freshly calculated complete K02 plan.
Projection polygons are filled as a raster union, without internal TIN edges.
The optional local CLEARANCES.json supplies the separately checked distances.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
from PIL.PngImagePlugin import PngInfo


ROOT = Path(__file__).resolve().parents[1]
COL = {'paper': '#ffffff', 'ink': '#182c3b', 'muted': '#4c6270',
       'grid': '#e5ebee', 'parcel': '#698276', 'land': '#f4f8f2',
       'house': '#dfe5e9', 'house_edge': '#748590', 'cellar': '#1f5e83',
       'exc': '#f5aa5c', 'exc_edge': '#a84d18',
       'pile': '#edcc74', 'pile_edge': '#866019', 'reserve': '#8559a2', 'hedge': '#2b7260'}
FONTDIR = Path('C:/Windows/Fonts')


def font(size, bold=False):
    win = FONTDIR/('arialbd.ttf' if bold else 'arial.ttf')
    return ImageFont.truetype(str(win) if win.exists() else ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'), size)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=ROOT/'reports/local/m02/PLAN.json')
    parser.add_argument('--out', type=Path, default=ROOT/'docs/entwicklungsstand/M01-2-PS01-F01-Lageplan.png')
    parser.add_argument('--clearances', type=Path, default=ROOT/'reports/local/m02/CLEARANCES.json')
    args = parser.parse_args()
    raw = args.plan.read_bytes()
    plan = json.loads(raw)
    assert plan['units'] == 'mm' and plan['construction_release'] is False
    for source in plan['provenance']['inputs']:
        assert hashlib.sha256((ROOT/source['path']).read_bytes()).hexdigest() == source['sha256'], source['path']
    field = next(f for f in plan['fields'] if f['id'] == 'PS01-F01')
    assert field['native_candidate'] and field['stockpile']['center_mm'] == [13000, -16000]
    catalog = json.loads((ROOT/'renovierung/planung/2026-11-01/sektionen.json').read_text(encoding='utf-8'))
    house = json.loads((ROOT/'projects/g02/haus/data/haus.json').read_text(encoding='utf-8'))
    compact = json.loads((ROOT/'renovierung/planung/2026-11-01/K02_MENGEN.json').read_text(encoding='utf-8'))
    quantities = next(f for f in compact['fields'] if f['id'] == field['id'])
    assert abs(quantities['volume_m3']-field['volume_m3']) < 1e-9
    boundary = house['site']['boundary']['points_local_mm']
    footprint = catalog['footprints']
    areas = {}
    for key in ('main','reserve_1_25'):
        areas[key] = sum(abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,poly[1:]+poly[:1])))/2
                        for poly in field['stockpile'][key]['projection_polygons'])/1e6
    distances = None
    if args.clearances.exists():
        measured = json.loads(args.clearances.read_text(encoding='utf-8'))
        assert measured['config'] == plan['provenance']['config']
        assert measured['source_inputs'] == plan['provenance']['inputs']
        distances = next(row for row in measured['rows'] if row['field']==field['id'])
        assert abs(distances['bank_m3']-field['volume_m3'])<1e-9

    W,H = 3000,2300
    image = Image.new('RGB',(W,H),COL['paper'])
    draw = ImageDraw.Draw(image)
    def txt(x,y,text,size=32,color='ink',bold=False,anchor=None):
        draw.text((x,y),text,font=font(size,bold),fill=COL.get(color,color),anchor=anchor)
    def line(points,color,width=3):
        draw.line(points,fill=COL.get(color,color),width=width)
    def number(value):return f'{value:.3f}'.replace('.',',')
    def wrap(x,y,text,width,size=30,color='muted',bold=False,leading=1.4):
        yy=y
        for paragraph in text.split('\n'):
            current=''
            for word in paragraph.split():
                proposal=(current+' '+word).strip()
                if draw.textlength(proposal,font=font(size,bold))>width and current:
                    txt(x,yy,current,size,color,bold);yy+=round(size*leading);current=word
                else:current=proposal
            if current:txt(x,yy,current,size,color,bold);yy+=round(size*leading)
        return yy

    txt(100,67,'WO BLEIBT DER SAND?',66,bold=True)
    txt(102,158,'PS01-F01  |  Aushub und Lagerflächen auf dem Grundstück',38)
    txt(103,221,'Berechnete Draufsicht aus K02-Geometrie  ·  Einzelfeldstudie  ·  Stand 04.11.2026',29,'muted')
    line([(100,290),(2900,290)],'grid',3)

    # A single scale on both map axes preserves all model geometry.
    box=(200,395,1660,2075)
    xmin,xmax=-12000,34000;ymin,ymax=-31000,29000
    scale=min((box[2]-box[0])/(xmax-xmin),(box[3]-box[1])/(ymax-ymin))
    xoff=box[0]+((box[2]-box[0])-scale*(xmax-xmin))/2
    yoff=box[1]+((box[3]-box[1])-scale*(ymax-ymin))/2
    def xy(p):return xoff+(p[0]-xmin)*scale,yoff+(ymax-p[1])*scale
    def poly(points,fill=None,outline=None,width=3):
        coords=[xy(p) for p in points]
        if fill:draw.polygon(coords,fill=COL.get(fill,fill))
        if outline:line(coords+[coords[0]],outline,width)
    txt(200,332,'LAGEPLAN  ·  gleiche Skalierung in X und Y',29,bold=True)
    poly(boundary,'land')
    for x in range(-10000,35000,5000):
        a=xy((x,ymin));b=xy((x,ymax));line([a,b],'grid',2)
        txt(a[0],box[3]+20,str(x//1000),25,'muted',anchor='mt')
    for y in range(-30000,30000,5000):
        a=xy((xmin,y));b=xy((xmax,y));line([a,b],'grid',2)
        txt(box[0]-18,a[1],str(y//1000),25,'muted',anchor='rm')
    poly(boundary,outline='parcel',width=5)
    for name in ('EG','GARAGE'):
        poly(footprint[name],'house','house_edge',3)
    for name in ('KG','ANBAU_KG'):
        poly(footprint[name],None,'cellar',5)

    def union_mask(polygons):
        mask=Image.new('L',(W,H),0);md=ImageDraw.Draw(mask)
        for p in polygons:md.polygon([xy(point) for point in p],fill=255)
        return mask
    def paint_union(polygons,fill,edge,dashed=False):
        mask=union_mask(polygons)
        if fill:image.paste(COL[fill],(0,0,W,H),mask)
        rim=ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(5)),mask.filter(ImageFilter.MinFilter(5)))
        if dashed:
            # Clip diagonal dash bands to the true raster perimeter; no convex hull.
            stripes=Image.new('L',(W,H),0);sd=ImageDraw.Draw(stripes)
            for k in range(-H,W,34):sd.line([(k,0),(k+H,H)],fill=255,width=17)
            rim=ImageChops.multiply(rim,stripes)
        image.paste(COL[edge],(0,0,W,H),rim)
    paint_union(field['projection_polygons'],'exc','exc_edge')
    paint_union(field['stockpile']['main']['projection_polygons'],'pile','pile_edge')
    paint_union(field['stockpile']['reserve_1_25']['projection_polygons'],None,'reserve',True)
    # Native G02 import references: mapped canopy sheets, not trunks or roots.
    job = json.loads((ROOT/'projects/g02/umgebung/data/IMPORTAUFTRAG_R09.json').read_text(encoding='utf-8-sig'))
    for row in job['parts']:
        if row['id'] not in ('V01','V02'): continue
        step = ROOT/'projects/g02/umgebung'/row['step_file']
        assert hashlib.sha256(step.read_bytes()).hexdigest() == row['geometry_reference']['source_sha256']
        for sheet in row['geometry_reference']['sheets']:
            nr,nc = sheet['grid_shape']; pts = sheet['samples_mm'][:nr*nc]
            poly([pts[0][:2],pts[nc-1][:2],pts[-1][:2],pts[-nc][:2]],'hedge')
    draw=ImageDraw.Draw(image)
    # The actual bottom line is a separate, measured register dimension.
    a=field['origin_mm'];b=[a[k]+field['length_mm']*field['tangent'][k] for k in range(2)]
    line([xy(a),xy(b)],'exc_edge',8)

    def plot_label(label,location,target,color):
        px,py=xy(location);qx,qy=xy(target)
        line([(px,py+37),(qx,qy)],color,3)
        draw.ellipse((qx-6,qy-6,qx+6,qy+6),fill=COL[color])
        bbox=draw.textbbox((px,py),label,font=font(29,True))
        draw.rounded_rectangle((bbox[0]-8,bbox[1]-5,bbox[2]+8,bbox[3]+5),radius=5,fill='white')
        txt(px,py,label,29,color,True)
    plot_label('1  Grube PS01-F01',(-7000,-6500),(1500,-1800),'exc_edge')
    plot_label('2  Sandlager',(15700,-21500),(14600,-17700),'pile_edge')
    # Centred labels name known footprints, never inferred room or foundation data.
    px,py=xy((7000,4600));txt(px,py,'Hauptbau',30,'ink',True,anchor='mm')
    px,py=xy((20500,12000));txt(px,py,'Anbau',29,'ink',True,anchor='mm')
    px,py=xy((-2300,15400));txt(px,py,'Garage',26,'ink',True,anchor='mm')
    px,py=xy((13000,-16000));draw.line([(px-9,py),(px+9,py)],fill=COL['pile_edge'],width=3)
    draw.line([(px,py-9),(px,py+9)],fill=COL['pile_edge'],width=3)
    txt(950,2160,'Modell-X [m]',28,'muted',anchor='mm')
    txt(105,1130,'Y [m]',28,'muted',True,anchor='mm')
    # Scale bar stays meaningful if the PNG is displayed at a different size.
    sx,sy=xy((-7000,-29500));length=10000*scale
    for i in range(2):
        draw.rectangle((sx+i*length/2,sy,sx+(i+1)*length/2,sy+12),fill=COL['ink'] if i==0 else 'white',outline=COL['ink'],width=2)
    for i,label in ((0,'0'),(1,'5'),(2,'10 m')):txt(sx+i*length/2,sy+23,label,24,'muted',anchor='mt')

    # A readable information column, outside the geometrically scaled map.
    x=1840;right=2875;cw=right-x
    txt(x,341,'1  EIN FELD IST GEÖFFNET',32,bold=True)
    y=409
    for label,value,unit,color in (
        ('Aushub, gewachsener Ansatz',field['volume_m3'],'m³','exc_edge'),
        ('Hauptlager, locker × 1,05',field['stockpile']['main']['volume_mm3']/1e9,'m³','pile_edge'),
        ('Reserve, alternativ × 1,25',field['stockpile']['reserve_1_25']['volume_mm3']/1e9,'m³','reserve')):
        txt(x,y,label,30,'muted');txt(x,y+48,number(value)+' '+unit,55,color,True);y+=142
    y=wrap(x,y+5,'Haupt- und Reservelager sind Alternativen am selben Platz. Die Reserve ist kein zweiter Haufen.',cw,30,'reserve',True)
    line([(x,y+19),(right,y+19)],'grid',3);y+=52
    txt(x,y,'2  BISHERIGER LAGERPLATZ · KONFLIKT',32,bold=True);y+=65
    y=wrap(x,y,'Zentrum: X = 13,000 m / Y = −16,000 m',cw,30)
    y=wrap(x,y+10,'Kontaktfläche Hauptlager: '+number(areas['main'])+' m²\nReserve: '+number(areas['reserve_1_25'])+' m²',cw,30)
    distance_note=('Geometrischer Mindestabstand der Grube zum Hauptlager: '+number(distances['excavation_to_pile_main_m'])+' m; zur Reserve: '+number(distances['excavation_to_pile_reserve_m'])+' m.') if distances else 'Abstände: siehe gesonderten Machbarkeitsbericht.'
    y=wrap(x,y+16,distance_note,cw,30)
    y=wrap(x,y+16,'Die grün eingezeichneten Heckenflächen überschneiden sich mit dem bisherigen Lager. Der Platz ist nicht als frei bestätigt.',cw,29,'hedge',True)
    line([(x,y+20),(right,y+20)],'grid',3);y+=53
    txt(x,y,'DARSTELLUNG',32,bold=True);y+=57
    legend=[('parcel','Grundstück · Kartenreferenz'),('house_edge','Haus / EG-Bestandsumriss'),('cellar','Kellerkonturen aus Modell'),('exc_edge','Grubenprojektion / Oberkante'),('pile_edge','Hauptlager · 21,268 m³'),('reserve','Reserve · gestrichelt, alternativ')]
    for color,label in legend:
        if color=='reserve':
            for xx in range(x,x+83,23):line([(xx,y+16),(min(xx+13,x+83),y+16)],color,5)
        else:line([(x,y+16),(x+83,y+16)],color,5)
        txt(x+110,y,label,29);y+=54
    y=wrap(x,y+21,'Sohle: '+number(field['length_mm']/1000)+' m × '+number(field['width_mm']/1000)+' m; Prüfziel Z = '+number(field['formation_z_mm']/1000)+' m. Seiten- und Endböschung 1:1.',cw,28)
    y=wrap(x,y+11,'Die Ausdehnung oben ist größer als die Feldsohle. Gezeigt sind echte Projektionspolygone, keine schematischen Rechtecke.',cw,28)
    # Strong study note separated from the map and quantities.
    note_y=2085
    draw.rounded_rectangle((1815,note_y,2900,2228),radius=12,fill='#f1f4f6')
    wrap(1840,note_y+18,'STUDIE – KEINE GRABFREIGABE\nGründung, Leitungen, Lagerlasten und Zugänge ungeprüft.',1030,26,'ink',True,1.35)
    txt(100,2248,'Quelle: frischer K02-Plan PS01-F01 · Modellmaße, keine Grenzvermessung · Keine NX-Bildschirmaufnahme',25,'muted')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    metadata=PngInfo()
    metadata.add_text('Title','PS01-F01 – Aushub und alternative Sandlager')
    metadata.add_text('Description','Berechneter maßstäblicher Lageplan; keine NX-Bildschirmaufnahme und keine Bauausführungsfreigabe.')
    metadata.add_text('K02_PLAN_SHA256',hashlib.sha256(raw).hexdigest())
    metadata.add_text('GENERATOR_SHA256',hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    image.save(args.out,dpi=(200,200),optimize=True,pnginfo=metadata)
    print(json.dumps({'output':str(args.out),'pixels':[W,H],
                      'plan_sha256':hashlib.sha256(raw).hexdigest(),
                      'scale_pixels_per_m':scale*1000,
                      'bank_m3':field['volume_m3'],'legend_end_y':y},ensure_ascii=False))


if __name__=='__main__':main()
