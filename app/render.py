"""Dựng hình từng cảnh: HTML động → ảnh từng khung (Chromium) → MP4 (FFmpeg)."""
from __future__ import annotations

import base64
import math
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from . import aivideo, media
from .project import QUALITY, UserError, digest, remove_stale
from .templates import TEMPLATE_VERSION, build_html

PREVIEW_SECONDS = 4.0
STALL_SECONDS = 60      # quá lâu không có khung hình mới ⇒ coi là đứng, tự mở lại trình duyệt
MAX_ATTEMPTS = 3
_VISUAL_KEYS = ("template", "kicker", "headline", "sub", "items", "bg", "fx")
_STYLE_KEYS = ("brand", "tagline", "url", "theme", "custom_colors", "continuous")


def anim_seconds_for(st: dict, duration: float | None, photo: bool = False) -> float:
    """Độ dài đoạn hoạt hình. Cố định (không phụ thuộc giọng) trừ khi cảnh có ảnh nền
    (chuyển động máy quay suốt cảnh) hoặc bật chuyển động liên tục — khi đó làm tròn lên theo giây."""
    if (st["continuous"] or photo) and duration:
        return float(math.ceil(duration))
    return round(float(st["anim_seconds"]), 1)


def anim_path(pdir: Path, i: int, scene: dict, st: dict, anim_sec: float) -> Path:
    colors = (st["accent_from"], st["accent_to"]) if st.get("custom_colors") else ()
    key = digest(
        TEMPLATE_VERSION,
        {k: scene.get(k) for k in _VISUAL_KEYS},
        {k: st.get(k) for k in _STYLE_KEYS},
        colors,
        st["quality"],
        anim_sec,
        media.bg_key(pdir, scene, st),
        scene.get("n") if st.get("theme") == "mono" else None,
    )
    return pdir / "clips" / f"anim-{i:02d}-{key}.mp4"


class _Watchdog:
    """Giám sát: nếu Chromium không tiến triển quá STALL_SECONDS thì tắt nó để lệnh đang treo báo lỗi."""

    def __init__(self, limit: float):
        self.limit = limit
        self.beat = time.monotonic()
        self.fired = False
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._t.start()

    def ping(self):
        self.beat = time.monotonic()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.wait(2.0):
            if time.monotonic() - self.beat > self.limit:
                self.fired = True
                self.beat = time.monotonic()
                subprocess.run(["pkill", "-9", "-f", "chrome|chromium|headless_shell"], check=False)


class Renderer:
    """Mở Chromium một lần, dùng cho nhiều cảnh. Tự mở lại nếu bị đứng."""

    def __init__(self, quality: str):
        self.q = QUALITY[quality]
        self.dog = _Watchdog(STALL_SECONDS)

    def _launch(self):
        self._browser = self._pw.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = self._browser.new_context(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
        self.page = ctx.new_page()
        self._cdp = ctx.new_cdp_session(self.page)  # chụp qua CDP nhanh gần gấp đôi

    def restart(self):
        try:
            self._browser.close()
        except Exception:  # noqa: BLE001
            pass
        self.dog.ping()
        self._launch()

    def __enter__(self):
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._launch()
        self.dog.ping()
        self.dog.start()
        return self

    def __exit__(self, *exc):
        self.dog.stop()
        for obj in (getattr(self, "_browser", None), getattr(self, "_pw", None)):
            try:
                obj.close() if hasattr(obj, "close") else obj.stop()
            except Exception:  # noqa: BLE001
                pass

    def render(self, html: str, out: Path, anim_sec: float, log=print) -> int:
        fps = self.q["fps"]
        n = max(2, math.ceil(anim_sec * fps))
        page = self.page
        self.dog.ping()
        try:
            page.set_content(html, wait_until="load", timeout=20000)
        except Exception:  # noqa: BLE001  (font/mạng chậm: vẫn dựng tiếp với phông dự phòng)
            pass
        try:
            page.evaluate("Promise.race([document.fonts.ready.then(() => true), new Promise(r => setTimeout(r, 6000))])")
        except Exception:  # noqa: BLE001
            pass
        self.dog.ping()
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg",
            "-i", "pipe:0", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-r", str(fps), str(out),
        ]
        step = 48
        t0 = time.monotonic()
        with tempfile.TemporaryFile() as errf:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=errf)
            try:
                for k in range(n):
                    page.evaluate(
                        "t => { for (const a of document.getAnimations()) { a.pause(); a.currentTime = t; } }",
                        k * 1000.0 / fps,
                    )
                    shot = self._cdp.send(
                        "Page.captureScreenshot", {"format": "jpeg", "quality": 92, "optimizeForSpeed": True,
                         "clip": {"x": 0, "y": 0, "width": 1080, "height": 1920, "scale": self.q["scale"]}}
                    )
                    proc.stdin.write(base64.b64decode(shot["data"]))
                    self.dog.ping()
                    if (k + 1) % step == 0 and k + 1 < n:
                        rate = (k + 1) / max(time.monotonic() - t0, 0.01)
                        log(f"   … {k + 1}/{n} khung ({rate:.1f} khung/s, còn khoảng {int((n - k - 1) / max(rate, 0.01))}s)")
                proc.stdin.close()
            except Exception:
                try:
                    proc.kill()
                except Exception:  # noqa: BLE001
                    pass
                raise
            rc = proc.wait()
            if rc != 0:
                errf.seek(0)
                raise RuntimeError("FFmpeg lỗi khi mã hoá cảnh: " + errf.read().decode(errors="ignore")[-300:])
        return n


