"""Route-consistent choice among K trajectory samples (numpy only, so it unit-tests without torch).

nuPlan bench (2026-09-29): 15 of the 24 lost scene points were the car taking the wrong branch at a
junction (straight where the route turns, or the reverse), ending as corridor exits or offroad.
The runtime sends route waypoints about 40-80 m ahead in the rig frame; the plan is 6.4 s long.
Sample 0 is exactly the K=1 plan (same seed), so it is kept unless another sample follows the route
by a clear margin: normal scenes drive as before, only a branch choice can change.
"""
import numpy as np


def _dist_to_polyline(p: np.ndarray, poly: np.ndarray) -> np.ndarray:
    """Distance from each point p (N, 2) to the polyline poly (M, 2)."""
    a, b = poly[:-1], poly[1:]
    ab = b - a
    t = np.einsum("nmk,mk->nm", p[:, None] - a[None], ab) / np.maximum((ab * ab).sum(1), 1e-9)
    q = a[None] + np.clip(t, 0, 1)[..., None] * ab[None]
    return np.linalg.norm(p[:, None] - q, axis=2).min(1)


def route_costs(xy: np.ndarray, route: np.ndarray, min_dist_m: float = 8.0) -> np.ndarray:
    """Mean distance of each sample's points beyond min_dist_m from the car to the polyline
    [car, route...]. xy: (K, T, 2) samples in the rig frame. Zero for samples that stay within
    min_dist_m (too short to tell a branch)."""
    route = np.asarray(route, dtype=np.float64).reshape(-1, 2)
    route = route[route[:, 0] > -2.0]
    if len(route) == 0:
        return np.zeros(len(xy))
    poly = np.vstack([np.zeros((1, 2)), route])
    out = np.zeros(len(xy))
    for k, s in enumerate(np.asarray(xy, dtype=np.float64)):
        far = s[np.linalg.norm(s, axis=1) > min_dist_m]
        if len(far):
            out[k] = _dist_to_polyline(far, poly).mean()
    return out


def path_lengths(xy: np.ndarray) -> np.ndarray:
    """Length of each sample's path from the car (origin) through its points, in metres."""
    xy = np.asarray(xy, dtype=np.float64)
    pts = np.concatenate([np.zeros((len(xy), 1, 2)), xy], 1)
    return np.linalg.norm(np.diff(pts, axis=1), axis=2).sum(1)


def choose(xy: np.ndarray, route: np.ndarray | None, margin_m: float = 2.0, min_len_ratio: float = 0.0,
           big_gap_m: float = 0.0, big_gap_min_len: float = 0.0) -> int:
    """Index of the sample to drive: 0 unless another is closer to the route by more than margin_m.
    min_len_ratio > 0 is a speed guard: only samples whose path is at least that fraction of sample 0's
    are eligible (PAI 2026-10-01: frequent switching to slower samples turned 4 passes into low progress).
    big_gap_m > 0 grades the guard: a sample closer to the route than sample 0 by more than big_gap_m (a lane
    change) only needs big_gap_min_len of sample 0's length (PAI v2: the guard blocked such samples in
    corridor-exit scenes that ended 4.0-4.2 m off)."""
    if route is None or len(xy) < 2:
        return 0
    c = route_costs(xy, route)
    if min_len_ratio > 0:
        L = path_lengths(xy)
        ok = L >= min_len_ratio * L[0]
        if big_gap_m > 0:
            ok |= (c[0] - c > big_gap_m) & (L >= big_gap_min_len * L[0])
        c = np.where(ok, c, np.inf)
        c[0] = route_costs(xy[:1], route)[0]
    j = int(c.argmin())
    return j if c[0] - c[j] > margin_m else 0


