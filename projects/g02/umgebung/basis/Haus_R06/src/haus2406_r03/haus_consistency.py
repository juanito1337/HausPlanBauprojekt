# -*- coding: utf-8 -*-
"""Quellen-/Referenz- und freie-Oeffnungspruefung des numerischen Bauauftrags.

Keine Lastberechnung, kein Aufmass, kein NX-/Parasolid-Formnachweis. Der Pruefer
schneidet absichtlich KEINE ungeklärten Hauptbau-/Anbauanschluesse automatisch.
"""
import math
from collections import Counter
from .haus_geometry import Parameters, enabled, opening_polygon, area
from .haus_roof import hip, height
from .haus_audit import vertical_record, intersection_volume, audit_compiled


def walk(value, path='$'):
    if isinstance(value, dict):
        yield path, value
        for key, child in value.items():
            yield from walk(child, path+'.'+str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, path+'[%d]'%index)


def source_integrity(data):
    """Checks references, NOT whether the cited source proves the assertion."""
    docs=data.get('source_document_pages',{})
    errors=[];count=0;used=Counter()
    for path,node in walk(data):
        source_items=list(node.get('sources',[])) if isinstance(node.get('sources'),list) else []
        if isinstance(node.get('source'),str) and node.get('page') is not None:
            source_items.append({'document':node['source'],'page':node['page']})
        for src in source_items:
            count+=1
            if not isinstance(src,dict):
                errors.append({'path':path,'error':'Quellreferenz ist kein Objekt'});continue
            doc=src.get('document');page=src.get('page');used[str(doc)]+=1
            if doc not in docs or type(page) is not int or not 1<=page<=docs.get(doc,0):
                errors.append({'path':path,'document':doc,'page':page,'error':'Dokument/Seite nicht im Quellenregister'})
    return {'checked_references':count,'errors':errors,'references_per_document':dict(sorted(used.items())),
      'meaning':'Referenzen auf vorhandene Dokumente/Seiten; KEIN semantischer Inhaltsnachweis.'}


def system_integrity(data):
    systems=data.get('construction',{}).get('systems',[])
    ids=[s.get('id') for s in systems];duplicates=[key for key,n in Counter(ids).items() if n>1]
    dangling=[]
    for path,node in walk(data):
        value=node.get('system_id')
        if value and value not in ids:
            dangling.append({'path':path,'system_id':value})
    return {'registered_systems':len(ids),'duplicate_systems':duplicates,'dangling':dangling}


def opening_clearance(data, compiled, threshold_mm3=1000.0):
    """Intersect the WHOLE declared clear opening, not only its generic frame.
    All modeled walls in all parts are considered. A box filter merely prunes;
    the final value is the polygon/plane intersection volume. A 1 cm3 threshold
    is numerical detection sensitivity, not permitted building tolerance.
    """
    if not math.isfinite(threshold_mm3) or threshold_mm3<=0:
        raise ValueError('Ungueltige Oeffnungspruefschwelle')
    params=Parameters(data['parameters'])
    records=[vertical_record(s,params,p['id']) for p in compiled['parts'] for s in p['solids']
             if s['kind']=='WAND']
    coverage={r['id']:r for r in compiled.get('coverage',[])}
    checks=[];not_built=[]
    for part in data['parts']:
        for wall in part.get('walls',[]):
            for opening in wall.get('openings',[]):
                item=coverage.get(opening['id'],{})
                if not item.get('status','').startswith('GEPLANT'):
                    not_built.append(opening['id']);continue
                poly=opening_polygon(wall,opening,params,extra=0)
                ref=opening.get('height_reference',wall['bottom'])
                z=params.number(ref)+params.number(opening['sill']);top=z+params.number(opening['height'])
                body={'polygon':poly,'lo':[0,0,z],'hi':[0,0,top]}
                A=[min(q[k] for q in poly) for k in (0,1)]+[z]+[max(q[k] for q in poly) for k in (0,1)]+[top]
                hits=[]
                for other in records:
                    B=other['box']
                    if any(min(A[k+3],B[k+3])-max(A[k],B[k])<=.001 for k in range(3)):continue
                    volume=intersection_volume(body,other)
                    if volume>threshold_mm3:
                        hits.append({'body':other['id'],'wall':other['parent'],'part':other['part'],
                                     'volume_cm3':round(volume/1000,6),'own_host_wall':other['parent']==wall['id']})
                checks.append({'opening':opening['id'],'wall':wall['id'],'part':part['id'],
                  'height_reference':ref,'bottom_mm':z,'top_mm':top,'obstructions':hits,
                  'status':'BLOCKIERT' if hits else 'NUMERISCH_FREI'})
    return {'scope':'Modellierte freie Oeffnung gegen modellierte Waende; keine reale lichte Herstellerbreite.',
      'threshold_cm3':threshold_mm3/1000,'checked_openings':len(checks),
      'blocked_count':sum(bool(c['obstructions']) for c in checks),
      'not_built':not_built,'checks':checks}


