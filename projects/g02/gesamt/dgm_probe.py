# -*- coding: utf-8 -*-
"""Existing G01 short probe, now called automatically after a failed terrain check.
No import, Save, Close or geometry edits in this module. No automatic release.
The calling terrain workflow is responsible for creating and recording its own part.
"""
import hashlib
import json
import math
from pathlib import Path
import time
TOLERANCE_MM = 0.25
MAX_FACES = 8
REFERENCE_SHA256 = 'abb6a336608be52ac362678c77ce005b4c516d26f2380983edd4f8f05b9e96d9'

def xyz_checked(point):
    if not isinstance(point, (list, tuple)) or len(point) != 3:
        raise ValueError('Drei XYZ-Koordinaten erforderlich.')
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in point):
        raise ValueError('Endliche numerische XYZ-Koordinaten erforderlich.')
    return [float(v) for v in point]

def load_reference(path):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != REFERENCE_SHA256:
        raise ValueError('Pruefpunkte-Datei fehlt zum Journal oder wurde geaendert; Paket nicht mischen.')
    ref = json.loads(data.decode('utf-8'))
    if ref.get('schema') != 'G01_DGM_DIAGNOSE_SOURCE_V1':
        raise ValueError('Falsches Referenzschema.')
    for idx in ref['replay_indices'] + ref['focus_indices']:
        xyz_checked(ref['points'][str(idx)])
    box = ref['source_bbox_mm']
    if (len(box) != 6 or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)
            or any(box[j] > box[j+3] for j in range(3))):
        raise ValueError('Ungueltige Quellbox.')
    return ref

def result_record(result, point):
    if not isinstance(result, (list, tuple)) or len(result) != 3:
        raise ValueError('AskMinimumDist: drei Rueckgabefelder erwartet.')
    distance = result[0]
    if type(distance) not in (int, float) or not math.isfinite(distance) or distance < 0:
        raise ValueError('Ungueltiger NX-Abstand.')
    p1, p2 = xyz_checked(result[1]), xyz_checked(result[2])
    query = xyz_checked(point)
    input_error = math.dist(query, p1)
    endpoint_distance = math.dist(p1, p2)
    consistent = input_error <= 0.002 and abs(endpoint_distance-distance) <= max(0.002, 1e-7*distance)
    return {'distance_mm': float(distance), 'returned_input_mm': p1,
            'returned_target_mm': p2,
            'target_minus_query_mm': [p2[j]-query[j] for j in range(3)],
            'input_point_error_mm': input_error,
            'distance_from_endpoints_mm': endpoint_distance,
            'numeric_result_consistent': consistent,
            'within_unchanged_0_25mm': consistent and distance <= TOLERANCE_MM}

def request_plan(reference, body_tag, face_tags):
    tags = list(face_tags)
    if not tags or len(tags) > MAX_FACES or len(set(tags)) != len(tags) or body_tag in tags:
        raise ValueError('Diagnose braucht 1 bis 8 unterschiedliche Face-Tags, getrennt vom Body-Tag.')
    points = reference['points']
    plan = []
    def add(method, tag, index, given2, guess, query=None, off_surface=False):
        p = xyz_checked(query if query is not None else points[str(index)])
        plan.append({'method': method, 'target_tag': int(tag),
                     'source_index_zero_based': index, 'query_mm': p,
                     'guess2_given': given2, 'guess2_mm': xyz_checked(guess),
                     'off_surface_control': off_surface})
    # Reproduce the order of the twelve BODY calls before the reported abort.
    for i in reference['replay_indices']:
        add('BODY_G01_REPLAY', body_tag, i, 0, [0., 0., 0.])
    # Add old one-based point85 (=index84) and neighbours for comparison.
    for i in reference['focus_indices']:
        if i not in reference['replay_indices']:
            add('BODY_G01_FOCUS', body_tag, i, 0, [0., 0., 0.])
    for tag in tags:
        for i in reference['focus_indices']:
            add('FACE_OHNE_STARTPUNKT', tag, i, 0, [0., 0., 0.])
        for i in reference['focus_indices']:
            add('FACE_MIT_STARTPUNKT', tag, i, 1, points[str(i)])
    # Read-only negative control. At least 1000 mm ABOVE the SOURCE bbox.
    # The target point is measured by NX; the guess is never treated as an answer.
    i = reference['known_failure_index_zero_based']
    high = xyz_checked(points[str(i)])
    high[2] = float(reference['source_bbox_mm'][5]) + 1000.
    add('BODY_KONTROLLPUNKT_OBERHALB', body_tag, None, 0, [0., 0., 0.], high, True)
    for tag in tags:
        add('FACE_KONTROLLE_START_BEI_QUERY', tag, None, 1, high, high, True)
        add('FACE_KONTROLLE_START_BEI_QUELLPUNKT', tag, None, 1, points[str(i)], high, True)
    return plan

