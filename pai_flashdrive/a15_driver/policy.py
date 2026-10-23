"""Alpamayo 1.5 policy for the AlpaSim driver contract (<= 16 GiB VRAM per replica).

* Weights load to CPU in bf16; torchao int8 weight-only quantization then moves each
  linear to the GPU as it is quantized, so the GPU never holds the 21 GB bf16 model.
  Quantized: language model, action expert, vision tower and lm_head linears (dims % 128).
* "No reasoning" mode (default): the assistant turn starts as <|cot_start|><|cot_end|>, so
  the model goes straight to <traj_future_start>. On nuReasoning validation this was
  faster (0.88 vs 1.60 s/plan on an L40S) and more accurate (ADE 1.96 vs 3.14 m) than
  generating the reasoning text (alpasim/LEDGER.md, Result 2).
* Model loading mirrors nureasoning/src/a15_infer.py::load_model (config from the public
  Qwen3-VL-8B-Instruct, verified vocab 155697 / traj offset 151669, zero missing keys).
"""
from __future__ import annotations

import json
import logging
import os
import time

import numpy as np
import torch

from .route_choice import choose as route_choose, choose_fast, path_lengths, route_costs, stall_rescue_choice

LOGGER = logging.getLogger("a15_policy")

# Alpamayo camera slots (alpasim_driver.models.alpamayo_base.CAMERA_NAME_TO_INDEX)
CAMERA_NAME_TO_INDEX = {
    "camera_cross_left_120fov": 0,
    "camera_front_wide_120fov": 1,
    "camera_cross_right_120fov": 2,
    "camera_rear_left_70fov": 3,
    "camera_rear_tele_30fov": 4,
    "camera_rear_right_70fov": 5,
    "camera_front_tele_30fov": 6,
}
# nuPlan track logical ids -> Alpamayo slots (Motional rig: L0 / F0 / R0 face left-front / front / right-front)
NUPLAN_TO_SLOT = {"CAM_L0": 0, "CAM_F0": 1, "CAM_R0": 2}


def _quantize(model, mode: str) -> int:
    if mode == "none":
        model.to("cuda")
        return 0
    from torchao.quantization import Int8WeightOnlyConfig, quantize_

    n = []

    def keep(m, fqn):
        ok = (isinstance(m, torch.nn.Linear) and m.in_features % 128 == 0 and m.out_features % 128 == 0
              and not any(k in fqn for k in ("action_in", "action_out", "diffusion")))
        if ok:
            n.append(m.in_features * m.out_features)
        return ok
    if mode != "int8wo":
        raise ValueError(f"unknown quantization {mode}")
    quantize_(model, Int8WeightOnlyConfig(), filter_fn=keep, device="cuda")
    model.to("cuda")                      # remaining (unquantized) parameters and buffers
    return sum(n)


class CpuEmbedding(torch.nn.Module):
    """Token-embedding lookup served from CPU memory (the 155,697 x 4,096 bf16 table is
    ~1.2 GiB of GPU memory otherwise). Exact: same weights, same gather, moved to the ids' device."""

    def __init__(self, emb: torch.nn.Embedding) -> None:
        super().__init__()
        self.weight_cpu = emb.weight.detach().to("cpu")
        self.padding_idx = emb.padding_idx
        self.num_embeddings, self.embedding_dim = emb.num_embeddings, emb.embedding_dim

    @property
    def weight(self):                      # some HF code reads .weight.dtype / .device
        return self.weight_cpu

    def forward(self, ids: torch.Tensor) -> torch.Tensor:
        return torch.nn.functional.embedding(ids.cpu(), self.weight_cpu, self.padding_idx).to(ids.device)


def _embed_to_cpu(model) -> int:
    lm = model.vlm.model.language_model
    emb = lm.embed_tokens
    n = emb.weight.numel()
    lm.embed_tokens = CpuEmbedding(emb)
    del emb
    return n


