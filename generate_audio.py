#!/usr/bin/env python3
"""
Ambient / binaural ses ureteci  v2

v1'e gore degisiklikler (ham sinus tonu rahatsiz ediciydi):
  - Tasiyici ton ARKA PLANDA, doga sesi ve pad ONDE
  - Yuksek tasiyicilar alt oktava indiriliyor (963Hz -> 481Hz)
  - Alcak gecirgen filtre ile sertlik aliniyor
  - Pad cok katmanli + detune (chorus) -> "bip" degil "yastik"
  - Yumusak acilis (ilk saniyelerde ses yavasca geliyor)
"""

import argparse
import json
import wave
from pathlib import Path

import numpy as np

SR = 44100

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

# tone = tasiyici seviyesi, pad = yastik, noise = doga sesi, cutoff = filtre
PURPOSES = {
    "sleep":      {"beat": (0.5, 3.0),   "tone": 0.10, "pad": 0.52, "noise": 0.74, "cutoff": 1400},
    "meditation": {"beat": (4.0, 7.5),   "tone": 0.12, "pad": 0.56, "noise": 0.66, "cutoff": 1800},
    "relax":      {"beat": (8.0, 11.0),  "tone": 0.12, "pad": 0.54, "noise": 0.68, "cutoff": 2000},
    "focus":      {"beat": (14.0, 18.0), "tone": 0.14, "pad": 0.48, "noise": 0.64, "cutoff": 2600},
    "study":      {"beat": (10.0, 13.0), "tone": 0.13, "pad": 0.50, "noise": 0.66, "cutoff": 2400},
}

TEXTURES = ["rain", "ocean", "wind", "stream", "fire", "whitenoise", "none"]

FOLD_ABOVE = 500.0


def _norm(x, peak=0.85):
    m = np.max(np.abs(x))
    return x * (peak / m) if m > 0 else x


def lowpass_fft(x, cutoff, slope=1.6):
    """FFT tabanli yumusak alcak gecirgen - hizli ve dogal."""
    n = len(x)
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    gain = 1.0 / (1.0 + (freqs / cutoff) ** (2 * slope))
    return np.fft.irfft(spec * gain, n)


def fold_carrier(f):
    """Yuksek tasiyiciyi duyulabilir ama yormayan bolgeye indir."""
    f = float(f)
    while f > FOLD_ABOVE:
        f /= 2.0
    return f


def pink_noise(n, rng):
    white = rng.standard_normal(n)
    spec = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    freqs[0] = freqs[1]
    return _norm(np.fft.irfft(spec / np.sqrt(freqs), n), 1.0)


def brown_noise(n, rng):
    white = rng.standard_normal(n)
    spec = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    freqs[0] = freqs[1]
    return _norm(np.fft.irfft(spec / freqs, n), 1.0)


def texture_layer(kind, n, rng):
    if kind == "none":
        return np.zeros(n)

    t = np.arange(n) / SR

    if kind == "rain":
        base = pink_noise(n, rng) + pink_noise(n, rng) * 0.30
        base = lowpass_fft(base, 5200, 1.2)
        lfo = 1.0 + 0.16 * np.sin(2 * np.pi * 0.013 * t + rng.uniform(0, 6.28))
        return _norm(base * lfo, 1.0)

    if kind == "ocean":
        base = lowpass_fft(brown_noise(n, rng), 2400, 1.2)
        period = rng.uniform(9.0, 13.0)
        swell = 0.40 + 0.60 * (0.5 + 0.5 * np.sin(2 * np.pi * t / period))
        return _norm(base * swell ** 1.5, 1.0)

    if kind == "wind":
        base = brown_noise(n, rng) * 0.7 + pink_noise(n, rng) * 0.3
        base = lowpass_fft(base, 1800, 1.3)
        gust = 1.0 + 0.32 * np.sin(2 * np.pi * 0.021 * t + rng.uniform(0, 6.28))
        gust = gust * (1.0 + 0.18 * np.sin(2 * np.pi * 0.007 * t))
        return _norm(base * gust, 1.0)

    if kind == "fire":
        # somine: derin ugultu + rastgele catirti
        base = lowpass_fft(brown_noise(n, rng), 900, 1.4)
        flicker = 1.0 + 0.30 * np.sin(2 * np.pi * 0.09 * t + rng.uniform(0, 6.28))
        flicker = flicker * (1.0 + 0.20 * np.sin(2 * np.pi * 0.31 * t))
        crack = np.zeros(n)
        # saniyede ~2 catirti
        hits = rng.integers(0, n, size=max(1, int(n / SR * 2)))
        crack[hits] = rng.uniform(0.5, 1.0, size=len(hits))
        env = np.exp(-np.arange(int(SR * 0.05)) / (SR * 0.010))
        crack = np.convolve(crack, env, mode="same")
        crack = lowpass_fft(crack, 3800, 1.2)
        return _norm(base * flicker + crack * 0.55, 1.0)

    if kind == "whitenoise":
        # saf, duz gurultu - bebek/uyku icin klasik
        base = pink_noise(n, rng) * 0.55 + rng.standard_normal(n) * 0.45
        return _norm(lowpass_fft(base, 7000, 1.0), 1.0)

    if kind == "stream":
        base = pink_noise(n, rng) + pink_noise(n, rng) * 0.40
        base = lowpass_fft(base, 4200, 1.2)
        lfo = 1.0 + 0.09 * np.sin(2 * np.pi * 0.05 * t)
        return _norm(base * lfo, 1.0)

    return np.zeros(n)


