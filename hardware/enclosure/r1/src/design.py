#!/usr/bin/env python3
"""CyberMachine five-drive NAS enclosure for Radxa Taco V1.61. Dimensions in millimetres.

Requires Python 3.12+, cadquery-ocp-novtk 8.0.1.1.0, numpy, trimesh.
Run with the supplied board reference: python design.py --board-step PATH
The repository root is the default workspace; --root overrides it.
The original Taco STEP is read-only. Printed parts are native analytic B-reps.
"""
import argparse, json, math
from pathlib import Path
from OCP.gp import gp_Pnt, gp_Dir, gp_Ax1, gp_Ax2, gp_Trsf, gp_Vec
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse, BRepAlgoAPI_Cut, BRepAlgoAPI_Common
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Shape, TopoDS_Compound
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepTools import BRepTools
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.StlAPI import StlAPI_Writer
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs, STEPControl_Reader
from OCP.Interface import Interface_Static
from OCP.collections import List_TopoDS_Shape as TopTools_ListOfShape

W,D,H = 144.,168.,210.
SATA_X = [29.,50.5,72.,93.5,115.]
BOARD_HOLES = [(20.1,60.2),(12.9,116.95),(105.,60.2),(119.45,116.9)]
FAN_TOP = (68.,91.)
REPO_ROOT = Path(__file__).resolve().parents[4]
ROOT = None
PARTS = []

def box(x,y,z,dx,dy,dz):
    return BRepPrimAPI_MakeBox(gp_Pnt(x,y,z),dx,dy,dz).Shape()

def cylinder(p,r,h,axis=(0,0,1)):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*p),gp_Dir(*axis)),r,h).Shape()

def compound(shapes):
    c=TopoDS_Compound(); b=BRep_Builder(); b.MakeCompound(c)
    for s in shapes: b.Add(c,s)
    return c

def fuse(shapes):
    s=shapes[0]
    for t in shapes[1:]:
        op=BRepAlgoAPI_Fuse(s,t); op.SimplifyResult(); s=op.Shape()
    return s

def cut(s,tools):
    if not tools: return s
    args=TopTools_ListOfShape(); args.Append(s)
    ts=TopTools_ListOfShape()
    for t in tools: ts.Append(t)
    op=BRepAlgoAPI_Cut(); op.SetArguments(args); op.SetTools(ts); op.Build(); op.SimplifyResult()
    if not op.IsDone(): raise RuntimeError('Boolean cut failed')
    return op.Shape()

def common(s,t): return BRepAlgoAPI_Common(s,t).Shape()

def bounds(s):
    b=Bnd_Box(); BRepBndLib.AddOptimal_s(s,b)
    p,q=b.CornerMin(),b.CornerMax()
    return [p.X(),p.Y(),p.Z(),q.X(),q.Y(),q.Z()]

def volume(s):
    g=GProp_GProps(); BRepGProp.VolumeProperties_s(s,g); return g.Mass()

def transform(s,axis=None,angle=0,move=(0,0,0)):
    t=gp_Trsf()
    if axis: t.SetRotation(gp_Ax1(gp_Pnt(0,0,0),gp_Dir(*axis)),angle)
    t.SetTranslationPart(gp_Vec(*move))
    return BRepBuilderAPI_Transform(s,t,True).Shape()

def rr(x,y,z,dx,dy,dz,r=3):
    """Rounded rectangle in XY, extruded Z."""
    r=min(r,dx/2-.001,dy/2-.001)
    return fuse([box(x+r,y,z,dx-2*r,dy,dz),box(x,y+r,z,dx,dy-2*r,dz)] +
                [cylinder((a,b,z),r,dz) for a in [x+r,x+dx-r] for b in [y+r,y+dy-r]])

def slot_xy(cx,cy,z,length,width,height):
    r=width/2; q=(length-width)/2
    if q<.0001: return cylinder((cx,cy,z),r,height)
    return fuse([box(cx-q,cy-r,z,2*q,width,height),cylinder((cx-q,cy,z),r,height),cylinder((cx+q,cy,z),r,height)])

def slot_xz(cx,cz,y,length,width,depth):
    return transform(slot_xy(cx,cz,0,length,width,depth),axis=(1,0,0),angle=math.pi/2,move=(0,y+depth,0))

def slot_yz(cy,cz,x,length,width,depth):
    # local X is global Y, local Y is global Z, local Z is global X
    s=slot_xy(cy,cz,0,length,width,depth)
    return transform(s,axis=(1,1,1),angle=2*math.pi/3,move=(x,0,0))

