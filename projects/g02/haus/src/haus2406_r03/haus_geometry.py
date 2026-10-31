# -*- coding: utf-8 -*-
"""Reine Geometrie und sichere Datenauswertung; keine NX- oder Fremdmodule.

Koordinaten in mm. Alle Polygonfunktionen arbeiten mit konvexen Teilflaechen.
XY-Koordinaten werden beim Neuaufbau berechnet. Z-Expressions werden in NX
an Extrusionsgrenzen gebunden. Keine behauptete globale CAD-Assoziativitaet.
"""
import ast
import math
import re

EPS = 1.0e-7
STATUSES = {'PLANWERT', 'ABGELEITET', 'GESCHAETZT', 'UNGEKLAERT'}


def area(poly):
    return 0.5 * sum(p[0]*q[1]-q[0]*p[1]
                     for p,q in zip(poly, poly[1:]+poly[:1]))


def clean(poly, eps=EPS):
    result=[]
    for p in poly:
        p=[float(p[0]),float(p[1])]
        if not result or math.dist(p,result[-1])>eps:
            result.append(p)
    if len(result)>1 and math.dist(result[0],result[-1])<eps:
        result.pop()
    if len(result)<3 or abs(area(result))<eps:
        return []
    return result if area(result)>0 else result[::-1]


def cross(a,b,p):
    return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])


def halfplane(poly,a,b,inside=True):
    """Sutherland-Hodgman; linke Seite von a->b ist innen."""
    if not poly:
        return []
    out=[]
    sign=1.0 if inside else -1.0
    for p,q in zip(poly,poly[1:]+poly[:1]):
        dp=sign*cross(a,b,p); dq=sign*cross(a,b,q)
        ip=dp>=-EPS; iq=dq>=-EPS
        if ip:
            out.append(p)
        if ip != iq:
            f=dp/(dp-dq)
            out.append([p[0]+f*(q[0]-p[0]),p[1]+f*(q[1]-p[1])])
    return clean(out)


def convex_intersection(subject,clip):
    out=clean(subject)
    c=clean(clip)
    if not out or not c:return []
    for a,b in zip(c,c[1:]+c[:1]):
        out=halfplane(out,a,b)
        if not out:
            break
    return out


def convex_difference(subject,clip):
    """Zerlegt subject minus clip in disjunkte konvexe Polygone."""
    s=clean(subject); c=clean(clip)
    if not s:
        return []
    if not convex_intersection(s,c):
        return [s]
    remainder=s; result=[]
    for a,b in zip(c,c[1:]+c[:1]):
        outside=halfplane(remainder,a,b,False)
        if outside and abs(area(outside))>0.1:
            result.append(outside)
        remainder=halfplane(remainder,a,b,True)
        if not remainder:
            break
    return result


def convex(poly):
    p=clean(poly)
    return bool(p) and all(cross(p[i],p[(i+1)%len(p)],p[(i+2)%len(p)])>=-EPS
                           for i in range(len(p)))


def triangulate(poly):
    """Ear clipping fuer einfache Polygone ohne Loecher."""
    p=clean(poly)
    if len(p)<3:
        raise ValueError('Degeneriertes Polygon')
    result=[]; limit=len(p)*len(p)+1
    while len(p)>3:
        found=False
        for i in range(len(p)):
            a,b,c=p[i-1],p[i],p[(i+1)%len(p)]
            if cross(a,b,c)<=EPS:
                continue
            tri=[a,b,c]
            def within(q):
                return all(cross(x,y,q)>=-EPS for x,y in zip(tri,tri[1:]+tri[:1]))
            others=[q for j,q in enumerate(p) if j not in {(i-1)%len(p),i,(i+1)%len(p)}]
            if any(within(q) for q in others):
                continue
            result.append(tri);p.pop(i);found=True;break
        limit-=1
        if not found or limit<=0:
            raise ValueError('Kontur nicht einfach / Triangulierung fehlgeschlagen')
    result.append(p)
    return result


def pieces(poly):
    return [clean(poly)] if convex(poly) else triangulate(poly)


def remove_overlaps(polygons,previous):
    out=[]
    for p in polygons:
        fragments=pieces(p)
        for cutter in previous:
            fragments=[f for piece in fragments for f in convex_difference(piece,cutter)]
            if not fragments:
                break
        out.extend(fragments)
    return out


