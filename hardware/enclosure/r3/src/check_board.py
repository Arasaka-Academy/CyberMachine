"""[INPUT]: 原厂 TACO STEP 与 OCCT 8 的实体距离计算。
[OUTPUT]: 主板承托台、螺丝和工具包络的精确净空报告。
[POS]: 独立复核四个孔周围的空间，不用旧报告证明新候选。
[PROTOCOL]: Update this header on change, then check AGENTS.md
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import pi, sqrt
from pathlib import Path

from OCP.Bnd import Bnd_Box
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Trsf, gp_Ax1, gp_Ax2, gp_Pnt, gp_Dir, gp_Vec
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer

ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / 'references/radxa-taco/radxa_taco_3d_stp_v1.61.stp'
HOLES = ((20.1, 60.2), (12.9, 116.95), (105., 60.2), (119.45, 116.9))
VOLUME_TOLERANCE = 1e-7


def bounds(shape):
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box)
    lo, hi = box.CornerMin(), box.CornerMax()
    return [lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()]


def overlap_volume(first, second):
    operation = BRepAlgoAPI_Common(first, second)
    if not operation.IsDone():
        raise RuntimeError('实体交集运算未完成')
    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(operation.Shape(), properties)
    return properties.Mass()


def box_distance(first, second):
    # 包围盒只排除远处实体；最终距离来自实体表面。
    return sqrt(sum(max(first[j]-second[j+3], second[j]-first[j+3], 0)**2
                    for j in range(3)))


def cylinder(x, y, z, radius, height):
    return BRepPrimAPI_MakeCylinder(
        gp_Ax2(gp_Pnt(x, y, z), gp_Dir(0, 0, 1)), radius, height
    ).Shape()


def read_board():
    reader = STEPControl_Reader()
    if int(reader.ReadFile(str(SOURCE))) != 1:
        raise RuntimeError('无法读取原厂 STEP')
    reader.TransferRoots()
    transform = gp_Trsf()
    transform.SetRotation(gp_Ax1(gp_Pnt(), gp_Dir(0, 1, 0)), pi)
    transform.SetTranslationPart(gp_Vec(72.1, 120, 135))
    board = BRepBuilderAPI_Transform(reader.OneShape(), transform, True).Shape()
    solids = []
    explorer = TopExp_Explorer(board, TopAbs_SOLID)
    while explorer.More():
        solids.append(explorer.Current())
        explorer.Next()
    if len(solids) != 730:
        raise RuntimeError(f'原厂实体数量变化：{len(solids)}')
    return board, solids


def inspect_envelope(envelope, solids, boxes, include_pcb=False):
    measured_box = bounds(envelope)
    minimum, nearest = float('inf'), None
    overlaps = []
    for index in range(0 if include_pcb else 1, len(solids)):
        if box_distance(measured_box, boxes[index]) > minimum:
            continue
        query = BRepExtrema_DistShapeShape(envelope, solids[index])
        query.Perform()
        if not query.IsDone():
            raise RuntimeError(f'实体 {index} 的距离计算未完成')
        distance = query.Value()
        if distance < minimum:
            minimum, nearest = distance, index
        if distance < 1e-6:
            volume = overlap_volume(envelope, solids[index])
            if volume > VOLUME_TOLERANCE:
                overlaps.append({'solid': index, 'volumeMm3': volume})
    return {'minDistanceMm': minimum, 'nearestSolid': nearest, 'overlaps': overlaps}


def main():
    board, solids = read_board()
    boxes = [bounds(solid) for solid in solids]
    print('Fresh native STEP solids:', len(solids), flush=True)
    checks = []
    envelopes = (
        ('support', 116., 17.4, 2.5, False),
        ('screw-head', 135., 1.5, 2.25, False),
        ('driver-shaft', 136.5, 42., 3., False),
        ('screw-shank', 128.9, 7.6, 1.25, True),
    )
    for kind, z, height, radius, include_pcb in envelopes:
        for number, (x, y) in enumerate(HOLES, 1):
            result = inspect_envelope(cylinder(x, y, z, radius, height), solids, boxes, include_pcb)
            checks.append({'kind': kind, 'hole': number, 'center': [x, y],
                           'z': [z, z+height], 'diameter': radius*2, **result})
            print(kind, number, round(result['minDistanceMm'], 5), result['overlaps'], flush=True)

    # 故意加粗螺杆，确认检测确实能发现孔壁干涉。
    bad_shank = cylinder(*HOLES[2], 132.9, 2., 2.6)
    negative_control = overlap_volume(bad_shank, solids[0])
    assert negative_control > .1, '检测未能识别故意植入的 PCB 孔壁干涉'
    report = {
        'checkedAt': datetime.now(timezone.utc).isoformat(),
        'source': str(SOURCE.relative_to(ROOT)), 'sha256': sha256(SOURCE.read_bytes()).hexdigest(),
        'nativeSolids': len(solids), 'pcbBounds': boxes[0], 'nativeBounds': bounds(board),
        'checks': checks, 'negativeControlOverlapMm3': negative_control,
        'scope': 'Fresh exact B-rep cylinders. Support/head/tool exclude PCB seat contact; '
                 'shanks also check PCB hole walls. Does not validate absent CM5/cooler/wifi, '
                 'real solder tails, actual hardware/tool geometry or printed fits.',
    }
    destination = ROOT / 'validation/r3/board-clearance.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    assert not any(check['overlaps'] for check in checks), '发现包络与主板实体相交'


if __name__ == '__main__':
    main()
