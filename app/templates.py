"""Chủ đề + mẫu hình ảnh (HTML/CSS động) — thiết kế ở khung 1080x1920."""
from __future__ import annotations

import html
import re

TEMPLATE_VERSION = "t3"

THEMES = {
    "aurora": {"label": "Cực quang", "a": "#F59E0B", "b": "#A855F7",
               "style": "cinematic, vibrant gradient lighting, soft glow, dreamy atmosphere"},
    "neon": {"label": "Neon công nghệ", "a": "#22D3EE", "b": "#F472B6",
             "style": "cyberpunk, neon lights, futuristic, night city, glowing"},
    "noir": {"label": "Điện ảnh tối", "a": "#E5E7EB", "b": "#EF4444",
             "style": "film noir, dramatic lighting, high contrast, moody, cinematic shadows"},
    "paper": {"label": "Giấy sáng", "a": "#C2410C", "b": "#0F766E",
              "style": "minimal flat illustration, warm paper texture, soft colors, editorial"},
    "sunset": {"label": "Hoàng hôn", "a": "#FDE047", "b": "#FB7185",
               "style": "synthwave sunset, warm gradient sky, retro, silhouette"},
    "mono": {"label": "Tối giản đậm", "a": "#FACC15", "b": "#FFFFFF",
             "style": "high contrast black and white photography, bold, graphic"},
}
FX = ["rise", "left", "zoom", "blur"]

