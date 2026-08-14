#!/usr/bin/env python3
"""
Sakin piyano ureteci.

Yaklasim:
  - Kompozisyon: prosedurel ama COK basit ve tutucu - yavas arpejler,
    sakin akor yuruyusu, pentatonik susleme. "Ambient piano" turu
    yanlis notaya izin vermeyen bir tur degil; sadelik = guvenlik.
  - Ses: FluidSynth + FluidR3 soundfont (GERCEK piyanodan kaydedilmis
    notalar) -> sentetik "biip" riski yok.
  - Islem: uzun reverb + yumusak filtre -> ruya gibi, uzak piyano hissi.

Cikti: seamless olmayan uzun bir parca (dongu yerine surekli uretim,
cunku muzikte dongu tekrari fark edilir; 10-15 dk uretilir, video
suresine gore tekrarlanmadan kesilir ya da fade ile baglanir).
"""

import random
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 44100
SF2 = "/usr/share/sounds/sf2/FluidR3_GM.sf2"

# Melankolik akor yuruyusleri (minor tonalite, duygusal renkler)
# dereceler A minor'e gore: 0=A, 2=B, 3=C, 5=D, 7=E, 8=F, 10=G
PROGRESSIONS = [
    [(0, "min"),  (8, "maj7"), (3, "maj"),  (7, "maj")],
    [(0, "min7"), (7, "min"),  (8, "maj"),  (10, "maj")],
    [(0, "min"),  (3, "maj7"), (8, "maj"),  (7, "min7")],
    [(0, "min"),  (10, "maj"), (8, "maj7"), (7, "maj")],
    [(5, "min7"), (0, "min"),  (8, "maj"),  (7, "maj")],
    [(0, "min"),  (5, "min7"), (8, "maj7"), (10, "maj")],
    [(0, "sus2"), (8, "maj"),  (5, "min"),  (7, "maj")],
    [(0, "min"),  (7, "min7"), (3, "maj"),  (10, "maj")],
    [(3, "maj7"), (0, "min"),  (8, "maj"),  (7, "maj")],
]

CHORD = {
    "maj":  [0, 4, 7],
    "min":  [0, 3, 7],
    "maj7": [0, 4, 7, 11],   # romantik/ruyamsi
    "min7": [0, 3, 7, 10],   # yumusak huzun
    "sus2": [0, 2, 7],       # acik, cozulmemis
}

# A minor gami (melodi bu notalardan gezer)
SCALE = [0, 2, 3, 5, 7, 8, 10]


