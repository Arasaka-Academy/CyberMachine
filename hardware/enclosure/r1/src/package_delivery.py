import json,zipfile,hashlib,shutil,csv,io,struct
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
BUILD_OUT=ROOT/'outputs'
OUT=BUILD_OUT/'CyberMachine-r1-design-package'
CAD=OUT/'hardware/enclosure/r1/cad'
PRINT=OUT/'hardware/enclosure/r1/print'
SOURCE=OUT/'hardware/enclosure/r1/src'
IMAGES=OUT/'docs/images/r1'
REPORTS=OUT/'validation/r1'
for folder in [CAD,PRINT,SOURCE,IMAGES,REPORTS,OUT/'docs/assembly',OUT/'references/radxa-taco']:
 folder.mkdir(parents=True,exist_ok=True)
src=ROOT/'work/slicer/release/CyberMachine-r1-5bay-p1s-petg.3mf'
result=json.loads((ROOT/'work/slicer/release/result.json').read_text())
manifest=json.loads((ROOT/'work/manifest.json').read_text())
mesh=json.loads((ROOT/'work/mesh_validation.json').read_text())
part_hits=json.loads((ROOT/'work/part_intersections.json').read_text())
ref_hits=json.loads((ROOT/'work/reference_intersections.json').read_text())
hdd_checks=json.loads((ROOT/'work/hdd_scenarios.json').read_text())
fastener_checks=json.loads((ROOT/'work/fastener_clearance.json').read_text())
assert result['return_code']==0 and len(result['sliced_plates'])==11
assert not part_hits and not ref_hits and all(m['valid'] for m in mesh)
assert not hdd_checks['downward_extraction_intersections']
assert all(not s['static_intersections'] for s in hdd_checks['static'])
assert all(not c.get('overlap_with_board_mm3',0) and not c.get('overlap_with_fan_mm3',0) for c in fastener_checks)
assert all(not p['warning_message'] for p in result['sliced_plates'])
z=zipfile.ZipFile(src); assert z.testzip() is None
model=ET.fromstring(z.read('3D/3dmodel.model')); assert model.get('unit')=='millimeter'
settings=json.loads(z.read('Metadata/project_settings.config'))
assert settings['printer_model']=='Bambu Lab P1S' and settings['wall_loops']=='4'
assert settings['filament_type']==['PETG'] and settings['sparse_infill_density']=='25%'
sliceinfo=ET.fromstring(z.read('Metadata/slice_info.config'))
assert len(sliceinfo.findall('plate'))==11
plates=[]
for i,p in enumerate(result['sliced_plates'],1):
 info=json.loads(z.read(f'Metadata/plate_{i}.json'))
 for b in info['bbox_objects']:
  a=b['bbox']; assert min(a)>=-1e-3 and max(a)<=256.001
  assert not(a[0]<18-1e-3 and a[1]<28-1e-3 and a[2]>0 and a[3]>0),('excluded corner',i,b)
 sp=sliceinfo.findall('plate')[i-1]
 def val(key): return sp.find(f'metadata[@key="{key}"]').get('value')
 assert val('outside')=='false'
 assert (val('support_used')=='true')==(i in [6,9])
 for obj in p['objects']:
  name=obj['name'].removesuffix('_1')
  data=(ROOT/'work/print_meshes'/f'{name}.stl').read_bytes()
  assert struct.unpack('<I',data[80:84])[0]==obj['triangle_count'],('stale mesh',name)
 plates.append(dict(plate=i,objects=[o['name'].removesuffix('_1') for o in p['objects']],
                    seconds=round(p['total_predication']),grams=round(sum(f['total_used_g'] for f in p['filaments']),2),
                    support=(i in [6,9]),bbox=info['bbox_all'],warnings=p['warning_message']))
assert sum(len(p['objects']) for p in plates)==35
shutil.copy2(src,PRINT/src.name)
shutil.copy2(ROOT/'work/slicer/coupon/CyberMachine-r1-fit-test-p1s.3mf',PRINT/'CyberMachine-r1-fit-test-p1s.3mf')
shutil.copy2(BUILD_OUT/'CyberMachine-r1-enclosure.step',CAD/'CyberMachine-r1-enclosure.step')

fontpath='/System/Library/Fonts/STHeiti Medium.ttc'
def font(n): return ImageFont.truetype(fontpath,n)
def titled(src,name,title,subtitle):
 im=Image.open(src).convert('RGB'); w,h=im.size
 canvas=Image.new('RGB',(w,h+130),'#f3f5f6'); canvas.paste(im,(0,130)); d=ImageDraw.Draw(canvas)
 d.text((52,24),title,font=font(42),fill='#24323b'); d.text((54,79),subtitle,font=font(24),fill='#586773')
 canvas.save(IMAGES/name)
