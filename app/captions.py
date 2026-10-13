"""Phụ đề cháy sẵn vào video: hiện từng cụm ngắn, từ đang đọc được tô sáng dần (kiểu karaoke).

Thời gian từng từ được ước lượng theo độ dài chữ và dấu câu trong khoảng giọng thật sự vang lên
(bỏ phần im lặng ở đầu/cuối cảnh), vì OmniVoice không trả về mốc thời gian từng từ.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import numpy as np

from .tts import SR

CAPTION_CHOICES = [("Tắt", "off"), ("Phía dưới", "bottom"), ("Giữa khung", "middle")]
FONT = "Noto Sans"
MAX_CHARS = 20      # số ký tự tối đa mỗi cụm hiện trên màn hình
MAX_TOKENS = 6
_END = re.compile(r"[.!?…]$")
_PAUSE = re.compile(r"[,;:–—]$")


def speech_window(pcm: np.ndarray, gap: float) -> tuple[float, float]:
    """Khoảng (bắt đầu, kết thúc) giây của giọng nói thật trong một cảnh."""
    dur = len(pcm) / SR
    x = np.abs(pcm.astype(np.float32)) / 32768.0
    if len(x) == 0 or float(x.max()) < 1e-4:
        return 0.0, max(dur - gap, 0.1)
    idx = np.flatnonzero(x > max(0.02, 0.06 * float(x.max())))
    if len(idx) == 0:
        return 0.0, max(dur - gap, 0.1)
    return max(idx[0] / SR - 0.03, 0.0), min(idx[-1] / SR + 0.05, dur)


def _weight(tok: str) -> float:
    core = re.sub(r"[^\w]", "", tok)
    w = max(len(core), 1) + 0.6
    if _END.search(tok):
        w += 5.0
    elif _PAUSE.search(tok):
        w += 2.5
    return w


def word_times(text: str, t0: float, t1: float) -> list[tuple[str, float, float]]:
    """[(từ, bắt đầu, kết thúc)] chia đều theo trọng số trong [t0, t1]."""
    toks = text.split()
    if not toks:
        return []
    ws = [_weight(t) for t in toks]
    total = sum(ws)
    out, t = [], t0
    for tok, w in zip(toks, ws):
        d = (t1 - t0) * w / total
        out.append((tok, t, t + d))
        t += d
    return out


def chunks(words: list[tuple[str, float, float]]) -> list[list[tuple[str, float, float]]]:
    """Gom từ thành cụm ngắn, ngắt ở dấu câu."""
    res, cur, chars = [], [], 0
    for w in words:
        tok = w[0]
        if cur and (chars + 1 + len(tok) > MAX_CHARS or len(cur) >= MAX_TOKENS):
            res.append(cur)
            cur, chars = [], 0
        cur.append(w)
        chars += len(tok) + (1 if len(cur) > 1 else 0)
        if _END.search(tok) or _PAUSE.search(tok):
            res.append(cur)
            cur, chars = [], 0
    if cur:
        res.append(cur)
    return res


def _t(sec: float) -> str:
    cs = int(round(sec * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


def _bgr(hex_color: str) -> str:
    h = (hex_color or "#FFD84D").lstrip("#")
    if len(h) != 6:
        h = "FFD84D"
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def _escape(s: str) -> str:
    return s.replace("\\", "").replace("{", "(").replace("}", ")")


def build_ass(scenes: list[dict], starts: list[float], windows: list[tuple[float, float]],
              size: tuple[int, int], position: str, accent: str) -> str:
    w, h = size
    fs = round(w * 0.07)
    outline = max(2, round(w * 0.0065))
    if position == "middle":
        align, margin_v = 5, 0
    else:
        align, margin_v = 2, round(h * 0.2)
    header = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {w}\nPlayResY: {h}\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Cap,{FONT},{fs},{_bgr(accent)},&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,"
        f"{outline},{max(1, outline // 2)},{align},{round(w * 0.05)},{round(w * 0.05)},{margin_v},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = []
    for sc, t0, (ws, we) in zip(scenes, starts, windows):
        words = word_times(sc["voice"], t0 + ws, t0 + we)
        groups = chunks(words)
        for gi, g in enumerate(groups):
            start = g[0][1]
            end = g[-1][2]
            if gi + 1 < len(groups):  # nối liền với cụm sau nếu khoảng nghỉ ngắn để chữ không nhấp nháy
                nxt = groups[gi + 1][0][1]
                if nxt - end < 0.35:
                    end = nxt
            else:
                end += 0.15
            parts = []
            for tok, a, b in g:
                parts.append("{\\kf%d}%s " % (max(int(round((b - a) * 100)), 1), _escape(tok)))
            text = "{\\fad(70,50)}" + "".join(parts).rstrip()
            lines.append(f"Dialogue: 0,{_t(start)},{_t(end)},Cap,,0,0,0,,{text}")
    return header + "\n".join(lines) + "\n"


def _filter_path(p: Path) -> str:
    s = p.as_posix().replace("\\", "/")
    return s.replace(":", r"\:").replace("'", r"\'").replace(",", r"\,").replace("[", r"\[").replace("]", r"\]")


def burn(video_in: Path, ass: Path, out: Path, extra_in: list[str] | None = None, extra_out: list[str] | None = None) -> None:
    """Cháy phụ đề vào hình (mã hoá lại phần hình, giữ nguyên/ghép âm thanh theo extra_*)."""
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video_in), *(extra_in or [])]
    cmd += ["-vf", f"ass={_filter_path(ass)}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
            "-pix_fmt", "yuv420p", *(extra_out or []), "-movflags", "+faststart", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("FFmpeg lỗi khi chèn phụ đề: " + r.stderr.strip()[-400:])
