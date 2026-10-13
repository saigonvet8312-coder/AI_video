"""Âm thanh phụ: nhạc nền (tự tổng hợp hoặc file của bạn), hiệu ứng chuyển cảnh, tự hạ nhạc khi có giọng đọc.

Mọi âm thanh được tạo bằng numpy nên không cần tải nhạc và không vướng bản quyền.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np

from .project import UserError
from .tts import SR

BGM_CHOICES = [
    ("Tắt", "off"),
    ("Êm dịu (nền hợp âm nhẹ)", "calm"),
    ("Trầm tối (kiểu điện ảnh)", "dark"),
    ("Dùng file nhạc của tôi", "file"),
]
USER_MUSIC_STEM = "bgm-user"

# Hợp âm theo số nốt MIDI. Mỗi bộ: (danh sách hợp âm, giây mỗi hợp âm, các hoạ âm (hệ số))
_MOODS = {
    "calm": {
        "chords": [[45, 52, 57, 60, 64], [41, 48, 53, 57, 60], [48, 55, 60, 64, 67], [43, 50, 55, 59, 62]],
        "seg": 6.0,
        "harm": (1.0, 0.35, 0.15, 0.06),
    },
    "dark": {
        "chords": [[38, 45, 50, 53], [34, 41, 46, 50], [43, 50, 55, 58], [33, 40, 45, 49]],
        "seg": 8.0,
        "harm": (1.0, 0.55, 0.35, 0.2),
    },
}
_XFADE = 1.6  # giây chồng lấn giữa hai hợp âm


def _midi_hz(n: int) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def _chord(notes: list[int], seconds: float, harm: tuple, rng: np.random.Generator) -> np.ndarray:
    n = int(seconds * SR)
    t = np.arange(n, dtype=np.float64) / SR
    out = np.zeros(n)
    for m in notes:
        f0 = _midi_hz(m)
        trem = 1.0 + 0.22 * np.sin(2 * np.pi * rng.uniform(0.08, 0.28) * t + rng.uniform(0, 6.28))
        for cents in (-4.0, 4.0):  # hai dây lệch nhẹ cho âm dày
            f = f0 * 2 ** (cents / 1200)
            ph = rng.uniform(0, 6.28)
            for k, a in enumerate(harm, start=1):
                out += a * trem * np.sin(2 * np.pi * f * k * t + ph * k)
    return out


def make_bgm(mood: str, seconds: float, seed: int = 7) -> np.ndarray:
    """Nhạc nền dài đúng `seconds` giây, biên độ đỉnh khoảng 0.9 (float32, mono, SR)."""
    spec = _MOODS[mood]
    rng = np.random.default_rng(seed)
    total = int(seconds * SR)
    seg = spec["seg"]
    out = np.zeros(total + int((seg + _XFADE) * SR) + 1)
    pos, k = 0.0, 0
    while pos < seconds + 0.1:
        notes = spec["chords"][k % len(spec["chords"])]
        wave = _chord(notes, seg + _XFADE, spec["harm"], rng)
        env = np.ones(len(wave))
        xf = int(_XFADE * SR)
        ramp = np.sin(np.linspace(0, np.pi / 2, xf)) ** 2
        env[:xf] = ramp
        env[-xf:] = ramp[::-1]
        i0 = int(pos * SR)
        out[i0:i0 + len(wave)] += wave * env
        pos += seg
        k += 1
    out = out[:total]
    peak = float(np.max(np.abs(out))) or 1.0
    return (out / peak * 0.9).astype(np.float32)


def load_user_music(path: Path, seconds: float) -> np.ndarray:
    """Đọc file nhạc bất kỳ (mp3/wav/m4a...), lặp lại nếu ngắn, cắt nếu dài."""
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
        capture_output=True,
    )
    if r.returncode != 0 or not r.stdout:
        raise UserError("Không đọc được file nhạc nền: " + r.stderr.decode(errors="ignore")[-200:])
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    need = int(seconds * SR)
    if len(x) < need:
        x = np.tile(x, need // max(len(x), 1) + 1)
    x = x[:need]
    peak = float(np.max(np.abs(x))) or 1.0
    return (x / peak * 0.9).astype(np.float32)


def stash_user_music(pdir: Path, file) -> Path | None:
    """Chép file nhạc người dùng tải lên vào thư mục dự án. Trả về đường dẫn (hoặc file đã có trước đó)."""
    if file:
        src = Path(getattr(file, "name", file))
        for old in pdir.glob(USER_MUSIC_STEM + ".*"):
            old.unlink(missing_ok=True)
        dst = pdir / (USER_MUSIC_STEM + (src.suffix.lower() or ".mp3"))
        shutil.copyfile(src, dst)
        return dst
    found = sorted(pdir.glob(USER_MUSIC_STEM + ".*"))
    return found[0] if found else None


# ── Hiệu ứng ─────────────────────────────────────────────────────────────────
def whoosh(seconds: float = 0.5, seed: int = 3) -> np.ndarray:
    """Tiếng vút: nhiễu lọc thấp, tần số cắt tăng dần, đỉnh ở khoảng 70% độ dài."""
    n = int(seconds * SR)
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n)
    u = np.linspace(0, 1, n)
    a = 0.01 + 0.55 * u ** 2  # hệ số bộ lọc một cực: càng về cuối càng sáng
    y = np.empty(n)
    prev = 0.0
    for i in range(n):
        prev += a[i] * (x[i] - prev)
        y[i] = prev
    rise = np.sin(np.pi / 2 * np.clip(u / _WHOOSH_PEAK, 0, 1)) ** 2
    fall = np.cos(np.pi / 2 * np.clip((u - _WHOOSH_PEAK) / (1 - _WHOOSH_PEAK), 0, 1)) ** 2
    env = np.where(u < _WHOOSH_PEAK, rise, fall)
    y = y * env
    return (y / (float(np.max(np.abs(y))) or 1.0)).astype(np.float32)


def thump(seconds: float = 0.45) -> np.ndarray:
    """Tiếng 'bụp' trầm: sin tụt tần số nhanh, tắt dần."""
    n = int(seconds * SR)
    t = np.arange(n) / SR
    f = 45 + 95 * np.exp(-t * 14)
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph) * np.exp(-t * 7.5)
    return (y / (float(np.max(np.abs(y))) or 1.0)).astype(np.float32)


_WHOOSH_PEAK = 0.7  # đỉnh tiếng vút nằm ở 70% độ dài → đặt đỉnh đúng điểm cắt cảnh


# ── Trộn ──────────────────────────────────────────────────────────────────────
def speech_gain(voice: np.ndarray, depth: float, rate: int = 100) -> np.ndarray:
    """Đường hệ số (0..1) để hạ nhạc khi có người nói. Vào nhanh (~80ms), nhả chậm (~450ms)."""
    hop = SR // rate
    nfr = len(voice) // hop + 1
    pad = np.zeros(nfr * hop)
    pad[:len(voice)] = voice
    frames = pad.reshape(nfr, hop)
    rms = np.sqrt(np.mean(frames ** 2, axis=1))
    ref = float(np.percentile(rms, 95)) or 1.0
    active = np.clip(rms / (0.25 * ref), 0.0, 1.0)  # >25% mức nói to = đang nói
    att, rel = np.exp(-1 / (0.08 * rate)), np.exp(-1 / (0.45 * rate))
    sm = np.empty(nfr)
    cur = 0.0
    for i, a in enumerate(active):
        coef = att if a > cur else rel
        cur = coef * cur + (1 - coef) * a
        sm[i] = cur
    gain = 1.0 - depth * sm
    return np.interp(np.arange(len(voice)) / hop, np.arange(nfr), gain).astype(np.float32)


def mix(voice_pcm: np.ndarray, total: float, cuts: list[tuple[float, str]], st: dict, pdir: Path) -> np.ndarray:
    """Trộn giọng + nhạc nền (tự hạ khi nói) + hiệu ứng. Trả về int16.

    `cuts`: danh sách (giây, mẫu cảnh) tại các điểm vào cảnh mới (không gồm cảnh đầu).
    """
    voice = voice_pcm.astype(np.float32) / 32768.0
    n = len(voice)
    out = voice.copy()
    mood = st.get("bgm", "off")
    if mood != "off":
        vol = float(st.get("bgm_volume", 0.18))
        if mood == "file":
            path = next(iter(sorted(pdir.glob(USER_MUSIC_STEM + ".*"))), None)
            if path is None:
                raise UserError("Chưa có file nhạc nền: hãy tải file lên ở tab ④ hoặc chọn kiểu nhạc khác.")
            bgm = load_user_music(path, n / SR)
        else:
            bgm = make_bgm(mood, n / SR)
        bgm = bgm[:n]
        fade_in, fade_out = int(1.0 * SR), int(min(2.5, total * 0.4) * SR)
        env = np.ones(len(bgm), dtype=np.float32)
        env[:fade_in] = np.linspace(0, 1, min(fade_in, len(env)), dtype=np.float32)[:len(env)]
        env[-fade_out:] *= np.linspace(1, 0, min(fade_out, len(env)), dtype=np.float32)
        out[:len(bgm)] += bgm * env * speech_gain(voice, depth=0.6)[:len(bgm)] * vol
    if st.get("sfx", True):
        w = whoosh()
        th = thump()
        for t, template in cuts:
            i0 = int((t - _WHOOSH_PEAK * len(w) / SR) * SR)
            _place(out, w, i0, 0.22)
            if template in ("stat", "outro"):
                _place(out, th, int(t * SR), 0.35)
    peak = float(np.max(np.abs(out))) or 1.0
    if peak > 0.97:
        out *= 0.97 / peak
    return (out * 32767).astype(np.int16)


def _place(dst: np.ndarray, clip: np.ndarray, start: int, gain: float) -> None:
    a, b = max(start, 0), min(start + len(clip), len(dst))
    if b > a:
        dst[a:b] += clip[a - start:b - start] * gain