def heat(p,axis):
    # M3 heat-set insert: 4.6 OD x 4 length; 4.1 pilot x 4.8 depth.
    return [cylinder(p,2.05,4.8,axis),cylinder(p,1.6,7.5,axis)]

def mesh(s,path):
    BRepMesh_IncrementalMesh(s,.05,False,.25,True).Perform()
    w=StlAPI_Writer(); w.ASCIIMode=False
    if not w.Write(s,str(path)): raise RuntimeError('STL export failed '+str(path))

def add(name,s,orientation='xy',group='shell',color=(.16,.19,.23)):
    valid=BRepCheck_Analyzer(s).IsValid()
    ex=TopExp_Explorer(s,TopAbs_SOLID); count=0
    failed_solids=[]
    while ex.More():
        failed_solids.append((bounds(ex.Current()),volume(ex.Current())))
        count+=1; ex.Next()
    if count!=1: print('DISCONNECTED',name,failed_solids,flush=True)
    if not valid or count!=1: raise RuntimeError(f'{name}: valid={valid}, solids={count}')
    b=bounds(s)
    if orientation=='yz': pr=transform(s,axis=(0,1,0),angle=-math.pi/2)
    elif orientation=='yz_flip': pr=transform(s,axis=(0,1,0),angle=math.pi/2)
    elif orientation=='xz': pr=transform(s,axis=(1,0,0),angle=math.pi/2)
    elif orientation=='xz_flip': pr=transform(s,axis=(1,0,0),angle=-math.pi/2)
    elif orientation=='flip': pr=transform(s,axis=(1,0,0),angle=math.pi)
    else: pr=s
    pb=bounds(pr); pr=transform(pr,move=(-pb[0],-pb[1],-pb[2])); pb=bounds(pr)
    BRepTools.Write_s(s,str(ROOT/'work/parts'/f'{name}.brep'))
    mesh(s,ROOT/'work/meshes'/f'{name}.stl')
    mesh(pr,ROOT/'work/print_meshes'/f'{name}.stl')
    meta=dict(name=name,bounds=[round(v,4) for v in b],print_size=[round(pb[i+3]-pb[i],4) for i in range(3)],
              volume_mm3=round(volume(s),3),orientation=orientation,group=group,color=color)
    PARTS.append((meta,s,pr)); print('PART',name,meta['print_size'],flush=True)

def build_base():
    s=box(3,3,0,138,162,8)
    s=cut(s,[box(18,18,-1,108,132,10),box(10,10,-1,124,148,4.5)])
    # Rear air dam blocks the direct bypass underneath the HDD bodies.
    s=fuse([s,box(12,123,3.5,120,3,18.5)])
    for y in [46,106.85]:
        s=fuse([s]+[cylinder((x,y,3.5),4.5,14.5) for x in [10,134]])
    tools=[]
    for x in [14,130]:
        for y in [14,154]: tools+=heat((x,y,3.5),(0,0,1))
    for x in [10,134]:
        for y in [46,106.85]: tools+=heat((x,y,18),(0,0,-1))
    for x in [7,137]:
        for y in [7,161]: tools+=heat((x,y,0),(0,0,1))
    # Side panel screw pockets.
    for x,axis in [(3,(1,0,0)),(141,(-1,0,0))]:
        for y in [22,146]: tools+=heat((x,y,4),(axis))
    add('01_base_frame',cut(s,tools),group='frame')
    s=rr(10.3,10.3,.2,123.4,147.4,3.1,2)
    add('02_service_hatch',cut(s,[cylinder((x,y,-1),1.7,6) for x in [14,130] for y in [14,154]]))

def build_sides():
    side_positions=[(0,'03_left_side'),(141,'04_right_side')]
    side_screws=[(22,4),(146,4),(7,16),(7,120),(161,16),(161,120),(161,184),(37.5,128),(37.5,198),(46,122.4),(132,122.4)]
    for x,name in side_positions:
        s=box(x,0,0,3,168,207)
        bx=3 if x==0 else 133
        s=fuse([s]+[box(bx,y,199,8,8,8) for y in [3,157]])
        tools=[cylinder((x-1,y,z),1.7,5,(1,0,0)) for y,z in side_screws]
        if x==0: tools.append(box(-1,75.2,133.2,5,18,7.2))
        for y in [7,161]: tools+=heat((7 if x==0 else 137,y,207),(0,0,-1))
        # Upper chamber only; 5 mm wide slots with round ends.
        for z in [149,158,167,176,185,194]:
            for y in [54,77,100,123,146]: tools.append(slot_yz(y,z,x-1,17,5,5))
        add(name,cut(s,tools),'yz' if x==0 else 'yz_flip')

