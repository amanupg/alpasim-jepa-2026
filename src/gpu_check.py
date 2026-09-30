"""GPU memory and latency of the WA-JEPA policy (4 cameras x 4 frames), as the AlpaSim driver runs it.
Reports nvidia-smi memory for THIS process (what a 16 GiB per-replica cap counts) and per-plan latency
for batch 1 and batch 2 (two concurrent rollouts per replica)."""
import os, subprocess, sys, time
import numpy as np, torch
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from wajepa_challenge.policy import WaJepaPolicy, InferenceInput
from wajepa_challenge.preprocessing import CAMERA_IDS, relative_se2

B = "/insomnia001/depts/edu/users/au2327/alpasim-jepa"
R = f"{B}/ext/WA-JEPA"


def smi():
    out = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout
    return max([int(l.split(",")[1]) for l in out.strip().splitlines() if l.split(",")[0].strip() == str(os.getpid())] or [0])


p = WaJepaPolicy(R, f"{R}/configs/wa_jepa_navsim_epdms.yaml", f"{B}/weights/wa-jepa/model_state_dict.pt", device="cuda")
rng = np.random.default_rng(0)
poses = np.array([[0, 0, 0], [2.5, 0, 0], [5, 0, 0], [7.5, 0, 0]], float)
def req():
    return InferenceInput(history=[{c: rng.integers(0, 255, (256, 512, 3), dtype=np.uint8) for c in CAMERA_IDS} for _ in range(4)],
                          history_trajectory=relative_se2(poses), ego_status=np.array([0, 1, 0, 0, 5, 0, 0, 0], np.float32))
for bs in (1, 2):
    lat = []
    for i in range(12):
        rs = [req() for _ in range(bs)]
        torch.cuda.synchronize(); t = time.time(); out = p.predict_batch(rs); torch.cuda.synchronize(); lat.append(time.time() - t)
    print(f"batch {bs}: latency mean {np.mean(lat[2:]):.3f}s p90 {np.percentile(lat[2:], 90):.3f}s", flush=True)
print(f"{torch.cuda.get_device_name()}: nvidia-smi {smi()} MiB, peak reserved {torch.cuda.max_memory_reserved()/2**30:.2f} GiB")
print("sample plan (x, y, yaw):", np.round(out[0].trajectory, 2).tolist())
