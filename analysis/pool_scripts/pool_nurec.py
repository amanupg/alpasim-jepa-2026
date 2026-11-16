import glob, json, random, sys
R="/insomnia001/depts/edu/users/au2327/alpasim-jepa/runs"
def load(tag):
    d={}
    for g in sorted(glob.glob(f"{R}/nurec_garage2_{tag}_c*/aggregate/results-summary.json")):
        for r in json.load(open(g))["rollouts"]:
            m=r.get("score_metrics") or {}
            d[r["clipgt_id"]]=(float(r.get("score") or 0),float(m.get("offroad") or 0),float(m.get("left_corridor_laterally") or 0),float(m.get("collision_at_fault") or 0))
    return d
b=load(sys.argv[1]); x=load(sys.argv[2])
k=sorted(set(b)&set(x)); d=[x[i][0]-b[i][0] for i in k]
rng=random.Random(0); ms=sorted(sum(rng.choice(d) for _ in d)/len(d) for _ in range(5000))
nz=sum(1 for i in k if b[i][0]>0 and x[i][0]==0); fx=sum(1 for i in k if b[i][0]==0 and x[i][0]>0)
s=lambda D,j:int(sum(D[i][j]>0 for i in k))
print(f"{sys.argv[2]} vs {sys.argv[1]}: n={len(k)} (base {len(b)}, var {len(x)}) mean {sum(x[i][0] for i in k)/len(k):.4f} vs {sum(b[i][0] for i in k)/len(k):.4f} diff {sum(d)/len(d):+.4f} [90% {ms[250]:+.4f}, {ms[4750]:+.4f}] W{sum(t>1e-9 for t in d)}/L{sum(t<-1e-9 for t in d)} newzero {nz} fixed {fx} | offroad {s(b,1)}->{s(x,1)} corridor {s(b,2)}->{s(x,2)} atfault {s(b,3)}->{s(x,3)}")