CSS = r"""
:root{--a:#F59E0B;--b:#A855F7;--fg:#F8FAFC;--mut:#A9B4D0;--card:rgba(255,255,255,.07);--cardb:rgba(255,255,255,.14);
 --onacc:#0A0F1F;--hl:rgba(245,158,11,.55);
 --fb:'Be Vietnam Pro','Noto Sans','Segoe UI','DejaVu Sans',sans-serif;--fh:var(--fb)}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1920px;overflow:hidden;background:#0A0F1F;color:var(--fg);font-family:var(--fb);-webkit-font-smoothing:antialiased}
.abs{position:absolute}
.bg{position:absolute;inset:0;overflow:hidden}
.wrap{position:absolute;inset:0;padding:190px 96px 400px;display:flex;flex-direction:column;justify-content:center;gap:44px}
.wrap.low{justify-content:flex-end;padding-bottom:430px}
.center{align-items:center;text-align:center}
h1,h2{font-family:var(--fh);font-weight:900;line-height:1.1;white-space:pre-line;word-break:break-word}
.sub{font-size:52px;line-height:1.35;color:var(--mut);font-weight:500;white-space:pre-line}

/* hiệu ứng vào cảnh (đổi theo từng cảnh) */
.rise,.pop,.w{opacity:0;animation-fill-mode:both;animation-delay:var(--d,0s);animation-timing-function:cubic-bezier(.2,.8,.2,1)}
.rise{animation-duration:.8s;animation-name:rise}
.fx-left .rise{animation-name:riseL}.fx-zoom .rise{animation-name:riseZ}.fx-blur .rise{animation-name:riseB}
.pop{animation:pop .7s cubic-bezier(.2,1.4,.4,1) var(--d,0s) both}
.w{display:inline-block;margin-right:.28em;animation-duration:.6s;animation-name:rise}
.fx-left .w{animation-name:riseL}.fx-zoom .w{animation-name:riseZ}.fx-blur .w{animation-name:riseB}
@keyframes rise{from{opacity:0;transform:translateY(60px)}to{opacity:1;transform:none}}
@keyframes riseL{from{opacity:0;transform:translateX(-140px)}to{opacity:1;transform:none}}
@keyframes riseZ{from{opacity:0;transform:scale(.8)}to{opacity:1;transform:none}}
@keyframes riseB{from{opacity:0;filter:blur(26px);transform:translateY(24px)}to{opacity:1;filter:none;transform:none}}
@keyframes pop{from{opacity:0;transform:scale(.55)}to{opacity:1;transform:none}}
.grow{transform-origin:left center;transform:scaleX(0);animation:grow .9s ease-out var(--d,0s) both}
@keyframes grow{to{transform:scaleX(1)}}

.pill{display:inline-block;align-self:flex-start;padding:18px 40px;border-radius:999px;background:var(--card);
 border:2px solid var(--cardb);font-size:40px;font-weight:700;letter-spacing:.06em;text-transform:uppercase}
.center .pill{align-self:center}
.grad{background:linear-gradient(90deg,var(--a),var(--b));-webkit-background-clip:text;background-clip:text;color:transparent}
.cta{align-self:flex-start;margin-top:20px;padding:26px 56px;border-radius:999px;font-size:44px;font-weight:800;color:var(--onacc);
 background:linear-gradient(90deg,var(--a),var(--b))}
.bar{height:14px;width:240px;border-radius:8px;background:linear-gradient(90deg,var(--a),var(--b))}
.foot{position:absolute;left:0;right:0;bottom:250px;text-align:center;font-size:36px;font-weight:600;
 letter-spacing:.16em;text-transform:uppercase;color:var(--mut);opacity:0;animation:rise .8s ease-out 1.2s both}
mark{color:inherit;background:linear-gradient(transparent 60%,var(--hl) 60% 92%,transparent 92%) no-repeat 0 0/0 100%;
 animation:hl .7s ease-out var(--d,1s) both;padding:0 .08em}
@keyframes hl{to{background-size:100% 100%}}
ul{list-style:none;display:flex;flex-direction:column;gap:30px}
li{display:flex;align-items:center;gap:36px;padding:34px 40px;border-radius:36px;background:var(--card);
 border:2px solid var(--cardb);font-size:54px;font-weight:700;line-height:1.25}
.ico{flex:none;width:112px;height:112px;border-radius:50%;display:flex;align-items:center;justify-content:center;
 font-size:58px;font-weight:900;color:var(--onacc);background:linear-gradient(135deg,var(--a),var(--b))}
.logo{width:380px;height:380px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:210px;font-weight:900;
 color:var(--onacc);background:linear-gradient(135deg,var(--a),var(--b));position:relative}
.logo::after{content:"";position:absolute;inset:-70px;border-radius:50%;background:radial-gradient(circle,var(--a) 0%,transparent 68%);
 opacity:.35;z-index:-1;animation:glow 3s ease-in-out infinite alternate}
@keyframes glow{from{transform:scale(.9);opacity:.25}to{transform:scale(1.15);opacity:.5}}
.url{padding:22px 50px;border-radius:999px;border:2px solid var(--cardb);font-size:42px;font-weight:600}
.count{--n:0;counter-reset:num var(--n);font-variant-numeric:tabular-nums}
.count::before{content:counter(num)}
@property --n{syntax:'<integer>';inherits:false;initial-value:0}
.qm{font-family:'Playfair Display',Georgia,serif;font-size:460px;line-height:.55;height:230px;color:var(--a);font-weight:900}
.q{font-weight:800}
.who{display:flex;align-items:center;gap:28px;font-size:46px;font-weight:600;color:var(--mut)}
.who i{display:block;width:90px;height:6px;border-radius:4px;background:var(--a)}
.cmp{display:flex;flex-direction:column;align-items:stretch;gap:0;position:relative}
.card{padding:48px 52px;border-radius:40px;background:var(--card);border:2px solid var(--cardb);font-size:58px;font-weight:700;line-height:1.28}
.card .tag{display:block;font-size:34px;letter-spacing:.14em;text-transform:uppercase;font-weight:800;margin-bottom:16px}
.c1{border-left:16px solid var(--a)}.c1 .tag{color:var(--a)}
.c2{border-left:16px solid var(--b)}.c2 .tag{color:var(--b)}
.vs{align-self:center;margin:-30px 0;z-index:2;width:120px;height:120px;border-radius:50%;display:flex;align-items:center;justify-content:center;
 font-size:44px;font-weight:900;color:var(--onacc);background:linear-gradient(135deg,var(--a),var(--b));border:8px solid #0A0F1F}

/* ảnh nền + Ken Burns */
.photo-layer{position:absolute;inset:0;background-size:cover;background-position:center;animation:kbin 16s linear both}
.kb-out .photo-layer{animation-name:kbout}.kb-left .photo-layer{animation-name:kbl}.kb-right .photo-layer{animation-name:kbr}
@keyframes kbin{from{transform:scale(1.03)}to{transform:scale(1.24)}}
@keyframes kbout{from{transform:scale(1.24)}to{transform:scale(1.03)}}
@keyframes kbl{from{transform:scale(1.16) translateX(3.5%)}to{transform:scale(1.16) translateX(-3.5%)}}
@keyframes kbr{from{transform:scale(1.16) translateX(-3.5%)}to{transform:scale(1.16) translateX(3.5%)}}
.shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.58) 0%,rgba(0,0,0,.22) 36%,rgba(0,0,0,.55) 66%,rgba(0,0,0,.88) 100%)}
body.photo{--fg:#fff;--mut:#E2E8F0;--card:rgba(255,255,255,.14);--cardb:rgba(255,255,255,.28);--onacc:#0A0F1F}

/* ── Chủ đề: aurora ── */
.th-aurora .bg{background:linear-gradient(165deg,#0A0F1F 0%,#111A38 55%,#1B1238 100%)}
.th-aurora .blob{position:absolute;width:1300px;height:1300px;border-radius:50%}
.th-aurora .b1{left:-520px;top:-340px;opacity:.5;background:radial-gradient(circle,var(--a) 0%,transparent 62%)}
.th-aurora .b2{right:-640px;top:520px;opacity:.5;background:radial-gradient(circle,var(--b) 0%,transparent 62%)}
.th-aurora .b3{left:-320px;bottom:-760px;opacity:.3;background:radial-gradient(circle,#22D3EE 0%,transparent 62%)}
.live.th-aurora .blob{animation:drift 14s ease-in-out infinite alternate}
@keyframes drift{from{transform:translate(0,0) scale(1)}to{transform:translate(120px,-90px) scale(1.15)}}

/* ── neon ── */
.th-neon{--fh:'Montserrat','Be Vietnam Pro','Noto Sans',sans-serif;--hl:rgba(244,114,182,.55);--card:rgba(34,211,238,.07);--cardb:rgba(34,211,238,.45)}
.th-neon .bg{background:radial-gradient(900px 700px at 85% 8%,rgba(244,114,182,.38),transparent 62%),
 radial-gradient(1000px 800px at 5% 92%,rgba(34,211,238,.30),transparent 62%),#05060F}
.th-neon .grid{position:absolute;left:-120%;right:-120%;bottom:0;height:3000px;opacity:.55;
 background:linear-gradient(var(--a) 3px,transparent 3px) 0 0/110px 110px,linear-gradient(90deg,var(--a) 3px,transparent 3px) 0 0/110px 110px;
 transform:perspective(1200px) rotateX(58deg);transform-origin:50% 100%;animation:gridmove 2.4s linear infinite;
 -webkit-mask-image:linear-gradient(transparent 0%,#000 40%)}
@keyframes gridmove{from{background-position:0 0,0 0}to{background-position:0 110px,0 0}}
.th-neon .ring{position:absolute;right:-380px;top:120px;width:900px;height:900px;border-radius:50%;border:8px solid var(--b);opacity:.35;
 box-shadow:0 0 90px var(--b),inset 0 0 90px var(--b);animation:spin 16s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.th-neon .scan{position:absolute;inset:0;background:repeating-linear-gradient(transparent 0 3px,rgba(0,0,0,.22) 3px 4px);opacity:.55}
.th-neon h1,.th-neon h2{text-shadow:0 0 36px color-mix(in srgb,var(--a) 55%,transparent)}
.th-neon h1.grad,.th-neon h2.grad{text-shadow:none}
.th-neon .grad{filter:drop-shadow(0 0 22px color-mix(in srgb,var(--b) 55%,transparent))}

/* ── noir ── */
.th-noir{--fh:'Playfair Display',Georgia,'Noto Serif',serif;--hl:rgba(239,68,68,.6);--onacc:#0A0A0B}
.th-noir .bg{background:radial-gradient(1300px 1500px at 50% 38%,#202024 0%,#0A0A0B 72%)}
.th-noir .leak{position:absolute;left:-400px;top:-300px;width:1200px;height:1200px;border-radius:50%;
 background:radial-gradient(circle,rgba(239,68,68,.34),transparent 62%)}
.th-noir .grain{position:absolute;inset:-100px;opacity:.16;mix-blend-mode:overlay;
 background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='320' height='320'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>")}
.th-noir .lbx{position:absolute;left:0;right:0;height:150px;background:#000;z-index:5}
.th-noir .lbx.t{top:0;border-bottom:4px solid var(--b)}.th-noir .lbx.b{bottom:0;border-top:4px solid var(--b)}
.th-noir .wrap{padding-top:260px}
.th-noir .sub,.th-noir .who{font-family:var(--fb)}

/* ── paper (giấy sáng) ── */
.th-paper{--fg:#1B1B1F;--mut:#5B5B66;--card:rgba(255,255,255,.7);--cardb:rgba(0,0,0,.14);--onacc:#FFF8EC;--hl:rgba(194,65,12,.30);
 --fh:'Playfair Display',Georgia,'Noto Serif',serif;background:#F3EEE3}
.th-paper .bg{background:#F3EEE3}
.th-paper .sh1{position:absolute;right:-330px;top:-400px;width:760px;height:760px;border-radius:50%;background:var(--a);opacity:.92}
.th-paper .sh2{position:absolute;left:-470px;bottom:-190px;width:760px;height:460px;border-radius:70px;background:var(--b);transform:rotate(-14deg);opacity:.9}
.th-paper .dots{position:absolute;left:60px;top:90px;width:300px;height:200px;opacity:.5;
 background:radial-gradient(circle,#1B1B1F 4px,transparent 5px) 0 0/40px 40px}
.th-paper .grad{background:none;color:var(--fg);-webkit-text-fill-color:var(--fg)}
.th-paper .center .grad{color:var(--a);-webkit-text-fill-color:var(--a)}
.th-paper .bar,.th-paper .cta,.th-paper .ico,.th-paper .logo{background:var(--a)}
.th-paper .foot{color:#6B6B76}
.th-paper .vs{border-color:#F3EEE3}
.th-paper .sub,.th-paper .who{font-family:var(--fb)}

/* ── sunset ── */
.th-sunset{--hl:rgba(253,224,71,.5);--onacc:#2B0A3D}
.th-sunset .bg{background:linear-gradient(180deg,#1E0A3C 0%,#5B1A64 34%,#C2306A 62%,#F2703C 82%,#FFB347 100%)}
.th-sunset .sun{position:absolute;left:50%;bottom:130px;width:620px;height:620px;margin-left:-310px;border-radius:50%;
 background:linear-gradient(180deg,var(--a) 0%,var(--b) 100%);
 -webkit-mask:linear-gradient(#000,#000) top/100% 52% no-repeat,repeating-linear-gradient(#000 0 30px,transparent 30px 46px) bottom/100% 48% no-repeat;
 animation:sunrise 2.2s cubic-bezier(.2,.8,.2,1) both}
@keyframes sunrise{from{transform:translateY(260px);opacity:0}to{transform:none;opacity:1}}
.th-sunset .wrap{padding-bottom:640px}
.th-sunset h1,.th-sunset h2,.th-sunset li,.th-sunset .sub{text-shadow:0 4px 34px rgba(30,5,50,.65)}
.th-sunset h1.grad,.th-sunset h2.grad{text-shadow:none;filter:drop-shadow(0 4px 22px rgba(30,5,50,.7))}
.th-sunset .hor{position:absolute;left:0;right:0;bottom:0;height:300px;background:#12061F;
 clip-path:polygon(0 38%,10% 20%,20% 34%,31% 8%,44% 30%,55% 14%,68% 36%,80% 12%,92% 30%,100% 18%,100% 100%,0 100%)}

/* ── mono ── */
.th-mono{--fh:'Montserrat','Be Vietnam Pro','Noto Sans',sans-serif;--hl:rgba(250,204,21,.7);--onacc:#0A0A0A;--card:rgba(255,255,255,.06);--cardb:rgba(255,255,255,.9)}
.th-mono .bg{background:#0A0A0A}
.th-mono .vl{position:absolute;inset:0;background:repeating-linear-gradient(90deg,rgba(255,255,255,.07) 0 2px,transparent 2px 135px)}
.th-mono .blk{position:absolute;left:0;top:150px;height:44px;width:340px;background:var(--a);transform-origin:left;animation:grow .8s ease-out both}
.th-mono .bignum{position:absolute;right:-30px;bottom:110px;font-family:var(--fh);font-weight:900;font-size:760px;line-height:.8;
 color:transparent;-webkit-text-stroke:4px rgba(255,255,255,.16);letter-spacing:-.05em}
.th-mono h1,.th-mono h2{text-transform:uppercase;letter-spacing:-.02em}
.th-mono .grad{background:none;color:var(--a);-webkit-text-fill-color:var(--a)}
.th-mono .pill,.th-mono .cta,.th-mono li,.th-mono .card,.th-mono .url{border-radius:0}
.th-mono .pill{background:var(--a);color:#0A0A0A;border-color:var(--a)}
.th-mono .ico{border-radius:0}
.th-mono .logo{border-radius:0}.th-mono .logo::after{display:none}
.th-mono .bar{border-radius:0;height:20px}
"""

