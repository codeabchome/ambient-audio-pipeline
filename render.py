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

from PIL import Image, ImageFilter
from pathlib import Path

import generate_audio as ga
import cover
import schedule as sch

# ------------------------------------------------------------------ ayarlar

WIDTH, HEIGHT = 1920, 1080
FPS = 24
MOTION_LOOP_SEC = 60          # render edilen tek segment
AUDIO_LOOP_SEC = 600          # uretilen ses dongusu (10 dk)
MUSIC_LOOP_SEC = 1800         # muzik dongusu (30 dk) - muzikte tekrar
                              # fark edilir, o yuzden cok daha uzun uretilir

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
    ap.add_argument("--nature", action="store_true", help="saf doga sesi videosu")
    ap.add_argument("--music", default=None,
                    choices=["deep_work", "sleep", "meditation"],
                    help="ambient muzik videosu (piyanosuz besteci)")
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
        # populer frekans rotasyonu (en cok arananlar)
        hz = sch.popular_next(advance=True)

    plan = sch.plan_for(hz)
    print(f"Frekans: {sch.format_hz(hz)} Hz  ({plan['mode']} modu)")

    import mixer, recipes as rcp
    _rng = __import__("numpy").random.default_rng(seed)

    meta = None
    _music_genre = None
    if a.music:
        import composer
        _music_genre = a.music
        print(f"Muzik turu: {_music_genre}")
        mwav = out / "music_src.wav"
        composer.render_music(_music_genre, MUSIC_LOOP_SEC / 60 + 0.3, seed, mwav)
        import mixer as _mx2
        stereo, _sr = _mx2.read_wav(mwav)
        stereo = _mx2.seamless(stereo.astype(__import__("numpy").float32), 8.0)
        meta = {"mix": "music", "genre": _music_genre,
                "carrier_hz": 0, "played_hz": 0, "beat_hz": 0,
                "purpose": _music_genre, "loop_seconds": MUSIC_LOOP_SEC,
                "seed": seed, "engine": "composer-v1"}
        mwav.unlink(missing_ok=True)

    kind = "nature" if a.nature else None
    if meta is None and kind:
        st = sch.load_state()
        recipe, st = rcp.pick(kind, "approved", st)
        if recipe:
            sch.save_state(st)
            print(f"Tarif: {recipe['id']}  ({', '.join(c for c,_ in recipe['layers'])}"
                  f"{' + piyano' if recipe['piano'] else ''})")
            stereo, meta = mixer.build_recipe(AUDIO_LOOP_SEC, recipe, seed)
            if meta:
                meta["recipe_obj"] = recipe["id"]
                _recipe = recipe
        if meta is None:
            print("UYARI: tarif icin kayit yok, frekansa dusuluyor")

    if meta is None:
        _recipe = None
        purpose = a.purpose or str(_rng.choice(["sleep","meditation","relax","focus","study"]))
        stereo, meta = mixer.build_mix(
            AUDIO_LOOP_SEC, carrier=plan["carrier"], beat=plan["beat"],
            label_hz=plan["label_hz"], purpose=purpose, category=None, seed=seed)
    meta["mode"] = plan["mode"]
    print(f"Miks: {meta.get('mix')}  kayit: {meta.get('recording','-')}")
    wav = out / "loop.wav"
    ga.write_wav(stereo, wav)
    del stereo
    print(json.dumps(meta, indent=2))

    # 2) gorsel + kapak yazisi
    print("== 2/5  gorsel hazirlaniyor")
    raw = out / "art.png"
    img = out / "bg.png"
    if meta.get("mix") == "recipe":
        art_meta = build_background(raw, int(hz * 1000) + seed % 1000, "sleep")
    else:
        # frekans videolari: 5 motor sirayla doner - ardisik videolar farkli
        st_v = sch.load_state()
        engines = ["attractor", "waves", "spiral", "flow", "rings",
                   "harmonograph", "grid"]
        vi = st_v.get("vis_i", 0) % len(engines)
        st_v["vis_i"] = vi + 1
        sch.save_state(st_v)
        import artgen as ag
        eng = engines[vi]
        img_e, art_meta = ag.generate_engine(eng, int(hz * 1000) + seed % 1000, 2560, 1440)
        img_e.save(raw)
        print(f"Gorsel motoru: {eng}")

    total_sec_tmp = int(a.hours * 3600)
    hrs = total_sec_tmp / 3600
    dur_lbl = (f"{int(round(hrs))} Hour" if abs(hrs - 1) < 0.01 else
               (f"{int(round(hrs))} Hours" if hrs >= 1 else
                f"{int(round(total_sec_tmp/60))} Minutes"))

    _photo_done = False
    if meta.get("mix") == "music":
        import cover_photo, composer
        _t, _d, _tg, _scene = composer.music_title(meta["genre"], dur_lbl)
        photo = out / "cover_photo.jpg"
        if cover_photo.fetch_photo(_scene, seed + 3, photo):
            try:
                pk = composer.MUSIC_PACK[meta["genre"]]
                cover_photo.make_cinematic_cover(
                    photo, pk["title"], pk["sub"], dur_lbl, img, seed=seed)
                cover_img = Image.open(img)
                _photo_done = True
                print("Sinematik muzik kapagi hazir")
            except Exception as e:
                print("Muzik kapak hatasi:", e)
            photo.unlink(missing_ok=True)
    if not _photo_done and meta.get("mix") == "recipe" and _recipe:
        import cover_photo
        photo = out / "cover_photo.jpg"
        if cover_photo.fetch_photo(_recipe["video"], seed + 3, photo):
            try:
                cover_photo.make_cinematic_cover(
                    photo, _recipe["title"], _recipe["sub"], dur_lbl, img,
                    seed=seed)
                cover_img = Image.open(img)
                _photo_done = True
                print("Sinematik foto kapak hazir")
            except Exception as e:
                print("Foto kapak hatasi, tipografiye dusuluyor:", e)
            photo.unlink(missing_ok=True)

    if not _photo_done:
        if meta.get("mix") in ("recipe", "music"):
            # Foto inmediyse: artgen gorseli uzerine sinematik tipografi.
            # ASLA frekans kapagina dusme (yoksa "0 Hz" yazardi).
            import cover_photo
            if meta.get("mix") == "music":
                import composer
                pk = composer.MUSIC_PACK[meta["genre"]]
                t_main, t_sub = pk["title"], pk["sub"]
            else:
                t_main, t_sub = _recipe["title"], _recipe["sub"]
            cover_photo.make_cinematic_cover(raw, t_main, t_sub, dur_lbl,
                                             img, seed=seed)
            cover_img = Image.open(img)
        else:
            fname, fbenefit = sch.name_for(meta["carrier_hz"])
            head_txt = f"{sch.format_hz(meta['carrier_hz'])} Hz"
            cover_img = cover.add_text(
                Image.open(raw), head_txt, fname, fbenefit, dur_lbl,
                purpose=meta.get("purpose", "sleep"), channel="TONEBED")
            cover_img.save(img)

    thumb = out / "thumb.jpg"
    t = cover_img.copy()
    t.thumbnail((1280, 720), Image.LANCZOS)
    # kucultme yazilari yumusatir - unsharp mask ile netligi geri getir
    t = t.filter(ImageFilter.UnsharpMask(radius=2, percent=115, threshold=2))
    for q in (90, 85, 78, 70, 60):
        t.save(thumb, "JPEG", quality=q, optimize=True)
        if thumb.stat().st_size < 1_900_000:
            break
    print(f"Kapak hazir (kucuk resim {thumb.stat().st_size//1024} KB)")

    # 3) hareket katmani
    print("== 3/5  hareket katmani")
    motion = out / "motion.mp4"
    total_sec = int(a.hours * 3600)
    _use_clip = False

    if meta.get("mix") in ("recipe", "music"):
        import video_bg
        clip = out / "clip.mp4"
        _vkey = meta.get("video_key") or {"deep_work": "wind", "sleep": "snow",
                                          "meditation": "ocean"}[meta["genre"]]
        if video_bg.fetch_clip(_vkey, seed, clip):
            try:
                video_bg.build_motion_from_clip(clip, motion, WIDTH, HEIGHT, FPS)
                seg = 28
                video_reps = max(1, -(-total_sec // seg)) - 1
                _use_clip = True
                print("Gercek video arka plan (Pexels)")
            except Exception as e:
                print("Klip islenemedi, gorsele dusuluyor:", e)
            clip.unlink(missing_ok=True)

    if not _use_clip:
        frames = MOTION_LOOP_SEC * FPS
        _eng = (art_meta or {}).get("engine", "attractor")
        # motor -> hareket karakteri (zoom miktari, renk salinimi)
        _mo = {
            "attractor": (0.04, 26),   # yavas nefes + renk kaymasi
            "waves":     (0.06, 14),   # dalgalanan yakinlasma
            "flow":      (0.05, 30),   # akiskan renk gecisi
            "rings":     (0.07, 10),   # nabiz gibi
            "grid":      (0.03, 20),   # sakin suzulme
            "spiral":       (0.05, 24),   # yavas donme hissi
            "harmonograph": (0.04, 22),   # suzulen cizgiler
        }.get(_eng, (0.04, 26))
        zexpr = f"1.0+{_mo[0]}*(0.5-0.5*cos(2*PI*on/{frames}))"
        huexpr = f"{_mo[1]}*sin(2*PI*t/{MOTION_LOOP_SEC})"
        run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-loop", "1", "-framerate", str(FPS), "-t", str(MOTION_LOOP_SEC),
            "-i", str(img),
            "-vf", (f"scale=2560:-2,"
                    f"zoompan=z='{zexpr}':d=1:"
                    f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                    f"s={WIDTH}x{HEIGHT}:fps={FPS},"
                    f"hue=h='{huexpr}':s=1.05,format=yuv420p"),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "29",
            "-g", str(FPS * 4), "-an", str(motion),
        ])
        video_reps = max(1, -(-total_sec // MOTION_LOOP_SEC)) - 1

    # 4) ses hedef sureye
    print("== 4/5  ses hedef sureye uzatiliyor")
    loop_len = meta.get("loop_seconds", AUDIO_LOOP_SEC)
    audio_reps = max(1, -(-total_sec // loop_len)) - 1
    m4a = out / "audio.m4a"
    mixer.encode_with_loudnorm(wav, m4a, total_sec, audio_reps)

    # 5) birlestir
    print("== 5/5  video birlestiriliyor")
    final = out / "video.mp4"
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-stream_loop", str(video_reps), "-i", str(motion),
        "-i", str(m4a),
        "-map", "0:v", "-map", "1:a", "-c", "copy",
        "-t", str(total_sec), "-movflags", "+faststart", str(final),
    ])

    hours2 = total_sec / 3600
    dur2 = (f"{int(round(hours2))} Hour" if abs(hours2-1) < 0.01 else
            (f"{int(round(hours2))} Hours" if hours2 >= 1 else
             f"{int(round(total_sec/60))} Minutes"))

    if meta.get("mix") == "music":
        import composer
        title, desc, tags, _scene = composer.music_title(meta["genre"], dur2)
        meta["scene"] = _scene
    elif meta.get("mix") == "recipe" and _recipe:
        title = rcp.build_title(_recipe, dur2)
        desc = rcp.build_description(_recipe, dur2)
        tags = rcp.build_tags(_recipe)
    else:
        title, desc, tags, _fpurpose = sch.freq_title(meta["carrier_hz"], dur2)
        meta["freq_purpose"] = _fpurpose
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
