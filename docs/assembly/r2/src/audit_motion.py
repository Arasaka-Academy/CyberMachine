"""Sample lesson paths against exact OCCT solids; run audit.mjs first.

Socket mating surfaces and modeled screw seating are reported separately.
This is a sampled design check, not a continuous collision or physical-fit proof.
"""
from __future__ import annotations
from collections import defaultdict
from hashlib import sha256
from math import pi,cos,sin
from pathlib import Path
import json

from OCP.BRep import BRep_Builder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopoDS import TopoDS_Compound
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from mesh_model import (ROOT,WORK,HERE,shape_of,bounds,STEPControl_Reader,
    gp_Trsf,gp_Ax1,gp_Pnt,gp_Dir,gp_Vec,BRepBuilderAPI_Transform,
    TopExp_Explorer,TopAbs_SOLID)


def compound(items):
    result=TopoDS_Compound();builder=BRep_Builder();builder.MakeCompound(result)
    for item in items: builder.Add(result,item)
    return result


def overlaps(a,b):
    return all(min(a[i+3],b[i+3])-max(a[i],b[i])>.002 for i in range(3))


def transform(pose):
    t=gp_Trsf();t.SetRotation(gp_Ax1(gp_Pnt(*pose['pivot']),gp_Dir(1,0,0)),pose['angle'])
    old=t.TranslationPart();t.SetTranslationPart(gp_Vec(*[old.Coord(i+1)+pose['offset'][i] for i in range(3)]))
    return t


def moved_box(box,pose):
    if abs(pose['angle'])<1e-10:return [n+pose['offset'][i%3] for i,n in enumerate(box)]
    c,s=cos(pose['angle']),sin(pose['angle']);px,py,pz=pose['pivot'];dx,dy,dz=pose['offset']
    points=[(x+dx,py+(y-py)*c-(z-pz)*s+dy,pz+(y-py)*s+(z-pz)*c+dz)
            for x in [box[0],box[3]] for y in [box[1],box[4]] for z in [box[2],box[5]]]
    return [min(p[i] for p in points) for i in range(3)]+[max(p[i] for p in points) for i in range(3)]


def volume(a,b):
    operation=BRepAlgoAPI_Common(a,b);operation.SetFuzzyValue(.00001);operation.Build()
    if not operation.IsDone():raise RuntimeError('OCCT common failed')
    props=GProp_GProps();BRepGProp.VolumeProperties_s(operation.Shape(),props)
    return abs(props.Mass())


