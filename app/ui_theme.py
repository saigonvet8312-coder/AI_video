"""Giao diện: bảng màu tối, font Be Vietnam Pro, thẻ kính, nút gradient. Chỉ là phần trình bày, không chứa logic."""
from __future__ import annotations

import gradio as gr

BG = "#0A0F1F"
SURFACE = "#111833"
SURFACE_2 = "#0D1330"
BORDER = "rgba(148,163,184,.18)"
TEXT = "#E8ECF8"
MUTED = "#94A3C0"
GRADIENT = "linear-gradient(135deg,#F59E0B 0%,#EC4899 55%,#A855F7 100%)"
GRADIENT_HOVER = "linear-gradient(135deg,#FBBF24 0%,#F472B6 55%,#C084FC 100%)"

HEAD = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
    '<meta name="theme-color" content="#0A0F1F">'
)


def make_theme():
    theme = gr.themes.Base(
        primary_hue="violet", secondary_hue="amber", neutral_hue="slate",
        font=[gr.themes.GoogleFont("Be Vietnam Pro"), "ui-sans-serif", "system-ui", "sans-serif"],
        radius_size=gr.themes.sizes.radius_lg,
        text_size=gr.themes.sizes.text_md,
    )
    base = dict(
        body_background_fill=BG,
        body_text_color=TEXT,
        body_text_color_subdued=MUTED,
        background_fill_primary=SURFACE,
        background_fill_secondary=SURFACE_2,
        block_background_fill=SURFACE,
        block_border_color=BORDER,
        block_border_width="1px",
        block_label_background_fill="transparent",
        block_label_text_color=MUTED,
        block_title_text_color=TEXT,
        block_title_text_weight="600",
        block_shadow="0 8px 30px rgba(0,0,0,.28)",
        panel_background_fill=SURFACE,
        panel_border_color=BORDER,
        border_color_primary=BORDER,
        input_background_fill=SURFACE_2,
        input_border_color=BORDER,
        input_border_color_focus="#A855F7",
        input_shadow_focus="0 0 0 3px rgba(168,85,247,.25)",
        button_primary_background_fill=GRADIENT,
        button_primary_background_fill_hover=GRADIENT_HOVER,
        button_primary_text_color="#0A0F1F",
        button_primary_border_color="transparent",
        button_secondary_background_fill="rgba(255,255,255,.06)",
        button_secondary_background_fill_hover="rgba(255,255,255,.12)",
        button_secondary_text_color=TEXT,
        button_secondary_border_color=BORDER,
        checkbox_background_color=SURFACE_2,
        checkbox_border_color=BORDER,
        checkbox_label_background_fill="transparent",
        checkbox_label_background_fill_hover="transparent",
        checkbox_label_text_color=TEXT,
        slider_color="#A855F7",
        table_even_background_fill=SURFACE,
        table_odd_background_fill=SURFACE_2,
        table_border_color=BORDER,
    )
    both = {}
    for k, v in base.items():  # chỉ có một giao diện tối: đặt cùng giá trị cho chế độ sáng và tối
        both[k] = v
        both[k + "_dark"] = v
    return theme.set(**both)


HERO_HTML = """
<div class="hero">
  <div class="hero-badge">AI · 9:16 · TikTok / Reels / Shorts</div>
  <h1 class="hero-title">🎬 AI Auto Video</h1>
  <p class="hero-sub">Dán kịch bản, chọn giọng, bấm một nút: ra video dọc có giọng đọc, hình động, nhạc nền và phụ đề.</p>
  <div class="stepper">
    <span class="step"><b>1</b> Kịch bản</span>
    <span class="step"><b>2</b> Giọng đọc</span>
    <span class="step"><b>3</b> Hình ảnh</span>
    <span class="step"><b>4</b> Xuất video</span>
  </div>
</div>
"""

DOCK_TITLE_HTML = """
<div class="dock-title">
  <div class="dock-kicker">KẾT QUẢ</div>
  <div class="dock-hint">Bấm <b>Tạo video trọn gói</b> để làm liền mạch giọng, hình và ghép video. Kết quả hiện ở đây dù bạn đang ở tab nào.</div>
</div>
"""

FOOT_HTML = """
<div class="foot">⚠️ Dự án chỉ lưu trong phiên Colab này, hãy tải <b>ket-qua.zip</b> về ngay khi xong. Khoá API chỉ dùng trong lúc bạn bấm nút và không được lưu lại.</div>
"""

