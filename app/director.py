"""“Đạo diễn AI”: Claude đọc kịch bản rồi chọn chủ đề, mẫu cảnh, chữ trên màn hình và mô tả ảnh nền."""
from __future__ import annotations

import json

from .project import UserError
from .scriptkit import TEMPLATES, complete_all
from .templates import THEMES

DEFAULT_MODEL = "claude-sonnet-5-5"

SYSTEM = """Bạn là đạo diễn hình ảnh cho video dọc 9:16 (TikTok/Shorts/Reels) bằng tiếng Việt.
Nhiệm vụ: đọc các cảnh (mỗi cảnh có lời đọc) rồi thiết kế phần hình cho từng cảnh sao cho video có CHỦ ĐỀ NHẤT QUÁN, nhịp điệu đa dạng, không nhàm chán.

CHỦ ĐỀ (chọn đúng 1 cho cả video, hợp nội dung):
{themes}

MẪU CẢNH (template) và cách điền:
- hero: cảnh mở đầu. headline ≤ 28 ký tự (dùng | để xuống dòng), kicker ngắn 1–3 từ, sub 1 dòng.
- stat: chỉ khi có con số thật. headline = số kèm đơn vị ngắn (vd 200MP, 85%, 12 triệu), sub giải thích ≤ 60 ký tự.
- statement: câu nhận định. headline ≤ 90 ký tự, đặt *từ khoá* trong dấu * để tô sáng (1–2 từ).
- list: 2–5 mục ngắn (≤ 28 ký tự), mỗi mục có thể mở đầu bằng 1 emoji. headline ≤ 22 ký tự.
- quote: câu trích/nhận định đáng nhớ. headline ≤ 120 ký tự, sub = nguồn/tác giả (nếu có).
- compare: so sánh 2 vế. items đúng 2 mục (≤ 50 ký tự), sub = "Nhãn A | Nhãn B", headline = tiêu đề ngắn.
- image: cảnh ảnh nền toàn khung, chữ nằm phía dưới. headline ≤ 50 ký tự. BẮT BUỘC có bg.
- outro: cảnh cuối. Để trống các trường (hệ thống tự điền tên kênh).

QUY TẮC:
- Cảnh đầu là hero, cảnh cuối là outro. Không dùng cùng một mẫu quá 2 cảnh liên tiếp.
- Chữ trên màn hình KHÔNG lặp nguyên văn lời đọc: rút gọn thành ý chính, mạnh và dễ đọc lướt.
- bg: mô tả ảnh nền bằng TIẾNG ANH, 12–25 từ, hình ảnh cụ thể/ẩn dụ gắn với nội dung cảnh, KHÔNG chứa chữ/logo/người nổi tiếng. {bg_rule}
- Không sửa lời đọc.

CHỈ TRẢ VỀ MỘT ĐỐI TƯỢNG JSON, không markdown, không giải thích:
{{"theme": "<id chủ đề>", "scenes": [{{"template": "...", "kicker": "", "headline": "", "sub": "", "items": [], "bg": ""}}, ...]}}
Số phần tử trong "scenes" PHẢI bằng số cảnh đầu vào, đúng thứ tự."""


def build_system(use_ai_images: bool, style: dict | None = None) -> str:
    themes = "\n".join(f"- {k}: {v['label']}" for k, v in THEMES.items())
    rule = ("Đặt bg cho khoảng một nửa số cảnh (hero và mọi cảnh image luôn có); các cảnh khác để trống."
            if use_ai_images else "Để bg trống ở mọi cảnh.")
    if use_ai_images and style:
        rule += (f" PHONG CÁCH ẢNH ĐÃ ĐƯỢC CỐ ĐỊNH ({style['style_name']}: {style['full_prompt_string'][:240]}). "
                 "Vì vậy bg CHỈ mô tả CHỦ THỂ/hình ảnh chính của cảnh (không lặp lại phong cách, ánh sáng, màu sắc).")
    return SYSTEM.format(themes=themes, bg_rule=rule)


