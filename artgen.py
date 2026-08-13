#!/usr/bin/env python3
"""
Simetrik cekici (attractor) gorsel ureteci.

Yuklenen ornekteki gibi: siyah zemin uzerinde canli renkli,
aynalanmis organik filament desenleri.

Tamamen kod ile uretilir:
  - dis API yok, internet yok, telif yok
  - her seed farkli desen -> sinirsiz cesit
  - deterministik (ayni seed = ayni gorsel)
"""

import numpy as np
from PIL import Image, ImageFilter

# ------------------------------------------------------------ renk paletleri

PALETTES = {
    # cok tonlu paletler - tek renk yerine gecisli
    "aurora":  [(0,0,0), (8,20,60), (0,110,150), (30,200,190), (140,240,170), (245,255,220)],
    "nebula":  [(0,0,0), (30,8,70), (110,25,160), (215,60,190), (255,140,210), (255,235,250)],
    "prism":   [(0,0,0), (15,25,85), (0,150,165), (90,220,150), (230,190,60), (255,245,215)],
    "orchid":  [(0,0,0), (20,10,55), (95,35,175), (190,70,215), (110,215,225), (240,240,255)],
    "reef":    [(0,0,0), (5,35,75), (15,125,175), (40,205,195), (200,225,110), (255,250,225)],
    "ember":   [(0,0,0), (45,10,35), (150,35,60), (235,120,50), (250,200,90), (255,245,215)],
    "spectra": [(0,0,0), (25,15,80), (0,145,160), (150,55,195), (245,180,90), (255,240,200)],
}


def _ramp(palette, size=1024):
    """Palet duraklarindan yumusak renk rampasi."""
    stops = np.array(palette, dtype=np.float64)
    k = len(stops)
    xs = np.linspace(0, k - 1, size)
    idx = np.clip(xs.astype(int), 0, k - 2)
    frac = (xs - idx)[:, None]
    return (stops[idx] * (1 - frac) + stops[idx + 1] * frac)


def _autocrop(dens, keep=0.992, margin=0.03):
    """
    Desenin GORSEL sinirlarini bul ve oraya kirp.
    Yuzdelik tabanli: cok soluk uzak pikseller cerceveyi genisletmesin,
    yoksa kenarlarda siyah bantlar kalir.
    """
    if dens.max() <= 0:
        return dens

    row = dens.sum(axis=1)
    col = dens.sum(axis=0)

    def bounds(v):
        c = np.cumsum(v)
        if c[-1] <= 0:
            return 0, len(v) - 1
        c = c / c[-1]
        lo = float((1 - keep) / 2)
        hi = float(1 - lo)
        a = int(np.searchsorted(c, lo))
        b = int(np.searchsorted(c, hi))
        return a, max(a + 10, b)

    r0, r1 = bounds(row)
    c0, c1 = bounds(col)

    h, w = dens.shape
    mr = int((r1 - r0) * margin)
    mc = int((c1 - c0) * margin)
    r0 = max(0, r0 - mr); r1 = min(h - 1, r1 + mr)
    c0 = max(0, c0 - mc); c1 = min(w - 1, c1 + mc)

    if r1 - r0 < 40 or c1 - c0 < 40:
        return dens
    return dens[r0:r1 + 1, c0:c1 + 1]


def _attractor_points(rng, n_traj=140_000, steps=110):
    """
    de Jong cekicisi - ince filament yapilari uretir.
    Paralel yorunge ile vektorlestirilmis (hizli).
    """
    a, b, c, d = rng.uniform(-3.0, 3.0, 4)

    x = rng.uniform(-2, 2, n_traj)
    y = rng.uniform(-2, 2, n_traj)

    xs = np.empty((steps, n_traj), dtype=np.float32)
    ys = np.empty((steps, n_traj), dtype=np.float32)

    for i in range(steps):
        x, y = np.sin(a * y) - np.cos(b * x), np.sin(c * x) - np.cos(d * y)
        xs[i] = x
        ys[i] = y

    return xs.ravel(), ys.ravel(), (a, b, c, d)


def _density(px, py, w, h):
    """Noktalari yogunluk haritasina cevir."""
    lo, hi = -2.2, 2.2
    m = (px > lo) & (px < hi) & (py > lo) & (py < hi)
    px, py = px[m], py[m]

    ix = ((px - lo) / (hi - lo) * (w - 1)).astype(np.int32)
    iy = ((py - lo) / (hi - lo) * (h - 1)).astype(np.int32)

    dens = np.zeros(w * h, dtype=np.float32)
    np.add.at(dens, iy * w + ix, 1.0)
    return dens.reshape(h, w)


