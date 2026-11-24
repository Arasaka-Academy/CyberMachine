"""[INPUT]: 原厂 STEP、本轮 R3 分件 STEP 与设计及I/O源码哈希。
[OUTPUT]: 九件候选干涉、730原厂实体逐件交叠、座区连续隔离和抽取采样报告。
[POS]: R3 精确实体验算；已知碰撞对照防止原厂多实体Compound布尔漏检。
[PROTOCOL]: Update this header on change, then check AGENTS.md
"""
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from datetime import datetime, timezone
import json
from math import pi

from OCP.BRep import BRep_Builder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS_Compound
from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

ROOT=Path(__file__).resolve().parents[4]
OUT=ROOT/'outputs/redesign-r3'
REPORT=ROOT/'validation/r3/geometry.json'
SATA_X=(29.,50.5,72.,93.5,115.)
DRIVE_THICKNESS_MM=7.


def read(path):
    reader=STEPControl_Reader()
    if int(reader.ReadFile(str(path))) != 1:
        raise RuntimeError(f'Cannot read {path}')
    reader.TransferRoots()
    return reader.OneShape()


def moved(shape,xyz=(0,0,0),angle=0):
    t=gp_Trsf()
    if angle:
        t.SetRotation(gp_Ax1(gp_Pnt(0,0,0),gp_Dir(0,1,0)),angle)
    t.SetTranslationPart(gp_Vec(*xyz))
    return BRepBuilderAPI_Transform(shape,t,False).Shape()


def solids(shape):
    result=[]
    ex=TopExp_Explorer(shape,TopAbs_SOLID)
    while ex.More():
        result.append(ex.Current())
        ex.Next()
    return result


def compound(items):
    builder=BRep_Builder()
    result=TopoDS_Compound()
    builder.MakeCompound(result)
    for shape in items:
        builder.Add(result,shape)
    return result


def volume(shape):
    props=GProp_GProps()
    BRepGProp.VolumeProperties_s(shape,props)
    return props.Mass()


def bounds(shape):
    box=Bnd_Box()
    BRepBndLib.AddOptimal_s(shape,box)
    a,b=box.CornerMin(),box.CornerMax()
    return (a.X(),a.Y(),a.Z(),b.X(),b.Y(),b.Z())


def candidate(a,b,tol=1e-6):
    return all(min(a[i+3],b[i+3])-max(a[i],b[i])>tol for i in range(3))


def overlap(a,b,known_a=None,known_b=None):
    if not candidate(known_a or bounds(a),known_b or bounds(b)):
        return 0.
    op=BRepAlgoAPI_Common(a,b)
    if not op.IsDone():
        raise RuntimeError('Common failed')
    return max(0.,volume(op.Shape()))


def distance(a,b):
    query=BRepExtrema_DistShapeShape(a,b)
    query.Perform()
    if not query.IsDone():
        raise RuntimeError('Distance failed')
    return query.Value()


def block(x,y,z,dx,dy,dz):
    return BRepPrimAPI_MakeBox(gp_Pnt(x,y,z),dx,dy,dz).Shape()


def records(items):
    return [(name,shape,bounds(shape)) for name,shape in items]


def individual_overlaps(shape,items):
    # 原厂多实体Compound有已知布尔漏检；逐闭合实体执行，必须包含PCB实体0。
    box=bounds(shape)
    checked=[]
    for name,part,part_box in items:
        if candidate(box,part_box):
            checked.append({'part':name,'overlapMm3':overlap(shape,part,box,part_box)})
    return sum(item['overlapMm3'] for item in checked),checked