def route_pull(xy: np.ndarray, yaw: np.ndarray, route: np.ndarray | None, w_max: float,
               d0_m: float = 30.0, d1_m: float = 45.0) -> tuple[np.ndarray, np.ndarray]:
    """Blend the far part of a plan toward the route (the recorded path 40-80 m ahead).

    PAI bench (2026-10-03): the remaining corridor exits end 4.0-4.2 m from the recorded path, mostly
    where the recorded driver changed lane and ours did not. A point at distance d from the car moves a
    fraction w(d) of the way to its nearest point ON the route waypoints (never onto the car-to-route
    chord, which cuts corners), with w rising linearly from 0 at d0_m to w_max at d1_m. Near points are
    untouched, so the next few seconds still follow the model; headings are recomputed where points moved.
    xy: (T, 2) plan in the rig frame; yaw: (T,). Returns new (xy, yaw)."""
    if route is None or w_max <= 0 or len(xy) < 2:
        return xy, yaw
    r = np.asarray(route, dtype=np.float64).reshape(-1, 2)
    r = r[np.isfinite(r).all(1) & (r[:, 0] > -2.0)]
    if len(r) < 2:
        return xy, yaw
    p = np.asarray(xy, dtype=np.float64)
    d = np.linalg.norm(p, axis=1)
    w = np.clip((d - d0_m) / max(d1_m - d0_m, 1e-6), 0.0, 1.0) * w_max
    if not (w > 0).any():
        return xy, yaw
    a, b = r[:-1], r[1:]
    ab = b - a
    t = np.einsum("nmk,mk->nm", p[:, None] - a[None], ab) / np.maximum((ab * ab).sum(1), 1e-9)
    q = a[None] + np.clip(t, 0, 1)[..., None] * ab[None]
    near = q[np.arange(len(p)), np.linalg.norm(p[:, None] - q, axis=2).argmin(1)]
    out = p + w[:, None] * (near - p)
    new_yaw = np.asarray(yaw, dtype=np.float64).copy()
    moved = np.nonzero(w > 0)[0]
    if len(moved):
        seg = np.diff(out, axis=0)
        hd = np.arctan2(seg[:, 1], seg[:, 0])
        for i in moved:
            if np.linalg.norm(seg[min(i, len(seg) - 1)]) > 0.05:
                new_yaw[i] = hd[min(i, len(seg) - 1)]
    return out.astype(np.asarray(xy).dtype), new_yaw.astype(np.asarray(yaw).dtype)


