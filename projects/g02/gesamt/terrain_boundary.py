# -*- coding: utf-8 -*-
"""G01d: compare one rectangular terrain perimeter, not four CAD edge IDs.

Pure Python; no NX calls and no modification of geometry. NX may divide each
source side into several edges. Every actual edge must be assigned exactly once
from its actual end positions. The sorted intervals must cover all four sides,
with no gap, overlap or disconnected junction beyond the existing CAD tolerance.
No integer edge count (including the reported 285) grants acceptance by itself.

This is an endpoint/interval test. It is combined by terrain_uv with actual NX
edge-distance probes and actual UV-position evaluation. Finite probes are not a
mathematical identity proof of the continuous, trimmed surface.
"""
import bisect
import math

MAX_EDGES = 4096  # documented workload limit, NOT a geometric acceptance count
TOLERANCE_MM = 0.25
MIN_SPAN_MM = 1e-7


class BoundaryError(RuntimeError):
    def __init__(self, message, details):
        super().__init__(message)
        self.boundary_details = details


def _point(value):
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise ValueError('DGM-Rand: genau drei Koordinaten erforderlich.')
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in value):
        raise ValueError('DGM-Rand: ungueltige oder nicht endliche Koordinate.')
    return [float(x) for x in value]


class SourceSide:
    """Straight XY side with the original piecewise linear terrain heights."""
    def __init__(self, name, points):
        self.name = str(name)
        self.points = [_point(p) for p in points]
        if len(self.points) < 2:
            raise ValueError('DGM-Rand: Quellseite braucht mindestens zwei Punkte.')
        p, q = self.points[0], self.points[-1]
        self.delta = [q[i]-p[i] for i in range(2)]
        self.length_mm = math.hypot(*self.delta)
        if self.length_mm <= MIN_SPAN_MM:
            raise ValueError('DGM-Rand: entartete Quellseite '+self.name)
        self.stations = [self.project_xy(v) for v in self.points]
        for i, (t, point) in enumerate(zip(self.stations, self.points)):
            expected_xy = [p[k]+t*self.delta[k] for k in range(2)]
            if math.hypot(*(point[k]-expected_xy[k] for k in range(2))) > 1e-4:
                raise ValueError('DGM-Rand: Quellseite in XY nicht geradlinig: '+self.name)
            if i and t <= self.stations[i-1]:
                raise ValueError('DGM-Rand: Quellpunkte nicht streng geordnet: '+self.name)
        if abs(self.stations[0]) > 1e-12 or abs(self.stations[-1]-1) > 1e-12:
            raise ValueError('DGM-Rand: ungueltiger Quellparameterbereich.')

    def project_xy(self, point):
        return sum((point[k]-self.points[0][k])*self.delta[k] for k in range(2))/(self.length_mm*self.length_mm)

    def at(self, t):
        # Only evaluate the ORIGINAL segment interpolation. Never move a NX vertex.
        t = max(0., min(1., float(t)))
        i = max(0, min(len(self.points)-2, bisect.bisect_right(self.stations, t)-1))
        f = (t-self.stations[i])/(self.stations[i+1]-self.stations[i])
        return [self.points[i][k]+f*(self.points[i+1][k]-self.points[i][k]) for k in range(3)]

    def locate(self, point, tolerance):
        t = self.project_xy(point)
        tol_t = tolerance/self.length_mm
        if t < -tol_t or t > 1.+tol_t:
            return None
        error = math.dist(point, self.at(t))
        return (t, error) if error <= tolerance else None


