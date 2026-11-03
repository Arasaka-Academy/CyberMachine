import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
BASE=Path('/Applications/BambuStudio.app/Contents/Resources/profiles/BBL')
(ROOT/'work/slicer').mkdir(parents=True,exist_ok=True)
files={}
for p in sorted(BASE.rglob('*.json')):
 try:
  d=json.loads(p.read_text())
  if 'name' in d: files.setdefault(d['name'],(p,d))
 except Exception: pass

def flatten(name,seen=()):
 if name in seen: raise RuntimeError('inheritance cycle '+name)
 p,d=files[name]; out={}
 if d.get('inherits'): out.update(flatten(d['inherits'],seen+(name,)))
 for n in d.get('include',[]): out.update(flatten(n,seen+(name,)))
 out.update(d); out.pop('inherits',None); out.pop('include',None)
 return out

machine=flatten('Bambu Lab P1S 0.4 nozzle')
process=flatten('0.20mm Standard @BBL X1C')
filament=flatten('Generic PETG @BBL P1P')
process.update(name='CyberMachine PETG 0.20 4 walls 25%',from_='user',layer_height='0.2',wall_loops='4',sparse_infill_density='25%',sparse_infill_pattern='gyroid',top_shell_layers='5',bottom_shell_layers='5',brim_type='no_brim',enable_support='0',curr_bed_type='Textured PEI Plate',print_sequence='by layer',initial_layer_speed=['25','25'],initial_layer_infill_speed=['35','35'],outer_wall_speed=['80','80'],inner_wall_speed=['140','140'],sparse_infill_speed=['150','150'],top_surface_speed=['80','80'],bridge_speed=['25','25'])
process.pop('from_',None); process['from']='user'; process['setting_id']='CYBERMACHINE020PETG'
filament.update(name='CyberMachine Generic PETG 255C P1S',compatible_printers=['Bambu Lab P1S 0.4 nozzle'],filament_colour=['#33424A'],filament_max_volumetric_speed=['10','10'])
for name,d in [('machine',machine),('process',process),('filament',filament)]:
 (ROOT/'work/slicer'/f'{name}.json').write_text(json.dumps(d,indent=2))

manifest=json.loads((ROOT/'work/manifest.json').read_text())
names=[m['name'] for m in manifest]
groups=[('01 Fit test first',[n for n in names if n.startswith('00_')]),
 ('02 Left side',['03_left_side']),('03 Right side',['04_right_side']),
 ('04 Rear fan panel',['06_rear_fan_panel']),
 ('05 Front and IO',['05_front_fan_panel','09_recessed_IO_panel']),
 ('06 Base frame supports',['01_base_frame']),
 ('07 Hatch and motherboard',['02_service_hatch','12_motherboard_saddle']),
 ('08 Top lid',['10_top_lid']),
 ('09 Drive guides',['13_front_drive_guide','14_rear_drive_guide']),
 ('10 Fan guards',['07_front_guard','08_rear_guard','11_top_guard']),
 ('11 Shoes shims feet',[n for n in names if n.startswith(('15_','16_','17_'))])]
plates=[]
for title,ns in groups:
 objs=[]
 for n in ns:
  obj=dict(path=str(ROOT/'work/print_meshes'/f'{n}.stl'),count=1,filaments=[1])
  if n.startswith('15_'): obj['print_params']={'sparse_infill_density':'100%'}
  objs.append(obj)
 p=dict(plate_name=title,need_arrange=True,objects=objs)
 if title.startswith(('06 ','09 ')):
  p['plate_params']={'enable_support':'1','support_type':'normal(auto)','support_on_build_plate_only':'1','support_threshold_angle':'35','support_top_z_distance':'0.2','support_bottom_z_distance':'0.2'}
 if title.startswith('09 '):
  # Reserve 24 mm between the guides for generated support toolpaths.
  p['need_arrange']=False
  for obj,y in zip(objs,[10.,140.]):
   obj.update(pos_x=[60.],pos_y=[y],pos_z=[0.])
 plates.append(p)
(ROOT/'work/slicer/assemble.json').write_text(json.dumps({'plates':plates},indent=2))
(ROOT/'work/slicer/coupon.json').write_text(json.dumps({'plates':plates[:1]},indent=2))
(ROOT/'work/plate_plan.json').write_text(json.dumps(groups,indent=2))
print('Presets and',len(plates),'plates prepared')
