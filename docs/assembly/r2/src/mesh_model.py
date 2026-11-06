#!/usr/bin/env python3
"""Tessellate native TACO STEP + the R2 analytic scene. Requires OCCT 8.

uv run --python 3.12 --with cadquery-ocp-novtk==8.0.1.1.0 python mesh_model.py
Inputs/outputs resolve from this file, independent of the current directory.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
from math import pi
from pathlib import Path

from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace, BRepBuilderAPI_Transform
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism, BRepPrimAPI_MakeRevol
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_SOLID, TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.TopLoc import TopLoc_Location
from OCP.gp import gp_Pnt, gp_Vec, gp_Ax1, gp_Dir, gp_Trsf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
WORK = ROOT / 'work/assembly-r2'


def at(frame, s, u=0., v=0.):
    return [frame['o'][i] + frame['a'][i]*s + frame['u'][i]*u + frame['v'][i]*v for i in range(3)]


def wire(points):
    builder = BRepBuilderAPI_MakePolygon()
    for point in points:
        builder.Add(gp_Pnt(*point))
    builder.Close()
    return builder.Wire()


def shape_of(spec):
    frame = spec['F']
    if spec['kind'] == 'prism':
        poly = spec['poly']
        signed = sum(p[0]*poly[(i+1)%len(poly)][1] - p[1]*poly[(i+1)%len(poly)][0] for i,p in enumerate(poly))
        if signed < 0:
            poly = list(reversed(poly))
        face = BRepBuilderAPI_MakeFace(wire([at(frame,spec['s0'],*p) for p in poly]))
        for cut in spec.get('cut', []):
            ring = cut['poly']
            signed = sum(p[0]*ring[(i+1)%len(ring)][1] - p[1]*ring[(i+1)%len(ring)][0] for i,p in enumerate(ring))
            if signed > 0:
                ring = list(reversed(ring))
            face.Add(wire([at(frame,spec['s0'],*p) for p in ring]))
        length = spec['s1'] - spec['s0']
        return BRepPrimAPI_MakePrism(face.Face(),gp_Vec(*[n*length for n in frame['a']])).Shape()
    if spec['kind'] == 'body':
        poly = spec['poly']
        # Axis-end duplicate points in a solid profile must not make null edges.
        points = []
        for s,r in poly:
            point = at(frame,s,r)
            if not points or sum((a-b)**2 for a,b in zip(point,points[-1])) > 1e-12:
                points.append(point)
        face = BRepBuilderAPI_MakeFace(wire(points)).Face()
        return BRepPrimAPI_MakeRevol(face,gp_Ax1(gp_Pnt(*frame['o']),gp_Dir(*frame['a'])),2*pi).Shape()
    raise ValueError(spec['kind'])


def bounds(shape):
    b = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape,b)
    p,q = b.CornerMin(),b.CornerMax()
    return [p.X(),p.Y(),p.Z(),q.X(),q.Y(),q.Z()]


def triangles(shape):
    BRepMesh_IncrementalMesh(shape,.09,False,.3,True).Perform()
    vertices,faces = [],[]
    ex = TopExp_Explorer(shape,TopAbs_FACE)
    while ex.More():
        face = TopoDS.Face(ex.Current())
        loc = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation_s(face,loc)
        if triangulation is not None:
            transform = loc.Transformation()
            offset = len(vertices)
            for i in range(1,triangulation.NbNodes()+1):
                point = triangulation.Node(i).Transformed(transform)
                vertices.append([round(point.X(),5),round(point.Y(),5),round(point.Z(),5)])
            for i in range(1,triangulation.NbTriangles()+1):
                a,b,c = triangulation.Triangle(i).Get()
                if face.Orientation() == TopAbs_REVERSED:
                    b,c = c,b
                faces.append([offset+a-1,offset+b-1,offset+c-1])
        ex.Next()
    return vertices,faces


def append_mesh(target,shape):
    vertices,faces = triangles(shape)
    offset = len(target['vertices'])
    target['vertices'].extend(vertices)
    target['faces'].extend([[a+offset,b+offset,c+offset] for a,b,c in faces])


def main():
    data = json.loads((WORK/'analytic.json').read_text())
    meshes = {}
    invalid = []
    def bucket(part,material):
        key = part+'__'+material
        if key not in meshes:
            meshes[key] = dict(name=key,part=part,material=material,vertices=[],faces=[])
        return meshes[key]
    for part in data['parts']:
        for index,item in enumerate(part['shapes']):
            shape = shape_of(item['shape'])
            if not BRepCheck_Analyzer(shape).IsValid():
                invalid.append(f"{part['id']}/{index}")
            append_mesh(bucket(part['id'],item['material']),shape)
    if invalid:
        raise RuntimeError('Invalid analytic geometry: '+', '.join(invalid))
    print('R2 analytic geometry valid:',sum(len(p['shapes']) for p in data['parts']),flush=True)
    reader = STEPControl_Reader()
    source = ROOT/'references/radxa-taco/radxa_taco_3d_stp_v1.61.stp'
    if int(reader.ReadFile(str(source))) != 1:
        raise RuntimeError('STEP read failed')
    reader.TransferRoots()
    t = gp_Trsf()
    t.SetRotation(gp_Ax1(gp_Pnt(0,0,0),gp_Dir(0,1,0)),pi)
    t.SetTranslationPart(gp_Vec(72.1,120,135))
    shape = BRepBuilderAPI_Transform(reader.OneShape(),t,True).Shape()
    ex = TopExp_Explorer(shape,TopAbs_SOLID)
    native = []
    while ex.More():
        solid = ex.Current()
        b = bounds(solid)
        i = len(native)
        d = [b[j+3]-b[j] for j in range(3)]
        material = ('pcb' if i==0 else 'metal' if b[1]<54.5 and d[0]>6 and d[1]>5 else
                    'plastic' if i in [691,692,693,694,695,697,706,707] else
                    'metal' if max(d)<3 else 'chip')
        append_mesh(bucket('taco',material),solid)
        native.append({'index':i,'bounds':[round(x,5) for x in b]})
        ex.Next()
    print('Native STEP solids:',len(native),flush=True)
    report={'sourceSha256':sha256(source.read_bytes()).hexdigest(),'nativeSolids':len(native),
            'analyticParts':len(data['parts']),'analyticShapes':sum(len(p['shapes']) for p in data['parts']),
            'invalidAnalyticShapes':invalid,'triangles':sum(len(m['faces']) for m in meshes.values()),
            'nativeBounds':native,'meshes':len(meshes),
            'supplementalEKey':'U33 placement-map envelope; connector height and antenna geometry are schematic.'}
    (WORK/'meshes.json').write_text(json.dumps(list(meshes.values()),separators=(',',':')))
    (WORK/'meshing-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Meshes:',len(meshes),'triangles:',report['triangles'],flush=True)


if __name__ == '__main__':
    main()