def main():
    printed={name:read(OUT/f'{name}.step') for name in ('shell','lid','spine','carrier','rear-fan-frame')}
    data={'date':datetime.now(timezone.utc).date().isoformat(),'status':'candidate','toleranceVolumeMm3':1e-4,'parts':{},'conflicts':[],
          'scope':'Exact OCCT solid booleans. Nonzero intentional seating contact is not permitted as overlap.',
          'notVerified':['actual solder tails','specific HDD connector geometry and insertion depth',
                         'specific cooler and CM5 attachment','fastener thread strength','support removal',
                         'physical assembly','temperature vibration and noise']}
    data['sourceSha256']=sha256((Path(__file__).parent/'design.py').read_bytes()).hexdigest()
    data['ioSourceSha256']=sha256((Path(__file__).parent/'io_geometry.py').read_bytes()).hexdigest()
    data['candidateStepSha256']={name:sha256((OUT/f'{name}.step').read_bytes()).hexdigest() for name in printed}
    data['purchasedStepSha256']={'top-fan':sha256((OUT/'top-fan.step').read_bytes()).hexdigest()}
    for name,shape in printed.items():
        data['parts'][name]={'valid':BRepCheck_Analyzer(shape).IsValid(),'solids':len(solids(shape)),
                              'boundsMm':bounds(shape),'volumeMm3':volume(shape)}
    source=ROOT/'references/radxa-taco/radxa_taco_3d_stp_v1.61.stp'
    native=moved(read(source),(72.1,120,135),pi)
    components=solids(native)
    assert len(components)==730,len(components)
    native_records=records([(f'native-{i}',part) for i,part in enumerate(components)])
    # 已知旧D座投影用于失败对照。混合树及纯闭合实体Compound均曾漏掉该碰撞。
    control=block(2.8,42.,0,8.7,12,200)
    control_total,control_parts=individual_overlaps(control,native_records)
    control_pcb=overlap(control,components[0])
    assert control_pcb>1. and control_total>=control_pcb-1e-5,control_parts
    data['nativeBooleanFailureControl']={'witnessBoundsMm':bounds(control),
        'knownBlockedCandidate':'144mm case, old left D seat X2.8..11.5/Y42..54',
        'pcb0OverlapMm3':control_pcb,'all730PerSolidOverlapMm3':control_total,
        'positiveParts':[item for item in control_parts if item['overlapMm3']>1e-4],
        'legacyMixedTreeCommonOverlapMm3':overlap(native,control),
        'pureClosedSolidsCompoundCommonOverlapMm3':overlap(compound(components),control),
        'verdictMethod':'Closed native solids individually, including PCB entity 0; both mixed-tree and pure-solid Compound Common are diagnostic only.'}
    print('Known blocked-seat control:',round(control_total,6),
          'mm3 per native solid; PCB0:',round(control_pcb,6),'mm3',flush=True)
    data['boardSourceSha256']=sha256(source.read_bytes()).hexdigest()
    data['boardSolids']=len(components)
    data['boardBoundsMm']=bounds(native)
    data['nativeBoardVolumeMm3']=volume(native)
    electronics=compound(components[1:])
    boardcheck=[]
    for name in ('shell','lid','spine','rear-fan-frame'):
        shape=printed[name]
        amount,per_solid=individual_overlaps(shape,native_records)
        gap=distance(shape,electronics)
        boardcheck.append({'part':name,'boardOverlapMm3':amount,'electronicsMinDistanceMm':gap,
                           'nativeSolidsChecked':730,'candidateSolidChecks':per_solid})
        if amount>1e-4:
            data['conflicts'].append({'a':name,'b':'native-taco','overlapMm3':amount})
    data['boardChecks']=boardcheck
    print('Board and printed-part checks complete',flush=True)
    allparts={k:v for k,v in printed.items() if k!='carrier'}
    allparts.update({f'carrier-{i+1}':moved(printed['carrier'],(x-29,0,0)) for i,x in enumerate(SATA_X)})
    pairchecks=[]
    for (a,sa),(b,sb) in combinations(allparts.items(),2):
        amount=overlap(sa,sb)
        pairchecks.append({'a':a,'b':b,'overlapMm3':amount})
        if amount>1e-4:
            data['conflicts'].append(pairchecks[-1])
    data['printedPairs']=pairchecks
    drivechecks=[]
    for index,x in enumerate(SATA_X,1):
        drive=block(x-2.7,41.5,22.25,DRIVE_THICKNESS_MM,69.85,100.45)
        for name,shape in allparts.items():
            amount=overlap(shape,drive)
            if amount>1e-4:
                data['conflicts'].append({'a':name,'b':f'drive-{index}','thicknessMm':DRIVE_THICKNESS_MM,'overlapMm3':amount})
        drivechecks.append({'bay':index,'thicknessMm':DRIVE_THICKNESS_MM,'boundsMm':bounds(drive)})
    data['driveSpecification']={'count':5,'thicknessMm':DRIVE_THICKNESS_MM,'datum':'negative-X','bays':drivechecks}
    print('Five 7 mm HDD envelopes complete',flush=True)
    purchased={'fan-envelope':block(12,142,8,120,25,120),
               'cm5-envelope':block(41.5,60.9,140,55,40,3),
               'cooler-envelope':block(40,57,143,58,45,27),
               'top-fan-envelope':block(26,54,175.2,92,92,14),
               'top-fan-hardware':read(OUT/'top-fan.step'),
               'lid-fasteners':read(OUT/'lid-fasteners.step')}
    for x in (19.5,124.5):
        for z in (15.5,120.5):
            purchased[f'fan-head-{x}-{z}']=BRepPrimAPI_MakeCylinder(
                gp_Ax2(gp_Pnt(x,167,z),gp_Dir(0,1,0)),2.85,1.7).Shape()
    purchased.update({f'drive-{i+1}':block(x-2.7,41.5,22.25,DRIVE_THICKNESS_MM,69.85,100.45) for i,x in enumerate(SATA_X)})
    purchasedchecks=[]
    for name,shape in purchased.items():
        for printed_name,printed_shape in allparts.items():
            amount=overlap(shape,printed_shape)
            purchasedchecks.append({'a':name,'b':printed_name,'overlapMm3':amount})
            if amount>1e-4:
                data['conflicts'].append(purchasedchecks[-1])
    data['purchasedEnvelopeChecks']=purchasedchecks
    data['topFanChecks']={
        'frameEnvelopeToCoolerMm':distance(purchased['top-fan-envelope'],purchased['cooler-envelope']),
        'completeGeometryToCoolerMm':distance(purchased['top-fan-hardware'],purchased['cooler-envelope']),
        'completeGeometryNativeOverlapMm3':individual_overlaps(purchased['top-fan-hardware'],native_records)[0],
        'frameEnvelopeCoolerOverlapMm3':overlap(purchased['top-fan-envelope'],purchased['cooler-envelope'])}
    if (data['topFanChecks']['completeGeometryNativeOverlapMm3']>1e-4 or
            data['topFanChecks']['frameEnvelopeCoolerOverlapMm3']>1e-4 or
            data['topFanChecks']['frameEnvelopeToCoolerMm']<5.19):
        data['conflicts'].append({'a':'top-fan','b':'cooler/native','checks':data['topFanChecks']})
    # 箱体保持固定；整个内部总成沿Z上提。10mm采样不等于连续扫掠证明。
    b=bounds(native)
    native_envelope=block(*b[:3],b[3]-b[0],b[4]-b[1],b[5]-b[2])
    inner=compound([shape for name,shape in allparts.items() if name not in ('shell','lid')]
                   +[native_envelope]+[shape for name,shape in purchased.items()
                                      if not name.startswith('top-fan') and name!='lid-fasteners'])
    exact_inner=compound([shape for name,shape in allparts.items() if name not in ('shell','lid')]
                   +components+[shape for name,shape in purchased.items()
                                if not name.startswith('top-fan') and name!='lid-fasteners'])
    moving_parts=[(name,shape) for name,shape in allparts.items() if name not in ('shell','lid')]
    moving_parts += [(name,shape) for name,shape in purchased.items()
                     if not name.startswith('top-fan') and name!='lid-fasteners']
    moving_records=records(moving_parts)
    exact_records=moving_records+native_records
    conservative_records=moving_records+records([('conservative-native-board-box',native_envelope)])
    # 整个内部实体与新座XY竖柱无交集，证明新座对任意Z直提位移隔离。
    isolation=[]
    inner_exact_bounds=bounds(exact_inner)
    assert inner_exact_bounds[2]>=0 and inner_exact_bounds[5]<=200
    for x,y in ((3.,48.),(141.,48.),(3.,152.),(141.,152.)):
        witness=block(-2.3 if x<72 else 135.8,y-6,0,10.5,12,200)
        native_amount,native_items=individual_overlaps(witness,native_records)
        all_amount,all_items=individual_overlaps(witness,exact_records)
        assert native_amount<1e-4 and all_amount<1e-4,(x,y,native_amount,all_amount)
        isolation.append({'centerXYmm':[x,y],'witnessBoundsMm':bounds(witness),
            'nativeBoardProjectionOverlapMm3':native_amount,
            'completeCartridgeProjectionOverlapMm3':all_amount,
            'nativeSolidsChecked':730,'perSolidCandidateChecks':native_items,
            'cartridgeCandidateChecks':all_items})
    data['newLidSeatsContinuousLiftIsolation']={'regions':isolation,
        'actualCartridgeBoundsMm':inner_exact_bounds,
        'basis':'All cartridge solids and conservative purchased envelopes lie within witness Z0..200. Zero intersection with each full-height seat XY prism proves those added seat/ramp footprints cannot intersect any Z translation. Original shell surfaces still use pose checks.',
        'includesNativeBoardSolids':len(components)}
    shell_bounds=bounds(printed['shell'])
    inner_bounds=bounds(inner)
    path=[]
    for z in range(0,201,10):
        translated=tuple(n+z if i in (2,5) else n for i,n in enumerate(inner_bounds))
        def at_pose(items):
            return [(name,moved(shape,(0,0,z)),tuple(n+z if i in (2,5) else n for i,n in enumerate(box)))
                    for name,shape,box in items]
        conservative_amount,_=individual_overlaps(printed['shell'],at_pose(conservative_records))
        amount=(individual_overlaps(printed['shell'],at_pose(exact_records))[0]
                if conservative_amount>1e-4 else conservative_amount)
        path.append({'liftMm':z,'overlapMm3':amount,
                     'conservativeBoardBoxOverlapMm3':conservative_amount,
                     'verdictBasis':'exact 730 board solids' if conservative_amount>1e-4 else 'conservative board box clear'})
        print('Lift',z,'overlap',round(amount,6),flush=True)
    data['cartridgeLift']={'stepMm':10,'rangeMm':[0,200],'samples':path,
                           'includes':'Lid and attached top fan removed first. Exact internal printed pieces including the rear fan frame and keys, five 7 mm HDD envelopes, rear fan/CM5/cooler design envelopes, four rear fan screw heads, conservative solid envelope of all native board components.',
                           'limitations':'Original shell checks are discrete poses. Conservative board-box failures are retained and resolved with all 730 native solids; added lid seats also have continuous XY isolation proof. Wiring, actual solder tail height and actual mating depths are excluded.'}
    data['cartridgeLift']['overlapMetric']='Sum of per-solid intersections; not a geometric union volume. Zero is the required verdict.'
    for item in path:
        if item['overlapMm3']>1e-4:
            data['conflicts'].append({'a':'shell','b':'cartridge','liftMm':item['liftMm'],'overlapMm3':item['overlapMm3']})
    data['passed']=not data['conflicts'] and all(p['valid'] and p['solids']==1 for p in data['parts'].values())
    data['checkedAt']=datetime.now(timezone.utc).isoformat()
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(data,indent=2)+'\n')
    summary=[{k:v for k,v in item.items() if k!='candidateSolidChecks'} for item in boardcheck]
    print(json.dumps({'passed':data['passed'],'boardChecks':summary,'conflicts':data['conflicts'],'report':str(REPORT)},indent=2),flush=True)
    if not data['passed']:
        raise SystemExit(1)


if __name__=='__main__':
    main()
