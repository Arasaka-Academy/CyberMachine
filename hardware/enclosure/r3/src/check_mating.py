"""[INPUT]: 本轮底壳与上盖 STEP；validate 的实体读取和测量。
[OUTPUT]: 四止口承台、四锁盖压套接触面积、外观缝与单侧间隙。
[POS]: 独立复核合盖硬限位，不从预览图读取尺寸。
[PROTOCOL]: Update this header on change, then check AGENTS.md
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from math import acos,sqrt,pi

from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

import validate as geometry

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'outputs/redesign-r3'


def intersection(first, second):
    operation = BRepAlgoAPI_Common(first, second)
    if not operation.IsDone():
        raise RuntimeError('止口交集测量未完成')
    return operation.Shape()


def seat_faces(shape,z):
    faces = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face(explorer.Current())
        bounds = geometry.bounds(face)
        if abs(bounds[2]-z) < 1e-6 and abs(bounds[5]-z) < 1e-6:
            faces.append(face)
        explorer.Next()
    return faces


def contact_area(shell,lid,z,region=None):
    area=0.
    for shell_face in seat_faces(shell,z):
        for lid_face in seat_faces(lid,z):
            common=intersection(shell_face,lid_face)
            if region is not None:
                common=intersection(common,region)
            properties=GProp_GProps()
            BRepGProp.SurfaceProperties_s(common,properties)
            area+=properties.Mass()
    return area


def main():
    shell = geometry.read(OUT / 'shell.step')
    lid = geometry.read(OUT / 'lid.step')
    contact = intersection(shell, lid)
    # 实体交集在零厚度接触处不保留面，面积由共面面片求交。
    spigot_area=contact_area(shell,lid,169.3)
    lock_seats=[]
    for x,y in ((3.,48.),(141.,48.),(3.,152.),(141.,152.)):
        area=contact_area(shell,lid,174.,geometry.block(x-7,y-7,173.9,14,14,.2))
        expected=pi*(6**2-2.05**2)-(36*acos(5.2/6)-5.2*sqrt(36-5.2**2))
        assert abs(area-expected)<1e-4,(x,y,area,expected)
        lock_seats.append({'centerXYmm':[x,y],'contactZmm':174.,'areaMm2':area,
                           'expectedAnnularAreaMm2':expected})
    lock_area=sum(item['areaMm2'] for item in lock_seats)
    outside = geometry.block(71.5, 28, 173.9, 1, 1, 1)
    side = geometry.block(-5,80,171,10,1,1)
    gap = geometry.distance(intersection(shell, outside), intersection(lid, outside))
    side_gap = geometry.distance(intersection(shell, side), intersection(lid, side))
    volume = geometry.volume(contact)
    assert abs(spigot_area-76.8)<1e-4 and abs(volume)<1e-6,'止口未正确落座'
    assert abs(gap-.3) < 1e-6, '名义外观缝改变'
    assert abs(side_gap-.35) < 1e-6, '止口单侧间隙改变'
    result = {
        'checkedAt': datetime.now(timezone.utc).isoformat(),
        'inputs': {name: sha256((OUT/name).read_bytes()).hexdigest()
                   for name in ('shell.step', 'lid.step')},
        'overlapMm3':volume,'seatContactAreaMm2':spigot_area+lock_area,
        'spigotSeatContactAreaMm2':spigot_area,'lidLockSeatContactAreaMm2':lock_area,
        'lidLockSeats':lock_seats,
        'externalGapMm': gap, 'spigotSingleSideGapMm': side_gap,
        'scope': 'Exact B-rep nominal mating only. Printed shrinkage, '
                 'warpage and fit feel are not measured.',
    }
    destination = ROOT / 'validation/r3/mating.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
