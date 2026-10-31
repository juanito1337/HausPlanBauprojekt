# -*- coding: utf-8 -*-
"""G01e dispatcher plus retained single-face DGM checker.

Multiple rectangular grid patches are validated in terrain_patches.py.
The historical single-face path below is used ONLY when NX returns one face.

Scope is deliberately limited to the delivered, untrimmed rectangular DGM:
one sheet, one face, four source sides (possibly split into many CAD edges). No nearest-point search is used for
interior samples. We evaluate actual NX positions and separately check all
source boundary knots/midpoints plus three probes for each actual NX edge.
The boundary chains are validated in terrain_boundary before querying geometry.

The four corner checks determine ONLY a swap/reversal of parameter axes.
They do not fit, scale, translate or modify geometry. Once chosen, the same
mapping is used for every sample. Unexpected reparametrisation is an error,
not an invitation to choose a more favourable map at each sample.

NX Python contract: UFSession.Modeling.AskFaceUvMinmax(faceTag) -> 4 numbers;
Modeling.EvaluateFace(faceTag, 0 [UF_MODL_EVAL], [u,v]) -> object.SrfPos;
Face.GetEdges(); Edge.GetVertices() -> pair of Point3d;
AskMinimumDist is used ONLY with an EDGE tag for boundary comparison.
No C++/.NET output-argument signatures are called from Python.
"""
import copy
import datetime
import itertools
import json
import math
import os
from pathlib import Path
import time

from . import PATCH
from .core import write_json
from .terrain_boundary import plan_boundary, boundary_probes, BoundaryError, MAX_EDGES

SOURCE_SHA256 = 'fb62317c99b8fb2e88a6f529bae98381e83c3399d20da18d5ac1598bcc1cbf2f'
DISTANCE_MM = 0.25
REPORT = 'DGM_FLAECHENPRUEFUNG_G01e.json'
EVENTS = 'DGM_FLAECHENPUNKTE_G01e.jsonl'
FOCUS = (0, 83, 84, 85, 1079, 1089, 1099, 8465, 8466, 16747)
BATCH = 128


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Nicht numerischer NX-/Referenzwert: ' + repr(value))
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Nicht endlicher NX-/Referenzwert.')
    return value


def vector(values, n=3):
    try:
        values = list(values)
    except TypeError as error:
        raise ValueError('Vektor-/Array-Rueckgabe erwartet.') from error
    if len(values) != n:
        raise ValueError('Vektorlaenge %d statt %d.' % (len(values), n))
    return [number(v) for v in values]


def point3d(point):
    # Fixed documented NX Point3d properties, not introspective best-match fields.
    return vector([point.X, point.Y, point.Z])


def prepared_reference(spec):
    from r09.surface_check import reference_checked
    if spec.get('id') != 'DGM' or spec.get('sha256') != SOURCE_SHA256:
        raise ValueError('UV-DGM-Pruefung passt nicht zur festgelegten G01d-Importquelle.')
    ref = reference_checked(spec)
    if spec['expected_sheets'] != 1 or spec['expected_faces'] != 1 or len(ref['sheets']) != 1:
        raise ValueError('UV-DGM-Pruefung erwartet genau einen rechteckigen Quell-Sheet.')
    row = ref['sheets'][0]
    shape = row['grid_shape']
    if shape != [102, 83] or len(row['samples_mm']) != 16748:
        raise ValueError('Originalraster 102 x 83 mit 16.748 Pruefpunkten erwartet.')
    nr, nc = shape
    points = [vector(v) for v in row['samples_mm']]
    # Source ordering is verified rather than accepted just because the count matches.
    for r in range(nr - 1):
        for c in range(nc - 1):
            corners = [points[r*nc+c], points[(r+1)*nc+c],
                       points[r*nc+c+1], points[(r+1)*nc+c+1]]
            centre = [sum(p[k] for p in corners)/4.0 for k in range(3)]
            idx = nr*nc + r*(nc-1) + c
            if math.dist(centre, points[idx]) > 1e-6:
                raise ValueError('Quell-Zellmitte stimmt nicht mit ihren vier Knoten ueberein: %d' % idx)
    return row, points