def grill_flat(size,pitch,aperture):
    s=rr(-size/2,-size/2,0,size,size,2,5)
    tools=[cylinder((x,y,-1),2.25,4) for x in [-pitch/2,pitch/2] for y in [-pitch/2,pitch/2]]
    rad=aperture/2-1
    for y in range(-int(rad)+7,int(rad),11):
        chord=2*math.sqrt(max(0,rad*rad-(abs(y)+4)**2))
        if chord>14: tools.append(slot_xy(0,y,-1,chord,7.8,4))
    return cut(s,tools)

def build_fan_panels():
    for name,y,height in [('05_front_fan_panel',0,132),('06_rear_fan_panel',165,207)]:
        s=box(3,y,0,138,3,height)
        z_boss=[16,120]+([184] if y else [])
        by=3 if y==0 else 157
        s=fuse([s]+[box(x,by,z-7,8,8,14) for x in [3,133] for z in z_boss])
        tools=[cylinder((72,y-1,68),57,5,(0,1,0))]
        tools += [cylinder((x,y-1,z),2.25,5,(0,1,0)) for x in [19.5,124.5] for z in [15.5,120.5]]
        for x,axis in [(3,(1,0,0)),(141,(-1,0,0))]:
            for z in z_boss: tools+=heat((x,by+4,z),axis)
        if y:
            for z in [149,158,167,176,185,194]:
                for x in [25,48,71,94,117]: tools.append(slot_xz(x,z,y-1,17,5,5))
        add(name,cut(s,tools),'xz' if y==0 else 'xz_flip')
    g=grill_flat(120,105,114)
    add('07_front_guard',transform(g,axis=(1,0,0),angle=math.pi/2,move=(72,5,68)),'xz','guard')
    add('08_rear_guard',transform(g,axis=(1,0,0),angle=math.pi/2,move=(72,165,68)),'xz','guard')

def build_io_lid():
    s=box(3,30.5,124,138,3,83)
    s=fuse([s]+[box(x,33.5,z-7,6,8,14) for x in [3,135] for z in [128,198]])
    tools=[]
    # Full connector body bounds from the supplied STEP, with access clearance.
    for x0,x1,z0,z1 in [(10.65,26.88,131.05,148.35),(31.65,47.88,131.05,148.35),
                        (51.04,66.71,131.802,150.5)]:
        tools.append(box(x0-.8,29,z0-.8,x1-x0+1.6,6,z1-z0+1.6))
    # Shared HDMI/USB-C window accepts moulded cable boots in the recessed bay.
    tools += [box(69.8,29,130.2,29.4,6,13),box(105.5,29,130.2,14,6,17.2)]
    for x,axis in [(3,(1,0,0)),(141,(-1,0,0))]:
        for z in [128,198]: tools+=heat((x,37.5,z),axis)
    add('09_recessed_IO_panel',cut(s,tools),'xz')
    s=box(0,0,207,144,168,3)
    tools=[cylinder((FAN_TOP[0],FAN_TOP[1],206),43,5)]
    tools += [cylinder((x,y,206),1.7,5) for x in [7,137] for y in [7,161]]
    tools += [cylinder((FAN_TOP[0]+x,FAN_TOP[1]+y,206),2.25,5) for x in [-41.25,41.25] for y in [-41.25,41.25]]
    add('10_top_lid',cut(s,tools))
    add('11_top_guard',transform(grill_flat(92,82.5,86),move=(FAN_TOP[0],FAN_TOP[1],205)),group='guard')

def build_saddle():
    s=box(6,34,124.4,132,102,3)
    # Five through windows leave structural ribs between the drive planes.
    tools=[box(x-4.5,39,123.4,13.1,74.8,5) for x in SATA_X]
    # Extra ventilation away from the original board's underside components.
    tools += [box(27,120,123.4,67,10,5),box(5,33,123.4,4.5,9,5),box(134.5,33,123.4,4.5,9,5)]
    s=cut(s,tools)
    s=fuse([s]+[box(x,y-4,117.4,12,8,10) for x in [3,129] for y in [46,132]])
    tools=[cylinder((x,y,123),1.4,6) for x,y in BOARD_HOLES]
    tools += [box(128.5,y-3.5,123.4,3,7,5) for y in [60,105]]
    for x,axis in [(3,(1,0,0)),(141,(-1,0,0))]:
        for y in [46,132]: tools+=heat((x,y,122.4),axis)
    add('12_motherboard_saddle',cut(s,tools),'flip','frame',(.24,.30,.34))

