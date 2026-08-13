#!/usr/bin/env python3
"""
Tam video boru hatti:
  ses uret -> gorsel getir -> hareket dongusu render et -> 1 saate uzat -> metadata yaz

Kritik hiz numarasi: 1 saatlik video bastan sona render EDILMEZ.
60 saniyelik kusursuz donen bir hareket segmenti render edilir,
sonra -c copy ile 60 kez tekrarlanir (yeniden kodlama yok).
"""

import argparse
import json
import os
import random
import subprocess
import sys
import urllib.parse
import urllib.request

from PIL import Image
from pathlib import Path

import generate_audio as ga

# ------------------------------------------------------------------ ayarlar

WIDTH, HEIGHT = 1920, 1080
FPS = 24
MOTION_LOOP_SEC = 60          # render edilen tek segment
AUDIO_LOOP_SEC = 600          # uretilen ses dongusu (10 dk)

# Gorsel temalari - amaca gore
SCENE_PROMPTS = {
    "sleep": [
        "calm night sky over still lake, deep blue, soft moonlight, minimal, serene, cinematic",
        "misty forest at night, soft moonlight through trees, deep blue tones, peaceful",
        "quiet starry sky above dark mountains, subtle aurora, tranquil, wide shot",
    ],
    "meditation": [
        "soft sunrise over calm ocean horizon, warm gentle light, minimal, serene",
        "zen misty mountain valley at dawn, layered peaks, soft pastel light, tranquil",
        "still water reflecting pale sky, minimal composition, soft gradient, peaceful",
    ],
    "relax": [
        "gentle rain on a window with soft bokeh lights, warm cozy tones, calm",
        "quiet beach at golden hour, soft waves, warm light, minimal, serene",
        "soft rolling green hills under pastel sky, calm, wide cinematic view",
    ],
    "focus": [
        "minimal desk by a rainy window, soft warm lamp light, calm study atmosphere",
        "quiet library corner with soft warm light, shelves blurred, cozy focused mood",
        "clean minimal workspace at dusk, soft ambient light, calm and uncluttered",
    ],
    "study": [
        "cozy study nook with rain on window, warm lamp, books, calm focused mood",
        "soft morning light on a quiet desk, minimal, warm neutral tones, peaceful",
        "warm cafe window seat at dusk, soft bokeh, calm study atmosphere",
    ],
}

PURPOSE_LABEL = {
    "sleep": "Deep Sleep Music",
    "meditation": "Meditation Music",
    "relax": "Relaxing Music",
    "focus": "Focus Music",
    "study": "Study Music",
}

TEXTURE_LABEL = {
    "fire": "Fireplace",
    "whitenoise": "White Noise",
    "rain": "Rain Sounds",
    "ocean": "Ocean Waves",
    "wind": "Soft Wind",
    "stream": "Flowing Stream",
    "none": "Pure Tone",
}


# ------------------------------------------------------------------ yardimci

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("FFmpeg hata:", r.stderr[-2000:], file=sys.stderr)
        raise SystemExit(1)
    return r


def build_background(out_path, seed, purpose):
    """
    Kapak gorseli: kod ile uretilen simetrik cekici deseni.
    Dis API yok -> her zaman calisir, telif sorunu yok, sinirsiz cesit.
    """
    import artgen
    # amaca gore palet egilimi (uyku daha soguk, odak daha canli)
    prefer = {
        "sleep":      ["orchid", "nebula", "aurora"],
        "meditation": ["aurora", "reef", "orchid"],
        "relax":      ["reef", "aurora", "prism"],
        "focus":      ["prism", "spectra", "reef"],
        "study":      ["spectra", "prism", "nebula"],
    }.get(purpose, list(artgen.PALETTES))

    rng = random.Random(seed)
    palette = rng.choice(prefer)
    sym = rng.choice(["mirror", "mirror", "quad"])

    img, meta = artgen.generate(seed, 2560, 1440, palette=palette, symmetry=sym)
    img.save(out_path)
    print(f"Gorsel uretildi: {meta}")
    return meta


def build_titles(meta, total_sec=3600):
    """
    Tur konvansiyonuna uygun baslik:
        "528 Hz The Miracle Tone | DNA Repair & Transformation | 1 Hour"
    """
    import schedule as sch

    hz = meta["carrier_hz"]
    name, benefit = sch.name_for(hz)
    hz_txt = sch.format_hz(hz)

    hours = total_sec / 3600
    if hours >= 1:
        h = int(round(hours))
        dur = f"{h} Hour" if h == 1 else f"{h} Hours"
    else:
        dur = f"{int(round(total_sec/60))} Minutes"

    title = f"{hz_txt} Hz {name} | {benefit} | {dur}"

    mode = meta.get("mode", "tone")
    if mode == "beat":
        how = (f"A {hz_txt} Hz binaural beat. Two close tones are played, one in "
               f"each ear, and the brain perceives the {hz_txt} Hz difference "
               f"between them. Frequencies this low cannot be heard directly, "
               f"so headphones are essential.")
    else:
        how = (f"A {hz_txt} Hz tone with a {meta['beat_hz']} Hz binaural beat "
               f"beneath it, on a soft ambient bed. Headphones are recommended.")

    desc = (
        f"{hz_txt} Hz — {name}.\n{benefit}.\n\n"
        f"{how}\n\n"
        f"{dur} of continuous, seamlessly looping sound. Play it while you sleep, "
        f"meditate, read or rest.\n\n"
        f"All audio is original and synthesised for this channel.\n\n"
        f"Sound is not a treatment. If something hurts or worries you, "
        f"please speak to a doctor."
    )

    tags = [
        f"{hz_txt}hz", f"{hz_txt} hz", f"{hz_txt}hz frequency",
        name.lower(), "healing frequency", "binaural beats",
        "sleep music", "meditation music", "relaxing music",
        "sound healing", "solfeggio", "ambient", "study music", "calm",
    ]
    return title, desc, tags[:15]


