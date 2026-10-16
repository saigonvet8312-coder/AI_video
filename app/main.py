"""Giao diện web (Gradio): kịch bản → giọng đọc → hình ảnh → xuất video."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

import gradio as gr

from . import aiimage, aivideo, assemble, audiofx, autobg, captions, director, media, render, scriptkit as K, subjects, tts, voices
from . import project as P
from . import ui_theme
from .jobs import run_job
from .project import UserError
from .templates import THEMES

# Khoá API chỉ giữ trong bộ nhớ phiên này, không bao giờ lưu vào dự án.

SETTING_KEYS = [
    "brand", "tagline", "url", "theme", "custom_colors", "accent_from", "accent_to", "quality",
    "continuous", "speed", "seed", "normalize", "voice", "auto_images",
    "bgm", "bgm_volume", "sfx", "captions", "video_ai", "video_frames", "video_motion",
    "style_preset", "style_note",
]


# ── Tiện ích dùng chung ───────────────────────────────────────────────────────
def merge_settings(vals) -> dict:
    st = {**P.DEFAULT_SETTINGS, **dict(zip(SETTING_KEYS, vals))}
    st["speed"] = float(st["speed"] or 1.0)
    st["seed"] = int(st["seed"] or 0)
    st["brand"] = (st["brand"] or "").strip() or P.DEFAULT_SETTINGS["brand"]
    st["voice"] = "" if st["voice"] in (None, voices.NO_VOICE) else st["voice"]
    st["ref_text"] = ""
    st["custom_colors"] = bool(st["custom_colors"])
    st["auto_images"] = bool(st["auto_images"])
    st["bgm"] = st["bgm"] if st["bgm"] in dict(audiofx.BGM_CHOICES).values() else "off"
    st["bgm_volume"] = min(max(float(st["bgm_volume"] or 0.0), 0.0), 0.5)
    st["sfx"] = bool(st["sfx"])
    st["captions"] = st["captions"] if st["captions"] in dict(captions.CAPTION_CHOICES).values() else "off"
    st["video_ai"] = bool(st["video_ai"])
    st["video_frames"] = 14 if int(st["video_frames"] or 25) <= 14 else 25
    st["video_motion"] = min(max(int(st["video_motion"] or 110), 20), 250)
    st["style_preset"] = st["style_preset"] if st["style_preset"] in media.STYLES else media.DEFAULT_STYLE_KEY
    st["style_note"] = str(st["style_note"] or "").strip()[:300]
    return st


def _sec(api_key="", model="", hf_token=""):
    """Khoá bí mật của MỘT yêu cầu (không lưu vào dự án, không dùng biến toàn cục nên không lẫn giữa các phiên)."""
    return {"api_key": (api_key or "").strip(), "model": (model or "").strip() or director.DEFAULT_MODEL,
            "hf_token": (hf_token or "").strip()}


def prepare(name: str, rows, vals, save: bool = True, auto: bool = False, log=print, keys: dict | None = None,
            refresh: bool = False):
    sec = keys or _sec()
    st = merge_settings(vals)
    scenes = K.complete_all(K.rows_to_scenes(rows))
    K.require_valid(scenes)
    pdir = P.project_dir(name)
    if st["voice"]:
        v = voices.get(st["voice"])
        stat = v["path"].stat()
        tts.use_reference(pdir, v["path"], f"{v['name']}-{stat.st_size}-{int(stat.st_mtime)}")
        st["ref_text"] = v["ref_text"]
    else:
        tts.clear_reference(pdir)
    if auto:
        autobg.fill(pdir, scenes, st, sec["api_key"], sec["model"], log=log, refresh=refresh)
    if save:
        P.save_project(name, scenes, st)
    # Chỉ dùng trong yêu cầu này, đặt SAU khi lưu nên không ghi ra file dự án
    st["_hf_token"], st["_api_key"], st["_model"] = sec["hf_token"], sec["api_key"], sec["model"]
    return pdir, scenes, st


# ── Dự án ─────────────────────────────────────────────────────────────────────
def open_project(name):
    data = P.load_project(name)
    st = data["settings"]
    rows = K.scenes_to_rows(data["scenes"])
    vals = [(st[k] or voices.NO_VOICE) if k == "voice" else st[k] for k in SETTING_KEYS]
    return [rows] + vals + [f"📂 Đã mở dự án **{P.slugify(name)}** (dự án chỉ lưu trong phiên Colab này — nhớ tải kết quả về)."]


def save_project(name, rows, *vals):
    try:
        prepare(name, rows, vals)
    except UserError as e:
        return f"⚠️ {e}"
    return f"💾 Đã lưu dự án **{P.slugify(name)}** (tạm thời trong phiên Colab)."


# ── ① Kịch bản ────────────────────────────────────────────────────────────────
def split_handler(text, add_outro, brand):
    if not (text or "").strip():
        raise gr.Error("Hãy dán kịch bản vào ô bên trên.")
    scenes = K.complete_all(K.split_script(text, brand=brand, add_outro=bool(add_outro)))
    return K.scenes_to_rows(scenes)


def fill_handler(rows):
    return K.scenes_to_rows(K.complete_all(K.rows_to_scenes(rows)))


def director_handler(rows, api_key, model, topic, use_ai, brand):
    scenes = K.rows_to_scenes(rows)
    try:
        style = media.get_style({})
        theme, designed = director.direct(
            scenes, api_key, model or director.DEFAULT_MODEL, topic or "", (brand or "").strip(), bool(use_ai), style)
    except UserError as e:
        raise gr.Error(str(e))
    except Exception as e:  # noqa: BLE001
        raise gr.Error(f"Đạo diễn AI gặp lỗi: {e}")
    label = render_theme_label(theme)
    return K.scenes_to_rows(designed), theme, f"✨ Đạo diễn AI đã thiết kế {len(designed)} cảnh · chủ đề **{label}**."


def render_theme_label(theme: str) -> str:
    from .templates import THEMES
    return THEMES.get(theme, {}).get("label", theme)


def voice_preview(name):
    if not name or name == voices.NO_VOICE:
        return None
    try:
        return str(voices.get(name)["path"])
    except UserError:
        return None


def voice_save(name, audio, ref_text):
    try:
        v = voices.save(name, audio, ref_text)
    except UserError as e:
        raise gr.Error(str(e))
    return gr.update(choices=voices.names(), value=v["name"]), f"💾 Đã lưu giọng **{v['name']}** vào `{voices.ROOT}`.", None, "", str(v["path"])


def voice_delete(name):
    if not name or name == voices.NO_VOICE:
        raise gr.Error("Hãy chọn một giọng để xoá.")
    try:
        voices.delete(name)
    except UserError as e:
        raise gr.Error(str(e))
    return gr.update(choices=voices.names(), value=voices.NO_VOICE), f"🗑️ Đã xoá giọng **{name}**.", None


def _job_ai(pdir, scenes, st, force, log):
    aiimage.generate_all(pdir, scenes, st, force=force, log=log)


def _job_video(pdir, scenes, st, force, log):
    aivideo.generate_all(pdir, scenes, st, force=force, log=log)


def video_handler(name, api_key, model, hf_token, force, rows, *vals):
    try:
        pdir, scenes, st = prepare(name, rows, vals, auto=True, keys=_sec(api_key, model, hf_token))
        if not st["video_ai"]:
            raise UserError("Hãy tick “Bật video AI” trước.")
    except UserError as e:
        yield f"⚠️ {e}"
        return
    for log, _res, _err in run_job(_job_video, pdir, scenes, st, bool(force)):
        yield log


def _ai_gallery(pdir, scenes, st):
    items = []
    for i, sc in enumerate(scenes):
        try:
            p = media.resolve(pdir, sc, st, download=False)
        except UserError:
            p = None
        if p is not None:
            items.append((str(p), f"Cảnh {i + 1}: {sc['bg'][:60]}"))
    return items


def ai_handler(name, api_key, model, force, rows, *vals):
    try:
        pdir, scenes, st = prepare(name, rows, vals, auto=True, keys=_sec(api_key, model))
    except UserError as e:
        yield f"⚠️ {e}", gr.update()
        return
    for log, _res, _err in run_job(_job_ai, pdir, scenes, st, bool(force)):
        yield log, gr.update()
    yield log, _ai_gallery(pdir, scenes, st)


COL_TPL, COL_BG, COL_VOICE = K.HEADERS.index("Mẫu"), K.HEADERS.index("Ảnh nền"), K.HEADERS.index("Lời đọc")
PROMPT_HEADERS = ["Cảnh", "Mẫu", "Lời đọc", "Prompt ảnh (sửa được)"]


def _nonblank(rows) -> list[tuple[int, list]]:
    return [(i, r) for i, r in enumerate(rows or []) if any(str(c).strip() for c in r)]


def _prompt_view(rows) -> list[list]:
    out = [[k + 1, str(r[COL_TPL]), str(r[COL_VOICE]), str(r[COL_BG])] for k, (_i, r) in enumerate(_nonblank(rows))]
    return out or [["", "", "", ""]]


def refresh_prompts(rows):
    """Nạp bảng prompt từ danh sách cảnh (bảng cảnh ở bước ① là nguồn dữ liệu chính)."""
    return _prompt_view(rows)


def sync_prompts(prompt_rows, rows):
    """Người dùng sửa prompt ở bước ③ → ghi ngược vào cột “Ảnh nền” của bảng cảnh."""
    target = _nonblank(rows)
    if not prompt_rows or len(prompt_rows) != len(target):
        return gr.update()
    new = [list(r) for r in rows]
    for k, (i, _r) in enumerate(target):
        new[i][COL_BG] = str(prompt_rows[k][3] or "").strip()
    return new


def prompts_handler(name, api_key, model, rewrite, rows, *vals):
    """Đọc lời đọc của từng cảnh và viết prompt hình ảnh; ghi vào bảng cảnh và bảng prompt."""
    rows = [list(r) for r in (rows or [])]
    if rewrite:  # xoá prompt cũ (trừ link ảnh) để viết lại từ đầu
        for _i, r in _nonblank(rows):
            if r[COL_TPL] != "outro" and not str(r[COL_BG]).strip().lower().startswith("http"):
                r[COL_BG] = ""
    vals = list(vals)
    vals[SETTING_KEYS.index("auto_images")] = True
    try:
        pdir, scenes, st = prepare(name, rows, vals, save=False, auto=True, keys=_sec(api_key, model), refresh=bool(rewrite))
    except UserError as e:
        raise gr.Error(str(e))
    out = K.scenes_to_rows(scenes)
    n = sum(1 for sc in scenes if sc["bg"].strip() and sc["template"] != "outro")
    return out, _prompt_view(out), f"✅ Đã có prompt cho {n} cảnh. Sửa trực tiếp trong bảng nếu muốn, rồi sang bước 2 để tạo ảnh."


def suggest_note_handler(api_key, model, preset, rows):
    voices = [str(r[COL_VOICE]).strip() for _i, r in _nonblank(rows) if str(r[COL_VOICE]).strip()]
    style = media.get_style({"style_preset": preset})
    return subjects.suggest_note(voices, style["style_name"], media.default_note(preset), (api_key or "").strip(),
                                 (model or "").strip() or director.DEFAULT_MODEL)


def scene_video_handler(name, idx, rows, *vals):
    try:
        pdir, scenes, st = prepare(name, rows, vals, save=False)
    except UserError as e:
        raise gr.Error(str(e))
    i = int(idx or 0) - 1
    if not 0 <= i < len(scenes):
        raise gr.Error(f"Chỉ có {len(scenes)} cảnh.")
    if not aivideo.eligible(pdir, scenes[i], st):
        raise gr.Error("Cảnh này không dùng video AI: cần bật video AI, mẫu hero/image/statement/quote và đã có ảnh.")
    clip = aivideo.clip_path(pdir, scenes[i], st)
    if not clip.exists():
        raise gr.Error("Chưa tạo video cho cảnh này. Hãy bấm “Tạo video AI” trước.")
    return str(clip)


# ── ② Giọng đọc ───────────────────────────────────────────────────────────────
def _job_tts(pdir, scenes, st, force, log):
    tts.synthesize_all(pdir, scenes, st, force=force, log=log)


def tts_handler(name, force, rows, *vals):
    try:
        pdir, scenes, st = prepare(name, rows, vals)
    except UserError as e:
        yield f"⚠️ {e}"
        return
    for log, _res, _err in run_job(_job_tts, pdir, scenes, st, bool(force)):
        yield log


def listen_handler(name, idx, rows, *vals):
    try:
        pdir, scenes, st = prepare(name, rows, vals, save=False)
    except UserError as e:
        raise gr.Error(str(e))
    i = int(idx) - 1
    if not 0 <= i < len(scenes):
        raise gr.Error(f"Chỉ có {len(scenes)} cảnh.")
    v = tts.voice_info(pdir, i, scenes[i], st)
    if not v:
        raise gr.Error("Cảnh này chưa có giọng — hãy bấm “Tạo giọng” trước.")
    return str(v[0])


# ── ③ Hình ảnh ────────────────────────────────────────────────────────────────
def _job_render(pdir, scenes, st, force, log):
    durations = {}
    for i, sc in enumerate(scenes):
        v = tts.voice_info(pdir, i, sc, st)
        if v:
            durations[i] = v[1]
    if not any(media.has_bg(pdir, sc) for sc in scenes):
        log("ℹ️ Chưa có ảnh nền nào nên cảnh chỉ có nền màu của chủ đề. Dán JSON phong cách ở tab ③ (bật “Tự tạo ảnh AI”) "
            "rồi bấm “Tạo ảnh AI” để có ảnh theo phong cách của bạn.")
    render.render_scenes(pdir, scenes, st, durations or None, force=force, log=log)


def render_handler(name, api_key, model, force, rows, *vals):
    try:
        pdir, scenes, st = prepare(name, rows, vals, auto=True, keys=_sec(api_key, model))
    except UserError as e:
        yield f"⚠️ {e}"
        return
    for log, _res, _err in run_job(_job_render, pdir, scenes, st, bool(force)):
        yield log


def _job_preview(pdir, scenes, st, i, log):
    return assemble.preview_scene(pdir, i, scenes, st, log=log)


def preview_handler(name, api_key, model, idx, rows, *vals):
    try:
        pdir, scenes, st = prepare(name, rows, vals, save=False, auto=True, keys=_sec(api_key, model))
    except UserError as e:
        yield f"⚠️ {e}", None
        return
    i = int(idx) - 1
    if not 0 <= i < len(scenes):
        yield f"⚠️ Chỉ có {len(scenes)} cảnh.", None
        return
    for log, res, _err in run_job(_job_preview, pdir, scenes, st, i):
        yield log, (str(res) if res else None)


# ── ④ Xuất video ──────────────────────────────────────────────────────────────
def _job_assemble(pdir, scenes, st, log):
    return assemble.assemble(pdir, scenes, st, log=log)


def _job_all(pdir, scenes, st, log):
    return assemble.run_all(pdir, scenes, st, log=log)


def _stream_result(job, *args):
    for log, res, _err in run_job(job, *args):
        if res:
            files = [str(res["zip"])] + [str(p) for k, p in res.items() if k != "zip"]
            yield log, str(res["video"]), files
        else:
            yield log, gr.update(), gr.update()


def _stash_music(pdir, st, bgm_file):
    """Chép file nhạc người dùng vào dự án (nếu có) và báo lỗi sớm khi chọn 'file' mà chưa có nhạc."""
    path = audiofx.stash_user_music(pdir, bgm_file)
    if st["bgm"] == "file" and path is None:
        raise UserError("Bạn chọn “Dùng file nhạc của tôi” nhưng chưa tải file nhạc lên (tab ④).")


def assemble_handler(name, api_key, model, hf_token, bgm_file, rows, *vals):
    try:
        pdir, scenes, st = prepare(name, rows, vals, auto=True, keys=_sec(api_key, model, hf_token))
        _stash_music(pdir, st, bgm_file)
    except UserError as e:
        yield f"⚠️ {e}", None, None
        return
    yield from _stream_result(_job_assemble, pdir, scenes, st)


def all_handler(name, api_key, model, hf_token, bgm_file, rows, *vals):
    try:
        pdir, scenes, st = prepare(name, rows, vals, auto=True, keys=_sec(api_key, model, hf_token))
        _stash_music(pdir, st, bgm_file)
    except UserError as e:
        yield f"⚠️ {e}", None, None
        return
    yield from _stream_result(_job_all, pdir, scenes, st)


# ── Giao diện ─────────────────────────────────────────────────────────────────
def _blocks():
    """Tạo khung giao diện; nếu theme/head không tương thích với phiên bản Gradio đang chạy thì tự lùi về cấu hình đơn giản."""
    try:
        theme = ui_theme.make_theme()
    except Exception:  # noqa: BLE001
        theme = gr.themes.Soft()
    try:
        return gr.Blocks(title="AI Auto Video", theme=theme, css=ui_theme.CSS, head=ui_theme.HEAD)
    except TypeError:
        return gr.Blocks(title="AI Auto Video", theme=theme, css=ui_theme.CSS)


def build_ui() -> gr.Blocks:
    existing = P.list_projects()
    default_project = existing[0] if existing else "du-an-1"
    d = P.DEFAULT_SETTINGS

    with _blocks() as demo:
        gr.HTML(ui_theme.HERO_HTML)
        with gr.Row(elem_classes="projbar"):
            project = gr.Dropdown(choices=existing, value=default_project, allow_custom_value=True,
                                  label="Dự án (gõ tên mới để tạo)", scale=4)
            open_btn = gr.Button("📂 Mở", scale=1)
            save_btn = gr.Button("💾 Lưu", scale=1)
        status = gr.Markdown()

        with gr.Row(equal_height=False):
            with gr.Column(scale=7, min_width=380):
                with gr.Tabs():
                    # ① Kịch bản ----------------------------------------------------
                    with gr.Tab("① Kịch bản"):
                        script_text = gr.Textbox(lines=8, label="Dán kịch bản của bạn",
                                                 placeholder="Mỗi đoạn cách nhau một dòng trống. Đoạn dài sẽ tự tách thành nhiều cảnh.")
                        with gr.Row():
                            add_outro = gr.Checkbox(value=True, label="Tự thêm cảnh kết (outro)")
                            split_btn = gr.Button("✂️ Tách thành các cảnh", variant="primary")
                            fill_btn = gr.Button("🪄 Điền tự động các ô trống")
                        with gr.Accordion("✨ Đạo diễn AI — tự chọn chủ đề, mẫu cảnh, chữ và mô tả ảnh nền (tuỳ chọn)", open=False):
                            api_key = gr.Textbox(type="password", label="Anthropic API key (không lưu vào dự án) — dùng cho Đạo diễn AI và để viết mô tả ảnh sát nội dung hơn")
                            with gr.Row():
                                dir_model = gr.Textbox(value=director.DEFAULT_MODEL, label="Mô hình")
                                dir_topic = gr.Textbox(label="Chủ đề / phong cách mong muốn (không bắt buộc)",
                                                       placeholder="vd: công nghệ, tông tối, nhịp nhanh")
                            dir_ai_img = gr.Checkbox(value=True, label="Để AI mô tả ảnh nền cho các cảnh")
                            director_btn = gr.Button("✨ Thiết kế video từ kịch bản")
                        table = gr.Dataframe(
                            value=[[""] * len(K.HEADERS)], headers=K.HEADERS, datatype=["str"] * len(K.HEADERS),
                            type="array", interactive=True, wrap=True, label="Danh sách cảnh (sửa trực tiếp, có thể thêm dòng)",
                        )
                        gr.Markdown(
                            "**Cách điền:** chỉ cần cột **Lời đọc** là đủ — các ô khác để trống sẽ được tự điền.\n\n"
                            "- **Mẫu:** `hero` · `stat` · `statement` · `list` · `quote` · `compare` · `image` · `outro`\n"
                            "- **Tiêu đề:** dùng `|` để xuống dòng, đặt `*từ khoá*` trong dấu sao để tô sáng · **Danh sách:** các mục cách nhau "
                            "bằng `|`, có thể bắt đầu bằng emoji (ví dụ `🔋 Pin trâu`)\n"
                            "- **Ảnh nền:** một đường link ảnh, hoặc **mô tả ảnh** (AI sẽ tạo) — để trống thì tự điền\n"
                            "- Lời đọc: số được tự đọc thành chữ (bật/tắt ở tab ②)."
                        )

                    # ② Giọng đọc ---------------------------------------------------
                    with gr.Tab("② Giọng đọc"):
                        gr.Markdown(f"**Thư viện giọng** lưu tại `{voices.ROOT}` (trên Google Drive nếu bạn đã bật ở Phần 2) — dùng lại cho mọi video.")
                        voice = gr.Dropdown(choices=voices.names(), value=d["voice"] or voices.NO_VOICE, allow_custom_value=True,
                                            label="Chọn giọng đọc cho video này")
                        voice_audio = gr.Audio(label="Nghe thử giọng đã chọn", interactive=False)
                        with gr.Accordion("➕ Lưu giọng mới vào thư viện", open=False):
                            new_name = gr.Textbox(label="Tên giọng", placeholder="vd: Giọng nam trầm")
                            new_audio = gr.Audio(sources=["upload", "microphone"], type="filepath",
                                                 label="Giọng mẫu (3–15 giây, rõ tiếng, ít tạp âm)")
                            new_text = gr.Textbox(label="Lời của giọng mẫu (không bắt buộc, để trống sẽ tự nhận dạng)")
                            with gr.Row():
                                voice_save_btn = gr.Button("💾 Lưu giọng", variant="primary")
                                voice_del_btn = gr.Button("🗑️ Xoá giọng đang chọn")
                            voice_info = gr.Markdown()
                        with gr.Row():
                            speed = gr.Slider(0.7, 1.4, value=d["speed"], step=0.05, label="Tốc độ đọc")
                            seed = gr.Number(value=d["seed"], precision=0, label="Seed")
                            normalize = gr.Checkbox(value=d["normalize"], label="Tự đọc số thành chữ")
                        with gr.Row():
                            force_tts = gr.Checkbox(value=False, label="Tạo lại từ đầu (bỏ qua giọng đã có)")
                            tts_btn = gr.Button("🎙️ Tạo giọng cho các cảnh", variant="primary")
                        tts_log = gr.Textbox(lines=8, label="Nhật ký", interactive=False, autoscroll=True)
                        with gr.Row():
                            listen_idx = gr.Number(value=1, precision=0, label="Nghe thử cảnh số")
                            listen_btn = gr.Button("▶ Nghe")
                        listen_audio = gr.Audio(label="Giọng của cảnh", interactive=False)

                    # ③ Hình ảnh ----------------------------------------------------
                    with gr.Tab("③ Hình ảnh & video") as tab3:
                        gr.Markdown("**Cách làm:** 1) tạo prompt cho từng cảnh từ kịch bản → 2) tạo ảnh từ prompt → 3) (tuỳ chọn) biến ảnh thành video chuyển động.")
                        with gr.Group(elem_classes="card"):
                            gr.Markdown("### 1 · Prompt cho từng cảnh")
                            gr.Markdown(
                                "Tool đọc **lời đọc của từng cảnh** (đã tách ở bước ①) và viết prompt mô tả hình ảnh. "
                                "Phong cách ảnh chọn ở bước 2, nên prompt chỉ cần nói về **chủ thể và hành động**. "
                                "Bạn có thể sửa trực tiếp trong bảng."
                            )
                            with gr.Row():
                                prompt_btn = gr.Button("✍️ Tạo prompt từ nội dung kịch bản", variant="primary", scale=3)
                                rewrite_prompts = gr.Checkbox(value=False, label="Viết lại cả prompt đã có", scale=2)
                            auto_images = gr.Checkbox(value=d["auto_images"],
                                                      label="Khi tạo ảnh/video, tự viết prompt cho cảnh còn trống")
                            prompt_status = gr.Markdown()
                            prompt_table = gr.Dataframe(
                                value=[["", "", "", ""]], headers=PROMPT_HEADERS, datatype=["str"] * 4, type="array",
                                interactive=True, wrap=True, label="Prompt theo từng cảnh (chỉ cột cuối sửa được)",
                            )
                        with gr.Group(elem_classes="card"):
                            gr.Markdown("### 2 · Tạo ảnh từ prompt")
                            with gr.Row():
                                style_preset = gr.Dropdown(choices=media.STYLE_CHOICES, value=d["style_preset"],
                                                           label="🎨 Phong cách ảnh AI", scale=3)
                                style_note = gr.Textbox(value=d["style_note"], scale=3,
                                                        label="Ghi chú phong cách thêm (tuỳ chọn, tiếng Anh)",
                                                        placeholder="để trống cũng được, hoặc bấm “Tự gợi ý”")
                                note_btn = gr.Button("✨ Tự gợi ý", scale=1)
                            with gr.Row():
                                force_ai = gr.Checkbox(value=False, label="Tạo lại ảnh AI từ đầu", scale=2)
                                ai_btn = gr.Button("🎨 Tạo ảnh AI từ prompt", variant="primary", scale=3)
                            ai_gallery = gr.Gallery(label="Ảnh AI đã tạo (chú thích là prompt của cảnh)", columns=5, height=260,
                                                    interactive=False)
                        with gr.Group(elem_classes="card"):
                            gr.Markdown("### 3 · Biến ảnh thành video chuyển động (tuỳ chọn, chậm, cần GPU)")
                            video_ai = gr.Checkbox(value=d["video_ai"],
                                                   label="Bật video AI cho cảnh có ảnh (hero / image / statement / quote)")
                            with gr.Row():
                                video_frames = gr.Radio(choices=[("25 khung (~3.5 giây, đẹp hơn)", 25), ("14 khung (~2 giây, nhanh hơn)", 14)],
                                                        value=d["video_frames"], label="Số khung SVD tạo cho mỗi cảnh")
                                video_motion = gr.Slider(40, 200, value=d["video_motion"], step=5,
                                                         label="Mức chuyển động (cao = động nhiều hơn nhưng dễ méo hình)")
                            hf_token = gr.Textbox(type="password", label="Hugging Face token (không lưu vào dự án) — cần để tải mô hình SVD")
                            gr.Markdown(
                                "Mô hình **ảnh → video**: nội dung theo ảnh (tạo từ prompt), còn chuyển động do mô hình tự suy ra, "
                                "không điều khiển được bằng chữ. Mỗi cảnh mất vài phút trên T4 (chưa đo thực tế). Cảnh có video AI "
                                "không có chữ trên hình nên phụ đề tự bật. Cần đồng ý điều khoản mô hình "
                                "`stabilityai/stable-video-diffusion-img2vid-xt` trên Hugging Face."
                            )
                            with gr.Row():
                                force_video = gr.Checkbox(value=False, label="Tạo lại video AI từ đầu", scale=2)
                                video_btn = gr.Button("🎬 Tạo video AI cho các cảnh", variant="primary", scale=3)
                            with gr.Row():
                                scene_video_idx = gr.Number(value=1, precision=0, label="Xem video AI của cảnh số")
                                scene_video_btn = gr.Button("▶️ Xem video cảnh")
                            scene_video = gr.Video(label="Video AI của cảnh", interactive=False)
                        with gr.Accordion("🎨 Chủ đề, thương hiệu & chất lượng dựng", open=False):
                            theme = gr.Dropdown(choices=[(v["label"], k) for k, v in THEMES.items()], value=d["theme"],
                                                label="🎨 Chủ đề hình ảnh (quyết định nền, màu, kiểu chữ, hiệu ứng)")
                            with gr.Row():
                                brand = gr.Textbox(value=d["brand"], label="Tên kênh / thương hiệu")
                                tagline = gr.Textbox(value=d["tagline"], label="Khẩu hiệu (cảnh kết)")
                                url = gr.Textbox(value=d["url"], label="Liên kết (cảnh kết)")
                            with gr.Row():
                                custom_colors = gr.Checkbox(value=d["custom_colors"], label="Dùng màu của riêng tôi (thay màu của chủ đề)")
                                accent_from = gr.ColorPicker(value=d["accent_from"], label="Màu nhấn 1")
                                accent_to = gr.ColorPicker(value=d["accent_to"], label="Màu nhấn 2")
                            quality = gr.Radio(
                                choices=[("Nhanh — 720×1280 · 24fps", "fast"), ("Chuẩn — 1080×1920 · 30fps", "standard")],
                                value=d["quality"], label="Chất lượng",
                            )
                            continuous = gr.Checkbox(value=d["continuous"],
                                                     label="Nền chuyển động suốt cảnh (đẹp hơn nhưng dựng lâu hơn)")
                        with gr.Accordion("🖼️ Dựng hình mẫu cảnh (chữ, số liệu, hoạt hình)", open=False):
                            with gr.Row():
                                force_render = gr.Checkbox(value=False, label="Dựng lại từ đầu (bỏ qua hình đã có)")
                                render_btn = gr.Button("🖼️ Dựng hình các cảnh", variant="primary")
                            render_log = gr.Textbox(lines=8, label="Nhật ký", interactive=False, autoscroll=True)
                            with gr.Row():
                                preview_idx = gr.Number(value=1, precision=0, label="Xem thử cảnh số")
                                preview_btn = gr.Button("👁️ Xem thử")
                            preview_video = gr.Video(label="Xem thử", interactive=False)

                    # ④ Xuất video --------------------------------------------------
                    with gr.Tab("④ Xuất video"):
                        gr.Markdown("Chọn nhạc nền và phụ đề, rồi bấm **Ghép video cuối** (khi đã có giọng và hình) hoặc **Tạo video trọn gói** ở khung bên phải.")
                        with gr.Accordion("🎵 Âm thanh & phụ đề (tuỳ chọn)", open=True):
                            with gr.Row():
                                bgm = gr.Radio(choices=audiofx.BGM_CHOICES, value=d["bgm"], label="Nhạc nền (tự tạo, không vướng bản quyền)")
                                bgm_volume = gr.Slider(0.0, 0.5, value=d["bgm_volume"], step=0.01, label="Âm lượng nhạc nền")
                            bgm_file = gr.File(file_types=["audio"], label="File nhạc của bạn (chỉ dùng khi chọn “Dùng file nhạc của tôi”)")
                            with gr.Row():
                                sfx = gr.Checkbox(value=d["sfx"], label="Hiệu ứng chuyển cảnh (tiếng vút, tiếng bụp ở cảnh số liệu/kết)")
                                caps = gr.Radio(choices=captions.CAPTION_CHOICES, value=d["captions"],
                                                label="Phụ đề cháy sẵn trong video (từ đang đọc được tô sáng)")
                            gr.Markdown("Nhạc tự hạ nhỏ khi có giọng đọc. Phụ đề có thể xem thử ở tab ③ (nút “Xem thử”).")
                        assemble_btn = gr.Button("🎬 Ghép video cuối", variant="primary")

            with gr.Column(scale=4, min_width=340, elem_classes="dock"):
                gr.HTML(ui_theme.DOCK_TITLE_HTML)
                all_btn = gr.Button("🚀 Tạo video trọn gói", variant="primary", elem_id="run_all")
                out_video = gr.Video(label="Video", interactive=False)
                out_files = gr.File(label="Tải về: ket-qua.zip (gồm tất cả) · video.mp4 · voice.mp3 · script.txt · captions.srt",
                                    file_count="multiple", interactive=False)
                out_log = gr.Textbox(lines=7, label="Nhật ký", interactive=False, autoscroll=True)
        gr.HTML(ui_theme.FOOT_HTML)

        settings = [brand, tagline, url, theme, custom_colors, accent_from, accent_to, quality, continuous, speed, seed, normalize, voice, auto_images,
                    bgm, bgm_volume, sfx, caps, video_ai, video_frames, video_motion, style_preset, style_note]
        base = [project, table] + settings  # đầu vào chung

        demo.load(open_project, [project], [table] + settings + [status])
        open_btn.click(open_project, [project], [table] + settings + [status])
        save_btn.click(save_project, base, status)

        director_btn.click(director_handler, [table, api_key, dir_model, dir_topic, dir_ai_img, brand], [table, theme, status])
        voice.change(voice_preview, [voice], [voice_audio])
        voice_save_btn.click(voice_save, [new_name, new_audio, new_text], [voice, voice_info, new_audio, new_text, voice_audio])
        voice_del_btn.click(voice_delete, [voice], [voice, voice_info, voice_audio])
        video_btn.click(video_handler, [project, api_key, dir_model, hf_token, force_video, table] + settings, [render_log])
        ai_btn.click(ai_handler, [project, api_key, dir_model, force_ai, table] + settings, [render_log, ai_gallery])
        prompt_btn.click(prompts_handler, [project, api_key, dir_model, rewrite_prompts, table] + settings,
                         [table, prompt_table, prompt_status])
        (getattr(prompt_table, "input", None) or prompt_table.change)(sync_prompts, [prompt_table, table], [table])
        tab3.select(refresh_prompts, [table], [prompt_table])
        note_btn.click(suggest_note_handler, [api_key, dir_model, style_preset, table], [style_note])
        scene_video_btn.click(scene_video_handler, [project, scene_video_idx, table] + settings, [scene_video])
        split_btn.click(split_handler, [script_text, add_outro, brand], table)
        fill_btn.click(fill_handler, [table], table)

        tts_btn.click(tts_handler, [project, force_tts, table] + settings, tts_log)
        listen_btn.click(listen_handler, [project, listen_idx, table] + settings, listen_audio)

        render_btn.click(render_handler, [project, api_key, dir_model, force_render, table] + settings, render_log)
        preview_btn.click(preview_handler, [project, api_key, dir_model, preview_idx, table] + settings, [render_log, preview_video])

        assemble_btn.click(assemble_handler, [project, api_key, dir_model, hf_token, bgm_file, table] + settings, [out_log, out_video, out_files])
        all_btn.click(all_handler, [project, api_key, dir_model, hf_token, bgm_file, table] + settings, [out_log, out_video, out_files])
    return demo


def main() -> None:
    P.ROOT.mkdir(parents=True, exist_ok=True)
    voices.ROOT.mkdir(parents=True, exist_ok=True)
    # Chỉ cho phép phục vụ file trong thư mục dự án và thư viện giọng (KHÔNG mở cả /content hay Google Drive).
    allowed = [str(P.ROOT), str(voices.ROOT)]
    share = os.environ.get("AVG_SHARE", "0") == "1"
    kwargs = {}
    if share:  # link công khai thì bắt buộc có mật khẩu
        user = os.environ.get("AVG_USER", "admin")
        pw = os.environ.get("AVG_PASS") or secrets.token_urlsafe(9)
        kwargs["auth"] = (user, pw)
        print(f"🔐 Đăng nhập giao diện: tài khoản `{user}` · mật khẩu `{pw}`", flush=True)
    demo = build_ui()
    demo.queue(default_concurrency_limit=1)
    demo.launch(
        share=share,
        server_name="127.0.0.1",
        server_port=int(os.environ.get("AVG_PORT", "7860")),
        allowed_paths=allowed,
        show_error=True,
        **kwargs,
    )


if __name__ == "__main__":
    main()
