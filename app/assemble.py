"""Ghép video cuối: khớp hình theo giọng, nối cảnh, trộn âm thanh, xuất phụ đề."""
from __future__ import annotations

import re
import subprocess
import zipfile
from pathlib import Path

import numpy as np

from . import aiimage, aivideo, audiofx, captions, media, render, tts
from .project import QUALITY, UserError, digest, remove_stale
from .scriptkit import sentences


def _ffmpeg(*args: str) -> None:
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("FFmpeg lỗi: " + r.stderr.strip()[-400:])


def _fit(anim: Path, frames: int, fps: int, out: Path) -> None:
    """Cắt/kéo dài clip hoạt hình đúng `frames` khung (giữ khung cuối nếu thiếu)."""
    _ffmpeg(
        "-i", str(anim), "-vf", "tpad=stop_mode=clone:stop_duration=120", "-frames:v", str(frames),
        "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(out),
    )


def _ts(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def make_srt(scenes: list[dict], starts: list[float], speech: list[float]) -> str:
    cues, n = [], 1
    for sc, t0, dur in zip(scenes, starts, speech):
        parts = sentences(sc["voice"]) or [sc["voice"]]
        total = sum(len(p) for p in parts) or 1
        t = t0
        for p in parts:
            d = dur * len(p) / total
            cues.append(f"{n}\n{_ts(t)} --> {_ts(t + d)}\n{p}\n")
            t += d
            n += 1
    return "\n".join(cues)


def _accent(st: dict) -> str:
    """Màu tô sáng từ đang đọc: màu nhấn của chủ đề (hoặc màu riêng của bạn)."""
    from .templates import THEMES

    if st.get("custom_colors"):
        return st.get("accent_from") or "#FFD84D"
    return THEMES.get(st.get("theme"), THEMES["aurora"])["a"]


def _collect(pdir: Path, scenes: list[dict], st: dict):
    voices, anims, missing = {}, {}, []
    for i, sc in enumerate(scenes):
        v = tts.voice_info(pdir, i, sc, st)
        if v is None:
            missing.append(f"giọng cảnh {i + 1}")
            continue
        voices[i] = v
        if aivideo.eligible(pdir, sc, st):
            a = aivideo.clip_path(pdir, sc, st)
            if not a.exists():
                missing.append(f"video AI cảnh {i + 1}")
            anims[i] = a
            continue
        photo = media.resolve(pdir, sc, st, download=False) is not None
        a = render.anim_path(pdir, i, sc, st, render.anim_seconds_for(st, v[1], photo))
        if not a.exists():
            missing.append(f"hình cảnh {i + 1}")
        anims[i] = a
    if missing:
        raise UserError("Chưa đủ nguyên liệu: " + ", ".join(missing) + ". Hãy chạy bước tương ứng trước.")
    return voices, anims


def assemble(pdir: Path, scenes: list[dict], st: dict, log=print) -> dict[str, Path]:
    fps = QUALITY[st["quality"]]["fps"]
    voices, anims = _collect(pdir, scenes, st)
    n = len(scenes)

    # Mốc thời gian (giây) và số khung hình tích luỹ để không lệch dần
    durs = [voices[i][1] for i in range(n)]
    hold = float(st["outro_hold"])
    starts, t = [], 0.0
    for d in durs:
        starts.append(t)
        t += d
    total = t + hold
    bounds = [round(s * fps) for s in starts] + [round(total * fps)]

    log("🎞️ Khớp hình theo giọng từng cảnh...")
    fits = []
    size = QUALITY[st["quality"]]["size"]
    vid = [aivideo.eligible(pdir, sc, st) for sc in scenes]
    for i in range(n):
        frames = max(1, bounds[i + 1] - bounds[i])
        out = pdir / "clips" / f"fit-{i:02d}-{digest(anims[i].name, frames, fps, size if vid[i] else '')}.mp4"
        if not out.exists():
            if vid[i]:
                log(f"🎬 Cảnh {i + 1}: làm mượt video AI cho vừa giọng đọc...")
                aivideo.fit(anims[i], frames, fps, size, out)
            else:
                _fit(anims[i], frames, fps, out)
            remove_stale(out.parent, f"fit-{i:02d}-*.mp4", out)
        fits.append(out)

    log("🔗 Nối các cảnh...")
    lst = pdir / "clips" / "concat.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in fits), encoding="utf-8")
    silent = pdir / "video-silent.mp4"
    _ffmpeg("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent))

    gap = float(st["gap"])
    log("🔊 Ghép giọng đọc...")
    pcms = [tts.read_wav(voices[i][0]) for i in range(n)]
    pcm = np.concatenate(pcms + [tts.silence(hold)])
    wav = pdir / "voice.wav"
    tts.write_wav(wav, pcm)
    mp3 = pdir / "voice.mp3"
    _ffmpeg("-i", str(wav), "-codec:a", "libmp3lame", "-q:a", "2", str(mp3))
    wav.unlink(missing_ok=True)

    audio_in = mp3
    if st.get("bgm", "off") != "off" or st.get("sfx", True):
        log("🎵 Trộn nhạc nền và hiệu ứng chuyển cảnh...")
        cuts = [(starts[i], scenes[i]["template"]) for i in range(1, n)]
        mixed = audiofx.mix(pcm, total, cuts, st, pdir)
        audio_in = pdir / "mix.wav"
        tts.write_wav(audio_in, mixed)

    video = pdir / "video.mp4"
    cap_mode = st.get("captions", "off")
    if cap_mode == "off" and any(vid):
        cap_mode = "bottom"
        log("💬 Cảnh video AI không có chữ trên hình nên tự bật phụ đề phía dưới.")
    if cap_mode != "off":
        log("💬 Chèn phụ đề từng từ vào video...")
        windows = [captions.speech_window(p, gap) for p in pcms]
        ass = pdir / "captions.ass"
        ass.write_text(captions.build_ass(scenes, starts, windows, size,
                                          cap_mode, _accent(st)), encoding="utf-8")
        captions.burn(silent, ass, video, extra_in=["-i", str(audio_in)],
                      extra_out=["-c:a", "aac", "-b:a", "192k", "-shortest"])
    else:
        _ffmpeg("-i", str(silent), "-i", str(audio_in), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", "-movflags", "+faststart", str(video))
    if audio_in != mp3:
        audio_in.unlink(missing_ok=True)

    (pdir / "script.txt").write_text("\n\n".join(s["voice"].strip() for s in scenes), encoding="utf-8")
    (pdir / "captions.srt").write_text(
        make_srt(scenes, starts, [max(d - gap, 0.1) for d in durs]), encoding="utf-8"
    )
    bundle = pdir / "ket-qua.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_STORED) as z:
        for f in (video, mp3, pdir / "script.txt", pdir / "captions.srt"):
            z.write(f, f.name)
    log(f"✅ Hoàn tất: {total:.1f}s · {video.stat().st_size / 1e6:.1f} MB — hãy tải về ngay (dự án không được lưu lại).")
    return {"video": video, "zip": bundle, "voice": mp3, "script": pdir / "script.txt", "srt": pdir / "captions.srt"}


def preview_scene(pdir: Path, i: int, scenes: list[dict], st: dict, log=print) -> Path:
    """Xem thử một cảnh (kèm giọng nếu đã có)."""
    fps = QUALITY[st["quality"]]["fps"]
    sc = scenes[i]
    v = tts.voice_info(pdir, i, sc, st)
    dur = v[1] if v else render.PREVIEW_SECONDS + 1.0
    photo = media.resolve(pdir, sc, st) is not None
    anim_sec = render.anim_seconds_for(st, dur, photo)
    render.render_scenes(pdir, scenes, st, {i: dur}, only=[i], log=log)
    anim = render.anim_path(pdir, i, sc, st, anim_sec)
    out = pdir / "preview.mp4"
    tmp = pdir / "preview-silent.mp4"
    _fit(anim, max(1, round(dur * fps)), fps, tmp)
    if v and st.get("captions", "off") != "off":
        pcm = tts.read_wav(v[0])
        win = captions.speech_window(pcm, float(st["gap"]))
        ass = pdir / "preview.ass"
        ass.write_text(captions.build_ass([sc], [0.0], [win], QUALITY[st["quality"]]["size"],
                                          st["captions"], _accent(st)), encoding="utf-8")
        captions.burn(tmp, ass, out, extra_in=["-i", str(v[0])], extra_out=["-c:a", "aac", "-shortest"])
    elif v:
        _ffmpeg("-i", str(tmp), "-i", str(v[0]), "-c:v", "copy", "-c:a", "aac", "-shortest", str(out))
    else:
        tmp.replace(out)
    tmp.unlink(missing_ok=True)
    return out


def run_all(pdir: Path, scenes: list[dict], st: dict, log=print) -> dict[str, Path]:
    voices = tts.synthesize_all(pdir, scenes, st, log=log)
    aiimage.generate_all(pdir, scenes, st, log=log)
    aivideo.generate_all(pdir, scenes, st, log=log)
    render.render_scenes(pdir, scenes, st, {i: d for i, (_, d) in voices.items()}, log=log)
    return assemble(pdir, scenes, st, log=log)