DECOR = {
    "aurora": '<div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div>',
    "neon": '<div class="ring"></div><div class="grid"></div><div class="scan"></div>',
    "noir": '<div class="leak"></div><div class="grain"></div>',
    "paper": '<div class="sh1"></div><div class="sh2"></div><div class="dots"></div>',
    "sunset": '<div class="sun"></div><div class="hor"></div>',
    "mono": '<div class="vl"></div><div class="blk"></div>',
}
OVERLAY = {
    "noir": '<div class="lbx t"></div><div class="lbx b"></div>',
}

PAGE = """<!doctype html><html lang="vi" style="--a:%%A%%;--b:%%B%%"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@500;700;800;900&family=Playfair+Display:wght@700;900&family=Montserrat:wght@700;800;900&display=block" rel="stylesheet">
<style>%%CSS%%</style></head><body class="%%CLS%%">
<div class="bg">%%DECOR%%</div>%%PHOTO%%
%%BODY%%%%OVERLAY%%</body></html>"""


# ── tiện ích ──────────────────────────────────────────────────────────────────
def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def plain(s: str) -> str:
    return str(s or "").replace("*", "")


def _fs(text: str, steps) -> int:
    longest = max((len(l) for l in plain(text).splitlines()), default=0) or 1
    for limit, px in steps:
        if longest <= limit:
            return px
    return steps[-1][1]