def retime_path(path_xy: np.ndarray, speed_xy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Drive path_xy's geometry with speed_xy's progress over time.

    Point k of the result lies on path_xy at the arc length speed_xy has covered by step k (both plans
    share the 0.1 s step and start at the car). Beyond the end of path_xy the last segment's direction is
    extended. Headings follow the path tangent. Used to take the route from the 4-camera plan and the
    speed from the 6-camera plan, whose rear cameras see a vehicle closing from behind (PAI 2026-10-08:
    6 cameras cut rear-end hits 9 to 3 on scenes 1-40 but added own collisions and corridor exits)."""
    p = np.vstack([np.zeros((1, 2)), np.asarray(path_xy, dtype=np.float64)])
    q = np.vstack([np.zeros((1, 2)), np.asarray(speed_xy, dtype=np.float64)])
    seg = np.diff(p, axis=0); L = np.linalg.norm(seg, axis=1); S = np.concatenate([[0.0], np.cumsum(L)])
    s_target = np.cumsum(np.linalg.norm(np.diff(q, axis=0), axis=1))          # (T,) progress per step
    out = np.empty((len(s_target), 2))
    last_dir = seg[-1] / max(L[-1], 1e-9) if len(L) else np.array([1.0, 0.0])
    for k, s in enumerate(s_target):
        if s >= S[-1]:
            out[k] = p[-1] + (s - S[-1]) * last_dir
        else:
            i = int(np.searchsorted(S, s, side="right") - 1)
            a = (s - S[i]) / max(L[i], 1e-9)
            out[k] = p[i] + a * seg[i]
    d = np.diff(np.vstack([np.zeros((1, 2)), out]), axis=0)
    yaw = np.arctan2(d[:, 1], d[:, 0])
    still = np.linalg.norm(d, axis=1) < 1e-3                                  # stopped: hold the path heading
    if still.any():
        path_yaw = np.arctan2(seg[0, 1], seg[0, 0]) if len(seg) else 0.0
        yaw[still] = path_yaw
    return out, yaw


def _route_points(route: np.ndarray | None) -> np.ndarray | None:
    if route is None:
        return None
    r = np.asarray(route, dtype=np.float64).reshape(-1, 2)
    r = r[np.isfinite(r).all(1) & (r[:, 0] > 0.0)]
    return r if len(r) >= 2 else None


def route_deviation(xy: np.ndarray, route: np.ndarray | None) -> float | None:
    """Mean distance from the route waypoints the plan reaches (within its path length) to the plan.

    Measured from the route side, so a plan that runs past the route's end is not penalised (the
    chooser's route_costs grows with plan length at highway speed). None if no waypoint is in reach."""
    r = _route_points(route)
    if r is None or len(xy) < 2:
        return None
    poly = np.vstack([np.zeros((1, 2)), np.asarray(xy, dtype=np.float64)])
    reach = np.linalg.norm(np.diff(poly, axis=0), axis=1).sum()
    r = r[np.linalg.norm(r, axis=1) <= reach]
    if len(r) == 0:
        return None
    return float(_dist_to_polyline(r, poly).mean())


def route_path(route: np.ndarray | None, step_m: float = 1.0) -> np.ndarray | None:
    """A drivable path from the car onto the route: a cubic Hermite curve from the car (heading +x) to the
    first waypoint, arriving along the route's direction, then the route waypoints. Excludes the origin.

    PAI v2 rerun (2026-10-09): in 11 of 14 corridor exits every one of the 6 samples stayed 3-12 m off the
    route (the recorded driver changed lane or took an exit; ours kept its lane), so no choice among samples
    can fix them. route_pull bent only points 30 m+ ahead and the car replans every second, so the bend
    never came closer; this path starts bending at the car."""
    r = _route_points(route)
    if r is None:
        return None
    p1 = r[0]
    d = np.linalg.norm(p1)
    t1 = (r[1] - r[0]) / max(np.linalg.norm(r[1] - r[0]), 1e-9)
    n = max(int(np.ceil(d / step_m)), 2)
    s = np.linspace(0.0, 1.0, n + 1)[1:, None]
    h00, h10, h01, h11 = 2 * s**3 - 3 * s**2 + 1, s**3 - 2 * s**2 + s, -2 * s**3 + 3 * s**2, s**3 - s**2
    curve = h10 * np.array([d, 0.0]) + h01 * p1 + h11 * (t1 * d)              # h00 * origin = 0
    return np.vstack([curve, r[1:]])


def route_parallel(route: np.ndarray | None, max_deg: float) -> bool:
    """True if the route runs nearly parallel to the car: both the direction from the car to the first
    waypoint and the route's direction there are within max_deg of the car's heading.

    PAI route snap v1 (2026-10-10): snaps that fixed corridor exits were lane changes and exits on straight
    roads (route heading at the first waypoint within +-7 deg); the snaps that broke passing scenes were
    turns and U-turns (60-180 deg), where the curve from the car to a waypoint ~40 m ahead cuts the corner."""
    r = _route_points(route)
    if r is None:
        return False
    chord = np.degrees(np.arctan2(r[0, 1], r[0, 0]))
    d = r[1] - r[0]
    hd = np.degrees(np.arctan2(d[1], d[0]))
    return bool(abs(chord) <= max_deg and abs(hd) <= max_deg)


def route_lateral_offset(route: np.ndarray | None) -> float:
    """Sideways distance (m) of the route's first waypoint from the car's heading line; 0 without a route."""
    r = _route_points(route)
    return 0.0 if r is None else float(abs(r[0, 1]))


class RouteMemory:
    """The recorded path the route has shown so far, kept in the world frame.

    The runtime sends route waypoints ~40-80 m ahead in the rig frame, so the stretch between the car and the
    first waypoint (where a turn or a lane change happens) is missing from any single route, and route_path
    has to bridge it with a curve that cuts corners (PAI 2026-10-10: snapping on turns went offroad, hence the
    15 deg guard). That stretch was in the routes received a few seconds earlier, so remembering them in
    world coordinates gives the whole path from the car onwards. Route data only, nothing else.
    """

    def __init__(self, max_points: int = 600, merge_m: float = 3.0):
        self.pts = np.zeros((0, 2))
        self.max_points, self.merge_m = max_points, merge_m
        self.last_merge: float | None = None

    def add(self, route_rig_xy: np.ndarray, pos: np.ndarray, R: np.ndarray) -> None:
        """route_rig_xy: (N, 2) waypoints in the rig frame of the pose (pos (3,), R (3, 3) rig-to-world)."""
        r = np.asarray(route_rig_xy, dtype=np.float64).reshape(-1, 2)
        r = r[np.isfinite(r).all(1)]
        if len(r) == 0:
            return
        w = (np.c_[r, np.zeros(len(r))] @ np.asarray(R).T + np.asarray(pos))[:, :2]
        self.last_merge = None
        if len(self.pts):
            d = np.linalg.norm(self.pts - w[0], axis=1)
            i = int(d.argmin())
            self.last_merge = float(d[i])                                   # registration check (debug log)
            # the new route starts on the remembered path: keep the path up to there (including the nearest
            # point if it lies behind the new start), take the fresher tail
            if d[i] <= self.merge_m:
                back = len(w) > 1 and float(np.dot(self.pts[i] - w[0], w[1] - w[0])) < -0.1
                self.pts = np.vstack([self.pts[:i + 1 if back else i], w])
            else:
                # the new route does not continue the remembered one (PAI 2026-10-19: only after the car had left
                # the route, merge 4-12 m; appending made the path double back): start over from this route
                self.pts = w
        else:
            self.pts = w
        self.pts = self.pts[-self.max_points:]

    def path_in_frame(self, pos0: np.ndarray, R0: np.ndarray, join_m: float = 25.0,
                      min_len_m: float = 20.0, near_m: float = 8.0) -> np.ndarray | None:
        """The remembered path ahead of the car, in the rig frame of (pos0, R0), excluding the origin.

        Starts at the path point nearest the car. If the car is beside the path (another lane), the offset is
        blended out over join_m metres (smoothstep), so the result leaves the car along a smooth lane change
        instead of jumping sideways. None if less than min_len_m of path lies ahead, or if the remembered path
        does not reach the car (nearest point farther than near_m, e.g. at session start), so the caller falls
        back to route_path."""
        if len(self.pts) < 2:
            return None
        p = np.c_[self.pts - np.asarray(pos0)[:2], np.zeros(len(self.pts))] @ np.asarray(R0)   # world -> rig
        p = p[:, :2]
        dist = np.linalg.norm(p, axis=1)
        i0 = int(dist.argmin())
        if dist[i0] > near_m:
            return None
        ahead = p[i0:]
        if len(ahead) < 2:
            return None
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(ahead, axis=0), axis=1))])
        if s[-1] < min_len_m:
            return None
        u = np.clip(s / max(join_m, 1e-6), 0.0, 1.0)
        w = 1.0 - (3 * u**2 - 2 * u**3)                                    # 1 at the car, 0 after join_m
        out = ahead + w[:, None] * (-ahead[0])[None]                       # shift toward the car near the start
        keep = np.r_[np.linalg.norm(out[0]) > 0.5, np.ones(len(out) - 1, bool)]   # drop a point at the car itself
        return out[keep]


