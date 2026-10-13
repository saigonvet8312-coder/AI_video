"""Tách kịch bản thành cảnh, điền tự động các ô trống, kiểm tra hợp lệ."""
from __future__ import annotations

import re

from .project import UserError

TEMPLATES = {
    "hero": "Mở đầu — tiêu đề lớn",
    "stat": "Một con số nổi bật (số tự chạy lên)",
    "statement": "Câu nhận định, chữ hiện từng từ, từ khoá được tô sáng",
    "list": "Danh sách 1–5 mục",
    "quote": "Trích dẫn / câu nói",
    "compare": "So sánh 2 vế (Danh sách: 2 mục, Phụ đề: nhãn “Trước | Sau”)",
    "image": "Ảnh nền toàn khung, chữ nằm phía dưới",
    "outro": "Kết video — tên kênh, khẩu hiệu, liên kết",
}
FIELDS = ["template", "kicker", "headline", "sub", "items", "bg", "voice"]
HEADERS = ["Mẫu", "Nhãn", "Tiêu đề", "Phụ đề", "Danh sách", "Ảnh nền", "Lời đọc"]
MAX_SCENES = 40

_BULLET = re.compile(r"^\s*(?:[-•*–]|\d+[.)])\s+")
_NUMBER = re.compile(r"\d[\d.,]*\s?(?:%|[A-Za-z]{1,4}\b)?")


def _words(s: str) -> int:
    return len(s.split())


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text.strip()) if s.strip()]


def short_title(voice: str, max_words: int = 9) -> str:
    first = sentences(voice)[0] if sentences(voice) else voice
    first = first.strip().rstrip(".!?…:;,")
    w = first.split()
    return " ".join(w[:max_words]) + ("…" if len(w) > max_words else "")


def _pack(text: str, max_words: int) -> list[str]:
    chunks, cur = [], []
    for s in sentences(text):
        if cur and _words(" ".join(cur + [s])) > max_words:
            chunks.append(" ".join(cur))
            cur = []
        cur.append(s)
    if cur:
        chunks.append(" ".join(cur))
    return chunks


_QUOTED = re.compile(r"[“\"«](.{12,}?)[”\"»]")


def blank_scene() -> dict:
    return {"template": "", "kicker": "", "headline": "", "sub": "", "items": [], "bg": "", "voice": ""}


def split_script(text: str, brand: str = "", add_outro: bool = True, max_words: int = 38) -> list[dict]:
    paras = [p for p in re.split(r"\n\s*\n", (text or "").strip()) if p.strip()]
    scenes: list[dict] = []
    for p in paras:
        lines = [l for l in p.splitlines() if l.strip()]
        if len(lines) >= 2 and all(_BULLET.match(l) for l in lines):
            items = [_BULLET.sub("", l).strip() for l in lines][:5]
            s = blank_scene()
            s.update(template="list", items=items, voice=". ".join(items) + ".")
            scenes.append(s)
            continue
        flat = " ".join(p.split())
        pieces = [flat] if _words(flat) <= max_words * 1.3 else _pack(flat, max_words)
        for piece in pieces:
            s = blank_scene()
            s["voice"] = piece
            scenes.append(s)
    if add_outro and scenes:
        s = blank_scene()
        s.update(template="outro", voice=f"Theo dõi {brand or 'kênh'} để xem thêm nội dung mới mỗi ngày.")
        scenes.append(s)
    return scenes[:MAX_SCENES]


def _auto_template(s: dict, i: int, n: int, prev: str | None, prev2: str | None) -> str:
    voice = s["voice"].strip()
    if i == 0:
        return "hero"
    if i == n - 1 and n > 1:
        return "outro"
    if s["items"]:
        return "list"
    if _QUOTED.search(voice):
        t = "quote"
    elif s["bg"]:
        t = "image"
    elif _NUMBER.search(voice) and _words(voice) <= 24 and prev != "stat":
        t = "stat"
    else:
        t = "statement"
    if t == prev == prev2:  # tránh lặp 3 lần liền nhau
        t = "image" if t != "image" else "statement"
    return t