def _color(c: str, default: str) -> str:
    return c if re.fullmatch(r"#[0-9a-fA-F]{6}", c or "") else default


def palette(st: dict) -> tuple[str, str]:
    th = THEMES.get(st.get("theme"), THEMES["aurora"])
    if st.get("custom_colors"):
        return _color(st.get("accent_from"), th["a"]), _color(st.get("accent_to"), th["b"])
    return th["a"], th["b"]


def auto_mark(text: str) -> str:
    """Nếu người dùng chưa đánh dấu *từ nhấn*, tự chọn số/từ viết hoa/từ dài nhất."""
    if "*" in text:
        return text
    words = text.split()
    if len(words) < 4:
        return text
    pick = [i for i, w in enumerate(words) if re.search(r"\d", w) or (len(w) >= 2 and w.isalpha() and w.isupper())]
    if not pick:
        longest = max(range(len(words)), key=lambda i: len(re.sub(r"\W", "", words[i])))
        if len(re.sub(r"\W", "", words[longest])) >= 6:
            pick = [longest]
    for i in pick[:2]:
        words[i] = f"*{words[i]}*"
    return " ".join(words)


def words_html(text: str, step: float, start: float, mark: bool = True) -> str:
    out, on = [], False
    for i, w in enumerate(text.split()):
        hl = on
        if w.startswith("*"):
            on = hl = True
            w = w[1:]
        if w.endswith("*"):
            on = False
            w = w[:-1]
        w = esc(w)
        d = start + i * step
        inner = f'<mark style="--d:{d + 0.5:.2f}s">{w}</mark>' if (hl and mark) else w
        out.append(f'<span class="w" style="--d:{d:.2f}s">{inner}</span>')
    return "".join(out)


