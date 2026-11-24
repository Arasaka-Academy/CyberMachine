"""[INPUT]: design.py 模型、io_geometry.py 开孔轮廓与 cad 导出接口。
[OUTPUT]: 水平通风横带候选STEP/STL/GLB，以及9件打印朝向和紧固清单。
[POS]: R3 候选生成入口；不覆盖 R1 或 R2 正式资料。
[PROTOCOL]: Update this header on change, then check AGENTS.md
"""
from pathlib import Path
import json
import build123d as bd
from math import acos,sqrt
from cad import model
from design import (assembly, shell, lid, spine, carrier, rear_fan_frame, lid_fasteners,
                    lid_print, spine_print, carrier_print, rear_fan_frame_print, top_fan,
                    top_grille_tools, vent_slots, vent_tools, TOP_FAN_CENTER,
                    TOP_GRILLE_RADII, VENT_SLOT_WIDTH, VENT_MIDDLE_Z, VENT_CROSS_WEB_MM,
                    TOP_FAN_FRAME, TOP_FAN_HOLES, TOP_FAN_LEAD, BOARD_STEP,
                    SATA_X, BOARD_HOLES, DRIVE_THICKNESS_MM, FRAME_WEB_THICKNESS_MM, FRAME_WEB_X,
                    FRAME_DIAGONAL_WIDTH_MM, FRAME_BASE_HEIGHT_MM, FRAME_CROSSBEAM,
                    FRAME_FAN_UPRIGHT_THICKNESS_MM, FRAME_ROOT_CONE, FRAME_ROOT_RAMP, FRAME_FRONT_ROOT_CLIP_X,
                    REAR_FRAME_KEY_X,LID_HOLES,LID_SEAT_Z,LID_PILOT_BOTTOM_Z,
                    BASE_WEB_THICKNESS_MM,FRONT_FOOT_GUSSETS,SPINE_SIDE_BEAM_X,
                    ENCLOSURE_X_MIN,ENCLOSURE_WIDTH_MM)
from io_geometry import port_metadata
from hashlib import sha256

ROOT=Path(__file__).resolve().parents[4]
OUT=ROOT/'outputs/redesign-r3'
OUT.mkdir(parents=True,exist_ok=True)

