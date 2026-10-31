# -*- coding: utf-8 -*-
"""Importgeometrie statt translatorabhaengiger Face-Anzahl pruefen.
Nur Standardbibliothek. Referenzen stammen aus den unveraenderten STEP-Dateien.
Kein mathematisch vollstaendiger Formgleichheits- oder Bestandsnachweis.
"""
import math
from .core import finite_number, check_box

DISTANCE_TOLERANCE_MM = 0.25
AREA_RELATIVE_TOLERANCE = 0.001
AREA_ABSOLUTE_TOLERANCE_MM2 = 1.0


def reference_checked(spec):
    ref = spec.get('geometry_reference')
    if not isinstance(ref, dict) or ref.get('schema') != 'R09B_SURFACE_REFERENCE_V1':
        raise ValueError('Geometrie-Pruefreferenz fehlt/ungueltig: ' + spec['id'])
    if ref.get('source_sha256') != spec['sha256']:
        raise ValueError('Pruefreferenz gehoert nicht zur STEP-Quelle: ' + spec['id'])
    for key, expected in (('distance_tolerance_mm', DISTANCE_TOLERANCE_MM),
                          ('area_relative_tolerance', AREA_RELATIVE_TOLERANCE),
                          ('area_absolute_tolerance_mm2', AREA_ABSOLUTE_TOLERANCE_MM2)):
        if finite_number(ref.get(key), key) != expected:
            raise ValueError('Geaenderte numerische Prueftoleranz: ' + key)
    if type(spec.get('expected_faces')) is not int or spec['expected_faces'] != spec['expected_sheets']:
        raise ValueError('Diese Quelle muss genau eine Quell-Face je Quell-Sheet besitzen.')
    rows = ref.get('sheets')
    if not isinstance(rows, list) or len(rows) != spec['expected_sheets']:
        raise ValueError('Pruefreferenzanzahl widerspricht Quellkoerpern.')
    total = 0
    for i, row in enumerate(rows):
        if type(row.get('source_index')) is not int or row['source_index'] != i:
            raise ValueError('Pruefreferenzindex vertauscht/doppelt.')
        area = finite_number(row.get('area_mm2'), 'Referenzflaeche')
        if area <= 0:
            raise ValueError('Referenzflaeche muss positiv sein.')
        dims = row.get('grid_shape')
        if not isinstance(dims, list) or len(dims) != 2 or any(type(x) is not int or x < 2 for x in dims):
            raise ValueError('Pruefraster ungueltig.')
        points = row.get('samples_mm')
        n = dims[0]*dims[1] + (dims[0]-1)*(dims[1]-1)
        if not isinstance(points, list) or len(points) != n:
            raise ValueError('Quellraster-/Zellmittelpunkte unvollstaendig.')
        box = check_box(spec['face_bounding_boxes_mm'][i])
        for p in points:
            if not isinstance(p, list) or len(p) != 3:
                raise ValueError('Pruefpunkt braucht drei Koordinaten.')
            for d, v in enumerate(p):
                v = finite_number(v, 'Pruefpunkt')
                if v < box[d] - 0.002 or v > box[d+3] + 0.002:
                    raise ValueError('Pruefpunkt liegt ausserhalb seiner Quellbox.')
        total += n
    if type(ref.get('sample_count')) is not int or total != ref['sample_count']:
        raise ValueError('Gesamtzahl der Pruefpunkte widerspruechlich.')
    return ref


def area_checked(expected, actual):
    expected = finite_number(expected, 'Quell-Flaecheninhalt')
    actual = finite_number(actual, 'NX-Flaecheninhalt')
    if expected <= 0 or actual <= 0:
        raise ValueError('Flaecheninhalt muss positiv sein.')
    delta = abs(actual - expected)
    limit = max(AREA_ABSOLUTE_TOLERANCE_MM2, expected * AREA_RELATIVE_TOLERANCE)
    result = {'expected_area_mm2': expected, 'actual_area_mm2': actual,
              'area_error_mm2': delta, 'area_relative_error': delta / expected,
              'area_limit_mm2': limit, 'area_passed': delta <= limit}
    return result


def distance_result_checked(result, point):
    """Python UF Modeling.AskMinimumDist: (min_dist, pt_on_obj1, pt_on_obj2).
    NULL_TAG als erstes Objekt verwendet guess1 als Messpunkt, kein Hilfsobjekt.
    Rueckgabekoordinaten pruefen, damit eine falsche Bindung nicht 0 vortaeuscht.
    """
    if not isinstance(result, (tuple, list)) or len(result) != 3:
        raise RuntimeError('AskMinimumDist-Rueckgabe ungueltig; drei Ergebnisfelder erwartet.')
    d = finite_number(result[0], 'NX-Minimalabstand')
    if d < 0:
        raise RuntimeError('Negativer NX-Minimalabstand.')
    pts = []
    for obj in result[1:]:
        if not isinstance(obj, (list, tuple)) or len(obj) != 3:
            raise RuntimeError('AskMinimumDist ohne gueltige XYZ-Rueckgabepunkte.')
        pts.append([finite_number(x, 'NX-Messpunkt') for x in obj])
    if math.dist(point, pts[0]) > 0.002:
        raise RuntimeError('AskMinimumDist hat einen anderen Eingangspunkt verwendet.')
    if abs(math.dist(pts[0], pts[1]) - d) > max(0.002, 1e-7 * d):
        raise RuntimeError('NX-Abstand und Rueckgabepunkte widersprechen sich.')
    return d
