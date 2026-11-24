"""[INPUT]: 已构建的分件模型、候选清单与设计和I/O源码哈希。
[OUTPUT]: 五种实际打印朝向的PETG FDM通用规则汇总与原始日志。
[POS]: 统一复现制造规则检查；不替代切片和实物试片。
[PROTOCOL]: Update this header on change, then check AGENTS.md
"""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT/'outputs/redesign-r3'
LOG = ROOT/'work/redesign-r3/dfm'
NAMES = ('shell', 'lid-print', 'spine-print', 'carrier-print', 'rear-fan-frame-print')


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    metadata = json.loads((OUT/'metadata.json').read_text())
    source_sha = digest(Path(__file__).with_name('design.py'))
    io_sha = digest(Path(__file__).with_name('io_geometry.py'))
    assert metadata['sourceSha256'] == source_sha, '先重新导出设计模型'
    assert metadata['ioSourceSha256'] == io_sha, '先重新导出I/O模型'
    identifiers = {part['name']: part['id'] for part in metadata['printParts']}
    LOG.mkdir(parents=True, exist_ok=True)
    results = []
    for name in NAMES:
        command = ['cad', 'model', 'dfm', identifiers[name], '--process', 'printing',
                   '--technology', 'fdm', '--material', 'petg', '--build-volume',
                   '256x256x256', '--layer-height', '0.2', '--nozzle', '0.4', '--json']
        execution = subprocess.run(command, capture_output=True, text=True)
        if execution.stderr:
            (LOG/f'{name}.stderr.log').write_text(execution.stderr)
        raw = json.loads(execution.stdout)
        (LOG/f'{name}.json').write_text(json.dumps(raw, indent=2)+'\n')
        findings = raw.get('findings', [])
        results.append({'name': name, 'status': raw.get('status'),
                        'exitCode': execution.returncode,
                        'codes': dict(Counter(item['code'] for item in findings)),
                        'errors': [item for item in findings if item['severity'] == 'error'],
                        'warnings': [{key: item.get(key) for key in
                                      ('code', 'value', 'limit', 'unit', 'location', 'hint')}
                                     for item in findings if item['severity'] == 'warning']})
        print(name, 'status', raw.get('status'), 'exit', execution.returncode,
              'findings', len(findings), flush=True)
    report = {'process': 'PETG FDM', 'machineEnvelopeMm': [256, 256, 256],
              'nozzleMm': .4, 'layerMm': .2, 'generalPracticeOnly': True,
              'results': results, 'checkedAt': datetime.now(timezone.utc).isoformat(),
              'sourceSha256': source_sha, 'ioSourceSha256': io_sha,
              'checkerSha256': digest(Path(__file__)),
              'candidateStepSha256': {name: digest(OUT/f'{name}.step') for name in NAMES}}
    (ROOT/'validation/r3/dfm-summary.json').write_text(json.dumps(report, indent=2)+'\n')
    assert all(item['exitCode'] == 0 and item['status'] == 'ok' and not item['errors']
               for item in results), 'DFM未全部完成或存在错误，见汇总报告'


if __name__ == '__main__':
    main()
