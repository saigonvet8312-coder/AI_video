"""Tự điền mô tả ảnh nền cho các cảnh còn trống khi đã có JSON phong cách (có nhớ để không đổi giữa các lần chạy)."""
from __future__ import annotations

import json
from pathlib import Path

from . import media, subjects
from .project import digest


def eligible(scene: dict) -> bool:
    return not scene["bg"].strip() and scene["template"] != "outro"


def _cache_file(pdir: Path) -> Path:
    return pdir / "bg_cache.json"


def _load(pdir: Path) -> dict:
    f = _cache_file(pdir)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def fill(pdir: Path, scenes: list[dict], st: dict, api_key: str = "", model: str = "", log=print) -> int:
    """Điền scene['bg'] cho cảnh còn trống. Trả về số cảnh được điền."""
    if not st.get("auto_images"):
        return 0
    style = media.parse_style(st.get("style_json"))
    if style is None:
        return 0
    need = [i for i, sc in enumerate(scenes) if eligible(sc)]
    if not need:
        return 0
    key = lambda sc: digest(sc["voice"].strip(), style["style_name"])  # noqa: E731
    cache = _load(pdir)
    missing = [i for i in need if key(scenes[i]) not in cache]
    if missing:
        outs = subjects.generate([scenes[i]["voice"] for i in missing], style, api_key, model, log=log)
        for i, subject in zip(missing, outs):
            cache[key(scenes[i])] = subject
        _cache_file(pdir).write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    for i in need:
        scenes[i]["bg"] = cache[key(scenes[i])]
    return len(need)
