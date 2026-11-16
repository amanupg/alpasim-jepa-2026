import glob, json, random, sys
R="/insomnia001/depts/edu/users/au2327/alpasim-jepa/runs"
P=["002","004","006","008","009","012","015"]
def load(pat):
    d={}
    for p in P:
        g=glob.glob(f"{R}/{pat.format(p=p)}/aggregate/results-summary.json")
        if not g: print("missing",pat,p); continue
        for r in json.load(open(g[0]))["rollouts"]:
            m=r.get("score_metrics") or {}
            d[r["clipgt_id"]]=(float(r.get("score") or 0),float(m.get("offroad") or 0),float(m.get("left_corridor_laterally") or 0),float(m.get("collision_at_fault") or 0))
    return d
b=load("nuplan_garage2_w1fresh{p}_0_*")
PFX=sys.argv[1]
for v in sys.argv[2:]:
    x=load("nuplan_garage2_"+PFX+"{p}_"+v+"_*")
    k=sorted(set(b)&set(x)); d=[x[i][0]-b[i][0] for i in k]
    rng=random.Random(0); ms=sorted(sum(rng.choice(d) for _ in d)/len(d) for _ in range(5000))
    nz=sum(1 for i in k if b[i][0]>0 and x[i][0]==0); fx=sum(1 for i in k if b[i][0]==0 and x[i][0]>0)
    s=lambda D,j:int(sum(D[i][j]>0 for i in k))
    print(f"{v}: n={len(k)} diff {sum(d)/len(d):+.4f} [90% {ms[250]:+.4f}, {ms[4750]:+.4f}] W{sum(t>1e-9 for t in d)}/L{sum(t<-1e-9 for t in d)} newzero {nz} fixed {fx} | offroad {s(b,1)}->{s(x,1)} corridor {s(b,2)}->{s(x,2)} atfault {s(b,3)}->{s(x,3)}")
    for i in k:
        if (x[i][3]>0)!=(b[i][3]>0) or (x[i][0]==0)!=(b[i][0]==0): print("   ",i[:60],"base",b[i],"var",x[i])
