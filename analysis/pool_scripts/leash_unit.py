import sys, types, numpy as np
for m in ["py123d_garage","py123d_garage.evaluation","py123d_garage.evaluation.alpasim","py123d_garage.evaluation.alpasim.help"]:
    sys.modules[m]=types.ModuleType(m)
sys.modules["py123d_garage.evaluation.alpasim"].evaluate=types.ModuleType("e")
sys.modules["py123d_garage.evaluation.alpasim.help"].driver_service=types.ModuleType("d")
sys.path.insert(0,"/insomnia001/depts/edu/users/au2327/alpasim-jepa/src")
from g2_leash.entry import leashed, reference, heading_change_deg
route=np.stack([np.arange(42,78,2.0),np.zeros(18)],1)
t=np.arange(1,65)*0.1; x=10*t; y=np.linspace(0,2,64); yaw=np.zeros(64)
p=np.column_stack([x,y,yaw]); q=leashed(p,route,0.5,30)
print("max lat before/after", y.max(), q[:,1].max().round(3), "x kept", np.abs(q[:,0]-x).max().round(3))
p2=np.column_stack([x,np.full(64,0.3),yaw]); print("unchanged", leashed(p2,route) is p2)
ang=np.linspace(0,np.pi/2,18); route2=np.stack([40+20*np.sin(ang),20-20*np.cos(ang)],1)
print("turn deg", round(heading_change_deg(reference(route2),70),1), "gated", leashed(p,route2) is p)
route3=np.stack([np.arange(42,78,2.0),np.full(18,1.5)],1)
q3=leashed(np.column_stack([x,np.zeros(64),yaw]),route3,0.5,30); print("offset case y at 1s,3s,6s", q3[[9,29,63],1].round(2))
ps=np.zeros((64,3)); print("stopped max", np.abs(leashed(ps,route)).max())
