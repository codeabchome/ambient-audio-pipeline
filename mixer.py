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
    """WAV veya FLAC oku (FLAC ise once WAV'a cevir)."""
    path = Path(path)
    if path.suffix.lower() != ".wav":
        tmp = Path("/tmp") / (path.stem + "_dec.wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path),
                        "-ar", str(SR), "-ac", "2", str(tmp)], check=True)
        path = tmp
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
    files = sorted(list(folder.glob("*.wav")) + list(folder.glob("*.flac")))
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

def build_mix(loop_sec, carrier, beat, label_hz, purpose, category, seed,
              piano=False):
    """
    Uc bagimsiz mod:
      category None            -> saf frekans (generate_audio v2)
      category dolu, piano=F   -> SADECE gercek kayit
      category dolu, piano=T   -> gercek kayit + duygusal piyano
    Frekans tonu ile doga/piyano ASLA karismaz.
    """
    rng = np.random.default_rng(seed)

    rec_path = pick_recording(category, rng) if category else None

    if rec_path is None:
        stereo, meta = ga.build(loop_sec, carrier=carrier, purpose=purpose,
                                texture="none", seed=seed, beat=beat,
                                label_hz=label_hz)
        meta["mix"] = "pure"
        return stereo, meta

    cross = 8.0
    tex = texture_from_recording(rec_path, loop_sec + cross, rng).astype(np.float32)

    # sadece temizlik: cok tiz sertligi hafif al
    tex = highshelf(tex, 7000, -2.0)

    # yumusak kompresyon: ani seviye oynamalarini topla
    tex = soft_compress(tex, thresh=0.5, ratio=2.5)

    # kusursuz dongu
    tex = seamless(tex, cross)

    # yaklasik LUFS hedefe cek (kesin deger encode'da loudnorm ile)
    cur = measure_lufs_approx(tex)
    gain = 10 ** ((TARGET_LUFS - cur) / 20)
    tex = np.clip(tex * gain, -0.98, 0.98)

    if piano:
        import piano as pn
        pw = Path("/tmp/mix_piano.wav")
        pn.render_piano(loop_sec / 60 + 0.5, seed + 11, pw)
        pd, psr = read_wav(pw)
        pd = pd[:, :tex.shape[1]].astype(np.float32)
        if pd.shape[1] < tex.shape[1]:
            pad = np.zeros((2, tex.shape[1] - pd.shape[1]), dtype=np.float32)
            pd = np.concatenate([pd, pad], axis=1)
        # piyano yagmurun YANINDA net duyulur ama bogmasin
        pd /= (np.abs(pd).max() + 1e-9)
        tex /= (np.abs(tex).max() + 1e-9)
        tex = (0.62 * pd + 0.55 * tex).astype(np.float32)
        tex = soft_compress(tex, thresh=0.5, ratio=2.2)
        tex = seamless(tex, cross)
        cur2 = measure_lufs_approx(tex)
        tex = np.clip(tex * 10 ** ((TARGET_LUFS - cur2) / 20), -0.98, 0.98)
        pw.unlink(missing_ok=True)

    meta = {
        "mix": "nature_piano" if piano else "nature",
        "recording": rec_path.name,
        "category": category,
        "lufs_pre": round(float(cur), 1),
        "carrier_hz": label_hz, "played_hz": 0,
        "beat_hz": 0, "purpose": purpose,
        "texture": category, "loop_seconds": loop_sec,
        "seed": seed, "engine": "nature-v1",
    }
    return tex, meta


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
    "sleep":      ["rain", "ocean", "thunder", "wind"],
    "meditation": ["stream", "forest", "ocean", "wind"],
    "relax":      ["rain", "stream", "fire", "forest"],
    "focus":      ["rain", "stream", "wind"],
    "study":      ["rain", "fire", "stream"],
}


def choose_category(purpose, rng):
    """approved/ icinde gercekten kaydi OLAN kategorilerden sec."""
    prefer = PURPOSE_CATEGORIES.get(purpose, list(PURPOSE_CATEGORIES["relax"]))
    have = [c for c in prefer if (APPROVED / c).exists()
            and (any((APPROVED / c).glob("*.wav")) or any((APPROVED / c).glob("*.flac")))]
    if not have:
        return None
    return have[int(rng.integers(0, len(have)))]


# ---------------------------------------------------------------- tarif miksi

def build_recipe(loop_sec, recipe, seed):
    """
    Tarife gore cok katmanli doga miksi (+ istege bagli piyano).
    Katmanlar tarifteki seviyelerle toplanir, sonra ortak isleme girer.
    """
    rng = np.random.default_rng(seed)
    cross = 8.0
    need = loop_sec + cross

    layers, used = [], []
    for cat, lvl in recipe["layers"]:
        path = pick_recording(cat, rng)
        if path is None:
            continue
        seg = texture_from_recording(path, need, rng).astype(np.float32)
        seg = highshelf(seg, 7000, -2.0)
        seg /= (np.abs(seg).max() + 1e-9)
        layers.append(seg * lvl)
        used.append(path.name)

    if not layers:
        return None, None

    n = min(l.shape[1] for l in layers)
    mix = np.zeros((2, n), dtype=np.float32)
    for l in layers:
        mix += l[:, :n]

    piano_file = None
    if recipe.get("piano"):
        import piano as pn
        pw = Path("/tmp/recipe_piano.wav")
        pn.render_piano(loop_sec / 60 + 0.6, seed + 11, pw)
        pd, _ = read_wav(pw)
        pd = pd[:, :n].astype(np.float32)
        if pd.shape[1] < n:
            pd = np.concatenate(
                [pd, np.zeros((2, n - pd.shape[1]), dtype=np.float32)], axis=1)
        pd /= (np.abs(pd).max() + 1e-9)
        mix /= (np.abs(mix).max() + 1e-9)
        # piyano onde-net, doga altta sarici
        mix = (0.60 * pd + 0.62 * mix).astype(np.float32)
        pw.unlink(missing_ok=True)
        piano_file = "procedural"

    mix = soft_compress(mix, thresh=0.5, ratio=2.3)
    mix = seamless(mix, cross)
    cur = measure_lufs_approx(mix)
    mix = np.clip(mix * 10 ** ((TARGET_LUFS - cur) / 20), -0.98, 0.98)

    meta = {
        "mix": "recipe",
        "recipe": recipe["id"],
        "carrier_hz": 0, "played_hz": 0, "beat_hz": 0,
        "purpose": "sleep",
        "layers": [c for c, _ in recipe["layers"]],
        "recordings": used,
        "piano": bool(piano_file),
        "video_key": recipe["video"],
        "lufs_pre": round(float(cur), 1),
        "loop_seconds": loop_sec,
        "seed": seed,
        "engine": "recipe-v1",
    }
    return mix, meta
