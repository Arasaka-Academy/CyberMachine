import bpy,math,json
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[4]
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
scene.render.engine='CYCLES'; scene.cycles.samples=24; scene.cycles.use_denoising=True
scene.render.resolution_x=1600; scene.render.resolution_y=1500; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.82,.85,.89,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35
scene.view_settings.view_transform='Filmic'

def mat(name,color,metal=0,rough=.4):
 m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
 p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*color,1)
 p.inputs['Metallic'].default_value=metal; p.inputs['Roughness'].default_value=rough
 return m
shell=mat('Graphite PETG',(.085,.115,.135),0,.32)
inner=mat('Interior graphite',(.18,.24,.27),0,.45)
amber=mat('Amber retainers',(.9,.28,.045),0,.4)
silver=mat('Aluminium',(.52,.57,.62),.7,.28)
black=mat('Fan polymer',(.028,.035,.043),0,.35)
pcb=mat('Solder mask',(.018,.22,.12),.1,.5)
gold=mat('Contacts',(.63,.40,.11),.6,.28)
white=mat('Drive labels',(.78,.8,.79),0,.6)
parts={}; fans={}

def stl(path,name,material):
 bpy.ops.import_mesh.stl(filepath=str(path),global_scale=.001)
 o=bpy.context.object; o.name=name; o.data.materials.clear(); o.data.materials.append(material)
 return o

def cube(name,p,d,material,bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=tuple((p[i]+d[i]/2)*.001 for i in range(3)))
 o=bpy.context.object; o.name=name; o.dimensions=tuple(v*.001 for v in d)
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(material)
 if bevel:
  m=o.modifiers.new('Edge radius','BEVEL'); m.width=bevel*.001; m.segments=2
  o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
 return o

manifest=json.loads((R/'work/manifest.json').read_text())
for m in manifest:
 if m['group'] in ['coupon','shim']: continue
 ma=amber if m['group']=='drive' else (inner if m['group']=='frame' else shell)
 if m['group']=='guard': ma=black
 parts[m['name']]=stl(R/'work/meshes'/f'{m["name"]}.stl',m['name'],ma)

for p in sorted((R/'work/meshes').glob('ref_board_*.stl')):
 idx=int(p.stem.split('_')[-1]); material=pcb if idx==0 else silver if idx in [698,699,700,710,711,714] else black
 stl(p,p.stem,material)

for i,x in enumerate([29,50.5,72,93.5,115],1):
 cube(f'SATA drive {i}',(x-2.7,41.5,22.25),(9.5,69.85,100.45),silver,.7)
 cube(f'Drive label {i}',(x-2.86,49,37),(0.15,52,68),white)
 cube(f'Drive connector {i}',(x-1.8,55.5,122.2),(2,42,5),black,.2)
 for j in range(6): cube(f'Drive label stripe {i} {j}',(x-2.95,53,44+j*4),(.08,30 if j<2 else 42,1.2),black)

# Standard-envelope visual proxies, not additional printable parts.
cube('CM5 PCB',(35.05,56.7,138.5),(55,40,1.2),pcb,.3)
cube('Official heatsink visual proxy',(34.55,55.2,140),(56,43,4),silver,.5)
for j in range(11): cube(f'Heatsink fin {j}',(35.55,56.2+j*3.8,144),(54,1.6,12),silver,.2)
cube('M2 SSD',(34.7,98.3,138),(80,22,1.2),pcb,.25)
cube('M2 heatspreader proxy',(39.7,98.3,139.2),(68,22,6),black,.5)
for j in range(6): cube(f'M2 fin {j}',(40.7,99.2+j*3.5,145.2),(66,1.5,3),silver,.15)
for x,y in [(20.1,60.2),(12.9,116.95),(105,60.2),(119.45,116.9)]:
 bpy.ops.mesh.primitive_cylinder_add(vertices=20,radius=.00225,depth=.006,location=(x*.001,y*.001,.1304))
 bpy.context.object.data.materials.append(gold)

