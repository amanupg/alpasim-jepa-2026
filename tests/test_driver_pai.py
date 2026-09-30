"""PAI-rig mapping (WAJEPA_RIG=pai, diagnostic): NVIDIA cameras at 10 Hz and 1916 px width are
mapped onto WA-JEPA's slots with the crop view, history frames are taken 0.5 s apart, the rear slot
is grey, and a new plan is made at most every 0.45 s (cached plan in between)."""
import io
import sys

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, __file__.rsplit("/tests/", 1)[0] + "/src")
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from alpasim_grpc.v0 import egodriver_pb2                     # noqa: E402

from test_driver_history import Ctx, FakeHandle, pose          # noqa: E402
from wajepa_challenge import driver as D                       # noqa: E402
from wajepa_challenge.preprocessing import PAI_VIEWS           # noqa: E402

PAI_CAMS = ("camera_front_wide_120fov", "camera_front_tele_30fov", "camera_cross_left_120fov",
            "camera_cross_right_120fov", "camera_rear_left_70fov", "camera_rear_right_70fov")


@pytest.fixture
def pai(monkeypatch):
    monkeypatch.setattr(D, "PAI_VIEW", PAI_VIEWS["crop"])
    monkeypatch.setattr(D, "HISTORY_STRIDE_US", 500_000)
    monkeypatch.setattr(D, "MIN_INFER_INTERVAL_US", 450_000)


def jpeg_split(left, right, step, w=1916):
    """left part = `left`, right part = `right` (split at x=0.5), plus the step number in the green channel"""
    a = np.zeros((1080, w, 3), np.uint8)
    a[:, : w // 2, 0] = left; a[:, w // 2:, 0] = right; a[:, :, 1] = step * 10
    b = io.BytesIO(); Image.fromarray(a).save(b, format="JPEG", quality=95); return b.getvalue()


def test_pai_mapping_stride_and_rate(pai):
    h = FakeHandle(); svc = D.NavsimTransfuserDriver(h); ctx = Ctx(); sid = "p1"
    spec = egodriver_pb2.DriveSessionRequest(session_uuid=sid)
    for c in PAI_CAMS:
        spec.rollout_spec.vehicle.available_cameras.add(logical_id=c)
    svc.start_session(spec, ctx)
    for k in range(0, 26):                                # 0.0 .. 2.5 s at 10 Hz
        t = k * 100_000
        tr = egodriver_pb2.RolloutEgoTrajectory(session_uuid=sid)
        tr.trajectory.poses.append(pose(t, 0.5 * k))      # 5 m/s
        tr.dynamic_states.add().linear_velocity.x = 5.0
        svc.submit_egomotion_observation(tr, ctx)
        for c in PAI_CAMS:
            img = egodriver_pb2.RolloutCameraImage(session_uuid=sid)
            img.camera_image.logical_id = c; img.camera_image.frame_end_us = t
            img.camera_image.image_bytes = jpeg_split(20, 200, k)
            svc.submit_image_observation(img, ctx)
        if k in (20, 21, 22, 25):
            svc.drive(egodriver_pb2.DriveRequest(session_uuid=sid, time_now_us=t, time_query_us=t), ctx)
    # inferences at 2.0 s and 2.5 s only (2.1 and 2.2 use the cached plan)
    assert len(h.w.seen) == 2
    c = svc._sessions[sid].counters
    assert (c.model_inference, c.cached_plan, c.straight_fallback) == (2, 2, 0)
    inp = h.w.seen[0]
    # history frames 0.5 s apart: steps 5, 10, 15, 20 (green channel = 10 * step)
    steps = [round(f["CAM_F0"][..., 1].mean() / 10) for f in inp.history]
    assert steps == [5, 10, 15, 20]
    np.testing.assert_allclose(inp.history_trajectory[:, 0], [-7.5, -5.0, -2.5, 0.0], atol=1e-5)
    last = inp.history[-1]
    # crops: L0 = right part of cross-left (red 200), R0 = left part of cross-right (mostly red 20)
    assert last["CAM_L0"][..., 0].mean() > 170
    assert last["CAM_R0"][..., 0].mean() < 40
    # F0 = centre crop straddling the split: both halves present
    assert 60 < last["CAM_F0"][..., 0].mean() < 160
    assert (last["CAM_B0"] == 128).all()
    assert all(f[s].shape == (256, 512, 3) for f in inp.history for s in f)
