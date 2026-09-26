#!/usr/bin/env python3
"""
Piksel art sahne motoru (Tonebed doga videolari icin).

Her sahne 320x180 piksel cizilir, 4x en-yakin komsu ile 1280x720'ye buyutulur.
12 fps (piksel art icin dogal) + crf 26: 8 saat ~0.5-2.7 GB video.
Tum hareketler dongu suresine TAM bolunur -> son kare ile ilk kare birebir ayni,
-stream_loop -1 -c copy ile 8 saate uzatildiginda dikis gorunmez.

Sahneler: rain_window, storm, fireplace, ocean
"""
import math
import subprocess
import numpy as np

W, H, S = 320, 180, 4          # 4x = 1280x720 (8 saatlik dosya boyutu icin)
BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16
YY, XX = np.mgrid[0:H, 0:W]
BM = BAYER[YY % 4, XX % 4]


def c(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.uint8)


def grad(stops, y0=0, y1=H):
    """Dikey, Bayer ile dither'lanmis gradyan (renk sayisi dusuk kalir)."""
    img = np.zeros((H, W, 3), np.uint8)
    n = len(stops) - 1
    for y in range(H):
        t = min(max((y - y0) / max(1, (y1 - y0)), 0), 0.9999) * n
        i, fr = int(t), t - int(t)
        row = np.where((fr > BAYER[y % 4, np.arange(W) % 4])[:, None], stops[i + 1], stops[i])
        img[y] = row
    return img


def add(img, mask, rgb):
    img[mask] = np.clip(img[mask].astype(int) + rgb, 0, 255).astype(np.uint8)


class Rain:
    def __init__(self, n, seed, kmin=5, kmax=9, lmin=3, lmax=6, slant=1, x0=0, x1=W, y0=0, y1=H):
        r = np.random.default_rng(seed)
        self.d = [(r.uniform(x0, x1), r.uniform(y0, y1), int(r.integers(kmin, kmax)),
                   int(r.integers(lmin, lmax))) for _ in range(n)]
        self.slant, self.box = slant, (x0, x1, y0, y1)

    def draw(self, img, ph, col, mask=None):
        x0, x1, y0, y1 = self.box
        w, h = x1 - x0, y1 - y0
        for (dx, dy, k, ln) in self.d:
            y = y0 + (dy - y0 + ph * k * h) % h
            x = x0 + (dx - x0 - ph * self.slant * max(1, round(k / 4)) * w) % w
            for i in range(ln):
                yi, xi = int(y) - i, int(x + i * 0.25 * self.slant)
                if y0 <= yi < y1 and x0 <= xi < x1 and (mask is None or mask[yi, xi]):
                    img[yi, xi] = col


