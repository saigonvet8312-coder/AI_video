"""Tự viết mô tả CHỦ THỂ ảnh nền (tiếng Anh) cho từng cảnh từ lời đọc tiếng Việt."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from .director import DEFAULT_MODEL
from .project import digest
from .scriptkit import sentences, short_title

SYSTEM = """Bạn là họa sĩ phân cảnh cho video dọc 9:16. Bạn nhận TOÀN BỘ kịch bản (mỗi dòng là lời đọc một cảnh, tiếng Việt). Với mỗi cảnh, viết MỘT mô tả CHỦ THỂ ảnh bằng TIẾNG ANH để AI vẽ.

Mỗi mô tả (15–30 từ) gồm: chủ thể cụ thể + hành động/trạng thái + bối cảnh + kiểu khung hình (close-up, wide shot, top-down, macro, low angle...).

QUY TẮC:
1. Vẽ ĐÚNG điều cảnh đang nói: nếu cảnh nhắc vật/người/nơi cụ thể (điện thoại, pin, con mèo, thành phố...) thì chính vật đó phải là chủ thể. Chỉ dùng ẩn dụ khi nội dung trừu tượng (cảm xúc, ý niệm).
2. Con số/thông số (6000 mAh, 200 MP...) → vẽ vật thể liên quan (viên pin đầy năng lượng, ống kính camera lớn), TUYỆT ĐỐI không đưa chữ, số, logo, giao diện có chữ vào ảnh.
3. Cả video phải có MỘT mạch hình ảnh nhất quán (cùng nhân vật/vật chủ đạo hoặc cùng thế giới), nhưng đổi kiểu khung hình giữa hai cảnh liền kề để không nhàm.
4. Không tên người nổi tiếng, không thương hiệu. Không lặp lại phong cách, ánh sáng, màu sắc: phong cách đã cố định ({style_name}: {style_hint}).
Chỉ trả về một mảng JSON các chuỗi, đúng số lượng và thứ tự cảnh, không giải thích."""


def _claude(voices: list[str], style: dict, api_key: str, model: str, client=None) -> list[str]:
    if client is None:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key.strip())
    system = SYSTEM.format(style_name=style["style_name"], style_hint=style["full_prompt_string"][:200])
    user = "\n".join(f"{i}. {v.strip()}" for i, v in enumerate(voices, 1))
    msgs = [{"role": "user", "content": user}]
    for _ in range(2):
        text = client.messages.create(model=model or DEFAULT_MODEL, max_tokens=4000, system=system,
                                      messages=msgs).content[0].text
        try:
            data = json.loads(text[text.index("["): text.rindex("]") + 1])
            if isinstance(data, list) and len(data) == len(voices) and all(isinstance(x, str) and x.strip() for x in data):
                return [x.strip() for x in data]
            err = f"cần đúng {len(voices)} chuỗi"
        except Exception as e:  # noqa: BLE001
            err = str(e)
        msgs += [{"role": "assistant", "content": text},
                 {"role": "user", "content": f"Lỗi: {err}. Chỉ trả về mảng JSON {len(voices)} chuỗi."}]
    raise ValueError("Claude chưa trả về danh sách hợp lệ")


def _translate(voices: list[str], log) -> list[str]:
    try:
        try:
            from deep_translator import GoogleTranslator
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "deep-translator"], check=True)
            from deep_translator import GoogleTranslator
        tr = GoogleTranslator(source="vi", target="en")
        out = []
        for v in voices:
            first = sentences(v)[0] if sentences(v) else v
            en = tr.translate(" ".join(first.split()[:24]))
            out.append(f"cinematic illustration of the idea: {en}, no text, no letters".strip())
        return out
    except Exception as e:  # noqa: BLE001
        log(f"⚠️ Không dịch tự động được ({e}); dùng nguyên văn tiếng Việt (ảnh có thể kém sát nội dung).")
        return [short_title(v, 14) for v in voices]


def generate(voices: list[str], style: dict, api_key: str = "", model: str = "", log=print, client=None) -> list[str]:
    if client is not None or (api_key or "").strip():
        try:
            log("🪄 Đang nhờ Claude viết mô tả chủ thể ảnh cho từng cảnh...")
            return _claude(voices, style, api_key, model, client)
        except Exception as e:  # noqa: BLE001
            log(f"⚠️ Không dùng được Claude ({e}); chuyển sang dịch tự động.")
    else:
        log("ℹ️ Chưa có Anthropic API key: dùng dịch tự động để mô tả ảnh (nhập key ở tab ① để ảnh sát nội dung hơn).")
    return _translate(voices, log)


# ── Đưa prompt về tiếng Anh sạch cho mô hình ảnh ──────────────────────────────
_NON_ASCII_LETTER = re.compile(r"[^\x00-\x7F]")
_JUNK = re.compile(r"[^\w\s,.'\-()/:;!?&%+]", re.UNICODE)


def needs_english(text: str) -> bool:
    """Có chữ có dấu (tiếng Việt, v.v.)? Mô hình ảnh chỉ hiểu tốt tiếng Anh."""
    return bool(_NON_ASCII_LETTER.search(_JUNK.sub("", text or "")))


def clean_prompt(text: str) -> str:
    """Bỏ emoji, ký hiệu và định dạng (*, |, 📌...) để không làm nhiễu prompt."""
    t = (text or "").replace("|", ", ").replace("*", "")
    t = _JUNK.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip(" ,;")


def _claude_translate(texts: list[str], api_key: str, model: str, client=None) -> list[str]:
    if client is None:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key.strip())
    system = ("Dịch từng dòng (tiếng Việt) thành MỘT mô tả hình ảnh ngắn bằng tiếng Anh (15–30 từ) để AI vẽ: chủ thể cụ thể, "
              "hành động, bối cảnh. Không đưa chữ/số/logo vào ảnh, không tên người nổi tiếng. "
              "Chỉ trả về một mảng JSON các chuỗi, đúng số lượng và thứ tự.")
    msg = client.messages.create(model=model or DEFAULT_MODEL, max_tokens=4000, system=system,
                                 messages=[{"role": "user", "content": "\n".join(f"{i}. {t}" for i, t in enumerate(texts, 1))}])
    raw = "".join(getattr(b, "text", "") for b in msg.content).strip()
    raw = raw[raw.index("["): raw.rindex("]") + 1]
    out = json.loads(raw)
    if len(out) != len(texts):
        raise ValueError("số mô tả không khớp")
    return [str(x).strip() for x in out]


def _google_translate(texts: list[str]) -> list[str]:
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "deep-translator"], check=True)
        from deep_translator import GoogleTranslator
    tr = GoogleTranslator(source="vi", target="en")
    return [tr.translate(" ".join(t.split()[:60])) for t in texts]


def english_for(pdir: Path, prompts: list[str], api_key: str = "", model: str = "", log=print, client=None) -> list[str]:
    """Prompt tiếng Anh sạch cho từng cảnh (dịch nếu cần, có nhớ kết quả trong dự án)."""
    cache_f = Path(pdir) / "prompt_en.json"
    cache = json.loads(cache_f.read_text(encoding="utf-8")) if cache_f.exists() else {}
    todo = [p for p in dict.fromkeys(prompts) if needs_english(clean_prompt(p)) and digest(p) not in cache]
    if todo:
        cleaned = [clean_prompt(p) for p in todo]
        outs = None
        if client is not None or (api_key or "").strip():
            try:
                log(f"🌐 Claude đang dịch {len(todo)} prompt tiếng Việt sang tiếng Anh cho mô hình ảnh...")
                outs = _claude_translate(cleaned, api_key, model, client)
            except Exception as e:  # noqa: BLE001
                log(f"⚠️ Không dùng được Claude để dịch ({e}); chuyển sang dịch tự động.")
        if outs is None:
            try:
                log(f"🌐 Đang dịch {len(todo)} prompt tiếng Việt sang tiếng Anh cho mô hình ảnh...")
                outs = _google_translate(cleaned)
            except Exception as e:  # noqa: BLE001
                log(f"⚠️ Không dịch được ({e}); dùng nguyên văn, ảnh có thể kém sát nội dung.")
                outs = cleaned
            else:
                pass
        for p, o in zip(todo, outs):
            cache[digest(p)] = clean_prompt(o)
        cache_f.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return [cache.get(digest(p), clean_prompt(p)) if needs_english(clean_prompt(p)) else clean_prompt(p) for p in prompts]


def suggest_note(voices: list[str], style_name: str, default_note: str, api_key: str = "", model: str = "", client=None) -> str:
    """Gợi ý ghi chú phong cách (tiếng Anh) hợp tâm trạng kịch bản; không có Claude thì dùng gợi ý mặc định của kiểu."""
    if client is None and not (api_key or "").strip():
        return default_note
    try:
        if client is None:
            from anthropic import Anthropic

            client = Anthropic(api_key=api_key.strip())
        system = (f"Phong cách ảnh đã chọn: {style_name}. Đọc kịch bản và đề xuất 4–8 từ khoá tiếng Anh, cách nhau bằng dấu phẩy, "
                  "về ÁNH SÁNG, KHÔNG KHÍ, MÀU SẮC, GÓC MÁY hợp tâm trạng kịch bản. Không nêu vật thể/chủ thể, không chữ/số. "
                  "Chỉ trả về các từ khoá, không giải thích.")
        text = "\n".join(v.strip() for v in voices[:14])[:3000]
        msg = client.messages.create(model=model or DEFAULT_MODEL, max_tokens=120, system=system,
                                     messages=[{"role": "user", "content": text}])
        out = "".join(getattr(b, "text", "") for b in msg.content).strip().strip(".")
        return clean_prompt(out) or default_note
    except Exception:  # noqa: BLE001
        return default_note
