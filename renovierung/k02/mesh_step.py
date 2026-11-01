"""Minimal AP214 faceted BREP interchange. Actual NX support requires a probe."""
import hashlib
import math
from pathlib import Path
from .geometry import validate_mesh, mesh_components


def write_step(path, mesh, name='K02_STUDY'):
    measure=validate_mesh(mesh)
    if not name.isascii() or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in name):
        raise ValueError('STEP name must be an ASCII identifier')
    rows=[]
    def entity(text):
        rows.append('#%d=%s;'%(len(rows)+1,text));return '#'+str(len(rows))
    def real(v):
        text=format(v,'.15g').upper()
        if 'E' in text and '.' not in text:text=text.replace('E','.E')
        if '.' not in text and 'E' not in text:text+='.'
        return text
    def triple(values):return ','.join(real(v) for v in values)
    solids=[]
    for component in mesh_components(mesh):
        points=[entity("CARTESIAN_POINT('',(%s))"%triple(p)) for p in component['vertices']]
        faces=[]
        for face in component['faces']:
            loop=entity("POLY_LOOP('',(%s))"%','.join(points[i] for i in face))
            bound=entity("FACE_OUTER_BOUND('',%s,.T.)"%loop)
            a,b,c=[component['vertices'][i] for i in face]
            u=[b[k]-a[k] for k in range(3)];v=[c[k]-a[k] for k in range(3)]
            normal=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
            norm=math.sqrt(sum(x*x for x in normal));unorm=math.sqrt(sum(x*x for x in u))
            axis=entity("DIRECTION('',(%s))"%triple([x/norm for x in normal]))
            reference=entity("DIRECTION('',(%s))"%triple([x/unorm for x in u]))
            placement=entity("AXIS2_PLACEMENT_3D('',%s,%s,%s)"%(points[face[0]],axis,reference))
            surface=entity("PLANE('',%s)"%placement)
            faces.append(entity("FACE_SURFACE('',(%s),%s,.T.)"%(bound,surface)))
        shell=entity("CLOSED_SHELL('',(%s))"%','.join(faces))
        solids.append(entity("FACETED_BREP('%s',%s)"%(name,shell)))
    length=entity('(LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.))')
    angle=entity('(NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.))')
    solid_angle=entity('(NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT())')
    uncertainty=entity("UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(0.000001),%s,'distance_accuracy_value','numerical topology tolerance')"%length)
    context=entity("(GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((%s)) GLOBAL_UNIT_ASSIGNED_CONTEXT((%s,%s,%s)) REPRESENTATION_CONTEXT('',''))"%(uncertainty,length,angle,solid_angle))
    representation=entity("FACETED_BREP_SHAPE_REPRESENTATION('%s',(%s),%s)"%(name,','.join(solids),context))
    application=entity("APPLICATION_CONTEXT('automotive_design')")
    entity("APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,%s)"%application)
    product_context=entity("PRODUCT_CONTEXT('',%s,'mechanical')"%application)
    product=entity("PRODUCT('%s','%s','',(%s))"%(name,name,product_context))
    formation=entity("PRODUCT_DEFINITION_FORMATION('1','',%s)"%product)
    definition_context=entity("PRODUCT_DEFINITION_CONTEXT('part definition',%s,'design')"%application)
    definition=entity("PRODUCT_DEFINITION('design','',%s,%s)"%(formation,definition_context))
    shape=entity("PRODUCT_DEFINITION_SHAPE('','',%s)"%definition)
    entity('SHAPE_DEFINITION_REPRESENTATION(%s,%s)'%(shape,representation))
    text="ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('K02 concept study'),'2;1');\nFILE_NAME('%s.step','2026-11-01T00:00:00',('K02'),(''),'K02 stdlib','K02','');\nFILE_SCHEMA(('AUTOMOTIVE_DESIGN'));\nENDSEC;\nDATA;\n"%name
    text+='\n'.join(rows)+'\nENDSEC;\nEND-ISO-10303-21;\n'
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='ascii')
    return dict(measure,path=str(path),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),nx_import_verified=False)