def complete_scene(s: dict, i: int, n: int, prev: str | None = None, prev2: str | None = None) -> dict:
    s = {**blank_scene(), **s}
    s["items"] = [x.strip() for x in (s["items"] or []) if str(x).strip()]
    s["headline"] = s["headline"].replace("|", "\n").strip()
    s["bg"] = (s["bg"] or "").strip()
    s["n"] = i + 1
    s["fx"] = ["rise", "left", "zoom", "blur"][i % 4]
    t = (s["template"] or "").strip().lower() or _auto_template(s, i, n, prev, prev2)
    s["template"] = t
    voice = s["voice"].strip()
    if t == "hero":
        s["kicker"] = s["kicker"] or "Nổi bật"
        s["headline"] = s["headline"] or short_title(voice, 8)
    elif t == "stat":
        if not s["headline"]:
            m = _NUMBER.search(voice)
            if m:
                s["headline"] = m.group(0).strip()
                s["sub"] = s["sub"] or short_title(voice, 10)
            else:
                s["template"] = "statement"
                s["headline"] = short_title(voice, 14)
    elif t in ("statement", "image"):
        s["headline"] = s["headline"] or short_title(voice, 14 if t == "statement" else 12)
    elif t == "quote":
        if not s["headline"]:
            m = _QUOTED.search(voice)
            s["headline"] = (m.group(1) if m else voice)[:220].strip()
    elif t == "list":
        s["headline"] = s["headline"] or "Điểm chính"
    return s


def complete_all(scenes: list[dict]) -> list[dict]:
    n, out = len(scenes), []
    for i, s in enumerate(scenes):
        prev = out[-1]["template"] if out else None
        prev2 = out[-2]["template"] if len(out) > 1 else None
        out.append(complete_scene(s, i, n, prev, prev2))
    return out


def validate(scenes: list[dict]) -> list[str]:
    errs = []
    if not scenes:
        errs.append("Chưa có cảnh nào. Hãy dán kịch bản rồi bấm “Tách thành các cảnh”.")
    if len(scenes) > MAX_SCENES:
        errs.append(f"Tối đa {MAX_SCENES} cảnh.")
    for i, s in enumerate(scenes, 1):
        if not s["voice"].strip():
            errs.append(f"Cảnh {i}: thiếu lời đọc.")
        if s["template"] not in TEMPLATES:
            errs.append(f"Cảnh {i}: mẫu “{s['template']}” không có. Dùng: {', '.join(TEMPLATES)}.")
        if s["template"] == "list" and not (1 <= len(s["items"]) <= 5):
            errs.append(f"Cảnh {i}: mẫu list cần 1–5 mục (ngăn cách bằng dấu |).")
        if s["template"] == "compare" and len(s["items"]) != 2:
            errs.append(f"Cảnh {i}: mẫu compare cần đúng 2 mục (ngăn cách bằng dấu |).")
    return errs


def rows_to_scenes(rows) -> list[dict]:
    scenes = []
    for row in rows or []:
        cells = [("" if c is None else str(c)).strip() for c in list(row)[: len(FIELDS)]]
        cells += [""] * (len(FIELDS) - len(cells))
        d = dict(zip(FIELDS, cells))
        if not any(d.values()):
            continue
        d["items"] = [x.strip() for x in d["items"].split("|") if x.strip()]
        d["headline"] = d["headline"].replace("|", "\n")
        scenes.append(d)
    return scenes


def scenes_to_rows(scenes: list[dict]) -> list[list[str]]:
    rows = []
    for s in scenes:
        s = {**blank_scene(), **s}
        rows.append([
            s["template"], s["kicker"], s["headline"].replace("\n", "|"),
            s["sub"], " | ".join(s["items"]), s["bg"], s["voice"],
        ])
    return rows or [[""] * len(FIELDS)]


def require_valid(scenes: list[dict]) -> None:
    errs = validate(scenes)
    if errs:
        raise UserError("\n".join(errs))
