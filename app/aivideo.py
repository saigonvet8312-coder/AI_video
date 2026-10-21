"""Biến ảnh nền AI của từng cảnh thành VIDEO chuyển động thật (Stable Video Diffusion, chạy được trên Colab T4).

Luồng: kịch bản → mô tả chủ thể → ảnh AI đúng nội dung cảnh → SVD cho ảnh chuyển động → làm chậm,
nội suy khung và chạy xuôi–ngược cho vừa độ dài giọng đọc.

Lưu ý: SVD là mô hình ẢNH → VIDEO nên nội dung do ảnh (tạo từ kịch bản) quyết định; chuyển động do mô hình tự suy ra,
không điều khiển được bằng chữ.
"""
from __future__ import annotations

import gc
import os
import subprocess
import tempfile
import time
from pathlib import Path

from . import aiimage, media
from .project import UserError, digest

# Cảnh nào được thay bằng video AI (cảnh số liệu/danh sách/so sánh giữ đồ hoạ động; cảnh kết giữ nguyên)
VIDEO_TEMPLATES = ("hero", "image", "statement", "quote")
SVD_MODEL = os.environ.get("AVG_VIDEO_MODEL", "stabilityai/stable-video-diffusion-img2vid-xt")
SIZE = (576, 1024)   # rộng x cao, khớp với ảnh AI
SVD_FPS = 7
STEPS = 20

GATE_HELP = (
    "Mô hình video SVD cần bạn đồng ý điều khoản trên Hugging Face:\n"
    "1) Mở https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt, đăng nhập và bấm đồng ý điều khoản.\n"
    "2) Tạo token loại Read tại https://huggingface.co/settings/tokens rồi dán vào ô “Hugging Face token” ở tab ③ "
    "(hoặc lưu vào Colab Secrets với tên HF_TOKEN).\n"
    "Kiểm tra điều khoản sử dụng nếu bạn dùng cho mục đích thương mại."
)


def eligible(pdir: Path, scene: dict, st: dict, download: bool = False) -> bool:
    """Cảnh này sẽ dùng video AI? (đã bật, đúng loại mẫu, và có ảnh nền)."""
    if not st.get("video_ai") or scene["template"] not in VIDEO_TEMPLATES:
        return False
    try:
        return media.resolve(pdir, scene, st, download=download) is not None
    except UserError:
        return False


def clip_path(pdir: Path, scene: dict, st: dict) -> Path:
    img = media.resolve(pdir, scene, st, download=False)
    key = digest(img.name, img.stat().st_size, SVD_MODEL, int(st["video_frames"]), int(st["video_motion"]), st.get("seed"))
    d = pdir / "aivideo"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"svd-{key}.mp4"


# ── Tạo video bằng SVD ────────────────────────────────────────────────────────
def _colab_secret(name: str) -> str:
    try:
        from google.colab import userdata  # type: ignore

        return userdata.get(name) or ""
    except Exception:  # noqa: BLE001
        return ""


def _load(log, hf_token: str = ""):
    import torch

    if not torch.cuda.is_available():
        raise UserError("Tạo video AI cần GPU. Bật Runtime → T4 GPU.")
    aiimage._ensure_diffusers(log)
    StableVideoDiffusionPipeline = aiimage.import_diffusers("StableVideoDiffusionPipeline", log)

    token = (hf_token or "").strip() or os.environ.get("HF_TOKEN") or _colab_secret("HF_TOKEN") or None
    log(f"⏳ Đang tải mô hình video {SVD_MODEL} (nặng, lần đầu mất vài phút)...")
    try:
        pipe = StableVideoDiffusionPipeline.from_pretrained(
            SVD_MODEL, torch_dtype=torch.float16, variant="fp16", token=token)
    except Exception as e:  # noqa: BLE001
        msg = str(e).lower()
        if any(k in msg for k in ("gated", "401", "403", "restricted", "access to model", "log in", "token")):
            raise UserError(GATE_HELP) from e
        raise
    pipe.enable_model_cpu_offload()  # giữ VRAM thấp để chạy trên T4
    try:
        pipe.unet.enable_forward_chunking()
    except Exception:  # noqa: BLE001
        pass
    return pipe


