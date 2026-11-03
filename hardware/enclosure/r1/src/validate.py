import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(Path(__file__).resolve().parent))
import design as cad
from OCP.TopoDS import TopoDS_Shape
from OCP.BRepTools import BRepTools
from OCP.BRep import BRep_Builder
import trimesh

manifest=json.loads((ROOT/'work/manifest.json').read_text())
parts=[]; meshes=[]
for m in manifest:
 s=TopoDS_Shape(); BRepTools.Read_s(s,str(ROOT/'work/parts'/f'{m["name"]}.brep'),BRep_Builder())
 mesh=trimesh.load_mesh(ROOT/'work/print_meshes'/f'{m["name"]}.stl',process=True)
 good=mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0
 meshes.append({'part':m['name'],'watertight':bool(mesh.is_watertight),'winding_consistent':bool(mesh.is_winding_consistent),'volume_mm3':round(float(mesh.volume),2),'triangles':len(mesh.faces),'valid':bool(good)})
 if m['group']!='coupon': parts.append((m,s))
collisions=[]
for i,(a,sa) in enumerate(parts):
 for b,sb in parts[i+1:]:
  aa,bb=a['bounds'],b['bounds']
  if all(aa[j]<bb[j+3]-1e-5 and aa[j+3]>bb[j]+1e-5 for j in range(3)):
   v=cad.volume(cad.common(sa,sb))
   if v>.015: collisions.append({'a':a['name'],'b':b['name'],'volume_mm3':round(v,4)})
print('MESH FAILURES',json.dumps([m for m in meshes if not m['valid']]))
print('PART COLLISIONS',json.dumps(collisions))
(ROOT/'work/mesh_validation.json').write_text(json.dumps(meshes,indent=2))
(ROOT/'work/part_intersections.json').write_text(json.dumps(collisions,indent=2))
scenarios=[]
for thickness in [9.5,7.0]:
 hits=[]
 for i,x in enumerate(cad.SATA_X,1):
  hdd=cad.box(x-2.7,41.5,22.25,thickness,69.85,100.45)
  for m,s in parts:
   if m['group']=='shim' and thickness==9.5: continue
   a,b=cad.bounds(hdd),m['bounds']
   if all(a[j]<b[j+3]-1e-5 and a[j+3]>b[j]+1e-5 for j in range(3)):
    v=cad.volume(cad.common(hdd,s))
    if v>.015: hits.append([i,m['name'],round(v,3)])
 scenarios.append({'thickness_mm':thickness,'static_intersections':hits})
extraction=[]
for thickness in [9.5,7.0]:
 for i,x in enumerate(cad.SATA_X,1):
  # Exact swept envelope covers every position from installed to 125 mm down.
  hdd=cad.box(x-2.7,41.5,22.25-125,thickness,69.85,100.45+125)
  for m,s in parts:
   if (m['group']=='shim' and thickness==9.5) or m['name'].startswith('15_') or m['name']=='02_service_hatch': continue
   a,b=cad.bounds(hdd),m['bounds']
   if all(a[j]<b[j+3]-1e-5 and a[j+3]>b[j]+1e-5 for j in range(3)):
    v=cad.volume(cad.common(hdd,s))
    if v>.015: extraction.append([thickness,i,m['name'],round(v,3)])
(ROOT/'work/hdd_scenarios.json').write_text(json.dumps({'static':scenarios,'extraction_travel_mm':125,'downward_extraction_intersections':extraction},indent=2))
print('HDD ENVELOPES',json.dumps(scenarios),'EXTRACTION',json.dumps(extraction))
board_raw=TopoDS_Shape()
BRepTools.Read_s(board_raw,str(ROOT/'work/taco-analysis.brep'),BRep_Builder())
board=cad.transform(board_raw,axis=(0,1,0),angle=cad.math.pi,move=(72.1,120,135))
fasteners=[]
for x,y in cad.BOARD_HOLES:
 standoff=cad.cylinder((x,y,127.4),2.25,6)
 fasteners.append({'item':'M2.5 standoff','position':[x,y],
                   'overlap_with_board_mm3':round(cad.volume(cad.common(standoff,board)),5)})
front_fan=cad.box(12,5,8,120,25,120)
for i,x in enumerate(cad.SATA_X,1):
 head=cad.cylinder((x+2.05,31.,14),2.85,1.7,(0,1,0))
 fasteners.append({'item':'M3 shoe head','slot':i,'clearance_to_front_fan_mm':1.,
                   'overlap_with_fan_mm3':round(cad.volume(cad.common(head,front_fan)),5)})
(ROOT/'work/fastener_clearance.json').write_text(json.dumps(fasteners,indent=2))
print('FASTENER INTERSECTIONS',json.dumps([f for f in fasteners if f.get('overlap_with_board_mm3',0) or f.get('overlap_with_fan_mm3',0)]))