def roof_height_checks(data):
    params=Parameters(data['parameters']);checks=[]
    for definition in data.get('roof_definitions',[]):
        if not enabled(definition,params,True)[0]:continue
        faces=hip(definition,params)
        values=[height(f,q) for f in faces for q in f['polygon']]
        target=params.number(definition['ridge_height']) if definition.get('ridge_height') is not None else None
        checks.append({'roof':definition['id'],'maximum_height_mm':max(values),'eave_derived_mm':min(values),
          'sourced_ridge_target_mm':target,'difference_mm':max(values)-target if target is not None else None,
          'status':'QUELLENKETTE_EINGEHALTEN' if target is not None and abs(max(values)-target)<.001 else
                   'HOEHENABWEICHUNG' if target is not None else 'PROXY_GEOMETRIE_OHNE_UNABHAENGIGEN_FIRSTSOLLWERT',
          'as_built_verified':False})
    return checks


def map_point_local(point, coordinate):
    origin=coordinate['local_origin_G05_pdf_pt'];scale=coordinate['mm_per_pdf_pt']
    east=(point[0]-origin[0])*scale[0]
    north=-(point[1]-origin[1])*scale[1]
    return [east*u[0]+north*u[1] for u in (coordinate['local_x_in_east_north'],coordinate['local_y_in_east_north'])]


def registration_checks(site, tolerance_mm=.02):
    """Independent recalculation from saved source points + matrices.
    Checks reproducibility only; cannot improve the accuracy of those maps.
    """
    if not site or not site.get('enabled'):return {'enabled':False,'checks':[],'errors':[]}
    coordinate=site['coordinate_reference'];regs={r['id']:r for r in site['registrations']}
    checks=[];errors=[];control_checks=[]
    for reg in site.get('registrations',[]):
        original=reg.get('source_points',[]);targets=reg.get('target_G05_pdf_pt',[]);stored=reg.get('control_residuals_mm',[])
        if not len(original)==len(targets)==len(stored) or not original:
            errors.append({'registration':reg['id'],'error':'Kontrollpunkte/Restwertanzahl unvollstaendig'});continue
        m=reg['matrix_2x3'];residuals=[]
        for q,destination in zip(original,targets):
            pdf=[r[0]*q[0]+r[1]*q[1]+r[2] for r in m]
            residuals.append(math.dist(map_point_local(pdf,coordinate),map_point_local(destination,coordinate)))
        delta=max(abs(a-b) for a,b in zip(residuals,stored))
        control_checks.append({'registration':reg['id'],'control_count':len(original),
          'max_stored_residual_difference_mm':delta,'max_source_fit_residual_mm':max(residuals)})
        if delta>tolerance_mm:errors.append({'registration':reg['id'],'error':'Kontrollreste nicht reproduzierbar','difference_mm':delta})
    for route in site.get('routes',[]):
        reg=regs.get(route.get('registration_id'))
        source=route.get('source_points_pdf_pt')
        if not reg or not source:
            errors.append({'route':route['id'],'error':'Quellpunkte/Registrierung fehlen'});continue
        if len(source)!=len(route['points_local_mm']):
            errors.append({'route':route['id'],'error':'Quell-/Modellpunktzahl verschieden'});continue
        m=reg['matrix_2x3'];deltas=[]
        for q,given in zip(source,route['points_local_mm']):
            pdf=[r[0]*q[0]+r[1]*q[1]+r[2] for r in m]
            calculated=map_point_local(pdf,coordinate)
            deltas.append(math.dist(given,calculated))
        maximum=max(deltas,default=0)
        row={'route':route['id'],'max_recalculation_difference_mm':maximum,
             'status':'REPRODUZIERBAR' if maximum<=tolerance_mm else 'TRANSFORMATION_ABWEICHEND'}
        checks.append(row)
        if maximum>tolerance_mm:errors.append(row)
    return {'enabled':True,'tolerance_mm':tolerance_mm,'checks':checks,'errors':errors,'control_checks':control_checks,
      'scope':'Rechenweg aus gespeicherten Quellpunkten; keine neue Leitungsortung oder Vermessung.',
      'boundary_graphic_area_m2':abs(area(site['boundary']['points_local_mm']))/1e6,
      'unknown_route_heights':sum(r.get('z_mm') is None for r in site.get('routes',[])),
      'unknown_outer_diameters':sum(r.get('diameter_outer_mm') is None for r in site.get('routes',[]))}


