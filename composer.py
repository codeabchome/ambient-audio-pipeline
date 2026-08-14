#!/usr/bin/env python3
"""
Cok enstrumanli, TUR SABLONLU besteci.

Ilke: "ne kadar cok enstruman o kadar iyi" DEGIL - her tur, o turde
gercekte kullanilan enstrumanlarla ve o turun kurallarina gore uretilir.
Sablonlar kati: Deep Work motoru duygusal melodi atmaz, Sleep hizlanmaz.

Turler:
  deep_work  - minimal piyano + cok hafif pad; tekrarlayan sakin motifler,
               dar dinamik (dikkat dagitmaz)
  sleep      - cok yavas seyrek piyano + legato yayli halilar; derin reverb
  meditation - pad drone + nadir piyano dokunuslari; neredeyse zamansiz
  emotional  - mevcut melankolik solo piyano (piano.py motoru)

Ses: FluidSynth + FluidR3 (gercek ornekler). Kanal bazli program:
  ch0 = piyano(0), ch1 = yayli(48), ch2 = pad(89/92)
"""

import random
import struct
import subprocess
import wave
from pathlib import Path

import numpy as np

import piano as pn   # sadece _make_ir (reverb) kullaniliyor

SR = 44100
SF2 = "/usr/share/sounds/sf2/FluidR3_GM.sf2"

SCALE = [0, 2, 3, 5, 7, 8, 10]          # dogal minor


