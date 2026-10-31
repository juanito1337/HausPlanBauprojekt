# -*- coding: utf-8 -*-
"""Quellengebundene Grundstücks-/Trassenreferenzen und getrennte Flachdachhaut.

KEINE angenommenen Leitungstiefen, keine DN->Außendurchmesser-Umrechnung.
Die Zeichenhöhe einer Planprojektion ist grundsätzlich kein Bestands-Z-Wert.
Nur Standardbibliothek; NX-Erzeugung nutzt vorhandene Linien/Extrusionswege.
"""
import copy
import math
from .haus_geometry import area, clean, pieces, remove_overlaps

NETWORK_PARTS = (
    ('GAS', 'GAS_PLAN', '07A_GAS_PLANPROJEKTION.prt'),
    ('STROM', 'STROM_PLAN', '07B_STROM_PLANPROJEKTION.prt'),
    ('TELEFON', 'TELEFON_PLAN', '07C_TELEFON_PLANPROJEKTION.prt'),
    ('BREITBAND', 'BREITBAND_PLAN', '07D_BREITBAND_PLANPROJEKTION.prt'),
)


def finite_number(v, label):
    if isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v):
        raise ValueError('Keine endliche Zahl: ' + label)
    return float(v)


def validate_line(item, closed=False):
    ident = item.get('id', '<ohne ID>')
    if not isinstance(ident, str) or not ident.strip():
        raise ValueError('Leere Referenz-ID.')
    points = item.get('points_local_mm')
    if not isinstance(points, list) or len(points) < (3 if closed else 2):
        raise ValueError('Zu wenige Referenzpunkte: ' + ident)
    for i, p in enumerate(points):
        if not isinstance(p, list) or len(p) != 2:
            raise ValueError('XY-Punkt erforderlich: ' + ident)
        for v in p: finite_number(v, ident)
    pairs = list(zip(points, points[1:]))
    if closed: pairs.append((points[-1], points[0]))
    for a, b in pairs:
        if math.dist(a, b) <= 0.01:
            raise ValueError('Nullsegment/duplizierter Endpunkt: ' + ident)
    if closed:
        if abs(area(points)) < 1:
            raise ValueError('Grenzpolygon ohne Flaeche: ' + ident)
        # Existing triangulator rejects non-simple polygons, not silently repairs them.
        fragments = pieces(points)
        if abs(sum(abs(area(p)) for p in fragments) - abs(area(points))) > 1.0:
            raise ValueError('Grenzpolygon nicht konsistent zerlegbar: ' + ident)
    z = item.get('z_mm')
    if z is not None:
        if not isinstance(z, list) or len(z) != len(points):
            raise ValueError('Echte Hoehen benoetigen einen Z-Wert pro XY-Punkt: ' + ident)
        for v in z: finite_number(v, ident + ' Z')
        if not item.get('height_sources') or not item.get('height_datum'):
            raise ValueError('Hoehenbezug/Quelle fuer echte 3D-Lage fehlt: ' + ident)
        if item.get('z_coordinate_system') != 'MODELL_Z_MM_EG0':
            raise ValueError('Z-Werte muessen in Modell-mm relativ zum EG-Bezug umgerechnet sein: ' + ident)
    if item.get('physical_pipe_model'):
        raise ValueError('Rohrkoerper sind hier nicht implementiert; Trassenachse nicht als Rohr ausgeben: ' + ident)
    return len(pairs)


def line_definition(item, site, category):
    """Build display coordinates but preserve unknown physical height in metadata."""
    result = copy.deepcopy(item)
    closed = bool(item.get('closed', False))
    validate_line(item, closed)
    z = item.get('z_mm')
    display_z = finite_number(site.get('display_plane_z_mm', 0), 'Zeichenebene')
    result['points3d'] = [[p[0], p[1], z[i] if z is not None else display_z]
                          for i, p in enumerate(item['points_local_mm'])]
    result['closed'] = closed
    result['category'] = category
    result['vertical_status'] = 'QUELLENBEZOGENE_Z_WERTE' if z is not None else 'UNGEKLAERT_KEINE_VERLEGETIEFE'
    result['representation'] = '3D_TRASSENACHSE' if z is not None else 'PLANPROJEKTION_KEINE_PHYSISCHE_HOEHE'
    result['display_plane_z_mm'] = display_z if z is None else None
    result['material'] = ''
    result['physical_pipe_model'] = False
    result['note'] = (item.get('note', '') + ' | Zeichenebene Z=%g mm ist nur eine Projektion, KEINE Verlegetiefe.' % display_z
                      if z is None else item.get('note', ''))
    return result