def build_guides():
    for rear,name in [(False,'13_front_drive_guide'),(True,'14_rear_drive_guide')]:
        web_y=111.75 if rear else 39.5
        side_y=108.75 if rear else 41.1
        mount_y=106.85 if rear else 46
        base_y=105.75 if rear else 39.5
        s=box(6,web_y,8,132,1.6,4)
        shapes=[s,box(6,web_y,110,132,1.6,4),box(6,web_y,8,10,1.6,14),box(128,web_y,8,10,1.6,14)]
        for x in SATA_X:
            left=x-3.1; right=x+7.2
            shapes += [box(left-1.6,web_y,8,13.5,1.6,106),
                       box(left-1.6,side_y,18,1.6,3.0,96),box(right,side_y,18,1.6,3.0,96)]
            # Keep the insert block entirely forward of the HDD extraction path.
            if not rear: shapes.append(box(x-3.95,34.9,8,12,6.2,12))
        shapes += [box(x-6,mount_y-6,18,12,12,4) for x in [10,134]]
        s=fuse(shapes)
        tools=[box(x-3.1,104 if rear else 41.1,17,10.3,7.75 if rear else 7,6) for x in SATA_X]
        for x in [10,134]:
            # 6 x 8 slot + large M3 washer permits bank alignment before tightening.
            sl=slot_xy(0,0,0,8,6,6)
            sl=transform(sl,axis=(0,0,1),angle=math.pi/2,move=(x,mount_y,17))
            tools.append(sl)
        if not rear:
            for x in SATA_X: tools += heat((x+2.05,34.9,14),(0,1,0))
        add(name,cut(s,tools),'xz_flip' if rear else 'xz','drive',(.23,.29,.32))

    for i,x in enumerate(SATA_X,1):
        # Each bottom shoe is individually removable and vertically adjustable.
        center=x+2.05
        s=fuse([box(center-8.55,30.9,5,17.1,4,23),
                box(center-8.55,34.9,18,1.45,12.6,4),box(center+7.1,34.9,18,1.45,12.6,4),
                box(center-8.55,46,18,17.1,4,4),box(center-8.55,50,18,17.1,29.5,4)])
        # Vertical screw slot in the front ear, axis Y.
        sl=slot_xy(0,0,0,14,3.4,6)
        sl=transform(sl,axis=(0,0,1),angle=math.pi/2)
        sl=transform(sl,axis=(1,0,0),angle=math.pi/2,move=(center,35.9,14))
        # Recess a <=1.7 mm button head and <=0.5 mm washer clear of the fan.
        pocket=slot_xy(0,0,0,20,9.4,2.4)
        pocket=transform(pocket,axis=(0,0,1),angle=math.pi/2)
        pocket=transform(pocket,axis=(1,0,0),angle=math.pi/2,move=(center,33.2,14))
        add(f'15_drive_shoe_{i}',cut(s,[sl,pocket]),'yz','drive',(.85,.40,.11))
        # A single 2.5 mm spacer clips to the positive-X edge of a 7 mm drive slot.
        # Supplied as two short strips per drive; captured by U-channel front/rear.
        for suffix,yy in [('front',41.1),('rear',108.75)]:
            sp=box(x+4.7,yy,34,2.5,3,80)
            # End stop catches the top of the corresponding guide rail.
            sp=fuse([sp,box(x+4.7,yy-1 if suffix=='rear' else yy,114,4.1,4,2)])
            add(f'16_7mm_shim_{i}_{suffix}',sp,'yz','shim',(.85,.40,.11))

def build_feet_coupon():
    for i,(x,y) in enumerate([(7,7),(137,7),(7,161),(137,161)],1):
        s=cylinder((x,y,-6),7,6)
        s=cut(s,[cylinder((x,y,-7),1.7,8),cylinder((x,y,-6.1),3.1,2.5)])
        add(f'17_foot_{i}',s,group='foot')
    # Separate coupon: same U slot and insert pilot as the production parts.
    s=fuse([box(0,0,0,36,24,3),box(3,3,3,1.6,9,15),box(14.9,3,3,1.6,9,15),
            box(3,3,3,13.5,1.6,15),box(23,3,3,10,10,7)])
    s=cut(s,heat((28,8,10),(0,0,-1))+[cylinder((28,18,-1),1.7,6)])
    add('00_fit_coupon',s,group='coupon',color=(.85,.40,.11))
    add('00_fit_shim_2p5',box(40,0,0,2.5,3,15),'yz',group='coupon',color=(.85,.40,.11))

