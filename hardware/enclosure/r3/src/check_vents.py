"""[INPUT]: 导出的上盖与底壳STEP、精修前STEP；check_top_fan的独立布尔测量。
[OUTPUT]: 通风面积、贯通、格栅筋及水平6mm横带的实体检查。
[POS]: 独立检查艺术通风图案；几何开孔面积不代替风量和刚度验证。
[PROTOCOL]: Update this header on change, then check AGENTS.md
"""
from datetime import datetime, timezone
from hashlib import sha256
from math import pi, sqrt
from pathlib import Path
import json
import argparse

from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform

from check_top_fan import boolean, cylinder, axial_surfaces
import validate as geo

ROOT, OUT = geo.ROOT, geo.OUT
BASELINE = ROOT/'work/vent-art-r3/baseline/outputs/redesign-r3'


def centroid(shape):
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    p = props.CentreOfMass()
    return [p.X(), p.Y(), p.Z()]


def mirrored(shape, axis):
    # x=72，或顶盖的y=100；检查实体空洞镜像而非元数据。
    reflection = gp_Trsf()
    if axis == 'x':
        reflection.SetMirror(gp_Ax2(gp_Pnt(72, 0, 0), gp_Dir(1, 0, 0)))
    else:
        reflection.SetMirror(gp_Ax2(gp_Pnt(0, 100, 0), gp_Dir(0, 1, 0)))
    return BRepBuilderAPI_Transform(shape, reflection, True).Shape()


def slice_openings(region, body, thickness):
    openings = boolean(region, body, cut=True)
    area = geo.volume(openings)/thickness
    return openings, area


def band_endpoints(holes):
    # 从实际STEP空洞配对每列槽，不读取设计常量或导出元数据。
    columns = {}
    for slot in geo.solids(holes):
        b = geo.bounds(slot)
        x = round((b[0]+b[3])/2, 6)
        columns.setdefault(x, []).append(b)
    assert len(columns) == 15, '横带检查需要15列槽'
    ends = []
    for x, slots in sorted(columns.items()):
        assert len(slots) == 2, (x, '每列需要上下两段槽')
        lower, upper = sorted(slots, key=lambda b: b[2])
        ends.append({'centerXMm': x, 'lowerSlotTopZMm': lower[5],
                     'upperSlotBottomZMm': upper[2],
                     'bandHeightMm': upper[2]-lower[5]})
    lower = [c['lowerSlotTopZMm'] for c in ends]
    upper = [c['upperSlotBottomZMm'] for c in ends]
    return {'columns': ends, 'lowerSlotTopRangeMm': [min(lower), max(lower)],
            'upperSlotBottomRangeMm': [min(upper), max(upper)],
            'bandHeightRangeMm': [min(c['bandHeightMm'] for c in ends),
                                  max(c['bandHeightMm'] for c in ends)],
            'lowerAlignmentErrorMm': max(lower)-min(lower),
            'upperAlignmentErrorMm': max(upper)-min(upper)}


def check_horizontal_band(body, holes, y):
    result = band_endpoints(holes)
    assert result['lowerAlignmentErrorMm'] < 1e-5, '下段槽端不水平'
    assert result['upperAlignmentErrorMm'] < 1e-5, '上段槽端不水平'
    for col in result['columns']:
        assert abs(col['lowerSlotTopZMm']-67) < 1e-5, col
        assert abs(col['upperSlotBottomZMm']-73) < 1e-5, col
        assert abs(col['bandHeightMm']-6) < 1e-5, col
    # 全宽实体见证条同时检查槽列之间的横带连续材料。
    witness = geo.block(13.8, y, 67, 116.4, .6, 6)
    missing = geo.volume(boolean(witness, body, cut=True))
    assert missing < 1e-5, ('横带实体不连续', missing)
    result['materialWitnessBoundsMm'] = geo.bounds(witness)
    result['materialWitnessMissingMm3'] = missing
    return result