def audit_site(site):
    if not site or not site.get('enabled'):
        return {'enabled': False, 'curve_segments': 0, 'route_count': 0}
    if site.get('schema') != 'HAUS_SITE_V1': raise ValueError('Unbekanntes Grundstuecksformat.')
    finite_number(site.get('display_plane_z_mm'), 'Zeichenebene')
    ids = set()
    boundary = site['boundary']
    if not boundary.get('closed'): raise ValueError('Grundstuecksgrenze muss geschlossen sein.')
    objects = [boundary, site['cadastral_house']] + site.get('routes', [])
    count = 0
    for obj in objects:
        if obj['id'] in ids: raise ValueError('Doppelte Grundstuecks-/Leitungs-ID: ' + obj['id'])
        ids.add(obj['id'])
        count += validate_line(obj, bool(obj.get('closed')))
    for reg in site.get('registrations', []):
        m = reg.get('matrix_2x3')
        if not isinstance(m, list) or len(m) != 2 or any(len(r) != 3 for r in m):
            raise ValueError('Ungueltige Quellen-Transformationsmatrix.')
        for row in m:
            for v in row: finite_number(v, 'Registrierung')
        if abs(m[0][0]*m[1][1]-m[0][1]*m[1][0]) < 1e-10:
            raise ValueError('Singulaere Quellen-Transformationsmatrix.')
    for route in site.get('routes', []):
        if route.get('network') not in ('GAS', 'GAS_TRANSPORT', 'STROM', 'TELEFON', 'BREITBAND'):
            raise ValueError('Unbekannte Leitungssparte: ' + route['id'])
        if not route.get('sources'): raise ValueError('Leitungsquelle fehlt: ' + route['id'])
    return {'enabled': True, 'route_count': len(site.get('routes', [])),
            'boundary_segments': len(boundary['points_local_mm']),
            'cadastral_house_segments': len(site['cadastral_house']['points_local_mm']),
            'route_segments': sum(len(r['points_local_mm'])-1 for r in site.get('routes', [])),
            'curve_segments': count, 'reference_only': True, 'physical_pipe_solids': 0,
            'routes_with_sourced_z': sum(r.get('z_mm') is not None for r in site.get('routes', [])),
            'excavation_clearance': False, 'survey_verified': site.get('survey_verified', False),
            'max_house_control_residual_mm': site['coordinate_reference']['max_house_control_residual_mm'],
            'missing_networks': site.get('unavailable_networks', []),
            'warnings': site.get('warnings', [])}


def apply_site(data, compiled):
    site = data.get('site')
    compiled['site_audit'] = audit_site(site)
    if not compiled['site_audit']['enabled']: return
    parts = []
    refs = [line_definition(site['boundary'], site, 'GRUNDSTUECKSGRENZE_KARTENREFERENZ'),
            line_definition(site['cadastral_house'], site, 'KATASTERHAUS_KONTROLLKONTUR')]
    parts.append({'id': 'GRUNDSTUECK', 'file': '06_GRUNDSTUECK_KARTENBEZUG.prt',
                  'solids': [], 'references': refs, 'force_reference_display': True})
    for network, ident, filename in NETWORK_PARTS:
        routes = [r for r in site['routes'] if r['network'] == network or
                  (network == 'GAS' and r['network'] == 'GAS_TRANSPORT')]
        if not routes: continue
        parts.append({'id': ident, 'file': filename, 'solids': [],
                      'references': [line_definition(r, site, 'LEITUNG_PLANREFERENZ') for r in routes],
                      'force_reference_display': True})
    existing_ids = {p['id'] for p in compiled['parts']}
    existing_files = {p['file'].lower() for p in compiled['parts']}
    for part in parts:
        if part['id'] in existing_ids or part['file'].lower() in existing_files:
            raise ValueError('Grundstuecks-Komponente bereits vorhanden: ' + part['id'])
        compiled['parts'].append(part)
        for ref in part['references']:
            compiled['coverage'].append({'id': ref['id'], 'part': part['id'], 'kind': ref['category'],
                'status': 'QUELLENREFERENZ_KEIN_LEITUNGSROHR', 'planned_solids': 0,
                'note': ref['representation'] + '; ' + ref.get('source_label', '')})
    compiled['warnings'].extend(site['warnings'])


