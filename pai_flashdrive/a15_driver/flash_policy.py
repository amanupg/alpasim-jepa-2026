"""FlashDrive-accelerated Alpamayo 1.5 behind the v5 policy interface (A15_FLASH=1).

FlashDrive (z-lab, MIT; arXiv 2608.12932) speeds Alpamayo 1.5 up with streaming KV reuse, DFlash speculative
decoding, W4A8 (ParoQuant) language-model weights, fused + cudagraph-compiled expert steps and adaptive action
caching. v5 runs the forced-<traj_future_start> path (no text decoding) at ~1 Hz with several scenes per driver
process, so this module takes only the parts that fit that call pattern:

* W4A8 ParoQuant language model (vLLM Marlin kernels), from z-lab/Alpamayo-1.5-10B-PARO;
* the patched Qwen3-VL backbone, a compiled vision encoder and the compiled, fused action expert;
* adaptive action caching: `euler_with_cache`, FlashDrive's 8 Euler steps reusing the velocity on steps 3-6.

Not used: streaming (it assumes one stream fed every 0.1 s; we replan from a fresh 4-frame window per scene and
call) and DFlash (no text is decoded on the forced path).

Each plan is a full prefill of the prompt with <traj_future_start> appended (as v5's `_forced_rollout`), then the
action-expert tail. The prompt length is fixed by the camera set and resolution, so one StaticCache and one
compiled graph per primitive are reused for every scene; a different length rebuilds them.

Memory: the bf16 model is loaded on the CPU and the language model is quantized there (ParoQuant surgery + checkpoint
load) before anything moves to the GPU, so loading never holds the 21 GB bf16 model on the device (4 drivers share
one H100 in the official runs). The token-embedding table and lm_head (unused on this path) stay on the CPU.
"""
from __future__ import annotations

import json
import logging
import os
import time

import numpy as np
import torch

LOGGER = logging.getLogger("a15_flash_policy")


def _load_paro_full(model, paro_dir: str) -> None:
    """ParoQuantMixin.setup_paroquant's surgery, then a strict load of the whole -PARO checkpoint: every persistent
    tensor of the model must come from it and nothing may be left over (setup_paroquant only warns)."""
    import glob

    from flashdrive.quantization import BF16RotateLinearWrapper, RotateLinearW4A8, _iter_linears
    from safetensors.torch import load_file
    import paroquant.kernels.cuda  # noqa: F401  (stub if the prebuilt kernel was loaded)
    for layer in model.vlm.model.language_model.layers:
        for parent, name, linear in list(_iter_linears(layer)):
            setattr(parent, name, BF16RotateLinearWrapper(RotateLinearW4A8(linear.in_features, linear.out_features)))
    sd = {}
    for shard in sorted(glob.glob(os.path.join(paro_dir, "model*.safetensors"))):
        sd.update(load_file(shard, device="cpu"))
    n = len(sd)
    missing, unexpected = model.load_state_dict(sd, strict=False)
    del sd
    assert not missing and not unexpected, f"PARO load not clean: missing {missing[:5]}, unexpected {unexpected[:5]}"
    LOGGER.info("loaded %d tensors from %s (strict)", n, paro_dir)


def _load_prebuilt_rotation_kernel() -> None:
    """A15_PARO_KERNEL=<paroquant_rotation.so>: load the prebuilt rotation kernel (pai_flashdrive/kernel, built with
    nvcc 12.8 for sm 8.0/8.6/8.9/9.0) instead of paroquant's JIT build, which needs nvcc on the node (Insomnia's
    compute nodes have none, and the official image runs offline). The .so registers torch.ops.rotation.rotate via
    TORCH_LIBRARY; a stub module then satisfies FlashDrive's `import paroquant.kernels.cuda`."""
    import sys
    import types
    so = os.environ.get("A15_PARO_KERNEL")
    if not so or "paroquant.kernels.cuda" in sys.modules:
        return
    torch.ops.load_library(so)
    try:
        @torch.library.register_fake("rotation::rotate")
        def _fake(x, idx_ij, theta, scales=None, group_size=128):
            return torch.empty_like(x)
    except RuntimeError:
        pass
    sys.modules["paroquant.kernels.cuda"] = types.ModuleType("paroquant.kernels.cuda")
    LOGGER.info("loaded prebuilt rotation kernel %s", so)


