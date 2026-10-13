"""Tạo ảnh nền bằng AI (Stable Diffusion XL rút gọn) từ mô tả trong cột "Ảnh nền"."""
from __future__ import annotations

import gc
import subprocess
import sys
from pathlib import Path

from . import media
from .project import UserError

STEPS = 25
GUIDANCE = 8.0


def _ensure_diffusers(log):
    try:
        import diffusers  # noqa: F401
    except ImportError:
        log("⏳ Đang cài thư viện tạo ảnh (diffusers)...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "diffusers", "accelerate", "safetensors"], check=True)


def _load(log):
    import torch

    if not torch.cuda.is_available():
        raise UserError("Tạo ảnh AI cần GPU. Bật Runtime → T4 GPU.")
    _ensure_diffusers(log)
    from diffusers import StableDiffusionXLPipeline

    log(f"⏳ Đang tải mô hình ảnh {media.AI_MODEL} (lần đầu mất vài phút)...")
    try:
        pipe = StableDiffusionXLPipeline.from_pretrained(
            media.AI_MODEL, torch_dtype=torch.float16, use_safetensors=True, variant="fp16")
    except Exception:  # noqa: BLE001  (một số mô hình không có biến thể fp16)
        pipe = StableDiffusionXLPipeline.from_pretrained(media.AI_MODEL, torch_dtype=torch.float16, use_safetensors=True)
    return pipe.to("cuda")


def generate_all(pdir: Path, scenes: list[dict], st: dict, force: bool = False, log=print) -> int:
    targets = []
    for i, sc in enumerate(scenes):
        kind, payload = media.classify(sc["bg"], pdir)
        if kind == "missing":
            raise UserError(f"Cảnh {i + 1}: không thấy ảnh “{payload}” trong thư viện ảnh.")
        if kind == "ai":
            path = media.ai_path(pdir, payload, st)
            if force or not path.exists():
                targets.append((i, payload, path))
    if not targets:
        log("✅ Không có cảnh nào cần tạo ảnh AI mới.")
        return 0

    import torch

    style = media.require_style(st)
    log(f"🎨 Phong cách: {style['style_name']}")
    pipe = _load(log)
    w, h = media.AI_SIZE
    try:
        for k, (i, prompt, path) in enumerate(targets, 1):
            log(f"🎨 Ảnh {k}/{len(targets)} (cảnh {i + 1}): {prompt[:70]}")
            gen = torch.Generator("cuda").manual_seed(int(st["seed"]) + i)
            p1, p2, neg = media.ai_prompts(prompt, style)
            img = pipe(
                prompt=p1, prompt_2=p2, negative_prompt=neg, negative_prompt_2=neg, width=w, height=h,
                num_inference_steps=STEPS, guidance_scale=GUIDANCE, generator=gen,
            ).images[0]
            img.save(path)
    finally:
        del pipe
        gc.collect()
        torch.cuda.empty_cache()
    log(f"✅ Xong: tạo {len(targets)} ảnh.")
    return len(targets)
