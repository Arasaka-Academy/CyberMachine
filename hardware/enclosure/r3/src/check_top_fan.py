"""[INPUT]: 导出的上盖、盖锁螺丝、顶扇、内框和原厂 STEP；validate 的实体测量。
[OUTPUT]: 顶扇紧固栈、格栅开口、服务空间与解锁后提盖采样报告。
[POS]: 独立复核顶盖风扇，不调用设计源码生成待测实体。
[PROTOCOL]: Update this header on change, then check AGENTS.md
"""
from datetime import datetime, timezone
from hashlib import sha256
from math import pi
import json

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

import validate as geo

ROOT, OUT = geo.ROOT, geo.OUT
HOLES = [(x, y) for x in (30.75, 113.25) for y in (58.75, 141.25)]


def boolean(first, second, cut=False):
    operation = (BRepAlgoAPI_Cut if cut else BRepAlgoAPI_Common)(first, second)
    assert operation.IsDone(), '顶扇布尔测量失败'
    return operation.Shape()


def cylinder(x, y, z, radius, height):
    return BRepPrimAPI_MakeCylinder(
        gp_Ax2(gp_Pnt(x, y, z), gp_Dir(0, 0, 1)), radius, height).Shape()


def faces(shape):
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        yield TopoDS.Face(explorer.Current())
        explorer.Next()


def contact_area(first, second, z):
    def at_level(shape):
        return [face for face in faces(shape)
                if abs(geo.bounds(face)[2]-z) < 1e-6
                and abs(geo.bounds(face)[5]-z) < 1e-6]
    total = 0.
    for a in at_level(first):
        for b in at_level(second):
            props = GProp_GProps()
            BRepGProp.SurfaceProperties_s(boolean(a, b), props)
            total += props.Mass()
    return total


def axial_surfaces(shape, x, y):
    result = []
    for face in faces(shape):
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Cylinder:
            continue
        cyl = surface.Cylinder()
        point, direction = cyl.Location(), cyl.Axis().Direction()
        if (abs(point.X()-x) < 1e-6 and abs(point.Y()-y) < 1e-6
                and abs(direction.Z()) > .999999):
            b = geo.bounds(face)
            result.append({'radiusMm': cyl.Radius(), 'zMm': [b[2], b[5]]})
    return result


