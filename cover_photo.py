#!/usr/bin/env python3
"""
Sinematik kapak: fotograf sahnesi + zarif genis-aralikli tipografi.

Ornek stil: okyanus manzarali oda + "F O C U S   M O D E"

Doga ve muzik videolari icin. Fotograf Pexels'ten gelir (tarif ile
eslesen sahne). PEXELS_KEY yoksa veya foto inmezse artgen'e duser.

Okunabilirlik: kucuk resim boyutunda (320px) yazi bolgesi kontrasti
olculur; yetersizse karartma perdesi otomatik artirilir.
"""

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import cover as covermod  # font yukleyici ve _tracked yardimcilarini kullan

PHOTO_API = "https://api.pexels.com/v1/search"

# tarif/amac -> fotograf sahne sorgulari (sinematik, insansiz tercih)
SCENES = {
    "rain_window":      ["rain on window cozy room", "rainy window evening",
                         "rain window city lights bokeh"],
    "rain_storm":       ["dark rainy window night", "storm clouds sea dark"],
    "fireplace":        ["cozy fireplace interior", "cabin fireplace warm light"],
    "fireplace_window": ["cozy cabin interior winter", "fireplace room window"],
    "ocean":            ["ocean sunset horizon calm", "sea view minimal dusk"],
    "stream":           ["forest stream sunlight", "creek moss forest"],
    "forest_morning":   ["misty forest sunrise", "sunbeams forest morning"],
    "forest_rain":      ["rain forest green leaves", "wet leaves forest"],
    "snow":             ["snowfall winter calm", "snowy forest evening"],
    "wind":             ["grass field golden hour", "wheat field sunset calm"],
    # muzik turleri
    "focus":            ["modern room ocean view sunset", "minimal desk window view",
                         "workspace window city dusk"],
    "sleep":            ["dim cozy bedroom night", "moonlight bedroom calm"],
    "meditation":       ["zen minimal interior", "calm horizon dusk minimal"],
    "piano":            ["grand piano dramatic light", "piano by window light"],
}


def fetch_photo(scene_key, seed, out_path):
    key = os.environ.get("PEXELS_KEY")
    if not key:
        return False
    import random
    rng = random.Random(seed)
    queries = SCENES.get(scene_key, SCENES["ocean"])
    query = rng.choice(queries)
    try:
        url = f"{PHOTO_API}?{urllib.parse.urlencode({'query': query, 'per_page': 20, 'orientation': 'landscape'})}"
        req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": "Mozilla/5.0 (tonebed-pipeline)"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
    except Exception as e:
        print(f"Pexels foto hatasi: {e}")
        return False
    photos = data.get("photos", [])
    if not photos:
        return False
    rng.shuffle(photos)
    for ph in photos[:6]:
        link = (ph.get("src") or {}).get("large2x") or (ph.get("src") or {}).get("large")
        if not link:
            continue
        try:
            req = urllib.request.Request(link, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                Path(out_path).write_bytes(r.read())
            if Path(out_path).stat().st_size > 60_000:
                print(f"Kapak fotografi indi: {query}")
                return True
        except Exception:
            continue
    return False


def _fit_cover(img, w=2560, h=1440):
    scale = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1),
                     Image.LANCZOS)
    x = (img.width - w) // 2
    y = (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


def _cinematic_grade(img):
    """Hafif sinematik ton: kontrast + hafif sicak/soguk denge."""
    from PIL import ImageEnhance
    img = ImageEnhance.Contrast(img).enhance(1.08)
    img = ImageEnhance.Color(img).enhance(1.06)
    # ust ve alt hafif vinyet
    w, h = img.size
    y = np.linspace(-1, 1, h)[:, None]
    vin = 1.0 - 0.28 * (np.abs(y) ** 2.2)
    arr = np.asarray(img, dtype=np.float64) * np.repeat(vin, w, axis=1)[:, :, None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _text_region_contrast(img, y_frac_top, y_frac_bot):
    """Yazi bolgesindeki ortalama parlaklik (0-255). Dusukse yazi okunur."""
    a = np.asarray(img.convert("L"), dtype=np.float64)
    h = a.shape[0]
    band = a[int(h * y_frac_top):int(h * y_frac_bot)]
    return float(band.mean())


def make_cinematic_cover(photo_path, title_main, title_sub, duration_label,
                         out_path, seed=0):
    """
    Fotograf + zarif tipografi.
    title_main: "FOCUS MODE" gibi kisa, buyuk metin
    title_sub:  altta ince aciklama
    """
    covermod.ensure_fonts()
    img = Image.open(photo_path).convert("RGB")
    img = _fit_cover(img)
    img = _cinematic_grade(img)
    W, H = img.size
    s = H / 1440.0

    # okunabilirlik: yazi bandi cok parlaksa perdeyi artir
    for strength in (0.30, 0.42, 0.55):
        test = _apply_scrim(img, strength)
        if _text_region_contrast(test, 0.36, 0.64) < 118:
            img2 = test
            break
        img2 = test

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    main = title_main.upper()
    f_main = covermod._load("CormorantGaramond.ttf", int(200 * s))
    tr = 34 * s
    while covermod._tracked_width(d, main, f_main, tr) > W * 0.9 and f_main.size > int(90 * s):
        f_main = covermod._load("CormorantGaramond.ttf", f_main.size - 8)

    f_sub = covermod._load("Raleway.ttf", int(46 * s))
    f_dur = covermod._load("Raleway.ttf", int(36 * s))

    cy = H * 0.47
    covermod._tracked(d, (0, cy - 120 * s), main, f_main,
                      (255, 255, 255, 255), tracking=tr, anchor_center_x=W / 2)

    # ince cizgi
    lw = min(W * 0.28, covermod._tracked_width(d, main, f_main, tr) * 0.5)
    d.line([(W/2 - lw, cy + 110 * s), (W/2 + lw, cy + 110 * s)],
           fill=(255, 255, 255, 110), width=max(1, int(2 * s)))

    sub = title_sub
    fs = f_sub
    while covermod._tracked_width(d, sub, fs, 6 * s) > W * 0.86 and fs.size > int(28 * s):
        fs = covermod._load("Raleway.ttf", fs.size - 3)
    covermod._tracked(d, (0, cy + 136 * s), sub, fs,
                      (235, 238, 245, 230), tracking=6 * s, anchor_center_x=W / 2)

    covermod._tracked(d, (0, cy + 208 * s), duration_label.upper(), f_dur,
                      (205, 212, 224, 200), tracking=8 * s, anchor_center_x=W / 2)

    glow = layer.filter(ImageFilter.GaussianBlur(max(2, int(10 * s))))
    outimg = Image.alpha_composite(img2.convert("RGBA"), glow)
    outimg = Image.alpha_composite(outimg, layer).convert("RGB")
    outimg.save(out_path)
    return True


def _apply_scrim(img, strength):
    """Orta banda yumusak karartma (yazi okunsun)."""
    w, h = img.size
    y = np.linspace(0, 1, h)[:, None]
    band = np.exp(-((y - 0.5) ** 2) / (2 * 0.22 ** 2))
    mask = (band * strength * 255).astype(np.uint8)
    mask = np.repeat(mask, w, axis=1)
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(dark, img, Image.fromarray(mask, "L"))
