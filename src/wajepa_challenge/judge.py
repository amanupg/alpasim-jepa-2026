"""GTRS-Dense as a judge for WA-JEPA's plan (WAJEPA_JUDGE=gtrs).

GTRS-Dense (the organisers' SimScale sample, vendored in ./gtrs) scores a fixed vocabulary of 16,384
candidate paths (40 poses at 0.1 s) with learned PDM-style heads: no at-fault collision (NC), drivable
area compliance (DAC), ego progress (EP), and more. Its trajectory head embeds each candidate with an
MLP, so any path can be scored. Here WA-JEPA's plan is appended to the vocabulary as one more
candidate, in one pass:
  s = log sigmoid(NC) + log sigmoid(DAC) + 3 log sigmoid(EP)   (the sample's NC*DAC*EP^3 scorer)
GTRS's own pick is taken over the vocabulary with the sample's settings (speed enhancement on:
top-64 speed reranking, weight 3). WA-JEPA's plan is kept unless s(GTRS pick) - s(WA-JEPA) > margin.
margin = inf only logs the scores (pure WA-JEPA driving).
"""
from __future__ import annotations

import logging
import math

import numpy as np
import torch

from .gtrs.config import GTRSDenseConfig
from .gtrs.io_utils import build_status_feature, load_navhard_vocabulary, normalized_checkpoint, preprocess_images
from .gtrs.model import NC_DAC_EP_SCORER, GTRSDenseModel, _speed_reranked_scores, _trajectory_scores

LOGGER = logging.getLogger(__name__)
JUDGE_CAMERAS = ("CAM_L0", "CAM_F0", "CAM_R0")
EP_EXPONENT, SPEED_TOP_K, SPEED_WEIGHT = 3.0, 64, 3.0       # the sample's GTRS_SPEED_ENHANCEMENT=1 defaults


def plan_to_vocab_poses(plan: np.ndarray) -> np.ndarray:
    """WA-JEPA [8, 3] at t = 0.5..4.0 s -> GTRS [40, 3] at t = 0.1..4.0 s (linear, from the origin)."""
    plan = np.asarray(plan, np.float64)
    t_src = np.arange(0, 9) * 0.5
    src = np.vstack([np.zeros(3), plan])
    src[:, 2] = np.unwrap(src[:, 2])
    t_dst = np.arange(1, 41) * 0.1
    return np.stack([np.interp(t_dst, t_src, src[:, k]) for k in range(3)], 1).astype(np.float32)


def vocab_poses_to_plan(poses: np.ndarray) -> np.ndarray:
    """GTRS [40, 3] at 0.1 s -> [8, 3] at 0.5 s (exact samples at 0.5, 1.0, ..., 4.0 s)."""
    return np.asarray(poses, np.float64)[4::5].copy()


class GtrsJudge:
    def __init__(self, checkpoint_path: str, vocabulary_path: str, device: str = "cuda", margin: float = 0.0) -> None:
        self.device = torch.device(device)
        self.margin = float(margin)
        vocabulary = load_navhard_vocabulary(vocabulary_path)
        payload = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        state_dict = normalized_checkpoint(payload, vocabulary)
        config = GTRSDenseConfig(vocab_size=int(vocabulary.shape[0]), backbone_type="resnet")
        model = GTRSDenseModel(config, vocab=vocabulary, scorer_mode=NC_DAC_EP_SCORER, ep_exponent=EP_EXPONENT,
                               speed_top_k=SPEED_TOP_K, speed_weight=SPEED_WEIGHT)
        model.load_state_dict(state_dict, strict=True)
        self.model = model.to(self.device).eval()
        LOGGER.info("GTRS judge loaded (%d tensors), margin %s", len(state_dict), self.margin)

    @torch.inference_mode()
    def judge(self, images: dict, ego_status: np.ndarray, plan: np.ndarray) -> dict:
        m = self.model
        head = m._trajectory_head
        camera = preprocess_images({c: images[c] for c in JUDGE_CAMERAS}).unsqueeze(0).to(self.device)
        status = build_status_feature(command_one_hot=ego_status[:4], velocity_xy=ego_status[4:6],
                                      acceleration_xy=ego_status[6:8]).unsqueeze(0).to(self.device)
        status_encoding = m._status_encoding(status)
        keyval = m._image_features(camera) + m._keyval_embedding.weight[None]

        vocab = head.vocab.detach()
        n = vocab.shape[0]
        extra = torch.from_numpy(plan_to_vocab_poses(plan)).to(vocab)
        candidates = torch.cat([vocab, extra[None]], 0)                             # [n + 1, 40, 3]
        embedded = head.pos_embed(candidates.reshape(n + 1, -1))[None]
        if head.normalize_vocab_pos:
            embedded = head.encoder(embedded)
        features = head.transformer(embedded, keyval) + status_encoding.unsqueeze(1)
        heads = {k: head.heads[k](features).squeeze(-1)
                 for k in ("no_at_fault_collisions", "drivable_area_compliance", "ego_progress")}
        base = _trajectory_scores(heads, NC_DAC_EP_SCORER, EP_EXPONENT)                # [1, n + 1]
        picked = _speed_reranked_scores(base[:, :n], vocab, top_k=SPEED_TOP_K, speed_weight=SPEED_WEIGHT,
                                        speed_proxy="longitudinal", curvature_weight=0.0,
                                        heading_change_weight=0.0)
        g = int(picked.argmax(1)[0])
        s_g, s_w = float(base[0, g]), float(base[0, n])
        use_gtrs = math.isfinite(self.margin) and (s_g - s_w) > self.margin
        sub = {k: v.sigmoid()[0] for k, v in heads.items()}
        record = {
            "s_w": round(s_w, 4), "s_g": round(s_g, 4), "use_gtrs": use_gtrs,
            "w": [round(float(sub[k][n]), 4) for k in ("no_at_fault_collisions", "drivable_area_compliance", "ego_progress")],
            "g": [round(float(sub[k][g]), 4) for k in ("no_at_fault_collisions", "drivable_area_compliance", "ego_progress")],
        }
        trajectory = vocab_poses_to_plan(vocab[g].float().cpu().numpy()) if use_gtrs else None
        return {"trajectory": trajectory, "record": record}
