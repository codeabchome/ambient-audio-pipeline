#!/usr/bin/env python3
"""
Profesyonel miksaj motoru.

Katmanlar:
  1. GERCEK doga kaydi (approved/ kutuphanesinden) - ana katman
  2. Frekans tonu + pad (generate_audio v2) - alt destek katmani

Islemler:
  - Kayittan her seferinde FARKLI kesit + hafif hiz varyasyonu
    -> hicbir video birebir ayni degil
  - EQ: pad'e alcak gecirgen, kayda hafif yuksek raf
    -> katmanlar birbirinin yerine girmez
  - Yumusak kompresyon: ani seviye oynamalarini toparlar
  - Kusursuz dongu (esit guclu capraz gecis)
  - LUFS normalizasyonu: YouTube standardi -14 LUFS
"""

import json
import random
import subprocess
import wave
from pathlib import Path

import numpy as np

import generate_audio as ga

SR = 44100
TARGET_LUFS = -14.0
APPROVED = Path("approved")


# ---------------------------------------------------------------- yardimci

def read_wav(path):
    w = wave.open(str(path), "rb")
    n = w.getnframes()
    d = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
    ch = w.getnchannels()
    sr = w.getframerate()
    w.close()
    if ch == 2:
        d = d.reshape(-1, 2).T
    else:
        d = np.vstack([d, d])
    return d, sr


def _fft_filter(x, gain_fn):
    """Bellek dostu: kanal kanal, float32, yerinde."""
    n = x.shape[-1]
    freqs = np.fft.rfftfreq(n, 1 / SR)
    g = gain_fn(freqs).astype(np.float64)
    out = np.empty_like(x, dtype=np.float32)
    for ch in range(x.shape[0]):
        spec = np.fft.rfft(x[ch].astype(np.float64))
        spec *= g
        out[ch] = np.fft.irfft(spec, n).astype(np.float32)
        del spec
    return out


def lowpass(x, cutoff, slope=1.5):
    return _fft_filter(x, lambda f: 1.0 / (1.0 + (f / cutoff) ** (2 * slope)))


def highshelf(x, freq, gain_db):
    g = 10 ** (gain_db / 20)
    return _fft_filter(x, lambda f: 1.0 + (g - 1.0) / (1.0 + (freq / (f + 1e-9)) ** 2))


def soft_compress(x, thresh=0.5, ratio=3.0, win_ms=80):
    """Yumusak RMS kompresyonu - ani patlamalari toparlar."""
    win = int(SR * win_ms / 1000)
    mono = np.abs(x).mean(0)
    kernel = np.ones(win) / win
    env = np.sqrt(np.convolve(mono ** 2, kernel, mode="same") + 1e-12)
    gain = np.ones_like(env)
    over = env > thresh
    gain[over] = (thresh + (env[over] - thresh) / ratio) / env[over]
    # kazanci yumusat
    gain = np.convolve(gain, kernel, mode="same")
    return x * gain[None, :]


def measure_lufs_approx(x):
    """
    Yaklasik LUFS (K-agirlikli RMS). ffmpeg loudnorm kadar hassas degil
    ama normalizasyon icin yeterli; son dogrulama ffmpeg ile yapilir.
    """
    # K-weighting kabaca: yuksek gecirgen 60Hz + raf +4dB @ 2kHz
    mono = x.mean(0).astype(np.float64)
    n = len(mono)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    hp = (freqs / 60.0) ** 2 / (1 + (freqs / 60.0) ** 2)
    shelf = 1.0 + 0.58 / (1.0 + (2000.0 / (freqs + 1e-9)) ** 2)
    w = np.fft.irfft(np.fft.rfft(mono) * hp * shelf, n)
    ms = (w ** 2).mean()
    return -0.691 + 10 * np.log10(ms + 1e-12)


def seamless(stereo, cross_sec=8.0):
    c = int(cross_sec * SR)
    n = stereo.shape[1] - c
    head = stereo[:, :c].copy()
    tail = stereo[:, n:n + c].copy()
    t = np.linspace(0, 1, c)
    fi, fo = np.sqrt(t), np.sqrt(1 - t)
    out = stereo[:, :n].copy()
    out[:, :c] = head * fi + tail * fo
    return out


# ---------------------------------------------------------------- kutuphane

def pick_recording(category, rng):
    """approved/ altindan kayit sec. Kategori klasoru yoksa None."""
    folder = APPROVED / category
    if not folder.exists():
        return None
    files = sorted(folder.glob("*.wav"))
    if not files:
        return None
    return files[rng.integers(0, len(files))]