def plan_boundary(edge_records, source_sides, tolerance=TOLERANCE_MM):
    """Return fixed side/edge assignments. Reject rather than drop unknown edges."""
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not math.isfinite(tolerance) or not 0 < tolerance <= TOLERANCE_MM:
        raise ValueError('DGM-Rand: Toleranz darf nicht groesser als 0,25 mm sein.')
    audit = {'actual_edge_count':len(edge_records), 'side_count_required':4,
             'tolerance_mm':tolerance, 'maximum_supported_edges':MAX_EDGES,
             'count_is_not_geometric_acceptance':True, 'geometry_changed':False,
             'edges':[], 'sides':[], 'status':'ENDPUNKTE_ZUORDNEN'}
    def fail(reason, **kw):
        audit.update(status='RANDPRUEFUNG_ABGEBROCHEN', reason=reason, **kw)
        raise BoundaryError('DGM-Rand: '+reason, audit)
    if len(edge_records) < 4:
        fail('Vier Quellseiten nicht abgedeckt: zu wenige unterschiedliche Kanten.')
    if len(edge_records) > MAX_EDGES:
        fail('Arbeitslimit von %d Randkanten ueberschritten; gesonderte Pruefung erforderlich.' % MAX_EDGES)
    sides = [SourceSide(name, pts) for name, pts in source_sides]
    if len(sides)!=4 or {s.name for s in sides} != {'R0','R1','C0','C1'}:
        raise ValueError('DGM-Rand: die vier rechteckigen Quellseiten R0/R1/C0/C1 sind erforderlich.')
    groups = {s.name:{'source':s,'segments':[]} for s in sides}
    used_tags=set();used_indices=set()
    for i, rec in enumerate(edge_records):
        tag=rec['tag'];index=rec['index']
        if type(tag) is not int or tag<=0 or type(index) is not int or index<0:
            fail('Ungueltige Kantenkennung.', edge_record_index=i)
        if tag in used_tags or index in used_indices:
            fail('Doppelte Kantenkennung; keine stille Deduplizierung.', edge_record_index=i, edge_tag=tag)
        used_tags.add(tag);used_indices.add(index)
        if not isinstance(rec['endpoints'],(list,tuple)) or len(rec['endpoints'])!=2:
            fail('Kante ohne zwei auswertbare Endpunkte.', edge_tag=tag)
        p,q=map(_point,rec['endpoints'])
        if math.dist(p,q)<=MIN_SPAN_MM:
            fail('Kante mit gleichen/entarteten Endpunkten; Innenring oder Sondertopologie nicht zugelassen.', edge_tag=tag)
        candidates=[]
        for side in sides:
            a,b=side.locate(p,tolerance),side.locate(q,tolerance)
            if a is not None and b is not None:
                span=abs(b[0]-a[0])*side.length_mm
                if span>MIN_SPAN_MM:
                    candidates.append((side,a,b))
        if len(candidates)!=1:
            fail('Randkante nicht eindeutig einer Quellseite zugeordnet (Innenkante, falsche Hoehe oder Eckquerung).',
                 edge_tag=tag, actual_endpoints_mm=[p,q], candidate_sides=[s.name for s,_,_ in candidates])
        side,a,b=candidates[0]
        forward=a[0]<b[0]
        lo,hi=(a,b) if forward else (b,a)
        ep0,ep1=(p,q) if forward else (q,p)
        row={'index':index, 'tag':tag, 'side':side.name,
             'start_fraction':lo[0], 'end_fraction':hi[0],
             'forward_vs_source':forward, 'start_mm':ep0,'end_mm':ep1,
             'maximum_endpoint_error_mm':max(a[1],b[1])}
        groups[side.name]['segments'].append(row);audit['edges'].append(row)

    for side in sides:
        group=groups[side.name]
        chain=sorted(group['segments'],key=lambda e:(e['start_fraction'],e['end_fraction'],e['tag']))
        if not chain:
            fail('Quellseite fehlt: '+side.name)
        group['segments']=chain
        gap=max(0.,chain[0]['start_fraction'])*side.length_mm
        over=max(0.,-chain[0]['start_fraction'])*side.length_mm
        max_join=0.;last=chain[0]
        for current in chain[1:]:
            jump=(current['start_fraction']-last['end_fraction'])*side.length_mm
            gap+=max(0.,jump);over+=max(0.,-jump)
            join=math.dist(last['end_mm'],current['start_mm']);max_join=max(max_join,join)
            if join>tolerance:
                fail('Randkette hat eine offene oder doppelte Verbindung an '+side.name,
                     junction_gap_mm=join, previous_edge=last['tag'], next_edge=current['tag'])
            last=current
        gap+=max(0.,1.-chain[-1]['end_fraction'])*side.length_mm
        over+=max(0.,chain[-1]['end_fraction']-1.)*side.length_mm
        summary={'side':side.name,'edge_count':len(chain),'ordered_edge_tags':[e['tag'] for e in chain],
                 'first_fraction':chain[0]['start_fraction'],'last_fraction':chain[-1]['end_fraction'],
                 'total_projected_gap_mm':gap,'total_projected_overlap_mm':over,
                 'max_junction_error_mm':max_join,
                 'first_corner_error_mm':math.dist(chain[0]['start_mm'],side.points[0]),
                 'last_corner_error_mm':math.dist(chain[-1]['end_mm'],side.points[-1])}
        audit['sides'].append(summary)
        # Accumulated gap/overlap limit: never allow hundreds of tolerated errors to accumulate.
        if gap>tolerance or over>tolerance:
            fail('Quellseite hat Luecken, Ueberlappungen oder unvollstaendige Abdeckung: '+side.name,
                 failed_side=summary)
        if max(summary['first_corner_error_mm'],summary['last_corner_error_mm'])>tolerance:
            fail('Randkette erreicht die Quellecke nicht: '+side.name, failed_side=summary)
        group['ends']=[e['end_fraction'] for e in chain]

    # Explicit four corner connections; sorted endpoints alone are not enough.
    corners=[('R0',0,'C0',0),('R0',-1,'C1',0),('R1',0,'C0',-1),('R1',-1,'C1',-1)]
    audit['corner_connections']=[]
    for a,ea,b,eb in corners:
        pa=groups[a]['segments'][ea]['start_mm' if ea==0 else 'end_mm']
        pb=groups[b]['segments'][eb]['start_mm' if eb==0 else 'end_mm']
        d=math.dist(pa,pb)
        audit['corner_connections'].append({'side_a':a,'side_b':b,'gap_mm':d})
        if d>tolerance:fail('Rand ist an einer Ecke nicht geschlossen.', corner_gap_mm=d, sides=[a,b])
    audit.update(status='VIER_QUELLSEITEN_DURCH_KANTENKETTEN_ABGEDECKT',
                 assigned_edges=sum(len(g['segments']) for g in groups.values()),
                 max_endpoint_error_mm=max(r['maximum_endpoint_error_mm'] for r in audit['edges']))
    return groups,audit