def _run(pipe, img_path: Path, st: dict, seed: int, log) -> list:
    """Sinh danh sách khung hình (PIL). Hết VRAM thì tự giảm số khung rồi thử lại."""
    import torch
    from PIL import Image

    image = Image.open(img_path).convert("RGB").resize(SIZE)
    plans = [(int(st["video_frames"]), 2), (14, 1)]
    last = None
    for n_frames, chunk in plans:
        try:
            gen = torch.Generator("cpu").manual_seed(seed)
            return pipe(image, height=SIZE[1], width=SIZE[0], num_frames=n_frames, decode_chunk_size=chunk,
                        motion_bucket_id=int(st["video_motion"]), noise_aug_strength=0.02, fps=SVD_FPS,
                        num_inference_steps=STEPS, generator=gen).frames[0]
        except torch.cuda.OutOfMemoryError as e:
            last = e
            torch.cuda.empty_cache()
            gc.collect()
            log(f"⚠️ Hết VRAM với {n_frames} khung — thử lại với cấu hình nhẹ hơn...")
    raise UserError(f"Hết bộ nhớ GPU khi tạo video AI ({last}). Hãy chọn 14 khung hoặc khởi động lại Runtime.")


def _write_mp4(frames: list, out: Path) -> None:
    with tempfile.TemporaryDirectory() as td:
        for k, fr in enumerate(frames):
            fr.save(Path(td) / f"{k:04d}.png")
        _ff("-framerate", str(SVD_FPS), "-i", str(Path(td) / "%04d.png"), "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "16", "-pix_fmt", "yuv420p", str(out))


def generate_all(pdir: Path, scenes: list[dict], st: dict, force: bool = False, log=print) -> int:
    targets = []
    for i, sc in enumerate(scenes):
        if eligible(pdir, sc, st, download=True):
            out = clip_path(pdir, sc, st)
            if force or not out.exists():
                targets.append((i, media.resolve(pdir, sc, st), out))
    if not targets:
        n_all = sum(1 for sc in scenes if eligible(pdir, sc, st))
        log("✅ Không có cảnh nào cần tạo video AI mới." if n_all else
            "ℹ️ Chưa có cảnh nào đủ điều kiện: cần bật “Video AI” và cảnh phải có ảnh nền (hãy bấm “Tạo ảnh AI” trước).")
        return 0

    import torch

    pipe = _load(log, st.get("_hf_token", ""))
    made = 0
    try:
        for k, (i, img, out) in enumerate(targets, 1):
            t0 = time.time()
            log(f"🎬 Video {k}/{len(targets)} (cảnh {i + 1}) — mỗi cảnh mất vài phút trên T4, xin chờ...")
            frames = _run(pipe, img, st, int(st["seed"]) + i, log)
            out.parent.mkdir(parents=True, exist_ok=True)
            _write_mp4(frames, out)
            made += 1
            log(f"   ✓ xong trong {time.time() - t0:.0f}s")
    finally:
        del pipe
        gc.collect()
        torch.cuda.empty_cache()
    log(f"✅ Xong: tạo {made} video AI.")
    return made


# ── Khớp video với độ dài giọng ──────────────────────────────────────────────
def _ff(*args: str) -> None:
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("FFmpeg lỗi: " + r.stderr.strip()[-400:])


def fit(clip: Path, frames: int, fps: int, size: tuple[int, int], out: Path) -> None:
    """Làm chậm ×1.5, nội suy lên `fps`, đổi kích thước rồi chạy xuôi–ngược (ping-pong) để đủ `frames` khung."""
    w, h = size
    tag = f"{clip.stem}-{w}x{h}-{fps}"
    base = out.parent / f"vbase-{tag}.mp4"
    pp = out.parent / f"vpp-{tag}.mp4"
    if not base.exists():
        vf = (f"setpts=1.5*PTS,minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
              f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,format=yuv420p")
        _ff("-i", str(clip), "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", str(base))
    if not pp.exists():
        _ff("-i", str(base), "-filter_complex", "[0:v]split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1[v]",
            "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", str(pp))
    _ff("-stream_loop", "-1", "-i", str(pp), "-frames:v", str(frames), "-r", str(fps), "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(out))
