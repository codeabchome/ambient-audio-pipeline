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


# ================================================================ yeni motorlar

def _colorize(dens, palette, rng, shift=0.18):
    """Yogunluk haritasini paletle boya (ortak yardimci)."""
    dens = np.clip(dens, 0, 1)
    hh, ww = dens.shape
    yy = np.linspace(-1, 1, hh)[:, None]
    xx = np.linspace(-1, 1, ww)[None, :]
    radius = np.sqrt(xx ** 2 + yy ** 2) / 1.4142
    pos = np.clip(dens * (1.0 - shift) + radius * shift, 0, 1)
    ramp = _ramp(PALETTES[palette])
    idx = np.clip((pos * (len(ramp) - 1)).astype(np.int32), 0, len(ramp) - 1)
    rgb = ramp[idx] * np.clip(dens * 1.15, 0, 1)[:, :, None]
    return Image.fromarray(rgb.astype(np.uint8), "RGB")


def make_waves(seed, width=2560, height=1440, palette=None):
    """Dalga alani: girisim yapan sinus dalgalari - su yuzeyi hissi."""
    rng = np.random.default_rng(seed)
    palette = palette or str(rng.choice(list(PALETTES.keys())))
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float64)
    xx /= width; yy /= height
    f = np.zeros((height, width))
    for _ in range(rng.integers(3, 6)):
        ang = rng.uniform(0, np.pi)
        freq = rng.uniform(4, 14)
        ph = rng.uniform(0, 6.28)
        f += np.sin(2*np.pi*freq*(xx*np.cos(ang)+yy*np.sin(ang)) + ph)
    # radyal modulasyon: merkezden dalgalanma
    r = np.sqrt((xx-0.5)**2 + (yy-0.5)**2)
    f += 1.4*np.sin(2*np.pi*rng.uniform(5, 11)*r + rng.uniform(0, 6.28))
    dens = (f - f.min()) / (f.max() - f.min())
    dens = np.abs(np.sin(dens * np.pi * rng.uniform(1.2, 2.0))) ** 2.6
    dens *= 0.75
    img = _colorize(dens, palette, rng, 0.25)
    img = Image.blend(img, img.filter(ImageFilter.GaussianBlur(6)), 0.5)
    return img, {"engine": "waves", "palette": palette}


def make_flow(seed, width=2560, height=1440, palette=None):
    """Akis cizgileri: vektor alaninda suzulen parcacik izleri."""
    rng = np.random.default_rng(seed)
    palette = palette or str(rng.choice(list(PALETTES.keys())))
    # alan: birkac sinus bileseni
    a1, a2 = rng.uniform(0.8, 2.6, 2)
    p1, p2 = rng.uniform(0, 6.28, 2)
    n_part, steps = 5000, 220
    x = rng.uniform(0, 1, n_part); y = rng.uniform(0, 1, n_part)
    W2, H2 = width // 2, height // 2   # yari cozunurlukte biriktir (hiz)
    dens = np.zeros((H2, W2), dtype=np.float32)
    dt = 0.0022
    for _ in range(steps):
        ang = (np.sin(a1*2*np.pi*x + p1) + np.cos(a2*2*np.pi*y + p2)) * np.pi
        x = (x + dt*np.cos(ang)) % 1.0
        y = (y + dt*np.sin(ang)) % 1.0
        ix = (x * (W2-1)).astype(np.int32); iy = (y * (H2-1)).astype(np.int32)
        np.add.at(dens, (iy, ix), 1.0)
    dens = np.log1p(dens); dens /= dens.max()
    dens = np.asarray(Image.fromarray((dens*255).astype(np.uint8)).resize((width, height), Image.BILINEAR), dtype=np.float64)/255
    dens = np.maximum(dens, dens[:, ::-1]) ** 0.8
    img = _colorize(dens, palette, rng, 0.20)
    img = Image.blend(img, img.filter(ImageFilter.GaussianBlur(2)), 0.3)
    return img, {"engine": "flow", "palette": palette}


