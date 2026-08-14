#!/usr/bin/env python3
"""
Freesound CC0 kutuphane tarayicisi + otomatik kalite kapisi.

Ne yapar:
  1. Freesound'da SADECE CC0 lisansli kayitlari arar (atif bile gerekmez)
  2. Her adayi indirir ve OLCULEBILIR kalite testinden gecirir:
       - ornekleme hizi >= 44100
       - sure >= 60 sn
       - klip yok (tepe < 0.99)
       - gurultu tabani makul (sessiz bolum orani dusuk)
       - DC ofset yok
       - stereo veya temiz mono
  3. Gecenleri candidates/ klasorune koyar + rapor uretir
  4. SON SOZ INSANDA: kullanici dinler, begendiklerini approved/ altina tasir

Kullanim:
  FREESOUND_KEY=xxx python3 library_scan.py --category rain --count 6
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
import wave
from pathlib import Path

import numpy as np

API = "https://freesound.org/apiv2"

# Kategori -> arama sorgulari (birden fazla sorgu = cesitlilik)
# SADECE rahatlatici kategoriler. Hayvan sesi olarak yalniz KUS kabul.
CATEGORIES = {
    "rain":    ["rain steady loop", "rain ambience field recording", "gentle rain window"],
    "ocean":   ["ocean waves loop", "sea waves ambience", "calm waves beach"],
    "stream":  ["stream water loop", "creek flowing gentle", "river calm"],
    "birds":   ["birdsong morning ambience", "birds forest ambience", "gentle birdsong"],
    "forest":  ["forest ambience calm", "woodland morning birds", "quiet forest wind"],
    "wind":    ["wind ambience soft", "gentle wind trees", "wind loop calm"],
    "fire":    ["fireplace crackling loop", "campfire ambience calm", "fire crackle cozy"],
    "thunder": ["distant thunder rain", "soft thunder ambience", "gentle storm rain"],
    "snow":    ["winter wind ambience", "snowstorm gentle ambience", "cold wind soft"],
}

# Rahatlatici OLMAYAN icerik: isim/etikette gecerse aday elenir
EXCLUDE_TERMS = [
    "frog", "cricket", "insect", "cicada", "owl", "wolf", "dog", "cat",
    "cow", "sheep", "goat", "rooster", "chicken", "duck", "goose",
    "monkey", "seagull", "crow", "raven", "traffic", "car", "train",
    "people", "voice", "talk", "crowd", "city", "siren", "horn",
    "scream", "horror", "scary",
]


def name_ok(name):
    n = name.lower()
    return not any(term in n for term in EXCLUDE_TERMS)

MIN_SR = 44100
MIN_DUR = 60.0
MAX_DUR = 900.0


def api_get(path, key, **params):
    params["token"] = key
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "tonebed-pipeline"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def search_cc0(key, query, page_size=25):
    """Sadece CC0, yeterince uzun, yuksek puanli kayitlar."""
    return api_get(
        "/search/text/", key,
        query=query,
        filter=f'license:"Creative Commons 0" duration:[{MIN_DUR} TO {MAX_DUR}] samplerate:[{MIN_SR} TO *]',
        sort="rating_desc",
        fields="id,name,duration,samplerate,channels,avg_rating,num_ratings,previews,license,username",
        page_size=page_size,
    )


def download_preview(sound, out_path):
    """
    Yuksek kalite onizleme (OGG/MP3 ~192kbps) indirir.
    Tam WAV icin OAuth gerekir; onizleme kalite testi ve
    ambiyans katmani icin yeterlidir (arka planda kisik calar).
    """
    url = sound["previews"].get("preview-hq-ogg") or sound["previews"].get("preview-hq-mp3")
    if not url:
        return False
    req = urllib.request.Request(url, headers={"User-Agent": "tonebed-pipeline"})
    with urllib.request.urlopen(req, timeout=120) as r:
        Path(out_path).write_bytes(r.read())
    return True


def to_wav(src, dst):
    import subprocess
    r = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
         "-ar", "44100", "-ac", "2", str(dst)],
        capture_output=True)
    return r.returncode == 0


def quality_check(wav_path):
    """Olculebilir kalite kapisi. (gecti_mi, rapor) doner."""
    w = wave.open(str(wav_path), "rb")
    sr = w.getframerate()
    n = w.getnframes()
    d = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
    if w.getnchannels() == 2:
        d = d.reshape(-1, 2).mean(1)
    w.close()

    dur = n / sr
    peak = float(np.max(np.abs(d)))
    rms = float(np.sqrt((d ** 2).mean()))
    dc = float(abs(d.mean()))

    # klip orani: tepeye yapisan ornek orani
    clip_ratio = float((np.abs(d) > 0.985).mean())

    # sessizlik orani: kayitta olu bosluk var mi
    frame = sr // 10
    frames = d[: (len(d) // frame) * frame].reshape(-1, frame)
    frame_rms = np.sqrt((frames ** 2).mean(1))
    silence_ratio = float((frame_rms < 0.004).mean())

    # seviye tutarliligi: ani patlamalar (yuksek varyans kotu ambiyans)
    level_cv = float(frame_rms.std() / (frame_rms.mean() + 1e-9))

    rep = {
        "duration": round(dur, 1), "peak": round(peak, 3),
        "rms": round(rms, 4), "dc_offset": round(dc, 5),
        "clip_ratio": round(clip_ratio, 5),
        "silence_ratio": round(silence_ratio, 3),
        "level_cv": round(level_cv, 2),
    }

    ok = (
        dur >= MIN_DUR
        and peak <= 0.995
        and clip_ratio < 0.001
        and dc < 0.02
        and rms > 0.01
        and silence_ratio < 0.25
        and level_cv < 1.8
    )
    return ok, rep


def scan(key, category, count, outdir):
    out = Path(outdir) / category
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path("/tmp/fs_tmp")
    tmp.mkdir(exist_ok=True)

    queries = CATEGORIES[category]
    accepted, report = [], []

    for q in queries:
        if len(accepted) >= count:
            break
        try:
            res = search_cc0(key, q)
        except Exception as e:
            print(f"  arama hatasi ({q}): {e}")
            continue

        for snd in res.get("results", []):
            if len(accepted) >= count:
                break
            sid = snd["id"]
            if any(a["id"] == sid for a in accepted):
                continue
            if not name_ok(snd["name"]):
                print(f"  [icerik] {sid} | {snd['name'][:48]} | rahatlatici degil, atlandi")
                continue

            raw = tmp / f"{sid}.ogg"
            wav = tmp / f"{sid}.wav"
            try:
                if not download_preview(snd, raw):
                    continue
                if not to_wav(raw, wav):
                    continue
                ok, rep = quality_check(wav)
            except Exception as e:
                print(f"  {sid} islenemedi: {e}")
                continue

            rep.update({"id": sid, "name": snd["name"][:60],
                        "by": snd["username"], "rating": snd.get("avg_rating"),
                        "query": q, "license": "CC0"})
            report.append({**rep, "passed": ok})

            mark = "GECTI" if ok else "elendi"
            print(f"  [{mark}] {sid} | {snd['name'][:48]} | {rep['duration']}s "
                  f"| klip {rep['clip_ratio']} | sessiz {rep['silence_ratio']}")

            if ok:
                dest = out / f"{category}_{sid}.wav"
                wav.rename(dest)
                rep["file"] = str(dest)
                accepted.append(rep)
            raw.unlink(missing_ok=True)
            wav.unlink(missing_ok=True)

    (out / "_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n{category}: {len(accepted)} aday hazir -> {out}/")
    print("Simdi bunlari DINLE ve begendiklerini approved/ klasorune tasi.")
    return accepted


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--category", required=True, choices=list(CATEGORIES))
    p.add_argument("--count", type=int, default=6)
    p.add_argument("--outdir", default="candidates")
    a = p.parse_args()

    key = os.environ.get("FREESOUND_KEY")
    if not key:
        sys.exit("FREESOUND_KEY ortam degiskeni gerekli")

    scan(key, a.category, a.count, a.outdir)