# ------------------------------------------------------------------ sahne 1
def scene_rain_window(weather="rain", seed=0):
    P = dict(sky=[c('#0b0f2a'), c('#1b1f4a'), c('#2d2a63')], moon=c('#f3e9c6'), glow=c('#4a4486'),
             far=c('#1a1840'), mid=c('#141233'), near=c('#0d0b24'), w1=c('#ffcf6b'), w2=c('#ff9d5c'),
             rain=c('#8fa3d9'), cloud=c('#2a2757'), wall=c('#2b1b2e'), wall2=c('#24162a'),
             wood=c('#5a3a2a'), wood2=c('#3d271e'), sill=c('#6b4632'), desk=c('#4a2f24'),
             desk2=c('#3a241c'), mug=c('#c9d4e8'), mug2=c('#9aa8c4'), steam=c('#6d6390'),
             book1=c('#7a3b3b'), book2=c('#3b5a7a'), book3=c('#c9a45c'), refl=c('#3a3470'),
             drop=c('#b9c8f0'), pot=c('#a0553a'), leaf=c('#3f7a4a'), leaf2=c('#2c5a37'))
    WX0, WX1, WY0, WY1 = 40, 280, 10, 126
    sky = grad(P['sky'], WY0, WY1)
    r = np.random.default_rng(1 + seed)
    def skyline(base, hmin, hmax, wmin, wmax):
        tops = np.full(W, H); x = WX0 - 8; b = []
        while x < WX1 + 8:
            w, h = int(r.integers(wmin, wmax)), int(r.integers(hmin, hmax))
            tops[max(0, x):min(W, x + w)] = base - h; b.append((x, w, base - h)); x += w + int(r.integers(0, 3))
        return tops, b
    ft, fb = skyline(112, 18, 40, 10, 22)
    mt, mb = skyline(118, 10, 30, 12, 26)
    wins = []
    for (x, w, top) in mb:
        for wy in range(top + 3, 116, 4):
            for wx in range(x + 2, x + w - 2, 3):
                if r.random() < .33: wins.append((wx, wy, int(r.integers(1, 5)), r.random(), 'w1' if r.random() < .6 else 'w2'))
    clouds = [(r.uniform(0, W), int(r.integers(16, 46)), int(r.integers(14, 30)), int(r.integers(3, 6))) for _ in range(7)]
    rain = Rain(240, 2 + seed, x0=WX0, x1=WX1, y0=WY0, y1=WY1)
    drops = [(int(r.integers(WX0 + 4, WX1 - 4)), r.random(), int(r.integers(1, 3))) for _ in range(14)]
    MX, MY, MR = int(r.integers(150, 250)), int(r.integers(26, 44)), 9
    dm = np.sqrt((XX - MX) ** 2 + (YY - MY) ** 2)
    base = np.empty((H, W, 3), np.uint8); base[:] = P['wall']; base[(YY % 8 == 0) & (BM < .3)] = P['wall2']

    def frame(ph, f):
        img = sky.copy()
        for (cx, cy, cw, ch) in clouds:
            x0 = (cx + ph * (W + 60)) % (W + 60) - 30
            img[(((XX - x0) / cw) ** 2 + ((YY - cy) / ch) ** 2 < 1) & (BM < .7)] = P['cloud']
        img[(dm < MR + 6) & (dm >= MR) & (BM < .5)] = P['glow']; img[dm < MR] = P['moon']
        for x in range(W):
            img[ft[x]:, x] = P['far']; img[mt[x]:, x] = P['mid']
        img[120:WY1, :] = P['near']
        for (wx, wy, per, off, col) in wins:
            if math.sin(2 * math.pi * (per * ph + off)) > -.6:
                img[wy:wy + 2, wx] = P[col]
                ry = 120 + (120 - wy) // 8
                if ry < WY1 and (f // 3 + wx) % 2 == 0: img[ry, wx] = P['refl']
        if weather == "rain": rain.draw(img, ph, P['rain'])
        out = base.copy()
        out[WY0:WY1, WX0:WX1] = img[WY0:WY1, WX0:WX1]
        if weather == "rain":
            for (dx, d0, sp) in drops:
                dy = int(WY0 + ((d0 + ph * sp) % 1) * (WY1 - WY0))
                for i in range(2, 7, 2):
                    if WY0 <= dy - i < WY1: out[dy - i, dx] = P['refl']
                if WY0 <= dy < WY1 - 1: out[dy:dy + 2, dx] = P['drop']
        for (a, b_, c0, d) in [(WX0 - 4, WX0, WY0 - 4, WY1 + 2), (WX1, WX1 + 4, WY0 - 4, WY1 + 2), (WX0 - 4, WX1 + 4, WY0 - 4, WY0)]:
            out[c0:d, a:b_] = P['wood']
        mx = (WX0 + WX1) // 2; out[WY0:WY1, mx - 1:mx + 2] = P['wood']; out[WY0:WY1, mx + 1] = P['wood2']
        out[(WY0 + WY1) // 2 - 12:(WY0 + WY1) // 2 - 10, WX0:WX1] = P['wood']
        out[WY1:WY1 + 5, WX0 - 10:WX1 + 10] = P['sill']; out[WY1 + 5:WY1 + 7, WX0 - 10:WX1 + 10] = P['wood2']
        # bitki (pervazda, sol)
        px = 58; out[WY1 - 10:WY1, px:px + 12] = P['pot']
        for (lx, ly, cc) in [(px + 5, WY1 - 18, 'leaf'), (px + 2, WY1 - 15, 'leaf2'), (px + 8, WY1 - 16, 'leaf'), (px + 6, WY1 - 22, 'leaf2'), (px + 10, WY1 - 20, 'leaf')]:
            sw = int(round(math.sin(2 * math.pi * ph * 2 + lx) * .6)); out[ly:ly + 4, lx + sw:lx + sw + 3] = P[cc]
        # masa + kupa + kitaplar
        out[148:, :] = P['desk']; out[148:150, :] = P['desk2']; out[(YY > 150) & (YY % 6 == 0) & (BM < .4)] = P['desk2']
        bx = 36
        for i, (bw, bc) in enumerate([(46, 'book1'), (40, 'book2'), (44, 'book3')]):
            out[146 - i * 5:151 - i * 5, bx + i * 2:bx + i * 2 + bw] = P[bc]
            out[146 - i * 5, bx + i * 2:bx + i * 2 + bw] = np.clip(P[bc].astype(int) + 30, 0, 255)
        kx, ky = 232, 140
        out[ky:ky + 16, kx:kx + 14] = P['mug']; out[ky:ky + 16, kx + 11:kx + 14] = P['mug2']
        out[ky + 3:ky + 11, kx + 14:kx + 17] = P['mug']; out[ky + 5:ky + 9, kx + 15] = P['desk']
        out[ky, kx + 1:kx + 13] = c('#5a3a2a')
        for j in range(3):  # buhar (periyodik yukselis)
            t = (ph * 3 + j / 3) % 1
            sy = int(ky - 2 - t * 22); sx = int(kx + 6 + math.sin(2 * math.pi * (t * 1.5 + j / 3)) * 3)
            if t < .85 and 0 <= sy < H: out[sy:sy + 2, sx:sx + 1] = P['steam']
        return out
    return frame


# ------------------------------------------------------------------ sahne 2
def scene_storm(seed=0):
    P = dict(sky=[c('#07081a'), c('#121633'), c('#1c2244')], cloud=c('#262c52'), cloud2=c('#323a66'),
             hill=c('#0c1420'), hill2=c('#101b28'), grass=c('#16263a'), house=c('#262840'),
             roof=c('#43303c'), win=c('#ffc86b'), win2=c('#ff9a4a'), rain=c('#7f93c8'),
             tree=c('#0a111b'), bolt=c('#eef2ff'), flash=[70, 76, 105])
    sky = grad(P['sky'], 0, 120)
    r = np.random.default_rng(5 + seed)
    hill = (128 + 10 * np.sin(XX[0] / 40) + 6 * np.sin(XX[0] / 17 + 1)).astype(int)
    hill2 = (148 + 6 * np.sin(XX[0] / 30 + 2)).astype(int)
    rain = Rain(420, 6 + seed, kmin=7, kmax=11, lmin=4, lmax=8, slant=2)
    cl = [(r.uniform(0, W), int(r.integers(8, 60)), int(r.integers(30, 60)), int(r.integers(6, 12))) for _ in range(12)]
    HX = int(r.integers(90, 200))
    trees = [(int(x), int(r.integers(14, 24))) for x in r.choice(np.r_[10:80, 230:300], 5, replace=False)]
    # dongude (60 sn) 1 uzak, soluk parlama. Cizgi simsek YOK: gok gurultusu
    # kaydiyla senkron degil ve uyku videosunda parlak flas rahatsiz eder.
    flashes = [(r.uniform(.2, .8), 0)]
    def bolt(seed):
        rr = np.random.default_rng(seed); pts = [(int(rr.integers(90, 230)), 0)]
        while pts[-1][1] < 122:
            x, y = pts[-1]; pts.append((x + int(rr.integers(-6, 7)), y + int(rr.integers(6, 12))))
        return pts
    bolts = [bolt(11), bolt(12)]

    def frame(ph, f):
        img = sky.copy()
        fl = 0.0; bi = None
        for i, (p0, _) in enumerate(flashes):
            d = (ph - p0) % 1
            if d < 0.006: fl = [.35, .15, .28, .1, .05][min(4, int(d / 0.0012))]; bi = i
        for (cx, cy, cw, ch) in cl:
            x0 = (cx + ph * (W + 120)) % (W + 120) - 60
            m = (((XX - x0) / cw) ** 2 + ((YY - cy) / ch) ** 2 < 1)
            img[m & (BM < .75)] = P['cloud']; img[m & (YY < cy) & (BM < .35)] = P['cloud2']
        if fl > 0:
            add(img, YY < 125, (np.array(P['flash']) * fl).astype(int))
            if False:
                pts = bolts[bi]
                for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                    for t in np.linspace(0, 1, 12):
                        x, y = int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t)
                        if 0 <= y < H: img[y, x:x + 2] = P['bolt']
        for x in range(W):
            img[hill[x]:, x] = P['hill']; img[hill2[x]:, x] = P['hill2']
        img[(YY > hill2[XX] + 4) & (BM < .25)] = P['grass']
        # agaclar (ruzgarda sallanir)
        for (tx, th) in trees:
            base = hill[tx] if tx < 200 else hill[tx]
            sw = math.sin(2 * math.pi * ph * 4 + tx) * 2
            for k in range(th):
                wdt = max(1, int((th - k) / 3)); xs = int(tx + sw * k / th)
                img[base - k, xs - wdt:xs + wdt + 1] = P['tree']
        # ev
        hx = HX; hy = hill[hx] - 18
        img[hy:hy + 18, hx:hx + 34] = P['house']
        for k in range(10): img[hy - 10 + k, hx + 8 - k * 1:hx + 26 + k * 1] = P['roof']
        for (wx, wy) in [(hx + 6, hy + 6), (hx + 22, hy + 6)]:
            img[wy:wy + 6, wx:wx + 6] = P['win']; img[wy + 3, wx:wx + 6] = P['win2']; img[wy:wy + 6, wx + 3] = P['win2']
        img[hy + 17, hx - 3:hx + 37] = P['hill2']
        rain.draw(img, ph, P['rain'])
        return img
    return frame


# ------------------------------------------------------------------ sahne 3
def scene_fireplace(weather="none", seed=0):
    P = dict(wall=c('#3a2418'), wall2=c('#2e1c13'), log=c('#4a2e1e'), stone=c('#4b4550'), stone2=c('#3a3540'),
             stone3=c('#5c5563'), dark=c('#120a08'), f1=c('#fff1a8'), f2=c('#ffc64a'), f3=c('#ff7a2a'),
             f4=c('#c0301a'), ember=c('#ff5a1a'), wood=c('#5a3522'), rug=c('#6a2a2a'), rug2=c('#8a3a32'),
             chair=c('#2a1a22'), chair2=c('#3a2430'), floor=c('#2a1a12'), floor2=c('#23150e'),
             sky=[c('#0b1030'), c('#1b2250')], snow=c('#e4e8f4'), rain=c('#8fa3d9'), frame=c('#5a3a2a'))
    base = np.empty((H, W, 3), np.uint8); base[:] = P['wall']
    for y in range(0, 132, 9): base[y:y + 1, :] = P['wall2']          # kutuk duvar
    base[(YY % 9 == 4) & (BM < .15)] = P['log']
    base[132:, :] = P['floor']; base[(YY >= 132) & (XX % 24 == 0)] = P['floor2']
    # tas ocak
    FX0, FX1, FY0 = 110, 210, 40
    for y in range(FY0, 132):
        for x in range(FX0, FX1):
            bx = (x + (6 if (y // 6) % 2 else 0)) // 12
            v = (bx * 7 + y // 6 * 3) % 3
            base[y, x] = [P['stone'], P['stone2'], P['stone3']][v]
            if y % 6 == 0 or (x + (6 if (y // 6) % 2 else 0)) % 12 == 0: base[y, x] = P['stone2']
    base[FY0 - 6:FY0, FX0 - 8:FX1 + 8] = P['wood']                     # raf
    OX0, OX1, OY0, OY1 = 130, 190, 78, 130
    base[OY0:OY1, OX0:OX1] = P['dark']
    for k in range(8): base[OY0 - 8 + k, OX0 + 8 - k:OX1 - 8 + k] = P['dark']
    # raf ustu: mum + saat kumu
    base[FY0 - 14:FY0 - 6, 124:128] = c('#e8dcc0'); base[FY0 - 12:FY0 - 6, 196:204] = c('#7a5a3a')
    # hali + koltuk
    for y in range(146, 172):
        hw = int(90 * math.sqrt(max(0, 1 - ((y - 159) / 13) ** 2)))
        base[y, 160 - hw:160 + hw] = P['rug']
        base[y, 160 - hw:160 + hw][(np.arange(2 * hw) % 8 < 2)] = P['rug2']
    base[112:160, 20:70] = P['chair']; base[112:120, 16:74] = P['chair2']; base[135:142, 12:78] = P['chair2']
    base[160:170, 22:26] = P['chair']; base[160:170, 64:68] = P['chair']
    # yan pencere (sag)
    WX0, WX1, WY0, WY1 = 240, 296, 30, 96
    wsky = grad(P['sky'], WY0, WY1)
    base[WY0 - 3:WY1 + 3, WX0 - 3:WX1 + 3] = P['frame']
    r = np.random.default_rng(9 + seed)
    flakes = [(r.uniform(WX0, WX1), r.uniform(WY0, WY1), int(r.integers(1, 3)), r.random()) for _ in range(40)]
    rain = Rain(70, 10, x0=WX0, x1=WX1, y0=WY0, y1=WY1)
    # alev profili: periyodik (tam sayi frekanslar)
    cols = np.arange(OX0 + 4, OX1 - 4)
    rng = np.random.default_rng(3 + seed)
    comps = [(int(rng.integers(1, 5)), rng.uniform(0, 6.28), rng.uniform(.5, 1.5), rng.uniform(.05, .25)) for _ in range(6)]

    def frame(ph, f):
        out = base.copy()
        out[WY0:WY1, WX0:WX1] = wsky[WY0:WY1, WX0:WX1]
        if weather == "snow":
            for (fx, fy, sp, o) in flakes:
                y = WY0 + (fy - WY0 + ph * sp * (WY1 - WY0)) % (WY1 - WY0)
                x = fx + math.sin(2 * math.pi * (ph * 3 + o)) * 2
                if WX0 <= x < WX1: out[int(y), int(x)] = P['snow']
        elif weather == "rain":
            rain.draw(out, ph, P['rain'])
        out[WY0:WY1, (WX0 + WX1) // 2] = P['frame']; out[(WY0 + WY1) // 2, WX0:WX1] = P['frame']
        # alev
        u = (cols - OX0) / (OX1 - OX0)
        env = np.sin(np.pi * u) ** .8
        h = np.zeros_like(u)
        for (k, p, sp, a) in comps:
            h += a * np.sin(2 * math.pi * (k * 4 * ph) + u * sp * 12 + p)
        h = (env * (0.75 + h) * 42).clip(2, 46)
        glow_r = 60 + 6 * math.sin(2 * math.pi * ph * 8) + 4 * math.sin(2 * math.pi * ph * 13)
        dg = np.sqrt((XX - 160) ** 2 + ((YY - 122) * 1.4) ** 2)
        gm = (dg < glow_r) & (BM < .45 * (1 - dg / glow_r)) & ~((XX >= OX0) & (XX < OX1) & (YY >= OY0) & (YY < OY1))
        add(out, gm, [55, 28, 6])
        for i, x in enumerate(cols):
            hh = h[i]
            for y in range(OY1 - 6, max(OY0, int(OY1 - 6 - hh)), -1):
                t = (OY1 - 6 - y) / hh
                col = P['f1'] if t < .25 else P['f2'] if t < .5 else P['f3'] if t < .78 else P['f4']
                if t > .78 and BAYER[y % 4, x % 4] > .5: continue
                out[y, x] = col
        out[OY1 - 6:OY1 - 2, OX0 + 8:OX1 - 8] = P['wood']; out[OY1 - 8:OY1 - 5, OX0 + 16:OX1 - 20] = c('#6a4028')
        for j in range(6):   # kivilcim
            t = (ph * 2 + j / 6) % 1
            ex = int(150 + j * 4 + math.sin(2 * math.pi * (t * 2 + j)) * 5); ey = int(OY1 - 20 - t * 50)
            if t < .7 and OY0 - 6 <= ey < OY1: out[ey, ex] = P['ember']
        return out
    return frame


# ------------------------------------------------------------------ sahne 4
def scene_ocean(seed=0):
    P = dict(sky=[c('#050817'), c('#0d1433'), c('#1b2452')], star=c('#cfd6ff'), moon=c('#f1ecd2'),
             glow=c('#2f3a73'), sea=[c('#0e1a3a'), c('#0a1330'), c('#070d24')], wave=c('#2b3f78'),
             shine=c('#e8e2c0'), shine2=c('#9aa6d8'), rock=c('#0a0c16'), light=c('#fff2b0'),
             tower=c('#d8d2c8'), tower2=c('#8a3a3a'), beam=[28, 26, 12], sand=c('#1a1a30'), foam=c('#b8c4ec'))
    HOR = 96
    sky = grad(P['sky'], 0, HOR)
    sea = grad(P['sea'], HOR, H)
    img0 = np.where((YY < HOR)[..., None], sky, sea)
    r = np.random.default_rng(4 + seed)
    stars = [(int(r.integers(0, W)), int(r.integers(0, HOR - 10)), int(r.integers(1, 4)), r.random()) for _ in range(70)]
    MX, MY, MR = int(r.integers(60, 190)), int(r.integers(26, 46)), 10
    dm = np.sqrt((XX - MX) ** 2 + (YY - MY) ** 2)
    waves = [(r.uniform(0, W), int(r.integers(HOR + 2, H - 20)), int(r.integers(3, 10)), int(r.choice([1, 2, -1]))) for _ in range(90)]
    # sagda kayalik + deniz feneri
    LX, LY = 262, 58
    rock = np.zeros((H, W), bool)
    for x in range(228, W):
        top = int(88 + 10 * math.sin((x - 228) / 14) + (x - 228) * .1)
        rock[top:HOR + 18, x] = True

    def frame(ph, f):
        img = img0.copy()
        for (sx, sy, per, o) in stars:
            if math.sin(2 * math.pi * (per * ph + o)) > -.3: img[sy, sx] = P['star']
        img[(dm < MR + 7) & (dm >= MR) & (BM < .45)] = P['glow']; img[dm < MR] = P['moon']
        img[(dm < MR) & ((XX - MX - 3) ** 2 + (YY - MY + 2) ** 2 < 8)] = c('#d8d1b0')
        # dalga cizgileri (yatay kayar, tam sayi tur)
        for (wx, wy, ln, sp) in waves:
            x = (wx + ph * sp * W) % W
            depth = (wy - HOR) / (H - HOR)
            L = int(ln * (0.5 + depth))
            xs = (np.arange(L) + int(x)) % W
            img[wy, xs] = P['wave']
        # ay yansimasi sutunu (parildar)
        for y in range(HOR + 1, H - 14):
            half = int(3 + (y - HOR) * .18)
            for x in range(MX - half, MX + half):
                v = math.sin(2 * math.pi * (ph * 6) + x * .9 + y * 1.7)
                if v > .55: img[y, x] = P['shine'] if abs(x - MX) < half * .5 else P['shine2']
        # fener isik huzmesi (1 tur/dongu)
        ang = 2 * math.pi * ph * 2
        dx, dy = XX - LX, YY - LY
        a = np.arctan2(dy, dx)
        dd = np.abs(((a - ang + math.pi) % (2 * math.pi)) - math.pi)
        beam = (dd < .13) & (np.sqrt(dx ** 2 + dy ** 2) < 240) & (BM < .5 * (1 - np.sqrt(dx ** 2 + dy ** 2) / 240))
        add(img, beam & (math.cos(ang) < .6), P['beam'])
        img[rock] = P['rock']
        img[LY:LY + 32, LX - 4:LX + 5] = P['tower']
        for k in range(LY + 4, LY + 32, 8): img[k:k + 4, LX - 4:LX + 5] = P['tower2']
        img[LY - 6:LY, LX - 3:LX + 4] = P['light'] if math.cos(ang) > -.2 else c('#b8a870')
        img[LY - 9:LY - 6, LX - 4:LX + 5] = P['rock']
        # kiyi kopugu (on planda, yuvarlanir)
        img[H - 12:, :] = P['sand']
        for j in range(3):
            t = (ph * 3 + j / 3) % 1
            fy = int(H - 14 + t * 8)
            amp = math.sin(math.pi * t)
            m = (YY == fy) & (np.sin(XX / 9 + j * 2 + t * 6.28) > .2 - amp * .6)
            img[m] = P['foam']
        return img
    return frame


SCENES = {
    "rain_window": lambda sd: scene_rain_window("rain", sd),
    "storm": lambda sd: scene_storm(sd),
    "fireplace": lambda sd: scene_fireplace("none", sd),
    "fireplace_rain": lambda sd: scene_fireplace("rain", sd),
    "fireplace_snow": lambda sd: scene_fireplace("snow", sd),
    "ocean": lambda sd: scene_ocean(sd),
}
LOOP_SEC = {"storm": 60}          # digerleri 12 sn

# tarif -> sahne (recipes.py'deki "video" anahtari)
RECIPE_SCENE = {
    "rain_window": "rain_window", "rain_storm": "storm", "fireplace": "fireplace_snow",
    "fireplace_window": "fireplace_rain", "ocean": "ocean",
}


def scene_for(recipe_video_key):
    """recipes.py 'video' anahtari -> sahne adi (yoksa None)."""
    return RECIPE_SCENE.get(recipe_video_key)


def still(name, out_path, seed=0, scale=8):
    """Kapak icin ilk kare (8x = 2560x1440, kapak motorunun olcusu)."""
    from PIL import Image
    img = SCENES[name](seed % 100000)(0.0, 0)
    Image.fromarray(img.repeat(scale, 0).repeat(scale, 1)).save(out_path)


def render(name, out_path, seconds=None, fps=12, still=None, seed=0):
    fr = SCENES[name](seed % 100000)
    seconds = seconds or LOOP_SEC.get(name, 12)
    T = seconds * fps
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W * S}x{H * S}", "-r", str(fps), "-i", "-",
                          "-c:v", "libx264", "-preset", "medium", "-crf", "26", "-tune", "animation",
                          "-pix_fmt", "yuv420p", "-g", str(fps * 10), "-an", str(out_path)], stdin=subprocess.PIPE)
    first = None
    for f in range(T):
        img = fr(f / T, f)
        if f == 0: first = img
        p.stdin.write(img.repeat(S, 0).repeat(S, 1).tobytes())
    p.stdin.close(); p.wait()
    assert p.returncode == 0
    seam = int(np.abs(fr(1.0, T).astype(int) - first.astype(int)).sum())
    if still:
        from PIL import Image
        Image.fromarray(first.repeat(S, 0).repeat(S, 1)).save(still)
    return seam


if __name__ == "__main__":
    import sys
    for n in (sys.argv[1:] or SCENES):
        s = render(n, f"{n}.mp4", still=f"{n}.png", seed=0)
        print(n, "dikis farki:", s)
