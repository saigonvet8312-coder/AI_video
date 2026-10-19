"""Tự viết mô tả CHỦ THỂ ảnh nền (tiếng Anh) cho từng cảnh từ lời đọc tiếng Việt."""
from __future__ import annotations

import gc
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from .director import DEFAULT_MODEL
from .project import UserError, digest
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


# ── Mô hình ngôn ngữ nhỏ chạy ngay trên Colab: viết thẳng prompt tiếng Anh, không cần API key ──────────────
LOCAL_MODEL = os.environ.get("AVG_LOCAL_LLM", "Qwen/Qwen2.5-3B-Instruct")  # đặt "off" để tắt
LOCAL_SYSTEM = (
    "You are a storyboard artist for a vertical 9:16 short video. For the scene you are given (Vietnamese narration), "
    "write ONE English image prompt of 15-30 words: concrete subject + action or state + setting + shot type "
    "(close-up, wide shot, top-down, macro, low angle...). Rules: depict what the narration literally says; use a metaphor "
    "only for abstract ideas such as emotions or concepts. Numbers or specs become related objects, never text, numbers, "
    "logos or interface. No celebrity names, no brands. Do not mention art style, lighting or colors (the style is fixed: "
    "{style_name}). Keep one consistent visual thread across the whole video. Output ONLY the English prompt on one line, no quotes."
)
LOCAL_REWRITE_SYSTEM = (
    "Rewrite the user's Vietnamese image description as ONE English image prompt of 15-30 words: concrete subject, action, "
    "setting, shot type. No text, numbers or logos in the image, no celebrity names or brands. Output ONLY the English prompt on one line."
)
_SHOTS = ["wide shot", "close-up", "low angle", "top-down view", "macro detail", "medium shot"]


def _one_line(text: str) -> str | None:
    """Lấy dòng prompt từ câu trả lời của mô hình; không hợp lệ (còn tiếng Việt, quá ngắn) thì trả None."""
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    if not lines:
        return None
    t = re.sub(r"^(english\s+)?(image\s+)?prompt\s*:\s*", "", lines[0], flags=re.I).strip(" \"'`")
    t = clean_prompt(t)
    return t if len(t.split()) >= 4 and not needs_english(t) else None


def _local_generate(pairs: list[tuple[str, str]], log=print, max_new_tokens: int = 80) -> list[str | None]:
    """Chạy mô hình ngôn ngữ trên GPU của Colab cho từng cặp (system, user). Giải phóng VRAM sau khi xong."""
    if LOCAL_MODEL.strip().lower() in ("", "off", "0", "false"):
        raise RuntimeError("đã tắt bằng AVG_LOCAL_LLM")
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("không có GPU")
    try:
        import transformers  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "transformers", "accelerate"], check=True)
    from transformers import AutoModelForCausalLM, AutoTokenizer

    log(f"🧠 Đang tải mô hình viết prompt chạy trên Colab ({LOCAL_MODEL}, lần đầu mất vài phút)...")
    tok = AutoTokenizer.from_pretrained(LOCAL_MODEL)
    model = AutoModelForCausalLM.from_pretrained(LOCAL_MODEL, torch_dtype=torch.float16, low_cpu_mem_usage=True).to("cuda")
    out: list[str | None] = []
    try:
        for k, (system, user) in enumerate(pairs, 1):
            msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            enc = tok(text, return_tensors="pt").to("cuda")
            with torch.no_grad():
                gen = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False, repetition_penalty=1.05)
            out.append(_one_line(tok.decode(gen[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)))
            if k % 5 == 0 or k == len(pairs):
                log(f"   ✍️ đã viết {k}/{len(pairs)} prompt")
    finally:
        del model
        gc.collect()
        torch.cuda.empty_cache()
    return out


def _local_scenes(voices: list[str], style: dict, log=print) -> list[str | None]:
    n = len(voices)
    topic = " ".join(v.strip() for v in voices[:3])[:500]
    system = LOCAL_SYSTEM.format(style_name=style["style_name"])
    pairs = [(system, f"Video topic (Vietnamese): {topic}\nScene {i}/{n} narration (Vietnamese): {v.strip()}\n"
                      f"Suggested shot type: {_SHOTS[(i - 1) % len(_SHOTS)]}\nEnglish image prompt:")
             for i, v in enumerate(voices, 1)]
    return _local_generate(pairs, log)



# ── Dịch tự động có giãn cách (Google giới hạn ~5 yêu cầu/giây) ──────────────────
_RETRY_WAITS = (2, 6, 15)   # giây chờ giữa các lần thử lại
_GAP = 0.4                  # giây nghỉ giữa hai yêu cầu


def _sleep(sec: float) -> None:
    time.sleep(sec)


def _translate_one(text: str) -> str:
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "deep-translator"], check=True)
        from deep_translator import GoogleTranslator
    return GoogleTranslator(source="vi", target="en").translate(text)


