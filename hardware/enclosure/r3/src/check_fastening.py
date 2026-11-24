"""[INPUT]: 最终分件与锁盖螺丝、改造前和原厂主板STEP；validate的通用OCCT测量。
[OUTPUT]: 四点竖锁、孔壁、紧固栈、底脚连筋及730实体投影隔离的独立几何证据。
[POS]: R3紧固结构独立审核；不调用design生成待测实体，不推断强度。
[PROTOCOL]: Update this header on change, then check AGENTS.md
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import acos, pi, sqrt
from pathlib import Path

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse, BRepAlgoAPI_Section
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeVertex
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Ax2, gp_Dir, gp_Pln, gp_Pnt, gp_Vec

import validate as geo

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT/'outputs/redesign-r3'
BASELINE = ROOT/'work/lid-fixing-r3/baseline/outputs/redesign-r3'
LOCKS = ((3.,48.), (141.,48.), (3.,152.), (141.,152.))
FEET = ((10.,36.), (134.,36.), (10.,132.), (134.,132.))
FRONT_TRIANGLES = (((10.,36.), (24.,36.), (18.,50.)),
                   ((134.,36.), (120.,36.), (126.,50.)))
TOLERANCE = 1e-4


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def boolean(first, second, operation='common'):
    query = {'common': BRepAlgoAPI_Common, 'cut': BRepAlgoAPI_Cut, 'fuse': BRepAlgoAPI_Fuse}[operation](first, second)
    assert query.IsDone(), f'紧固测量布尔运算失败：{operation}'
    return query.Shape()


def cylinder(x, y, z, radius, height, axis='z'):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x,y,z), gp_Dir(0,0,1) if axis == 'z' else gp_Dir(0,1,0)),
                                    radius, height).Shape()


def annulus(x, y, z, inner, outer, height, axis='z'):
    return boolean(cylinder(x,y,z,outer,height,axis), cylinder(x,y,z,inner,height,axis), 'cut')


def prism(points, direction):
    wire = BRepBuilderAPI_MakePolygon()
    for point in points:
        wire.Add(gp_Pnt(*point))
    wire.Close()
    return BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(wire.Wire()).Face(), gp_Vec(*direction)).Shape()


def d_seat(x, y):
    left = x < 72
    edge_x = 6.2 if left else 137.8
    result = boolean(geo.block(-2.3 if left else 137.8,y-6,164,8.5,12,10),
                     geo.block(6.2 if left else 135.8,y-4,164,2,8,10),'fuse')
    for dy in (-4.,4.):
        result = boolean(result,cylinder(edge_x,y+dy,164,2,10),'fuse')
    return result


def required_region(shape, region, label, enforce=True):
    missing = max(0., geo.volume(boolean(region, shape, 'cut')))
    result = {'feature':label, 'requiredVolumeMm3':geo.volume(region), 'missingMaterialMm3':missing}
    if enforce:
        assert missing < TOLERANCE, result
    return result


def faces(shape):
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        yield TopoDS.Face(explorer.Current())
        explorer.Next()


def axial_surfaces(shape, x, y, axis='z', z=None):
    records = []
    for face in faces(shape):
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Cylinder:
            continue
        body = surface.Cylinder()
        point, direction = body.Location(), body.Axis().Direction()
        aligned = (abs(point.X()-x) < 1e-5 and abs(point.Y()-y) < 1e-5 and abs(direction.Z()) > .999999
                   if axis == 'z' else abs(point.X()-x) < 1e-5 and abs(point.Z()-z) < 1e-5 and abs(direction.Y()) > .999999)
        if aligned:
            bounds = geo.bounds(face)
            lower, upper = (bounds[2],bounds[5]) if axis == 'z' else (bounds[1],bounds[4])
            records.append({'radiusMm':body.Radius(), 'axisRangeMm':[lower,upper],
                            'angularSpanRad':surface.LastUParameter()-surface.FirstUParameter()})
    return records


def measured_cylinder(records, radius, expected_range):
    matches = [record for record in records if abs(record['radiusMm']-radius) < 1e-5
               and all(abs(a-b) < 1e-5 for a,b in zip(record['axisRangeMm'],expected_range))]
    assert matches, (radius,expected_range,records)
    return matches[0]


def radial_section(shape, center, bore_radius, axis='z'):
    # 截平面上的孔口边除外；最近其余边给出真实环壁或自由边距离。
    plane = BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(*center),gp_Dir(0,0,1) if axis == 'z' else gp_Dir(0,1,0)),
                                    -400,400,-400,400).Face()
    section = BRepAlgoAPI_Section(shape,plane)
    assert section.IsDone(), '孔壁截面求交失败'
    vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*center)).Vertex()
    candidates = []
    explorer = TopExp_Explorer(section.Shape(),TopAbs_EDGE)
    while explorer.More():
        edge = explorer.Current()
        distance = geo.distance(vertex,edge)
        if abs(distance-bore_radius) > 1e-5:
            candidates.append((distance,geo.bounds(edge)))
        explorer.Next()
    assert candidates
    distance, nearest = min(candidates,key=lambda item:item[0])
    return {'sectionCenterMm':list(center), 'boreRadiusMm':bore_radius,
            'nearestOtherBoundaryFromAxisMm':distance, 'minimumMaterialToOtherBoundaryMm':distance-bore_radius,
            'nearestBoundaryBoundsMm':list(nearest)}


def contact_at_level(first, second, z, region=None):
    def at_level(shape):
        return [face for face in faces(shape) if abs(geo.bounds(face)[2]-z) < 1e-6
                and abs(geo.bounds(face)[5]-z) < 1e-6]
    total = 0.
    for left in at_level(first):
        for right in at_level(second):
            shared = boolean(left,right)
            if region is not None:
                shared = boolean(shared,region)
            properties = GProp_GProps()
            BRepGProp.SurfaceProperties_s(shared,properties)
            total += properties.Mass()
    return total


def tool_check(tool, obstacles):
    records = [{'part':name, 'overlapMm3':geo.overlap(tool,shape), 'distanceMm':geo.distance(tool,shape)}
               for name,shape in obstacles]
    assert all(record['overlapMm3'] < TOLERANCE for record in records), records
    return records


def nearest_solid_distance(shape, parts):
    # 单实体逐项测距；包围盒下界仅用于剪枝，整树布尔不参与通过判定。
    box = geo.bounds(shape)
    ordered = []
    for index,solid in enumerate(parts):
        other = geo.bounds(solid)
        lower = sqrt(sum(max(box[i]-other[i+3],other[i]-box[i+3],0.)**2 for i in range(3)))
        ordered.append((lower,index,solid))
    minimum,nearest = float('inf'),None
    for lower,index,solid in sorted(ordered,key=lambda item:item[0]):
        if lower >= minimum:
            break
        distance = geo.distance(shape,solid)
        if distance < minimum:
            minimum,nearest = distance,index
    return minimum,nearest


def lid_lock_checks(shapes):
    lid, shell = shapes['lid'], shapes['shell']
    screws = geo.solids(shapes['lid-fasteners'])
    assert len(screws) == 4
    result = []
    for x,y in LOCKS:
        lid_surfaces, shell_surfaces = axial_surfaces(lid,x,y), axial_surfaces(shell,x,y)
        pilot = measured_cylinder(shell_surfaces,2.05,[166.4,174.])
        through = measured_cylinder(lid_surfaces,1.7,[174.,191.8])
        counterbore = measured_cylinder(lid_surfaces,3.15,[191.8,194.])
        assert abs(counterbore['angularSpanRad']-2*pi) < 1e-5, counterbore
        screw = next(s for s in screws if abs((geo.bounds(s)[0]+geo.bounds(s)[3])/2-x) < 1e-5
                     and abs((geo.bounds(s)[1]+geo.bounds(s)[4])/2-y) < 1e-5)
        screw_surfaces = axial_surfaces(screw,x,y)
        shaft = measured_cylinder(screw_surfaces,1.5,[166.8,191.8])
        head = measured_cylinder(screw_surfaces,2.85,[191.8,193.5])
        required = []
        seat = boolean(d_seat(x,y),cylinder(x,y,166.4,2.05,7.7),'cut')
        required.append(required_region(shell,seat,'D-shaped-shell-seat'))
        sleeve = annulus(x,y,174,1.7,6,13.2)
        required.append(required_region(lid,sleeve,'D12-compression-sleeve'))
        root = BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(x,y,187.2),gp_Dir(0,0,1)),6,8,2).Shape()
        root = boolean(root,cylinder(x,y,187.1,1.7,2.2),'cut')
        root = boolean(root,geo.block(-5,28,186.9,154,144,5))
        required.append(required_region(lid,root,'45-degree-sleeve-root'))
        crown = boolean(annulus(x,y,189.2,1.7,8,2.),geo.block(-5,28,186.9,154,144,5))
        required.append(required_region(lid,crown,'D16-roof-root-clipped-to-outer-wall'))
        required.append(required_region(lid,annulus(x,y,191.81,3.15,6.15,2.18),'closed-counterbore-rim'))
        required.append(required_region(shell,cylinder(x,y,164,2.04,2.39),'blind-floor-material'))
        left = x < 72
        ramp_points = ((-2.3,y-6,153.5),(8.2,y-6,164),(-2.3,y-6,164)) if left else (
                       (146.3,y-6,153.5),(135.8,y-6,164),(146.3,y-6,164))
        required.append(required_region(shell,prism(ramp_points,(0,12,0)),'45-degree-wall-arm-ramp'))
        sleeve_section = radial_section(lid,(x,y,180),1.7)
        pilot_section = radial_section(shell,(x,y,171),2.05)
        rim_section = radial_section(lid,(x,y,192.5),3.15)
        assert abs(sleeve_section['minimumMaterialToOtherBoundaryMm']-4.3) < 1e-5
        assert abs(pilot_section['minimumMaterialToOtherBoundaryMm']-3.15) < 1e-5
        assert abs(rim_section['minimumMaterialToOtherBoundaryMm']-4.85) < 1e-5
        seat_area = contact_at_level(shell,lid,174,cylinder(x,y,173.9,6.1,.2))
        removed_cap = 6**2*acos(5.2/6)-5.2*sqrt(6**2-5.2**2)
        expected_area = pi*(6**2-2.05**2)-removed_cap
        assert abs(seat_area-expected_area) < 1e-4, (seat_area,expected_area)
        head_bearing = contact_at_level(lid,screw,191.8)
        assert abs(head_bearing-pi*(2.85**2-1.7**2)) < 1e-4
        print_overlap = {name:geo.overlap(screw,shapes[name]) for name in ('lid','shell','spine','rear-fan-frame','top-fan')}
        assert all(value < TOLERANCE for value in print_overlap.values()), print_overlap
        # 铜套仅作明确尺寸的无牙占位量规，不能当采购或热熔配合结论。
        insert = annulus(x,y,168.6,1.5,2.05,5.4)
        insert_overlap = geo.overlap(insert,shell)
        assert insert_overlap < TOLERANCE
        driver = cylinder(x,y,193.5,3,40)
        obstacles = [('lid',lid),('top-fan',shapes['top-fan'])]
        obstacles += [(f'other-lock-{n}',s) for n,s in enumerate(screws) if s is not screw]
        driver_records = tool_check(driver,obstacles)
        assert abs(driver_records[0]['distanceMm']-.15) < 1e-5
        tip_floor = shaft['axisRangeMm'][0]-pilot['axisRangeMm'][0]
        assert abs(tip_floor-.4) < 1e-5
        result.append({'xyMm':[x,y], 'pilot':pilot, 'throughHole':through, 'counterbore':counterbore,
            'screwShaft':shaft, 'screwHead':head, 'headBelowRoofMm':194-head['axisRangeMm'][1],
            'seatContactAreaMm2':seat_area, 'headBearingAreaMm2':head_bearing,
            'pilotSidewallSection':pilot_section, 'sleeveWallSection':sleeve_section, 'counterboreEdgeSection':rim_section,
            'requiredMaterial':required, 'screwPrintedPartOverlapMm3':print_overlap,
            'insertGauge':{'outerDiameterMm':4.1,'innerDiameterMm':3.,'lengthMm':5.4,'zMm':[168.6,174.],
                'shellOverlapMm3':insert_overlap,'assumptionOnly':True,'actualInsertSelected':False},
            'nominalThreadOverlapMm':5.4,'screwBeyondInsertMm':1.8,'tipFloorClearanceMm':tip_floor,
            'blindFloorMaterialMm':pilot['axisRangeMm'][0]-164., 'driverDiameterMm':6.,'driverChecks':driver_records})
        print('Lid lock',x,y,'contact',round(seat_area,5),'mm2',flush=True)
    return result


def base_checks(shell, spine, old_shell, old_spine):
    result = []
    for x,y in FEET:
        left = x < 72
        root_x = -2.3 if left else 137.8
        web = geo.block(root_x,y-1.6,2.7,8.5,3.2,5.3)
        region = required_region(shell,web,'shell-foot-to-wall-web')
        old_region = required_region(old_shell,web,'old-missing-shell-web',False)
        assert old_region['missingMaterialMm3'] > 10
        section_x = 4.5 if left else 139.4
        section_region = geo.block(section_x,y-2,2.81,.1,4,5.18)
        section = boolean(shell,section_region)
        box = geo.bounds(section)
        assert abs((box[4]-box[1])-3.2) < 1e-5
        section_area = geo.volume(section)/.1
        assert abs(section_area-3.2*5.18) < 1e-4
        shell_surfaces, frame_surfaces = axial_surfaces(shell,x,y), axial_surfaces(spine,x,y)
        bore = measured_cylinder(frame_surfaces,2.05,[8,12.8])
        head_bore = measured_cylinder(shell_surfaces,3.15,[0,2.2])
        screw = boolean(cylinder(x,y,2.2,1.5,10),cylinder(x,y,.5,2.85,1.7),'fuse')
        assert geo.overlap(screw,shell) < TOLERANCE and geo.overlap(screw,spine) < TOLERANCE
        floor = required_region(spine,cylinder(x,y,12.81,2.04,1.18),'base-insert-blind-floor')
        insert = annulus(x,y,8,1.5,2.05,4.8)
        assert geo.overlap(insert,spine) < TOLERANCE
        contact = contact_at_level(shell,spine,8,cylinder(x,y,7.9,4.6,.2))
        assert abs(contact-pi*(4.5**2-2.05**2)) < 1e-4
        driver = tool_check(cylinder(x,y,-39.5,3,40),[('shell',shell),('spine',spine)])
        result.append({'xyMm':[x,y], 'shellWebRequiredMaterial':region, 'baselineMissingWeb':old_region,
            'webSectionBoundsMm':list(box), 'webSectionAreaMm2':section_area, 'framePilot':bore,
            'shellHeadCounterbore':head_bore, 'contactAreaMm2':contact,
            'blindFloor':floor, 'blindFloorMaterialMm':14-bore['axisRangeMm'][1],
            'screwGauge':{'size':'M3x10','shaftZMm':[2.2,12.2],'headDiameterMm':5.7,'headZMm':[.5,2.2]},
            'insertGauge':{'outerDiameterMm':4.1,'lengthMm':4.8,'zMm':[8.,12.8],
                'assumptionOnly':True,'actualInsertSelected':False},
            'screwTipFloorClearanceMm':bore['axisRangeMm'][1]-12.2,'nominalThreadOverlapMm':4.2,
            'driverChecks':driver})
    front = []
    for index,points in enumerate(FRONT_TRIANGLES):
        x,y = FEET[index]
        region = prism([(a,b,8) for a,b in points],(0,0,6))
        region = boolean(region,cylinder(x,y,7.9,2.05,4.9),'cut')
        current = required_region(spine,region,'front-frame-foot-gusset')
        previous = required_region(old_spine,region,'old-front-frame-foot-root',False)
        assert previous['missingMaterialMm3'] > 10
        probe_x = 14.5 if index == 0 else 128.5
        probe = geo.block(probe_x,40.5,8,1,1,6)
        witness = required_region(spine,probe,'front-root-full-height-witness')
        measured = geo.bounds(boolean(spine,probe))
        assert abs(measured[5]-measured[2]-6) < 1e-5
        front.append({'corner':index+1,'material':current,'baselineMissingMaterial':previous,
                      'rootWitness':witness,'measuredRootThicknessMm':measured[5]-measured[2]})
    return result,front


def added_seat_projection_checks(shapes, native):
    # 将实测新增座的XY包围盒贯穿运动件全高；正间隙覆盖任意Z平移。
    # 包围盒是座投影的保守上界，不把主板整体盒的交叠当真实器件交叠。
    native_solids = geo.solids(native)
    assert len(native_solids) == 730
    moving = [('spine',shapes['spine']),('rear-fan-frame',shapes['rear-fan-frame'])]
    for index,x in enumerate((29.,50.5,72.,93.5,115.),1):
        moving += [(f'carrier-{index}',geo.moved(shapes['carrier'],(x-29,0,0))),
                   (f'7mm-drive-{index}',geo.block(x-2.7,41.5,22.25,7,69.85,100.45))]
    moving += [('rear-fan-envelope',geo.block(12,142,8,120,25,120)),
               ('cm5-envelope',geo.block(41.5,60.9,140,55,40,3)),
               ('cooler-envelope',geo.block(40,57,143,58,45,27))]
    for x in (19.5,124.5):
        for z in (15.5,120.5):
            moving.append((f'rear-fan-head-{x}-{z}',cylinder(x,167,z,2.85,1.7,'y')))
    native_bounds = geo.bounds(native)
    native_box = geo.block(*native_bounds[:3],*(native_bounds[i+3]-native_bounds[i] for i in range(3)))
    result = []
    for x,y in LOCKS:
        region_x = -2.2 if x < 72 else 135.8
        region = geo.block(region_x,y-6,153.49,10.4,12,20.52)
        seat_solids = geo.solids(boolean(shapes['shell'],region))
        assert len(seat_solids) == 1, (x,y,len(seat_solids))
        addition = seat_solids[0]
        box = geo.bounds(addition)
        expected = (-2.2,8.2) if x < 72 else (135.8,146.2)
        assert all(abs(actual-target) < 1e-5 for actual,target in zip((box[0],box[3]),expected)), box
        assert abs(box[1]-(y-6)) < 1e-5 and abs(box[4]-(y+6)) < 1e-5, box
        margin = 1e-5
        column = geo.block(box[0]-margin,box[1]-margin,-10,
                           box[3]-box[0]+2*margin,box[4]-box[1]+2*margin,410)
        records = []
        for name,shape in moving:
            assert geo.bounds(shape)[2] > -10 and geo.bounds(shape)[5] < 400
            amount,clearance = geo.overlap(column,shape),geo.distance(column,shape)
            assert amount < TOLERANCE and clearance > margin, (x,y,name,amount,clearance)
            records.append({'part':name,'projectionOverlapMm3':amount,'xyClearanceMm':clearance})
        native_records = []
        for index,solid in enumerate(native_solids):
            if geo.candidate(geo.bounds(column),geo.bounds(solid)):
                amount = geo.overlap(column,solid)
                assert amount < TOLERANCE, (x,y,'native-board-solid',index,amount)
                native_records.append({'solidIndex':index,'overlapMm3':amount})
        native_clearance,nearest_native = nearest_solid_distance(column,native_solids)
        assert native_clearance > margin
        native_box_overlap = geo.overlap(column,native_box)
        result.append({'xyMm':[x,y],'actualAddedSeatBoundsMm':list(box),'addedSeatVolumeMm3':geo.volume(addition),
            'projectionMethod':'Exact final seat B-rep clipped inside the moved sidewall inner face; its measured bounds are expanded 0.00001 mm in XY and extended through all moving-part heights. This rectangular projection contains the actual seat projection.',
            'columnBoundsMm':list(geo.bounds(column)),'movingParts':records,
            'nativeBoard':{'solidCount':len(native_solids),'broadphaseCandidates':native_records,
                           'actualProjectionOverlapMm3':sum(item['overlapMm3'] for item in native_records),
                           'xyClearanceMm':native_clearance,'nearestSolidIndex':nearest_native,
                           'wholeBoardBoxOverlapMm3':native_box_overlap,
                           'wholeBoardBoxFalsePositive':native_box_overlap > TOLERANCE},
            'scope':'Continuous vertical-translation isolation for the four added shell seats only. Full shell service path remains covered by geometry.json discrete poses.'})
        print('Added-seat XY projection',x,y,'native gap',round(native_clearance,6),flush=True)
    return result


def negative_controls(shapes, old_shell, old_lid, native):
    old_lip = radial_section(old_lid,(12.,167.5,171.8),1.65,'y')
    assert abs(old_lip['minimumMaterialToOtherBoundaryMm']-.85) < 1e-5
    old_rim = annulus(12,170.9,171.8,2.5,3,.2,'y')
    old_open = required_region(old_shell,old_rim,'old-open-rear-head-recess',False)
    assert old_open['missingMaterialMm3'] > .01
    x,y = LOCKS[0]
    large_shank = geo.overlap(cylinder(x,y,174.1,1.8,17.6),shapes['lid'])
    large_head = geo.overlap(cylinder(x,y,191.8,3.5,1.7),shapes['lid'])
    large_driver = geo.overlap(cylinder(x,y,193.5,4,40),shapes['lid'])
    assert min(large_shank,large_head,large_driver) > .1
    web = geo.block(2.7,34.4,2.7,3.5,3.2,5.3)
    damaged = boolean(shapes['shell'],geo.block(4.4,34.3,2.69,.3,3.4,5.32),'cut')
    missing_web = required_region(damaged,web,'deliberately-cut-foot-web',False)
    assert missing_web['missingMaterialMm3'] > 1
    blocked_projection = geo.overlap(geo.block(7,35,-10,12,12,410),shapes['spine'])
    assert blocked_projection > 1, '原13/41宽座投影应阻断真实内架'
    old_d_column = geo.block(2.8,42,-10,8.7,12,410)
    pcb_projection = geo.overlap(old_d_column,geo.solids(native)[0])
    assert pcb_projection > 40, '原7/48座投影应阻断原厂PCB'
    tree_projection = geo.overlap(old_d_column,native)
    return {'oldLidLip':old_lip,'oldLipFailsTwoMmMaterialCriterion':old_lip['minimumMaterialToOtherBoundaryMm'] < 2,
        'oldOpenCounterbore':old_open,'oversizeShaftDiameterMm':3.6,'oversizeShaftOverlapMm3':large_shank,
        'oversizeHeadDiameterMm':7.,'oversizeHeadOverlapMm3':large_head,
        'oversizeDriverDiameterMm':8.,'oversizeDriverOverlapMm3':large_driver,'cutFootWeb':missing_web,
        'previousWideSeatProjection':{'boundsXyMm':[7,35,19,47],
            'actualFrameProjectionOverlapMm3':blocked_projection,'rejected':True},
        'nativeWholeTreeBooleanControl':{'boundsXyMm':[2.8,42,11.5,54],
            'pcbSolidProjectionOverlapMm3':pcb_projection,'wholeTreeProjectionOverlapMm3':tree_projection,
            'wholeTreeFalseNegativeObserved':tree_projection < TOLERANCE,
            'acceptanceUsesIndividualSolids':True,'rejected':True}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline',type=Path,default=BASELINE,help='改造前shell/lid/spine STEP目录')
    args = parser.parse_args()
    names = ('shell','lid','spine','carrier','rear-fan-frame','top-fan','lid-fasteners')
    inputs = {f'{name}.step':OUT/f'{name}.step' for name in names}
    baseline_inputs = {f'{name}.step':args.baseline/f'{name}.step' for name in ('shell','lid','spine')}
    assert all(path.is_file() for path in [*inputs.values(),*baseline_inputs.values()]), '缺少最终或基线STEP'
    hashes = {name:digest(path) for name,path in inputs.items()}
    baseline_hashes = {name:digest(path) for name,path in baseline_inputs.items()}
    metadata_path = OUT/'metadata.json'
    metadata_hash = digest(metadata_path)
    checker_hash = digest(Path(__file__))
    metadata = json.loads(metadata_path.read_text())
    source_hash = digest(Path(__file__).with_name('design.py'))
    assert metadata['sourceSha256'] == source_hash, '先导出同轮CAD'
    board_path = ROOT/'references/radxa-taco/radxa_taco_3d_stp_v1.61.stp'
    board_hash = digest(board_path)
    native = geo.moved(geo.read(board_path),(72.1,120,135),pi)
    shapes = {name:geo.read(path) for name,path in ((name,inputs[f'{name}.step']) for name in names)}
    old = {name:geo.read(path) for name,path in baseline_inputs.items()}
    assert all(len(geo.solids(shapes[name])) == 1 and BRepCheck_Analyzer(shapes[name]).IsValid()
               for name in ('shell','lid','spine','carrier','rear-fan-frame'))
    assert geo.overlap(shapes['shell'],shapes['lid']) < TOLERANCE
    locks = lid_lock_checks(shapes)
    bases,front = base_checks(shapes['shell'],shapes['spine'],old['shell.step'],old['spine.step'])
    projections = added_seat_projection_checks(shapes,native)
    controls = negative_controls(shapes,old['shell.step'],old['lid.step'],native)
    old_contact = contact_at_level(shapes['shell'],shapes['lid'],169.3)
    new_contact = contact_at_level(shapes['shell'],shapes['lid'],174.)
    assert abs(old_contact-76.8) < 1e-4
    assert abs(new_contact-sum(lock['seatContactAreaMm2'] for lock in locks)) < 1e-4
    assert hashes == {name:digest(path) for name,path in inputs.items()}, '最终STEP在审核期间变化'
    assert baseline_hashes == {name:digest(path) for name,path in baseline_inputs.items()}, '基线STEP在审核期间变化'
    assert source_hash == digest(Path(__file__).with_name('design.py')), '设计源码在审核期间变化'
    assert metadata_hash == digest(metadata_path), '导出清单在审核期间变化'
    assert checker_hash == digest(Path(__file__)), '紧固审核源码在执行期间变化'
    assert board_hash == digest(board_path), '原厂主板STEP在审核期间变化'
    report = {'checkedAt':datetime.now(timezone.utc).isoformat(),'passed':True,'geometryPassed':True,
        'strengthValidated':False,'sourceSha256':source_hash,'checkerSha256':checker_hash,
        'metadataSha256':metadata_hash,
        'boardSourceSha256':board_hash,
        'inputs':hashes,'baseline':{'directory':str(args.baseline.relative_to(ROOT)) if args.baseline.is_relative_to(ROOT) else str(args.baseline),
                                   'inputSha256':baseline_hashes},
        'lidLocks':locks,'baseMounts':bases,'frontFrameRoots':front,'addedSeatProjectionIsolation':projections,
        'negativeControls':controls,
        'mating':{'oldStopContactAreaMm2':old_contact,'newFourSeatContactAreaMm2':new_contact,
                  'totalContactAreaMm2':old_contact+new_contact,'shellLidOverlapMm3':geo.overlap(shapes['shell'],shapes['lid'])},
        'limits':['Independent STEP/B-rep geometry only; no physical or FEA strength, torque, fatigue, vibration or thermal validation.',
                  'Insert OD4.1/length5.4 for lid and OD4.1/length4.8 for base are unthreaded geometric gauges, not purchase specifications or heat-set fit guarantees.',
                  'M3 fully threaded shafts and nominal head envelopes omit threads, knurls, tolerances and tool-bit shape.',
                  'Driver envelopes prove the stated rigid shafts only, not full hand access; wiring and real solder-tail variation remain unverified.',
                  'Nominal coplanar contact area and material sections do not prove preload distribution or printed strength.']}
    destination = ROOT/'validation/r3/fastening.json'
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'geometryPassed':True,'strengthValidated':False,'newSeatContactAreaMm2':new_contact,
                      'totalSeatContactAreaMm2':old_contact+new_contact,'report':str(destination)},indent=2),flush=True)


if __name__ == '__main__':
    main()