def _kicker(s, d=".1s"):
    return f'<div class="pill rise" style="--d:{d}">{esc(plain(s["kicker"]))}</div>' if s["kicker"] else ""


def _sub(s, d="1s"):
    return f'<p class="sub rise" style="--d:{d}">{esc(plain(s["sub"]))}</p>' if s["sub"] else ""


def _foot(st):
    return f'<div class="foot">{esc(st["brand"])}</div>' if st.get("brand") else ""


def _count(headline: str):
    m = re.fullmatch(r"(\D*?)(\d{1,9})(\D*)", plain(headline).strip())
    return m.groups() if m else None


# ── các mẫu cảnh ──────────────────────────────────────────────────────────────
def hero(s, st):
    fs = _fs(s["headline"], [(10, 220), (16, 176), (26, 140), (40, 112), (999, 92)])
    return f"""<div class="wrap">{_kicker(s,".2s")}
<h1 class="grad rise" style="--d:.5s;font-size:{fs}px">{esc(plain(s["headline"]))}</h1>
{_sub(s,"1s")}<div class="cta pop" style="--d:1.4s">{esc(st["brand"])}</div></div>"""


def stat(s, st):
    fs = _fs(s["headline"], [(3, 380), (5, 250), (7, 200), (10, 160), (999, 120)])
    c = _count(s["headline"])
    if c:
        pre, num, suf = c
        style = f"<style>@keyframes count{{from{{--n:0}}to{{--n:{int(num)}}}}}.count{{animation:count 1.5s cubic-bezier(.2,.8,.2,1) .4s both}}</style>"
        inner = f'{esc(pre)}<span class="count"></span>{esc(suf)}'
    else:
        style, inner = "", esc(plain(s["headline"]))
    return f"""{style}<div class="wrap center">{_kicker(s,".1s")}
<h1 class="grad pop" style="--d:.3s;font-size:{fs}px;white-space:nowrap">{inner}</h1>
<div class="bar grow" style="--d:1.1s"></div>{_sub(s,"1.3s")}</div>{_foot(st)}"""


