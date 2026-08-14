#!/usr/bin/env python3
"""
Gercek doga VIDEOSU arka plani (Pexels).

Doga ve doga+piyano videolarinda statik gorsel yerine gercek yagmur/
okyanus/orman goruntusu, yavas ve kusursuz dongulu.

Kusursuz dongu numarasi: klip + tersten klip (bumerang) = dikissiz.
Yagmur/su/atesin geri akisi gozle fark edilmez, sonsuz dongu hissi verir.

Pexels lisansi: ucretsiz, ticari kullanim serbest, atif gerekmez.
PEXELS_KEY yoksa sistem artgen gorseline duser - hic bozulmaz.
"""

import json
import os
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.pexels.com/videos/search"

QUERIES = {
    "rain_window":      ["rain window close up", "rain drops on glass",
                         "rain window night"],
    "rain_storm":       ["rain storm window night", "heavy rain dark",
                         "storm rain glass"],
    "fireplace":        ["fireplace close up", "campfire flames slow",
                         "fire burning cozy"],
    "fireplace_window": ["fireplace room cozy", "fire place window",
                         "cozy cabin fire"],
    "ocean":            ["ocean waves slow motion", "calm sea waves",
                         "waves shore sunset"],
    "stream":           ["forest stream water", "creek flowing rocks",
                         "river close up"],
    "forest_morning":   ["forest sunlight morning", "green forest calm",
                         "misty forest trees"],
    "forest_rain":      ["rain forest leaves", "rain trees green",
                         "rain in woods"],
    "snow":             ["snow falling slow", "snowfall trees winter",
                         "snow calm night"],
    "wind":             ["grass field wind", "trees wind sky",
                         "wheat field wind"],
}


def fetch_clip(category, seed, out_path):
    """Kategoriye uygun HD klip indir. Basarisizsa False."""
    key = os.environ.get("PEXELS_KEY")
    if not key:
        return False

    import random
    rng = random.Random(seed)
    queries = QUERIES.get(category, QUERIES["rain_window"])
    query = rng.choice(queries)

    try:
        url = f"{API}?{urllib.parse.urlencode({'query': query, 'per_page': 15, 'orientation': 'landscape'})}"
        req = urllib.request.Request(url, headers={"Authorization": key})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
    except Exception as e:
        print(f"Pexels arama hatasi: {e}")
        return False

    vids = data.get("videos", [])
    if not vids:
        return False
    rng.shuffle(vids)

    for v in vids[:6]:
        # 1080p'ye yakin, cok buyuk olmayan dosyayi sec
        files = sorted(v.get("video_files", []),
                       key=lambda f: abs((f.get("height") or 0) - 1080))
        for f in files[:2]:
            link = f.get("link")
            if not link:
                continue
            try:
                req = urllib.request.Request(link, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=180) as r:
                    Path(out_path).write_bytes(r.read())
                if Path(out_path).stat().st_size > 500_000:
                    print(f"Pexels klip indi: {query} / video {v['id']}")
                    return True
            except Exception:
                continue
    return False


def build_motion_from_clip(clip_path, out_path, width=1920, height=1080, fps=24):
    """
    Klipten kusursuz dongulu hareket segmenti:
      ileri + geri (bumerang) -> dikissiz sonsuz dongu.
    Yavaslatma (%80 hiz) ile daha huzurlu his.
    """
    # klibin ilk 14 sn'sini al, olcekle+kirp, yavaslat, bumerangla
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(clip_path), "-t", "14",
        "-filter_complex",
        (f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
         f"crop={width}:{height},setpts=1.25*PTS,fps={fps},split[a][b];"
         f"[b]reverse[r];[a][r]concat=n=2:v=1[out]"),
        "-map", "[out]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
        "-g", str(fps * 4), "-an", str(out_path),
    ], check=True)
    return True