def build_user(scenes: list[dict], topic: str, brand: str) -> str:
    lines = [f"Thương hiệu: {brand}", f"Chủ đề / phong cách mong muốn: {topic.strip() or '(để bạn tự quyết định theo nội dung)'}",
             f"Số cảnh: {len(scenes)}", "", "Các cảnh:"]
    for i, s in enumerate(scenes, 1):
        lines.append(f"{i}. {s['voice'].strip()}")
    return "\n".join(lines)


def parse(text: str, n: int) -> tuple[str, list[dict]]:
    try:
        data = json.loads(text[text.index("{"): text.rindex("}") + 1])
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"không phải JSON hợp lệ ({e})")
    theme = data.get("theme")
    if theme not in THEMES:
        raise ValueError(f"theme phải là một trong: {', '.join(THEMES)}")
    sc = data.get("scenes")
    if not isinstance(sc, list) or len(sc) != n:
        raise ValueError(f"cần đúng {n} cảnh, nhận được {len(sc) if isinstance(sc, list) else 'không có'}")
    out = []
    for i, s in enumerate(sc, 1):
        if not isinstance(s, dict):
            raise ValueError(f"cảnh {i} không hợp lệ")
        t = str(s.get("template", "")).strip().lower()
        if t not in TEMPLATES:
            raise ValueError(f"cảnh {i}: template “{t}” không có")
        items = s.get("items") or []
        if not isinstance(items, list):
            raise ValueError(f"cảnh {i}: items phải là danh sách")
        items = [str(x).strip() for x in items if str(x).strip()]
        if t == "compare" and len(items) != 2:
            raise ValueError(f"cảnh {i}: compare cần đúng 2 mục")
        if t == "list" and not 1 <= len(items) <= 5:
            raise ValueError(f"cảnh {i}: list cần 1–5 mục")
        out.append({k: str(s.get(k) or "").strip() for k in ("kicker", "headline", "sub", "bg")} | {"template": t, "items": items})
    return theme, out


def direct(scenes: list[dict], api_key: str, model: str = DEFAULT_MODEL, topic: str = "",
           brand: str = "", use_ai_images: bool = True, style: dict | None = None, client=None, log=print) -> tuple[str, list[dict]]:
    """Trả về (chủ_đề, danh_sách_cảnh_đã_thiết_kế). Giữ nguyên lời đọc."""
    if not scenes or any(not s["voice"].strip() for s in scenes):
        raise UserError("Cần có lời đọc ở mọi cảnh trước khi nhờ đạo diễn AI.")
    if client is None:
        if not (api_key or "").strip():
            raise UserError("Hãy nhập Anthropic API key.")
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key.strip())
    system = build_system(use_ai_images, style)
    msgs = [{"role": "user", "content": build_user(scenes, topic, brand)}]
    last_err = ""
    for attempt in range(2):
        resp = client.messages.create(model=model or DEFAULT_MODEL, max_tokens=8000, system=system, messages=msgs)
        text = resp.content[0].text
        try:
            theme, designed = parse(text, len(scenes))
            break
        except ValueError as e:
            last_err = str(e)
            log(f"⚠️ Lần {attempt + 1} chưa hợp lệ: {last_err}")
            msgs += [{"role": "assistant", "content": text},
                     {"role": "user", "content": f"Lỗi: {last_err}. Hãy sửa và chỉ trả về JSON."}]
    else:
        raise UserError(f"Đạo diễn AI chưa trả về kết quả hợp lệ: {last_err}")
    merged = []
    for src, d in zip(scenes, designed):
        merged.append({**src, **d, "voice": src["voice"]})
    if not use_ai_images:
        for m, src in zip(merged, scenes):
            m["bg"] = src.get("bg", "")
    return theme, complete_all(merged)
