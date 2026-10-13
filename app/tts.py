"""Tạo giọng đọc từng cảnh bằng OmniVoice (có cache theo nội dung)."""
from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np

from . import vnnum
from .project import UserError, digest, remove_stale

SR = 24000
_model = None


# ── WAV helpers (mono, 16-bit, 24 kHz) ────────────────────────────────────────
def write_wav(path: Path, pcm: np.ndarray) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.astype(np.int16).tobytes())


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(round(seconds * SR)), dtype=np.int16)


# ── Giọng mẫu ─────────────────────────────────────────────────────────────────
def ref_path(pdir: Path) -> Path | None:
    p = pdir / "ref.wav"
    return p if p.exists() else None


def use_reference(pdir: Path, wav: Path, key: str) -> None:
    """Đặt giọng mẫu của dự án từ thư viện. Chỉ chép lại khi giọng thay đổi (giữ cache ổn định)."""
    out, keyfile = pdir / "ref.wav", pdir / "ref.key"
    if out.exists() and keyfile.exists() and keyfile.read_text() == key:
        return
    shutil.copyfile(wav, out)
    keyfile.write_text(key)


def clear_reference(pdir: Path) -> None:
    (pdir / "ref.wav").unlink(missing_ok=True)
    (pdir / "ref.key").unlink(missing_ok=True)


def _ref_fingerprint(pdir: Path) -> str:
    p = ref_path(pdir)
    return f"{p.stat().st_size}-{int(p.stat().st_mtime)}" if p else "none"


# ── Đường dẫn + cache ─────────────────────────────────────────────────────────
def spoken_text(scene: dict, st: dict) -> str:
    return vnnum.speakable(scene["voice"], numbers=bool(st["normalize"]))


def voice_path(pdir: Path, i: int, scene: dict, st: dict) -> Path:
    key = digest(spoken_text(scene, st), st["speed"], st["seed"], st["ref_text"], st["gap"], _ref_fingerprint(pdir))
    return pdir / "voice" / f"scene-{i:02d}-{key}.wav"


def voice_info(pdir: Path, i: int, scene: dict, st: dict):
    p = voice_path(pdir, i, scene, st)
    return (p, wav_duration(p)) if p.exists() else None


# ── Mô hình ───────────────────────────────────────────────────────────────────
def _get_model(log):
    global _model
    if _model is None:
        log("⏳ Đang tải mô hình OmniVoice (lần đầu mất vài phút)...")
        import torch
        from omnivoice import OmniVoice

        cuda = torch.cuda.is_available()
        if not cuda:
            log("⚠️ Không có GPU — sẽ rất chậm. Bật Runtime → T4 GPU.")
        _model = OmniVoice.from_pretrained(
            "k2-fsa/OmniVoice",
            device_map="cuda:0" if cuda else "cpu",
            dtype=torch.float16 if cuda else torch.float32,
        )
        log("✅ Mô hình đã sẵn sàng.")
    return _model


def _apply_speed(pcm: np.ndarray, speed: float, tmp: Path) -> np.ndarray:
    if abs(speed - 1.0) < 0.01:
        return pcm
    src, dst = tmp.with_suffix(".src.wav"), tmp.with_suffix(".dst.wav")
    write_wav(src, pcm)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-filter:a", f"atempo={speed:.3f}", str(dst)],
        check=True,
    )
    out = read_wav(dst)
    src.unlink(missing_ok=True)
    dst.unlink(missing_ok=True)
    return out


def synthesize_all(pdir: Path, scenes: list[dict], st: dict, force: bool = False,
                   only: list[int] | None = None, log=print) -> dict:
    """Tạo giọng cho các cảnh còn thiếu. Trả về {chỉ_số: (đường_dẫn, thời_lượng)}."""
    ref = ref_path(pdir)
    if ref is None:
        log("⚠️ Chưa có giọng mẫu: mỗi cảnh có thể ra một giọng hơi khác nhau.")
    result, made = {}, 0
    for i, sc in enumerate(scenes):
        if only is not None and i not in only:
            continue
        path = voice_path(pdir, i, sc, st)
        if path.exists() and not force:
            result[i] = (path, wav_duration(path))
            log(f"• Cảnh {i + 1}: dùng lại giọng đã có ({result[i][1]:.1f}s)")
            continue

        import torch

        model = _get_model(log)
        kw = {"text": spoken_text(sc, st)}
        if ref:
            kw["ref_audio"] = str(ref)
            if st["ref_text"].strip():
                kw["ref_text"] = st["ref_text"].strip()
        log(f"🎙️ Cảnh {i + 1}/{len(scenes)}: đang tạo giọng...")
        torch.manual_seed(int(st["seed"]))
        audio = model.generate(**kw)
        a = audio[0]
        if hasattr(a, "detach"):
            a = a.detach().cpu().numpy()
        wav = np.clip(np.squeeze(np.asarray(a, dtype=np.float32)), -1.0, 1.0)
        pcm = (wav * 32767).astype(np.int16)
        pcm = _apply_speed(pcm, float(st["speed"]), path)
        pcm = np.concatenate([pcm, silence(float(st["gap"]))])
        write_wav(path, pcm)
        remove_stale(path.parent, f"scene-{i:02d}-*.wav", path)
        result[i] = (path, wav_duration(path))
        made += 1
        log(f"   ✓ {result[i][1]:.1f}s")
    log(f"✅ Xong giọng đọc: tạo mới {made}, dùng lại {len(result) - made}.")
    return result