def sample_fraction(index, nr=102, nc=83):
    if type(index) is not int or not 0 <= index < nr*nc + (nr-1)*(nc-1):
        raise ValueError('Ungueltiger Referenzindex.')
    if index < nr*nc:
        r, c = divmod(index, nc)
    else:
        r, c = divmod(index - nr*nc, nc-1)
        r += 0.5; c += 0.5
    return r/(nr-1), c/(nc-1)


def mapped_uv(fraction, mapping, limits):
    a, b = fraction
    if mapping['swap']:
        a, b = b, a
    if mapping['reverse_u']:
        a = 1.0 - a
    if mapping['reverse_v']:
        b = 1.0 - b
    u0, u1, v0, v1 = limits
    return [u0 + (u1-u0)*a, v0 + (v1-v0)*b]


def determine_mapping(nx_corners, source_corners):
    """Unique axis swap/reversal, based on all four *actual* corner positions."""
    accepted = []
    trials = []
    for swap, ru, rv in itertools.product((False, True), repeat=3):
        m = {'swap':swap, 'reverse_u':ru, 'reverse_v':rv}
        errors = []
        for frac, point in source_corners.items():
            uv = mapped_uv(frac, m, [0,1,0,1])
            errors.append(math.dist(nx_corners[tuple(uv)], point))
        trial = dict(m, maximum_corner_error_mm=max(errors))
        trials.append(trial)
        if max(errors) <= DISTANCE_MM:
            accepted.append(m)
    if len(accepted) != 1:
        error = RuntimeError('Keine eindeutige UV-Eckzuordnung: %d passende Abbildungen; keine Geometrieaenderung.' % len(accepted))
        error.mapping_trials = trials
        raise error
    return accepted[0], trials


def sides(points, nr=102, nc=83):
    """Boundary orientation is irrelevant; preserve the 1-m source polyline."""
    return [
        ('R0', [points[c] for c in range(nc)]),
        ('R1', [points[(nr-1)*nc+c] for c in range(nc)]),
        ('C0', [points[r*nc] for r in range(nr)]),
        ('C1', [points[r*nc+nc-1] for r in range(nr)]),
    ]


def assign_edges(edge_endpoints, source_sides):
    """HISTORICAL G01b checker, kept only for regression. NOT used in production."""
    if len(edge_endpoints) != 4:
        raise RuntimeError('DGM-Randtopologie: genau vier Randkanten erwartet, erhalten %d. Keine stille Behandlung neuer Trimmungen.' % len(edge_endpoints))
    mapping = []
    used = set()
    for name, points in source_sides:
        matches = []
        for j, endpoints in enumerate(edge_endpoints):
            x, y = endpoints
            forward = max(math.dist(x,points[0]),math.dist(y,points[-1]))
            reverse = max(math.dist(x,points[-1]),math.dist(y,points[0]))
            if min(forward,reverse) <= DISTANCE_MM:
                matches.append(j)
        if len(matches) != 1 or matches[0] in used:
            raise RuntimeError('DGM-Randkante nicht eindeutig den Quell-Endpunkten zugeordnet: '+name)
        used.add(matches[0]);mapping.append((name,matches[0],points))
    return mapping