def _nearest_scale(semitone):
    """Verilen yarim tonu gamdaki en yakin notaya cek."""
    oct_off = (semitone // 12) * 12
    rel = semitone % 12
    best = min(SCALE, key=lambda x: min(abs(x - rel), 12 - abs(x - rel)))
    return oct_off + best


def compose(minutes, seed):
    """
    Iki elli, duygusal kompozisyon:
      Sol el: bar basinda YAYILI akor (notalar 30-80ms arayla, insan gibi)
      Sag el: melodi cumleleri - soru/cevap, uzun notalar, cumle sonu dusus
      Rubato: tempo cumle icinde dalgalanir
      Dinamik: cumle ortasi yukselir, sonu soner
    """
    rng = random.Random(seed)
    prog = rng.choice(PROGRESSIONS)

    # TON cesitliligi: her parca farkli tonalitede (A, G, B, C, D, E minor)
    key_root = rng.choice([57, 55, 59, 60, 50, 52])

    # TEMPO cesitliligi: dusunceliden akiciya genis yelpaze
    base_tempo = rng.uniform(40, 72)

    # STIL: seyrek (cok az nota) / akan (daha hareketli) / dengeli
    style = rng.choice(["sparse", "balanced", "balanced", "flowing"])
    density = {"sparse": 0.6, "balanced": 1.0, "flowing": 1.5}[style]

    events = []
    t = 0.0
    total = minutes * 60
    phrase_i = 0

    # melodi hafizasi: cumleler birbirine benzesin (motif tekrari = muzikalite)
    motif = None

    while t < total:
        for ci, (root_off, quality) in enumerate(prog):
            if t >= total:
                break
            root = key_root + root_off
            tones = CHORD[quality]
            beat = 60.0 / (base_tempo * rng.uniform(0.92, 1.08))  # rubato
            bar = beat * 4

            # --- SOL EL: yayili akor (arpejlesmis, alttan yukari) ---
            spread = rng.uniform(0.03, 0.09)
            lh_notes = [root - 24, root - 12, root - 12 + tones[1], root - 12 + tones[2]]
            for k, n in enumerate(lh_notes):
                vel = rng.randint(30, 42) - k * 2
                events.append((t + k * spread, bar * 1.9, n, max(24, vel)))

            # bazen bar ortasinda tek bas nota (nefes hissi)
            if rng.random() < 0.4:
                events.append((t + bar * 0.5, bar, root - 12, rng.randint(24, 32)))

            # --- SAG EL: melodi cumlesi ---
            # cumle: 3-6 nota, akor tonlarindan baslar, gam icinde gezer,
            # cumle sonunda asagi cozulur (melankoli imzasi)
            is_answer = (phrase_i % 2 == 1)

            if motif is None or (phrase_i % 4 == 0 and rng.random() < 0.5):
                # yeni motif uret
                n_notes = max(2, int(rng.randint(3, 5) * density))
                motif = []
                cur = root + 12 + rng.choice(tones)
                for i in range(n_notes):
                    motif.append(cur - key_root)
                    step = rng.choice([-2, -1, -1, 1, 2, 3, -3])
                    cur = key_root + _nearest_scale(cur - key_root + step)
                if not is_answer:
                    pass
            # motifi bu akora uyarl a (transpoze + gam duzeltme)
            phrase = [key_root + _nearest_scale(m + root_off) for m in motif]

            if is_answer:
                # cevap cumlesi: ayni motif ama sonda asagi cozulum
                phrase = phrase[:-1] + [key_root + _nearest_scale(
                    phrase[-1] - key_root - rng.choice([2, 3, 4]))]

            # zamanlama: notalar arasi degisken, sona dogru yavaslar
            nt = t + beat * rng.uniform(0.4, 0.9)
            n_ph = len(phrase)
            for i, m in enumerate(phrase):
                if nt >= total:
                    break
                # dinamik yay: ortada zirve, sonda soner
                arc = 1.0 - abs((i / max(1, n_ph - 1)) - 0.45) * 1.2
                vel = int(34 + 26 * max(0.2, arc)) + rng.randint(-4, 4)
                # sure: son nota uzun tinlar
                if i == n_ph - 1:
                    dur = bar * rng.uniform(1.1, 1.6)
                else:
                    dur = beat * rng.uniform(1.2, 1.9)
                events.append((nt, dur, m + 12, min(64, max(26, vel))))
                # duygusal zirvede yumusak oktav ciftleme
                if arc > 0.85 and rng.random() < 0.35:
                    events.append((nt + 0.02, dur, m + 24, max(20, vel - 18)))
                # sona dogru genisleyen aralar (ritardando hissi)
                gap = beat * rng.uniform(0.55, 0.95) * (1.0 + i * 0.12)
                nt += gap

            # bazen cumle sonunda tek suslu nota (ic cekis)
            if rng.random() < 0.3 and nt < total:
                orn = key_root + _nearest_scale(phrase[-1] - key_root + 7) + 12
                events.append((nt + beat * 0.4, bar, orn, rng.randint(24, 34)))

            phrase_i += 1
            t += bar
            # cumleler arasi nefes
            if rng.random() < 0.35:
                t += beat * rng.uniform(0.5, 1.2)

    # PARCA SONU: tonik akorda uzun, sonen cozulum (yarim kalma hissi olmasin)
    root = key_root
    for k, iv in enumerate([-24, -12, -12 + 3, -12 + 7, 0, 3]):
        events.append((t + k * 0.10, 10.0, root + iv, max(20, 40 - k * 3)))
    return events


def write_midi(events, path, tempo_us=1000000):
    """Minimal tek kanalli MIDI yazici (tik = ms)."""
    import struct

    TPQ = 1000  # tik/ceyrek; tempo 60bpm -> 1 tik = 1 ms

    msgs = []
    for start, dur, midi, vel in events:
        midi = max(21, min(108, int(midi)))
        on_t = max(0, int(start * 1000))
        off_t = max(on_t + 100, int((start + dur) * 1000))
        msgs.append((on_t, 0x90, midi, vel))
        msgs.append((off_t, 0x80, midi, 0))
    msgs.sort(key=lambda m: m[0])

    track = bytearray()
    # tempo 60 bpm
    track += bytes([0, 0xFF, 0x51, 0x03]) + (1000000).to_bytes(3, "big")
    # sustain pedal hafif (CC64) - notalar birbirine aksin
    track += bytes([0, 0xB0, 64, 90])
    prev = 0
    for t, st, d1, d2 in msgs:
        delta = max(0, t - prev)
        prev = t
        # variable length
        vl = bytearray()
        v = delta & 0x7F
        vl.insert(0, v)
        delta >>= 7
        while delta:
            vl.insert(0, (delta & 0x7F) | 0x80)
            delta >>= 7
        track += vl + bytes([st, d1, d2])
    track += bytes([0, 0xFF, 0x2F, 0x00])

    with open(path, "wb") as f:
        f.write(b"MThd" + struct.pack(">IHHH", 6, 0, 1, TPQ))
        f.write(b"MTrk" + struct.pack(">I", len(track)) + bytes(track))


def _reverb_chain(seed):
    """Parcaya gore degisen oda derinligi."""
    r = random.Random(seed + 7)
    depth = r.choice(["intimate", "room", "hall"])
    if depth == "intimate":
        echo = "aecho=0.8:0.8:40|90|180:0.35|0.25|0.15"
        lp = 5600
    elif depth == "room":
        echo = "aecho=0.8:0.85:60|110|230|420:0.4|0.32|0.22|0.14"
        lp = 5200
    else:
        echo = "aecho=0.85:0.9:80|150|300|520|760:0.42|0.34|0.26|0.18|0.11"
        lp = 4800
    return f"{echo},lowpass=f={lp},volume=1.4"


def render_piano(minutes, seed, out_wav):
    """Kompozisyon -> MIDI -> FluidSynth -> reverb -> WAV."""
    tmp_mid = Path("/tmp/piano.mid")
    tmp_dry = Path("/tmp/piano_dry.wav")

    events = compose(minutes, seed)
    write_midi(events, tmp_mid)

    # FluidSynth: gercek piyano ornekleriyle render
    subprocess.run(
        ["fluidsynth", "-ni", "-g", "0.7", "-F", str(tmp_dry),
         "-r", str(SR), SF2, str(tmp_mid)],
        check=True, capture_output=True)

    # uzun, yumusak reverb + hafif alcak gecirgen (ruya hissi)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp_dry),
         "-af",
         _reverb_chain(seed),
         "-ar", str(SR), "-ac", "2", "/tmp/piano_wet.wav"],
        check=True)

    # normalize: tepe -6 dB civari (mikste yer kalsin)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", "/tmp/piano_wet.wav",
         "-af", "loudnorm=I=-20:TP=-3:LRA=9",
         "-ar", str(SR), "-ac", "2", str(out_wav)],
        check=True)
    Path("/tmp/piano_wet.wav").unlink(missing_ok=True)

    tmp_mid.unlink(missing_ok=True)
    tmp_dry.unlink(missing_ok=True)
    return out_wav


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=2)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="piano.wav")
    a = ap.parse_args()
    render_piano(a.minutes, a.seed, a.out)
    print("hazir:", a.out)
