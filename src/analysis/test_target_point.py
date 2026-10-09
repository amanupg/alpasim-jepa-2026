"""Check wajepa_challenge.route_bridge.target_point_py123d against py123d_garage's own route code (v0.1.1)."""
import numpy as np
from py123d_garage.evaluation.alpasim.help.driver_service import _extend_route, _resample_route
from wajepa_challenge import route_bridge as rb      # run with PYTHONPATH=src


def ref(w, d=45.0):
    r = w[~np.isnan(w).any(axis=1)]
    if np.linalg.norm(r[0]) > 0.1:
        r = np.vstack([np.zeros((1, 2)), r])
    r = _extend_route(r, d + 2.0)
    m = _resample_route(r, 0.1, 0.0)
    return np.array([m.polyline_x[450], m.polyline_y[450]])


rng = np.random.default_rng(0)
cases = [np.array([[40., 0], [60, 0]]), np.array([[40., 0], [40, 10], [30, 30]]), np.array([[10., 0]]),
         np.array([[38., 2], [45, 6], [50, 15], [52, 30]]), np.array([[0.05, 0], [20, 0], [20, 30]])]
for _ in range(200):
    k = rng.integers(1, 8)
    cases.append(np.cumsum(rng.normal([8, 0], [4, 4], (k, 2)), 0) + [rng.uniform(0, 45), rng.normal(0, 3)])
err = max(float(np.abs(rb.target_point_py123d(c) - ref(c)).max()) for c in cases)
print("cases", len(cases), "max |ours - py123d| =", round(err, 4), "m (py123d resamples at 0.1 m)")
print("example", rb.target_point_py123d(cases[1]), ref(cases[1]))