def apply_flat_roofs(data, compiled, params, allow_estimates):
    roofs = data.get('flat_roofs', [])
    if not roofs: return
    part = {'id': 'FLACHDACH', 'file': '05B_FLACHDACH_ANBAU_REFERENZ.prt', 'solids': [], 'references': []}
    for roof in roofs:
        if not roof.get('enabled'): continue
        if roof.get('representation') != 'REFERENZHAUT_KEIN_DACHBAUSTOFF':
            raise ValueError('Ungepruefter physischer Flachdachaufbau: ' + roof['id'])
        if roof.get('physical_layers'):
            raise ValueError('Physische Dachschichten brauchen separaten freigegebenen Generator.')
        if not allow_estimates:
            compiled['coverage'].append({'id': roof['id'], 'part': part['id'], 'kind': 'FLACHDACH_REFERENZ',
                'status': 'NAEHERUNG_GESPERRT', 'planned_solids': 0,
                'note': 'Dachhaut hat noch keine bestaetigten Hoehen-/Aufbaudaten.'})
            continue
        thickness = params.number(roof['display_thickness']); z = params.number(roof['z'])
        if thickness <= 0 or thickness > 1.0:
            raise ValueError('Flachdach-Referenzhaut darf nicht als reale Dachdicke erscheinen.')
        fragments = pieces(roof['polygon'])
        if roof.get('exclude_existing_roof_projection'):
            for face in compiled['roof_faces']:
                fragments = remove_overlaps(fragments, pieces(face['polygon']))
        fragments = [clean(f) for f in fragments if abs(area(f)) > 0.1]
        for i, poly in enumerate(fragments):
            meta = dict(roof, category='FLACHDACH_REFERENZ', quantity_excluded=True,
                        construction_status='HOEHE_GRENZE_GEFALLE_AUFBAU_UNBESTAETIGT')
            part['solids'].append({'id': roof['id'] + '_S%03d' % (i+1), 'parent': roof['id'],
                'kind': 'FLACHDACH_REFERENZ', 'polygon': poly, 'bottom': '(' + roof['z'] + ')-(' + roof['display_thickness'] + ')',
                'top': roof['z'], 'meta': meta})
        compiled['coverage'].append({'id': roof['id'], 'part': part['id'], 'kind': 'FLACHDACH_REFERENZ',
            'status': 'GEPLANT_NAEHERUNG', 'planned_solids': len(fragments),
            'note': '1-mm-Anzeigehaut. Kein realer Baustoff, Gefaelle oder Tragwerk; Dachzuordnung am Zwischenanbau vorlaeufig.'})
    if part['solids']:
        if any(p['id'] == part['id'] or p['file'].lower() == part['file'].lower() for p in compiled['parts']):
            raise ValueError('Flachdach-Komponente doppelt.')
        compiled['parts'].append(part)
    compiled['flat_roof_audit'] = {'display_solids': len(part['solids']),
        'reference_area_m2': sum(abs(area(s['polygon'])) for s in part['solids']) / 1e6,
        'physical_roof_materials': 0, 'construction_verified': False,
        'location_assignment': 'HOFSEITIGER_ZWISCHENANBAU_VORLAEUFIG',
        'warning': 'Ehemalige Schwimmhalle behaelt dokumentiertes geneigtes Binderdach; dieses wird nicht ersetzt.'}
