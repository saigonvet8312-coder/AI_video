"""Tạo ảnh nền bằng AI (Stable Diffusion XL rút gọn) từ mô tả trong cột "Ảnh nền"."""
from __future__ import annotations

import gc
import importlib
import subprocess
import sys
from pathlib import Path

from . import media, subjects
from .project import UserError

STEPS = 25
GUIDANCE = 8.0


def _ensure_diffusers(log):
    try:
        import diffusers  # noqa: F401
    except ImportError:
        log("⏳ Đang cài thư viện tạo ảnh (diffusers)...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "diffusers", "accelerate", "safetensors"], check=True)


def _is_torchao_error(e: BaseException) -> bool:
    msg = f"{type(e).__name__}: {e}".lower()
    return "torchao" in msg or "fqntoconfig" in msg


def _drop_torchao(log) -> None:
    """Gỡ torchao (thư viện tuỳ chọn, hay lệch phiên bản với diffusers trên Colab) và xoá bản diffusers đã nạp dở."""
    log("🔧 Thư viện torchao trên Colab không khớp với diffusers: gỡ torchao (tool không cần) rồi thử lại...")
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "-q", "torchao"], check=False)
    for name in [k for k in sys.modules if k.split(".")[0] in ("diffusers", "torchao")]:
        del sys.modules[name]
    importlib.invalidate_caches()


def import_diffusers(attr: str, log=print):
    """Lấy một lớp từ diffusers; nếu lỗi do torchao lệch phiên bản thì tự sửa rồi thử lại một lần."""
    try:
        return getattr(importlib.import_module("diffusers"), attr)
    except Exception as e:  # noqa: BLE001
        if not _is_torchao_error(e):
            raise
        _drop_torchao(log)
        return getattr(importlib.import_module("diffusers"), attr)


def _load(log):
    import torch

    if not torch.cuda.is_available():
        raise UserError("Tạo ảnh AI cần GPU. Bật Runtime → T4 GPU.")
    _ensure_diffusers(log)
    StableDiffusionXLPipeline = import_diffusers("StableDiffusionXLPipeline", log)

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
    english = subjects.english_for(pdir, [t[1] for t in targets], st.get("_api_key", ""), st.get("_model", ""), log=log)
    pipe = _load(log)
    w, h = media.AI_SIZE
    try:
        for k, (i, prompt, path) in enumerate(targets, 1):
            subject = english[k - 1]
            log(f"🎨 Ảnh {k}/{len(targets)} (cảnh {i + 1}): {subject[:70]}")
            gen = torch.Generator("cuda").manual_seed(int(st["seed"]) + i)
            p1, p2, neg = media.ai_prompts(subject, style)
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