titled(ROOT/'work/closed.png','assembled.png','CyberMachine · 五盘 NAS 外壳','144 × 168 × 210 mm + 6 mm 脚垫  |  前后 12025 · 顶部 9225')
titled(ROOT/'work/cutaway.png','exploded.png','内部结构与风扇布局','移除左侧板和 I/O 面板，分离顶盖与前风扇模块；硬件形状为示意')
canvas=Image.new('RGB',(1800,1100),'#f3f5f6'); d=ImageDraw.Draw(canvas)
d.text((54,35),'CyberMachine / FIVE BAY',font=font(48),fill='#26343d')
d.text((56,102),'五块 7 / 9.5 mm 硬盘 · P1S / PETG · 12025 × 2 + 9225 × 1',font=font(27),fill='#5c6b76')
for p,x,width in [('closed.png',0,850),('cutaway.png',830,970)]:
 im=Image.open(ROOT/'work'/p).convert('RGB'); im.thumbnail((width,875),Image.Resampling.LANCZOS)
 canvas.paste(im,(x+(width-im.width)//2,180+(875-im.height)//2))
canvas.save(IMAGES/'overview.png')

# Native Bambu plate thumbnails with concise Chinese labels.
labels=['试装件','左侧板','右侧板','后风扇面板','前面板与 I/O','底框（含支撑）','检修盖与主板支架','顶盖','硬盘导轨（含支撑）','三个风扇护网','托脚 / 垫片 / 脚垫']
grid=Image.new('RGB',(1600,1920),'#eef1f3'); dr=ImageDraw.Draw(grid)
dr.text((40,25),'P1S 打印盘 · 0.20 mm / PETG',font=font(38),fill='#26343d')
for i,label in enumerate(labels,1):
 x=((i-1)%3)*526+15; y=((i-1)//3)*450+100
 im=Image.open(io.BytesIO(z.read(f'Metadata/plate_{i}.png'))).convert('RGBA'); im.thumbnail((490,365),Image.Resampling.LANCZOS)
 grid.paste(im,(x+(500-im.width)//2,y),im)
 dr.text((x+16,y+375),f'{i:02d}  {label}',font=font(25),fill='#26343d')
grid.save(IMAGES/'print-plates.png')

report=dict(revision='R1',date='2026-10-30',units='mm',printer='Bambu Lab P1S 0.4 nozzle',
 envelope_mm=[144,168,210],feet_mm=6,printed_case_parts=33,test_parts=2,step_readback_solids=33,
 native_cad_valid=True,mesh_checks=mesh,part_intersections=part_hits,reference_intersections=ref_hits,
 hdd_checks=hdd_checks,
 fastener_checks=fastener_checks,
 board_reference='Original supplied Taco V1.61 STEP transformed by Y rotation 180 degrees, translation (72.1,120,135) mm',
 standard_hdd_envelopes_mm=[[100.45,69.85,9.5],[100.45,69.85,7]],
 limitations=['CM5/heatsink/HDD/fans/M2 are reference envelopes, not supplied exact models','HDD connector datum and insertion depth require physical trial assembly','No physical print, vibration, acoustic or thermal test performed'],
 slicer_version='BambuStudio-02.08.02.61',slicer_return_code=result['return_code'],plates=plates,
 total_estimated_hours=round(sum(p['seconds'] for p in plates)/3600,2),total_estimated_grams=round(sum(p['grams'] for p in plates),2))
(REPORTS/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
with (PRINT/'plate-list.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f); w.writerow(['盘号','内容','预计小时','预计克数','启用支撑','零件'])
 for p,l in zip(plates,labels): w.writerow([p['plate'],l,round(p['seconds']/3600,2),p['grams'],'是' if p['support'] else '否','; '.join(p['objects'])])

with zipfile.ZipFile(PRINT/'CyberMachine-r1-stl.zip','w',zipfile.ZIP_DEFLATED) as zz:
 for m in manifest: zz.write(ROOT/'work/print_meshes'/f'{m["name"]}.stl',f'{m["name"]}.stl')
for name in ['README.md','design.py','prepare_slicer.py','validate.py','render.py','package_delivery.py']:
 shutil.copy2(HERE/name,SOURCE/name)
shutil.copy2(ROOT/'docs/assembly/r1.md',OUT/'docs/assembly/r1.md')
for reference in (ROOT/'references/radxa-taco').iterdir():
 if reference.is_file(): shutil.copy2(reference,OUT/'references/radxa-taco'/reference.name)
(OUT/'README.md').write_text(
 '# CyberMachine R1 设计包\n\n'
 '基于 Radxa Taco V1.61 的五盘 NAS 机箱设计，单位为毫米。\n\n'
 '- [装配、五金与打印说明](docs/assembly/r1.md)\n'
 '- [CAD 源码、依赖与重建方法](hardware/enclosure/r1/src/README.md)\n'
 '- [原交付数字验证报告](validation/r1/report.json)\n\n'
 '先打印试装件，再验证实际配合。数字验证不能代替实物打印、装配、温升、振动与噪声测试。\n\n'
 '在本目录运行 `shasum -a 256 -c SHA256SUMS.txt` 校验包内文件。\n',encoding='utf-8')
for cache in OUT.rglob('__pycache__'):
 if cache.is_dir(): shutil.rmtree(cache)
bundle=BUILD_OUT/'CyberMachine-r1-design-package.zip'
checks=[]
for p in sorted(OUT.rglob('*')):
 if p.is_file() and p!=bundle and p.name!='SHA256SUMS.txt': checks.append(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(OUT)))
(OUT/'SHA256SUMS.txt').write_text('\n'.join(checks)+'\n')
with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as zz:
 for p in sorted(OUT.rglob('*')):
  if p.is_file() and p!=bundle: zz.write(p,str(p.relative_to(OUT)))
print('PACKAGED',len(plates),'plates',report['total_estimated_hours'],'hours',report['total_estimated_grams'],'g')
print('ARCHIVE',bundle.stat().st_size,'bytes')