def rectangle(a,b,t,left=0.5):
    dx=b[0]-a[0];dy=b[1]-a[1];ln=math.hypot(dx,dy)
    if ln<EPS or t<=0:
        raise ValueError('Ungueltige Wandachse oder Wanddicke')
    nx=-dy/ln;ny=dx/ln
    return clean([[a[0]-nx*t*(1-left),a[1]-ny*t*(1-left)],
                  [b[0]-nx*t*(1-left),b[1]-ny*t*(1-left)],
                  [b[0]+nx*t*left,b[1]+ny*t*left],
                  [a[0]+nx*t*left,a[1]+ny*t*left]])


def transformed(p,origin=(0,0),angle=0.0):
    r=math.radians(angle);c=math.cos(r);s=math.sin(r)
    return [origin[0]+p[0]*c-p[1]*s,origin[1]+p[0]*s+p[1]*c]


def affine_source(point,anchors):
    """Affine Abbildung aus drei im Planregister dokumentierten Bildankern."""
    o,x,y=anchors['pixels']; ox,oy=o
    a=x[0]-ox;b=y[0]-ox;c=x[1]-oy;d=y[1]-oy
    det=a*d-b*c
    if abs(det)<EPS:
        raise ValueError('Singulaere Scan-Kalibrierung')
    px=point[0]-ox;py=point[1]-oy
    return [(d*px-b*py)/det*anchors['dimensions_mm'][0],
            (-c*px+a*py)/det*anchors['dimensions_mm'][1]]


class Parameters:
    """Arithmetik ohne eval, Imports, Funktionen oder Attributzugriff."""
    def __init__(self,items):
        self.items=items;self.cache={};self.stack=[]

    def value(self,name):
        if name in self.cache:
            return self.cache[name]
        if name not in self.items:
            raise ValueError('Unbekannter Parameter: '+name)
        if name in self.stack:
            raise ValueError('Zyklische Parameter: '+' -> '.join(self.stack+[name]))
        self.stack.append(name)
        try:
            item=self.items[name]
            expr=item.get('formula')
            value=self.number(expr) if expr is not None else item.get('value')
            if value is None:
                raise ValueError('Ungeklaerter Parameter: '+name)
            value=float(value)
            if not math.isfinite(value):
                raise ValueError('Nicht endlicher Parameter: '+name)
            self.cache[name]=value
            return value
        finally:
            self.stack.pop()

    def number(self,expression):
        if isinstance(expression,(int,float)):
            if not math.isfinite(float(expression)):
                raise ValueError('Nicht endlicher Wert')
            return float(expression)
        tree=ast.parse(str(expression),mode='eval')
        def visit(n):
            if isinstance(n,ast.Expression):return visit(n.body)
            if isinstance(n,ast.Constant) and type(n.value) in (int,float):return float(n.value)
            if isinstance(n,ast.Name):return self.value(n.id)
            if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):
                return visit(n.operand)*(1 if isinstance(n.op,ast.UAdd) else -1)
            if isinstance(n,ast.BinOp) and isinstance(n.op,(ast.Add,ast.Sub,ast.Mult,ast.Div)):
                x=visit(n.left);y=visit(n.right)
                if isinstance(n.op,ast.Add):return x+y
                if isinstance(n.op,ast.Sub):return x-y
                if isinstance(n.op,ast.Mult):return x*y
                return x/y
            raise ValueError('Nicht zugelassener Ausdruck: '+str(expression))
        val=visit(tree)
        if not math.isfinite(val):raise ValueError('Nicht endlicher Ausdruck')
        return val

    def dependencies(self,expr):
        if expr is None:return set()
        try:tree=ast.parse(str(expr),mode='eval')
        except SyntaxError:return set()
        return {n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}

    def uncertain(self,expr,seen=None):
        seen=set() if seen is None else set(seen)
        result=set()
        for name in self.dependencies(expr):
            if name in seen:continue
            seen.add(name)
            item=self.items[name]
            if item['status'] in ('GESCHAETZT','UNGEKLAERT') or item.get('conflict'):
                result.add(name)
            if item.get('formula') is not None:
                result.update(self.uncertain(item['formula'],seen))
        return result


def wall_polygon(w,params):
    if 'polygon' in w:
        return clean(w['polygon'])
    t=params.number(w['thickness'])
    return rectangle(w['a'],w['b'],t,w.get('material_left_fraction',0.5))