def cap_speed_on_path(path_xy: np.ndarray, speed_xy: np.ndarray, a_lat: float = 3.0, dt: float = 0.1,
                      brake: float = 3.0, v_floor: float = 2.0, smooth_m: float = 4.0) -> np.ndarray:
    """A progress profile for driving path_xy: the model's speed (from speed_xy, 0.1 s steps from the car) capped so
    the lateral acceleration on the path stays below a_lat (v <= sqrt(a_lat / curvature)). The cap is propagated
    backwards at a comfortable deceleration `brake` (v(s) <= sqrt(vmax(s')^2 + 2 brake (s' - s)) for every s' ahead),
    so the car slows gradually before a curve instead of braking hard at the start of the plan. Returns a straight
    polyline whose arc lengths are that progress, i.e. a speed_xy for retime_path.

    PAI memory snap (2026-10-20): following the remembered path through turns fixed missed turns (622908, 3defec)
    but sent others offroad or into collisions (1845f6, ec6f99, 36ea68, 57016f), plausibly because the recorded
    curve was driven at the model's speed for its own (straighter) plan."""
    p = np.vstack([np.zeros((1, 2)), np.asarray(path_xy, dtype=np.float64)])
    seg = np.diff(p, axis=0); L = np.linalg.norm(seg, axis=1)
    keep = L > 1e-6
    seg, L = seg[keep], L[keep]
    S = np.concatenate([[0.0], np.cumsum(L)])
    q = np.vstack([np.zeros((1, 2)), np.asarray(speed_xy, dtype=np.float64)])
    v_model = np.linalg.norm(np.diff(q, axis=0), axis=1) / dt                     # (T,)
    if len(L) < 2:
        return np.asarray(speed_xy, dtype=np.float64)
    hd = np.unwrap(np.arctan2(seg[:, 1], seg[:, 0]))
    mid = (S[:-1] + S[1:]) / 2
    # curvature = d(heading)/ds over a smoothing window of smooth_m metres
    kap = np.empty(len(mid))
    for i, m in enumerate(mid):
        j0 = int(np.searchsorted(mid, m - smooth_m / 2)); j1 = int(np.searchsorted(mid, m + smooth_m / 2)) - 1
        j0, j1 = max(0, min(j0, i)), min(len(mid) - 1, max(j1, i))
        kap[i] = abs(hd[j1] - hd[j0]) / max(mid[j1] - mid[j0], 1e-6) if j1 > j0 else 0.0
    vmax = np.maximum(np.sqrt(a_lat / np.maximum(kap, 1e-6)), v_floor)
    s, out = 0.0, np.empty(len(v_model))
    for k, vk in enumerate(v_model):
        ahead = mid >= s - 0.5
        cap = float(np.min(np.sqrt(vmax[ahead] ** 2 + 2 * brake * np.maximum(mid[ahead] - s, 0.0)))) if ahead.any() \
            else float(vmax[-1])
        s += min(vk, cap) * dt
        out[k] = s
    return np.stack([out, np.zeros_like(out)], 1)


