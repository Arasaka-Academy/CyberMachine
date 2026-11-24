"""[INPUT]: 最终总成、主架、后扇框和盘托STEP及哈希；打印优化前基线。
[OUTPUT]: 五块7mm盘、尖拱、定位键、35mm紧固栈和材料加减报告。
[POS]: 独立复核加固内框，不调用design生成待测实体；不推断打印件刚度。
[PROTOCOL]: Update this header on change, then check AGENTS.md
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import hypot
from pathlib import Path

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec

import validate as geo

ROOT, OUT = geo.ROOT, geo.OUT
BOARD_HOLES = ((20.1, 60.2), (12.9, 116.95), (105., 60.2), (119.45, 116.9))


def boolean(first, second, cut=False):
    operation = (BRepAlgoAPI_Cut if cut else BRepAlgoAPI_Common)(first, second)
    assert operation.IsDone(), '内框布尔测量失败'
    return operation.Shape()


def close(actual, expected, tolerance=1e-5):
    assert abs(actual-expected) < tolerance, (actual, expected)


def clipped(shape, region):
    result = boolean(shape, region)
    assert geo.volume(result) > 1e-5, '测量截面为空'
    return result


def diagonal_probe(x):
    # 在斜撑中点截取10mm长、20mm宽的棱柱，避开周框和孔下直带。
    dy, dz = 55.8, 90.
    length = hypot(dy, dz)
    uy, uz = dy/length, dz/length
    ny, nz = -uz, uy
    polygon = BRepBuilderAPI_MakePolygon()
    for along, across in ((-5, -10), (5, -10), (5, 10), (-5, 10)):
        polygon.Add(gp_Pnt(x-1, 92.1+along*uy+across*ny, 63+along*uz+across*nz))
    polygon.Close()
    face = BRepBuilderAPI_MakeFace(polygon.Wire()).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(6, 0, 0)).Shape()


def support_tips(spine):
    records = []
    for x, y in BOARD_HOLES:
        matching = []
        explorer = TopExp_Explorer(spine, TopAbs_FACE)
        while explorer.More():
            face = TopoDS.Face(explorer.Current())
            surface = BRepAdaptor_Surface(face)
            if surface.GetType() == GeomAbs_Cylinder:
                cylinder = surface.Cylinder()
                point, direction = cylinder.Location(), cylinder.Axis().Direction()
                if (abs(point.X()-x) < 1e-5 and abs(point.Y()-y) < 1e-5
                        and abs(direction.Z()) > .999999 and abs(cylinder.Radius()-2.5) < 1e-5):
                    matching.append(geo.bounds(face))
            explorer.Next()
        assert matching, (x, y)
        top = max(b[5] for b in matching)
        close(top, 133.4)
        records.append({'xyMm': [x, y], 'diameterMm': 5., 'topZMm': top})
    return records


def reinforcement_regions(spine):
    records = []
    for index, (x, y) in enumerate(BOARD_HOLES):
        for label, z, r1, r2, height in (('lower-45deg-ramp', 103.5, 1.2, 5.5, 4.3),
                                         ('upper-root', 107.8, 5.5, 3.5, 8.2)):
            region = BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(x, y, z), gp_Dir(0, 0, 1)), r1, r2, height).Shape()
            if y > 110:
                region = boolean(region, geo.block(x-10, y-10, z-1, 20, 114.4-(y-10), height+2), cut=True)
            else:
                clip_x = 23.95 if index == 0 else 109.95
                region = boolean(region, geo.block(clip_x, y-10, z-1, 20, 20, height+2), cut=True)
            missing = max(0., geo.volume(boolean(region, spine, cut=True)))
            assert missing < .001, (index, label, missing)
            records.append({'feature': label, 'support': index+1, 'requiredVolumeMm3': geo.volume(region),
                            'missingMaterialMm3': missing})
    for index, points in enumerate((((9.75,8),(27.75,8),(9.75,26)),
                                     ((135.75,8),(117.75,8),(135.75,26)),
                                     ((9.75,128),(27.75,128),(9.75,110)),
                                     ((135.75,128),(117.75,128),(135.75,110))), 1):
        polygon = BRepBuilderAPI_MakePolygon()
        for x, z in points:
            polygon.Add(gp_Pnt(x, 134, z))
        polygon.Close()
        region = BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(polygon.Wire()).Face(), gp_Vec(0, 4, 0)).Shape()
        # 原有风扇铜套孔穿入三角肋，预期材料必须扣除这些设计孔。
        hole_x, hole_z = (19.5 if index % 2 else 124.5), (15.5 if index <= 2 else 120.5)
        bore = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(hole_x, 131.6, hole_z), gp_Dir(0, 1, 0)), 2.05, 6.5).Shape()
        region = boolean(region, bore, cut=True)
        for base_x in (10., 134.):
            base_bore = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(base_x, 132, 7.9), gp_Dir(0, 0, 1)), 2.05, 4.9).Shape()
            region = boolean(region, base_bore, cut=True)
        missing = max(0., geo.volume(boolean(region, spine, cut=True)))
        assert missing < .001, (index, missing)
        records.append({'feature': 'rear-fan-corner-gusset', 'corner': index,
                        'requiredVolumeMm3': geo.volume(region), 'missingMaterialMm3': missing})
    return records


def baseline_comparison(spine, rear_frame, carrier, directory):
    if directory:
        metadata_path=directory/'metadata.json'
        previous=json.loads(metadata_path.read_text())
        result={'baselineSourceSha256':previous['sourceSha256'],
                'baselineMetadataSha256':sha256(metadata_path.read_bytes()).hexdigest(),
                'baselineDirectory':str(directory.relative_to(ROOT) if directory.is_relative_to(ROOT) else directory)}
        for name,current_parts,old_names in (
                ('spine',(spine,rear_frame),('spine','rear-fan-frame')),
                ('carrier',(carrier,),('carrier',))):
            old_parts=[]
            hashes={}
            for old_name in old_names:
                path=directory/f'{old_name}.step'
                digest=sha256(path.read_bytes()).hexdigest()
                assert digest==previous['exportedStepSha256'][path.name]
                old_parts.append(geo.read(path));hashes[path.name]=digest
            old_volume=sum(geo.volume(part) for part in old_parts)
            current_volume=sum(geo.volume(part) for part in current_parts)
            removed,added=0.,0.
            for original,subtractors in ((old_parts,current_parts),(current_parts,old_parts)):
                measured=0.
                for part in original:
                    remaining=part
                    for other in subtractors:
                        remaining=boolean(remaining,other,cut=True)
                    measured+=max(0.,geo.volume(remaining))
                if original is old_parts:
                    removed=measured
                else:
                    added=measured
            close(added-removed,current_volume-old_volume,.01)
            result[name]={'baselineVolumeMm3':old_volume,'currentVolumeMm3':current_volume,
                'netAddedVolumeMm3':current_volume-old_volume,
                'volumeChangePercent':100*(current_volume/old_volume-1),
                'removedMaterialMm3':removed,'addedMaterialMm3':added,
                'baselineStepSha256':hashes,'comparisonBasis':'Direct sequential per-solid STEP differences with volume identity'}
        result['spine'].update({'mainSpineVolumeMm3':geo.volume(spine),
                                'separateRearFrameVolumeMm3':geo.volume(rear_frame)})
        close(result['carrier']['netAddedVolumeMm3'],0.,.001)
        return result
    archive_path = ROOT/'validation/r3/baseline-before-print-balance.json'
    archive = json.loads(archive_path.read_text())
    previous = archive['reports']['geometry.json']
    result = {'baselineSourceSha256': previous['sourceSha256'],
              'archiveSha256': sha256(archive_path.read_bytes()).hexdigest()}
    for name, shape in (('spine', geo.compound([spine,rear_frame])), ('carrier', carrier)):
        old_volume = previous['parts'][name]['volumeMm3']
        current_volume = geo.volume(shape)
        result[name] = {'baselineVolumeMm3': old_volume, 'currentVolumeMm3': current_volume,
                        'netAddedVolumeMm3': current_volume-old_volume,
                        'volumeChangePercent': 100*(current_volume/old_volume-1)}
        path = directory/f'{name}.step' if directory else None
        if path:
            assert path.is_file(), f'显式基线缺少STEP：{path}'
            baseline_digest = sha256(path.read_bytes()).hexdigest()
            assert baseline_digest == previous['candidateStepSha256'][name], (name, baseline_digest)
            old = geo.read(path)
            assert BRepCheck_Analyzer(old).IsValid() and len(geo.solids(old)) == 1
            close(geo.volume(old), old_volume, .001)
            # 逐实体布尔避免共面复合体直接差集漏算材料；体积恒等式复核。
            current_parts=(spine,rear_frame) if name=='spine' else (carrier,)
            remaining=old
            for part in current_parts:
                remaining=boolean(remaining,part,cut=True)
            removed=max(0.,geo.volume(remaining))
            added=sum(max(0.,geo.volume(boolean(part,old,cut=True))) for part in current_parts)
            close(added-removed,current_volume-old_volume,.01)
            result[name].update({'baselineStepSha256': baseline_digest,
                                 'removedMaterialMm3': removed, 'addedMaterialMm3': added,
                                 'comparisonBasis': 'Direct STEP boolean difference'})
        else:
            result[name]['comparisonBasis'] = 'Archived pre-print-balance volume; no add-only boolean claim'
    result['spine'].update({'mainSpineVolumeMm3':geo.volume(spine),
                           'separateRearFrameVolumeMm3':geo.volume(rear_frame),
                           'currentVolumeIncludes':'main spine plus separate rear fan frame'})
    close(result['carrier']['netAddedVolumeMm3'], 0., .001)
    return result


def roof_regions(spine):
    records=[]
    for x in (17.7,103.8):
        for a,b in ((43.,56.2),(64.2,120.)):
            mid,top=(a+b)/2,108.
            low=top-(b-a)/2
            for points in (((a,low),(mid,top),(a,top)),((b,low),(mid,top),(b,top))):
                polygon=BRepBuilderAPI_MakePolygon()
                for y,z in points:
                    polygon.Add(gp_Pnt(x,y,z))
                polygon.Close()
                region=BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(polygon.Wire()).Face(),gp_Vec(3.6,0,0)).Shape()
                missing=max(0.,geo.volume(boolean(region,spine,cut=True)))
                assert missing<.001,(x,a,missing)
            records.append({'webXmm':x,'windowYmm':[a,b],'slopeStartZmm':low,
                            'apexZmm':top,'angleFromHorizontalDeg':45.,
                            'missingMaterialMm3':missing})
    return records


def rear_joint(spine,frame):
    assert BRepCheck_Analyzer(frame).IsValid() and len(geo.solids(frame))==1
    close(geo.overlap(spine,frame),0.,1e-5)
    records=[]
    for x in (12.75,132.75):
        key=clipped(frame,geo.block(x-2,136,65,4,2,6))
        b=geo.bounds(key)
        for actual,expected in zip(b,(x-1.5,136.5,65.5,x+1.5,138,70.5)):
            close(actual,expected)
        close(geo.volume(key),22.5,.001)
        pocket=geo.block(x-1.799,136.201,65.201,3.598,1.799,5.598)
        close(geo.overlap(spine,pocket),0.,1e-5)
        # 五个内壁见证片分别测0.3mm间隙；开口面Y138用于贴合。
        witnesses=[geo.block(x-2,136.5,65.5,.2,1.4,5),
                   geo.block(x+1.8,136.5,65.5,.2,1.4,5),
                   geo.block(x-1.5,136.5,65,3,1.4,.2),
                   geo.block(x-1.5,136.5,70.8,3,1.4,.2),
                   geo.block(x-1.5,136.0,65.5,3,.2,5)]
        clearances=[]
        for witness in witnesses:
            wall=clipped(spine,witness)
            gap=geo.distance(key,wall)
            close(gap,.3)
            clearances.append(gap)
        oversized=geo.block(x-1.9,136.5,65.5,3.8,1.5,5)
        planted=geo.overlap(spine,oversized)
        assert planted>1.,planted
        records.append({'centerXZmm':[x,68.],'maleBoundsMm':b,'maleVolumeMm3':geo.volume(key),
            'pocketBoundsMm':[x-1.8,136.2,65.2,x+1.8,138.,70.8],
            'measuredSideEndFloorClearanceMm':clearances,
            'remainingSidewallMm':1.2,'oversizedKeyFailureControlOverlapMm3':planted})
    bores=[]
    for x in (19.5,124.5):
        for z in (15.5,120.5):
            pilot=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x,131.601,z),gp_Dir(0,1,0)),2.049,6.399).Shape()
            floor=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x,131.5,z),gp_Dir(0,1,0)),1.5,.099).Shape()
            clearance=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x,138.001,z),gp_Dir(0,1,0)),1.699,3.998).Shape()
            shank=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x,132,z),gp_Dir(0,1,0)),1.5,35).Shape()
            assert geo.overlap(spine,pilot)<1e-5 and geo.overlap(spine,floor)>.1
            assert geo.overlap(frame,clearance)<1e-5
            assert geo.overlap(spine,shank)<1e-5 and geo.overlap(frame,shank)<1e-5
            bores.append({'centerXZmm':[x,z],'mainPilotYmm':[131.6,138.],
                'mainPilotDiameterMm':4.1,'frameClearanceYmm':[138.,142.],
                'frameClearanceDiameterMm':3.4,'screwLengthMm':35.,
                'underHeadYmm':167.,'tipYmm':132.,'floorAllowanceMm':.4})
    return {'frameBoundsMm':geo.bounds(frame),'mainFrameOverlapMm3':geo.overlap(spine,frame),
            'keys':records,'bores':bores,'newFasteners':0,'newInserts':0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', type=Path, help='打印优化前分件STEP目录；缺省只比较归档体积')
    args = parser.parse_args()
    paths = {name: OUT/name for name in ('spine.step','rear-fan-frame.step','carrier.step','CyberMachine-r3-candidate.step')}
    metadata = json.loads((OUT/'metadata.json').read_text())
    source_digest = sha256((Path(__file__).parent/'design.py').read_bytes()).hexdigest()
    assert metadata['sourceSha256'] == source_digest
    assert metadata['ioSourceSha256'] == sha256((Path(__file__).parent/'io_geometry.py').read_bytes()).hexdigest()
    for name, path in paths.items():
        assert metadata['exportedStepSha256'][name] == sha256(path.read_bytes()).hexdigest(), name
    spine,rear_frame,carrier,assembly = (geo.read(path) for path in paths.values())
    assert BRepCheck_Analyzer(spine).IsValid() and len(geo.solids(spine)) == 1
    drives = []
    for shape in geo.solids(assembly):
        b = geo.bounds(shape)
        if (abs(b[1]-41.5) < 1e-5 and abs(b[2]-22.25) < 1e-5
                and abs(b[4]-111.35) < 1e-5 and abs(b[5]-122.7) < 1e-5):
            close(b[3]-b[0], 7.)
            close(geo.volume(shape), 7*69.85*100.45, .001)
            drives.append((b[0], shape))
    drives.sort(key=lambda item: item[0])
    assert len(drives) == 5, len(drives)
    drive_records, carrier_checks = [], []
    for index, ((negative_x, drive), sata_x) in enumerate(zip(drives, geo.SATA_X), 1):
        close(negative_x, sata_x-2.7)
        overlap = geo.overlap(spine, drive)+geo.overlap(rear_frame,drive)
        assert overlap < 1e-4, (index, overlap)
        drive_records.append({'bay': index, 'sataXmm': sata_x, 'boundsMm': geo.bounds(drive),
                              'thicknessMm': geo.bounds(drive)[3]-negative_x,
                              'spineOverlapMm3': overlap})
        translated = geo.moved(carrier, (sata_x-29, 0, 0))
        overlap = geo.overlap(spine, translated)+geo.overlap(rear_frame,translated)
        assert overlap < 1e-4, (index, overlap)
        carrier_checks.append({'bay': index, 'spineOverlapMm3': overlap,
                               'spineMinDistanceMm': geo.distance(spine, translated)})
    sections = []
    for x in (17.7, 103.8):
        web = clipped(spine, geo.block(x-1, 36, 60, 6, 2, 2))
        b = geo.bounds(web)
        thickness = b[3]-b[0]
        close(thickness, 3.6)
        diagonal = clipped(spine, diagonal_probe(x))
        width = geo.volume(diagonal)/(10*thickness)
        close(width, 8., .001)
        sections.append({'negativeXmm': b[0], 'webThicknessMm': thickness,
                         'diagonalWidthMm': width, 'diagonalCrossSectionAreaMm2': width*thickness})
    base = clipped(spine, geo.block(65, 36, 7, 10, 2, 12))
    base_bounds = geo.bounds(base)
    close(base_bounds[2], 8.)
    close(base_bounds[5], 14.)
    crossbeam = geo.block(7, 70, 8, 130, 8, 6)
    crossbeam_missing = max(0., geo.volume(boolean(crossbeam, spine, cut=True)))
    assert crossbeam_missing < .001, crossbeam_missing
    beam_gap = min(geo.distance(crossbeam, geo.moved(carrier, (x-29, 0, 0))) for x in geo.SATA_X)
    close(beam_gap, 5.85)
    uprights = []
    for x in (9.75, 129.75):
        b = geo.bounds(clipped(spine, geo.block(x-1, 130, 65, 9, 2, 5)))
        close(b[3]-b[0], 6.)
        uprights.append({'xMm': [b[0], b[3]], 'thicknessMm': b[3]-b[0]})
    stop = geo.bounds(clipped(spine, geo.block(74, 115, 20, 4, 4, 10)))
    close(stop[2], 22.25)
    close(stop[5], 28.25)
    base_regions=[]
    for x in (13.5,124.5):
        required=geo.block(x,40.6,8,6,83.4,6)
        missing=max(0.,geo.volume(boolean(required,spine,cut=True)))
        assert missing<.001,(x,missing)
        base_regions.append({'feature':'moved-side-beam','boundsMm':geo.bounds(required),'missingMaterialMm3':missing})
    for points in (((10.,36.),(24.,36.),(18.,50.)),((134.,36.),(120.,36.),(126.,50.))):
        polygon=BRepBuilderAPI_MakePolygon()
        for x,y in points:
            polygon.Add(gp_Pnt(x,y,8))
        polygon.Close()
        required=BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(polygon.Wire()).Face(),gp_Vec(0,0,6)).Shape()
        # 脚根原有铜套孔是角板中的预期空洞。
        for x in (10.,134.):
            bore=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x,36,7.9),gp_Dir(0,0,1)),2.05,4.9).Shape()
            required=boolean(required,bore,cut=True)
        missing=max(0.,geo.volume(boolean(required,spine,cut=True)))
        assert missing<.001,missing
        base_regions.append({'feature':'front-foot-gusset','xyMm':points,'missingMaterialMm3':missing})
    result = {'checkedAt': datetime.now(timezone.utc).isoformat(), 'passed': True,
              'sourceSha256': source_digest,
              'metadataSha256': sha256((OUT/'metadata.json').read_bytes()).hexdigest(),
              'inputs': {name: sha256(path.read_bytes()).hexdigest() for name, path in paths.items()},
              'driveSpecification': {'count': 5, 'thicknessMm': 7, 'datum': 'negative-X', 'actualSolids': drive_records},
              'sections': {'longitudinalFrames': sections, 'baseZmm': [base_bounds[2], base_bounds[5]],
                           'rearFanUprights': uprights},
              'crossbeam': {'boundsMm': geo.bounds(crossbeam), 'requiredVolumeMm3': geo.volume(crossbeam),
                            'missingMaterialMm3': crossbeam_missing, 'minCarrierDistanceMm': beam_gap},
              'boardSupportTips': support_tips(spine), 'rearStopZmm': [stop[2], stop[5]],
              'reinforcementRegions': reinforcement_regions(spine),
              'windowRoofs':roof_regions(spine),'rearFanJoint':rear_joint(spine,rear_frame),
              'baseMountRegions':base_regions,
              'carrierChecks': carrier_checks,
              'materialComparison': baseline_comparison(spine,rear_frame,carrier,args.baseline),
              'limits': ['Nominal generic HDD bodies; exact purchased drive mating and screw depth remain unverified.',
                         'Section thickness, material addition and clearance are geometric evidence only.',
                         'No stiffness, fatigue, impact, vibration, physical assembly or thermal validation.']}
    (ROOT/'validation/r3/frame.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