def _nearest_scale(semi):
    oct_off = (semi // 12) * 12
    rel = semi % 12
    best = min(SCALE, key=lambda x: min(abs(x - rel), 12 - abs(x - rel)))
    return oct_off + best


# ---------------------------------------------------------------- MIDI (coklu kanal)

def write_midi_multi(events, path):
    """
    events: (start_s, dur_s, midi, vel, ch) listesi.
    ch: 0 piyano, 1 yayli, 2 pad.  midi=-1/-2 pedal off/on (ch'e uygulanir).
    """
    TPQ = 1000
    msgs = []
    # program atamalari
    for ch, prog in ((0, 0), (1, 48), (2, 89), (3, 89), (4, 48)):
        msgs.append((0, 0xC0 | ch, prog, None))
        # kanal ses seviyesi (CC7)
        vol = {0: 100, 1: 88, 2: 80, 3: 80, 4: 88}[ch]
        msgs.append((0, 0xB0 | ch, 7, vol))
        # hafif genislik: pan (CC10) - piyano orta, yayli sol, pad sag
        pan = {0: 64, 1: 46, 2: 82, 3: 82, 4: 46}[ch]
        msgs.append((0, 0xB0 | ch, 10, pan))

    for start, dur, midi, vel, ch in events:
        t = max(0, int(start * 1000))
        if midi == -1:
            msgs.append((t, 0xB0 | ch, 64, 0)); continue
        if midi == -2:
            msgs.append((t, 0xB0 | ch, 64, int(vel))); continue
        m = max(21, min(108, int(midi)))
        off = max(t + 120, int((start + dur) * 1000))
        msgs.append((t, 0x90 | ch, m, int(vel)))
        msgs.append((off, 0x80 | ch, m, 0))

    msgs.sort(key=lambda x: x[0])
    track = bytearray()
    track += bytes([0, 0xFF, 0x51, 0x03]) + (1000000).to_bytes(3, "big")
    prev = 0
    for t, st, d1, d2 in msgs:
        delta = max(0, t - prev); prev = t
        vl = bytearray(); v = delta & 0x7F; vl.insert(0, v); delta >>= 7
        while delta:
            vl.insert(0, (delta & 0x7F) | 0x80); delta >>= 7
        if d2 is None:
            track += vl + bytes([st, d1])
        else:
            track += vl + bytes([st, d1, d2])
    track += bytes([0, 0xFF, 0x2F, 0x00])
    with open(path, "wb") as f:
        f.write(b"MThd" + struct.pack(">IHHH", 6, 0, 1, TPQ))
        f.write(b"MTrk" + struct.pack(">I", len(track)) + bytes(track))


# ---------------------------------------------------------------- tur sablonlari

def compose_deep_work(minutes, seed):
    """
    Minimal, dongusel, dikkat dagitmayan.
    - Kisa motif (3-4 nota) SUREKLI tekrar, cok yavas evrim
    - Dar velocity araligi (dinamik surpriz yok)
    - Pad cok kisik, tek akor uzun tutar
    """
    rng = random.Random(seed)
    key = rng.choice([57, 55, 60, 62])
    tempo = rng.uniform(58, 68)
    beat = 60.0 / tempo
    ev = []
    t, total = 0.0, minutes * 60

    # tek motif uret, parca boyunca dondur
    motif_iv = []
    cur = 12
    for _ in range(rng.randint(3, 4)):
        motif_iv.append(cur)
        cur = _nearest_scale(cur + rng.choice([2, 3, -2, 5, -3]))
    prog = [(0, [0, 3, 7]), (8, [0, 4, 7]), (5, [0, 3, 7]), (7, [0, 4, 7])]

    bar_i = 0
    while t < total:
        root_off, tones = prog[bar_i % len(prog)]
        root = key + root_off
        bar = beat * 4

        # pad: bar basinda akor, cok uzun (ch2)
        if bar_i % 2 == 0:
            pch = 2 if (bar_i // 2) % 2 == 0 else 3
            for k, iv in enumerate(tones[:2]):
                ev.append((t + k*0.05, bar*2.2, root - 12 + iv, 30, pch))

        # yayli doku: akorun ust sesleri kisa-orta tutuslarla nefes alir
        sch = 1 if bar_i % 2 == 0 else 4
        for i, iv in enumerate(motif_iv[:3]):
            nt = t + i * beat * rng.uniform(1.6, 2.2)
            vel = rng.randint(28, 38)
            ev.append((nt, beat * rng.uniform(2.5, 3.5),
                       root + _nearest_scale(iv + root_off) - root_off + 12, vel, sch))
        # 8 barda bir dokuda tek ses degisir (yavas evrim)
        if bar_i % 8 == 7 and rng.random() < 0.6:
            j = rng.randrange(len(motif_iv))
            motif_iv[j] = _nearest_scale(motif_iv[j] + rng.choice([-2, 2]))

        t += bar
        bar_i += 1
    return ev, "deep_work"


def compose_sleep(minutes, seed):
    """
    Cok yavas, seyrek piyano + legato yayli halilar.
    - Yayli: uzun, ust uste binen akor tutuslari
    - Piyano: nadir, yumusak tek notalar / kucuk cifte
    """
    rng = random.Random(seed)
    key = rng.choice([55, 57, 52])
    tempo = rng.uniform(36, 44)
    beat = 60.0 / tempo
    ev = []
    t, total = 0.0, minutes * 60
    prog = [(0, [0, 3, 7, 10]), (8, [0, 4, 7, 11]), (5, [0, 3, 7]), (7, [0, 3, 7, 10])]
    bar_i = 0
    while t < total:
        root_off, tones = prog[bar_i % len(prog)]
        root = key + root_off
        bar = beat * 4

        # yayli hali: uzun overlap, almasik kanal (nota cakismasi olmaz)
        sch = 1 if bar_i % 2 == 0 else 4
        for k, iv in enumerate(tones):
            ev.append((t + k * 0.30, bar * 2.4, root - 12 + iv,
                       rng.randint(30, 40) - k * 2, sch))

        # ust pad nefesi: nadir, yumusak tek ses (piyano yerine)
        if rng.random() < 0.6:
            pch = 2 if bar_i % 2 == 0 else 3
            iv = rng.choice(tones)
            ev.append((t + rng.uniform(0.4, bar * 0.6), bar * 1.8,
                       root + iv + 12, rng.randint(20, 28), pch))

        t += bar
        bar_i += 1
    return ev, "sleep"


def compose_meditation(minutes, seed):
    """
    Drone + nadir piyano dokunuslari. Neredeyse zamansiz.
    - Pad: tonik drone surekli, bes araliginda gidip gelen ikinci ses
    - Piyano: 15-30 sn'de bir tek yumusak nota
    """
    rng = random.Random(seed)
    key = rng.choice([50, 52, 55, 57])
    ev = []
    total = minutes * 60

    # drone (ch2): uzun ust uste segmentler
    seg = 20.0
    t = 0.0
    si = 0
    while t < total:
        ch = 2 if si % 2 == 0 else 3          # almasik kanal: nota cakismasi olmaz
        ev.append((t, seg * 1.6, key - 12, 34, ch))
        ev.append((t + rng.uniform(2, 6), seg * 1.5, key - 5, 26, ch))
        if rng.random() < 0.5:
            ev.append((t + rng.uniform(4, 9), seg * 1.4, key + 7 - 12, 22, ch))
        t += seg
        si += 1

    # yayli nefes (ch1): arada bir uzun tek ses
    t = rng.uniform(8, 15)
    while t < total:
        iv = rng.choice([0, 3, 7, 10])
        ev.append((t, rng.uniform(10, 16), key + iv, rng.randint(24, 32), 1))
        t += rng.uniform(14, 26)

    # ust yayli dokunuslari: nadir, uzun tek sesler (piyano yerine)
    t = rng.uniform(6, 12)
    while t < total:
        iv = _nearest_scale(rng.choice([0, 3, 7, 12]))
        ch = 1 if int(t) % 2 == 0 else 4
        ev.append((t, rng.uniform(8, 12), key + 12 + iv, rng.randint(20, 30), ch))
        t += rng.uniform(18, 32)
    return ev, "meditation"


GENRES = {
    "deep_work":  compose_deep_work,
    "sleep":      compose_sleep,
    "meditation": compose_meditation,
}


# ---------------------------------------------------------------- render

def render_music(genre, minutes, seed, out_wav):
    """Tur sablonuyla bestele -> FluidSynth -> convolution reverb + EQ."""
    ev, g = GENRES[genre](minutes, seed)
    mid = Path("/tmp/music.mid")
    dry = Path("/tmp/music_dry.wav")
    write_midi_multi(ev, mid)

    subprocess.run(
        ["fluidsynth", "-ni", "-g", "0.7", "-F", str(dry),
         "-r", str(SR), SF2, str(mid)],
        check=True, capture_output=True)

    # tur bazli oda: deep_work yakin oda, sleep/meditation genis salon
    kind = {"deep_work": "room", "sleep": "hall", "meditation": "hall"}[g]
    ir = pn._make_ir(kind, seed)
    wet = {"room": 0.34, "hall": 0.48}[kind]

    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-i", str(dry), "-i", str(ir),
         "-filter_complex",
         (f"[0:a][1:a]afir=dry=1:wet={wet}:maxir=4:gtype=2[rv];"
          f"[rv]highpass=f=45,"
          f"equalizer=f=250:t=q:w=1.1:g=-2.0,"
          f"equalizer=f=4200:t=q:w=1.6:g=+1.2,"
          f"equalizer=f=9000:t=q:w=1.2:g=+0.8,"
          f"lowpass=f=12500,volume=1.3[out]"),
         "-map", "[out]", "-ar", str(SR), "-ac", "2", "/tmp/music_wet.wav"],
        check=True)
    ir.unlink(missing_ok=True)

    lufs = {"deep_work": -19, "sleep": -21, "meditation": -22}[g]
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", "/tmp/music_wet.wav",
         "-af", f"loudnorm=I={lufs}:TP=-3:LRA=9",
         "-ar", str(SR), "-ac", "2", str(out_wav)],
        check=True)
    for f in (mid, dry, Path("/tmp/music_wet.wav")):
        f.unlink(missing_ok=True)
    return out_wav


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--genre", required=True,
                    choices=["deep_work", "sleep", "meditation"])
    ap.add_argument("--minutes", type=float, default=1.5)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="music.wav")
    a = ap.parse_args()
    render_music(a.genre, a.minutes, a.seed, a.out)
    print("hazir:", a.out)


