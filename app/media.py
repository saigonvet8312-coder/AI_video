"""Ảnh nền cho cảnh: ảnh tải lên, đường link, hoặc ảnh do AI tạo theo mô tả."""
from __future__ import annotations

import base64
import io
import json
import os
import re
import shutil
from pathlib import Path

from .project import UserError, digest

IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")
AI_MODEL = os.environ.get("AVG_AI_MODEL", "segmind/SSD-1B")
AI_SIZE = (576, 1024)


def media_dir(pdir: Path) -> Path:
    d = pdir / "media"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_media(pdir: Path) -> list[Path]:
    return sorted(p for p in media_dir(pdir).iterdir() if p.suffix.lower() in IMG_EXT and not p.name.startswith("ai-"))


def save_uploads(pdir: Path, files) -> list[str]:
    saved = []
    for f in files or []:
        src = Path(getattr(f, "name", f))
        dst = media_dir(pdir) / re.sub(r"[^\w.\-]+", "_", src.name)
        if src.resolve() != dst.resolve():
            shutil.copy(src, dst)
        saved.append(dst.name)
    return saved


NEGATIVE_BASE = "text, letters, watermark, logo, signature, blurry, low quality, deformed, extra limbs, cropped"
STYLE_FIELDS = ("full_prompt_string", "composition", "lighting", "color_palette", "negative_prompt")


def parse_style(text: str | None) -> dict | None:
    """Đọc JSON phong cách ảnh do người dùng cung cấp. Trả None nếu để trống."""
    t = (text or "").strip()
    if not t:
        return None
    try:
        data = json.loads(t)
    except json.JSONDecodeError as e:
        raise UserError(f"JSON phong cách chưa hợp lệ: {e.msg} (dòng {e.lineno}, cột {e.colno}).")
    if isinstance(data, list) and data and isinstance(data[0], dict):
        data = data[0]
    if not isinstance(data, dict) or not str(data.get("full_prompt_string", "")).strip():
        raise UserError("JSON phong cách cần có trường \"full_prompt_string\".")
    style = {k: str(data.get(k, "") or "").strip() for k in STYLE_FIELDS}
    style["style_name"] = str(data.get("style_name", "") or "").strip() or "phong cách riêng"
    return style


def require_style(st: dict) -> dict:
    style = parse_style(st.get("style_json"))
    if style is None:
        raise UserError("Chưa có JSON phong cách ảnh. Hãy dán JSON ở tab ③ → “Phong cách ảnh AI” trước khi tạo ảnh AI.")
    return style


def ai_prompts(subject: str, style: dict) -> tuple[str, str, str]:
    """(prompt chính, prompt phụ cho bộ mã hoá thứ hai của SDXL, negative). Chủ thể luôn đứng đầu."""
    subject = subject.strip()
    p1 = ", ".join(x for x in (subject, style["full_prompt_string"]) if x)
    p2 = ", ".join(x for x in (subject, style["composition"], style["lighting"], style["color_palette"]) if x)
    neg = ", ".join(x for x in (style["negative_prompt"], NEGATIVE_BASE) if x)
    return p1, p2, neg


def _style_fp(st: dict) -> str:
    raw = (st.get("style_json") or "").strip()
    try:
        return json.dumps(json.loads(raw), sort_keys=True, ensure_ascii=False) if raw else ""
    except json.JSONDecodeError:
        return raw


def ai_path(pdir: Path, prompt: str, st: dict) -> Path:
    # Phụ thuộc mô tả + JSON phong cách (đổi phong cách ⇒ tạo ảnh mới), không phụ thuộc chủ đề giao diện.
    key = digest(prompt.strip(), _style_fp(st), AI_MODEL, AI_SIZE, st.get("seed"))
    return media_dir(pdir) / f"ai-{key}.png"


def classify(value: str, pdir: Path):
    """Trả về (loại, nội dung): none | url | file | missing | ai."""
    v = (value or "").strip()
    if not v:
        return "none", None
    if re.match(r"https?://", v, re.I):
        return "url", v
    for p in media_dir(pdir).iterdir():
        if p.name.lower() == v.lower() and p.suffix.lower() in IMG_EXT:
            return "file", p
    if re.fullmatch(r"\S+\.(jpe?g|png|webp|gif)", v, re.I):
        return "missing", v
    return "ai", v


def _url_path(pdir: Path, url: str) -> Path:
    return media_dir(pdir) / f"url-{digest(url)}.img"


def fetch_url(pdir: Path, url: str) -> Path:
    dst = _url_path(pdir, url)
    if dst.exists():
        return dst
    import requests

    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        raise UserError(f"Không tải được ảnh từ link: {url} ({e})")
    if "image" not in r.headers.get("content-type", "image"):
        raise UserError(f"Link không phải ảnh: {url}")
    dst.write_bytes(r.content)
    return dst


def resolve(pdir: Path, scene: dict, st: dict, download: bool = True) -> Path | None:
    kind, payload = classify(scene.get("bg", ""), pdir)
    if kind == "none":
        return None
    if kind == "file":
        return payload
    if kind == "url":
        return fetch_url(pdir, payload) if download else (_url_path(pdir, payload) if _url_path(pdir, payload).exists() else None)
    if kind == "ai":
        p = ai_path(pdir, payload, st)
        return p if p.exists() else None
    raise UserError(f"Không thấy ảnh “{payload}” trong thư viện ảnh của dự án.")


def has_bg(pdir: Path, scene: dict) -> bool:
    return classify(scene.get("bg", ""), pdir)[0] != "none"


def bg_key(pdir: Path, scene: dict, st: dict) -> str:
    """Dấu vân tay của ảnh nền, dùng để biết khi nào phải dựng lại cảnh."""
    kind, payload = classify(scene.get("bg", ""), pdir)
    if kind == "none":
        return ""
    p = None
    if kind == "file":
        p = payload
    elif kind == "url":
        p = _url_path(pdir, payload)
    elif kind == "ai":
        p = ai_path(pdir, payload, st)
    size = p.stat().st_size if p is not None and p.exists() else 0
    return f"{kind}:{scene['bg']}:{size}"


def data_uri(path: Path, max_w: int = 1200, max_h: int = 2100) -> str:
    try:
        from PIL import Image

        im = Image.open(path).convert("RGB")
        im.thumbnail((max_w, max_h))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=88)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()
