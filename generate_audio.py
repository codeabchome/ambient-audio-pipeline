#!/usr/bin/env python3
"""
Ambient / binaural audio generator.
Uretilen ses tamamen matematiksel sentez - telif yok, dis kaynak yok.
Seamless loop uretir, FFmpeg ile istenen sureye uzatilir.
"""

import argparse
import json
import random
import wave
from pathlib import Path

import numpy as np

SR = 44100  # ornekleme frekansi


# ---------------------------------------------------------------- presetler

# Solfeggio + yaygin sifa frekanslari (tasiyici ton)
CARRIERS = {
    174: "pain relief",
    285: "tissue healing",
    396: "releasing fear",
    417: "facilitating change",
    432: "natural tuning",
    528: "transformation",
    639: "connection",
    741: "awakening intuition",
    852: "spiritual order",
    963: "divine consciousness",
}

# Amaca gore beyin dalgasi araligi (binaural beat frekansi, Hz)
PURPOSES = {
    "sleep":      {"beat": (0.5, 3.0),  "brightness": 0.25, "noise": 0.32},
    "meditation": {"beat": (4.0, 7.5),  "brightness": 0.40, "noise": 0.24},
    "relax":      {"beat": (8.0, 11.0), "brightness": 0.45, "noise": 0.26},
    "focus":      {"beat": (14.0, 18.0), "brightness": 0.60, "noise": 0.18},
    "study":      {"beat": (10.0, 13.0), "brightness": 0.55, "noise": 0.20},
}

# Dogal doku katmani (sentetik - gercek kayit degil)
TEXTURES = ["rain", "ocean", "wind", "stream", "none"]


# ---------------------------------------------------------------- yardimci