def edge_for_station(group, t):
    """Choose by the fixed source interval, NOT by the most favourable measured distance."""
    idx=bisect.bisect_left(group['ends'],t)
    idx=min(idx,len(group['segments'])-1)
    return group['segments'][idx]


def boundary_probes(groups):
    """736 original knots/midpoints, plus 3 explicit probes for EVERY actual edge."""
    for name in ('R0','R1','C0','C1'):
        g=groups[name];s=g['source']
        for i,t in enumerate(s.stations):
            yield {'kind':'ORIGINAL_RANDKNOTEN','side':name,'index':i,'fraction':t,
                   'query_mm':s.points[i], 'edge':edge_for_station(g,t)}
            if i+1<len(s.points):
                tm=(t+s.stations[i+1])/2.
                yield {'kind':'ORIGINAL_RANDMITTE','side':name,'index':i,'fraction':tm,
                       'query_mm':s.at(tm),'edge':edge_for_station(g,tm)}
        for edge in g['segments']:
            for frac in (.25,.5,.75):
                t=edge['start_fraction']+(edge['end_fraction']-edge['start_fraction'])*frac
                yield {'kind':'JE_KANTE_ZUSATZPROBE','side':name,'index':edge['index'],
                       'edge_fraction':frac,'fraction':t,'query_mm':s.at(t),'edge':edge}