def statement(s, st):
    text = auto_mark(s["headline"])
    n = max(len(text.split()), 1)
    fs = _fs(s["headline"], [(40, 100), (80, 84), (140, 72), (999, 60)])
    cls = "center" if s.get("n", 1) % 2 == 0 else ""
    return f"""<div class="wrap {cls}">{_kicker(s,".1s")}
<h2 style="font-size:{fs}px">{words_html(text, min(0.07, 1.6 / n), 0.3)}</h2>{_sub(s,"1.9s")}</div>{_foot(st)}"""


def listing(s, st):
    fs = _fs(s["headline"], [(18, 104), (30, 86), (999, 70)])
    rows = []
    for i, raw in enumerate(s["items"][:5]):
        m = re.match(r"^(\S)\s+(.*)$", raw)
        if m and not m.group(1).isalnum():
            icon, text = m.group(1), m.group(2)
        else:
            icon, text = str(i + 1), raw
        rows.append(f'<li class="rise" style="--d:{0.7 + i * 0.28:.2f}s"><span class="ico">{esc(icon)}</span><span>{esc(plain(text))}</span></li>')
    return f"""<div class="wrap">{_kicker(s,".1s")}
<h2 class="grad rise" style="--d:.3s;font-size:{fs}px">{esc(plain(s["headline"]))}</h2>
<ul>{"".join(rows)}</ul></div>{_foot(st)}"""