def fan(name,center,size,axis):
 objs=[]; cx,cy,cz=center; thick=25; r=size*.445
 # Build in local XY (fan face), thickness along local Z, then orient.
 def point(u,v,w):
  if axis=='Y': return (cx+u,cy+w,cz+v)
  return (cx+u,cy+v,cz+w)
 def block(u,v,w,du,dv,dw):
  p=point(u,v,w); d=(du,dw,dv) if axis=='Y' else (du,dv,dw)
  objs.append(cube(name+' frame',p,d,black,.8))
 a=size/2; rim=7
 block(-a,-a,-12.5,size,rim,25); block(-a,a-rim,-12.5,size,rim,25)
 block(-a,-a+rim,-12.5,rim,size-2*rim,25); block(a-rim,-a+rim,-12.5,rim,size-2*rim,25)
 bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=size*.145*.001,depth=.016,location=tuple(v*.001 for v in center))
 hub=bpy.context.object; hub.name=name+' hub'; hub.data.materials.append(black)
 if axis=='Y': hub.rotation_euler[0]=math.pi/2
 objs.append(hub)
 for i in range(7):
  ang=i*2*math.pi/7
  uv=[(r*.32,-5,-2),(r*.5,-13,1),(r*.96,-8,3),(r,5,1),(r*.68,13,-2),(r*.34,8,-2)]
  verts=[]
  for u,v,w in uv:
   xx=u*math.cos(ang)-v*math.sin(ang); yy=u*math.sin(ang)+v*math.cos(ang)
   verts.append(tuple(c*.001 for c in point(xx,yy,w)))
  me=bpy.data.meshes.new('blade'); me.from_pydata(verts,[],[tuple(range(6))]); me.update()
  ob=bpy.data.objects.new(name+' blade',me); bpy.context.collection.objects.link(ob); ob.data.materials.append(black)
  so=ob.modifiers.new('Blade thickness','SOLIDIFY'); so.thickness=.0012; objs.append(ob)
 fans[name]=objs

fan('Front 12025',(72,17.5,68),120,'Y'); fan('Rear 12025',(72,150.5,68),120,'Y')
fan('Top 9225',(68,91,192.5),92,'Z')

floor=mat('Backdrop',(.83,.85,.86),0,.7)
cube('Ground',(-2000,-2000,-8),(4000,4000,1.8),floor)
for name,loc,power,size in [('Key',(-.35,-.45,.65),450,.45),('Fill',(.48,-.05,.4),260,.4),('Rim',(.15,.5,.6),400,.35)]:
 bpy.ops.object.light_add(type='AREA',location=loc); o=bpy.context.object; o.name=name; o.data.energy=power*.035; o.data.shape='DISK'; o.data.size=size
 o.rotation_euler=(Vector((.072,.084,.10))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(); cam=bpy.context.object; scene.camera=cam; cam.data.type='ORTHO'; cam.data.lens=50

def camera(loc,target,scale):
 cam.location=loc; cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.ortho_scale=scale

camera((-.32,-.46,.33),(.072,.080,.100),.32)
scene.render.filepath=str(R/'work/closed.png'); bpy.ops.render.render(write_still=True)

# Cutaway/exploded view; remove left side and separate lid/fan, front panel/guard.
parts['03_left_side'].hide_render=True
parts['09_recessed_IO_panel'].hide_render=True
parts['10_top_lid'].location.z+=.055
parts['11_top_guard'].location.z+=.055
for o in fans['Top 9225']: o.location.z+=.055
parts['05_front_fan_panel'].location.y-=.038
parts['07_front_guard'].location.y-=.038
for o in fans['Front 12025']: o.location.y-=.038
camera((-.20,-.55,.36),(.070,.065,.122),.40)
scene.render.resolution_x=1800; scene.render.resolution_y=1500
scene.render.filepath=str(R/'work/cutaway.png'); bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(R/'work/assembly_preview.blend'))
