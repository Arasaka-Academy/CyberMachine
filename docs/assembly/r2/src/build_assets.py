"""Run with Blender 3.6+ --background --factory-startup --python build_assets.py.

Imports the source-derived meshes, preserves semantic nodes and named anchors,
and exports a self-contained glTF binary. No third-party assets are fetched.
"""
from pathlib import Path
import json
import gzip
import bpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
WORK = ROOT/'work/assembly-r2'
OUT = HERE.parent/'assets'
OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)

palette={
    'shell':('#dce2df',.15,.68),'metal':('#aebbb8',.72,.3),
    'aluminium':('#b9c6c2',.8,.36),'pcb':('#2e6051',.05,.75),
    'chip':('#26332f',.1,.65),'plastic':('#283430',.02,.72),
    'fan':('#8e9e97',.05,.62),'disk':('#b4c0ba',.35,.5),
    'label':('#f2f3ea',.0,.85),'gold':('#bd9a60',.72,.3),
}
def linear(v):
    return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
materials={}
for name,(color,metal,roughness) in palette.items():
    m=bpy.data.materials.new(name)
    m.use_nodes=True
    shader=m.node_tree.nodes.get('Principled BSDF')
    rgb=tuple(linear(int(color[i:i+2],16)/255) for i in [1,3,5])
    shader.inputs['Base Color'].default_value=(*rgb,1)
    shader.inputs['Metallic'].default_value=metal
    shader.inputs['Roughness'].default_value=roughness
    m.use_backface_culling=True
    materials[name]=m
parents={}
for item in json.loads((WORK/'meshes.json').read_text()):
    part=item['part']
    if part not in parents:
        parent=bpy.data.objects.new(part,None)
        bpy.context.collection.objects.link(parent)
        parent['partId']=part
        parents[part]=parent
    mesh=bpy.data.meshes.new(item['name'])
    mesh.from_pydata([[v/1000 for v in point] for point in item['vertices']],[],item['faces'])
    mesh.materials.append(materials[item['material']])
    mesh.update()
    obj=bpy.data.objects.new(item['name'],mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent=parents[part]
    # CAD face boundaries retain sharp edges; smooth only genuinely curved faces.
    for poly in mesh.polygons: poly.use_smooth=True
    mesh.use_auto_smooth=True
    mesh.auto_smooth_angle=.52

catalog=json.loads((HERE/'catalog.json').read_text())
for kind,points in catalog['anchors'].items():
    if isinstance(points[0],(int,float)): points=[points]
    for index,point in enumerate(points):
        obj=bpy.data.objects.new(f'anchor-{kind}-{index+1}',None)
        obj.empty_display_size=.002
        obj.location=[v/1000 for v in point]
        obj['anchorMm']=point
        bpy.context.collection.objects.link(obj)
        if kind in ['sata','cm5']:
            obj.parent=parents['taco']
        elif kind in ['wifi','wifiMount']:
            obj.parent=parents['wifi-slot']
        elif kind=='antenna':
            obj.parent=parents['wifi']
        elif kind=='drive':
            obj.parent=parents[f'drive-{index+1}-95']
            alt=obj.copy()
            alt.name=f'anchor-drive-{index+1}-7'
            alt.parent=parents[f'drive-{index+1}-7']
            bpy.context.collection.objects.link(alt)
for i,point in enumerate(catalog['anchors']['cm5']):
    obj=bpy.data.objects.new(f'anchor-cm5-mating-{i+1}',None)
    obj.location=[v/1000 for v in point]
    obj.parent=parents['cm5']
    bpy.context.collection.objects.link(obj)
obj=bpy.data.objects.new('anchor-wifi-mating',None)
obj.location=[v/1000 for v in catalog['anchors']['wifi']]
obj.parent=parents['wifi']
bpy.context.collection.objects.link(obj)
bpy.ops.wm.save_as_mainfile(filepath=str(WORK/'assembly.blend'))
bpy.ops.export_scene.gltf(filepath=str(OUT/'assembly.glb'),export_format='GLB',
                         export_yup=True,export_animations=False,export_extras=True,
                         export_materials='EXPORT',export_normals=True)
(OUT/'assembly.glb.gz').write_bytes(gzip.compress((OUT/'assembly.glb').read_bytes(),compresslevel=9,mtime=0))
print('Exported',len(parents),'semantic parts to',OUT/'assembly.glb')
