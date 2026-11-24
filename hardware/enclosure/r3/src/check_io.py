"""[INPUT]: 原厂 STEP 前端面、七组 I/O 参数与本轮分件 STEP。
[OUTPUT]: 独立面证据、孔道量规、USB-C 开放壳距离及漏孔失败对照。
[POS]: I/O 数字校准验证；不代替实际插头与按键试装。
[PROTOCOL]: Update this header on change, then check AGENTS.md
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import build123d as bd
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane
from OCP.TopAbs import TopAbs_FACE, TopAbs_SHELL
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from check_board import read_board, bounds, overlap_volume
from io_geometry import PORTS, inner_profile, outer_profile

ROOT=Path(__file__).resolve().parents[4]
OUT=ROOT/'outputs/redesign-r3'
TOLERANCE=1e-5


def faces(shape):
    result=[]
    ex=TopExp_Explorer(shape,TopAbs_FACE)
    while ex.More():
        result.append(bd.Face(TopoDS.Face(ex.Current())))
        ex.Next()
    return result


def swept(profile, front_y=0.):
    # 从接口前端一直扫到壳外，是连续直孔量规，不是运动采样。
    return bd.extrude(profile,amount=front_y+2,dir=(0,-1,0))


def gauge_profiles(port,native_face):
    if port['id']=='usb-a':
        # 原厂壳前端有薄缝；分别检查两嘴，不把薄 C 形面当插孔。
        return [bd.Pos(58.875,33.,(z0+z1)/2)*(bd.Plane.XZ*bd.Rectangle(12.5,z1-z0))
                for z0,z1 in ((136.58,142.3),(144.48,150.2))]
    if port['id']=='board-button':
        return [bd.Pos(92.64955,33.44007,138.5)*(bd.Plane.XZ*bd.Circle(1.5))]
    if port['id']=='dc':
        return [bd.Pos(112.515,34.35,140.35)*(bd.Plane.XZ*bd.Circle(3.25))]
    if port['id']=='usb-c':
        return [bd.Pos(101.935913,34.35,139.6)*(bd.Plane.XZ*bd.SlotOverall(8.94,3.16,rotation=90))]
    return [bd.Face(native_face.outer_wire())]


def main():
    native,native_solids=read_board()
    usbc=[]
    ex=TopExp_Explorer(native,TopAbs_SHELL)
    while ex.More():
        b=bounds(ex.Current())
        if all(abs(a-c)<1e-4 for a,c in zip(b,[100.09591334,34.35,133.1,103.77591344,48.35,144.07])):
            usbc.append(bd.Shell(TopoDS.Shell(ex.Current())))
        ex.Next()
    assert len(usbc)==1
    parts={name:bd.import_step(OUT/f'{name}.step') for name in ('shell','lid','spine','rear-fan-frame','carrier')}
    rows=[]
    for port in PORTS:
        source=usbc[0].wrapped if port['id']=='usb-c' else native_solids[int(port['nativeNames'][-1].split('-')[-1])]
        face=faces(source)[port['sourceFace']]
        surface=BRepAdaptor_Surface(face.wrapped)
        assert surface.GetType()==GeomAbs_Plane
        y=surface.Plane().Location().Y()
        assert abs(y-port['nativeFrontY'])<1e-4,(port['id'],y)
        gauges=[]
        for profile in gauge_profiles(port,face):
            gauge=swept(profile,port['nativeFrontY'])
            overlap=max(0.,overlap_volume(gauge.wrapped,parts['shell'].wrapped))
            clearance=gauge.distance_to(parts['shell'])
            gauges.append({'sweptVolumeMm3':gauge.volume,'shellOverlapMm3':overlap,
                           'shellMinDistanceMm':clearance,'profileBoundsMm':bounds(profile.wrapped)})
            assert overlap<TOLERANCE,(port['id'],overlap)
            assert clearance>=.49,(port['id'],clearance)
        inner,outer=inner_profile(port),outer_profile(port)
        rows.append({'id':port['id'],'label':port['label'],'nativeNames':port['nativeNames'],
                     'nativeFrontFace':port['sourceFace'],'measuredNativeFrontY':y,
                     'nativeFrontFaceBoundsMm':bounds(face.wrapped),
                     'throatAreaMm2':inner.area,'outerAreaMm2':outer.area,
                     'throatBoundsMm':bounds(inner.wrapped),'gauges':gauges})
        print(port['id'],'gauge gaps',[round(x['shellMinDistanceMm'],4) for x in gauges],flush=True)

    # 故意在 USB-C 前封堵，确认本轮漏孔会失败。
    plug=bd.Pos(100.,27.8,134.)*bd.Box(4.,3.2,11.,align=(bd.Align.MIN,)*3)
    bad=parts['shell']+plug
    p=next(p for p in PORTS if p['id']=='usb-c')
    gauge=swept(gauge_profiles(p,None)[0],p['nativeFrontY'])
    negative=overlap_volume(gauge.wrapped,bad.wrapped)
    assert negative>50,'未检出故意植入的 USB-C 封堵'

    shell_distances=[]
    printed={k:v for k,v in parts.items() if k!='carrier'}
    printed.update({f'carrier-{i}':bd.Pos(x-29,0,0)*parts['carrier']
                    for i,x in enumerate((29.,50.5,72.,93.5,115.),1)})
    for name,part in printed.items():
        gap=usbc[0].distance_to(part)
        shell_distances.append({'part':name,'distanceMm':gap})
        assert gap>.2
    old=[(17.83,18.9),(17.83,18.9),(17.27,20.3),(29.4,13.),(14.,17.2)]
    old_area=sum(w*h-(4-3.141592653589793)*.8**2 for w,h in old)
    report={'checkedAt':datetime.now(timezone.utc).isoformat(),'passed':True,
            'designSha256':sha256((Path(__file__).parent/'design.py').read_bytes()).hexdigest(),
            'ioSourceSha256':sha256((Path(__file__).parent/'io_geometry.py').read_bytes()).hexdigest(),
            'boardSourceSha256':sha256((ROOT/'references/radxa-taco/radxa_taco_3d_stp_v1.61.stp').read_bytes()).hexdigest(),
            'shellStepSha256':sha256((OUT/'shell.step').read_bytes()).hexdigest(),
            'candidateStepSha256':{name:sha256((OUT/f'{name}.step').read_bytes()).hexdigest()
                                   for name in ('shell','lid','spine','rear-fan-frame','carrier')},
            'ports':rows,'openUsbcShell':{'faces':len(usbc[0].faces()),'closed':False,
                                        'boundsMm':bounds(usbc[0].wrapped),'printedPartDistances':shell_distances},
            'negativeControlBlockedUsbcOverlapMm3':negative,
            'frontOpenAreaMm2':sum(r['outerAreaMm2'] for r in rows),
            'baselineFrontOpenAreaMm2':old_area,
            'scope':'Fresh native front-face planes and continuous straight gauges through the case wall. '
                    'The USB-C open shell is checked by exact surface distance, not treated as a valid solid. '
                    'The gauges are connector-mouth/tool envelopes; they do not model actual cable boots, '
                    'latches, full insertion travel, button force/travel, or printing deviations.'}
    (ROOT/'validation/r3/io-clearance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('I/O report passed',flush=True)


if __name__=='__main__':
    main()
