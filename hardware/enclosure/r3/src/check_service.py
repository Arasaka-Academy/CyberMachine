"""[INPUT]: 当前加固内总成、7mm盘包络、顶扇上盖和独立原厂主板。
[OUTPUT]: 主板/后扇/盖锁盲孔、35/25mm紧固栈和36项工具空间报告。
[POS]: 补充装配检验；不把静态工具包络当作实物可装配结论。
[PROTOCOL]: Update this header on change, then check AGENTS.md
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import build123d as bd
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepGProp import BRepGProp
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.GProp import GProp_GProps

from check_board import bounds, box_distance, overlap_volume, read_board
from design import (BOARD_HOLES, SATA_X, TOP_FAN_FRAME, TOP_FAN_HOLES,
                    DRIVE_THICKNESS_MM, FRAME_WEB_THICKNESS_MM, FRAME_DIAGONAL_WIDTH_MM,
                    FRAME_BASE_HEIGHT_MM,LID_HOLES,carrier,lid,spine,rear_fan_frame,shell,top_fan)

ROOT = Path(__file__).resolve().parents[4]
TOLERANCE = 1e-7


def cylinder(x, y, z, radius, length, axis='z'):
    shape = bd.Cylinder(radius, length,
                        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    if axis == 'y':
        shape = bd.Rot(-90, 0, 0) * shape
    return bd.Pos(x, y, z) * shape


def intersections(envelope, obstacles):
    box = bounds(envelope.wrapped)
    collisions = []
    closest = None
    distance = float('inf')
    for label, shape, other_box in obstacles:
        if box_distance(box, other_box) > distance:
            continue
        measured = envelope.distance_to(shape)
        if measured < distance:
            closest, distance = label, measured
        if measured < 1e-6:
            volume = overlap_volume(envelope.wrapped, shape.wrapped)
            if volume > TOLERANCE:
                collisions.append({'part': label, 'overlapMm3': volume})
    return {'minDistanceMm': distance, 'nearestPart': closest,
            'overlaps': collisions}


def board_bores(shape):
    result = []
    for number, (x, y) in enumerate(BOARD_HOLES, 1):
        matching = []
        for face in shape.faces():
            surface = BRepAdaptor_Surface(face.wrapped)
            if surface.GetType() != GeomAbs_Cylinder:
                continue
            measured = surface.Cylinder()
            point, axis = measured.Location(), measured.Axis().Direction()
            if (abs(measured.Radius()-1.65) < 1e-6 and
                    abs(point.X()-x) < 1e-6 and abs(point.Y()-y) < 1e-6 and
                    abs(axis.Z()) > .999999):
                matching.append(bounds(face.wrapped))
        assert matching, f'未找到主板孔 {number} 的真实圆柱面'
        bottom, top = min(b[2] for b in matching), max(b[5] for b in matching)
        screw_bottom = 135.-6.
        bore = cylinder(x, y, bottom+.01, 1.64, top-bottom-.02)
        floor = cylinder(x, y, bottom-.1, 1.25, .05)
        shank = cylinder(x, y, screw_bottom, 1.25, 6.)
        bore_overlap = overlap_volume(bore.wrapped, shape.wrapped)
        floor_volume = overlap_volume(floor.wrapped, shape.wrapped)
        screw_overlap = overlap_volume(shank.wrapped, shape.wrapped)
        assert bore_overlap < TOLERANCE and floor_volume > .1
        assert screw_overlap < TOLERANCE and screw_bottom-bottom >= .49
        result.append({'hole': number, 'centerMm': [x, y],
                       'diameterMm': 3.3, 'measuredBottomZ': bottom,
                       'measuredTopZ': top, 'measuredDepthMm': top-bottom,
                       'screw': 'M2.5 low-head x6, no washer',
                       'screwEndZ': screw_bottom,
                       'nominalEngagementMm': top-screw_bottom,
                       'nominalBottomAllowanceMm': screw_bottom-bottom,
                       'boreOverlapMm3': bore_overlap,
                       'floorWitnessVolumeMm3': floor_volume,
                       'screwPlasticOverlapMm3': screw_overlap})
    return result


def rear_fan_bores(frame, rear_frame):
    result=[]
    for x in (19.5,124.5):
        for z in (15.5,120.5):
            matching=[]
            for face in frame.faces():
                surface=BRepAdaptor_Surface(face.wrapped)
                if surface.GetType()!=GeomAbs_Cylinder:
                    continue
                measured=surface.Cylinder()
                point,axis=measured.Location(),measured.Axis().Direction()
                if (abs(measured.Radius()-2.05)<1e-6 and abs(point.X()-x)<1e-6
                        and abs(point.Z()-z)<1e-6 and abs(axis.Y())>.999999):
                    matching.append(bounds(face.wrapped))
            assert matching,(x,z)
            bottom,top=min(b[1] for b in matching),max(b[4] for b in matching)
            assert abs(bottom-131.6)<1e-6 and abs(top-138)<1e-6,(bottom,top)
            bore=cylinder(x,bottom+.01,z,2.04,top-bottom-.02,'y')
            floor=cylinder(x,bottom-.1,z,1.5,.05,'y')
            shank=cylinder(x,132,z,1.5,35,'y')
            clearance=cylinder(x,138.01,z,1.69,3.98,'y')
            assert overlap_volume(bore.wrapped,frame.wrapped)<TOLERANCE
            assert overlap_volume(floor.wrapped,frame.wrapped)>.1
            assert overlap_volume(shank.wrapped,frame.wrapped)<TOLERANCE
            assert overlap_volume(shank.wrapped,rear_frame.wrapped)<TOLERANCE
            assert overlap_volume(clearance.wrapped,rear_frame.wrapped)<TOLERANCE
            result.append({'centerXZmm':[x,z],'measuredBoreYmm':[bottom,top],
                'measuredBoreDepthMm':top-bottom,'screw':'M3 x35, no washer',
                'screwTipYmm':132.,'screwUnderHeadYmm':167.,
                'nominalFloorAllowanceMm':132-bottom,'frameClearanceDiameterMm':3.4,
                'frameThicknessMm':4.,'nominalInsertLengthMm':5.4,
                'insertSpecificationVerified':False})
    return result


def material_comparison(frame, tray, rear_frame):
    # 历史减料与本轮加固各用独立基线；当前值重新取自模型。
    previous_frame, previous_tray = 109383.404113391, 15393.050740064
    datum = bd.Pos(26.3, 76.425, 72.475)*(bd.Plane.YZ*bd.Rectangle(69.85, 100.45))
    common = BRepAlgoAPI_Common(tray.wrapped, datum.face().wrapped)
    properties = GProp_GProps()
    BRepGProp.SurfaceProperties_s(common.Shape(), properties)
    return {
        'baselineDesignSha256': 'ce3048c023bf72616ed49128c970f5d1fa4328f358106d42b4788f4fdd7713a8',
        'spine': {'beforeMm3': previous_frame, 'currentMm3': frame.volume,
                  'rearFrameMm3':rear_frame.volume,
                  'combinedCurrentMm3':frame.volume+rear_frame.volume,
                  'reductionPercent': (1-(frame.volume+rear_frame.volume)/previous_frame)*100},
        'carrier': {'beforeMm3': previous_tray, 'currentMm3': tray.volume,
                    'reductionPercent': (1-tray.volume/previous_tray)*100,
                    'beforeDatumContactAreaMm2': 3218.7375,
                    'currentDatumContactAreaMm2': properties.Mass()},
        'reinforcementBaseline': {'sourceSha256':'e874404198cd09697694dc932cd375fd87b6e8dfde03335970dd293193a73b7a',
                                  'spineVolumeMm3':82897.49201150429,
                                  'volumeAddedMm3':frame.volume+rear_frame.volume-82897.49201150429,
                                  'volumeAddedPercent':((frame.volume+rear_frame.volume)/82897.49201150429-1)*100},
        'frameMinimumMm': {'outerFrame': 8., 'diagonal': FRAME_DIAGONAL_WIDTH_MM,
                           'thickness': FRAME_WEB_THICKNESS_MM,'baseHeight':FRAME_BASE_HEIGHT_MM},
        'carrierMinimumMm': {'frontSideContact': 6., 'rearSideContact': 6.1,
                             'bottomSideContact': 12.75, 'topSideContact': 10.,
                             'floorLongitudinalRail': 2.6, 'floorCrossBand': 6.,
                             'frontScrewHoleEdge': 2.8, 'frontWasherEdge': 1.75},
        'scope': 'B-rep material and contact geometry only; no stiffness, fatigue or vibration proof.',
    }


def lid_bores(body,cover):
    records=[]
    for x,y in LID_HOLES:
        surfaces=[]
        for face in body.faces():
            s=BRepAdaptor_Surface(face.wrapped)
            if s.GetType()!=GeomAbs_Cylinder:
                continue
            c=s.Cylinder();p=c.Location();axis=c.Axis().Direction()
            if abs(c.Radius()-2.05)<1e-6 and abs(p.X()-x)<1e-6 and abs(p.Y()-y)<1e-6 and abs(axis.Z())>.999999:
                surfaces.append(bounds(face.wrapped))
        assert surfaces,(x,y)
        bottom,top=min(b[2] for b in surfaces),max(b[5] for b in surfaces)
        assert abs(bottom-166.4)<1e-6 and abs(top-174)<1e-6
        witness=cylinder(x,y,bottom+.01,2.04,top-bottom-.02)
        floor=cylinder(x,y,bottom-.1,1.5,.05)
        screw=cylinder(x,y,166.8,1.5,25)+cylinder(x,y,191.8,2.85,1.7)
        assert overlap_volume(witness.wrapped,body.wrapped)<TOLERANCE
        assert overlap_volume(floor.wrapped,body.wrapped)>.1
        assert overlap_volume(screw.wrapped,body.wrapped)<TOLERANCE
        assert overlap_volume(screw.wrapped,cover.wrapped)<TOLERANCE
        records.append({'centerXYmm':[x,y],'actualPilotZmm':[bottom,top],
            'actualPilotDepthMm':top-bottom,'screw':'M3 ISO7380 x25, no washer',
            'screwTipZmm':166.8,'screwUnderHeadZmm':191.8,'screwHeadTopZmm':193.5,
            'nominalFloorAllowanceMm':166.8-bottom,'nominalInsertLengthMm':5.4,
            'nominalInsertZmm':[168.6,174.],'actualInsertSpecificationVerified':False})
    return records


def main():
    frame = spine().shape
    shell_body=shell().shape
    cover=lid().shape
    rear_frame = rear_fan_frame().shape
    tray = carrier().shape
    _, board_solids = read_board()
    obstacles = [('spine', frame),('rear-fan-frame',rear_frame)]
    for number, x in enumerate(SATA_X, 1):
        obstacles.append((f'carrier-{number}', bd.Pos(x-29., 0, 0)*tray))
        drive = bd.Pos(x-2.7, 41.5, 22.25)*bd.Box(
            DRIVE_THICKNESS_MM, 69.85, 100.45, align=(bd.Align.MIN,)*3)
        obstacles.append((f'drive-{number}', drive))
    obstacles += [(f'native-{i}', bd.Shape.cast(s)) for i, s in enumerate(board_solids)]
    obstacles = [(label, shape, bounds(shape.wrapped)) for label, shape in obstacles]
    print('Service obstacles:', len(obstacles), flush=True)
    tools = []
    # 裸总成在箱外操作。Ø6杆到达螺丝头前；Ø14短圆柱只代表指尖净空。
    for number, x in enumerate(SATA_X, 1):
        for z in (32.1, 108.7):
            for label, radius, y, length in (('driver-shaft', 3., -4.4, 40.),
                                             ('fingertip', 7., 28.6, 7.)):
                envelope = cylinder(x+.3, y, z, radius, length, 'y')
                measured = intersections(envelope, obstacles)
                tools.append({'kind': label, 'bay': number,
                              'screwCenterMm': [x+.3, 39.1, z],
                              'diameterMm': radius*2, 'axisY': [y, y+length],
                              **measured})
        print('HDD tool checks bay', number, 'complete', flush=True)
    for x in (19.5, 124.5):
        for z in (15.5, 120.5):
            envelope = cylinder(x, 168.7, z, 3., 40., 'y')
            tools.append({'kind': 'rear-fan-driver', 'centerMm': [x, z],
                          'diameterMm': 6., 'axisY': [168.7, 208.7],
                          **intersections(envelope, obstacles)})
    # 顶扇在拆下的盖上固定。工具包络停在螺丝头或螺母接触面外。
    top_obstacles = [('detached-lid',lid().shape),
                     ('top-fan-frame-envelope',bd.Pos(*TOP_FAN_FRAME[:3])*bd.Box(
                         *TOP_FAN_FRAME[3:],align=(bd.Align.MIN,)*3))]
    top_obstacles = [(label,shape,bounds(shape.wrapped)) for label,shape in top_obstacles]
    for x,y in TOP_FAN_HOLES:
        for label,radius,z,length in (('top-fan-driver',3.,193.5,40.),
                                       ('top-fan-nut-tool',4.5,162.9,10.)):
            envelope = cylinder(x,y,z,radius,length)
            tools.append({'kind':label,'centerMm':[x,y],
                          'diameterMm':radius*2,'axisZ':[z,z+length],
                          'assemblyState':'lid detached; tool excludes mating fastener body',
                          **intersections(envelope,top_obstacles)})
    lid_obstacles=[('shell',shell_body),('lid',cover),('top-fan',top_fan().shape)]
    lid_obstacles=[(label,shape,bounds(shape.wrapped)) for label,shape in lid_obstacles]
    for x,y in LID_HOLES:
        envelope=cylinder(x,y,193.5,3.,40.)
        tools.append({'kind':'lid-lock-driver','centerXYmm':[x,y],'diameterMm':6.,
                      'axisZmm':[193.5,233.5],**intersections(envelope,lid_obstacles)})
    report = {
        'checkedAt': datetime.now(timezone.utc).isoformat(),
        'designSha256': sha256((Path(__file__).with_name('design.py')).read_bytes()).hexdigest(),
        'ioSourceSha256': sha256((Path(__file__).with_name('io_geometry.py')).read_bytes()).hexdigest(),
        'pcbInsertBores': board_bores(frame), 'rearFanInsertBores':rear_fan_bores(frame,rear_frame),
        'lidInsertBores':lid_bores(shell_body,cover),
        'toolEnvelopes': tools,
        'materialGeometry': material_comparison(frame, tray, rear_frame),
        'scope': 'Current exact spine/carriers/native board, five 7 mm drive boxes. '
                 'HDD and rear-fan fastening occur with shell absent. Top fan is fastened to a detached lid. Driver shaft is diameter '
                 '6 mm; fingertip is only a static diameter 14 mm short cylinder, not a hand model. '
                 'M2.5x6 engagement assumes a 1.6 mm PCB and no washer. Does not prove '
                 'heat-set insert fit, full hand access, wire route or physical assembly.',
    }
    destination = ROOT/'validation/r3/service-access.json'
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    assert not any(item['overlaps'] for item in tools), '工具包络碰到总成'
    print(json.dumps({'pcbBores': report['pcbInsertBores'],
                      'toolChecks': len(tools),
                      'minimumToolClearanceMm': min(t['minDistanceMm'] for t in tools)},
                     ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
