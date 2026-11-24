"""[INPUT]: 本轮导出的二进制 STL，不读取 CAD 内存模型。
[OUTPUT]: 三角网格闭合、边方向、连通体及有向体积报告。
[POS]: 验证实际候选网格；不证明切片、支撑拆除或实物配合。
[PROTOCOL]: Update this header on change, then check AGENTS.md
"""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[4]


def inspect(path):
    data=path.read_bytes()
    count=struct.unpack_from('<I',data,80)[0]
    assert len(data)==84+50*count,'要求标准二进制 STL'
    vertices={}
    parents=[]
    edges=Counter()
    winding=Counter()
    volume=0.

    def vertex(point):
        key=tuple(round(v,5) for v in point)
        if key not in vertices:
            vertices[key]=len(parents)
            parents.append(len(parents))
        return vertices[key]

    def root(i):
        while parents[i]!=i:
            parents[i]=parents[parents[i]]
            i=parents[i]
        return i

    degenerate=0
    for triangle in struct.iter_unpack('<12fH',data[84:]):
        points=[triangle[i:i+3] for i in (3,6,9)]
        ids=[vertex(p) for p in points]
        if len(set(ids))<3:
            degenerate+=1
        for a,b in ((ids[0],ids[1]),(ids[1],ids[2]),(ids[2],ids[0])):
            edge=tuple(sorted((a,b)))
            edges[edge]+=1
            winding[edge]+=1 if a<b else -1
            parents[root(a)]=root(b)
        a,b,c=points
        cross=(b[1]*c[2]-b[2]*c[1],b[2]*c[0]-b[0]*c[2],b[0]*c[1]-b[1]*c[0])
        volume+=sum(a[i]*cross[i] for i in range(3))/6
    non_manifold=sum(n!=2 for n in edges.values())
    inconsistent=sum(n!=0 for n in winding.values())
    components=len({root(i) for i in range(len(parents))})
    result={'file':str(path.relative_to(ROOT)),'sha256':sha256(data).hexdigest(),
            'triangles':count,'vertices':len(vertices),'components':components,
            'nonManifoldEdges':non_manifold,'inconsistentEdges':inconsistent,
            'degenerateTriangles':degenerate,'signedVolumeMm3':volume,
            'watertight':non_manifold==0,'windingConsistent':inconsistent==0}
    assert non_manifold==0 and inconsistent==0 and degenerate==0 and components==1 and volume>0,result
    return result


if __name__=='__main__':
    parts=[inspect(ROOT/f'outputs/redesign-r3/{name}.stl')
           for name in ('shell','lid','spine','carrier','rear-fan-frame',
                        'lid-print','spine-print','carrier-print','rear-fan-frame-print')]
    report={'checkedAt':datetime.now(timezone.utc).isoformat(),'passed':True,
            'coordinateWeldToleranceMm':1e-5,'parts':parts,
            'scope':'Exported binary STL edge topology and oriented volume. '
                    'Does not prove self-intersection freedom, slicing, print supports or physical fits.'}
    (ROOT/'validation/r3/mesh.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(parts,indent=2))