def make_rings(seed, width=2560, height=1440, palette=None):
    """Halka desenleri: ic ice moduleli halkalar - ses dalgasi/nabiz hissi."""
    rng = np.random.default_rng(seed)
    palette = palette or str(rng.choice(list(PALETTES.keys())))
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float64)
    cx = width*rng.uniform(0.42, 0.58); cy = height*rng.uniform(0.42, 0.58)
    r = np.sqrt((xx-cx)**2 + (yy-cy)**2) / (min(width, height)*0.55)
    th = np.arctan2(yy-cy, xx-cx)
    k = rng.integers(4, 9)                      # acisal simetri
    wob = 0.06*np.sin(k*th + rng.uniform(0, 6.28))
    rings = np.sin(2*np.pi*(r + wob)*rng.uniform(9, 16) + rng.uniform(0, 6.28))
    dens = np.abs(rings) ** rng.uniform(1.8, 3.2)
    dens *= np.exp(-r*1.35)                     # disari dogru soner
    dens = np.clip(dens / dens.max(), 0, 1)
    img = _colorize(dens, palette, rng, 0.15)
    img = Image.blend(img, img.filter(ImageFilter.GaussianBlur(4)), 0.4)
    return img, {"engine": "rings", "palette": palette}


def make_grid(seed, width=2560, height=1440, palette=None):
    """Geometrik izgara: derinlikli cizgi aglari - minimal/teknolojik his."""
    rng = np.random.default_rng(seed)
    palette = palette or str(rng.choice(list(PALETTES.keys())))
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float64)
    xx = xx/width - 0.5; yy = yy/height - 0.5
    # perspektif benzeri bukum
    warp = rng.uniform(0.5, 1.4)
    u = xx / (1.0 + warp*np.abs(yy))
    v = yy / (1.0 + warp*np.abs(xx))
    n1 = rng.integers(14, 26); n2 = rng.integers(14, 26)
    g1 = np.abs(np.sin(np.pi*n1*u)) ** 14
    g2 = np.abs(np.sin(np.pi*n2*v)) ** 14
    dens = np.clip(g1 + g2, 0, 1)
    # merkez parlama + kose sonumu
    r = np.sqrt(xx**2 + yy**2)
    dens = dens*np.exp(-r*1.1) + 0.25*np.exp(-r*4.0)
    dens = np.clip(dens / dens.max(), 0, 1)
    img = _colorize(dens, palette, rng, 0.22)
    img = Image.blend(img, img.filter(ImageFilter.GaussianBlur(2)), 0.3)
    return img, {"engine": "grid", "palette": palette}