def opening_polygon(w,o,params,extra=2.0):
    a=w['a'];b=w['b'];dx=b[0]-a[0];dy=b[1]-a[1];ln=math.hypot(dx,dy)
    f=params.number(o['offset']);width=params.number(o['width'])
    p=[a[0]+dx*f/ln,a[1]+dy*f/ln]
    q=[a[0]+dx*(f+width)/ln,a[1]+dy*(f+width)/ln]
    t=params.number(w['thickness'])+2*extra
    return rectangle(p,q,t,w.get('material_left_fraction',0.5))


def enabled(obj,params,allow_estimates=False):
    if obj.get('enabled',True) is False:return False,'NICHT_ENTHALTEN'
    if obj.get('status')=='UNGEKLAERT':return False,'DATEN_FEHLEN'
    dependencies=set()
    for key in ('bottom','top','thickness','offset','width','sill','height','height_reference','ridge_height'):
        if key in obj:dependencies.update(params.uncertain(obj[key]))
    if not allow_estimates and (obj.get('status')=='GESCHAETZT' or obj.get('conflicts') or dependencies):
        return False,'NAEHERUNG_GESPERRT'+(':'+','.join(sorted(dependencies)) if dependencies else '')
    return True,'OK'


def validate(data):
    errors=[];warnings=[];ids=set();p=Parameters(data['parameters'])
    if data.get('units')!='mm':errors.append('Nur mm sind zulaessig')
    if data.get('schema_version')!=1:errors.append('Unbekannte Schema-Version')
    for name,item in data['parameters'].items():
        if not re.match(r'^[A-Za-z][A-Za-z0-9_]*$',name):errors.append('Parametername '+name)
        if item.get('status') not in STATUSES:errors.append('Parameterstatus '+name)
        if item.get('value') is None and item.get('formula') is None:
            warnings.append('Parameter offen: '+name);continue
        try:p.value(name)
        except (ValueError,ZeroDivisionError) as ex:errors.append(str(ex))
    documents=data.get('source_document_pages',{})
    def source_check(obj):
        for src in obj.get('sources',[]):
            doc=src.get('document');page=src.get('page')
            if documents and (doc not in documents or not isinstance(page,int) or not 1<=page<=documents.get(doc,0)):
                errors.append('Ungueltige Planreferenz: '+str(doc)+' S.'+str(page))
    for item in data['parameters'].values():source_check(item)
    filenames=set();part_ids=set()
    for group in data['parts']:
        filename=group.get('file','')
        if group.get('id') in part_ids:errors.append('Teil-ID doppelt: '+str(group.get('id')))
        part_ids.add(group.get('id'))
        if not re.match(r'^[A-Za-z0-9_\-]+\.prt$',filename):errors.append('Unsicherer Dateiname: '+filename)
        if filename.lower() in filenames:errors.append('Dateiname doppelt: '+filename)
        filenames.add(filename.lower())
        for kind in ('walls','slabs','prisms','references'):
            for obj in group.get(kind,[]):
                ident=obj['id']
                source_check(obj)
                if ident in ids:errors.append('ID doppelt: '+ident)
                ids.add(ident)
                if obj.get('status') not in STATUSES:errors.append('Status '+ident)
                if not obj.get('sources'):errors.append('Quelle fehlt: '+ident)
                try:
                    if kind=='walls':
                        poly=wall_polygon(obj,p)
                        if not all(math.isfinite(float(x)) for q in (obj['a'],obj['b']) for x in q):errors.append('Nicht endliche Wandkoordinaten: '+ident)
                        if p.number(obj['thickness'])<=0:errors.append('Wanddicke: '+ident)
                        if not 0<=obj.get('material_left_fraction',.5)<=1:errors.append('Materialseite: '+ident)
                        if math.dist(obj['a'],obj['b'])<1:errors.append('Kurze Wand: '+ident)
                    elif kind=='slabs':poly=clean(obj['polygon'])
                    else:poly=None
                    if poly is not None:
                        if not poly:errors.append('Polygon leer: '+ident)
                        else:
                            if not all(math.isfinite(float(x)) for q in poly for x in q):errors.append('Nicht endliches Polygon: '+ident)
                            triangulate(poly)
                    if kind in ('walls','slabs'):
                        if p.number(obj['top'])<=p.number(obj['bottom']):errors.append('Hoehen: '+ident)
                    for o in obj.get('openings',[]):
                        source_check(o)
                        if o.get('status') not in STATUSES:errors.append('Oeffnungsstatus: '+o['id'])
                        if not o.get('sources'):errors.append('Oeffnungsquelle fehlt: '+o['id'])
                        if o.get('kind') not in ('FENSTER','TUER'):errors.append('Oeffnungsart: '+o['id'])
                        if o['id'] in ids:errors.append('ID doppelt: '+o['id'])
                        ids.add(o['id'])
                        for key in ('offset','width','sill','height'):
                            p.number(o[key])
                        ln=math.dist(obj['a'],obj['b'])
                        if p.number(o['offset'])<0 or p.number(o['offset'])+p.number(o['width'])>ln+1:
                            errors.append('Oeffnung ausserhalb Wand: '+o['id'])
                        if p.number(o['height'])<=0 or p.number(o['width'])<=0:errors.append('Oeffnung ungueltig: '+o['id'])
                        if p.number(o['sill'])<0:errors.append('Negative Bruestung: '+o['id'])
                        z=p.number(o.get('height_reference',obj['bottom']))+p.number(o['sill'])
                        if z < p.number(obj['bottom'])-1:
                            errors.append('Oeffnung unter Wand: '+o['id'])
                        if z+p.number(o['height'])>p.number(obj['top'])+1:
                            errors.append('Oeffnung ueber Wand: '+o['id'])
                    if kind=='prisms':
                        points=obj['points'];v=obj['vector']
                        if len(points)<3 or sum(t*t for t in v)<EPS:errors.append('Prisma: '+ident)
                        else:
                            a,b,c=points[:3]
                            ab=[b[i]-a[i] for i in range(3)];ac=[c[i]-a[i] for i in range(3)]
                            n=[ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0]]
                            norm=math.sqrt(sum(t*t for t in n))
                            if norm<EPS:errors.append('Prisma kollinear: '+ident)
                            else:
                                dev=max(abs(sum(n[i]*(q[i]-a[i]) for i in range(3)))/norm for q in points)
                                if dev>0.1:errors.append('Prisma nicht eben: '+ident)
                except (ValueError,KeyError,ZeroDivisionError,TypeError,SyntaxError,OverflowError) as ex:errors.append(ident+': '+str(ex))
    for kind in ('roof_definitions','dormers'):
        for obj in data.get(kind,[]):
            ident=obj.get('id','?');source_check(obj)
            if ident in ids:errors.append('ID doppelt: '+ident)
            ids.add(ident)
            if obj.get('status') not in STATUSES:errors.append('Dachstatus: '+ident)
            if not obj.get('sources'):errors.append('Dachquelle fehlt: '+ident)
            try:
                x0,y0,x1,y1=[p.number(x) for x in obj['rect']]
                if x1<=x0 or y1<=y0:errors.append('Dachrechteck: '+ident)
                if kind=='roof_definitions':
                    if not 0<p.number(obj['pitch'])<89:errors.append('Dachneigung: '+ident)
                    p.number(obj['eave']);p.number(obj.get('orientation',0))
                    if obj.get('ridge_height') is not None:p.number(obj['ridge_height'])
                    if len(obj['origin'])!=2 or not all(math.isfinite(float(x)) for x in obj['origin']):errors.append('Dachursprung: '+ident)
                else:
                    if obj.get('axis') not in ('x','y'):errors.append('Gaubenachse: '+ident)
                    if obj.get('rear_attachment') is not None:
                        if obj['rear_attachment']!='INTERSECTION_WITH_HOST':errors.append('Gaubenanschlussregel: '+ident)
                        if obj.get('front_axis') not in ('xmin','xmax','ymin','ymax'):errors.append('Gaubenvorderkante: '+ident)
                        if not 0<p.number(obj['pitch'])<80:errors.append('Gaubenneigung: '+ident)
                        p.number(obj['front_roof_z'])
                        if p.number(obj['max_join_distance_mm'])<=0:errors.append('Gaubenanschluss-Suchgrenze: '+ident)
                        if not obj.get('host_parents'):errors.append('Gaubenwirtsdach fehlt: '+ident)
                    else:
                        if len(obj['roof_z'])!=2:errors.append('Gaubenhoehen: '+ident)
                        for z in obj['roof_z']:p.number(z)
            except (KeyError,ValueError,TypeError,ZeroDivisionError) as ex:errors.append(ident+': '+str(ex))
    for key,value in data.get('visual_defaults',{}).items():
        if key.endswith('_mm'):
            try:
                if not math.isfinite(float(value)) or float(value)<=0:errors.append('Visualisierungsparameter: '+key)
            except (ValueError,TypeError):errors.append('Visualisierungsparameter: '+key)
    return {'errors':errors,'warnings':warnings,'unique_ids':len(ids),'parameter_count':len(data['parameters'])}
