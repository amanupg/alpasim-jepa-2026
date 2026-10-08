"""Smoke test: build a few samples from the fetched logs and print their contents."""
import sys, time
import numpy as np
from wajepa_route.samples import list_scenes, build_sample, SKIP_REASONS

root, split, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
t = time.time(); scenes = list_scenes(root, split, 2.0, log_names=(sys.argv[5].split(",") if len(sys.argv) > 5 else None)); print(f"{len(scenes)} scenes in {split} ({time.time()-t:.1f} s)")
ok = 0; t = time.time()
for sc in scenes[:: max(1, len(scenes) // n)][:n]:
    s = build_sample(sc)
    if s is None:
        print("skip", sc.log_name); continue
    ok += 1
    print(s.log_name, s.timestamp_us, "img", s.images.shape, s.images.dtype, "mean %.1f" % s.images.mean(),
          "| hist", np.round(s.history_trajectory[:, :2], 2).tolist(), "| fut_end", np.round(s.future_trajectory[-1], 2).tolist(),
          "| ego", np.round(s.ego_status, 2).tolist(), "| tp", np.round(s.target_point, 1).tolist())
print("skip reasons", SKIP_REASONS); print(f"{ok}/{n} built, {(time.time()-t)/max(ok,1):.2f} s per sample")
if ok:
    import cv2
    cv2.imwrite(sys.argv[4], cv2.cvtColor(np.concatenate([np.concatenate(list(s.images[3]), 1), np.concatenate(list(s.images[11]), 1)], 0), cv2.COLOR_RGB2BGR))