def _translate_backup(text: str) -> str:
    """Dịch dự phòng bằng MyMemory (miễn phí, giới hạn theo ngày) khi Google từ chối."""
    from deep_translator import MyMemoryTranslator

    return MyMemoryTranslator(source="vietnamese", target="english").translate(text)


def _translate_throttled(texts: list[str], log=print, on_item=None) -> list[str | None]:
    """Dịch từng câu, nghỉ giữa các yêu cầu và thử lại khi bị giới hạn. Câu không dịch được trả về None."""
    out: list[str | None] = []
    for k, text in enumerate(texts):
        if k:
            _sleep(_GAP)
        res = None
        for attempt, wait in enumerate((0,) + _RETRY_WAITS):
            if wait:
                log(f"⏳ Dịch bị giới hạn tốc độ, chờ {wait}s rồi thử lại ({attempt}/{len(_RETRY_WAITS)})...")
                _sleep(wait)
            try:
                res = _translate_one(text)
                break
            except Exception:  # noqa: BLE001
                res = None
        if not res:
            try:
                res = _translate_backup(text)
            except Exception:  # noqa: BLE001
                res = None
        out.append(res.strip() if res else None)
        if res and on_item:
            on_item(k, out[-1])
    return out



def _translate(voices: list[str], log) -> list[str]:
    firsts = [" ".join((sentences(v)[0] if sentences(v) else v).split()[:24]) for v in voices]
    outs = _translate_throttled(firsts, log)
    bad = sum(1 for o in outs if not o)
    if bad:
        log(f"⚠️ Không dịch được {bad}/{len(voices)} cảnh; các cảnh đó dùng tạm tiêu đề tiếng Việt (sẽ được dịch lại khi tạo ảnh).")
    return [f"cinematic illustration of the idea: {o}, no text, no letters" if o else short_title(v, 14)
            for v, o in zip(voices, outs)]


def generate(voices: list[str], style: dict, api_key: str = "", model: str = "", log=print, client=None) -> list[str]:
    """Viết prompt tiếng Anh cho từng cảnh: Claude (nếu có key) → mô hình chạy trên Colab → dịch tự động."""
    if client is not None or (api_key or "").strip():
        try:
            log("🪄 Đang nhờ Claude viết mô tả chủ thể ảnh cho từng cảnh...")
            return _claude(voices, style, api_key, model, client)
        except Exception as e:  # noqa: BLE001
            log(f"⚠️ Không dùng được Claude ({e}); chuyển sang mô hình chạy trên Colab.")
    else:
        log("ℹ️ Chưa có Anthropic API key: dùng mô hình viết prompt chạy ngay trên Colab (không cần key).")
    try:
        outs = _local_scenes(voices, style, log)
    except Exception as e:  # noqa: BLE001
        log(f"⚠️ Không chạy được mô hình trên Colab ({e}); chuyển sang dịch tự động.")
        return _translate(voices, log)
    bad = [i for i, o in enumerate(outs) if not o]
    if bad:  # chỉ dịch tự động riêng những cảnh mô hình viết chưa đạt
        log(f"ℹ️ {len(bad)} cảnh chưa đạt, dùng dịch tự động cho các cảnh đó.")
        fixed = _translate([voices[i] for i in bad], log)
        for i, f in zip(bad, fixed):
            outs[i] = f
    return outs


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
            def save_item(k, en):  # lưu ngay từng câu để lần sau chạy tiếp được
                cache[digest(todo[k])] = clean_prompt(en)
                cache_f.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

            outs = [None] * len(todo)
            try:
                log(f"🧠 Đang viết lại {len(todo)} prompt tiếng Việt thành tiếng Anh bằng mô hình chạy trên Colab...")
                outs = _local_generate([(LOCAL_REWRITE_SYSTEM, t) for t in cleaned], log)
            except Exception as e:  # noqa: BLE001
                log(f"ℹ️ Mô hình trên Colab không dùng được ({e}); dùng dịch tự động.")
            for k, o in enumerate(outs):
                if o:
                    save_item(k, o)
            pending = [k for k, o in enumerate(outs) if not o]
            if pending:
                log(f"🌐 Đang dịch tự động {len(pending)} prompt (mỗi câu cách nhau vài phần giây)...")
                res = _translate_throttled([cleaned[k] for k in pending], log,
                                           on_item=lambda j, en: save_item(pending[j], en))
                for k, r in zip(pending, res):
                    outs[k] = r
            failed = sum(1 for o in outs if not o)
            if failed:
                raise UserError(
                    f"Chưa viết được {failed}/{len(todo)} prompt sang tiếng Anh (dịch tự động đang bị giới hạn tốc độ). "
                    "Các câu đã xong được lưu lại. Hãy đợi 1–2 phút rồi bấm tạo ảnh lại, "
                    "hoặc nhập Anthropic API key ở tab ① để Claude viết ngay."
                )
        else:
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