def pad_layer(carrier, n, rng, cutoff):
    """Cok katmanli yumusak pad; her harmonik 3 detune sesle chorus yapar."""
    t = np.arange(n) / SR
    out = np.zeros(n)
    base = fold_carrier(carrier)

    harmonics = [
        (0.5,  0.55),
        (1.0,  1.00),
        (1.5,  0.20),
        (2.0,  0.26),
        (3.0,  0.10),
        (4.0,  0.05),
    ]

    for mult, amp in harmonics:
        f = base * mult
        if f < 30 or f > 6000:
            continue
        for d in (-1, 0, 1):
            detune = d * rng.uniform(0.25, 0.7)
            phase = rng.uniform(0, 6.28)
            rate = rng.uniform(0.006, 0.022)
            breathe = 0.70 + 0.30 * np.sin(2 * np.pi * rate * t + phase)
            out += (amp / 3.0) * breathe * np.sin(2 * np.pi * (f + detune) * t + phase)

    out = lowpass_fft(out, cutoff, 1.5)
    return _norm(out, 1.0)


def binaural_layer(carrier, beat, n, cutoff):
    """
    Cift oktav tasiyici:
      - GERCEK frekans (or. 963Hz) dusuk seviyede gercekten calar
        -> basliktaki iddia dogru olur
      - Alt oktavi (or. 481.5Hz) daha belirgin calar
        -> kulaga yumusak gelir
    Oktav ayni nota oldugu icin muzikal olarak tutarli.
    """
    t = np.arange(n) / SR
    true_f = float(carrier)
    fold_f = fold_carrier(carrier)

    # alt oktav (belirgin)
    left = np.sin(2 * np.pi * (fold_f - beat / 2) * t)
    right = np.sin(2 * np.pi * (fold_f + beat / 2) * t)

    # gercek frekans (kisik) - sadece katlanmissa ekle
    if abs(true_f - fold_f) > 0.1:
        # ne kadar cok katlandiysa o kadar kisik (yuksek = daha yorucu)
        octaves = np.log2(true_f / fold_f)
        lvl = 0.22 / octaves
        left += lvl * np.sin(2 * np.pi * (true_f - beat / 2) * t)
        right += lvl * np.sin(2 * np.pi * (true_f + beat / 2) * t)

    # gercek frekans filtreye takilmasin diye kesim noktasini yukselt
    cut = max(cutoff, true_f * 1.6)
    return lowpass_fft(left, cut, 1.5), lowpass_fft(right, cut, 1.5)


def seamless(stereo, cross_sec=8.0):
    """Esit guclu capraz gecis - dongude ses cukuru olusmaz."""
    c = int(cross_sec * SR)
    n = stereo.shape[1] - c
    head = stereo[:, :c].copy()
    tail = stereo[:, n:n + c].copy()
    x = np.linspace(0, 1, c)
    fi, fo = np.sqrt(x), np.sqrt(1 - x)
    out = stereo[:, :n].copy()
    out[:, :c] = head * fi + tail * fo
    return out


def soft_open(stereo, seconds=6.0):
    """KULLANILMIYOR - fade render.py'de FFmpeg ile uygulanir."""
    n = stereo.shape[1]
    f = min(int(seconds * SR), n // 2)
    ramp = np.sin(np.linspace(0, np.pi / 2, f)) ** 2
    stereo[:, :f] *= ramp
    return stereo


def build(loop_sec=600, carrier=None, purpose=None, texture=None, seed=None):
    rng = np.random.default_rng(seed)

    carrier = int(carrier or rng.choice(list(CARRIERS.keys())))
    purpose = purpose or str(rng.choice(list(PURPOSES.keys())))
    texture = texture if texture is not None else str(rng.choice(TEXTURES))

    cfg = PURPOSES[purpose]
    beat = round(float(rng.uniform(*cfg["beat"])), 2)
    cutoff = cfg["cutoff"]

    cross = 8.0
    n = int((loop_sec + cross) * SR)

    bl, br = binaural_layer(carrier, beat, n, cutoff)
    pad = pad_layer(carrier, n, rng, cutoff)
    tex = texture_layer(texture, n, rng)

    lvl_tone = cfg["tone"]
    lvl_pad = cfg["pad"]
    lvl_tex = cfg["noise"]

    if texture == "none":
        lvl_pad += 0.25
        lvl_tone += 0.03

    left = lvl_tone * bl + lvl_pad * pad + lvl_tex * tex
    right = lvl_tone * br + lvl_pad * pad + lvl_tex * tex

    stereo = np.vstack([left, right])
    stereo = seamless(stereo, cross)
    # NOT: yumusak acilis burada UYGULANMAZ - dongu tekrarlandiginda
    # her tekrarda kesinti olusturur. Fade, render.py'de tam sure
    # olusturulduktan sonra bir kez uygulanir.
    stereo = _norm(stereo, 0.80)

    meta = {
        "carrier_hz": carrier,
        "played_hz": round(fold_carrier(carrier), 1),
        "carrier_meaning": CARRIERS[carrier],
        "beat_hz": beat,
        "purpose": purpose,
        "texture": texture,
        "loop_seconds": loop_sec,
        "seed": seed,
        "engine": "v2",
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
    p.add_argument("--loop", type=int, default=600)
    p.add_argument("--carrier", type=int, default=None)
    p.add_argument("--purpose", default=None)
    p.add_argument("--texture", default=None)
    p.add_argument("--seed", type=int, default=None)
    a = p.parse_args()

    stereo, meta = build(a.loop, a.carrier, a.purpose, a.texture, a.seed)
    write_wav(stereo, a.out)
    Path(a.meta).write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
