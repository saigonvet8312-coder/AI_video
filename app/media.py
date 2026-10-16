"""Ảnh nền cho cảnh: ảnh tải lên, đường link, hoặc ảnh do AI tạo theo mô tả."""
from __future__ import annotations

import base64
import io
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


_NEG = "text, logo, watermark, cluttered typography, busy background elements unrelated to the central subject"

STYLES = {
    "cosmic": {
        "note": "glowing particles, deep space, dramatic backlight",
        "label": "Vũ trụ công nghệ phát sáng (mặc định)",
        "style": {
            "style_name": "cosmic tech brain glow",
            "full_prompt_string": (
                "futuristic digital art, glowing brain or neural motif as central subject, circuit-board and neural network "
                "line patterns, cosmic sci-fi atmosphere, hyper-detailed 3D render quality, tech-mysticism fusion aesthetic, "
                "ultra sharp digital illustration, particle and spark accents, ethereal energy emanating from the subject"),
            "composition": (
                "centered symmetrical composition, medium to close-up framing, glowing subject as singular focal point, "
                "circuit lines or energy trails radiating outward, large dark negative space surrounding the subject"),
            "lighting": (
                "dramatic glow and bloom lighting, strong central light source emanating from the subject, neon-like "
                "luminescence, high contrast between dark background and glowing highlights, soft rim light"),
            "color_palette": (
                "deep black or navy background, vibrant neon accents shifting between electric blue, violet-purple, and "
                "warm orange-gold across pieces, high saturation glow, occasional teal or red variant"),
            "negative_prompt": _NEG,
        },
    },
    "mystic": {
        "note": "foggy, low light, dramatic shadows, ancient atmosphere",
        "label": "Huyền bí, triết học tối",
        "style": {
            "style_name": "dark mystical philosophy",
            "full_prompt_string": (
                "dark mystical philosophical art, ancient ruins and cosmic mist, symbolic imagery, esoteric sigils, "
                "cinematic oil-painting texture, solemn contemplative atmosphere, weathered stone statues, hooded lone figure"),
            "composition": (
                "wide cinematic composition, small lone subject against a vast scene, strong vertical lines, "
                "large dark negative space, symmetrical framing with a distant light source"),
            "lighting": (
                "low-key chiaroscuro lighting, a single shaft of moonlight or golden candle glow, deep shadows, "
                "volumetric fog and drifting dust"),
            "color_palette": "deep charcoal, midnight blue, muted antique gold accents, occasional dark crimson, desaturated tones",
            "negative_prompt": _NEG + ", cartoon, bright cheerful colors, modern objects",
        },
    },
    "cinematic": {
        "note": "golden hour, shallow depth of field, film grain",
        "label": "Điện ảnh chân thực",
        "style": {
            "style_name": "cinematic photoreal",
            "full_prompt_string": (
                "photorealistic cinematic still, 35mm film look, shallow depth of field, natural textures, "
                "high detail, realistic materials, subtle film grain, professional color grading"),
            "composition": "rule-of-thirds composition, subject in sharp focus with softly blurred background, vertical 9:16 framing",
            "lighting": "natural motivated lighting, soft golden-hour or moody practical lights, gentle contrast",
            "color_palette": "teal and warm orange cinematic grade, rich but natural saturation",
            "negative_prompt": _NEG + ", cartoon, illustration, oversaturated, plastic skin",
        },
    },
    "anime": {
        "note": "soft pastel colors, warm sunset light, gentle clouds",
        "label": "Hoạt hình vẽ tay (kiểu anime)",
        "style": {
            "style_name": "painterly anime illustration",
            "full_prompt_string": (
                "soft hand-painted anime-inspired illustration, lush painterly background, clean delicate linework, "
                "whimsical atmosphere, detailed environment, gentle clouds and foliage"),
            "composition": "balanced composition with clear foreground subject and layered background depth",
            "lighting": "soft diffused daylight or warm sunset glow, gentle highlights",
            "color_palette": "harmonious pastel and vivid sky tones, soft gradients, fresh greens and warm light",
            "negative_prompt": _NEG + ", photorealistic, harsh shadows, dark gritty",
        },
    },
    "flat": {
        "note": "bold shapes, limited colors, plenty of empty space",
        "label": "Minh hoạ phẳng tối giản",
        "style": {
            "style_name": "minimal flat vector",
            "full_prompt_string": (
                "minimal flat vector illustration, simple geometric shapes, clean editorial design, subtle paper texture, "
                "bold silhouettes, limited detail"),
            "composition": "centered subject, generous empty space, clear visual hierarchy, simple background shapes",
            "lighting": "flat even lighting with minimal soft shadow",
            "color_palette": "limited palette of 3 to 4 harmonious colors, warm paper tones with one bold accent color",
            "negative_prompt": _NEG + ", photorealistic, gradients noise, complex textures",
        },
    },
    "watercolor": {
        "note": "soft washes, airy light, paper texture",
        "label": "Màu nước",
        "style": {
            "style_name": "delicate watercolor",
            "full_prompt_string": (
                "delicate watercolor painting, soft bleeding washes, visible paper grain, loose ink outlines, "
                "airy and poetic, hand-painted feel"),
            "composition": "loose balanced composition with soft vignette edges and white paper breathing space",
            "lighting": "soft luminous light, gentle tonal transitions",
            "color_palette": "translucent muted blues, warm ochres, soft rose and sage greens",
            "negative_prompt": _NEG + ", sharp digital rendering, harsh outlines, photorealistic",
        },
    },
    "cyberpunk": {
        "note": "neon reflections, rainy night, strong rim light",
        "label": "Cyberpunk thành phố neon",
        "style": {
            "style_name": "neon cyberpunk city",
            "full_prompt_string": (
                "cyberpunk neon cityscape, rain-slicked streets, holographic signage without readable text, dense futuristic "
                "architecture, atmospheric haze, high-tech low-life mood, cinematic digital art"),
            "composition": "dramatic low or high angle, strong perspective lines leading to a glowing vanishing point",
            "lighting": "neon magenta and cyan glow, reflections on wet surfaces, strong rim lights",
            "color_palette": "deep indigo shadows with hot magenta, electric cyan and amber highlights",
            "negative_prompt": _NEG + ", daylight, rural, pastel",
        },
    },
    "clay": {
        "note": "soft studio light, pastel backdrop, playful",
        "label": "Đất sét 3D dễ thương",
        "style": {
            "style_name": "cute 3D clay",
            "full_prompt_string": (
                "cute 3D clay render, soft rounded shapes, tactile plasticine texture with fingerprint details, "
                "playful miniature diorama, charming and friendly"),
            "composition": "centered hero object on a simple diorama base, shallow depth of field, slight top-down angle",
            "lighting": "soft studio lighting, gentle shadows, subtle ambient occlusion",
            "color_palette": "bright cheerful candy colors, soft pastel backdrop",
            "negative_prompt": _NEG + ", realistic photo, dark gritty, scary",
        },
    },
}
DEFAULT_STYLE_KEY = "cosmic"
DEFAULT_STYLE = STYLES[DEFAULT_STYLE_KEY]["style"]
STYLE_CHOICES = [(v["label"], k) for k, v in STYLES.items()]