def summarize(report, reference):
    summaries = []
    for index in reference['focus_indices']:
        rows = [r for r in report['measurements'] if r['source_index_zero_based'] == index
                and not r['off_surface_control']]
        values = [r['distance_mm'] for r in rows if r.get('numeric_result_consistent')]
        summaries.append({'source_index_zero_based': index,
                          'valid_numeric_measurements': len(values),
                          'method_distance_spread_mm': max(values)-min(values) if values else None,
                          'methods': [{k: r.get(k) for k in ('method','target_tag','status','distance_mm',
                                      'returned_target_mm','numeric_result_consistent','nearest_focus_source_index',
                                      'distance_to_nearest_focus_source_mm')} for r in rows]})
    report['comparisons'] = summaries
    report['geometry_release'] = False
    report['production_code_changed'] = False
    report['hint'] = ('Mehrere Methoden werden dokumentiert, nicht nachtraeglich nach dem passendsten '
                      'Wert ausgewaehlt. Kein automatischer Fix und keine Gesamtformfreigabe.')

def run_measurements(modeling, reference, body_tag, face_tags, actual_box, report, checkpoint, log):
    plan = request_plan(reference, body_tag, face_tags)
    report.update(planned_calls=len(plan), completed_calls=0, measurements=[], status='MESSUNGEN_LAUFEN')
    checkpoint(report)
    for request in plan:
        row = dict(request)
        row['status'] = 'AUFRUF_LAEUFT'
        report['measurements'].append(row)
        report['current_operation'] = '%s / Index %s / Tag %s' % (
            row['method'], row['source_index_zero_based'], row['target_tag'])
        checkpoint(report)
        log('%d/%d: %s' % (report['completed_calls']+1, len(plan), report['current_operation']))
        start = time.perf_counter()
        try:
            # Fresh arrays for every argument/call: an in/out binding cannot corrupt the reference.
            result = modeling.AskMinimumDist(0, row['target_tag'], 1, list(row['query_mm']),
                                             row['guess2_given'], list(row['guess2_mm']))
            row.update(result_record(result, row['query_mm']))
            target = row['returned_target_mm']
            nearest = min(reference['focus_indices'],
                          key=lambda i: math.dist(target, reference['points'][str(i)]))
            row['nearest_focus_source_index'] = nearest
            row['distance_to_nearest_focus_source_mm'] = math.dist(target, reference['points'][str(nearest)])
            row['target_inside_actual_body_box'] = all(actual_box[j]-TOLERANCE_MM <= target[j]
                                                       <= actual_box[j+3]+TOLERANCE_MM for j in range(3))
            if row['off_surface_control']:
                lower_bound = row['query_mm'][2] - actual_box[5]
                row['distance_lower_bound_from_actual_box_mm'] = lower_bound
                row['off_surface_control_consistent'] = (row['numeric_result_consistent']
                    and row['distance_mm'] >= lower_bound-TOLERANCE_MM
                    and row['target_inside_actual_body_box'])
            row['status'] = 'MESSUNG_ERFASST'
        except Exception as error:
            row.update(status='MESSUNG_FEHLGESCHLAGEN', error=str(error), exception_type=type(error).__name__)
            try:
                row['nx_error_code'] = int(error.ErrorCode)
            except (AttributeError, ValueError, TypeError):
                pass
        finally:
            row['seconds'] = time.perf_counter()-start
            report['completed_calls'] += 1
            checkpoint(report)
    summarize(report, reference)
    report['measurement_error_count'] = sum(r['status'] != 'MESSUNG_ERFASST'
        or not r.get('numeric_result_consistent',False)
        or (r['off_surface_control'] and not r.get('off_surface_control_consistent',False))
        for r in report['measurements'])
    report['status'] = 'DIAGNOSE_BEENDET' if report['measurement_error_count']==0 else 'DIAGNOSE_BEENDET_MIT_MESSFEHLERN'
    report['current_operation'] = 'NUR_DIAGNOSE_KEINE_GEOMETRIEFREIGABE'
    checkpoint(report)
