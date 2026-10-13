"""Chuyển số/ký hiệu trong lời đọc sang chữ tiếng Việt để giọng đọc không đọc sai."""
from __future__ import annotations

import re

_D = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
_UNITS = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ"]

UNIT_WORDS = {
    "mAh": "miliampe giờ", "GHz": "gigahéc", "MHz": "megahéc", "Hz": "héc",
    "MP": "megapixel", "GB": "gigabyte", "TB": "terabyte", "MB": "megabyte",
    "KB": "kilobyte", "kg": "ki lô gam", "km": "ki lô mét", "cm": "xen ti mét",
    "mm": "mi li mét", "ms": "mi li giây", "fps": "khung hình trên giây",
}

_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200d]")


def _group(n: int, full: bool) -> str:
    tram, rest = divmod(n, 100)
    chuc, donvi = divmod(rest, 10)
    out = []
    if tram or full:
        out.append(f"{_D[tram]} trăm")
    if chuc == 0:
        if donvi:
            out.append((f"linh {_D[donvi]}") if (tram or full) else _D[donvi])
    elif chuc == 1:
        out.append("mười" + ("" if donvi == 0 else " " + ("lăm" if donvi == 5 else _D[donvi])))
    else:
        s = f"{_D[chuc]} mươi"
        if donvi == 1:
            s += " mốt"
        elif donvi == 5:
            s += " lăm"
        elif donvi:
            s += " " + _D[donvi]
        out.append(s)
    return " ".join(out)


def int_to_words(n: int) -> str:
    if n == 0:
        return _D[0]
    if n >= 10**15:
        return " ".join(_D[int(c)] for c in str(n))
    groups = []
    while n:
        n, g = divmod(n, 1000)
        groups.append(g)
    parts, started = [], False
    for idx in range(len(groups) - 1, -1, -1):
        g = groups[idx]
        if g == 0:
            continue
        text = _group(g, full=started)
        unit = _UNITS[idx]
        parts.append(f"{text} {unit}".strip())
        started = True
    return " ".join(parts)


def _digits(s: str) -> str:
    return " ".join(_D[int(c)] for c in s)


def number_to_words(token: str) -> str:
    # 1.234.567 hoặc 1.234.567,5  → kiểu Việt (dấu chấm ngăn cách hàng nghìn)
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", token):
        ip, _, frac = token.partition(",")
        words = int_to_words(int(ip.replace(".", "")))
        return words + (f" phẩy {_digits(frac)}" if frac else "")
    m = re.fullmatch(r"(\d+)([.,])(\d+)", token)
    if m:
        ip, sep, frac = m.groups()
        head = _digits(ip) if (len(ip) > 1 and ip.startswith("0")) else int_to_words(int(ip))
        return f"{head} {'chấm' if sep == '.' else 'phẩy'} {_digits(frac)}"
    if len(token) > 1 and token.startswith("0"):
        return _digits(token)
    return int_to_words(int(token))


_NUM = r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?"
_UNIT_ALT = "|".join(sorted(map(re.escape, UNIT_WORDS), key=len, reverse=True))
_PATTERN = re.compile(
    rf"(?P<cur>\$\s?)?(?P<num>{_NUM})(?P<pct>\s?%)?(?P<unit>\s?(?:{_UNIT_ALT})(?![A-Za-z0-9]))?"
)


def _repl(m: re.Match) -> str:
    words = number_to_words(m.group("num"))
    if m.group("cur"):
        words += " đô la"
    if m.group("pct"):
        words += " phần trăm"
    if m.group("unit"):
        words += " " + UNIT_WORDS[m.group("unit").strip()]
    return words


def speakable(text: str, numbers: bool = True) -> str:
    """Làm sạch lời đọc: bỏ emoji/ký hiệu, (tuỳ chọn) đọc số thành chữ."""
    t = _EMOJI.sub(" ", text)
    if numbers:
        t = _PATTERN.sub(_repl, t)
    t = t.replace("&", " và ")
    t = re.sub(r"[→←↑↓#=*_~^|<>]", " ", t)
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if t and t[-1] not in ".!?…":
        t += "."
    return t
