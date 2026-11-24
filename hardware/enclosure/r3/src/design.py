"""[INPUT]: io_geometry.py 七组孔口、原厂 STEP 的实体和 USB-C 开放壳，以及 R1 安装基准。
[OUTPUT]: R3 水平6mm通风横带、四角竖锁顶盖及五盘7mm装配与打印朝向。
[POS]: R3 CAD 唯一几何源；导出与验算脚本调用本模块。
[PROTOCOL]: Update this header on change, then check AGENTS.md

PETG FDM 候选，0.4 mm 喷嘴、0.2 mm 层高、256 mm 立方构建体积。
切片证据单独保存。尚未实物试装。硬盘与散热器是外形包络。
"""
from pathlib import Path
from math import cos, pi, sin, sqrt

import build123d as bd
from cad import model
from bd_materials import plastics
from bd_materials.processes import fdm
from io_geometry import aperture_tools

ROOT = Path(__file__).resolve().parents[4]
BOARD_STEP = ROOT / 'references/radxa-taco/radxa_taco_3d_stp_v1.61.stp'
SATA_X = (29., 50.5, 72., 93.5, 115.)
DRIVE_THICKNESS_MM = 7.
FRAME_WEB_THICKNESS_MM = 3.6
FRAME_WEB_X = (17.7,103.8)
FRAME_DIAGONAL_WIDTH_MM = 8.
FRAME_BASE_HEIGHT_MM = 6.
FRAME_CROSSBEAM = (7.,70.,8.,130.,8.,6.)
FRAME_FAN_UPRIGHT_THICKNESS_MM = 6.
FRAME_ROOT_CONE = (5.5,3.5,107.8,8.2)
FRAME_ROOT_RAMP = (1.2,5.5,103.5,4.3)
FRAME_FRONT_ROOT_CLIP_X = (23.95,109.95)
REAR_FRAME_KEY_X = (12.75,132.75)
ENCLOSURE_X_MIN = -5.
ENCLOSURE_WIDTH_MM = 154.
LID_HOLES = ((3.,48.),(141.,48.),(3.,152.),(141.,152.))
LID_SEAT_Z = 174.
LID_PILOT_BOTTOM_Z = 166.4
BASE_WEB_THICKNESS_MM = 3.2
FRONT_FOOT_GUSSETS = (((10.,36.),(24.,36.),(18.,50.)),
                     ((134.,36.),(120.,36.),(126.,50.)))
SPINE_SIDE_BEAM_X = (13.5,124.5)
BOARD_HOLES = ((20.1, 60.2), (12.9, 116.95), (105., 60.2), (119.45, 116.9))
FRAME_HOLES = ((10., 36.), (134., 36.), (10., 132.), (134., 132.))
TOP_FAN_CENTER = (72.,100.)
TOP_FAN_HOLES = tuple((x,y) for x in (30.75,113.25) for y in (58.75,141.25))
TOP_FAN_FRAME = (26.,54.,175.2,92.,92.,14.)
TOP_FAN_LEAD = (65.,148.,169.3,14.,14.,19.9)
TOP_GRILLE_RADII = tuple(4.4+6*i for i in range(7))
VENT_SLOT_WIDTH = 4.4
VENT_MIDDLE_Z = 70.
VENT_CROSS_WEB_MM = 6.


def box(x, y, z, dx, dy, dz):
    return bd.Pos(x, y, z) * bd.Box(dx, dy, dz, align=(bd.Align.MIN,)*3)