def choose_fast(xy: np.ndarray, shape_tol_m: float = 1.0, min_gain: float = 1.02) -> int:
    """Index of the sample to drive: among samples whose PATH SHAPE agrees with the medoid's (mean distance of
    their points to the medoid's polyline <= shape_tol_m, so speed differences don't count), the one that covers
    the most distance; sample 0 (the K=1 plan) unless that one is at least min_gain times longer.

    PAI 2026-10-21: most low-progress scenes are rear-ends by replayed traffic (we drive slower than the recorded
    car). Scaling every plan up was a disaster (-0.307: it ignores what the model sees); this only takes extra
    speed the model itself proposed in a plausible plan for the same path."""
    xy = np.asarray(xy, dtype=np.float64)
    K = len(xy)
    if K < 2:
        return 0
    flat = xy.reshape(K, -1)
    m = int(np.linalg.norm(flat[:, None] - flat[None], axis=2).sum(1).argmin())
    poly = np.vstack([np.zeros((1, 2)), xy[m]])
    L = path_lengths(xy)
    # shape agreement over the stretch both plans cover (a faster plan runs past the medoid's end on the same road)
    shape = np.empty(K)
    for k, s in enumerate(xy):
        cum = np.cumsum(np.linalg.norm(np.diff(np.vstack([np.zeros((1, 2)), s]), axis=0), axis=1))
        pts = s[cum <= L[m]]
        shape[k] = _dist_to_polyline(pts, poly).mean() if len(pts) else 0.0
    ok = shape <= shape_tol_m
    if not ok.any():
        return 0
    j = int(np.where(ok, L, -np.inf).argmax())
    return j if L[j] >= min_gain * L[0] else 0


