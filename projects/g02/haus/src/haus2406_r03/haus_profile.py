# -*- coding: utf-8 -*-
"""Strenge 3D-Profilpruefung vor NX-Feature-Erzeugung. Keine CAD-Kernelpruefung."""
import math
from .haus_geometry import area, convex, Parameters

MIN_EDGE_MM = 0.01
PLANAR_MM = 0.001


def _dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def _cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def profile_check(points, direction, name='PROFIL'):
    if len(points) < 3:
        raise ValueError(name + ': mindestens drei Eckpunkte erforderlich.')
    if any(len(p) != 3 for p in points) or len(direction) != 3:
        raise ValueError(name + ': 3D-Koordinaten und 3D-Richtung erforderlich.')
    points = [[float(x) for x in p] for p in points]
    direction = [float(x) for x in direction]
    if not all(math.isfinite(x) for p in points + [direction] for x in p):
        raise ValueError(name + ': NaN oder unendliche Koordinate.')
    edges = [math.dist(a, b) for a, b in zip(points, points[1:] + points[:1])]
    if min(edges) < MIN_EDGE_MM - 1e-8:
        raise ValueError(name + ': Profilkante kuerzer als %.4f mm.' % MIN_EDGE_MM)
    norm_d = math.sqrt(_dot(direction, direction))
    if norm_d <= 1e-12:
        raise ValueError(name + ': Extrusionsrichtung ist Null.')
    direction = [x/norm_d for x in direction]
    # Maximalflaechiges Dreieck statt blind die ersten drei Ecken zu verwenden.
    origin = points[0]
    vectors = [[q[i]-origin[i] for i in range(3)] for q in points[1:]]
    normals = [_cross(a,b) for i,a in enumerate(vectors) for b in vectors[i+1:]]
    normal = max(normals, key=lambda x:_dot(x,x))
    size = math.sqrt(_dot(normal,normal))
    if size < 1e-9:
        raise ValueError(name + ': kollineares Profil.')
    normal = [x/size for x in normal]
    deviation = max(abs(_dot(normal, [q[i]-origin[i] for i in range(3)])) for q in points)
    if deviation > PLANAR_MM:
        raise ValueError(name + ': Profil nicht eben (Abweichung %.6g mm).' % deviation)
    projection = abs(_dot(normal, direction))
    if projection < 1e-7:
        raise ValueError(name + ': Extrusionsrichtung liegt in der Profilebene (kein Volumen).')
    u = vectors[0]
    size_u = math.sqrt(_dot(u,u))
    u = [x/size_u for x in u]
    v = _cross(normal,u)
    flat = [[_dot([q[i]-origin[i] for i in range(3)],axis) for axis in (u,v)] for q in points]
    # Eigentliche Bauauftraege bestehen ausschliesslich aus konvexen Zellen.
    # Nichtkonvexitaet einschliesslich Selbstkreuzung wird nicht NX ueberlassen.
    if not convex(flat):
        raise ValueError(name + ': nichtkonvexes/selbstschneidendes Profil; vorab zerlegen.')
    # Nichtbenachbarte Beruehrungen / Kreuzungen explizit pruefen.
    def cross2(a,b,c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def on(a,b,p):
        return abs(cross2(a,b,p)) < 1e-8 and min(a[0],b[0])-1e-8 <= p[0] <= max(a[0],b[0])+1e-8 and min(a[1],b[1])-1e-8 <= p[1] <= max(a[1],b[1])+1e-8
    n = len(flat)
    for i in range(n):
        a,b = flat[i],flat[(i+1)%n]
        for j in range(i+1,n):
            if j in ((i+1)%n, (i-1)%n):
                continue
            c,d = flat[j],flat[(j+1)%n]
            f,g,h,k = cross2(a,b,c),cross2(a,b,d),cross2(c,d,a),cross2(c,d,b)
            if (f*g<0 and h*k<0) or on(a,b,c) or on(a,b,d) or on(c,d,a) or on(c,d,b):
                raise ValueError(name + ': nichtbenachbarte Profilkanten beruehren/kreuzen sich.')
    return {'minimum_edge_mm':min(edges), 'planarity_mm':deviation,
            'area_mm2':abs(area(flat)), 'normal_direction_projection':projection,
            'direction':direction}


def validate_compiled_profiles(compiled, params):
    records=[]
    for part in compiled['parts']:
        for solid in part['solids']:
            if 'points' in solid:
                points=solid['points'];direction=solid['vector']
            else:
                points=[[q[0],q[1],0] for q in solid['polygon']];direction=[0,0,1]
                if params.number(solid['top'])-params.number(solid['bottom']) <= 0.001:
                    raise ValueError(solid['id']+': keine ausreichende Ausgangshoehe.')
            check=profile_check(points,direction,solid['id'])
            records.append(dict(check,id=solid['id'],part=part['id']))
    return {'status':'OFFLINE_PROFILE_BESTANDEN', 'profile_count':len(records),
            'minimum_edge_mm':min((r['minimum_edge_mm'] for r in records),default=None),
            'max_planarity_mm':max((r['planarity_mm'] for r in records),default=None),
            'scope':'Mathematische Vorpruefung, NICHT NX-Kernel.', 'profiles':records}