def texture_from_recording(path, need_sec, rng):
    """
    Kayittan rastgele kesit al, hafif hiz varyasyonu uygula,
    gerekirse kendi icinde dongule.
    """
    d, sr = read_wav(path)
    if sr != SR:
        # ffmpeg zaten 44100'e cevirmis olmali; guvenlik icin atla
        pass

    total = d.shape[1]
    need = int(need_sec * SR)

    # hafif hiz varyasyonu (+-%2): ayni kayit her videoda farklilassin
    speed = float(rng.uniform(0.98, 1.02))
    idx = np.arange(0, total - 1, speed)
    idx_i = idx.astype(np.int64)
    frac = idx - idx_i
    d = d[:, idx_i] * (1 - frac) + d[:, np.minimum(idx_i + 1, total - 1)] * frac
    total = d.shape[1]

    if total >= need:
        start = int(rng.integers(0, total - need))
        seg = d[:, start:start + need].copy()
    else:
        # kayit kisa: kusursuz dongulayerek uzat
        looped = seamless(d.copy(), min(4.0, total / SR / 4))
        reps = int(np.ceil(need / looped.shape[1]))
        seg = np.tile(looped, (1, reps))[:, :need].copy()

    return seg


# ---------------------------------------------------------------- ana miks

def build_mix(loop_sec, carrier, beat, label_hz, purpose, category, seed):
    """
    Tam miks: gercek kayit + frekans yatagi.
    category None ise saf frekans moduna duser.
    Doner: (stereo, meta)
    """
    rng = np.random.default_rng(seed)

    # 1) frekans yatagi (v2 motoru, doku kapali)
    bed, meta = ga.build(loop_sec, carrier=carrier, purpose=purpose,
                         texture="none", seed=seed, beat=beat,
                         label_hz=label_hz)

    rec_path = pick_recording(category, rng) if category else None

    if rec_path is None:
        meta["mix"] = "pure"
        return bed, meta

    # 2) gercek kayit katmani
    cross = 8.0
    tex = texture_from_recording(rec_path, loop_sec + cross, rng)

    bed = bed.astype(np.float32)
    tex = tex.astype(np.float32)

    # 3) EQ ile yer acma
    bed_eq = lowpass(bed, 1800, 1.4); del bed
    tex_eq = highshelf(tex, 6500, -2.5); del tex

    # 4) seviyeler: kayit ONDE, frekans yatagi altta
    tex_eq /= (np.abs(tex_eq).max() + 1e-9)
    bed_eq /= (np.abs(bed_eq).max() + 1e-9)
    mix = (0.72 * tex_eq[:, :bed_eq.shape[1]] + 0.34 * bed_eq).astype(np.float32)
    del tex_eq, bed_eq

    # 5) yumusak kompresyon
    mix = soft_compress(mix, thresh=0.45, ratio=2.5)

    # 6) kusursuz dongu
    mix = seamless(mix, cross)

    # 7) LUFS normalizasyonu (yaklasik; ffmpeg son adimda dogrular)
    cur = measure_lufs_approx(mix)
    gain = 10 ** ((TARGET_LUFS - cur) / 20)
    mix = np.clip(mix * gain, -0.98, 0.98)

    meta.update({
        "mix": "recording+bed",
        "recording": rec_path.name,
        "category": category,
        "lufs_pre": round(float(cur), 1),
    })
    return mix, meta


def encode_with_loudnorm(wav_in, m4a_out, total_sec, reps):
    """FFmpeg ile uzat + kesin -14 LUFS normalizasyonu + fade."""
    fade_out_start = max(0, total_sec - 8)
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-stream_loop", str(reps), "-i", str(wav_in),
        "-t", str(total_sec),
        "-af", (f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11,"
                f"afade=t=in:st=0:d=6,"
                f"afade=t=out:st={fade_out_start}:d=8"),
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", str(m4a_out),
    ], check=True)


# kategori secimi: amaca uygun dokular
PURPOSE_CATEGORIES = {
    "sleep":      ["rain", "ocean", "night", "thunder"],
    "meditation": ["stream", "forest", "ocean", "wind"],
    "relax":      ["rain", "stream", "fire", "forest"],
    "focus":      ["rain", "stream", "wind"],
    "study":      ["rain", "fire", "stream"],
}


def choose_category(purpose, rng):
    """approved/ icinde gercekten kaydi OLAN kategorilerden sec."""
    prefer = PURPOSE_CATEGORIES.get(purpose, list(PURPOSE_CATEGORIES["relax"]))
    have = [c for c in prefer if (APPROVED / c).exists()
            and any((APPROVED / c).glob("*.wav"))]
    if not have:
        return None
    return have[int(rng.integers(0, len(have)))]