def make_spiral(seed, width=2560, height=1440, palette=None):
    """Cok kollu galaksi sarmali: parlak cekirdek + sacilan yildiz kollari."""
    rng = np.random.default_rng(seed)
    palette = palette or str(rng.choice(list(PALETTES.keys())))
    W2, H2 = width // 2, height // 2

    arms = int(rng.integers(2, 6))
    turns = rng.uniform(1.1, 2.3)
    spin = rng.choice([-1.0, 1.0])
    n_arm = 60_000

    xs, ys, ws = [], [], []
    for a_i in range(arms):
        t = rng.uniform(0, 1, n_arm) ** 0.72
        base = a_i * 2 * np.pi / arms + spin * turns * 2 * np.pi * t
        # kol genisligi disari dogru acilir
        th = base + rng.normal(0, 0.05 + 0.16 * t, n_arm)
        r = t * (1.0 + rng.normal(0, 0.03, n_arm))
        xs.append(r * np.cos(th))
        ys.append(r * np.sin(th))
        ws.append((1.15 - t) ** 1.3 + 0.15)   # ic kisim parlak

    # merkez cekirdek (yogun parlak top)
    n_core = 25_000
    rc = np.abs(rng.normal(0, 0.06, n_core))
    tc = rng.uniform(0, 2 * np.pi, n_core)
    xs.append(rc * np.cos(tc)); ys.append(rc * np.sin(tc))
    ws.append(np.full(n_core, 1.35))

    x = np.concatenate(xs); y = np.concatenate(ys)
    w = np.concatenate(ws).astype(np.float32)

    dens = np.zeros((H2, W2), dtype=np.float32)
    scale = 0.46 * H2
    ix = np.clip((W2 / 2 + x * scale).astype(np.int32), 0, W2 - 1)
    iy = np.clip((H2 / 2 + y * scale).astype(np.int32), 0, H2 - 1)
    np.add.at(dens, (iy, ix), w)
    dens = np.log1p(dens); dens /= dens.max()

    dimg = Image.fromarray((dens * 255).astype(np.uint8))
    dimg = dimg.filter(ImageFilter.GaussianBlur(1.1))
    dens = np.asarray(dimg.resize((width, height), Image.BILINEAR),
                      dtype=np.float64) / 255
    dens = np.clip(dens * 1.45, 0, 1) ** 0.80
    img = _colorize(dens, palette, rng, 0.14)
    img = Image.blend(img, img.filter(ImageFilter.GaussianBlur(4)), 0.32)
    return img, {"engine": "spiral", "palette": palette,
                 "arms": arms, "turns": round(float(turns), 2)}


def make_harmonograph(seed, width=2560, height=1440, palette=None):
    """Harmonograf: sonen sarkac egrileri - zarif, ipeksi cizgi aglari."""
    rng = np.random.default_rng(seed)
    palette = palette or str(rng.choice(list(PALETTES.keys())))
    W2, H2 = width // 2, height // 2
    t = np.linspace(0, 90 * np.pi, 500_000)
    f = rng.integers(2, 7, 4).astype(np.float64) + rng.uniform(-0.02, 0.02, 4)
    p = rng.uniform(0, 2 * np.pi, 4)
    dmp = rng.uniform(0.002, 0.007, 4)
    x = (np.exp(-dmp[0] * t) * np.sin(f[0] * t + p[0]) +
         np.exp(-dmp[1] * t) * np.sin(f[1] * t + p[1]))
    y = (np.exp(-dmp[2] * t) * np.sin(f[2] * t + p[2]) +
         np.exp(-dmp[3] * t) * np.cos(f[3] * t + p[3]))
    dens = np.zeros((H2, W2), dtype=np.float32)
    scale = 0.235 * H2
    ix = np.clip((W2 / 2 + x * scale * 1.35).astype(np.int32), 0, W2 - 1)
    iy = np.clip((H2 / 2 + y * scale).astype(np.int32), 0, H2 - 1)
    np.add.at(dens, (iy, ix), 1.0)
    dens = np.log1p(dens); dens /= dens.max()
    dens = np.maximum(dens, dens[:, ::-1])          # ayna simetrisi
    dens = np.asarray(Image.fromarray((dens * 255).astype(np.uint8))
                      .resize((width, height), Image.BILINEAR),
                      dtype=np.float64) / 255
    dens = dens ** 0.78
    img = _colorize(dens, palette, rng, 0.18)
    img = Image.blend(img, img.filter(ImageFilter.GaussianBlur(2)), 0.30)
    return img, {"engine": "harmonograph", "palette": palette}


ENGINES = {
    "attractor": None,   # generate() mevcut motoru kullanir
    "waves":     make_waves,
    "flow":      make_flow,
    "rings":     make_rings,
    "grid":      make_grid,
    "spiral":       make_spiral,
    "harmonograph": make_harmonograph,
}


def generate_engine(engine, seed, width=2560, height=1440, palette=None):
    """Motor adina gore gorsel uret. attractor -> mevcut generate()."""
    if engine == "attractor" or engine not in ENGINES:
        img, meta = generate(seed, width, height, palette=palette)
        meta["engine"] = "attractor"
        return img, meta
    return ENGINES[engine](seed, width, height, palette)