def cyl(x, y, z, radius, height, axis='z'):
    body = bd.Cylinder(radius, height, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    if axis == 'y':
        body = bd.Rot(-90, 0, 0) * body
    return bd.Pos(x, y, z) * body


def rounded(x, y, z, dx, dy, dz, radius):
    profile = bd.Pos(x+dx/2, y+dy/2, z) * bd.RectangleRounded(dx, dy, radius)
    return bd.extrude(profile, amount=dz)


def rounded_yz(x,y,z,dx,dy,dz,radius):
    profile=bd.Pos(x,y+dy/2,z+dz/2)*(bd.Plane.YZ*bd.RectangleRounded(dy,dz,radius))
    return bd.extrude(profile,amount=dx)


def rounded_xz(x,y,z,dx,dy,dz,radius):
    profile=bd.Pos(x+dx/2,y+dy,z+dz/2)*(bd.Plane.XZ*bd.RectangleRounded(dx,dz,radius))
    return bd.extrude(profile,amount=dy)


def diagonal_yz(x,start,end,width,thickness):
    dy,dz=end[0]-start[0],end[1]-start[1]
    length=(dy*dy+dz*dz)**.5
    oy,oz=-dz/length*width/2,dy/length*width/2
    points=[(start[0]+oy,start[1]+oz),(end[0]+oy,end[1]+oz),
            (end[0]-oy,end[1]-oz),(start[0]-oy,start[1]-oz)]
    profile=bd.Pos(x,0,0)*(bd.Plane.YZ*bd.Polygon(*points,align=None))
    return bd.extrude(profile,amount=thickness,dir=(1,0,0))


def triangle_yz(x,points,thickness):
    profile=bd.Pos(x,0,0)*(bd.Plane.YZ*bd.Polygon(*points,align=None))
    return bd.extrude(profile,amount=thickness,dir=(1,0,0))


def triangle_xz(points,y,depth):
    profile=bd.Pos(0,y,0)*(bd.Plane.XZ*bd.Polygon(*points,align=None))
    return bd.extrude(profile,amount=depth,dir=(0,1,0))


def triangle_xy(points,z,height):
    return bd.extrude(bd.Pos(0,0,z)*bd.Polygon(*points,align=None),amount=height,dir=(0,0,1))


def petg(shape, label, color):
    shape.label = label
    shape.material = plastics.petg(process=fdm(layer_height_mm=.2))
    shape.color = color
    assert shape.is_valid, label
    assert len(shape.solids()) == 1, (label, len(shape.solids()))
    return shape


def vent_slots(upper=False):
    # 外端保持对称缓拱；内端齐平，形成水平等宽6mm横带。
    slots = []
    for x in range(16,129,8):
        ratio = abs(x-72)/56
        if upper:
            inset = 3*ratio**1.5
            slots.append((x,143+inset,168-inset))
        else:
            inset = 8*ratio**1.5
            slots.extend(((x,14+inset,VENT_MIDDLE_Z-VENT_CROSS_WEB_MM/2),
                          (x,VENT_MIDDLE_Z+VENT_CROSS_WEB_MM/2,126-inset)))
    return slots


def vent_tools(y,upper=False):
    # 圆柱端头与中段重叠构成严格4.4mm圆端槽，不作退化圆角矩形。
    radius = VENT_SLOT_WIDTH/2
    return [box(x-radius,y,low+radius,VENT_SLOT_WIDTH,5,high-low-VENT_SLOT_WIDTH)
            +cyl(x,y,low+radius,radius,5,'y')+cyl(x,y,high-radius,radius,5,'y')
            for x,low,high in vent_slots(upper)]


def top_grille_tools():
    # 七道同心断环由四向4mm连筋串接；3.2mm环槽、2.8mm径向筋。
    x,y = TOP_FAN_CENTER
    crossbar = box(x-43,y-2,190.8,86,4,3.8)+box(x-2,y-43,190.8,4,86,3.8)
    return [(cyl(x,y,190.9,radius+1.6,3.5)-cyl(x,y,190.8,radius-1.6,3.8))-crossbar
            for radius in TOP_GRILLE_RADII]


@model
def shell():
    body = rounded(-5,28,0,154,144,174,8)
    body -= rounded(-2.2,30.8,2.8,148.4,138.4,173,5.2)
    for tool in vent_tools(27) + vent_tools(168):
        body -= tool
    for tool in vent_tools(168,upper=True):
        body -= tool
    # 四处止口承台提供合盖硬限位；底面45度，不悬空悬挑。
    for y in (70.,122.):
        for points in (((-2.3,166.45),(.55,169.3),(-2.3,169.3)),
                       ((146.3,166.45),(146.3,169.3),(143.45,169.3))):
            profile=bd.Plane.XZ * bd.Polygon(*points,align=None)
            body += bd.Pos(0,y+8,0) * bd.extrude(profile,amount=8)
    # 七组孔跟随实际前端截面，外侧1mm的45度导入口留出进入空间。
    for tool in aperture_tools():
        body -= tool
    # 四个底座使内骨架在硬接触面定位，螺丝只提供预紧。
    for x, y in FRAME_HOLES:
        body += cyl(x, y, 2.7, 4.5, 5.3)
        # 径向竖筋把脚座接入侧壁，硬接触顶仍为Z8。
        body += box(-2.3 if x<72 else 137.8,y-BASE_WEB_THICKNESS_MM/2,2.7,
                    8.5,BASE_WEB_THICKNESS_MM,5.3)
        body -= cyl(x, y, -1, 1.7, 10)
        body -= cyl(x, y, -1, 3.15, 3.2)
    # D座贴侧壁，内缘避开内总成；底坡45度，避免孤柱与悬空底面。
    for x,y in LID_HOLES:
        if x<72:
            body += box(-2.3,y-6,164,8.5,12,10)+box(6.2,y-4,164,2,8,10)
            edge_x=6.2
            points=((-2.3,153.5),(8.2,164.),(-2.3,164.))
        else:
            body += box(137.8,y-6,164,8.5,12,10)+box(135.8,y-4,164,2,8,10)
            edge_x=137.8
            points=((146.3,153.5),(135.8,164.),(146.3,164.))
        for edge_y in (y-4,y+4):
            body += cyl(edge_x,edge_y,164,2,10)
        body += triangle_xz(points,y-6,12)
        body -= cyl(x,y,LID_PILOT_BOTTOM_Z,2.05,7.7)
    return petg(body, 'shell', '#dce2df')


@model
def lid():
    body = rounded(-5,28,174.3,154,144,19.7,8)
    body -= rounded(-2.2,30.8,174.2,148.4,138.4,17,5.2)
    # 下伸止口比壳体内轮廓每边小 0.35 mm。
    ring = rounded(-1.85,31.15,169.3,147.7,137.7,8,4.85)
    ring -= rounded(.55,33.55,168.9,142.9,132.9,9,2.45)
    # 闭合止口在D座内侧绕行，2.4mm U形带与座边保留0.35mm。
    for x,y in LID_HOLES:
        left=x<72
        ring -= box(-2.3 if left else 135.45,y-6.35,168.9,10.85,12.7,8.8)
        inner_x=8.55 if left else 133.05
        ring += box(inner_x,y-8.75,169.3,2.4,17.5,8)
        for end_y in (y-8.75,y+6.35):
            ring += box(-1.85 if left else 133.05,end_y,169.3,12.8,2.4,8)
    bridge = rounded(-5,28,174.3,154,144,3,8)
    bridge -= rounded(.55,33.55,174.1,142.9,132.9,3.4,2.45)
    body += ring + bridge
    # 压套底接壳座Z174；Ø16根座以45度收至Ø12，倒置打印向上缩小。
    for x,y in LID_HOLES:
        body += cyl(x,y,LID_SEAT_Z,6.,17.4)
        crown=bd.Pos(x,y,187.2)*bd.Cone(6.,8.,2.,align=(bd.Align.CENTER,bd.Align.CENTER,bd.Align.MIN))
        crown+=cyl(x,y,189.2,8.,2.2)
        # 根座贴盖侧壁，完整Ø16根与154mm外宽相切。
        body += crown & box(-5,28,186.9,154,144,5)
        body -= cyl(x,y,173.9,1.7,20.6)
        body -= cyl(x,y,191.8,3.15,2.7)
    # 顶扇用一体硬座定位。14mm最大风扇厚度已包含自带软垫。
    for x,y in TOP_FAN_HOLES:
        body += cyl(x,y,189.2,4.5,2.1)
        body -= cyl(x,y,188.8,1.7,6)
        # 圆柱沉孔容纳低头螺丝；不是锥形沉头孔。
        body -= cyl(x,y,191.8,3.15,3)
    for tool in top_grille_tools():
        body -= tool
    return petg(body, 'lid', '#dce2df')


@model
def spine():
    body = box(7, 35, 8, 130, 4, FRAME_BASE_HEIGHT_MM)
    body += box(7, 124, 8, 130, 12, FRAME_BASE_HEIGHT_MM)
    for x in SPINE_SIDE_BEAM_X:
        body += box(x,35,8,6,101,FRAME_BASE_HEIGHT_MM)
    # 盘托下方跨X横梁连接两片桁架，顶面距盘托底面5.85mm。
    body += box(*FRAME_CROSSBEAM)
    # 前脚平面角板将铜套根接入前横梁与侧底梁，不增加打印高度。
    for points in FRONT_FOOT_GUSSETS:
        body += triangle_xy(points,8,FRAME_BASE_HEIGHT_MM)
    # 首片向负X加厚，保留首盘前螺丝的指尖空间；另一片向正X加厚。
    for x in FRAME_WEB_X:
        rail=box(x,35,8,FRAME_WEB_THICKNESS_MM,93,108)
        rail-=rounded_yz(x-.1,43,18,FRAME_WEB_THICKNESS_MM+.2,13.2,90,5)
        rail-=rounded_yz(x-.1,64.2,18,FRAME_WEB_THICKNESS_MM+.2,55.8,90,6)
        rail+=diagonal_yz(x,(64.2,18),(120,108),FRAME_DIAGONAL_WIDTH_MM,FRAME_WEB_THICKNESS_MM)
        # 尖拱两侧均为45度坡面，消除窗顶长跨距支撑；保留顶部8mm承力带。
        for a,b in ((43.,56.2),(64.2,120.)):
            mid,top=(a+b)/2,108.
            low=top-(b-a)/2
            rail+=triangle_yz(x,((a,low),(mid,top),(a,top)),FRAME_WEB_THICKNESS_MM)
            rail+=triangle_yz(x,((b,low),(mid,top),(b,top)),FRAME_WEB_THICKNESS_MM)
        body+=rail
    for x, y in BOARD_HOLES:
        if y > 110:
            body += box(x-2.5, 114.4, 8, 5, 21.6, 108)
        # 根部锥筋止于Z116；后柱裁去前侧，保留盘托肩0.35mm间隙。
        radius_bottom,radius_top,z,height = FRAME_ROOT_CONE
        root = bd.Pos(x,y,z)*bd.Cone(radius_bottom,radius_top,height,align=(bd.Align.CENTER,bd.Align.CENTER,bd.Align.MIN))
        # 下端从腹板内1.2mm半径起坡，45度展开到5.5mm，消除根筋底突台。
        start_radius,end_radius,start_z,ramp_height = FRAME_ROOT_RAMP
        root += bd.Pos(x,y,start_z)*bd.Cone(start_radius,end_radius,ramp_height,align=(bd.Align.CENTER,bd.Align.CENTER,bd.Align.MIN))
        if y > 110:
            root -= box(x-6,y-6,start_z-.1,12,114.4-(y-6),height+ramp_height+.2)
        else:
            # 正X侧裁边避开盘托顶带；主板孔1/3分别留0.35mm。
            limit = FRAME_FRONT_ROOT_CLIP_X[0 if x < 50 else 1]
            root -= box(limit,y-6,start_z-.1,10,12,height+ramp_height+.2)
        body += root
        body += cyl(x, y, 115.8, 3.5, 13.2)
        body += cyl(x, y, 128.8, 2.5, 4.6)
        # M2.5 热熔套安装孔；最终孔径以选定铜套试片确认。
        body -= cyl(x, y, 128.5, 1.65, 5.4)
    # 后横梁下表面限定盘托插入终点；底部螺丝承受盘托重力。
    body += box(7, 114.4, 22.25, 130, 6.4, 6)
    for x in (18., 41.5, 63., 84.5, 106., 128.):
        body += box(x-1.8, 114.4, 8, 3.6, 13.6, 19.25)
    for x in SATA_X:
        body -= cyl(x-1.65,117.3,22.15,2.05,4.9)
    # 主架直立打印。后扇框另件平放，共用四颗风扇螺丝夹紧。
    for x in (9.75, 129.75):
        body += box(x, 127, 8, FRAME_FAN_UPRIGHT_THICKNESS_MM, 11, 120)
    # 四角18mm三角肋位于Y134..138，不进入后扇Y142..167包络。
    for points in (((9.75,8),(27.75,8),(9.75,26)),
                   ((135.75,8),(117.75,8),(135.75,26)),
                   ((9.75,128),(27.75,128),(9.75,110)),
                   ((135.75,128),(117.75,128),(135.75,110))):
        body += triangle_xz(points,134,4)
    for x,dx,points in ((9.75,13.75,((15.75,108.75),(23.5,116.5),(15.75,116.5))),
                        (120.5,15.25,((129.75,107.25),(120.5,116.5),(129.75,116.5)))):
        body += box(x,127,116.5,dx,11,11.5)
        body += triangle_xz(points,127,11)
        body += box(x,127,11.5,dx,11,8)
    for x in (19.5, 124.5):
        for z in (15.5,120.5):
            body -= cyl(x,131.6,z,2.05,6.5,'y')
    # 定位键只负责对齐。每边0.3mm净空，竖柱剩余侧壁1.2mm。
    for x in REAR_FRAME_KEY_X:
        body -= box(x-1.8,136.2,65.2,3.6,1.9,5.6)
    # 铜套从骨架底面装入；外壳底部上拧螺丝，不经过主板上方。
    for x, y in FRAME_HOLES:
        body += cyl(x,y,8,4.5,6)
    for x, y in FRAME_HOLES:
        body -= cyl(x,y,7.9,2.05,4.9)
    return petg(body, 'spine', '#57746b')


@model
def rear_fan_frame():
    body=box(9.75,138,8,6,4,120)+box(129.75,138,8,6,4,120)
    for z in (8.,123.5):
        body+=box(9.75,138,z,126,4,4.5)
    for x in (19.5,124.5):
        for z in (15.5,120.5):
            body+=box(x-4,138,z-4,8,4,8)
            body-=cyl(x,137.9,z,1.7,4.2,'y')
    for x in REAR_FRAME_KEY_X:
        body+=box(x-1.5,136.5,65.5,3,1.5,5)
    return petg(body,'rear-fan-frame','#57746b')


def carrier_body(x):
    body = box(x-4.7, 39.1, 19.85, 14.3, 74.95, 2.4)
    # 偏置小耳避开第5盘后方主板柱；五托架仍使用同一几何。
    body += box(x-4.7,114.,19.85,6.1,6.6,2.4)
    # 前侧两块短肩只承托螺丝与垫圈，负X立边将力传入侧框和底梁。
    body += box(x-4.7,39.1,22.15,2,2.4,91.85)
    for z in (32.1,108.7):
        body+=rounded_xz(x-4.7,39.1,z-4.5,9.5,2.4,9,2)
    # 后侧保留上下导向短肩，取消挡风的中部端板。
    body += box(x-4.7,111.65,22.15,2,2.4,91.85)
    body += rounded_xz(x-4.7,111.65,22.15,14.3,2.4,12,2)
    body += rounded_xz(x-4.7,111.65,104,14.3,2.4,10,2)
    body += box(x-4.7, 41.4, 22.15, 2, 70.35, 91.85)
    # 负X面不变，接触框前后至少6mm、上下10mm，圆角窗释放侧向气流。
    body -= rounded_yz(x-5,47.5,35,3,57.75,69,4)
    # 两条2.6mm纵梁和三道横带承托硬盘底面；后偏耳保持完整。
    for y,length in ((49,27),(82,24)):
        body-=rounded(x-2.1,y,19.75,9.1,length,2.6,3)
    for z in (32.1, 108.7):
        body -= cyl(x+.3, 38.5, z, 1.7, 4, 'y')
    body -= cyl(x-1.65,117.3,19,1.7,4)
    return body


@model
def carrier():
    return petg(carrier_body(29.), 'carrier', '#7b948b')


@model
def lid_print():
    body = bd.Rot(180,0,0) * lid().shape
    minimum = body.bounding_box().min
    body = bd.Pos(-minimum.X,-minimum.Y,-minimum.Z) * body
    body.label = 'lid-print'
    return body


def print_pose(shape,name,rotation):
    body=rotation*shape
    minimum=body.bounding_box().min
    body=bd.Pos(-minimum.X,-minimum.Y,-minimum.Z)*body
    body.label=name
    return body


@model
def spine_print():
    return print_pose(spine().shape,'spine-print',bd.Rot(0,0,0))


@model
def carrier_print():
    # 负X大侧面朝床；打印高度从94.15降到14.3mm。
    return print_pose(carrier().shape,'carrier-print',bd.Rot(0,-90,0))


@model
def rear_fan_frame_print():
    # 后面Y142朝床，前伸定位键向上长出。
    return print_pose(rear_fan_frame().shape,'rear-fan-frame-print',bd.Rot(-90,0,0))


@model
def taco():
    # 原板保留全部实体及真实USB-C开放壳；不以薄片替代两面元件。
    source = bd.import_step(BOARD_STEP)
    solids = list(source.solids())
    assert len(solids) == 730
    for index, solid in enumerate(solids):
        solid.label = f'native-{index}'
        size = solid.bounding_box().size
        solid.color = '#285b49' if index == 0 else '#abb8b3' if max(size)>10 else '#35433d'
    # 原厂USB-C是开放壳，不能转成有效实体；按装配坐标包围盒识别。
    usbc_shells = []
    expected = (100.09591334,34.35,133.1,103.77591344,48.35,144.07)
    for shell in source.shells():
        placed = bd.Pos(72.1,120,135)*bd.Rot(0,180,0)*shell
        bounds = placed.bounding_box()
        measured = (*bounds.min,*bounds.max)
        if all(abs(a-b)<1e-4 for a,b in zip(measured,expected)):
            shell.label = 'native-usbc-shell'
            shell.color = '#abb8b3'
            usbc_shells.append(shell)
    assert len(usbc_shells) == 1, ('USB-C原厂开放壳数量变化',len(usbc_shells))
    # 其余非实体参考节点仍排除，730实体标签和索引保持稳定。
    board = bd.Compound(children=[*solids,*usbc_shells])
    board = bd.Pos(72.1, 120, 135) * bd.Rot(0, 180, 0) * board
    board.label = 'taco'
    return board


def envelope(x, y, z, dx, dy, dz, name, color):
    shape = box(x,y,z,dx,dy,dz)
    shape.label = name
    shape.color = color
    return shape


@model
def top_fan():
    # 通用92×14最大外形示意，不声明真实型号或风量。
    cx,cy = TOP_FAN_CENTER
    frame = box(*TOP_FAN_FRAME)-cyl(cx,cy,175.1,42,14.2)
    for x,y in TOP_FAN_HOLES:
        frame -= cyl(x,y,175.1,2.15,14.2)
    frame.label,frame.color = 'top-fan-frame','#303f39'
    rotor = cyl(cx,cy,176.2,12,12)
    for angle in range(0,360,60):
        blade = box(-3,11,177.2,6,27,10)
        rotor += bd.Pos(cx,cy,0)*bd.Rot(0,0,angle)*blade
    rotor.label,rotor.color = 'top-fan-rotor','#303f39'
    pieces = [frame,rotor]
    for index,(x,y) in enumerate(TOP_FAN_HOLES,1):
        screw = cyl(x,y,171.8,1.5,20)+cyl(x,y,191.8,2.85,1.7)
        screw.label,screw.color = f'top-fan-m3-{index}','#aebbb8'
        washer = cyl(x,y,174.7,3.5,.5)-cyl(x,y,174.6,1.7,.7)
        washer.label,washer.color = f'top-fan-washer-{index}','#aebbb8'
        radius = 5.5/sqrt(3)
        points = [(radius*cos(i*pi/3),radius*sin(i*pi/3)) for i in range(6)]
        nut = bd.Pos(x,y,172.9)*bd.extrude(bd.Polygon(*points,align=None),amount=1.8,dir=(0,0,1))
        nut -= cyl(x,y,172.8,1.5,2)
        nut.label,nut.color = f'top-fan-nut-{index}','#aebbb8'
        pieces.extend([screw,washer,nut])
    assert all(piece.is_valid for piece in pieces)
    return bd.Compound(children=pieces,label='top-fan')


@model
def lid_fasteners():
    pieces=[]
    for index,(x,y) in enumerate(LID_HOLES,1):
        screw=cyl(x,y,166.8,1.5,25)+cyl(x,y,191.8,2.85,1.7)
        screw.label,screw.color=f'lid-m3-{index}','#aebbb8'
        pieces.append(screw)
    return bd.Compound(children=pieces,label='lid-fasteners')


@model
def assembly():
    pieces = [shell().shape,lid().shape,spine().shape,rear_fan_frame().shape,
              top_fan().shape,lid_fasteners().shape]
    base = carrier().shape
    for i, x in enumerate(SATA_X,1):
        placed = bd.Pos(x-29, 0, 0) * base
        placed.label = f'carrier-{i}'
        pieces.append(placed)
        pieces.append(envelope(x-2.7,41.5,22.25,DRIVE_THICKNESS_MM,69.85,100.45,f'drive-{i}','#acb8b4'))
    pieces.append(taco().shape)
    fan = box(12,142,8,120,25,120)
    fan -= cyl(72,141,68,55,27,'y')
    for x in (19.5,124.5):
        for z in (15.5,120.5):
            fan -= cyl(x,141,z,1.7,27,'y')
    fan += cyl(72,142,68,15,25,'y')
    # 静态叶片包络用于识别，风量不由叶片模型推导。
    for angle in range(0,360,60):
        blade = box(-3,-10,14,6,20,38)
        blade = bd.Rot(0,angle,0) * blade
        fan += bd.Pos(72,154.5,68)*blade
    fan.label = 'fan-body'
    fan.color = '#303f39'
    fan_parts=[fan]
    for x in (19.5,124.5):
        for z in (15.5,120.5):
            screw=cyl(x,132,z,1.5,35,'y')+cyl(x,167,z,2.85,1.7,'y')
            screw.label=f'fan-m3-{x}-{z}'
            screw.color='#aebbb8'
            fan_parts.append(screw)
    pieces.append(bd.Compound(children=fan_parts,label='rear-fan'))
    pieces.append(envelope(41.5,60.9,140,55,40,3,'cm5','#245b45'))
    pieces.append(envelope(40,57,143,58,45,27,'cooler','#9eaaa7'))
    return bd.Compound(children=pieces, label='CyberMachine-r3-candidate')


if __name__ == '__main__':
    assembly()
