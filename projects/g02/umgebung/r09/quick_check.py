# -*- coding: utf-8 -*-
"""Bounded BASIC surface inspection. Deliberately weaker than INTENSIV.

No area integration in BASIC. No source value is returned as an NX measurement.
All bodies, dimensions and ownership are checked; a deterministic, spatially
spread subset of ORIGINAL reference nodes/cell midpoints is inspected per body.
CAD input geometry and numerical point tolerance are never changed.
"""
from pathlib import Path
from .core import PATCH, write_json, compare_boxes
from .surface_check import reference_checked, DISTANCE_TOLERANCE_MM
from .area_measure import runtime_information

BASIC_STATUS = 'IMPORT_BASISPRUEFUNG_BESTANDEN_VOLLPRUEFUNG_OFFEN'


def grid_selection(row, axis_count):
    """Reference layout: row-major nodes, then row-major cell centres.
    Include corners, uniformly distributed rows/columns, and height extrema.
    Return source indices, never freshly interpolated/altered input points.
    """
    if type(axis_count) is not int or axis_count < 2:
        raise ValueError('Mindestens zwei Stichproben pro Rasterachse erforderlich.')
    rows, cols = row['grid_shape']
    points = row['samples_mm']
    expected = rows * cols + (rows-1) * (cols-1)
    if len(points) != expected:
        raise ValueError('Referenzraster unvollstaendig.')
    def indices(n, count):
        if n <= count:
            return list(range(n))
        return sorted({round(i*(n-1)/(count-1)) for i in range(count)})
    selected = {r*cols+c for r in indices(rows,axis_count)
                for c in indices(cols,axis_count)}
    # With two nodes per axis there is still at least one cell-centre check.
    centres = max(2, axis_count-1)
    selected.update(rows*cols+r*(cols-1)+c for r in indices(rows-1,centres)
                    for c in indices(cols-1,centres))
    selected.add(min(range(len(points)), key=lambda i: points[i][2]))
    selected.add(max(range(len(points)), key=lambda i: points[i][2]))
    return sorted(selected)


def inspection_plan(spec):
    reference = reference_checked(spec)
    axis_count = 9 if spec['id'] == 'DGM' else 3
    selections = [grid_selection(row, axis_count) for row in reference['sheets']]
    return reference, selections


def verify_basic(adapter, part, spec, out):
    """Reject detected errors, but do not call this a full geometry verification."""
    adapter.ensure_work(part)
    reference, selections = inspection_plan(spec)
    path = Path(out)/('IMPORTPRUEFUNG_'+spec['id']+'_R11a_BASIS.json')
    report = {
        'patch':'R11a-LAUFZEIT', 'id':spec['id'], 'status':'BASISPRUEFUNG_LAEUFT',
        'report_file':str(path), 'source_sha256':spec['sha256'],
        'source_sheets':spec['expected_sheets'], 'source_faces':spec['expected_faces'],
        'validation_level':'BASIS', 'area_check_performed':False,
        'full_reference_check_performed':False,
        'point_tolerance_mm':DISTANCE_TOLERANCE_MM,
        'available_source_points':reference['sample_count'],
        'selected_source_points':sum(map(len,selections)), 'checked_samples':0,
        'scope':'Alle Sheet-Anzahlen/Typen/Boxen und verteilte Originalpunkt-Stichproben. '
                'KEINE Flaechenintegration, KEIN vollstaendiger Quellpunktvergleich. '
                'Schwaechere Pruefung als INTENSIV, keine Bestands-/Formfreigabe.',
        'sheets_checked':[]}
    try:
        bodies=list(part.Bodies)
        if any(b.OwningPart.Tag != part.Tag for b in bodies):
            raise RuntimeError('Importkoerper im falschen Part.')
        if any(b.IsSolidBody for b in bodies):
            raise RuntimeError('Volumenkoerper statt offener Referenzoberflaeche.')
        counts=[len(b.GetFaces()) for b in bodies]
        report.update(nx_sheets=len(bodies),nx_faces=sum(counts),faces_per_sheet_import_order=counts)
        write_json(path, report)
        adapter.operation='BASIS Sheet-/Boxpruefung: '+spec['id']
        boxes=compare_boxes(spec['face_bounding_boxes_mm'],[adapter.surface_box(b) for b in bodies])
        report['box_check']=boxes
        if any(n<=0 for n in counts):
            raise RuntimeError('Importierter Sheet ohne Faces.')
        maximum=0.0
        for source_i, body_i in boxes['mapping']:
            body=bodies[body_i];row=reference['sheets'][source_i]
            selected=selections[source_i]
            checked={'source_index':source_i, 'body_index':body_i,
                     'nx_faces':counts[body_i], 'available_samples':len(row['samples_mm']),
                     'selected_sample_indices':selected, 'checked_samples':0,
                     'area_check_performed':False, 'max_point_distance_mm':0.0}
            report['sheets_checked'].append(checked)
            for idx in selected:
                xyz=row['samples_mm'][idx]
                adapter.operation='BASIS %s Sheet %d/%d Quellpunkt %d' % (
                    spec['id'],source_i+1,len(bodies),idx)
                distance=adapter.surface_distance_mm(body,xyz)
                checked['checked_samples']+=1;report['checked_samples']+=1
                checked['max_point_distance_mm']=max(checked['max_point_distance_mm'],distance)
                maximum=max(maximum,distance)
                if distance>DISTANCE_TOLERANCE_MM:
                    checked.update(failed_sample_index=idx,failed_sample_mm=xyz,failed_distance_mm=distance)
                    raise RuntimeError('BASIS-Quellpunktabweichung %s Sheet %d: %.6f mm > %.3f mm' % (
                        spec['id'],source_i+1,distance,DISTANCE_TOLERANCE_MM))
            if (source_i+1)%10==0:
                write_json(path,report)
        if report['checked_samples'] != report['selected_source_points']:
            raise RuntimeError('BASIS: Nicht alle ausgewaehlten Punkte geprueft.')
        changed=sum(counts)!=spec['expected_faces']
        report.update(status=BASIC_STATUS,max_point_distance_mm=maximum,face_count_changed=changed)
        if changed:
            warning=('BASIS %s: Einzelflaechenunterteilung %d -> %d. Sheetzahl/Boxen und '
                     'Punkt-Stichproben bestanden; Flaecheninhalt und Vollvergleich NICHT geprueft.' % (
                         spec['id'],spec['expected_faces'],sum(counts)))
            adapter.warnings.append(warning);adapter.log(warning)
        write_json(path,report)
        boxes.update(faces=sum(counts),face_count_changed=changed,source_faces=spec['expected_faces'],
            geometry_report=str(path),checked_source_points=report['checked_samples'],
            available_source_points=reference['sample_count'],max_point_distance_mm=maximum,
            geometry_validation_status=BASIC_STATUS,validation_level='BASIS',
            area_check_performed=False,full_reference_check_performed=False,
            faces_per_sheet_import_order=counts)
        return boxes
    except Exception as error:
        report.update(status='BASISPRUEFUNG_ABGEBROCHEN',error=str(error),operation=adapter.operation)
        try:write_json(path,report)
        except Exception as log_error:report['diagnostic_write_error']=str(log_error)
        error.nx_surface_check={k:report[k] for k in (
            'id','report_file','status','source_sheets','source_faces','nx_sheets','nx_faces',
            'error','operation','validation_level') if k in report}
        if report['sheets_checked']:
            error.nx_surface_check['last_sheet']=report['sheets_checked'][-1]
        error.nx_runtime=runtime_information(adapter)
        raise
