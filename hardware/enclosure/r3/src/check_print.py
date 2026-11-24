"""[INPUT]: 最终五盘G-code、3MF、预设和printing.json。
[OUTPUT]: 独立哈希、支撑设置持久化、禁区、路径间距与后框零支撑证据。
[POS]: R3独立切片审核；读取切片产物并输出正式数字证据。
[PROTOCOL]: Update this header on change, then check AGENTS.md
"""
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import atan2, cos, hypot, inf, pi, sin
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[4]
FINAL = ROOT/'outputs/print-r3'
NUMBER = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def fresh_bounds():
    return [[inf]*3, [-inf]*3]


def extend(bounds, points, radius=0.):
    for point in points:
        for axis in range(3):
            pad = radius if axis < 2 else 0.
            bounds[0][axis] = min(bounds[0][axis], point[axis]-pad)
            bounds[1][axis] = max(bounds[1][axis], point[axis]+pad)


def metadata(element):
    return {m.attrib['key']: m.attrib['value'] for m in element.findall('metadata') if 'key' in m.attrib}


def arc_points(before, after, values, code):
    points = [before, after]
    if code not in ('G2', 'G3'):
        return points
    assert 'R' not in values and any(k in values for k in ('I', 'J'))
    center = (before[0]+values.get('I', 0), before[1]+values.get('J', 0))
    a = atan2(before[1]-center[1], before[0]-center[0])
    b = atan2(after[1]-center[1], after[0]-center[0])
    direction = 1 if code == 'G3' else -1
    sweep = (direction*(b-a)) % (2*pi)
    if hypot(after[0]-before[0], after[1]-before[1]) < 1e-8:
        sweep = 2*pi
    radius = max(hypot(before[0]-center[0], before[1]-center[1]),
                 hypot(after[0]-center[0], after[1]-center[1]))
    for angle in [0., pi/2, pi, 3*pi/2]:
        if (direction*(angle-a)) % (2*pi) <= sweep+1e-8:
            points.extend([(center[0]+radius*cos(angle), center[1]+radius*sin(angle), z)
                           for z in [before[2], after[2]]])
    return points