class UVLog:
    """One durable record before/after each batch, full point data in JSONL.
    Batching avoids forcing >16,000 summary rewrites on a mapped drive. On a
    native hard hang the current batch and last flushed data remain; there is
    no claim of a hard timeout or durable storage of the currently executing call.
    """
    def __init__(self, out, trace, adapter):
        self.path=Path(out)/REPORT; self.events=Path(out)/EVENTS
        if self.path.exists() or self.events.exists():
            raise FileExistsError('DGM-UV-Diagnosedatei existiert bereits; kein Ueberschreiben.')
        self.stream=self.events.open('x',encoding='utf-8',buffering=65536)
        self.trace=trace;self.adapter=adapter;self.started=time.perf_counter()
        self.data={'patch':PATCH,'method':'FIXED_UV_COORDINATES_PLUS_SEGMENTED_BOUNDARY_CHAINS',
            'status':'GESTARTET','report_file':str(self.path),'events_file':str(self.events),
            'source_sha256':SOURCE_SHA256,'original_step_sha256':'25a972e13beecdd9ebcf2a3420124803c78805263c806162a9785b84e167fd61',
            'source_boundary_representation':'366_EXACT_LINE_SEGMENTS',
            'source_topology_changed_since_G01c':True,'carrier_surface_modified':False,
            'position_tolerance_mm':DISTANCE_MM,
            'geometry_changed':False,'numeric_translation_or_scaling_fitted':False,
            'closest_point_search_used_for_interior':False,'area_check_performed':False,
            'full_reference_check_performed':False,'geometry_release':False,
            'original_boundary_samples_checked':0,'per_edge_extra_samples_checked':0,
            'as_built_approved':False,'checked_samples':0,'boundary_samples_checked':0,
            'max_position_error_mm':0.0,'max_boundary_error_mm':0.0,
            'focus_points':[], 'scope':'Endlicher parametrischer Koordinatenvergleich und separater Randabgleich. Keine Vermessungs-/Tragwerksfreigabe; keine allgemeine Minimumabstandsberechnung.',
            'new_NX_calls_tested_here':False}
        try:
            self.checkpoint('QUELLREFERENZ')
        except BaseException:
            self.stream.close()
            raise

    def event(self,kind,row):
        from .terrain_audit import json_safe
        self.stream.write(json.dumps({'kind':kind,'data':json_safe(row)},ensure_ascii=False,allow_nan=False)+'\n')

    def checkpoint(self,phase):
        self.stream.flush()
        self.data.update(phase=phase,updated_at=datetime.datetime.now().isoformat(),
                         elapsed_seconds=round(time.perf_counter()-self.started,6))
        write_json(self.path,self.data)
        self.trace.data['direct_parameter_check']=copy.deepcopy(self.data)
        self.trace.write()
        self.adapter.monitor.check_cancel()

    def close(self):
        if not self.stream.closed:
            self.stream.flush();self.stream.close()