def quote(s, st):
    text = auto_mark(s["headline"])
    n = max(len(text.split()), 1)
    fs = _fs(s["headline"], [(60, 84), (120, 72), (999, 60)])
    who = f'<div class="who rise" style="--d:1.9s"><i></i>{esc(plain(s["sub"]))}</div>' if s["sub"] else ""
    return f"""<div class="wrap">{_kicker(s,".1s")}<div class="qm pop" style="--d:.15s">“</div>
<h2 class="q" style="font-size:{fs}px">{words_html(text, min(0.06, 1.5 / n), 0.5)}</h2>{who}</div>{_foot(st)}"""


def compare(s, st):
    tags = [t.strip() for t in plain(s["sub"]).split("|")] + ["", ""]
    items = (s["items"] + ["", ""])[:2]
    fs = _fs("\n".join(items), [(40, 62), (80, 54), (999, 46)])
    title = f'<h2 class="grad rise" style="--d:.2s;font-size:84px">{esc(plain(s["headline"]))}</h2>' if s["headline"] else ""
    return f"""<div class="wrap">{_kicker(s,".1s")}{title}
<div class="cmp"><div class="card c1 rise" style="--d:.6s;font-size:{fs}px"><span class="tag">{esc(tags[0] or "A")}</span>{esc(plain(items[0]))}</div>
<div class="vs pop" style="--d:1.1s">VS</div>
<div class="card c2 rise" style="--d:1.4s;font-size:{fs}px"><span class="tag">{esc(tags[1] or "B")}</span>{esc(plain(items[1]))}</div></div></div>{_foot(st)}"""


def image(s, st):
    text = auto_mark(s["headline"])
    n = max(len(text.split()), 1)
    fs = _fs(s["headline"], [(30, 110), (60, 92), (110, 78), (999, 64)])
    return f"""<div class="wrap low">{_kicker(s,".2s")}
<h2 style="font-size:{fs}px">{words_html(text, min(0.07, 1.4 / n), 0.5)}</h2>{_sub(s,"1.8s")}</div>{_foot(st)}"""


def outro(s, st):
    name = s["headline"] or st["brand"]
    initial = (plain(name).strip()[:1] or "A").upper()
    tag = s["sub"] or st.get("tagline", "")
    url = f'<div class="url rise" style="--d:1.2s">{esc(st["url"])}</div>' if st.get("url") else ""
    return f"""<div class="wrap center" style="gap:50px"><div class="logo pop" style="--d:.2s">{esc(initial)}</div>
<h1 class="grad rise" style="--d:.7s;font-size:{_fs(name,[(12,130),(22,100),(999,78)])}px">{esc(plain(name))}</h1>
<p class="sub rise" style="--d:1s">{esc(plain(tag))}</p>{url}</div>"""


RENDERERS = {"hero": hero, "stat": stat, "statement": statement, "list": listing,
             "quote": quote, "compare": compare, "image": image, "outro": outro}


def build_html(scene: dict, st: dict, photo_uri: str | None = None) -> str:
    theme = st.get("theme") if st.get("theme") in THEMES else "aurora"
    a, b = palette(st)
    n = int(scene.get("n") or 1)
    fx = scene.get("fx") if scene.get("fx") in FX else FX[(n - 1) % len(FX)]
    kb = ["in", "out", "left", "right"][(n - 1) % 4]
    cls = [f"th-{theme}", f"fx-{fx}", f"kb-{kb}"]
    if photo_uri:
        cls.append("photo")
    if st.get("continuous"):
        cls.append("live")
    photo = (
        f'<div class="photo-layer" style="background-image:url(\'{photo_uri}\')"></div><div class="shade"></div>'
        if photo_uri else ""
    )
    decor = DECOR[theme]
    if theme == "mono":
        decor += f'<div class="bignum">{n:02d}</div>'
    body = RENDERERS[scene["template"]](scene, st)
    return (
        PAGE.replace("%%CSS%%", CSS)
        .replace("%%CLS%%", " ".join(cls))
        .replace("%%A%%", a).replace("%%B%%", b)
        .replace("%%DECOR%%", decor)
        .replace("%%PHOTO%%", photo)
        .replace("%%OVERLAY%%", OVERLAY.get(theme, ""))
        .replace("%%BODY%%", body)
    )