def main():
    report_path = ROOT/'validation/r3/printing.json'
    report = json.loads(report_path.read_text())
    assert report['passed'] and report['plateCount'] == 5 and report['pieceCount'] == 9
    assert report['projectSha256'] == digest(FINAL/'CyberMachine-r3-print-candidate.gcode.3mf')
    assert report['resultSha256'] == digest(FINAL/'result.json')
    assert report['sourceSha256'] == digest(ROOT/'hardware/enclosure/r3/src/design.py')
    assert report['checkerSha256'] == digest(ROOT/'hardware/enclosure/r3/src/slice_candidates.py')
    assert report['metadataSha256'] == digest(ROOT/'outputs/redesign-r3/metadata.json')
    assert report['meshReportSha256'] == digest(ROOT/'validation/r3/mesh.json')
    preset_paths = {path.name: path for path in (FINAL/'presets').glob('*.json')}
    assert set(preset_paths) == set(report['presetHashes']) == {'machine.json', 'process.json', 'filament.json'}
    for name, path in preset_paths.items():
        assert digest(path) == report['presetHashes'][name], f'预设与切片报告不一致：{name}'
    tracked = [report_path, FINAL/'result.json', FINAL/'print-plan.json',
               FINAL/'CyberMachine-r3-print-candidate.gcode.3mf']
    tracked.extend(FINAL/f'plate_{pid}.gcode' for pid in range(1, 6))
    tracked.extend(preset_paths.values())
    initial_hashes = {str(p.relative_to(ROOT)): digest(p) for p in tracked}
    machine = json.loads((FINAL/'presets/machine.json').read_text())
    assert machine['bed_exclude_area'] == ['0x0', '18x0', '18x28', '0x28']
    assert machine['printable_area'] == ['0x0', '256x0', '256x256', '0x256']
    plates = []
    with zipfile.ZipFile(FINAL/'CyberMachine-r3-print-candidate.gcode.3mf') as archive:
        config = ET.fromstring(archive.read('Metadata/model_settings.config'))
        objects = {o.attrib['id']: o for o in config.findall('object')}
        project = json.loads(archive.read('Metadata/project_settings.config'))
        assert project['print_sequence'] == 'by layer'
        for plate_element in config.findall('plate'):
            pid = int(metadata(plate_element)['plater_id'])
            plate_report = next(p for p in report['plates'] if p['plate'] == pid)
            gcode = FINAL/f'plate_{pid}.gcode'
            raw = gcode.read_bytes()
            assert sha256(raw).hexdigest() == plate_report['gcodeSha256']
            assert archive.read(f'Metadata/plate_{pid}.gcode') == raw
            instances = {}
            for instance in plate_element.findall('model_instance'):
                values = metadata(instance)
                obj = objects[values['object_id']]
                part_values = metadata(obj.find('part'))
                obj_values = metadata(obj)
                support_type = obj_values.get('support_type', project['support_type'])
                if part_values['source_file'] == 'lid-print.stl':
                    assert support_type == 'normal(auto)', '上盖普通支撑未保存在3MF对象设置中'
                matrix = list(map(float, part_values['matrix'].split()))
                assert [matrix[n] for n in [0,1,2,4,5,6,8,9,10]] == [1.,0.,0.,0.,1.,0.,0.,0.,1.]
                instances[values['identify_id']] = {'name': metadata(obj)['name'],
                    'sourceFile': part_values['source_file'], 'enableSupport': obj_values['enable_support'],
                    'savedSupportType': support_type}
            text = raw.decode()
            assert re.search(r'^G21\b', text, re.M), 'G-code未声明毫米'
            density = float(re.search(r'^; filament_density: ([\d.]+)', text, re.M)[1])
            diameter = float(re.search(r'^; filament_diameter: ([\d.]+)', text, re.M)[1])
            factor = pi*(diameter/2)**2*density/1000
            assert not re.search(r'^G(?:18|19|20|90\.1)\b|^M200\b|^G1[01]\b', text, re.M)
            xyz, epos, debt, relative, absolute = (0.,0.,0.), 0., 0., False, True
            feature, identity, line_width = 'Custom', None, .5
            masses = defaultdict(lambda: defaultdict(float))
            by_object = defaultdict(fresh_bounds)
            center_bounds, material_bounds, support_bounds = fresh_bounds(), fresh_bounds(), fresh_bounds()
            exclude_clearance, minimum_bed_margin, forbidden, segments, arc_count = inf, inf, 0, 0, 0
            for line in text.splitlines():
                if line.startswith('; FEATURE: '): feature = line[11:]
                if line.startswith('; OBJECT_ID: '): identity = line.split(': ', 1)[1]
                if line.startswith('; LINE_WIDTH: '): line_width = float(line.split(': ', 1)[1])
                command = line.split(';', 1)[0].strip()
                match = re.match(r'^([GM])(\d+)\b', command)
                if not match: continue
                code = match[1]+str(int(match[2]))
                values = {k: float(v) for k,v in re.findall(r'\b([XYZEFIJR])('+NUMBER+r')', command)}
                if code in ('M82', 'M83'): relative = code == 'M83'
                elif code in ('G90', 'G91'): absolute = code == 'G90'
                elif code == 'G92':
                    epos = values.get('E', epos)
                    xyz = tuple(values.get(a, xyz[n]) for n,a in enumerate('XYZ'))
                elif code in ('G0', 'G1', 'G2', 'G3'):
                    before = xyz
                    xyz = tuple(values.get(a, xyz[n]) if absolute else xyz[n]+values.get(a,0.) for n,a in enumerate('XYZ'))
                    if 'E' not in values: continue
                    delta = values['E'] if relative else values['E']-epos
                    epos = epos+delta if relative else values['E']
                    if delta < 0: debt -= delta; continue
                    repay = min(debt, delta); debt -= repay; delta -= repay
                    moving = hypot(xyz[0]-before[0],xyz[1]-before[1]) > 1e-8 or code in ('G2','G3') and any(k in values for k in ('I','J','R'))
                    if not moving or delta <= 1e-10: continue
                    masses[identity][feature] += delta*factor
                    if feature in ('Custom','Flush'): continue
                    assert identity in instances, (pid, identity)
                    points = arc_points(before, xyz, values, code)
                    segments += 1; arc_count += code in ('G2','G3')
                    extend(center_bounds, points); extend(material_bounds, points, line_width/2)
                    extend(by_object[identity], points, line_width/2)
                    if feature.startswith('Support'): extend(support_bounds, points)
                    local = fresh_bounds(); extend(local, points, line_width/2)
                    margin = min(local[0][0],local[0][1],256-local[1][0],256-local[1][1])
                    minimum_bed_margin = min(minimum_bed_margin, margin)
                    assert margin >= -1e-5 and local[0][2] >= 0 and local[1][2] <= 250
                    dx = max(local[0][0]-18, -local[1][0], 0.)
                    dy = max(local[0][1]-28, -local[1][1], 0.)
                    clearance = hypot(dx,dy)
                    exclude_clearance = min(exclude_clearance, clearance)
                    if clearance <= 0: forbidden += 1
            assert forbidden == 0, (pid, forbidden)
            collisions, pair_gaps = [], []
            ids = list(by_object)
            for n,left in enumerate(ids):
                for right in ids[n+1:]:
                    a,b = by_object[left],by_object[right]
                    dx = max(a[0][0]-b[1][0],b[0][0]-a[1][0],0.)
                    dy = max(a[0][1]-b[1][1],b[0][1]-a[1][1],0.)
                    gap = hypot(dx,dy)
                    pair_gaps.append({'left':left,'right':right,'expandedPathAabbGapMm':gap})
                    if gap == 0: collisions.append([left,right])
            assert not collisions, (pid,collisions)
            for identity, info in instances.items():
                info['supportPathEstimatedG'] = sum(g for f,g in masses[identity].items() if f.startswith('Support'))
                info['expandedMaterialPathBoundsMm'] = by_object[identity]
                if info['sourceFile'] == 'rear-fan-frame-print.stl':
                    assert info['enableSupport'] == '0' and info['supportPathEstimatedG'] == 0
            support = sum(g for features in masses.values() for f,g in features.items() if f.startswith('Support'))
            assert abs(support-plate_report['pathEstimate']['supportPathEstimatedG']) < 1e-6
            plates.append({'plate':pid,'objectCount':len(instances),'objects':instances,
                'embeddedGcodeEqualsExternal':True,'gcodeSha256':sha256(raw).hexdigest(),
                'supportPathEstimatedG':support,'supportPathBoundsMm':support_bounds,
                'depositionCenterlineBoundsMm':center_bounds,'nominalMaterialBoundsMm':material_bounds,
                'depositionCommands':segments,'depositionArcCommands':arc_count,
                'minimumBedEdgeMarginAfterHalfLineWidthMm':minimum_bed_margin,
                'minimumExcludeRectangleAabbClearanceAfterHalfLineWidthMm':exclude_clearance,
                'excludedAreaIntersectingDepositionAabbCount':forbidden,
                'separateObjectExpandedPathAabbCollisions':collisions,'pairwisePathAabbGaps':pair_gaps})
    assert sum(p['objectCount'] for p in plates) == 9
    assert len(plates) == 5
    assert abs(sum(p['supportPathEstimatedG'] for p in plates)-report['supportPathEstimatedG']) < 1e-6
    assert initial_hashes == {str(p.relative_to(ROOT)):digest(p) for p in tracked}, '审核期间输入发生变化'
    evidence = {'checkedAt':datetime.now(timezone.utc).isoformat(),'passed':True,
        'checkerSha256':digest(Path(__file__)),'inputSha256':initial_hashes,'plateCount':5,'pieceCount':9,
        'presetHashes':{name:digest(path) for name,path in preset_paths.items()},
        'nominalExcludedRectangleMm':[[0,0],[18,28]],'nominalBedMm':[256,256,250],
        'plates':plates,'supportPathEstimatedG':sum(p['supportPathEstimatedG'] for p in plates),
        'limits':['Read-only digital audit; no slicer or printer invoked.',
          'Envelope includes half each G-code LINE_WIDTH in XY; physical bead shape is unmeasured.',
          'Arc bounds use analytic cardinal extrema with a conservative maximum rounded endpoint radius.',
          'Excluded-zone proof uses conservative per-command expanded AABBs; Custom/Flush machine preparation is excluded.',
          'Separate object AABBs cover deposited model, brim and support paths; by-layer mode verified.',
          'Does not prove support removal, print quality, assembly fit, strength or thermal behavior.']}
    output = ROOT/'validation/r3/printing-audit.json'
    output.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    print(output)
    for plate in plates:
        print(plate['plate'],plate['supportPathEstimatedG'],plate['minimumBedEdgeMarginAfterHalfLineWidthMm'],
              plate['minimumExcludeRectangleAabbClearanceAfterHalfLineWidthMm'],plate['pairwisePathAabbGaps'])


if __name__ == '__main__':
    main()
