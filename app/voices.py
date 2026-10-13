"""Thư viện giọng đọc (lưu trên Google Drive): mỗi giọng là một file wav mẫu + lời của mẫu."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .project import UserError, slugify

ROOT = Path(os.environ.get("AVG_VOICES_DIR", "/content/voices"))
NO_VOICE = "(không dùng giọng mẫu)"
SR = 24000


def _ensure() -> Path:
    ROOT.mkdir(parents=True, exist_ok=True)
    return ROOT


def list_voices() -> list[dict]:
    out = []
    for meta in sorted(_ensure().glob("*.json")):
        wav = meta.with_suffix(".wav")
        if not wav.exists():
            continue
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        out.append({"name": data.get("name") or meta.stem, "ref_text": data.get("ref_text", ""), "path": wav})
    return out


def names() -> list[str]:
    return [NO_VOICE] + [v["name"] for v in list_voices()]


def get(name: str) -> dict:
    for v in list_voices():
        if v["name"] == name:
            return v
    raise UserError(f"Không thấy giọng “{name}” trong thư viện. Hãy chọn lại ở tab ②.")


def save(name: str, audio_path: str, ref_text: str = "") -> dict:
    name = (name or "").strip()
    if not name:
        raise UserError("Hãy đặt tên cho giọng.")
    if not audio_path:
        raise UserError("Hãy tải lên hoặc ghi âm một đoạn giọng mẫu (3–15 giây, rõ tiếng).")
    base = _ensure() / slugify(name)
    r = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(audio_path), "-t", "20", "-ac", "1", "-ar", str(SR),
         str(base.with_suffix(".wav"))],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise UserError("Không đọc được file âm thanh: " + r.stderr.strip()[-200:])
    base.with_suffix(".json").write_text(
        json.dumps({"name": name, "ref_text": (ref_text or "").strip()}, ensure_ascii=False, indent=2), encoding="utf-8")
    return get(name)


def delete(name: str) -> None:
    v = get(name)
    v["path"].unlink(missing_ok=True)
    v["path"].with_suffix(".json").unlink(missing_ok=True)
