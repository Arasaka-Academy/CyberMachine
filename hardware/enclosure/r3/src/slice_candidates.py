"""[INPUT]: 最终CAD打印朝向清单与STL、本机Bambu Studio及完整BBL预设。
[OUTPUT]: 保留对象支撑设置的五盘P1S/PETG工程、G-code与打印证据。
[POS]: R3打印候选生成入口；仅离线切片，不连接设备或启动打印。
[PROTOCOL]: Update this header on change, then check AGENTS.md
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import atan2, hypot, pi
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[4]
CAD = ROOT/'outputs/redesign-r3'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def locate_slicer():
    mac = Path('/Applications/BambuStudio.app/Contents/MacOS/BambuStudio')
    if mac.is_file():
        return mac
    found = shutil.which('bambu-studio') or shutil.which('BambuStudio')
    assert found, '未找到Bambu Studio；用--slicer指定可执行文件'
    return Path(found)


def preset_bundle(base, output):
    files = {}
    for path in sorted(base.rglob('*.json')):
        try:
            data = json.loads(path.read_text())
            if 'name' in data:
                files.setdefault(data['name'], (path, data))
        except (ValueError, UnicodeError):
            pass
    inputs = {}

    def flatten(name, seen=()):
        assert name not in seen, f'预设继承循环：{name}'
        path, data = files[name]
        inputs[str(path.relative_to(base))] = digest(path)
        result = {}
        if data.get('inherits'):
            result.update(flatten(data['inherits'], (*seen, name)))
        for included in data.get('include', []):
            result.update(flatten(included, (*seen, name)))
        result.update(data)
        result.pop('inherits', None)
        result.pop('include', None)
        return result

    machine = flatten('Bambu Lab P1S 0.4 nozzle')
    filament = flatten('Generic PETG @BBL P1P')
    filament.update(name='CyberMachine R3 Generic PETG comparison',
                    compatible_printers=['Bambu Lab P1S 0.4 nozzle'])
    process = flatten('0.20mm Standard @BBL X1C')
    process.update(name='CyberMachine R3 PETG 0.20 4 walls 25%',
                   compatible_printers=['Bambu Lab P1S 0.4 nozzle'],
                   layer_height='0.2', wall_loops='4', sparse_infill_density='25%',
                   sparse_infill_pattern='gyroid', top_shell_layers='5', bottom_shell_layers='5',
                   curr_bed_type='Textured PEI Plate', print_sequence='by layer',
                   brim_type='outer_only', brim_width='5', enable_support='1',
                   support_type='tree(auto)', support_on_build_plate_only='0',
                   support_threshold_angle='35', support_top_z_distance='0.2',
                   support_bottom_z_distance='0.2')
    output.mkdir(parents=True, exist_ok=True)
    for name, data in [('machine', machine), ('process', process), ('filament', filament)]:
        (output/f'{name}.json').write_text(json.dumps(data, indent=2)+'\n')
    return inputs


def gcode_features(path):
    text = path.read_text()
    times = re.search(r'^; model printing time: (.*?); total estimated time: (.*?)$', text, re.M)
    assert times, 'G-code缺少时间估算'
    assert not re.search(r'^G(?:18|19|90\.1)\b', text, re.M), '包络只支持XY平面和相对I/J圆心'
    def seconds(value):
        units = {'d': 86400, 'h': 3600, 'm': 60, 's': 1}
        return sum(float(number)*units[unit] for number, unit in re.findall(r'([\d.]+)([dhms])', value))
    assert not re.search(r'^G20\b|^M200\b|^G1[01]\b', text, re.M), '不支持英制、体积挤出或固件回抽'
    assert re.search(r'^G21\b', text, re.M), 'G-code未声明毫米'
    density = float(re.search(r'^; filament_density(?::| =)\s*([\d.]+)', text, re.M)[1])
    diameter = float(re.search(r'^; filament_diameter(?::| =)\s*([\d.]+)', text, re.M)[1])
    assert re.search(r'^; printer_model = Bambu Lab P1S$', text, re.M)
    assert re.search(r'^; filament_type = PETG$', text, re.M)
    assert re.search(r'^; nozzle_diameter = 0.4$', text, re.M)
    assert re.search(r'^; layer_height = 0.2$', text, re.M)
    flow = re.findall(r'^M221\s+S([\d.]+)', text, re.M)
    assert all(float(value) == 100 for value in flow), flow
    number = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'
    extrusion = defaultdict(float)
    relative, e_position, debt, feature = False, 0., 0., 'Custom'
    x, y, z, absolute_xyz = 0., 0., 0., True
    bounds = [[float('inf')]*3, [float('-inf')]*3]
    support_bounds = [[float('inf')]*3, [float('-inf')]*3]
    for line in text.splitlines():
        if line.startswith('; FEATURE: '):
            feature = line[11:]
        command = line.split(';', 1)[0].strip()
        match = re.match(r'^([GM])(\d+)\b', command)
        if not match:
            continue
        code = match[1]+str(int(match[2]))
        values = {key: float(value) for key, value in re.findall(r'\b([XYZEFIJR])('+number+r')', command)}
        if code == 'M83':
            relative = True
        elif code == 'M82':
            relative = False
        elif code in ('G90', 'G91'):
            absolute_xyz = code == 'G90'
        elif code == 'G92':
            e_position = values.get('E', e_position)
            x, y, z = values.get('X', x), values.get('Y', y), values.get('Z', z)
        elif code in ('G0', 'G1', 'G2', 'G3'):
            previous = (x, y, z)
            next_x = values.get('X', x) if absolute_xyz else x+values.get('X', 0.)
            next_y = values.get('Y', y) if absolute_xyz else y+values.get('Y', 0.)
            next_z = values.get('Z', z) if absolute_xyz else z+values.get('Z', 0.)
            moving = abs(next_x-x)+abs(next_y-y) > 1e-8 or code in ('G2', 'G3') and any(key in values for key in ('I', 'J', 'R'))
            x, y, z = next_x, next_y, next_z
            if 'E' not in values:
                continue
            delta = values['E'] if relative else values['E']-e_position
            e_position = e_position+delta if relative else values['E']
            if delta < 0:
                debt -= delta
            else:
                repay = min(debt, delta)
                debt -= repay
                if moving:
                    extrusion[feature] += delta-repay
                    if delta-repay > 1e-8 and feature not in ('Custom', 'Flush'):
                        points = [previous, (x, y, z)]
                        if code in ('G2', 'G3'):
                            assert 'R' not in values and ('I' in values or 'J' in values), '圆弧要求相对I/J圆心'
                            cx, cy = previous[0]+values.get('I', 0.), previous[1]+values.get('J', 0.)
                            start, end = atan2(previous[1]-cy, previous[0]-cx), atan2(y-cy, x-cx)
                            sign = 1 if code == 'G3' else -1
                            sweep = (sign*(end-start)) % (2*pi)
                            if hypot(x-previous[0], y-previous[1]) < 1e-8:
                                sweep = 2*pi
                            radius = max(hypot(previous[0]-cx, previous[1]-cy), hypot(x-cx, y-cy))
                            for angle, dx, dy in ((0,1,0),(pi/2,0,1),(pi,-1,0),(-pi/2,0,-1)):
                                if (sign*(angle-start)) % (2*pi) <= sweep+1e-8:
                                    points.append((cx+radius*dx, cy+radius*dy, z))
                        for target in [bounds]+([support_bounds] if feature.startswith('Support') else []):
                            for point in points:
                                for axis in range(3):
                                    target[0][axis] = min(target[0][axis], point[axis])
                                    target[1][axis] = max(target[1][axis], point[axis])
    factor = pi*(diameter/2)**2*density/1000
    assert all(0 <= bounds[0][axis] <= bounds[1][axis] <= maximum
               for axis, maximum in enumerate((256, 256, 250))), bounds
    return {'filamentDiameterMm': diameter, 'filamentDensityGcm3': density,
            'slicerVersion': re.search(r'^; BambuStudio ([\d.]+)$', text, re.M)[1],
            'modelEstimatedSeconds': seconds(times[1]), 'totalEstimatedSeconds': seconds(times[2]),
            'depositedPathBoundsMm': bounds,
            'supportPathBoundsMm': support_bounds if any(name.startswith('Support') for name in extrusion) else None,
            'depositedPathEstimatedG': {name: length*factor for name, length in extrusion.items()},
            'supportPathEstimatedG': sum(length*factor for name, length in extrusion.items() if name.startswith('Support')),
            'boundary': 'FEATURE path deposition, excluding E-only purge. Not measured support mass or a fraction of total spool use.'}


def make_plan(parts):
    def item(name, x, y, support=True, support_type='tree(auto)'):
        minimum = parts[name]['boundsMm'][0]
        return {'path': str(CAD/f'{name}.stl'), 'count': 1, 'filaments': [1],
                'pos_x': [x-minimum[0]], 'pos_y': [y-minimum[1]], 'pos_z': [-minimum[2]],
                'print_params': {'enable_support': '1' if support else '0',
                                 'support_type': support_type}}
    return {'plates': [
        {'plate_name': '01 Shell upright', 'need_arrange': False, 'objects': [item('shell', 56, 56)]},
        {'plate_name': '02 Lid top down', 'need_arrange': False,
         'objects': [item('lid-print', 56, 56, support_type='normal(auto)')]},
        {'plate_name': '03 Main frame upright', 'need_arrange': False, 'objects': [item('spine-print', 61.5, 74.75)]},
        {'plate_name': '04 Fan frame and two carriers', 'need_arrange': False,
         'objects': [item('rear-fan-frame-print', 10, 60, False),
                     item('carrier-print', 151, 20), item('carrier-print', 151, 130)]},
        {'plate_name': '05 Three carriers flat', 'need_arrange': False,
         'objects': [item('carrier-print', 20, 35), item('carrier-print', 141, 35),
                     item('carrier-print', 80.5, 145)]}
    ]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--slicer', type=Path)
    parser.add_argument('--profile-root', type=Path, help='Bambu Studio profiles/BBL目录')
    parser.add_argument('--output', type=Path, default=ROOT/'outputs/print-r3')
    parser.add_argument('--comparison', type=Path, help='先前同预设对照JSON；仅归档引用，不当本轮结果')
    args = parser.parse_args()
    slicer = (args.slicer or locate_slicer()).resolve()
    profiles = args.profile_root or slicer.parents[1]/'Resources/profiles/BBL'
    assert profiles.is_dir(), '用--profile-root指定BBL预设目录'
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    metadata = json.loads((CAD/'metadata.json').read_text())
    source_sha = digest(Path(__file__).with_name('design.py'))
    assert metadata['sourceSha256'] == source_sha, '先重新导出CAD'
    assert metadata['ioSourceSha256'] == digest(Path(__file__).with_name('io_geometry.py')), 'I/O参数与导出不一致'
    mesh_path = ROOT/'validation/r3/mesh.json'
    mesh = json.loads(mesh_path.read_text())
    assert mesh['passed'], '先检查实际导出网格'
    checked_mesh = {Path(part['file']).name: part for part in mesh['parts']}
    assert metadata['printPieceCount'] == 9
    parts = {part['name']: part for part in metadata['printParts']}
    assert sum(part['quantity'] for part in parts.values()) == 9
    names = ('shell', 'lid-print', 'spine-print', 'rear-fan-frame-print', 'carrier-print')
    for name in names:
        assert (CAD/f'{name}.stl').is_file() and parts[name]['valid'] and parts[name]['solids'] == 1
        assert digest(CAD/f'{name}.step') == metadata['exportedStepSha256'][f'{name}.step']
        assert digest(CAD/f'{name}.stl') == checked_mesh[f'{name}.stl']['sha256'], 'STL与网格检查不一致'
    preset_inputs = preset_bundle(profiles, output/'presets')
    plan_path = output/'print-plan.json'
    plan = make_plan(parts)
    plan_path.write_text(json.dumps(plan, indent=2)+'\n')
    project_name = 'CyberMachine-r3-print-candidate.gcode.3mf'
    command = [str(slicer), '--load-assemble-list', str(plan_path),
               '--load-settings', f'{output}/presets/process.json;{output}/presets/machine.json',
               '--load-filaments', str(output/'presets/filament.json'), '--arrange', '0', '--orient', '0',
               '--slice', '0', '--mstpp', '300', '--outputdir', str(output), '--export-3mf', project_name]
    with (output/'slice.log').open('w') as log:
        execution = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=900)
    assert execution.returncode == 0, f'切片失败，见{output}/slice.log'
    result_path = output/'result.json'
    result = json.loads(result_path.read_text())
    assert result['return_code'] == 0 and len(result['sliced_plates']) == 5
    assert abs(result['layer_height']-.2) < 1e-5 and result['wall_loops'] == 4
    assert result['sparse_infill_density'] == 25
    plates = []
    for plate in result['sliced_plates']:
        gcode = output/f'plate_{plate["id"]}.gcode'
        assert gcode.is_file()
        expected = len(plan['plates'][plate['id']-1]['objects'])
        assert len(plate['objects']) == expected, (plate['id'], plate['objects'])
        assert not plate.get('warning_message'), (plate['id'], plate['warning_message'])
        first = plate['objects'][0]['bbox']
        first_plan = plan['plates'][plate['id']-1]['objects'][0]
        first_name = Path(first_plan['path']).stem
        origin = [first[axis]-first_plan[f'pos_{axis}'][0]-parts[first_name]['boundsMm'][0][i]
                  for i, axis in enumerate(('x', 'y', 'z'))]
        local_bounds = []
        for obj, planned in zip(plate['objects'], plan['plates'][plate['id']-1]['objects']):
            box = obj['bbox']
            local = dict(box, **{axis: box[axis]-origin[i] for i, axis in enumerate(('x', 'y', 'z'))})
            name = Path(planned['path']).stem
            for i, axis in enumerate(('x', 'y', 'z')):
                expected_min = planned[f'pos_{axis}'][0]+parts[name]['boundsMm'][0][i]
                assert abs(local[axis]-expected_min) < .002, (name, local)
            assert min(local['x'], local['y'], local['z']) >= -.001, local
            assert local['x']+local['width'] <= 256.001 and local['y']+local['depth'] <= 256.001, local
            assert local['z']+local['height'] <= 250.001, local
            local_bounds.append(local)
        path_estimate = gcode_features(gcode)
        assert abs(path_estimate['totalEstimatedSeconds']-plate['total_predication']) <= 1.1
        plates.append({'plate': plate['id'], 'name': plan['plates'][plate['id']-1]['plate_name'],
                       'objectCount': expected, 'objects': plate['objects'],
                       'resultSceneOriginMm': origin, 'localObjectBoundsMm': local_bounds,
                       'estimatedSeconds': plate['total_predication'],
                       'totalFilamentG': sum(f['total_used_g'] for f in plate['filaments']),
                       'featureTimesSeconds': plate['feature_type_times'],
                       'pathEstimate': path_estimate, 'warning': plate.get('warning_message'),
                       'gcodeSha256': digest(gcode)})
    project = output/project_name
    assert project.is_file()
    report = {'checkedAt': datetime.now(timezone.utc).isoformat(), 'passed': True,
              'sourceSha256': source_sha, 'checkerSha256': digest(Path(__file__)),
              'ioSourceSha256': metadata['ioSourceSha256'], 'meshReportSha256': digest(mesh_path),
              'metadataSha256': digest(CAD/'metadata.json'), 'process': 'P1S 0.4mm / Generic PETG / 0.20mm / 4 walls / 25% gyroid',
              'supportStrategy': 'Automatic tree supports; lid normal supports; flat fan frame support disabled. 0.2mm contact Z gap.',
              'bedType': 'Textured PEI Plate', 'installedSlicer': str(slicer),
              'presetSourceHashes': preset_inputs,
              'presetHashes': {p.name: digest(p) for p in (output/'presets').glob('*.json')},
              'candidateStlSha256': {name: digest(CAD/f'{name}.stl') for name in names},
              'printTransforms': metadata['printTransforms'], 'pieceCount': 9, 'plateCount': len(plates),
              'plates': plates, 'totalEstimatedSeconds': sum(p['estimatedSeconds'] for p in plates),
              'modelEstimatedSeconds': sum(p['pathEstimate']['modelEstimatedSeconds'] for p in plates),
              'timeEstimateBasis': 'Bambu header total estimated time, including preset preparation estimates; actual heating, calibration and handling times vary.',
              'totalFilamentG': sum(p['totalFilamentG'] for p in plates),
              'supportPathEstimatedG': sum(p['pathEstimate']['supportPathEstimatedG'] for p in plates),
              'projectPath': str(project.relative_to(ROOT)) if project.is_relative_to(ROOT) else str(project),
              'projectSha256': digest(project), 'resultSha256': digest(result_path),
              'limits': ['Slice estimates only; no print started and no printer contacted.',
                         'Actual support removal, print finish, fit, insert strength, stiffness and thermal performance require physical trials.',
                         'Use actual printer, plate, dried filament and nozzle settings before printing; stock Generic PETG is a comparison preset.']}
    if args.comparison:
        report['previousComparison'] = {'sha256': digest(args.comparison),
                                        'records': json.loads(args.comparison.read_text())}
    (ROOT/'validation/r3/printing.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({key: report[key] for key in ('passed', 'plateCount', 'pieceCount', 'totalEstimatedSeconds', 'totalFilamentG', 'supportPathEstimatedG', 'projectPath')}, indent=2))


if __name__ == '__main__':
    main()
