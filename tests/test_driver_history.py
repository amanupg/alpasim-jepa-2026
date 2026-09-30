"""Driver-level test of the WA-JEPA adapter with simulated gRPC traffic and a fake policy:
4 cameras at 2 Hz, ego driving +x at 5 m/s with a left turn ahead on the route. Checks the
exact tensors the policy would receive (history order, relative poses, command, speed) and
that Drive returns a trajectory from the fresh plan."""
import io
import math
import sys

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, __file__.rsplit("/tests/", 1)[0] + "/src")
from alpasim_grpc.v0 import common_pb2, egodriver_pb2          # noqa: E402

from wajepa_challenge import driver as D                        # noqa: E402
from wajepa_challenge.policy import Prediction                  # noqa: E402
from wajepa_challenge.preprocessing import CAMERA_IDS           # noqa: E402


class Ctx:
    def abort(self, code, msg):
        raise RuntimeError(f"abort {code}: {msg}")

    def time_remaining(self):
        return 10.0


class FakeWorker:
    def __init__(self):
        self.seen = []

    def predict(self, inp, timeout=None):
        self.seen.append(inp)
        traj = np.stack([np.arange(1, 9) * 2.5, np.zeros(8), np.zeros(8)], 1)   # straight 5 m/s
        return Prediction(trajectory=traj)


class FakeHandle:
    def __init__(self):
        self.w = FakeWorker()

    def start(self): pass
    def wait_ready(self, timeout): return True
    def load_error(self): return None
    def worker(self): return self.w
    def stop(self): pass


def jpeg(value):
    b = io.BytesIO()
    Image.fromarray(np.full((1080, 1920, 3), value, np.uint8)).save(b, format="JPEG")
    return b.getvalue()


def pose(t_us, x):
    return common_pb2.PoseAtTime(timestamp_us=t_us, pose=common_pb2.Pose(
        vec=common_pb2.Vec3(x=x, y=0.0, z=0.0), quat=common_pb2.Quat(w=1.0)))


def test_history_and_drive():
    h = FakeHandle(); svc = D.NavsimTransfuserDriver(h); ctx = Ctx(); sid = "s1"
    spec = egodriver_pb2.DriveSessionRequest(session_uuid=sid)
    for c in CAMERA_IDS + ("CAM_L1",):
        spec.rollout_spec.vehicle.available_cameras.add(logical_id=c)
    svc.start_session(spec, ctx)
    # route: turn left 50 m ahead (rig frame), as the runtime sends it (starting ~40 m ahead)
    route = egodriver_pb2.RouteRequest(session_uuid=sid)
    route.route.waypoints.extend([common_pb2.Vec3(x=40 + 2 * i, y=0.0 if i < 5 else 3.0 * (i - 4)) for i in range(10)])
    svc.submit_route(route, ctx)
    times = [0, 500_000, 1_000_000, 1_500_000]
    for k, t in enumerate(times):
        tr = egodriver_pb2.RolloutEgoTrajectory(session_uuid=sid)
        tr.trajectory.poses.append(pose(t, 2.5 * k))
        ds = tr.dynamic_states.add(); ds.linear_velocity.x = 5.0
        svc.submit_egomotion_observation(tr, ctx)
        for j, c in enumerate(CAMERA_IDS):
            img = egodriver_pb2.RolloutCameraImage(session_uuid=sid)
            img.camera_image.logical_id = c; img.camera_image.frame_end_us = t
            img.camera_image.image_bytes = jpeg(10 * k + j)
            svc.submit_image_observation(img, ctx)
    resp = svc.drive(egodriver_pb2.DriveRequest(session_uuid=sid, time_now_us=1_500_000,
                                               time_query_us=1_500_000), ctx)
    assert len(h.w.seen) == 1
    inp = h.w.seen[0]
    # history oldest first, one frame per 0.5 s step, per-camera pixel values encode (step, camera)
    for k, frame in enumerate(inp.history):
        for j, c in enumerate(CAMERA_IDS):
            assert frame[c].shape == (256, 512, 3)
            assert abs(int(frame[c].mean()) - (10 * k + j)) <= 2
    np.testing.assert_allclose(inp.history_trajectory[:, 0], [-7.5, -5.0, -2.5, 0.0], atol=1e-5)
    np.testing.assert_allclose(inp.history_trajectory[:, 1:], 0.0, atol=1e-5)
    np.testing.assert_allclose(inp.ego_status[4:], [5.0, 0.0, 0.0, 0.0], atol=1e-5)
    assert inp.ego_status[:4].tolist() in ([1, 0, 0, 0], [0, 1, 0, 0])     # LEFT (or STRAIGHT) per organisers' rule
    assert len(resp.trajectory.poses) > 2
    assert resp.trajectory.poses[-1].pose.vec.x > 7.5


def test_padding_early_in_rollout():
    h = FakeHandle(); svc = D.NavsimTransfuserDriver(h); ctx = Ctx(); sid = "s2"
    spec = egodriver_pb2.DriveSessionRequest(session_uuid=sid)
    for c in CAMERA_IDS:
        spec.rollout_spec.vehicle.available_cameras.add(logical_id=c)
    svc.start_session(spec, ctx)
    tr = egodriver_pb2.RolloutEgoTrajectory(session_uuid=sid); tr.trajectory.poses.append(pose(0, 0.0))
    svc.submit_egomotion_observation(tr, ctx)
    for c in CAMERA_IDS:
        img = egodriver_pb2.RolloutCameraImage(session_uuid=sid)
        img.camera_image.logical_id = c; img.camera_image.frame_end_us = 0; img.camera_image.image_bytes = jpeg(50)
        svc.submit_image_observation(img, ctx)
    svc.drive(egodriver_pb2.DriveRequest(session_uuid=sid, time_now_us=0, time_query_us=0), ctx)
    assert len(h.w.seen) == 1 and len(h.w.seen[0].history) == 4
    assert svc._sessions[sid].counters.history_pad == 1
