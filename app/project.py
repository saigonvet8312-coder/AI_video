"""Quản lý dự án: thư mục, cài đặt, lưu/đọc kịch bản, băm nội dung để cache."""
from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path

ROOT = Path(os.environ.get("AVG_PROJECTS_DIR", "/content/projects"))

DEFAULT_SETTINGS = {
    "brand": "Kênh của tôi",
    "tagline": "Nội dung mới mỗi ngày",
    "url": "",
    "auto_images": True,
    "theme": "aurora",
    "custom_colors": False,
    "accent_from": "#F59E0B",
    "accent_to": "#A855F7",
    "quality": "fast",
    "continuous": False,
    "anim_seconds": 3.0,
    "speed": 1.0,
    "seed": 1234,
    "normalize": True,
    "voice": "",
    "ref_text": "",
    "gap": 0.25,
    "outro_hold": 2.0,
    "bgm": "calm",
    "bgm_volume": 0.18,
    "sfx": True,
    "captions": "off",
    "video_ai": False,
    "video_frames": 25,
    "video_motion": 110,
    "style_preset": "cosmic",
    "style_note": "",
}

# Khung thiết kế luôn là 1080x1920; "scale" chỉ đổi độ phân giải xuất ra.
QUALITY = {
    "fast": {"scale": 2 / 3, "fps": 24, "size": (720, 1280)},
    "standard": {"scale": 1.0, "fps": 30, "size": (1080, 1920)},
}


class UserError(Exception):
    """Lỗi do người dùng nhập thiếu/sai — hiển thị thẳng lên giao diện."""


def slugify(name: str, limit: int = 48) -> str:
    s = (name or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:limit].strip("-") or "du-an"


def project_dir(name: str) -> Path:
    p = ROOT / slugify(name)
    for sub in ("voice", "clips"):
        (p / sub).mkdir(parents=True, exist_ok=True)
    return p


def list_projects() -> list[str]:
    if not ROOT.exists():
        return []
    return sorted(d.name for d in ROOT.iterdir() if (d / "project.json").exists())


def load_project(name: str) -> dict:
    f = project_dir(name) / "project.json"
    data = {"scenes": [], "settings": {}}
    if f.exists():
        data.update(json.loads(f.read_text(encoding="utf-8")))
    data["settings"] = {**DEFAULT_SETTINGS, **data.get("settings", {})}
    return data


def save_project(name: str, scenes: list[dict], settings: dict) -> None:
    f = project_dir(name) / "project.json"
    f.write_text(
        json.dumps({"scenes": scenes, "settings": settings}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def digest(*parts) -> str:
    raw = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def remove_stale(folder: Path, pattern: str, keep: Path) -> None:
    for f in folder.glob(pattern):
        if f != keep:
            try:
                f.unlink()
            except OSError:
                pass