def render_scenes(pdir: Path, scenes: list[dict], st: dict, durations: dict[int, float] | None = None,
                  force: bool = False, only: list[int] | None = None, log=print) -> dict[int, Path]:
    durations = durations or {}
    out: dict[int, Path] = {}
    made = 0
    pending_ai = [i + 1 for i, sc in enumerate(scenes)
                  if (only is None or i in only) and media.classify(sc["bg"], pdir)[0] == "ai" and media.resolve(pdir, sc, st) is None]
    if pending_ai:
        raise UserError("Cảnh " + ", ".join(map(str, pending_ai)) + " cần ảnh AI: hãy bấm “Tạo ảnh AI” trước.")
    with Renderer(st["quality"]) as r:
        for i, sc in enumerate(scenes):
            if only is not None and i not in only:
                continue
            if aivideo.eligible(pdir, sc, st, download=True):
                log(f"🎬 Cảnh {i + 1}: dùng video AI, bỏ qua dựng hoạt hình")
                continue
            photo_path = media.resolve(pdir, sc, st)
            photo = photo_path is not None
            if (photo or st["continuous"]) and i not in durations:
                log(f"⏭️ Cảnh {i + 1}: cần có giọng trước (ảnh nền/chuyển động liên tục phụ thuộc thời lượng).")
                continue
            anim = anim_seconds_for(st, durations.get(i), photo)
            path = anim_path(pdir, i, sc, st, anim)
            out[i] = path
            if path.exists() and not force:
                log(f"• Cảnh {i + 1}: dùng lại hình đã có")
                continue
            log(f"🖼️ Cảnh {i + 1}/{len(scenes)} ({sc['template']}{' + ảnh nền' if photo else ''}): đang dựng {anim:.1f}s hoạt hình...")
            uri = media.data_uri(photo_path) if photo else None
            html = build_html(sc, st, uri)
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    n = r.render(html, path, anim, log=log)
                    break
                except Exception as e:  # noqa: BLE001
                    path.unlink(missing_ok=True)
                    if attempt == MAX_ATTEMPTS:
                        raise UserError(f"Cảnh {i + 1} dựng lỗi sau {MAX_ATTEMPTS} lần thử: {e}")
                    log(f"⚠️ Cảnh {i + 1} bị đứng/lỗi ({type(e).__name__}) — mở lại trình duyệt, thử lần {attempt + 1}/{MAX_ATTEMPTS}...")
                    r.restart()
            remove_stale(path.parent, f"anim-{i:02d}-*.mp4", path)
            made += 1
            log(f"   ✓ {n} khung hình")
    log(f"✅ Xong hình: dựng mới {made}, dùng lại {len(out) - made - 0}.")
    return out