CSS = """
:root{--g:%(g)s;--gh:%(gh)s;--bd:%(bd)s;--mut:%(mut)s}
html,body,.gradio-container{background:%(bg)s !important}
.gradio-container{max-width:1320px !important;margin:0 auto !important;padding:18px 18px 40px !important;
  font-family:'Be Vietnam Pro',ui-sans-serif,system-ui,sans-serif !important}
.gradio-container::before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;
  background:radial-gradient(700px 380px at 12%% -5%%,rgba(168,85,247,.22),transparent 60%%),
             radial-gradient(640px 360px at 95%% 0%%,rgba(245,158,11,.16),transparent 60%%)}

/* Hero */
.hero{position:relative;overflow:hidden;border:1px solid var(--bd);border-radius:22px;padding:26px 28px 22px;
  background:linear-gradient(135deg,rgba(168,85,247,.16),rgba(245,158,11,.10));box-shadow:0 18px 50px rgba(0,0,0,.35)}
.hero-badge{display:inline-block;font-size:12px;font-weight:700;letter-spacing:.06em;color:#FDE68A;
  background:rgba(245,158,11,.14);border:1px solid rgba(245,158,11,.35);padding:5px 12px;border-radius:999px}
.hero-title{margin:12px 0 6px !important;font-size:38px !important;line-height:1.15 !important;font-weight:800 !important;
  background:var(--g);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:transparent}
.hero-sub{margin:0 0 16px !important;color:#C7D0E6 !important;font-size:16px;max-width:760px}
.stepper{display:flex;flex-wrap:wrap;gap:10px}
.step{display:inline-flex;align-items:center;gap:8px;padding:7px 14px;border-radius:999px;font-weight:600;font-size:14px;
  color:#E8ECF8;background:rgba(255,255,255,.06);border:1px solid var(--bd)}
.step b{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%%;
  background:var(--g);color:#0A0F1F;font-size:12px}

/* Thanh dự án */
.projbar{margin-top:14px !important;padding:10px 12px !important;border:1px solid var(--bd) !important;border-radius:16px !important;
  background:rgba(17,24,51,.7) !important;backdrop-filter:blur(8px);gap:10px !important}

/* Thẻ / khối */
.block,.form,.panel{border-radius:16px !important}
.gradio-container .block{border-color:var(--bd) !important}
.gradio-container label span, .gradio-container .block-title{font-weight:600 !important}

/* Tab: dạng viên thuốc */
.gradio-container button[role="tab"]{font-weight:700 !important;font-size:15px !important;border-radius:12px !important;
  padding:9px 16px !important;margin-right:6px !important;color:var(--mut) !important;border:1px solid transparent !important;
  background:transparent !important}
.gradio-container button[role="tab"][aria-selected="true"]{color:#fff !important;background:rgba(168,85,247,.20) !important;
  border-color:rgba(168,85,247,.55) !important;box-shadow:0 6px 20px rgba(168,85,247,.20)}
.gradio-container .tab-wrapper,.gradio-container .tab-container{border-bottom:1px solid var(--bd) !important}

/* Nút */
.gradio-container button{border-radius:12px !important;font-weight:700 !important;transition:transform .12s ease,box-shadow .12s ease}
.gradio-container button.primary{box-shadow:0 10px 26px rgba(168,85,247,.30)}
.gradio-container button.primary:hover{transform:translateY(-1px);box-shadow:0 14px 32px rgba(236,72,153,.35)}
.gradio-container button.secondary:hover{transform:translateY(-1px)}

/* Khung kết quả cố định bên phải */
.dock{position:sticky;top:14px;align-self:flex-start;gap:12px !important;padding:16px !important;border:1px solid var(--bd) !important;
  border-radius:20px !important;background:linear-gradient(180deg,rgba(17,24,51,.92),rgba(13,19,48,.92)) !important;
  box-shadow:0 18px 50px rgba(0,0,0,.35)}
.dock-kicker{font-size:12px;font-weight:800;letter-spacing:.14em;color:#FBBF24}
.dock-hint{margin-top:4px;color:#C7D0E6;font-size:13.5px;line-height:1.5}
#run_all button,button#run_all{height:68px !important;font-size:20px !important;font-weight:800 !important;border-radius:16px !important;
  letter-spacing:.2px;color:#0A0F1F !important}
.dock textarea{font-family:ui-monospace,SFMono-Regular,Menlo,monospace !important;font-size:12.5px !important}

/* Bảng cảnh */
.gradio-container table{font-size:14px}
.gradio-container th{background:rgba(168,85,247,.14) !important;color:#E8ECF8 !important;font-weight:700 !important}

.foot{margin-top:18px;text-align:center;color:var(--mut);font-size:13px}
.foot b{color:#FDE68A}

@media (max-width: 900px){
  .dock{position:static}
  .hero-title{font-size:30px !important}
  .hero{padding:20px 18px}
}
""" % dict(g=GRADIENT, gh=GRADIENT_HOVER, bd=BORDER, mut=MUTED, bg=BG)