def default_note(key: str) -> str:
    return (STYLES.get(key) or STYLES[DEFAULT_STYLE_KEY]).get("note", "")


def get_style(st: dict | None = None) -> dict:
    """Phong cách ảnh AI theo cài đặt: kiểu có sẵn (style_preset) + ghi chú thêm (style_note)."""
    st = st or {}
    preset = STYLES.get(st.get("style_preset") or DEFAULT_STYLE_KEY) or STYLES[DEFAULT_STYLE_KEY]
    style = dict(preset["style"])
    note = str(st.get("style_note") or "").strip()
    if note:
        style["full_prompt_string"] = f'{style["full_prompt_string"]}, {note}'
    return style


def require_style(st: dict) -> dict:
    return get_style(st)


def ai_prompts(subject: str, style: dict) -> tuple[str, str, str]:
    """(prompt chính, prompt phụ cho bộ mã hoá thứ hai của SDXL, negative). Chủ thể luôn đứng đầu."""
    subject = subject.strip()
    # Phong cách khác mặc định: đặt tên phong cách lên đầu để mô hình bám sát hơn (mặc định giữ nguyên như cũ)
    lead = style["style_name"] if style["style_name"] != DEFAULT_STYLE["style_name"] else ""
    p1 = ", ".join(x for x in (lead, subject, style["full_prompt_string"]) if x)
    p2 = ", ".join(x for x in (lead, subject, style["composition"], style["lighting"], style["color_palette"]) if x)
    neg = ", ".join(x for x in (style["negative_prompt"], NEGATIVE_BASE) if x)
    return p1, p2, neg


def _style_fp(st: dict) -> str:
    """Khoá cache ảnh theo phong cách. Phong cách mặc định không ghi chú → rỗng (giữ nguyên ảnh đã tạo trước đó)."""
    key = st.get("style_preset") or DEFAULT_STYLE_KEY
    note = str(st.get("style_note") or "").strip()
    return "" if key == DEFAULT_STYLE_KEY and not note else f"{key}|{note}"


def ai_path(pdir: Path, prompt: str, st: dict) -> Path:
    # Phụ thuộc mô tả + phong cách đã chọn (đổi phong cách ⇒ tạo ảnh mới), không phụ thuộc chủ đề giao diện.
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