def consistency_report(data,compiled,numerical=None):
    sources=source_integrity(data);systems=system_integrity(data)
    opening=opening_clearance(data,compiled);roof=roof_height_checks(data)
    maps=registration_checks(data.get('site'))
    numerical=audit_compiled(data,compiled) if numerical is None else numerical
    proxies=[s['id'] for p in compiled['parts'] for s in p['solids'] if s['meta'].get('quantity_excluded')]
    logical_errors=[]
    logical_errors.extend({'code':'QUELLREFERENZ','detail':e} for e in sources['errors'])
    logical_errors.extend({'code':'SYSTEMVERWEIS','detail':e} for e in systems['dangling'])
    logical_errors.extend({'code':'DOPPELTES_SYSTEM','detail':e} for e in systems['duplicate_systems'])
    logical_errors.extend({'code':'KARTENTRANSFORMATION','detail':e} for e in maps.get('errors',[]))
    logical_errors.extend({'code':'FIRSTHOEHE','detail':e} for e in roof if e['status']=='HOEHENABWEICHUNG')
    hard_gaps=[
      {'code':'ANSCHLUESSE','open':numerical['collision_count']>0,'count':numerical['collision_count'],
       'note':'Modellierte Materialueberschneidungen; keine stillschweigende Anschlusskorrektur.'},
      {'code':'OEFFNUNGEN','open':opening['blocked_count']>0,'count':opening['blocked_count'],
       'note':'Nicht alle deklarierten Oeffnungen sind im Rechenmodell frei.'},
      {'code':'TRAGWERK','open':not data.get('construction',{}).get('structural_calculation_provided',False),
       'note':'Statik/Tragglieder nicht vollstaendig; keine erfundenen Balken.'},
      {'code':'BESTAND','open':not data.get('construction',{}).get('as_built_verified',False),
       'note':'Dokumentierte Planung ist nicht automatisch gebauter Bestand.'},
      {'code':'LEITUNGSHOEHEN','open':maps.get('unknown_route_heights',0)>0,
       'note':'Z=0-Zeichenprojektion nicht physische Hoehe oder Verlegetiefe.'},
      {'code':'FLACHDACH','open':any(not r.get('as_built_verified',False) for r in data.get('flat_roofs',[])),
       'note':'Vorlaeufige 1-mm-Haut, keine bestaetigte Dachkonstruktion.'},
      {'code':'DOKUMENTVOLLSTAENDIGKEIT','open':not data.get('document_coverage_complete',False),
       'note':'Quelleninventar und verarbeitete Fakten sind keine vollstaendige Transkription aller Planmasse.'}]
    return {'schema':'HAUS_KONSISTENZPRUEFUNG_R06','scope':'Numerischer Bauauftrag und Quelldaten; kein NX-/Bestands-/Statiknachweis.',
      'source_integrity':sources,'system_integrity':systems,'opening_clearance':opening,'roof_heights':roof,
      'map_registration':maps,'logical_errors':logical_errors,'open_gaps':hard_gaps,
      'numerical_collisions':numerical['collision_count'],'proxy_excluded_from_quantities':len(proxies),
      'proxy_ids':proxies,'technical_consistency_confirmed':False,'document_coverage_complete':False,
      'as_built_verified':False,'structural_design_verified':False,'nx_runtime_performed_here':False,
      'status':'DATENFEHLER' if logical_errors else 'DATEN_KONSISTENTER_ABER_TECHNISCH_UNVOLLSTAENDIG'}