def main():
    names = ['lid', 'lid-fasteners', 'top-fan', 'shell', 'spine', 'rear-fan-frame', 'carrier']
    shapes = {name: geo.read(OUT/f'{name}.step') for name in names}
    lid, fan = shapes['lid'], shapes['top-fan']
    lid_screws = geo.solids(shapes['lid-fasteners'])
    assert len(lid_screws) == 4, len(lid_screws)
    assert geo.overlap(shapes['lid-fasteners'], fan) < 1e-5
    assert geo.overlap(shapes['lid-fasteners'], lid) < 1e-5
    fan_solids = geo.solids(fan)
    assert len(fan_solids) == 14, len(fan_solids)
    classes = {'frame': [], 'rotor': [], 'screw': [], 'washer': [], 'nut': []}
    for shape in fan_solids:
        b = geo.bounds(shape)
        height = b[5]-b[2]
        kind = ('frame' if abs(height-14) < 1e-5 else
                'rotor' if abs(height-12) < 1e-5 else
                'screw' if abs(height-21.7) < 1e-5 else
                'washer' if abs(height-.5) < 1e-5 else
                'nut' if abs(height-1.8) < 1e-5 else None)
        assert kind, b
        classes[kind].append(shape)
    assert {k: len(v) for k, v in classes.items()} == {
        'frame': 1, 'rotor': 1, 'screw': 4, 'washer': 4, 'nut': 4}
    frame, rotor = classes['frame'][0], classes['rotor'][0]
    assert all(abs(a-b) < 1e-5 for a, b in zip(
        geo.bounds(frame), (26, 54, 175.2, 118, 146, 189.2)))
    assert abs(geo.bounds(lid)[5]-194) < 1e-5
    cooler = geo.block(40, 57, 143, 58, 45, 27)
    clearance = geo.distance(geo.block(26, 54, 175.2, 92, 92, 14), cooler)
    assert abs(clearance-5.2) < 1e-5
    actual_frame_gap = geo.distance(frame, cooler)
    assert actual_frame_gap >= clearance-1e-5
    assert geo.overlap(fan, lid) < 1e-5
    fasteners = []
    for x, y in HOLES:
        matched = {}
        for kind in ('screw', 'washer', 'nut'):
            matched[kind] = next(shape for shape in classes[kind]
                                 if abs((geo.bounds(shape)[0]+geo.bounds(shape)[3])/2-x) < 1e-5
                                 and abs((geo.bounds(shape)[1]+geo.bounds(shape)[4])/2-y) < 1e-5)
        surfaces = axial_surfaces(lid, x, y)
        expected = [(1.7, 189.2, 191.8), (3.15, 191.8, 194), (4.5, 189.2, 191.2)]
        for radius, bottom, top in expected:
            assert any(abs(s['radiusMm']-radius) < 1e-5
                       and all(abs(a-b) < 1e-5 for a, b in zip(s['zMm'], [bottom, top]))
                       for s in surfaces), (x, y, surfaces)
        assert any(abs(s['radiusMm']-2.15) < 1e-5
                   for s in axial_surfaces(frame, x, y))
        bearing = contact_area(frame, matched['washer'], 175.2)
        assert bearing > 23.9, bearing
        boss_bearing = contact_area(lid, frame, 189.2)
        assert boss_bearing > 190, boss_bearing
        stack = {kind: list(geo.bounds(shape)[2::3]) for kind, shape in matched.items()}
        screw_bounds = geo.bounds(matched['screw'])
        assert abs(screw_bounds[3]-screw_bounds[0]-5.7) < 1e-5
        head_recess = 194-stack['screw'][1]
        assert abs(head_recess-.5) < 1e-5
        nut_tool = cylinder(x, y, 160, 4, 12.9)
        nut_tool_overlap = geo.overlap(nut_tool, lid)
        assert nut_tool_overlap < 1e-5
        protrusion = stack['nut'][0]-stack['screw'][0]
        assert abs(protrusion-1.1) < 1e-5
        fasteners.append({'xyMm': [x, y], 'lidCylindricalSurfaces': surfaces,
                          'hardwareZMm': stack, 'screwPastNutMm': protrusion,
                          'headDiameterMm': screw_bounds[3]-screw_bounds[0],
                          'headBelowRoofMm': head_recess,
                          'nutSocketEnvelope': {'diameterMm': 8, 'zMm': [160, 172.9],
                                                'lidOverlapMm3': nut_tool_overlap},
                          'washerFrameBearingAreaMm2': bearing,
                          'hardwareCoolerDistanceMm': min(geo.distance(s, cooler) for s in matched.values())})
    # 直接从屋顶薄截片求空洞；同心环由四向连筋分成28段。
    region = cylinder(72, 100, 191.3, 42, .4)
    openings = boolean(region, lid, cut=True)
    slots = geo.solids(openings)
    assert len(slots) == 28, len(slots)
    open_area = geo.volume(openings)/.4
    bar = geo.block(65, 98, 191.3, 14, 4, .4)
    assert abs(geo.overlap(bar, lid)-geo.volume(bar)) < 1e-5
    frame_roof_gap = geo.distance(frame, boolean(lid, cylinder(72, 100, 191.19, 46, 2.9)))
    assert abs(frame_roof_gap-2) < 1e-5
    source = ROOT/'references/radxa-taco/radxa_taco_3d_stp_v1.61.stp'
    native = geo.moved(geo.read(source), (72.1, 120, 135), pi)
    b = geo.bounds(native)
    board_envelope = geo.block(*b[:3], *(b[i+3]-b[i] for i in range(3)))
    fixed = geo.compound([shapes['shell'], shapes['spine'], shapes['rear-fan-frame'], board_envelope, cooler,
                          geo.block(12, 142, 8, 120, 25, 120)]
                         +[geo.moved(shapes['carrier'], (x-29, 0, 0)) for x in geo.SATA_X]
                         +[geo.block(x-2.7, 41.5, 22.25, 7, 69.85, 100.45) for x in geo.SATA_X])
    # 光杆金属实体随盖移动只核对展示包络；实物须先完整旋出四颗盖锁螺丝。
    moving = geo.compound([lid, fan, shapes['lid-fasteners']])
    path = []
    for lift in [*range(17), 25, 50, 100, 200]:
        overlap = geo.overlap(geo.moved(moving, (0, 0, lift)), fixed)
        assert overlap < 1e-4, (lift, overlap)
        path.append({'liftMm': lift, 'overlapMm3': overlap})
        print(f'Unlocked lid group lift {lift} mm: {overlap:.6f} mm3', flush=True)
    service = geo.block(65, 148, 169.3, 14, 14, 19.9)
    service_overlap = geo.overlap(service, geo.compound([moving, fixed]))
    assert service_overlap < 1e-5
    old_frame = geo.block(26, 54, 164.2, 92, 92, 25)
    incompatible = geo.overlap(old_frame, cooler)
    assert incompatible > 10000, incompatible
    result = {
        'checkedAt': datetime.now(timezone.utc).isoformat(), 'passed': True,
        'checkerSha256': sha256((ROOT/'hardware/enclosure/r3/src/check_top_fan.py').read_bytes()).hexdigest(),
        'sourceSha256': sha256((ROOT/'hardware/enclosure/r3/src/design.py').read_bytes()).hexdigest(),
        'inputs': {f'{name}.step': sha256((OUT/f'{name}.step').read_bytes()).hexdigest() for name in names},
        'boardSourceSha256': sha256(source.read_bytes()).hexdigest(),
        'partCounts': {k: len(v) for k, v in classes.items()},
        'frameBoundsMm': geo.bounds(frame),
        'frameCenterXYMm': [(geo.bounds(frame)[i]+geo.bounds(frame)[i+3])/2 for i in (0, 1)],
        'lidTopMm': geo.bounds(lid)[5],
        'frameEnvelopeCoolerClearanceMm': clearance,
        'modeledFrameCoolerDistanceMm': actual_frame_gap,
        'completeFanCoolerDistanceMm': geo.distance(fan, cooler),
        'frameRoofGapMm': frame_roof_gap,
        'lidFanOverlapMm3': geo.overlap(lid, fan), 'fasteners': fasteners,
        'lidClosureScrewCount': len(lid_screws),
        'allFourBossFrameBearingAreaMm2': boss_bearing,
        'grille': {'activeDiameterMm': 84, 'slotSegments': len(slots), 'pattern': 'seven concentric rings with four axial spokes',
                   'openAreaMm2': open_area, 'openRatioOfActiveDisk': open_area/(pi*42**2),
                   'crossRibWidthMm': 4, 'radialRibNominalWidthMm': 2.8},
        'lidLift': {'samples': path, 'movingParts': ['lid', 'top-fan', 'lid-fasteners'],
                    'prerequisite': 'Fully unscrew and remove all four M3 lid screws before physically lifting the lid.',
                    'scope': 'Discrete vertical poses, 1 mm steps to 16 mm and larger poses to 200 mm. Smooth screw solids translate with the lid only to check the visual group envelope. Thread engagement and screw withdrawal are not simulated. No continuous swept-volume claim.'},
        'serviceReserve': {'boundsMm': geo.bounds(service), 'overlapMm3': service_overlap,
                           'scope': 'Empty geometric reserve only; actual connector, wiring and service slack are not modeled.'},
        'negativeControl': {'description': 'Old 92x25 fan, same upper mounting plane',
                            'coolerEnvelopeOverlapMm3': incompatible},
        'limits': ['92 mm fan total thickness must be <=14 mm including any supplied pads.',
                   'Generic fan envelope and rotor, not a measured purchased fan.',
                   'Disconnect power, fully remove four lid screws, initially lift lid, unplug fan, then remove lid. Connector and lift slack need physical verification.',
                   'M3 button-head x20, head <=5.7 diameter / 1.7 high, four OD7 x0.5 washers and AF5.5 x1.8 thin nuts; actual tools and fastening strength untested.',
                   'No thermal, airflow, acoustic, vibration, electrical header capacity or physical print-fit validation.']}
    (ROOT/'validation/r3/top-fan.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