def main():
    source=json.loads((WORK/'analytic.json').read_text())
    groups={p['id']:[shape_of(s['shape']) for s in p['shapes']] for p in source['parts']}
    reader=STEPControl_Reader();reader.ReadFile(str(ROOT/'references/radxa-taco/radxa_taco_3d_stp_v1.61.stp'));reader.TransferRoots()
    t=gp_Trsf();t.SetRotation(gp_Ax1(gp_Pnt(0,0,0),gp_Dir(0,1,0)),pi);t.SetTranslationPart(gp_Vec(72.1,120,135))
    native=BRepBuilderAPI_Transform(reader.OneShape(),t,True).Shape()
    ex=TopExp_Explorer(native,TopAbs_SOLID);solids=[]
    while ex.More():solids.append(ex.Current());ex.Next()
    groups['taco']=solids
    local={name:[(s,bounds(s)) for s in items] for name,items in groups.items()}
    snapshots=json.loads((WORK/'poses.json').read_text())
    cache={};baseline={};findings={};stats=defaultdict(int)
    local_boxes={name:[min(box[i] for _,box in items) for i in range(3)]+[max(box[i] for _,box in items) for i in range(3,6)] for name,items in local.items()}

    def common_part(a,b,pa,pb):
        # Ignore only native receptacle shells involved in deliberate mating.
        omitted=set()
        other=a if b=='taco' else b
        if 'taco' in (a,b):
            if other.startswith('drive-'):omitted=set(range(691,696))
            if other=='cm5':omitted={706,707}
        ta,tb=transform(pa),transform(pb)
        aa=[(s,moved_box(box,pa)) for i,(s,box) in enumerate(local[a]) if not(a=='taco' and i in omitted)]
        bb=[(s,moved_box(box,pb)) for i,(s,box) in enumerate(local[b]) if not(b=='taco' and i in omitted)]
        candidates=[]
        for sa,ba in aa:
            hits=[BRepBuilderAPI_Transform(sb,tb,False).Shape() for sb,box in bb if overlaps(ba,box)]
            if hits:candidates.append((BRepBuilderAPI_Transform(sa,ta,False).Shape(),hits))
        total=0
        for sa,hits in candidates:
            stats['booleanOperations']+=1
            total+=volume(sa,compound(hits))
        return total

    # Exact broad-phase transformed bounds cached per pose and logical part.
    transformed={}
    def get_bounds(name,pose):
        key=(name,tuple(pose['offset']),pose['angle'],tuple(pose['pivot']))
        if key not in transformed:
            transformed[key]=moved_box(local_boxes[name],pose)
        return transformed[key]
    zero=dict(offset=[0,0,0],angle=0,pivot=[0,0,0])
    for si,state in enumerate(snapshots):
        active=[(n,p) for n,p in state['poses'].items() if p['visible']]
        for ai,(a,pa) in enumerate(active):
            for b,pb in active[ai+1:]:
                if pa['offset']==pb['offset'] and pa['angle']==pb['angle']:continue
                if not overlaps(get_bounds(a,pa),get_bounds(b,pb)):continue
                # Relative translation is enough when neither part rotates.
                signature=(a,b,tuple(round(pa['offset'][i]-pb['offset'][i],5) for i in range(3)),round(pa['angle'],7),round(pb['angle'],7))
                if signature in cache:continue
                stats['candidatePairs']+=1
                amount=common_part(a,b,pa,pb);cache[signature]=amount
                if amount<.02:continue
                pair=(a,b)
                if pair not in baseline:baseline[pair]=common_part(a,b,zero,zero)
                seated=baseline[pair]
                if amount>seated+.05:
                    entry={'parts':[a,b],'chapter':state['chapter']+1,'progress':state['progress'],'mode':state['thicknessMode'],'volumeMm3':round(amount,5),'seatedVolumeMm3':round(seated,5)}
                    first=pair not in findings
                    if first or findings[pair]['volumeMm3']<amount:findings[pair]=entry
                    if first:print('Contact',entry,flush=True)
        if si%100==0:print('Audited',si+1,'/',len(snapshots),'states;',len(findings),'path conflicts',flush=True)
    # Board additions must also be checked when fully seated; no baseline waiver.
    board_ids=['wifi-slot','wifi','cm5','cm5-cooler']
    seated=[]
    for ai,a in enumerate(board_ids):
        for b in ['taco',*board_ids[ai+1:]]:
            amount=common_part(a,b,zero,zero)
            seated.append({'parts':[a,b],'volumeMm3':round(amount,6)})
    cable_contacts=[];cable_checks=0
    cables=json.loads((WORK/'cables.json').read_text())
    obstacles=['taco','cm5','cm5-cooler','wifi-slot','wifi','right','front-fan','rear-fan','top-fan']
    for route in cables:
        for i,(a,b) in enumerate(zip(route['points'],route['points'][1:])):
            segment_box=[min(a[j],b[j])-.65 for j in range(3)]+[max(a[j],b[j])+.65 for j in range(3)]
            edge=None
            for name in obstacles:
                # The first 2 mm intentionally meets the module's antenna terminal.
                if name=='wifi' and i<10:continue
                for solid,box in local[name]:
                    if not overlaps(segment_box,box):continue
                    if edge is None:edge=BRepBuilderAPI_MakeEdge(gp_Pnt(*a),gp_Pnt(*b)).Edge()
                    distance=BRepExtrema_DistShapeShape(edge,solid);distance.Perform();cable_checks+=1
                    if distance.Value()<.64:
                        entry={'cable':route['id']+1,'terminalLiftMm':route['lift'],'segment':i,'part':name,'clearanceMm':round(distance.Value()-.65,5)}
                        if entry not in cable_contacts:cable_contacts.append(entry)
    report={'date':'2026-11-06','kind':'sampled exact B-rep motion audit','states':len(snapshots),
        'statistics':dict(stats),'pathConflicts':list(findings.values()),'seatedBoardContacts':seated,
        'antennaWires':{'routes':len(cables),'samplesPerRoute':201,'radiusMm':.65,'exactDistanceChecks':cable_checks,'contacts':cable_contacts,'intentionalContacts':'first 2 mm at wireless antenna terminals; wire ends enter FPC antenna pads'},
        'toleranceVolumeMm3':.05,'sampling':'101 uniform samples per chapter plus phase boundaries, all 3 thickness modes',
        'intentionalContacts':['native SATA shells 691-695 versus drive tongue','native CM5 carrier shells 706-707 versus CM5 mating connectors','seated screw heads, fasteners, and inherited R2 joined surfaces use final contact volume as baseline'],
        'limits':['sampled paths, not continuous swept-volume proof','antenna curves sampled every 1/200 curve parameter at 10 terminal heights; no flexible cable mechanics or RF validation','no physical trial, print, thermal, vibration, noise or driver test'],
        'sources':source['sources'],'lessonSha256':sha256((HERE/'lesson.mjs').read_bytes()).hexdigest()}
    out=ROOT/'validation/r2/assembly-motion.json';out.write_text(json.dumps(report,indent=2)+'\n')
    print('Path conflicts:',len(findings),'Cable contacts:',len(cable_contacts),'Seated board:',seated,flush=True)
    if findings or cable_contacts or any(contact['volumeMm3']>.05 for contact in seated):raise SystemExit(1)


if __name__=='__main__':main()