# ------------------------------------------------------------------ ana akis

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="out")
    ap.add_argument("--hours", type=float, default=1.0)
    ap.add_argument("--carrier", type=float, default=None)
    ap.add_argument("--purpose", default=None)
    ap.add_argument("--texture", default=None)
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()

    seed = a.seed if a.seed is not None else random.randrange(1, 10**9)
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)

    # 1) ses  -- frekans plandan sirayla gelir
    print("== 1/5  ses uretiliyor")
    import schedule as sch

    if a.carrier:
        hz = float(a.carrier)
    else:
        hz = sch.next_frequency(advance=True)

    plan = sch.plan_for(hz)
    print(f"Frekans: {sch.format_hz(hz)} Hz  ({plan['mode']} modu)")

    stereo, meta = ga.build(
        AUDIO_LOOP_SEC,
        carrier=plan["carrier"],
        purpose=a.purpose,
        texture=a.texture or "none",
        seed=seed,
        beat=plan["beat"],
        label_hz=plan["label_hz"],
    )
    meta["mode"] = plan["mode"]
    wav = out / "loop.wav"
    ga.write_wav(stereo, wav)
    del stereo
    print(json.dumps(meta, indent=2))

    # 2) gorsel + kapak yazisi
    print("== 2/5  gorsel hazirlaniyor")
    raw = out / "art.png"
    img = out / "bg.png"
    art_meta = build_background(raw, int(hz * 1000) + seed % 1000, meta["purpose"])

    import cover
    total_sec_tmp = int(a.hours * 3600)
    hrs = total_sec_tmp / 3600
    dur_lbl = (f"{int(round(hrs))} Hour" if abs(hrs - 1) < 0.01 else
               (f"{int(round(hrs))} Hours" if hrs >= 1 else
                f"{int(round(total_sec_tmp/60))} Minutes"))
    fname, fbenefit = sch.name_for(meta["carrier_hz"])
    cover_img = cover.add_text(
        Image.open(raw),
        sch.format_hz(meta["carrier_hz"]),
        fname,
        fbenefit,
        dur_lbl,
        purpose=meta["purpose"],
        channel="TONEBED",
    )
    cover_img.save(img)

    # YouTube kucuk resim siniri 2 MB -> ayri, sikistirilmis JPEG uret
    thumb = out / "thumb.jpg"
    t = cover_img.copy()
    t.thumbnail((1280, 720), Image.LANCZOS)
    for q in (90, 85, 78, 70, 60):
        t.save(thumb, "JPEG", quality=q, optimize=True)
        if thumb.stat().st_size < 1_900_000:
            break
    print(f"Kapak yazisi eklendi (kucuk resim {thumb.stat().st_size//1024} KB)")

    total_sec = int(a.hours * 3600)

    # 3) hareket dongusu
    print("== 3/5  hareket dongusu render ediliyor")
    if True:
        frames = MOTION_LOOP_SEC * FPS
        motion = out / "motion.mp4"
        zexpr = f"1.0+0.04*(0.5-0.5*cos(2*PI*on/{frames}))"
        huexpr = f"26*sin(2*PI*t/{MOTION_LOOP_SEC})"
        run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-loop", "1", "-framerate", str(FPS), "-t", str(MOTION_LOOP_SEC), "-i", str(img),
            "-vf", (f"scale=2560:-2,"
                    f"zoompan=z='{zexpr}':d=1:"
                    f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                    f"s={WIDTH}x{HEIGHT}:fps={FPS},"
                    f"hue=h='{huexpr}':s=1.05,"
                    f"format=yuv420p"),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "29",
            "-g", str(FPS * 4), "-an", str(motion),
        ])
        video_reps = max(1, -(-total_sec // MOTION_LOOP_SEC)) - 1

    # 4) sesi hedef sureye uzat + encode
    print("== 4/5  ses hedef sureye uzatiliyor")
    audio_reps = max(1, -(-total_sec // AUDIO_LOOP_SEC)) - 1
    m4a = out / "audio.m4a"
    # yumusak acilis/kapanis TAM sureye bir kez uygulanir
    # (dongunun icine konursa her tekrarda kesinti olusur)
    fade_in = 6
    fade_out = 8
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-stream_loop", str(audio_reps), "-i", str(wav),
        "-t", str(total_sec),
        "-af", (f"afade=t=in:st=0:d={fade_in},"
                f"afade=t=out:st={max(0, total_sec - fade_out)}:d={fade_out}"),
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", str(m4a),
    ])

    # 5) birlestir (-c copy => yeniden kodlama yok, saniyeler surer)
    print("== 5/5  video birlestiriliyor")
    final = out / "video.mp4"
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-stream_loop", str(video_reps), "-i", str(motion),
        "-i", str(m4a),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "copy",
        "-t", str(total_sec), "-movflags", "+faststart", str(final),
    ])

    # metadata
    title, desc, tags = build_titles(meta, total_sec)
    meta.update({"title": title, "description": desc, "tags": tags,
                 "art": art_meta, "duration_sec": total_sec,
                 "video": str(final), "thumbnail": str(thumb)})
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    # ara dosyalari temizle (disk sismesin)
    for f in (wav, motion, m4a, raw):
        f.unlink(missing_ok=True)

    size = final.stat().st_size / 1e6
    print(f"\nTAMAM  {final}  ({size:.0f} MB)")
    print(f"Baslik: {title}")


if __name__ == "__main__":
    main()