def _fade(n, samples):
    """Baslangic/bitis icin yumusak fade zarfi."""
    env = np.ones(n)
    f = min(samples, n // 2)
    if f > 0:
        ramp = np.sin(np.linspace(0, np.pi / 2, f)) ** 2
        env[:f] = ramp
        env[-f:] = ramp[::-1]
    return env


def _norm(x, peak=0.85):
    m = np.max(np.abs(x))
    return x * (peak / m) if m > 0 else x


# ---------------------------------------------------------------- katmanlar

def pink_noise(n, rng):
    """Pembe gurultu - Voss-McCartney benzeri, FFT tabanli."""
    white = rng.standard_normal(n)
    spec = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    freqs[0] = freqs[1]
    spec /= np.sqrt(freqs)
    out = np.fft.irfft(spec, n)
    return _norm(out, 1.0)


def brown_noise(n, rng):
    """Kahverengi gurultu - daha derin, ugultu benzeri."""
    white = rng.standard_normal(n)
    spec = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    freqs[0] = freqs[1]
    spec /= freqs
    out = np.fft.irfft(spec, n)
    return _norm(out, 1.0)


def texture_layer(kind, n, rng):
    """Sentetik dogal doku. Gercek kayit kullanilmaz."""
    if kind == "none":
        return np.zeros(n)

    t = np.arange(n) / SR

    if kind == "rain":
        base = pink_noise(n, rng)
        # ince damla parlakligi
        hiss = pink_noise(n, rng) * 0.35
        base = base + hiss
        # cok yavas yogunluk dalgalanmasi
        lfo = 1.0 + 0.18 * np.sin(2 * np.pi * 0.013 * t + rng.uniform(0, 6.28))
        return _norm(base * lfo, 1.0)

    if kind == "ocean":
        base = brown_noise(n, rng)
        # dalga cevrimi ~9-13 saniye
        period = rng.uniform(9.0, 13.0)
        swell = 0.45 + 0.55 * (0.5 + 0.5 * np.sin(2 * np.pi * t / period))
        return _norm(base * swell ** 1.6, 1.0)

    if kind == "wind":
        base = brown_noise(n, rng) * 0.7 + pink_noise(n, rng) * 0.3
        gust = 1.0 + 0.35 * np.sin(2 * np.pi * 0.021 * t + rng.uniform(0, 6.28))
        gust *= 1.0 + 0.20 * np.sin(2 * np.pi * 0.007 * t)
        return _norm(base * gust, 1.0)

    if kind == "stream":
        base = pink_noise(n, rng)
        bubble = pink_noise(n, rng) * 0.45
        lfo = 1.0 + 0.10 * np.sin(2 * np.pi * 0.05 * t)
        return _norm((base + bubble) * lfo, 1.0)

    return np.zeros(n)


def pad_layer(carrier, n, rng, brightness):
    """Yumusak atmosferik pad - tasiyici frekansin harmonikleri."""
    t = np.arange(n) / SR
    out = np.zeros(n)

    # temel + harmonikler (brightness ust harmoniklerin seviyesini belirler)
    harmonics = [(1.0, 1.00), (2.0, 0.42 * brightness), (3.0, 0.22 * brightness),
                 (4.0, 0.12 * brightness), (6.0, 0.06 * brightness)]

    for mult, amp in harmonics:
        if amp <= 0.001:
            continue
        f = carrier * mult
        if f > 8000:
            continue
        # her harmonik hafif farkli hizda nefes alsin
        rate = rng.uniform(0.008, 0.03)
        phase = rng.uniform(0, 6.28)
        breathe = 0.75 + 0.25 * np.sin(2 * np.pi * rate * t + phase)
        # cok hafif detune -> canli, olu olmayan ton
        detune = rng.uniform(-0.4, 0.4)
        out += amp * breathe * np.sin(2 * np.pi * (f + detune) * t + phase)

    # alt oktav derinlik
    sub = carrier / 2
    if sub >= 40:
        out += 0.30 * np.sin(2 * np.pi * sub * t)

    return _norm(out, 1.0)


def binaural_layer(carrier, beat, n):
    """Binaural beat: sol/sag kulak arasinda beat kadar fark."""
    t = np.arange(n) / SR
    left = np.sin(2 * np.pi * (carrier - beat / 2) * t)
    right = np.sin(2 * np.pi * (carrier + beat / 2) * t)
    return left, right


# ---------------------------------------------------------------- loop

def seamless(stereo, cross_sec=6.0):
    """
    Kusursuz dongu: kuyruk ile bas capraz gecisle harmanlanir.
    Girdi (2, N + cross) uzunlugunda, cikti (2, N).
    """
    c = int(cross_sec * SR)
    n = stereo.shape[1] - c
    head = stereo[:, :c].copy()
    tail = stereo[:, n:n + c].copy()
    ramp = np.linspace(0, 1, c)
    blended = head * ramp + tail * (1 - ramp)
    out = stereo[:, :n].copy()
    out[:, :c] = blended
    return out


# ---------------------------------------------------------------- ana uretim

def build(loop_sec=600, carrier=None, purpose=None, texture=None, seed=None):
    rng = np.random.default_rng(seed)

    carrier = carrier or rng.choice(list(CARRIERS.keys()))
    purpose = purpose or rng.choice(list(PURPOSES.keys()))
    texture = texture if texture is not None else rng.choice(TEXTURES)

    cfg = PURPOSES[purpose]
    beat = round(float(rng.uniform(*cfg["beat"])), 2)

    cross = 6.0
    n = int((loop_sec + cross) * SR)

    # katmanlar
    bl, br = binaural_layer(carrier, beat, n)
    pad = pad_layer(carrier, n, rng, cfg["brightness"])
    tex = texture_layer(texture, n, rng)

    # seviyeler
    lvl_bin = 0.30
    lvl_pad = 0.42
    lvl_tex = cfg["noise"] if texture != "none" else 0.0
    if texture == "none":
        lvl_pad += 0.15

    left = lvl_bin * bl + lvl_pad * pad + lvl_tex * tex
    right = lvl_bin * br + lvl_pad * pad + lvl_tex * tex

    stereo = np.vstack([left, right])
    stereo = seamless(stereo, cross)
    stereo = _norm(stereo, 0.82)

    meta = {
        "carrier_hz": int(carrier),
        "carrier_meaning": CARRIERS[int(carrier)],
        "beat_hz": beat,
        "purpose": purpose,
        "texture": texture,
        "loop_seconds": loop_sec,
        "seed": seed,
    }
    return stereo, meta


def write_wav(stereo, path):
    data = np.clip(stereo.T, -1, 1)
    pcm = (data * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="loop.wav")
    p.add_argument("--meta", default="meta.json")
    p.add_argument("--loop", type=int, default=600, help="loop uzunlugu (saniye)")
    p.add_argument("--carrier", type=int, default=None)
    p.add_argument("--purpose", default=None, choices=list(PURPOSES) + [None])
    p.add_argument("--texture", default=None, choices=TEXTURES + [None])
    p.add_argument("--seed", type=int, default=None)
    a = p.parse_args()

    stereo, meta = build(a.loop, a.carrier, a.purpose, a.texture, a.seed)
    write_wav(stereo, a.out)
    Path(a.meta).write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
