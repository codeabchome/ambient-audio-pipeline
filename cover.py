#!/usr/bin/env python3
"""
Kapak yazisi katmani.

Gorselin uzerine baslikla uyumlu, amaca gore font secilen zarif bir
metin duzeni yerlestirir. Kapak tiklanma oranini dogrudan etkiler.
"""

import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_DIR = Path("fonts")
GF = "https://raw.githubusercontent.com/google/fonts/main"

# amaca gore ruh haline uygun font
FONT_SOURCES = {
    "CormorantGaramond.ttf": f"{GF}/ofl/cormorantgaramond/CormorantGaramond%5Bwght%5D.ttf",
    "Marcellus.ttf":         f"{GF}/ofl/marcellus/Marcellus-Regular.ttf",
    "Raleway.ttf":           f"{GF}/ofl/raleway/Raleway%5Bwght%5D.ttf",
    "JosefinSans.ttf":       f"{GF}/ofl/josefinsans/JosefinSans%5Bwght%5D.ttf",
    "PlayfairDisplay.ttf":   f"{GF}/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
}

# (ana font, alt font)  - amaca gore his
MOOD_FONTS = {
    "sleep":      ("CormorantGaramond.ttf", "Raleway.ttf"),
    "meditation": ("Marcellus.ttf",         "Raleway.ttf"),
    "relax":      ("PlayfairDisplay.ttf",   "Raleway.ttf"),
    "focus":      ("JosefinSans.ttf",       "Raleway.ttf"),
    "study":      ("JosefinSans.ttf",       "Raleway.ttf"),
}

FALLBACK = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FALLBACK_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"


def ensure_fonts():
    """Fontlari indir (yoksa). GitHub uzerinden - Actions'ta erisilebilir."""
    FONT_DIR.mkdir(exist_ok=True)
    for name, url in FONT_SOURCES.items():
        p = FONT_DIR / name
        if p.exists() and p.stat().st_size > 20000:
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            if len(data) > 20000:
                p.write_bytes(data)
        except Exception as e:
            print(f"  font inmedi ({name}): {e}")


def _load(name, size):
    p = FONT_DIR / name
    try:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    except Exception:
        pass
    for fb in (FALLBACK_SERIF, FALLBACK):
        try:
            return ImageFont.truetype(fb, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _tracked(draw, xy, text, font, fill, tracking=0, anchor_center_x=None):
    """Harf araligi (tracking) ile metin ciz - zarif gorunum."""
    x, y = xy
    if tracking == 0:
        draw.text((x, y), text, font=font, fill=fill)
        return

    widths = [draw.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    if anchor_center_x is not None:
        x = anchor_center_x - total / 2
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=font, fill=fill)
        x += w + tracking
    return total


def _tracked_width(draw, text, font, tracking):
    widths = [draw.textlength(ch, font=font) for ch in text]
    return sum(widths) + tracking * (len(text) - 1)


def _scrim(img, strength=0.55):
    """
    Metin bolgesine yumusak karartma perdesi.
    Yazinin desen uzerinde okunakli kalmasini saglar.
    """
    w, h = img.size
    y = np.linspace(0, 1, h)[:, None]
    # merkeze dogru koyulasan yatay bant
    band = np.exp(-((y - 0.5) ** 2) / (2 * 0.20 ** 2))
    mask = (band * strength * 255).astype(np.uint8)
    mask = np.repeat(mask, w, axis=1)
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(dark, img, Image.fromarray(mask, "L"))


def add_text(img, hz, name_label, benefit_label, duration_label,
             purpose="sleep", channel="TONEBED"):
    """
    Kapak yazisini yerlestir.
    Duzen:
        [kanal adi]        - ust, kucuk, genis aralikli
        963Hz              - buyuk, ana odak
        STUDY MUSIC        - orta, genis aralikli
        Rain Sounds - 1 Hour  - alt, ince
    """
    ensure_fonts()
    img = img.convert("RGB")
    W, H = img.size

    main_f, sub_f = MOOD_FONTS.get(purpose, MOOD_FONTS["sleep"])

    img = _scrim(img, 0.50)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    s = H / 1440.0  # olcek

    f_channel = _load(sub_f,  int(42 * s))
    f_hz      = _load(main_f, int(275 * s))
    f_purpose = _load(sub_f,  int(108 * s))
    f_detail  = _load(sub_f,  int(62 * s))

    cx = W / 2
    white = (255, 255, 255, 255)
    soft = (232, 236, 245, 235)
    dim = (198, 208, 224, 210)

    # DIKKAT CEKICI vurgu: buyuk Hz sayisi amaca gore renklenir.
    # Kucuk onizlemede (320px) renkli sayi, beyaz yazidan cok daha
    # fazla goze carpar - tiklanma oranini dogrudan etkiler.
    ACCENT = {
        "sleep":      (140, 190, 255, 255),   # buz mavisi - gece hissi
        "meditation": (200, 170, 255, 255),   # eflatun - spiritüel
        "relax":      (130, 230, 200, 255),   # su yesili - ferahlik
        "focus":      (255, 205, 110, 255),   # sicak altin - enerji
        "study":      (255, 205, 110, 255),
    }
    accent = ACCENT.get(purpose, white)

    # dikey yerlesim
    total_h = 620 * s
    y = H / 2 - total_h / 2 - 40 * s

    # kanal adi
    _tracked(d, (0, y), channel, f_channel, dim,
             tracking=10 * s, anchor_center_x=cx)
    y += 76 * s

    # frekans - ana odak (vurgu renginde)
    hz_text = str(hz)
    wid = d.textlength(hz_text, font=f_hz)
    d.text((cx - wid / 2, y), hz_text, font=f_hz, fill=accent)
    y += 368 * s

    # ince ayirici cizgi
    lw = 190 * s
    d.line([(cx - lw, y), (cx + lw, y)], fill=(255, 255, 255, 90), width=max(1, int(2 * s)))
    y += 46 * s

    # amac
    # frekans adi - uzunluga gore kucult
    nm = name_label.upper() if name_label else ""
    fp = f_purpose
    while _tracked_width(d, nm, fp, 8 * s) > W * 0.86 and fp.size > int(52 * s):
        fp = _load(sub_f, fp.size - 4)
    if nm:
        _tracked(d, (0, y), nm, fp, soft, tracking=8 * s, anchor_center_x=cx)
    y += 138 * s

    # fayda + sure
    detail = f"{benefit_label}  ·  {duration_label}"
    fd = f_detail
    while _tracked_width(d, detail, fd, 4 * s) > W * 0.88 and fd.size > int(34 * s):
        fd = _load(sub_f, fd.size - 3)
    _tracked(d, (0, y), detail, fd, dim, tracking=4 * s, anchor_center_x=cx)

    # yumusak parlama - yazi desenden ayrilsin
    glow = layer.filter(ImageFilter.GaussianBlur(radius=max(2, int(9 * s))))
    img = Image.alpha_composite(img.convert("RGBA"), glow)
    img = Image.alpha_composite(img, layer)
    return img.convert("RGB")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--img", required=True)
    p.add_argument("--out", default="cover.png")
    p.add_argument("--hz", type=int, default=528)
    p.add_argument("--purpose", default="sleep")
    p.add_argument("--purpose-label", default="Deep Sleep Music")
    p.add_argument("--texture-label", default="Rain Sounds")
    p.add_argument("--duration", default="1 Hour")
    a = p.parse_args()

    im = Image.open(a.img)
    out = add_text(im, a.hz, a.purpose_label, a.texture_label,
                   a.duration, a.purpose)
    out.save(a.out)
    print("kaydedildi:", a.out)
