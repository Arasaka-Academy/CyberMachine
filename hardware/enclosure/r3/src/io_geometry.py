"""[INPUT]: 原厂 STEP 前端面、器件位置图与原理图的接口基准。
[OUTPUT]: 七组独立 I/O 孔、45 度导入口及浏览器使用的截面数据。
[POS]: design.py 与导出流程共用的 I/O 几何源。
[PROTOCOL]: Update this header on change, then check AGENTS.md
"""
import build123d as bd

OUTER_Y = 28.
THROAT_Y = 29.
INNER_Y = 30.8
LEAD_IN = 1.

# 前缘面来自原厂拓扑。外壳包围盒含引脚，不作为插孔。
PORTS = (
    dict(id='ethernet-1g', label='1G 网口', nativeNames=['native-699'],
         bodyBoundsMm=[10.65,33.05,131.05,26.88,54.3,148.35],
         nativeFrontY=33.05, kind='rect', mouthBoundsXZ=[11.03,135.28,26.5,148.12],
         clearance=.6, radius=.6, sourceFace=25),
    dict(id='ethernet-2-5g', label='2.5G 网口', nativeNames=['native-700'],
         bodyBoundsMm=[31.65,33.05,131.05,47.88,54.3,148.35],
         nativeFrontY=33.05, kind='rect', mouthBoundsXZ=[32.03,135.28,47.5,148.12],
         clearance=.6, radius=.6, sourceFace=25),
    dict(id='usb-a', label='双 USB-A', nativeNames=[f'native-{i}' for i in range(708,715)],
         bodyBoundsMm=[51.04,33.,131.3,66.71,50.46,150.5],
         nativeFrontY=33., kind='rect', mouthBoundsXZ=[52.325,136.28,65.425,150.5],
         clearance=.4, radius=.6, sourceFace=230),
    dict(id='hdmi', label='HDMI', nativeNames=['native-698'],
         bodyBoundsMm=[70.62201,33.4,132.975,85.62201,45.4,141.25],
         nativeFrontY=33.4, kind='polygon', clearance=.8, sourceFace=6,
         points=[(70.62201,140.25),(71.62201,141.25),(84.62201,141.25),
                 (85.62201,140.25),(85.62201,138.06644),(84.92314,137.11286),
                 (84.57799,137.00386),(84.35976,136.86487),(83.58921,136.02428),
                 (82.85206,135.7),(73.39196,135.7),(72.65481,136.02428),
                 (71.88442,136.8647),(71.66626,137.00379),(71.32088,137.11286),
                 (70.62201,138.06644)]),
    dict(id='board-button', label='板载按钮', nativeNames=['native-687'],
         bodyBoundsMm=[88.944999,33.44007,131.00761,96.344999,40.84007,142.00761],
         nativeFrontY=33.44007, kind='circle', center=[92.64955,138.5],
         nativeRadius=1.47, clearance=.63, sourceFace=111,
         note='SW2 圆柱按钮；Ø3 工具按压包络，按键行程需实测。'),
    dict(id='usb-c', label='USB-C 刷机口', nativeNames=['native-usbc-shell'],
         bodyBoundsMm=[100.09591334,34.35,133.1,103.77591344,48.35,144.07],
         nativeFrontY=34.35, kind='capsule', mouthBoundsXZ=[100.355913,135.13,103.515913,144.07],
         clearance=.5, sourceFace=115,
         note='原厂为竖向、非闭合壳面；保留壳面，不伪造为实体。'),
    dict(id='dc', label='12V DC', nativeNames=['native-701'],
         bodyBoundsMm=[107.515,34.35,132.199055,117.515,47.35,145.4],
         nativeFrontY=34.35, kind='circle', center=[112.515,140.35],
         nativeRadius=3.25, clearance=.75, sourceFace=52,
         note='中心来自原厂前端孔；Ø8 喉口不证明电缆包胶可进入。'),
)


def inner_profile(port):
    """截面位于世界 XZ，法向为 -Y。"""
    kind = port['kind']
    if kind == 'circle':
        x,z = port['center']
        return bd.Pos(x,0,z) * (bd.Plane.XZ * bd.Circle(port['nativeRadius']+port['clearance']))
    if kind == 'polygon':
        face = bd.Plane.XZ * bd.Polygon(*port['points'], align=None)
        return bd.offset(face, amount=port['clearance'])
    x0,z0,x1,z1 = port['mouthBoundsXZ']
    margin = port['clearance']
    w,h = x1-x0+margin*2,z1-z0+margin*2
    sketch = bd.SlotOverall(h,w,rotation=90) if kind == 'capsule' else bd.RectangleRounded(w,h,port['radius'])
    return bd.Pos((x0+x1)/2,0,(z0+z1)/2) * (bd.Plane.XZ * sketch)


def outer_profile(port):
    return bd.offset(inner_profile(port), amount=LEAD_IN)


def aperture_tools():
    result=[]
    for port in PORTS:
        inner,outer=inner_profile(port),outer_profile(port)
        straight=bd.Pos(0,32,0) * bd.extrude(inner, amount=5,dir=(0,-1,0))
        lead=bd.loft([bd.Pos(0,OUTER_Y,0)*outer,bd.Pos(0,THROAT_Y,0)*inner])
        result.extend([straight,lead])
    return result


def outline(profile):
    # 线性段端点与曲线均采样；同一截面用于显示和实体切除。
    wire=profile.faces()[0].outer_wire()
    points=[[float(p.X),float(p.Z)] for p in (wire.position_at(i/240) for i in range(240))]
    return points+[points[0]]


def port_metadata():
    records=[]
    for port in PORTS:
        inner,outer=inner_profile(port),outer_profile(port)
        b=inner.bounding_box()
        records.append({**port,'innerProfileMm':outline(inner),'outerProfileMm':outline(outer),
                        'outerY':OUTER_Y,'innerY':THROAT_Y,'wallInnerY':INNER_Y,
                        'openingBoundsMm':[b.min.X,OUTER_Y,b.min.Z,b.max.X,INNER_Y,b.max.Z],
                        'nominalProfileMarginMm':port['clearance'],
                        'leadInDepthMm':LEAD_IN,'leadInAngleDeg':45.,
                        'verificationBoundary':'原厂前端截面与数字开孔；实际插头、按钮行程与打印偏差待实测。'})
    return records
