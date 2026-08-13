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
    """SEO basligi + aciklama + etiketler."""
    hz = meta["carrier_hz"]
    purpose = meta["purpose"]
    tex = meta["texture"]
    beat = meta["beat_hz"]

    p_label = PURPOSE_LABEL[purpose]
    t_label = TEXTURE_LABEL[tex]

    hours = total_sec / 3600
    if hours >= 1:
        h = int(round(hours))
        dur = f"{h} Hour" if h == 1 else f"{h} Hours"
    else:
        dur = f"{int(round(total_sec/60))} Minutes"

    if tex == "none":
        title = f"{hz}Hz {p_label} | Binaural Beats | {dur}"
    else:
        title = f"{hz}Hz {p_label} with {t_label} | {dur}"

    desc = (
        f"{hz}Hz tone with a {beat}Hz binaural beat, layered with "
        f"{t_label.lower()}. {dur} of continuous, seamlessly looping ambience "
        f"for {purpose}.\n\n"
        f"Headphones are recommended for the binaural effect.\n\n"
        f"Carrier: {hz}Hz ({meta['carrier_meaning']})\n"
        f"Binaural beat: {beat}Hz\n"
        f"Texture: {t_label}\n\n"
        f"All audio is original and synthesised for this channel.\n\n"
        f"This is ambience for rest and focus, not medical advice or treatment."
    )

    tags = [
        f"{hz}hz", f"{hz} hz", "binaural beats", p_label.lower(),
        "sleep music", "meditation music", "relaxing music",
        "study music", "focus music", "ambient", "1 hour",
        t_label.lower(), "healing frequency", "solfeggio",
    ]
    return title, desc, tags[:15]


def render_pomodoro(bg_path, out_path, total_sec, work_min=25, break_min=5):
    """
    Pomodoro sayaci: 25 dk calisma / 5 dk mola dongusu.
    Sayac her saniye degistigi icin dongu numarasi kullanilamaz,
    tum sure render edilir. Arka plan yumusatilir:
      - dosya 14 kat kuculur (detayli desen sikismiyor)
      - sayac cok daha okunakli olur
    """
    from PIL import Image, ImageFilter, ImageEnhance

    soft = out_path.parent / "pomo_bg.png"
    im = Image.open(bg_path).convert("RGB").resize((WIDTH, HEIGHT), Image.LANCZOS)
    im = im.filter(ImageFilter.GaussianBlur(18))
    im = ImageEnhance.Brightness(im).enhance(0.55)
    im.save(soft)

    cycle = (work_min + break_min) * 60
    work_s = work_min * 60

    font = None
    for c in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "fonts/JosefinSans.ttf"):
        if Path(c).exists():
            font = c
            break

    # kalan sure: calisma icindeyse work_s'den, molada ise cycle'dan geri sayar
    rem = f"if(lt(mod(t\\,{cycle})\\,{work_s}), {work_s}-mod(t\\,{cycle}), {cycle}-mod(t\\,{cycle}))"
    mm = f"%{{eif\\:floor(({rem})/60)\\:d\\:2}}"
    ss = f"%{{eif\\:mod(floor({rem})\\,60)\\:d\\:2}}"
    label = f"%{{eif\\:1\\:d\\:1}}"

    draw = (f"drawtext=fontfile={font}:text='{mm}\\:{ss}':"
            f"fontsize=220:fontcolor=white:"
            f"shadowcolor=black@0.7:shadowx=4:shadowy=4:"
            f"x=(w-tw)/2:y=(h-th)/2-30")
    # calisma/mola etiketi
    phase = (f"drawtext=fontfile={font}:"
             f"text='%{{expr_int_format\\:1\\:d\\:1}}':fontsize=1:fontcolor=black@0")

    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-framerate", "6", "-t", str(total_sec), "-i", str(soft),
        "-vf", f"{draw},format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
        "-crf", "30", "-g", "24", "-an", str(out_path),
    ])
    soft.unlink(missing_ok=True)


# ------------------------------------------------------------------ ana akis

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="out")
    ap.add_argument("--hours", type=float, default=1.0)
    ap.add_argument("--carrier", type=int, default=None)
    ap.add_argument("--purpose", default=None)
    ap.add_argument("--texture", default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--pomodoro", action="store_true", help="sayacli calisma videosu")
    a = ap.parse_args()

    seed = a.seed if a.seed is not None else random.randrange(1, 10**9)
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)

    # 1) ses
    print("== 1/5  ses uretiliyor")
    stereo, meta = ga.build(AUDIO_LOOP_SEC, a.carrier, a.purpose, a.texture, seed)
    wav = out / "loop.wav"
    ga.write_wav(stereo, wav)
    del stereo
    print(json.dumps(meta, indent=2))

    # 2) gorsel + kapak yazisi
    print("== 2/5  gorsel hazirlaniyor")
    raw = out / "art.png"
    img = out / "bg.png"
    art_meta = build_background(raw, seed, meta["purpose"])

    import cover
    total_sec_tmp = int(a.hours * 3600)
    hrs = total_sec_tmp / 3600
    dur_lbl = (f"{int(round(hrs))} Hour" if abs(hrs - 1) < 0.01 else
               (f"{int(round(hrs))} Hours" if hrs >= 1 else
                f"{int(round(total_sec_tmp/60))} Minutes"))
    cover_img = cover.add_text(
        Image.open(raw),
        meta["carrier_hz"],
        PURPOSE_LABEL[meta["purpose"]],
        TEXTURE_LABEL[meta["texture"]],
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

    # 3) gorsel katman
    if a.pomodoro:
        print("== 3/5  pomodoro sayaci render ediliyor")
        motion = out / "motion.mp4"
        render_pomodoro(img, motion, total_sec)
        video_reps = 0
    else:
        print("== 3/5  hareket dongusu render ediliyor")
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
    if a.pomodoro:
        dur = title.split("|")[-1].strip()
        title = f"Pomodoro Timer 25/5 | {TEXTURE_LABEL[meta['texture']]} | {dur}"
        desc = ("25 minute focus sessions with 5 minute breaks, on a continuous "
                f"loop with {TEXTURE_LABEL[meta['texture']].lower()} and a "
                f"{meta['carrier_hz']}Hz ambient bed.\n\n"
                "The on-screen timer counts down through each session, so you can "
                "start it and leave it running.\n\n"
                "All audio is original and synthesised for this channel.")
        tags = ["pomodoro", "pomodoro timer", "25 minute timer", "study timer",
                "focus timer", "study with me", "deep work", "concentration",
                TEXTURE_LABEL[meta['texture']].lower(), "ambient"]
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