def verify_dgm_single_face(adapter, part, spec, out, trace):
    from r09.core import compare_boxes
    from r09.surface_check import distance_result_checked, area_checked
    log=UVLog(out,trace,adapter)
    m=adapter.uf.Modeling
    checked=[]
    try:
        adapter.ensure_work(part)
        adapter.check_millimeters(part,'DGM UV-Koordinatenpruefung')
        for method in ('AskFaceUvMinmax','EvaluateFace','AskMinimumDist'):
            if not callable(getattr(m,method,None)):
                raise RuntimeError('DGM-UV-Pruefung: NX-Python-API fehlt: Modeling.'+method)
        ref,points=prepared_reference(spec)
        bodies=list(part.Bodies)
        if len(bodies)!=1 or bodies[0].IsSolidBody or bodies[0].OwningPart.Tag!=part.Tag:
            raise RuntimeError('DGM: genau ein offener Flaechenkoerper im neuen Part erwartet.')
        body=bodies[0];faces=list(body.GetFaces())
        if len(faces)!=1 or faces[0].OwningPart.Tag!=part.Tag:
            raise RuntimeError('DGM Einzelpfad: Face-Anzahl=%d oder Face-Eigentuemer passt nicht zum Part %s.' % (len(faces), part.Tag))
        face=faces[0]
        boxes=compare_boxes(spec['face_bounding_boxes_mm'],[adapter.surface_box(body)])
        limits=vector(m.AskFaceUvMinmax(face.Tag),4)
        if not (limits[0]<limits[1] and limits[2]<limits[3]):
            raise RuntimeError('DGM: entarteter oder umgekehrter UV-Bereich.')
        # Persist the counts BEFORE any topology assumption. More than four edge
        # objects is NOT an error by itself; the four geometric side chains matter.
        edges=list(face.GetEdges())
        log.data.update(body_tag=int(body.Tag),face_tag=int(face.Tag),nx_sheets=1,nx_faces=1,
            edge_count_returned=len(edges),edge_tags=[int(e.Tag) for e in edges],uv_limits=limits,
            bounds_check=boxes,source_grid_shape=[102,83],available_samples=len(points),
            evaluate_request=0,evaluate_request_meaning='UF_MODL_EVAL: position only, no derivatives at C0 knots',
            edges_modified_or_merged=False)
        log.checkpoint('TATSAECHLICHE_RANDKANTEN_ERFASSEN')
        if len(edges)>MAX_EDGES:
            raise RuntimeError('DGM-Rand: Arbeitslimit von %d Kanten ueberschritten; kein pauschales Geometrieurteil.' % MAX_EDGES)
        if any(e.OwningPart.Tag!=part.Tag for e in edges):
            raise RuntimeError('DGM-Randkante gehoert nicht zum neuen Part.')
        records=[]
        for k,edge in enumerate(edges):
            adapter.operation='DGM G01e Randendpunkte %d/%d'%(k+1,len(edges))
            pair=edge.GetVertices()
            if len(pair)!=2:raise RuntimeError('DGM-Randkante ohne zwei Endpunkte: '+str(edge.Tag))
            row={'index':k,'tag':int(edge.Tag),'endpoints':[point3d(p) for p in pair]}
            records.append(row);log.event('NX_RANDKANTEN_ENDPUNKTE',row)
            log.data['edge_endpoints_read']=k+1
            if (k+1)%BATCH==0:log.checkpoint('TATSAECHLICHE_RANDKANTEN_ERFASSEN')
        log.data['edge_records']=records
        log.checkpoint('VIER_RANDSEITEN_ALS_KETTEN_ZUORDNEN')
        source_sides=sides(points)
        groups,boundary_audit=plan_boundary(records,source_sides,DISTANCE_MM)
        log.data['boundary_chains']=boundary_audit
        probes=list(boundary_probes(groups))
        expected_boundary_checks=736+3*len(edges)
        if len(probes)!=expected_boundary_checks:
            raise RuntimeError('Interner Fehler im segmentunabhaengigen Randpruefumfang.')
        log.data['expected_boundary_samples']=expected_boundary_checks
        log.data['expected_original_boundary_samples']=736
        log.data['expected_per_edge_extra_samples']=3*len(edges)
        adapter.log('G01e DGM (Einzelflaeche): %d CAD-Kanten den vier Quellseiten zugeordnet; %d Randproben vorgesehen.'%(len(edges),expected_boundary_checks))
        log.checkpoint('VIER_ECKEN_AUS_NX_LESEN')

        def evaluate(uv,kind,idx=None):
            started=time.perf_counter()
            adapter.operation='DGM G01e %s %s'%(kind,'' if idx is None else idx)
            try:
                value=m.EvaluateFace(face.Tag,0,list(uv))
                if not hasattr(value,'SrfPos'):
                    raise RuntimeError('EvaluateFace-Rueckgabe besitzt kein SrfPos: '+type(value).__name__)
                actual=vector(value.SrfPos)
                log.event('NX_EVALUATE_FACE',{'kind':kind,'index':idx,'face_tag':int(face.Tag),
                    'uv':uv,'actual_position_mm':actual,'seconds':time.perf_counter()-started})
                return actual
            except Exception as error:
                log.event('NX_EVALUATE_FACE_FEHLER',{'kind':kind,'index':idx,'uv':uv,
                    'error':str(error),'exception_type':type(error).__name__,
                    'nx_error_code':getattr(error,'ErrorCode',None)})
                raise

        corner_indices={(0,0):0,(1,0):101*83,(0,1):82,(1,1):8465}
        actual_corners={}
        for frac in corner_indices:
            uv=mapped_uv(frac,{'swap':False,'reverse_u':False,'reverse_v':False},limits)
            actual_corners[frac]=evaluate(uv,'ECKE')
        mapping,trials=determine_mapping(actual_corners,{f:points[i] for f,i in corner_indices.items()})
        log.data.update(uv_mapping=mapping,mapping_trials=trials,
                        actual_corner_positions={str(k):v for k,v in actual_corners.items()})
        # Compare the historic failing sites first so a real deformation is reported
        # before the large grid pass. ALL points are still checked exactly once.
        order=list(FOCUS)+[i for i in range(len(points)) if i not in FOCUS]
        if len(order)!=len(points) or len(set(order))!=len(points):
            raise RuntimeError('Interner Fehler der DGM-Pruefreihenfolge.')
        for chunk in range(0,len(order),BATCH):
            batch=order[chunk:chunk+BATCH]
            log.data['active_batch']={'start':chunk,'count':len(batch),'first_source_index':batch[0],
                                      'last_source_index':batch[-1]}
            log.checkpoint('RASTERPUNKTE_DIREKT_AUSWERTEN')
            for idx in batch:
                uv=mapped_uv(sample_fraction(idx),mapping,limits)
                actual=evaluate(uv,'QUELLPUNKT',idx)
                deviation=math.dist(points[idx],actual)
                row={'source_index':idx,'uv':uv,'source_mm':points[idx],
                     'NX_position_mm':actual,'position_error_mm':deviation}
                log.event('KOORDINATENVERGLEICH',row)
                log.data['checked_samples']+=1
                log.data['max_position_error_mm']=max(log.data['max_position_error_mm'],deviation)
                if idx in FOCUS:log.data['focus_points'].append(row)
                log.data['last_sample']=row
                if deviation>DISTANCE_MM:
                    log.data['failed_sample']=row
                    raise RuntimeError('DGM-UV-Koordinatenabweichung Punkt %d: %.6f mm > %.3f mm; keine Freigabe.'%(idx,deviation,DISTANCE_MM))
                checked.append(idx)
            if chunk==0 or (chunk//BATCH)%8==0:
                adapter.log('G01e DGM (Einzelflaeche): %d/%d Originalpunkte direkt aus NX verglichen.'%(len(checked),len(points)))
        log.data['active_batch']=None
        log.data['all_carrier_reference_points_passed']=True
        log.data['carrier_reference_points_expected']=16748
        log.checkpoint('SEGMENTIERTE_RANDKANTEN_PRUEFEN')
        # One fixed assignment per source station. Never select the edge with the
        # smallest measured error. Every actual edge gets its own additional probes.
        touched=set()
        for start in range(0,len(probes),BATCH):
            batch=probes[start:start+BATCH]
            log.data['active_boundary_batch']={'start':start,'count':len(batch)}
            log.checkpoint('SEGMENTIERTE_RANDKANTEN_PRUEFEN')
            for j,probe in enumerate(batch,start):
                edge_rec=probe['edge'];edge=edges[edge_rec['index']]
                q=probe['query_mm'];name=probe['side']
                adapter.operation='DGM G01e Rand %s Kante %d Probe %d'%(name,int(edge.Tag),j)
                data={'side':name,'index':j,'query_mm':q,'probe_kind':probe['kind'],
                      'edge_tag':int(edge.Tag),'source_fraction':probe['fraction']}
                try:
                    raw=m.AskMinimumDist(0,edge.Tag,1,list(q),0,[0.,0.,0.])
                    data['raw_result']=raw
                    log.event('NX_RANDABSTAND',data)
                    distance=distance_result_checked(raw,q)
                    log.data['boundary_samples_checked']+=1
                    field=('per_edge_extra_samples_checked' if probe['kind']=='JE_KANTE_ZUSATZPROBE'
                           else 'original_boundary_samples_checked')
                    log.data[field]+=1;touched.add(int(edge.Tag))
                    log.data['max_boundary_error_mm']=max(log.data['max_boundary_error_mm'],distance)
                    if distance>DISTANCE_MM:
                        data['distance_mm']=distance
                        log.data['failed_boundary']=data
                        raise RuntimeError('DGM-Randabweichung %s Kante %d Probe %d: %.6f mm > %.3f mm.'%(name,int(edge.Tag),j,distance,DISTANCE_MM))
                except Exception as error:
                    log.data['active_boundary_failure']=dict(data,error=str(error),
                        exception_type=type(error).__name__,nx_error_code=getattr(error,'ErrorCode',None))
                    raise
        log.data['active_boundary_batch']=None
        log.data['actual_edges_with_distance_checks']=len(touched)
        if (log.data['boundary_samples_checked']!=expected_boundary_checks or len(checked)!=16748 or
            log.data['original_boundary_samples_checked']!=736 or len(touched)!=len(edges) or
            log.data['per_edge_extra_samples_checked']!=3*len(edges)):
            raise RuntimeError('DGM: Pruefumfang nicht vollstaendig abgearbeitet.')
        # An independent negative comparison must fail the same tolerance test.
        uv=mapped_uv(sample_fraction(1089),mapping,limits)
        actual=evaluate(uv,'KONTROLLPUNKT_OBERHALB')
        elevated=list(points[1089]);elevated[2]=max(p[2] for p in points)+1000.
        off=math.dist(elevated,actual)
        log.data['negative_control']={'source_index':1089,'reference_above_mm':elevated,
            'NX_position_mm':actual,'distance_mm':off,'correctly_not_accepted':off>999.0}
        if off<=999.:raise RuntimeError('DGM: Gegenprobe oberhalb der Flaeche unerwartet nahe; keine Freigabe.')
        if adapter.validation_level=='INTENSIV':
            log.checkpoint('OPTIONALE_FLAECHENINTEGRATION')
            measured=adapter.surface_area_mm2(body)
            area=area_checked(ref['area_mm2'],measured)
            log.data.update(area_check_performed=True,area_result=area)
            if not area['area_passed']:raise RuntimeError('DGM: Flaecheninhalt weicht im INTENSIV-Modus ab.')
        log.data.update(status='UV_RASTER_UND_RANDVERGLEICH_BESTANDEN_KEIN_BESTANDSNACHWEIS',
            full_reference_check_performed=True,selected_checks_passed=True,
            geometry_release=False)
        log.checkpoint('PRUEFUNG_BESTANDEN_SPEICHERN_AUSSTEHEND')
        for key,value in {
            'HAUS_IMPORTPRUEFUNG':'G01e_EINZELFLAECHE_UV_PLUS_RANDKETTEN',
            'HAUS_ALLE_QUELLPUNKTE_GEPRUEFT':'True',
            'HAUS_FLAECHENINHALT_GEPRUEFT':str(log.data['area_check_performed']),
            'HAUS_RANDKANTEN_ANZAHL':str(len(edges)),
            'HAUS_IMPORTPRUEFUNG_HINWEIS':'16.748 Koordinatenvergleiche; 736 Originalrandproben + 3 je NX-Kante; vier Randseiten; kein Bestandsnachweis.'}.items():
            adapter._set_user_attribute(part,key,value,'DGM')
        result=dict(boxes,faces=1,source_faces=1,face_count_changed=False,
            faces_per_sheet_import_order=[1],checked_source_points=16748,
            available_source_points=16748,max_point_distance_mm=log.data['max_position_error_mm'],
            geometry_validation_status=log.data['status'],validation_level='DGM_UV_G01c',
            requested_environment_level=adapter.validation_level,geometry_report=str(log.path),
            area_check_performed=log.data['area_check_performed'],full_reference_check_performed=True,
            boundary_samples_checked=expected_boundary_checks,original_boundary_samples_checked=736,
            actual_boundary_edges=len(edges),boundary_chains_passed=True,normal_distance_search_used=False)
        return result
    except Exception as error:
        log.data.update(status='DGM_UV_PRUEFUNG_ABGEBROCHEN',error=str(error),
                        exception_type=type(error).__name__,operation=adapter.operation,
                        selected_checks_passed=False,geometry_release=False)
        if hasattr(error,'boundary_details'):log.data['boundary_chains']=error.boundary_details
        if hasattr(error,'mapping_trials'):log.data['mapping_trials']=error.mapping_trials
        try:log.checkpoint('ABGEBROCHEN')
        except Exception as secondary:log.data['secondary_logging_error']=str(secondary)
        error.nx_terrain_uv_g01b=copy.deepcopy(log.data)  # compatibility for existing report readers
        error.nx_terrain_boundary_g01c=copy.deepcopy(log.data)
        error.nx_surface_check={'id':'DGM','status':log.data['status'],'report_file':str(log.path),
            'error':str(error),'operation':adapter.operation,'method':log.data['method'],
            'checked_samples':log.data['checked_samples'],'failed_sample':log.data.get('failed_sample')}
        raise
    finally:
        log.close()


def verify_dgm_uv(adapter, part, spec, out, trace):
    """Dispatch by actual NX topology; counts alone never grant acceptance.

    Retain the single-face verifier for installations keeping a single face.
    Rectangular raster subfaces are independently mapped and checked by G01e.
    """
    bodies = list(part.Bodies)
    if len(bodies) == 1 and len(bodies[0].GetFaces()) > 1:
        from .terrain_patches import verify_dgm_patches
        return verify_dgm_patches(adapter, part, spec, out, trace)
    return verify_dgm_single_face(adapter, part, spec, out, trace)


def make_uv_audited_adapter(base_type,reference_path):
    from .terrain_audit import make_audited_adapter
    return make_audited_adapter(base_type,reference_path,dgm_validator=verify_dgm_uv)