class _Ticker:
    """Per-stage GPU time in ms (A15_FD_TIMING=1; synchronizes, so only for measurements)."""

    def __init__(self, on: bool) -> None:
        self.on, self.ms = on, {}
        if on:
            torch.cuda.synchronize()
            self.t = time.perf_counter()

    def __call__(self, name: str) -> None:
        if self.on:
            torch.cuda.synchronize()
            t = time.perf_counter()
            self.ms[name] = round((t - self.t) * 1000, 1)
            self.t = t


class FlashAlpamayo15Policy:
    """predict(frames, cam_slots, hist_xyz, hist_rot) -> (xy (64,2), yaw (64,), info), like Alpamayo15Policy."""

    output_frequency_hz = 10.0

    def __init__(self, *, model_dir: str, paro_dir: str, vlm_dir: str, processor_dir: str, seed: int = 42,
                 embed_cpu: bool = True, compile_mode: str | None = "max-autotune", steps: int = 8,
                 cache_steps: tuple[int, ...] = (3, 4, 5, 6), **ignored) -> None:
        import flashdrive  # noqa: F401  (applies the patch-embed fix at import)
        from alpamayo1_5 import helper
        from alpamayo1_5.models.alpamayo1_5 import Alpamayo1_5
        from flashdrive import FlashDriveMixin
        from flashdrive._backbone import patch_backbone

        from .policy import CpuEmbedding

        if ignored:
            LOGGER.info("FlashDrive policy ignores v5 options: %s", sorted(k for k, v in ignored.items() if v))
        t0 = time.time()
        helper.BASE_PROCESSOR_NAME = processor_dir
        d = json.load(open(os.path.join(model_dir, "config.json")))
        d["vlm_name_or_path"] = vlm_dir
        d["attn_implementation"] = "sdpa"
        cfg = Alpamayo1_5.config_class(**d)
        cfg._attn_implementation = "sdpa"
        Alpamayo1_5._supports_sdpa = True
        # The -PARO checkpoint holds the whole model (quantized language-model linears plus every other tensor in
        # bf16), so the model is built empty on the CPU (no random init), the language-model linears are swapped for
        # the W4A8 modules, and everything is filled from it: the 22 GB bf16 base is never read (its LM linears would
        # be thrown away; reading it from the shared fileset took ~13 of the first load's 17.5 min).
        from transformers.modeling_utils import no_init_weights
        with no_init_weights():
            model = Alpamayo1_5._from_config(cfg, torch_dtype=torch.bfloat16)
        model.eval()
        # FlashDrive's composition (flashdrive.from_pretrained) minus streaming and DFlash, and on the CPU first
        model.__class__ = type(f"FlashDrive{Alpamayo1_5.__name__}", (FlashDriveMixin, Alpamayo1_5), {})
        model._past_key_values = None
        model.traj_start_token_id = model.tokenizer.convert_tokens_to_ids("<|traj_future_start|>")
        patch_backbone(model)
        model.setup_torch_compile(compile_mode)
        _load_prebuilt_rotation_kernel()
        _load_paro_full(model, paro_dir)         # CPU surgery + every tensor from the -PARO checkpoint (strict)
        model.setup_expert_fusion()
        t1 = time.time()
        if embed_cpu:
            lm = model.vlm.model.language_model
            lm.embed_tokens = CpuEmbedding(lm.embed_tokens)
        lm_head = model.vlm.lm_head
        model.vlm.lm_head = torch.nn.Identity()  # not used: no text is decoded on the forced path
        model.to("cuda")
        model.vlm.lm_head = lm_head              # kept on the CPU for completeness
        torch.cuda.empty_cache()
        self._model, self._helper = model, helper
        self._proc = helper.get_processor(model.tokenizer)
        self._seed = seed
        self._diff = {"inference_step": int(steps), "cache_steps": list(cache_steps), "int_method": "euler_with_cache"}
        self._len = None
        self._timing = os.environ.get("A15_FD_TIMING", "0") == "1"
        self.last_timing = None
        self.last_choice, self.last_costs, self.last_ends = 0, None, None
        LOGGER.info("FlashDrive Alpamayo 1.5 loaded in %.0fs (build + PARO load + fusion %.0fs), compile %s, %d steps cache %s, "
                    "reserved %.2f GiB", time.time() - t0, t1 - t0, compile_mode, steps, list(cache_steps),
                    torch.cuda.memory_reserved() / 2**30)

    def _setup_length(self, ids: torch.Tensor, grid: torch.Tensor) -> None:
        """StaticCache + position table for a prompt of this length (first call, or if the length ever changes)."""
        from flashdrive._backbone import StaticCache
        m = self._model
        L = ids.shape[1]
        m.max_cache_len = L + m.num_action_tokens
        m._past_key_values = StaticCache(config=m.vlm.config, max_cache_len=m.max_cache_len, max_batch_size=1)
        if self._len is not None:                # a new length: the compiled primitives were bound to the old shapes
            LOGGER.warning("prompt length changed %d -> %d: rebuilding cache and compiled steps", self._len, L)
            m.setup_torch_compile(m._torch_compile)
            m.vlm.model.visual.reset_shape_caches()
            m.vlm.model.language_model.reset_shape_caches()
        self._len = L

    @torch.no_grad()
    def predict(self, frames: torch.Tensor, cam_slots: list[int], hist_xyz: torch.Tensor, hist_rot: torch.Tensor,
                nav_text: str | None = None, route_xy: np.ndarray | None = None,
                num_samples: int | None = None) -> tuple[np.ndarray, np.ndarray, dict]:
        """Same inputs and outputs as Alpamayo15Policy.predict on its forced-start, K=1 path."""
        if num_samples not in (None, 1):
            raise ValueError("FlashDrive policy draws one sample per plan")
        m = self._model
        msgs = self._helper.create_message(frames.flatten(0, 1), camera_indices=torch.tensor(cam_slots),
                                           nav_text=nav_text)
        msgs[-1]["content"][0]["text"] = "<|cot_start|><|cot_end|>"
        tok = self._proc.apply_chat_template(msgs, tokenize=True, add_generation_prompt=False,
                                             continue_final_message=True, return_dict=True, return_tensors="pt")
        inp = self._helper.to_device({"tokenized_data": tok, "ego_history_xyz": hist_xyz,
                                      "ego_history_rot": hist_rot}, "cuda")
        hx, hr = inp["ego_history_xyz"], inp["ego_history_rot"]
        td = inp["tokenized_data"]
        torch.cuda.manual_seed_all(self._seed)
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            ids = m.fuse_traj_tokens(td["input_ids"], {"ego_history_xyz": hx, "ego_history_rot": hr})
            ids = torch.cat([ids, torch.full((1, 1), m.traj_start_token_id, dtype=ids.dtype, device=ids.device)], 1)
            am = td.get("attention_mask")
            if am is not None:
                am = torch.cat([am, torch.ones((1, 1), dtype=am.dtype, device=am.device)], 1)
            grid = td["image_grid_thw"]
            if self._len != ids.shape[1]:
                self._setup_length(ids, grid)
            L = ids.shape[1]
            tick = _Ticker(self._timing)
            image_embeds, deepstack = m._encode(td["pixel_values"], grid)
            tick("encode")
            embeds, image_mask = m._embed_tokens_with_images(ids, image_embeds)
            pos, _ = m.vlm.model.get_rope_index(ids, grid, None, None)
            pad = m.max_cache_len - L
            pos = torch.cat([pos, pos[:, :, -1:] + torch.arange(1, pad + 1, device=pos.device)], -1)
            m.streaming_position_ids = pos
            m.vlm.model.language_model(inputs_embeds=embeds, position_ids=pos, attention_mask=am,
                                       past_key_values=m._past_key_values,
                                       cache_position=torch.arange(L, device=ids.device),
                                       visual_pos_masks=image_mask[..., 0], deepstack_visual_embeds=deepstack,
                                       streaming_attention_mask=None, use_cache=True)
            tick("prefill")
            xyz, rot = m._sample_actions_and_format(
                action_start_pos=torch.tensor([L], device=ids.device), num_traj_samples=1, num_traj_sets=1,
                ego_history_xyz=hx, ego_history_rot=hr, output_ids=ids, diffusion_kwargs=self._diff,
                return_extra=False)
            tick("action")
            self.last_timing = tick.ms
        xy = xyz[0, 0, 0, :, :2].float().cpu().numpy()
        r = rot[0, 0, 0].float()
        yaw = torch.atan2(r[:, 1, 0], r[:, 0, 0]).cpu().numpy()
        return xy, yaw, {"prompt_tokens": int(tok["input_ids"].shape[1]), "cot": "", "choice": 0,
                          "costs": None, "ends": None}