# ---------------------------------------------------------------- basliklar

MUSIC_PACK = {
    "deep_work": {
        "title": "Deep Work Music",
        "sub": "Maximum Focus & Productivity",
        "scene": "focus",
        "tags": ["deep work music", "focus music", "study music",
                 "concentration music", "productivity", "work music",
                 "ambient study", "coding music"],
    },
    "sleep": {
        "title": "Deep Sleep Music",
        "sub": "Fall Asleep Fast & Sleep Deeply",
        "scene": "sleep",
        "tags": ["sleep music", "deep sleep music", "fall asleep fast",
                 "relaxing sleep", "insomnia", "calm music", "ambient sleep"],
    },
    "meditation": {
        "title": "Meditation Music",
        "sub": "Inner Peace & Deep Stillness",
        "scene": "meditation",
        "tags": ["meditation music", "ambient meditation", "inner peace",
                 "zen music", "mindfulness", "drone ambient", "spiritual"],
    },
}


def music_title(genre, duration_label):
    pk = MUSIC_PACK[genre]
    title = f"{pk['title']} | {pk['sub']} | {duration_label}"
    desc = (f"{pk['title']} — {pk['sub'].lower()}.\n\n"
            f"{duration_label} of continuous, seamlessly flowing ambient music. "
            f"No sudden changes, no vocals — a calm bed of strings and soft pads, "
            f"composed and rendered exclusively for this channel.\n\n"
            f"Play it while you work, study, meditate or rest.\n\n"
            f"Every piece on this channel is original — nothing is sampled "
            f"from other artists.")
    tags = (pk["tags"] + ["1 hour", "no vocals", "ambient music",
                          "relaxing music"])[:15]
    return title, desc, tags, pk["scene"]