def main():
    lid, shell = (geo.read(OUT/f'{name}.step') for name in ('lid', 'shell'))
    parser = argparse.ArgumentParser(description='检查通风图案；--baseline指定精修前STEP目录')
    parser.add_argument('--baseline', type=Path, default=BASELINE)
    parser.add_argument('--straight-baseline', type=Path,
                        help='拉直前的弧形横带shell.step或所在目录，用作失败对照')
    args = parser.parse_args()
    baseline = args.baseline
    archived_path = ROOT/'validation/r3/baseline-before-art-vents.json'
    archived = json.loads(archived_path.read_text())
    prior = archived['priorVentMeasurement']
    old_top_area = prior['topOpenAreaMm2']
    old_lid = geo.read(baseline/'lid.step') if (baseline/'lid.step').exists() else None
    old_shell = geo.read(baseline/'shell.step') if (baseline/'shell.step').exists() else None
    baseline_inputs = ({name: sha256((baseline/f'{name}.step').read_bytes()).hexdigest()
                        for name in ('lid', 'shell')} if old_lid and old_shell else
                       {'historicalReport': sha256(archived_path.read_bytes()).hexdigest()})
    ring_region = cylinder(72, 100, 191.3, 42, .4)
    rings, top_area = slice_openings(ring_region, lid, .4)
    if old_lid:
        _, old_top_area = slice_openings(cylinder(72, 82, 191.3, 42, .4), old_lid, .4)
    assert len(geo.solids(rings)) == 28
    center = centroid(rings)
    assert abs(center[0]-72) < 1e-5 and abs(center[1]-100) < 1e-5
    top_symmetry = {axis: geo.volume(boolean(rings, mirrored(rings, axis), cut=True))
                    for axis in ('x', 'y')}
    assert max(top_symmetry.values()) < 1e-5
    assert top_area >= old_top_area
    radii = sorted({round(s['radiusMm'], 6) for s in axial_surfaces(lid, 72, 100)})
    # 最内环的r2.8内弧被4mm十字方角完全截去。
    expected = [round(4.4+6*i+delta, 6) for i in range(7) for delta in (-1.6, 1.6)
                if i or delta > 0]
    assert radii == sorted(expected), radii
    probes = []
    for radius in [4.4+6*i for i in range(7)]:
        x, y = 72+radius/sqrt(2), 100+radius/sqrt(2)
        # 连续圆柱从盖内贯通到盖外，两侧0.1mm名义余量。
        probe_radius = .9 if radius < 5 else 1.5
        probe = cylinder(x, y, 191.1, probe_radius, 3)
        gap, overlap = geo.distance(probe, lid), geo.overlap(probe, lid)
        assert overlap < 1e-5 and gap >= .09999, (radius, gap, overlap)
        probes.append({'ringCenterRadiusMm': radius, 'probeDiameterMm': probe_radius*2,
                       'continuousZMm': [191.1, 194.1], 'minWallGapMm': gap,
                       'overlapMm3': overlap})
    spokes = []
    for b in [(30, 98, 191.3, 84, 4, .4), (70, 58, 191.3, 4, 84, .4)]:
        witness = geo.block(*b)
        missing = geo.volume(boolean(witness, lid, cut=True))
        assert missing < 1e-5
        spokes.append({'boundsMm': geo.bounds(witness), 'missingVolumeMm3': missing})
    walls = {}
    for name, y in [('front', 28.6), ('rear', 170.6)]:
        region = geo.block(13, y, 13, 118, .6, 114)
        holes, area = slice_openings(region, shell, .6)
        old_area = prior['lowerWallOpenAreaMm2']
        if old_shell:
            _, old_area = slice_openings(region, old_shell, .6)
        assert len(geo.solids(holes)) == 30, (name, len(geo.solids(holes)))
        assert area >= old_area-1e-4, (name, area, old_area)
        mirror_error = geo.volume(boolean(holes, mirrored(holes, 'x'), cut=True))
        assert mirror_error < 1e-5, (name, mirror_error)
        details = []
        for slot in geo.solids(holes):
            b = geo.bounds(slot)
            assert abs(b[3]-b[0]-4.4) < 1e-5, b
            x, z = (b[0]+b[3])/2, (b[2]+b[5])/2
            bore = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y-2, z), gp_Dir(0, 1, 0)), 1.9, 6).Shape()
            amount = geo.overlap(bore, shell)
            assert amount < 1e-5, (name, b, amount)
            details.append({'boundsMm': b, 'continuousDiameter3_8GaugeOverlapMm3': amount})
        walls[name] = {'openings': len(details), 'openAreaMm2': area,
                       'slotWidthMm': 4.4, 'interColumnWebMm': 3.6,
                       'baselineOpenAreaMm2': old_area, 'areaChangePercent': (area/old_area-1)*100,
                       'mirrorDifferenceMm3': mirror_error, 'slots': details,
                       'horizontalBand': check_horizontal_band(shell, holes, y)}
    assert abs(walls['front']['openAreaMm2']-walls['rear']['openAreaMm2']) < 1e-5
    curved_control = {'performed': False,
                      'scope': 'Supply --straight-baseline to reject the prior curved STEP.'}
    if args.straight_baseline:
        path = args.straight_baseline
        path = path/'shell.step' if path.is_dir() else path
        curved_shell = geo.read(path)
        curved_holes, _ = slice_openings(geo.block(13, 28.6, 13, 118, .6, 114), curved_shell, .6)
        rejected, reason = False, None
        try:
            check_horizontal_band(curved_shell, curved_holes, 28.6)
        except AssertionError as error:
            rejected, reason = True, str(error)
        assert rejected, '拉直前弧形横带未被水平检查拒绝'
        curved_control = {'performed': True, 'rejected': rejected, 'reason': reason,
                          'inputSha256': sha256(path.read_bytes()).hexdigest(),
                          'measuredEndpoints': band_endpoints(curved_holes)}
    upper_region = geo.block(13, 170.6, 142, 118, .6, 27)
    upper_holes, upper_area = slice_openings(upper_region, shell, .6)
    old_upper_area = prior['rearUpperOpenAreaMm2']
    if old_shell:
        _, old_upper_area = slice_openings(upper_region, old_shell, .6)
    assert len(geo.solids(upper_holes)) == 15
    for slot in geo.solids(upper_holes):
        b = geo.bounds(slot)
        assert abs(b[3]-b[0]-4.4) < 1e-5
        gauge = BRepPrimAPI_MakeCylinder(gp_Ax2(
            gp_Pnt((b[0]+b[3])/2, 168, (b[2]+b[5])/2), gp_Dir(0, 1, 0)), 1.9, 6).Shape()
        assert geo.overlap(gauge, shell) < 1e-5
    assert upper_area >= old_upper_area
    upper_symmetry = geo.volume(boolean(upper_holes, mirrored(upper_holes, 'x'), cut=True))
    assert upper_symmetry < 1e-5
    sweep_region = BRepPrimAPI_MakeCylinder(
        gp_Ax2(gp_Pnt(72, 170.6, 68), gp_Dir(0, 1, 0)), 55, .6).Shape()
    _, sweep_area = slice_openings(sweep_region, shell, .6)
    old_sweep_area = prior['rearFanSweepProjectionOpenAreaMm2']
    if old_shell:
        _, old_sweep_area = slice_openings(sweep_region, old_shell, .6)
    assert sweep_area >= old_sweep_area, (sweep_area, old_sweep_area)
    result = {'checkedAt': datetime.now(timezone.utc).isoformat(), 'passed': True,
              'sourceSha256': sha256((ROOT/'hardware/enclosure/r3/src/design.py').read_bytes()).hexdigest(),
              'inputs': {name: sha256((OUT/f'{name}.step').read_bytes()).hexdigest() for name in ('lid', 'shell')},
              'baselineInputs': baseline_inputs,
              'baselineBasis': 'Prior STEP slices' if old_lid and old_shell else 'Archived independent prior STEP measurements with original STEP hashes',
              'top': {'centerXYMm': center[:2], 'openAreaMm2': top_area,
                      'baselineOpenAreaMm2': old_top_area, 'areaChangePercent': (top_area/old_top_area-1)*100,
                      'slotSegments': 28, 'radiiMm': radii, 'radialSlotWidthMm': 3.2,
                      'radialRibWidthMm': 2.8, 'spokeWidthMm': 4,
                      'innermostInnerEndRadiusMm': 2*sqrt(2),
                      'mirrorDifferenceMm3': top_symmetry, 'continuousBoreProbes': probes,
              'solidSpokeWitnesses': spokes}, 'walls': walls,
              'negativeControls': {'curvedMiddleBand': curved_control},
              'rearUpper': {'openings': 15, 'openAreaMm2': upper_area,
                            'baselineOpenAreaMm2': old_upper_area,
                            'areaChangePercent': (upper_area/old_upper_area-1)*100,
                            'mirrorDifferenceMm3': upper_symmetry},
              'rearFanSweepProjection': {'diameterMm': 110, 'centerXZMm': [72, 68],
                                        'openAreaMm2': sweep_area, 'baselineOpenAreaMm2': old_sweep_area,
                                        'scope': 'Wall openings clipped by nominal rotor disk only; hub, frame, blades and pressure drop excluded.'},
              'limits': ['Geometric area is not airflow or cooling performance.',
                         'Outer ring arcs span about 59 mm between spokes; pressure deflection, impact, fan guarding and vibration are untested.',
                         'Rounded slot caps, overhangs, support removal and PETG warpage require slicing and physical trial.']}
    (ROOT/'validation/r3/vents.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