class Alpamayo15Policy:
    """predict(frames, cam_slots, hist_xyz, hist_rot) -> (xy (64,2), yaw (64,)) in the t0 rig frame."""

    output_frequency_hz = 10.0

    def __init__(self, *, model_dir: str, vlm_dir: str, processor_dir: str,
                 quant: str = "int8wo", reasoning: bool = False, seed: int = 42,
                 embed_cpu: bool = True, cuda_graph: bool = False, num_samples: int = 1,
                 chooser: str = "medoid", route_margin: float = 2.0, route_min_len: float = 0.0,
                 route_big_gap: float = 0.0, route_big_gap_min_len: float = 0.0,
                 diffusion_temperature: float = 1.0, fast_tol: float = 1.0, expert_ckpt: str | None = None,
                 stall_m: float = 3.0, force_start: bool = False) -> None:
        from alpamayo1_5 import helper
        from alpamayo1_5.models.alpamayo1_5 import Alpamayo1_5

        t0 = time.time()
        helper.BASE_PROCESSOR_NAME = processor_dir      # offline: local Qwen3-VL-2B processor files
        d = json.load(open(os.path.join(model_dir, "config.json")))
        want = (d["vocab_size"], d["traj_token_start_idx"])
        d["vlm_name_or_path"] = vlm_dir
        d["attn_implementation"] = "sdpa"
        cfg = Alpamayo1_5.config_class(**d)
        got = (cfg.vocab_size, cfg.traj_token_start_idx)
        assert got == want, f"tokenizer mismatch: {got} != {want}"
        model, info = Alpamayo1_5.from_pretrained(model_dir, config=cfg, dtype=torch.bfloat16,
                                                  output_loading_info=True, low_cpu_mem_usage=True)
        bad = {k: v for k, v in info.items() if v}
        assert not bad, f"loading info not clean: { {k: list(v)[:5] for k, v in bad.items()} }"
        if expert_ckpt:                    # fine-tuned action expert (a15_ft/train.py): replaces expert + projections
            sd = {k: v for k, v in torch.load(expert_ckpt, map_location="cpu").items() if not k.startswith("_")}  # _step: metadata
            res = model.load_state_dict(sd, strict=False)
            assert not res.unexpected_keys, f"unexpected keys in {expert_ckpt}: {res.unexpected_keys[:5]}"
            left = [k for k in res.missing_keys if k.startswith(("expert.", "action_in_proj.", "action_out_proj."))]
            assert not left, f"{expert_ckpt} misses expert keys: {left[:5]}"
            LOGGER.info("loaded fine-tuned expert %s (%d tensors)", expert_ckpt, len(sd))
        model.eval()
        t1 = time.time()
        if embed_cpu:                      # before the GPU move, so the table never lands there
            self.cpu_embedding_params = _embed_to_cpu(model)
        self.quantized_params = _quantize(model, quant)
        if cuda_graph:                     # bounded exact CUDA graphs for the diffusion expert (alpamayo1_5 API)
            model.enable_diffusion_expert_cuda_graph(max_batch_size=1)
        torch.cuda.empty_cache()
        self._model, self._helper = model, helper
        self._proc = helper.get_processor(model.tokenizer)
        self._reasoning, self._seed = reasoning, seed
        self._eos = model.tokenizer.convert_tokens_to_ids("<|traj_future_start|>")
        self._num_samples, self._hist = max(1, int(num_samples)), None
        self._chooser, self._route, self.last_choice = chooser, None, 0
        self._k_now = self._num_samples
        self._route_margin, self._route_min_len = route_margin, route_min_len
        self._fast_tol = fast_tol                  # chooser "fast": path-shape tolerance to the medoid, m
        self._stall_m = stall_m                    # chooser "stall": sample 0 moving less than this in 4 s stalls
        self._force_start = force_start            # append <traj_future_start> instead of generating it
        self._route_big_gap, self._route_big_gap_min_len = route_big_gap, route_big_gap_min_len
        # initial-noise temperature of the flow-matching sampler (Alpamayo 1.5 nav notebook uses 0.6:
        # "more stable but less diverse" trajectories); 1.0 is the library default we ran until 2026-10-04
        self._diff_kwargs = {} if diffusion_temperature == 1.0 else {"temperature": float(diffusion_temperature)}
        if self._num_samples > 1:
            self._wrap_diffusion_medoid()
        LOGGER.info("Alpamayo 1.5 loaded in %.0fs, quantized %s (%.2fB params) in %.0fs, reserved %.2f GiB",
                    t1 - t0, quant, self.quantized_params / 1e9, time.time() - t1,
                    torch.cuda.memory_reserved() / 2**30)

    def _wrap_diffusion_medoid(self) -> None:
        """K trajectory samples per plan. chooser "medoid": keep the medoid (least total xy distance
        to the others). chooser "route": keep sample 0 (the K=1 plan) unless another sample follows
        the route waypoints clearly better (route_choice.choose).
        The VLM prompt runs ONCE; only the flow-matching sampler repeats, reusing the prompt KV cache
        (sample_trajectories_from_data_with_vlm_rollout's step_fn crops the cache back after every
        expert call). Sampling K sequences through the VLM instead would copy the ~470 MB prompt
        cache K times and break the 16 GiB cap."""
        model, orig = self._model, self._model.diffusion.sample

        def sample(*args, batch_size, **kw):
            assert batch_size == 1, "medoid wrapper expects one plan per call"
            K = self._k_now                       # per-call sample count (predict(..., num_samples=...))
            if K == 1:
                self.last_choice = 0
                return orig(*args, batch_size=1, **kw)
            hx, hr = self._hist
            to_xy = lambda S_: model.action_space.action_to_traj(
                S_, hx[:, -1].repeat(len(S_), *[1] * (hx.dim() - 2)), hr[:, -1].repeat(len(S_), *[1] * (hr.dim() - 2)))[0]
            if self._chooser == "stall":
                # draw sample 0 only; more samples only if it stalls (moves < 3 m in 4 s), so normal replans cost
                # what K=1 costs
                s0 = orig(*args, batch_size=1, **kw)
                x0 = to_xy(s0)[..., :2].reshape(1, -1, 2).float().cpu().numpy()
                if np.linalg.norm(x0[0, 39]) >= self._stall_m:
                    self.last_choice = 0
                    return s0
                S = torch.cat([s0] + [orig(*args, batch_size=1, **kw) for _ in range(K - 1)], 0)
                cand = to_xy(S)[..., :2].reshape(K, -1, 2).float().cpu().numpy()
                i = stall_rescue_choice(cand, stall_m=self._stall_m)
                self.last_choice = i
                self.last_costs = np.linalg.norm(cand[:, 39], axis=1).round(1).tolist()   # 4 s displacement per sample
                self.last_ends = cand[:, ::8].round(1).tolist()
                return S[i:i + 1]
            S = torch.cat([orig(*args, batch_size=1, **kw) for _ in range(K)], 0)       # (K, *action_dims)
            if self._chooser == "record":
                # RoaD-style data capture: drive sample 0 (what K=1 would drive) and keep all K for labelling
                tr = model.action_space.action_to_traj(
                    S, hx[:, -1].repeat(K, *[1] * (hx.dim() - 2)), hr[:, -1].repeat(K, *[1] * (hr.dim() - 2)))
                self.last_samples = (tr[0].reshape(K, -1, 3).float().cpu().numpy(),
                                     tr[1].reshape(K, -1, 3, 3).float().cpu().numpy())
                self.last_choice = 0
                return S[0:1]
            xyz = to_xy(S)
            xy = xyz[..., :2].reshape(K, -1).float()
            if self._chooser == "fast":
                cand = xy.reshape(K, -1, 2).cpu().numpy()
                i = choose_fast(cand, shape_tol_m=self._fast_tol)
                self.last_costs = path_lengths(cand).round(1).tolist()           # logged as "costs": path lengths
                self.last_ends = cand[:, ::8].round(1).tolist()
            elif self._chooser == "route":
                cand = xy.reshape(K, -1, 2).cpu().numpy()
                i = route_choose(cand, self._route, margin_m=self._route_margin, min_len_ratio=self._route_min_len,
                                 big_gap_m=self._route_big_gap, big_gap_min_len=self._route_big_gap_min_len)
                if self._route is not None:
                    self.last_costs = route_costs(cand, self._route).round(1).tolist()
                    self.last_ends = cand[:, ::8].round(1).tolist()           # 8 points per candidate
            else:
                i = int(torch.cdist(xy, xy).sum(1).argmin())
            self.last_choice = i
            self._last_spread = float(torch.cdist(xy, xy).max()) / max(xyz.shape[-2], 1) ** 0.5
            return S[i:i + 1]
        model.diffusion.sample = sample

    @torch.no_grad()
    def _forced_rollout(self, inp: dict) -> tuple[torch.Tensor, torch.Tensor]:
        """Trajectory with <traj_future_start> appended to the prompt instead of generated (A15_FORCE_TRAJ_START=1).

        In closed loop the 4-token generation misses <traj_future_start> in 30-42% of plans (PAI H100 runs,
        2026-10-21: 336/800 and 237/799), and the library then attaches the action block after whatever was
        generated. Appending it is what NVIDIA's own teacher-forced training forward does (alpamayo-recipes
        alpamayo1_5_quant), so the expert always sees the context it was trained with. Same prefill, same
        position ids and attention mask as the library's rollout for one sequence; the diffusion sampler is the
        model's own (so the K-sample choosers still wrap it)."""
        import einops
        from alpamayo1_5.models.token_utils import to_special_token
        m = self._model
        hx, hr = inp["ego_history_xyz"], inp["ego_history_rot"]
        td = dict(inp["tokenized_data"])
        ids = m.fuse_traj_tokens(td.pop("input_ids"), {"ego_history_xyz": hx, "ego_history_rot": hr})
        dev = ids.device
        start = m.tokenizer.convert_tokens_to_ids(to_special_token("traj_future_start"))
        ids = torch.cat([ids, torch.full((ids.shape[0], 1), start, dtype=ids.dtype, device=dev)], 1)
        if td.get("attention_mask") is not None:
            am = td["attention_mask"]
            td["attention_mask"] = torch.cat([am, torch.ones((am.shape[0], 1), dtype=am.dtype, device=am.device)], 1)
        out = m.vlm(input_ids=ids, use_cache=True, return_dict=True, **td)
        cache = out.past_key_values
        L = cache.get_seq_length()
        n_tok = m.action_space.get_action_space_dims()[0]
        pos = einops.repeat(torch.arange(n_tok, device=dev), "l -> 3 b l", b=1).clone()
        pos += (m.vlm.model.rope_deltas + torch.full((1,), L, device=dev, dtype=torch.long)[:, None]).to(pos.device)
        mask = torch.zeros((1, 1, n_tok, L + n_tok), dtype=torch.float32, device=dev)
        fwd = {"is_causal": False} if m.config.expert_non_causal_attention else {}

        def step_fn(x, t):
            b = x.shape[0]
            e = m.action_in_proj(x, t)
            if e.dim() == 2:
                e = e.view(b, n_tok, -1)
            o = m.expert(inputs_embeds=e, position_ids=pos.expand(3, b, n_tok) if b > 1 else pos,
                         past_key_values=cache, attention_mask=mask.expand(b, -1, -1, -1), use_cache=True, **fwd)
            cache.crop(L)
            return m.action_out_proj(o.last_hidden_state[:, -n_tok:]).view(-1, *m.action_space.get_action_space_dims())

        a = m.diffusion.sample(batch_size=1, step_fn=step_fn, device=dev, return_all_steps=False, **self._diff_kwargs)
        return m.action_space.action_to_traj(a, hx[:, -1], hr[:, -1])

    @torch.no_grad()
    def predict(self, frames: torch.Tensor, cam_slots: list[int],
                hist_xyz: torch.Tensor, hist_rot: torch.Tensor, nav_text: str | None = None,
                route_xy: np.ndarray | None = None, num_samples: int | None = None) -> tuple[np.ndarray, np.ndarray, dict]:
        """frames: (n_cam, 4, 3, H, W) uint8 ordered as cam_slots (ascending);
        hist_*: (1, 1, 16, 3) / (1, 1, 16, 3, 3) ego history in the t0 rig frame;
        nav_text: optional route instruction ("Turn left in 30m"), Alpamayo 1.5's navigation input;
        route_xy: route waypoints in the rig frame, used by the "route" chooser."""
        self._route, self.last_choice, self.last_costs, self.last_ends = route_xy, 0, None, None
        self.last_samples = None
        self._k_now = self._num_samples if num_samples is None else max(1, int(num_samples))
        msgs = self._helper.create_message(frames.flatten(0, 1), camera_indices=torch.tensor(cam_slots),
                                           nav_text=nav_text)
        if not self._reasoning:
            msgs[-1]["content"][0]["text"] = "<|cot_start|><|cot_end|>"
        tok = self._proc.apply_chat_template(msgs, tokenize=True, add_generation_prompt=False,
                                             continue_final_message=True, return_dict=True, return_tensors="pt")
        inp = self._helper.to_device({"tokenized_data": tok, "ego_history_xyz": hist_xyz,
                                      "ego_history_rot": hist_rot}, "cuda")
        self._hist = (inp["ego_history_xyz"], inp["ego_history_rot"])
        torch.cuda.manual_seed_all(self._seed)
        if self._force_start and not self._reasoning:
            with torch.autocast("cuda", dtype=torch.bfloat16):
                xyz, rot = self._forced_rollout(inp)
            extra = {}
            xy = xyz[0, :, :2].float().cpu().numpy()
            r = rot[0].float()
        else:
            with torch.autocast("cuda", dtype=torch.bfloat16):
                xyz, rot, extra = self._model.sample_trajectories_from_data_with_vlm_rollout(
                    data=inp, top_p=0.98, temperature=0.6, num_traj_samples=1, diffusion_kwargs=self._diff_kwargs,
                    max_generation_length=256 if self._reasoning else 4, return_extra=True)
            xy = xyz[0, 0, 0, :, :2].float().cpu().numpy()
            r = rot[0, 0, 0].float()
        yaw = torch.atan2(r[:, 1, 0], r[:, 0, 0]).cpu().numpy()
        cot = str(np.array(extra.get("cot", [""]), dtype=object).ravel()[0]) if self._reasoning else ""
        return xy, yaw, {"prompt_tokens": int(tok["input_ids"].shape[1]), "cot": cot, "choice": self.last_choice,
                          "costs": self.last_costs, "ends": self.last_ends}