def warped_source_times(times_s: np.ndarray, scale: float, horizon_s: float = 4.0) -> np.ndarray:
    """The organisers' trajectory time warp, from their GTRS sample (NVlabs/alpasim e2e_challenge,
    navsim_gtrs_dense_challenge/trajectory.py::_warped_source_times, Apache-2.0, Copyright (c) 2026 NVIDIA),
    as ported by the alpasim-jepa thread (wajepa_challenge/timewarp.py). The plan is read ahead of time in the
    near term (t <= 1 s: scale * t; 1-3 s: t + (scale - 1); 3-4 s: the lead tapers to 0 at 4 s), so the controller
    is asked to keep up with the plan. Beyond horizon_s (our plans run 6.4 s) times are unchanged."""
    if not 1.0 <= scale <= 1.25:
        raise ValueError("time scale must be in [1.0, 1.25]")
    t = np.asarray(times_s, dtype=np.float64)
    if scale == 1.0:
        return t
    lead = scale - 1.0
    src = np.where(t <= 1.0, scale * t, np.where(t <= 3.0, t + lead,
                   np.where(t <= horizon_s, t + lead * (horizon_s - t), t)))
    return src


def heading_change_deg(xy: np.ndarray, upto_s: float = 4.0, dt: float = 0.1) -> float:
    """Largest heading change along the plan's first upto_s seconds (degrees), ignoring near-standstill steps."""
    p = np.asarray(xy, dtype=np.float64)[: int(round(upto_s / dt))]
    d = np.diff(np.vstack([np.zeros((1, 2)), p]), axis=0)
    moving = np.linalg.norm(d, axis=1) > 0.02
    if moving.sum() < 2:
        return 0.0
    h = np.unwrap(np.arctan2(d[moving, 1], d[moving, 0]))
    return float(np.degrees(np.abs(h - h[0]).max()))


def time_warp_plan(xy: np.ndarray, yaw: np.ndarray, scale: float, dt: float = 0.1) -> tuple[np.ndarray, np.ndarray]:
    """Read a (T, 2) plan at 0.1 s (+ yaw) at the warped times (origin at t = 0)."""
    xy = np.asarray(xy, dtype=np.float64); yaw = np.asarray(yaw, dtype=np.float64)
    T = len(xy)
    times = np.arange(0, T + 1) * dt
    src_xy = np.vstack([np.zeros((1, 2)), xy]); src_yaw = np.unwrap(np.concatenate([[0.0], yaw]))
    st = np.clip(warped_source_times(times[1:], scale), 0.0, times[-1])
    out_xy = np.stack([np.interp(st, times, src_xy[:, k]) for k in range(2)], 1)
    return out_xy, np.interp(st, times, src_yaw)


def stall_rescue_choice(xy: np.ndarray, stall_m: float = 3.0, min_move_m: float = 3.0, at_s: float = 4.0,
                        min_frac: float = 0.5, dt: float = 0.1) -> int:
    """Index of the sample to drive when sample 0 stalls (moves < stall_m within at_s): the medoid of the samples
    that move >= min_move_m, if at least min_frac of all samples do (the model's own majority says go);
    otherwise 0. Model-sample analogue of the alpasim-jepa thread's GTRS stall rescue (their judge's
    collision-free / drivable-area probabilities are replaced by the sample majority)."""
    xy = np.asarray(xy, dtype=np.float64)
    k = min(int(round(at_s / dt)), xy.shape[1]) - 1
    disp = np.linalg.norm(xy[:, k], axis=1)
    if disp[0] >= stall_m:
        return 0
    mov = np.nonzero(disp >= min_move_m)[0]
    if len(mov) < max(1, int(np.ceil(min_frac * len(xy)))):
        return 0
    flat = xy[mov].reshape(len(mov), -1)
    return int(mov[np.linalg.norm(flat[:, None] - flat[None], axis=2).sum(1).argmin()])
