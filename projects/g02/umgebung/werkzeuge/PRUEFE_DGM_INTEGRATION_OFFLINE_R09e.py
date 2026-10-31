# -*- coding: utf-8 -*-
"""Independent DGM source-area check from the REAL unchanged STEP poles.

Offline only: needs numpy, cadquery and OCP. Does NOT measure the user's NX part.
Integrates ||dP/du x dP/dv|| on each bilinear knot cell with Gauss-Legendre rules.
Unlike a whole-face area call, no integration interval crosses a derivative kink.
Does not change any source, NX model or runtime acceptance tolerance.
"""
from pathlib import Path
import argparse
import json
import math
import os
import sys
import numpy as np
import cadquery as cq
from OCP.BRep import BRep_Tool
from OCP.BRepCheck import BRepCheck_Analyzer

BASE=Path(os.path.abspath(__file__)).parents[1]
sys.path.insert(0,str(BASE))
from r09.core import read_json,write_json,sha256


def integrate_cells(points,order):
    a=points[1:,:-1]-points[:-1,:-1]
    b=points[:-1,1:]-points[:-1,:-1]
    c=points[1:,1:]-points[1:,:-1]-points[:-1,1:]+points[:-1,:-1]
    nodes,weights=np.polynomial.legendre.leggauss(order)
    nodes=(nodes+1.0)/2.0;weights=weights/2.0
    areas=np.zeros(a.shape[:2],dtype=float)
    for u,wu in zip(nodes,weights):
        for v,wv in zip(nodes,weights):
            cross=np.cross(a+v*c,b+u*c)
            areas+=wu*wv*np.linalg.norm(cross,axis=-1)
    if not np.isfinite(areas).all() or np.any(areas<=0):
        raise ValueError('Degenerate/nonfinite bilinear source cells.')
    return areas


def run():
    job=read_json(BASE/'data/IMPORTAUFTRAG_R09.json')
    spec=next(p for p in job['parts'] if p['id']=='DGM')
    path=BASE/spec['step_file']
    if sha256(path)!=spec['sha256']:raise ValueError('STEP hash differs from reference.')
    shape=cq.importers.importStep(str(path)).val()
    if not BRepCheck_Analyzer(shape.wrapped).IsValid() or shape.Solids() or len(shape.Faces())!=1:
        raise ValueError('Expected one valid open DGM source face.')
    surface=BRep_Tool.Surface_s(shape.Faces()[0].wrapped)
    if surface.UDegree()!=1 or surface.VDegree()!=1 or surface.IsURational() or surface.IsVRational():
        raise ValueError('This verifier only handles nonrational bilinear knot cells.')
    rows,cols=surface.NbUPoles(),surface.NbVPoles()
    for knots,mults,count in [(surface.UKnots(),surface.UMultiplicities(),rows),
                              (surface.VKnots(),surface.VMultiplicities(),cols)]:
        vs=[float(knots.Value(i)) for i in range(knots.Lower(),knots.Upper()+1)]
        ms=[int(mults.Value(i)) for i in range(mults.Lower(),mults.Upper()+1)]
        if len(vs)!=count or ms!=[2]+[1]*(count-2)+[2] or any(b<=a for a,b in zip(vs,vs[1:])):
            raise ValueError('Unexpected knot multiplicity or nonmonotone knot vector.')
    points=np.array([[[surface.Pole(i+1,j+1).X(),surface.Pole(i+1,j+1).Y(),
                       surface.Pole(i+1,j+1).Z()] for j in range(cols)] for i in range(rows)])
    ref=spec['geometry_reference']['sheets'][0]
    if [rows,cols]!=ref['grid_shape']:raise ValueError('Reference/source grid mismatch.')
    all_reference=np.array(ref['samples_mm'],dtype=float)
    centers=(points[:-1,:-1]+points[1:,:-1]+points[:-1,1:]+points[1:,1:])/4
    all_source=np.vstack((points.reshape(-1,3),centers.reshape(-1,3)))
    err=float(np.max(np.linalg.norm(all_source-all_reference,axis=1)))
    if err>0.002:raise ValueError('Source/reference sample mismatch: '+str(err))
    rules=[]
    for order in (2,4,8,16):
        cell_areas=integrate_cells(points,order)
        area=math.fsum(map(float,cell_areas.ravel()))
        rules.append({'order_per_direction':order,'area_mm2':area,'area_m2':area/1e6,
                      'difference_to_stored_reference_mm2':area-ref['area_mm2']})
    convergence=abs(rules[-1]['area_mm2']-rules[-2]['area_mm2'])
    if convergence>0.1:raise ValueError('8/16-point quadrature total not stable within 0.1 mm2.')
    if abs(rules[-1]['difference_to_stored_reference_mm2'])>0.1:
        raise ValueError('Stored source area differs from independent integral.')
    obs=read_json(BASE/'tests/fixtures/DGM_MESSWERTE_NX_R09d.json')
    low,high=[r['area_mm2'] for r in obs['measurements']]
    return {'patch':'R09e-ADAPTIVE-FLAECHENMESSUNG','status':'DGM_QUELLINTEGRATION_BESTANDEN',
            'source_step':spec['step_file'],'source_sha256':sha256(path),
            'grid_shape':[rows,cols],'bilinear_cells':(rows-1)*(cols-1),
            'all_source_nodes_and_centers_compared':len(all_source),
            'max_sample_reference_error_mm':err,'quadrature':rules,
            'quadrature_8_vs_16_mm2':convergence,
            'uploaded_NX_low_area_m2':low/1e6,'uploaded_NX_high_area_m2':high/1e6,
            'uploaded_NX_pair_delta_m2':abs(high-low)/1e6,
            'uploaded_NX_pair_relative_percent':abs(high-low)/high*100,
            'uploaded_NX_high_to_source_relative_percent':abs(high-ref['area_mm2'])/ref['area_mm2']*100,
            'source_area_changed':False,'CAD_geometry_changed':False,
            'new_NX_measurement_executed':False,
            'scope':'Integral of the unchanged STEP SOURCE; NOT the imported NX geometry. '
                    'Numerical convergence, not a rigorous error bound or terrain survey. '
                    'Only the first two NX values are from the user log; no later NX values exist here.'}


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--report',default='')
    args=ap.parse_args();r=run()
    print(json.dumps(r,ensure_ascii=False,indent=2))
    if args.report:write_json(Path(args.report),r)