if __name__ == '__main__':
    doc=assembly()
    model.export(doc,OUT/'CyberMachine-r3-candidate.step')
    model.export(doc,OUT/'preview.glb',tolerance=.08,angle=15)
    fan_doc=top_fan()
    model.export(fan_doc,OUT/'top-fan.step')
    lock_doc=lid_fasteners()
    model.export(lock_doc,OUT/'lid-fasteners.step')
    records=[]
    print_records=[]
    models={}
    assembly_functions=[('shell',shell),('lid',lid),('spine',spine),('carrier',carrier),
                        ('rear-fan-frame',rear_fan_frame)]
    print_functions=[('lid-print',lid_print),('spine-print',spine_print),
                     ('carrier-print',carrier_print),('rear-fan-frame-print',rear_fan_frame_print)]
    for name,fn in assembly_functions+print_functions:
        part=fn()
        model.export(part,OUT/f'{name}.step')
        model.export(part,OUT/f'{name}.stl',tolerance=.025,angle=12)
        shape=part.shape
        bounds=shape.bounding_box()
        models[name]=shape
        record={'name':name,'id':part.id,'boundsMm':[list(bounds.min),list(bounds.max)],
                'volumeMm3':shape.volume,'valid':shape.is_valid,'solids':len(shape.solids())}
        (print_records if name.endswith('-print') else records).append(record)
    print_records.insert(0,dict(records[0]))
    print_transforms={}
    for name,source,rotation,bed_face,quantity in (
            ('shell','shell',(0,0,0),'bottom Z0',1),
            ('lid-print','lid',(180,0,0),'outer top Z194',1),
            ('spine-print','spine',(0,0,0),'base Z8',1),
            ('carrier-print','carrier',(0,-90,0),'negative-X large side X24.3',5),
            ('rear-fan-frame-print','rear-fan-frame',(-90,0,0),'rear Y142',1)):
        rotated=bd.Rot(*rotation)*models[source]
        minimum=rotated.bounding_box().min
        print_transforms[name]={'source':source,'rotationDegXYZ':list(rotation),
            'translationMm':([0.,0.,0.] if name=='shell' else [-minimum.X,-minimum.Y,-minimum.Z]),
            'bedFace':bed_face,'quantity':quantity}
        next(part for part in print_records if part['name']==name).update(
            {'source':source,'quantity':quantity})
    data={'status':'candidate-not-print-release','boardSolids':730,'boardOpenShells':1,
          'boardOpenShellNames':['native-usbc-shell'],
          'boardSourceSha256':sha256(BOARD_STEP.read_bytes()).hexdigest(),
          'sourceSha256':sha256((Path(__file__).parent/'design.py').read_bytes()).hexdigest(),
          'previewGlbSha256':sha256((OUT/'preview.glb').read_bytes()).hexdigest(),
          'coordinateMapping':'CAD [x,y,z] mm -> glTF [x,z,-y] m',
          'assemblyId':doc.id,'nodes':['shell','lid','spine','rear-fan-frame']+[f'carrier-{i}' for i in range(1,6)]
          +[f'drive-{i}' for i in range(1,6)]+['taco','rear-fan','top-fan','lid-fasteners','cm5','cooler'],
          'parts':records,'hardware':{'boardScrews':'4 x M2.5 low-head x6, head <=4.5 mm diameter / 1.5 mm high, no washer; 4.4 mm nominal engagement and 0.5 mm blind-hole floor allowance; actual insert spec pending',
          'lidScrews':'4 x M3 ISO7380 button-head x25 vertical from top; head <=5.7 mm diameter / 1.7 mm high, no washer; clearance 3.4 mm, counterbore 6.3 x2.2 mm; pilot 4.1 x7.6 mm, nominal insert 5.4 mm; screw tip floor allowance 0.4 mm; actual insert spec pending',
          'spineScrews':'4 x M3 low-head x10 from shell bottom, shell clearance 3.4 / counterbore 6.3 x2.2, spine heat-set pilot 4.1 x4.8 mm',
          'driveScrews':'2 x M3 x5 + 0.5 mm washer per drive, head and washer <=5.5 mm, nominal engagement 2.1 mm subject to HDD limit; 1 x M3 x6 per carrier head <=5.5 mm, spine heat-set pilot 4.1 x4.8 mm',
          'fanScrews':'4 x M3 x35 from rear, head <=1.7 mm high without washer; frame clearance 3.4 x4 mm; main insert pilot 4.1 x6.4 mm, nominal 5.4 mm insert at Y138; actual insert spec pending',
          'topFanScrews':'4 x M3 button-head x20, ISO7380 candidate, head <=5.7 mm diameter / 1.7 mm high, no washer above; below fan use M3 washer OD7 x0.5 and thin M3 nut AF5.5 x1.8; 1.1 mm nominal tip beyond nut; tighten only until seated in PETG',
          'heatSetInsertCount':21,'heatSetInsertBreakdown':{'M3':17,'M2.5':4}},
          'unverified':['physical assembly','actual HDD holes and connector insertion','actual cooler height','thermal and acoustic tests']}
    data.update({'printParts':print_records,'printTransforms':print_transforms,'printPieceCount':9,
        'profiles':{'process':'PETG FDM','machineEnvelopeMm':[256,256,256],
                    'nozzleMm':.4,'layerMm':.2,'orientations':list(print_transforms)}})
    data['enclosure']={'outerBoundsMm':[[-5.,28.,0.],[149.,172.,194.]],
        'sizeMm':[ENCLOSURE_WIDTH_MM,144.,194.],'centerXYmm':[72.,100.],
        'shellHeightMm':174.,'lidOuterLowerZmm':174.3,
        'topFanOuterMarginsMm':{'leftRight':31.,'frontRear':26.}}
    lock_bounds=lock_doc.shape.bounding_box()
    data['lidClosure']={'id':lock_doc.id,'semanticNode':'lid-fasteners','movesWith':'lid',
        'mountingHolesXYmm':[list(point) for point in LID_HOLES],
        'fastenerCount':4,'screw':'M3 ISO7380 x25','axis':'Z',
        'boundsMm':[list(lock_bounds.min),list(lock_bounds.max)],
        'screwUnderHeadZmm':191.8,'screwTipZmm':166.8,'screwHeadTopZmm':193.5,
        'headCounterboreDiameterMm':6.3,'headCounterboreZmm':[191.8,194.],
        'clearanceDiameterMm':3.4,'seatTopZmm':LID_SEAT_Z,
        'insertPilotDiameterMm':4.1,'insertPilotZmm':[LID_PILOT_BOTTOM_Z,LID_SEAT_Z],
        'nominalTipFloorClearanceMm':.4,'nominalInsertLengthMm':5.4,
        'nominalInsertZmm':[168.6,174.],'nominalScrewBeyondInsertMm':1.8,
        'compressionSleeveOuterDiameterMm':12.,'compressionSleeveZmm':[174.,191.4],
        'sleeveRoot':{'lowerZmm':187.2,'transitionTopZmm':189.2,
                      'upperZmm':191.4,'diametersMm':[12.,16.],'angleDeg':45.},
        'shellSeats':{'shape':'wall-integrated-D','internalSizeXYmm':[10.4,12.],
            'innerCornerRadiusMm':2.,'zMm':[164.,174.],
            'xMm':[[-2.2,8.2],[135.8,146.2]],
            'pilotSidewallMm':{'wallSideToInnerWallPlane':3.15,'inside':3.15,'frontRear':3.95},
            'blindFloorMaterialMm':2.4,'wallRampAngleDeg':45.,
            'leftWallRampXZmm':[[-2.3,153.5],[8.2,164.],[-2.3,164.]],
            'rightWallRampXZmm':[[146.3,153.5],[135.8,164.],[146.3,164.]],
            'modeledRampXmm':[[-2.3,8.2],[135.8,146.3]],'rampYHalfWidthMm':6.},
        'spigotBypass':{'pattern':'closed-U-detour','wallThicknessMm':2.4,
            'seatClearanceMm':.35,'zMm':[169.3,177.3],
            'insideExtentXmm':[10.95,133.05],'yHalfExtentMm':8.75},
        'spigotSeats':{'yMm':[[70.,78.],[122.,130.]],'topZmm':169.3,
                        'nominalTotalContactAreaMm2':76.8},
        'nominalSeatContactAreaPerPointMm2':3.141592653589793*(6**2-2.05**2)-(36*acos(5.2/6)-5.2*sqrt(36-5.2**2)),
        'appearanceGapMm':.3,'spigotClearancePerSideMm':.35,
        'opening':'Remove all four top screws, then lift lid vertically with attached top fan; unplug its lead before full removal.',
        'boundary':'Nominal solid geometry only. PETG strength, insert fit, preload and physical hand access remain unverified.'}
    data['baseMounts']={'mountingHolesXYmm':[list(point) for point in ((10.,36.),(134.,36.),(10.,132.),(134.,132.))],
        'shellBossDiameterMm':9.,'contactZmm':8.,'shellWebThicknessMm':BASE_WEB_THICKNESS_MM,
        'shellWebXmm':[[-2.3,6.2],[137.8,146.3]],'shellWebZmm':[2.7,8.],
        'frontSpineGussetsXYmm':[[list(point) for point in points] for points in FRONT_FOOT_GUSSETS],
        'frontSpineGussetZmm':[8.,14.],'carrierBottomGapMm':5.85}
    data['baseMounts']['spineSideBeamXmm']=[[x,x+6] for x in SPINE_SIDE_BEAM_X]
    data['rearFanJoint']={'semanticNode':'rear-fan-frame','movesWith':'spine',
        'frameYmm':[138.,142.],'mainUprightYmm':[127.,138.],
        'screw':'4 x M3 x35; same screws clamp fan and frame',
        'screwUnderHeadYmm':167.,'screwTipYmm':132.,'blindFloorYmm':131.6,
        'nominalTipAllowanceMm':.4,'insertCountAdded':0,
        'keys':{'centersXZmm':[[x,68.] for x in REAR_FRAME_KEY_X],
                'maleSizeMm':[3.,1.5,5.],'maleYmm':[136.5,138.],
                'pocketSizeMm':[3.6,1.8,5.6],'pocketYmm':[136.2,138.],
                'nominalClearancePerSideMm':.3,'remainingUprightSidewallMm':1.2},
        'boundary':'Nominal locating and clamping geometry only. Insert dimensions, printed joint fit and vibration are unverified.'}
    data['ports']=port_metadata()
    data['driveThicknessMm']=DRIVE_THICKNESS_MM
    data['driveSpecification']={
        'count':5,'thicknessMm':DRIVE_THICKNESS_MM,'datum':'negative-X',
        'sataXmm':list(SATA_X),'status':'7mm-only-user-confirmed',
        'bayEnvelopes':[{'bay':i,'boundsMm':[[x-2.7,41.5,22.25],
            [x-2.7+DRIVE_THICKNESS_MM,111.35,122.7]]} for i,x in enumerate(SATA_X,1)],
        'boundary':'Nominal 7 mm envelopes only. Exact HDD model holes, connector insertion and screw depth still need physical confirmation.'}
    data['frameReinforcement']={
        'baselineSourceSha256':'e874404198cd09697694dc932cd375fd87b6e8dfde03335970dd293193a73b7a',
        'baselineSpineVolumeMm3':82897.49201150429,
        'spineVolumeMm3':next(part['volumeMm3'] for part in records if part['name']=='spine'),
        'longitudinalWebThicknessMm':FRAME_WEB_THICKNESS_MM,
        'longitudinalWebXmm':[[x,x+FRAME_WEB_THICKNESS_MM] for x in FRAME_WEB_X],
        'diagonalWidthMm':FRAME_DIAGONAL_WIDTH_MM,'outerWebWidthMm':8.,
        'baseHeightMm':FRAME_BASE_HEIGHT_MM,'baseZmm':[8.,8.+FRAME_BASE_HEIGHT_MM],
        'crossbeamBoundsMm':[list(FRAME_CROSSBEAM[:3]),
            [FRAME_CROSSBEAM[i]+FRAME_CROSSBEAM[i+3] for i in range(3)]],
        'crossbeamNominalCarrierGapMm':19.85-(FRAME_CROSSBEAM[2]+FRAME_CROSSBEAM[5]),
        'rearCarrierStopZmm':22.25,'rearCarrierBeamBoundsMm':[[7.,114.4,22.25],[137.,120.8,28.25]],
        'rearCarrierUnderWebThicknessMm':3.6,
        'boardSupportTopDiameterMm':5.,'boardSupportTopZmm':133.4,
        'boardRootGussets':{'centersXYmm':[list(point) for point in BOARD_HOLES],
            'bottomRadiusMm':FRAME_ROOT_CONE[0],'topRadiusMm':FRAME_ROOT_CONE[1],
            'zMm':[FRAME_ROOT_CONE[2],FRAME_ROOT_CONE[2]+FRAME_ROOT_CONE[3]],
            'lowerRampZmm':[FRAME_ROOT_RAMP[2],FRAME_ROOT_RAMP[2]+FRAME_ROOT_RAMP[3]],
            'lowerRampRadiiMm':list(FRAME_ROOT_RAMP[:2]),'lowerRampAngleDeg':45.,
            'rearMinimumYmm':114.4,'frontPositiveXClipMm':list(FRAME_FRONT_ROOT_CLIP_X)},
        'rearFanUprightThicknessMm':FRAME_FAN_UPRIGHT_THICKNESS_MM,
        'rearFanFrameVolumeMm3':next(part['volumeMm3'] for part in records if part['name']=='rear-fan-frame'),
        'windowRoof':{'angleDeg':45.,'topZmm':108.,
            'windowsYmm':[[43.,56.2],[64.2,120.]],'roofStartZmm':[101.4,80.1]},
        'rearFanCornerGussets':{'count':4,'legLengthMm':18.,'yMm':[134.,138.],
            'outerXmm':[9.75,135.75],'outerZmm':[8.,128.]},
        'boundary':'B-rep material and nominal cross-sections only. Stiffness, fatigue, vibration and printed part strength are not verified.'}
    b=fan_doc.shape.bounding_box()
    frame=TOP_FAN_FRAME
    lead=TOP_FAN_LEAD
    grille_area=sum(tool.volume/3.5 for tool in top_grille_tools())
    data['topFan']={
        'id':fan_doc.id,'semanticNode':'top-fan','movesWith':'lid',
        'status':'generic-envelope-not-selected-product','nominalSizeMm':[92,92,14],
        'maximumThicknessIncludesFactoryPads':True,
        'centerMm':list(TOP_FAN_CENTER),
        'boundsMm':[list(b.min),list(b.max)],
        'frameBoundsMm':[list(frame[:3]),[frame[i]+frame[i+3] for i in range(3)]],
        'mountingHolesMm':[list(point) for point in TOP_FAN_HOLES],
        'fanMountingHoleDiameterMm':4.3,'lidClearanceHoleDiameterMm':3.4,
        'grilleTopZ':194.,'roofInnerZ':191.2,'hardStandoffHeightMm':2.,
        'coolerNominalGapMm':5.2,'grilleSlotWidthMm':3.2,'grillePitchMm':6.,
        'grilleCrossbarWidthMm':4.,'grilleReferenceDiameterMm':84.,
        'grillePattern':'seven-concentric-interrupted-rings',
        'grilleCenterlineRadiiMm':list(TOP_GRILLE_RADII),
        'grilleRadialRibWidthMm':2.8,'grilleRoofThicknessMm':2.8,
        'grilleOpenAreaMm2':grille_area,
        'grilleOpenFractionOfReferenceDisk':grille_area/(3.141592653589793*42**2),
        'leadReservationBoundsMm':[list(lead[:3]),[lead[i]+lead[i+3] for i in range(3)]],
        'screwUnderHeadZ':191.8,'screwTipZ':171.8,'washerZ':[174.7,175.2],
        'nutZ':[172.9,174.7],'nominalTipBeyondNutMm':1.1,
        'airflowIntent':'top intake downward; rear 120 mm exhaust',
        'verificationBoundary':'Fan envelope, hole locations and fasteners are nominal. Select an actual fan before manufacture. Added pads change clearance and thread allowance. No cable connector, electrical capacity, vibration or airflow performance is verified.'}
    data['ventilation']={
        'patternFamily':'record-rings-and-organ-pipes',
        'frontLower':{'planeY':28.,'wallThicknessMm':2.8,'slotWidthMm':VENT_SLOT_WIDTH,'columnPitchMm':8.,
            'slotsXBottomTopMm':[list(slot) for slot in vent_slots()],
            'openAreaMm2':sum(tool.volume/5 for tool in vent_tools(27)),
            'boundsXZMm':[[13.8,14.],[130.2,126.]],'nominalMinimumCrossWebMm':VENT_CROSS_WEB_MM,
            'middleBandPattern':'horizontal-straight','middleBandCenterZMm':VENT_MIDDLE_Z,
            'middleBandZMm':[VENT_MIDDLE_Z-VENT_CROSS_WEB_MM/2,VENT_MIDDLE_Z+VENT_CROSS_WEB_MM/2],
            'nominalMinimumColumnWebMm':8-VENT_SLOT_WIDTH},
        'rearLower':{'planeY':172.,'wallThicknessMm':2.8,'slotWidthMm':VENT_SLOT_WIDTH,'columnPitchMm':8.,
            'slotsXBottomTopMm':[list(slot) for slot in vent_slots()],
            'openAreaMm2':sum(tool.volume/5 for tool in vent_tools(168)),
            'boundsXZMm':[[13.8,14.],[130.2,126.]],'nominalMinimumCrossWebMm':VENT_CROSS_WEB_MM,
            'middleBandPattern':'horizontal-straight','middleBandCenterZMm':VENT_MIDDLE_Z,
            'middleBandZMm':[VENT_MIDDLE_Z-VENT_CROSS_WEB_MM/2,VENT_MIDDLE_Z+VENT_CROSS_WEB_MM/2],
            'nominalMinimumColumnWebMm':8-VENT_SLOT_WIDTH},
        'rearUpper':{'planeY':172.,'wallThicknessMm':2.8,'slotWidthMm':VENT_SLOT_WIDTH,'columnPitchMm':8.,
            'slotsXBottomTopMm':[list(slot) for slot in vent_slots(True)],
            'openAreaMm2':sum(tool.volume/5 for tool in vent_tools(168,True)),
            'boundsXZMm':[[13.8,143.],[130.2,168.]],'nominalMinimumColumnWebMm':8-VENT_SLOT_WIDTH},
        'top':{'centerMm':list(TOP_FAN_CENTER),'wallThicknessMm':2.8,
            'slotRadialWidthMm':3.2,'radialPitchMm':6.,'spokeWidthMm':4.,
            'slotCenterlineRadiiMm':list(TOP_GRILLE_RADII),'openAreaMm2':grille_area},
        'boundary':'Open areas are nominal face areas, not airflow, pressure drop, grille rigidity or safety ratings.'}
    data['ioSourceSha256']=sha256((Path(__file__).parent/'io_geometry.py').read_bytes()).hexdigest()
    data['exportedStepSha256']={path.name:sha256(path.read_bytes()).hexdigest()
                                for path in sorted(OUT.glob('*.step'))}
    (OUT/'metadata.json').write_text(json.dumps(data,indent=2)+'\n')