def make_art(seed, width=2560, height=1440, palette=None, symmetry="mirror"):
    """Simetrik cekici gorseli uret."""
    rng = np.random.default_rng(seed)

    if palette is None:
        palette = str(rng.choice(list(PALETTES.keys())))

    # kare tuvalde uret, sonra kirp (desen bozulmasin)
    side = max(width, height)
    side = min(side, 2600)

    px, py, params = _attractor_points(rng)
    dens = _density(px, py, side, side)

    # log olcekle -> ince detaylar gorunur
    dens = np.log1p(dens)
    if dens.max() > 0:
        dens /= dens.max()

    # simetri
    if symmetry == "mirror":
        dens = np.maximum(dens, dens[:, ::-1])
    elif symmetry == "quad":
        dens = np.maximum(dens, dens[:, ::-1])
        dens = np.maximum(dens, dens[::-1, :])

    # deseni cerceveye otur
    dens = _autocrop(dens)

    # kontrast egrisi - siyah zemin derin kalsin, parlak yerler patlasin
    dens = np.clip(dens, 0, 1) ** 0.72

    # renklendir: yogunluk + konuma gore ton kaymasi (cok renkli gorunum)
    hh, ww = dens.shape
    yy = np.linspace(-1, 1, hh)[:, None]
    xx = np.linspace(-1, 1, ww)[None, :]
    radius = np.sqrt(xx ** 2 + yy ** 2) / 1.4142
    shift = rng.uniform(0.10, 0.26)
    pos = np.clip(dens * (1.0 - shift) + radius * shift, 0, 1)

    ramp = _ramp(PALETTES[palette])
    idx = np.clip((pos * (len(ramp) - 1)).astype(np.int32), 0, len(ramp) - 1)
    rgb = ramp[idx]
    # parlaklik yogunluktan gelsin - bos alanlar siyah kalsin
    rgb = rgb * np.clip(dens * 1.15, 0, 1)[:, :, None]
    rgb = rgb.astype(np.uint8)

    img = Image.fromarray(rgb, "RGB")

    # hafif parlama (glow) - canli gorunum
    glow = img.filter(ImageFilter.GaussianBlur(radius=side / 260))
    img = Image.blend(img, glow, 0.34)
    img = Image.blend(img, img.filter(ImageFilter.GaussianBlur(radius=1.2)), 0.18)

    # hedef orana doldur (kirpilmis desen cerceveyi kaplasin)
    tw, th = width, height
    scale = max(tw / img.width, th / img.height)
    nw = max(tw, int(img.width * scale) + 1)
    nh = max(th, int(img.height * scale) + 1)
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (img.width - tw) // 2
    top = (img.height - th) // 2
    img = img.crop((left, top, left + tw, top + th))

    meta = {"palette": palette, "symmetry": symmetry,
            "attractor": [round(float(v), 3) for v in params]}
    return img, meta


def is_interesting(img, min_ink=0.10, max_ink=0.72):
    """
    Bos, asiri seyrek veya asiri dolu gorselleri ele.
    Bazi parametreler tek cizgi / tam ekran leke uretir.
    """
    a = np.asarray(img.convert("L"), dtype=np.float32) / 255.0
    ink = float((a > 0.10).mean())
    if not (min_ink < ink < max_ink):
        return False, ink
    if float(a.std()) < 0.075:
        return False, ink
    # merkez gercekten dolu mu (kenara yapisik kompozisyonlari ele)
    h, w = a.shape
    mid = a[int(h * 0.22):int(h * 0.78), int(w * 0.22):int(w * 0.78)]
    if float((mid > 0.10).mean()) < 0.16:
        return False, ink
    return True, ink


def generate(seed, width=2560, height=1440, palette=None, symmetry="mirror",
             tries=14):
    """Ilginc bir gorsel bulana kadar dene."""
    for k in range(tries):
        img, meta = make_art(seed + k * 9973, width, height, palette, symmetry)
        ok, ink = is_interesting(img)
        if ok:
            meta["ink"] = round(ink, 4)
            meta["attempt"] = k + 1
            return img, meta
    meta["ink"] = round(ink, 4)
    meta["attempt"] = tries
    return img, meta


if __name__ == "__main__":
    import argparse, json
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--out", default="art.png")
    p.add_argument("--palette", default=None)
    p.add_argument("--symmetry", default="mirror", choices=["mirror", "quad", "none"])
    p.add_argument("--width", type=int, default=2560)
    p.add_argument("--height", type=int, default=1440)
    a = p.parse_args()

    img, meta = generate(a.seed, a.width, a.height, a.palette, a.symmetry)
    img.save(a.out)
    print(json.dumps(meta, indent=2))