def references():
    s=TopoDS_Shape(); BRepTools.Read_s(s,str(ROOT/'work/taco-analysis.brep'),BRep_Builder())
    board=transform(s,axis=(0,1,0),angle=math.pi,move=(72.1,120,135))
    mesh(board,ROOT/'work/meshes/reference_taco.stl')
    ex=TopExp_Explorer(board,TopAbs_SOLID); idx=0
    while ex.More():
        if idx==0 or idx>=687: mesh(ex.Current(),ROOT/'work/meshes'/f'ref_board_{idx}.stl')
        idx+=1; ex.Next()
    refs={'taco':board}
    for i,x in enumerate(SATA_X,1):
        hdd=box(x-2.7,41.5,22.25,9.5,69.85,100.45)
        refs[f'hdd_{i}']=hdd; mesh(hdd,ROOT/'work/meshes'/f'reference_hdd_{i}.stl')
    for name,p,dims in [('front_fan',(12,5,8),(120,25,120)),('rear_fan',(12,138,8),(120,25,120)),
                        ('top_fan',(22,45,180),(92,92,25))]:
        refs[name]=box(*p,*dims)
    refs['heatsink_keepout']=box(34.55,55.2,135,56,43,35)
    refs['m2_keepout']=box(34.7,97.2,135,82,24,13)
    return refs

def save_step():
    # Separate roots retain all printable solid boundaries in analytic STEP.
    Interface_Static.SetCVal_s('write.step.schema','AP214')
    w=STEPControl_Writer()
    for meta,s,_ in PARTS:
        if meta['group']=='coupon': continue
        Interface_Static.SetCVal_s('write.step.product.name',meta['name'])
        w.Transfer(s,STEPControl_AsIs)
    status=w.Write(str(ROOT/'outputs/CyberMachine-r1-enclosure.step'))
    print('STEP',status,flush=True)

def main():
    global ROOT
    ap=argparse.ArgumentParser(); ap.add_argument('--root',default=str(REPO_ROOT)); ap.add_argument('--only',default='')
    ap.add_argument('--board-step',help='Path to the original Radxa Taco V1.61 STEP')
    args=ap.parse_args(); ROOT=Path(args.root).resolve()
    for p in ['work/parts','work/meshes','work/print_meshes','outputs']: (ROOT/p).mkdir(parents=True,exist_ok=True)
    cache=ROOT/'work/taco-analysis.brep'
    if args.board_step:
        reader=STEPControl_Reader()
        if int(reader.ReadFile(str(Path(args.board_step).resolve())))!=1: raise RuntimeError('Cannot read board STEP')
        reader.TransferRoots(); BRepTools.Write_s(reader.OneShape(),str(cache))
    if not cache.exists(): raise RuntimeError('Provide --board-step with the original Radxa Taco STEP')
    tasks=[build_base,build_sides,build_fan_panels,build_io_lid,build_saddle,build_guides,build_feet_coupon]
    for fn in tasks:
        if not args.only or args.only in fn.__name__: print('BUILD',fn.__name__,flush=True); fn()
    if args.only: return
    refs=references(); save_step()
    (ROOT/'work/manifest.json').write_text(json.dumps([p[0] for p in PARTS],indent=2))
    # Exact reference checks. Expected contact and copper/fastener interfaces are
    # excluded; the HDD solids are labelled standard-envelope proxies.
    checks=[]
    for meta,s,_ in PARTS:
        if meta['group']=='coupon': continue
        for key,r in refs.items():
            if key.startswith('hdd') and meta['group']=='shim': continue
            b,c=bounds(s),bounds(r)
            overlap=all(b[i]<c[i+3]-1e-5 and b[i+3]>c[i]+1e-5 for i in range(3))
            if overlap:
                v=volume(common(s,r))
                if v>0.01: checks.append(dict(part=meta['name'],reference=key,overlap_mm3=round(v,4)))
    (ROOT/'work/reference_intersections.json').write_text(json.dumps(checks,indent=2))
    print('REFERENCE_INTERSECTIONS',json.dumps(checks),flush=True)

if __name__=='__main__': main()
