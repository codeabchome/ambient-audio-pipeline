#!/usr/bin/env python3
"""
TARIF (recipe) sistemi.

Her video bir "tarif"tir: hangi ses katmanlari, hangi video arka plani,
hangi baslik/etiket. YouTube'da tutan kombinasyonlar elle secildi -
rastgele karisim degil, kuratorlu liste.

Kalite kurallari:
  - Ses katmanlari birbirini bogmaz (seviyeler tarifte sabit)
  - Video arka plani sesle ORTUSUR (somine sesi -> somine goruntusu)
  - Baslik turun konvansiyonuna uyar
  - Ayni kategoriden pesbese ayni tarif gelmez (rotasyon)
"""

# ---------------------------------------------------------------- tarifler
#
# layers: (kategori, seviye) listesi - approved/<kategori>/ altindan kayit
# piano: piyano eklensin mi
# video: video_bg sorgu anahtari
# title / sub: baslik parcalari
# tags: ek etiketler

RECIPES = [
    # ---------------- YAGMUR AILESI ----------------
    {
        "id": "rain_pure",
        "layers": [("rain", 1.00)],
        "piano": False,
        "video": "rain_window",
        "title": "Gentle Rain Sounds",
        "sub": "Sleep, Study & Relaxation",
        "tags": ["rain sounds", "rain for sleeping", "rain white noise"],
    },
    {
        "id": "rain_thunder",
        "layers": [("rain", 0.90), ("thunder", 0.55)],
        "piano": False,
        "video": "rain_storm",
        "title": "Heavy Rain & Distant Thunder",
        "sub": "Deep Sleep & Stormy Night Ambience",
        "tags": ["thunderstorm sounds", "rain and thunder", "storm for sleeping"],
    },

    # ---------------- SOMINE AILESI ----------------
    {
        "id": "fire_pure",
        "layers": [("fire", 1.00)],
        "piano": False,
        "video": "fireplace",
        "title": "Crackling Fireplace",
        "sub": "Cozy Fire Sounds for Sleep & Focus",
        "tags": ["fireplace sounds", "crackling fire", "fireplace ambience"],
    },
    {
        "id": "fire_rain",          # klasik kombinasyon
        "layers": [("fire", 0.85), ("rain", 0.70)],
        "piano": False,
        "video": "fireplace_window",
        "title": "Fireplace & Rain on the Window",
        "sub": "Cozy Ambience for Deep Sleep",
        "tags": ["fireplace and rain", "cozy cabin sounds", "rain fireplace"],
    },

    # ---------------- SU / OKYANUS ----------------
    {
        "id": "ocean_pure",
        "layers": [("ocean", 1.00)],
        "piano": False,
        "video": "ocean",
        "title": "Ocean Waves",
        "sub": "Calming Sea Sounds for Deep Sleep",
        "tags": ["ocean sounds", "waves for sleeping", "sea ambience"],
    },

    # ---------------- ORMAN / KUS ----------------
    {
        "id": "birds_stream",
        "layers": [("birds", 0.85), ("stream", 0.75)],
        "piano": False,
        "video": "stream",
        "title": "Forest Stream & Birdsong",
        "sub": "Nature Sounds for Calm & Focus",
        "tags": ["forest sounds", "birds and water", "nature ambience"],
    },

    # ---------------- RUZGAR / KIS ----------------
    {
        "id": "wind_pure",
        "layers": [("wind", 1.00)],
        "piano": False,
        "video": "wind",
        "title": "Soft Wind Ambience",
        "sub": "Gentle Wind Sounds for Sleep",
        "tags": ["wind sounds", "wind for sleeping", "white noise wind"],
    },
]


ORTAK_TAGS = [
    "relaxing music", "sleep music", "study music", "ambience",
    "1 hour", "no ads", "calm", "asmr",
]


def available(recipe, approved_dir):
    """Tarifin TUM katmanlarinin kaydi var mi?"""
    from pathlib import Path
    ad = Path(approved_dir)
    for cat, _ in recipe["layers"]:
        folder = ad / cat
        if not folder.exists():
            return False
        if not (any(folder.glob("*.wav")) or any(folder.glob("*.flac"))):
            return False
    return True


def pick(kind, approved_dir, state):
    """
    kind: "nature" - saf doga tarifleri (muzik iceren tarif kalmadi)
    Kullanilabilir tarifler icinde SIRAYLA doner (tekrar etmesin).
    Doner: (recipe, yeni_state) - tarif yoksa (None, state)
    """
    pool = [r for r in RECIPES if available(r, approved_dir)]
    if not pool:
        return None, state

    key = f"recipe_i_{kind}"
    i = state.get(key, 0) % len(pool)
    state[key] = (i + 1) % len(pool)
    return pool[i], state


def build_title(recipe, duration_label):
    return f"{recipe['title']} | {recipe['sub']} | {duration_label}"


def build_description(recipe, duration_label):
    layers = ", ".join(c for c, _ in recipe["layers"])
    music = "with no music and no talking"
    return (
        f"{recipe['title']} — {recipe['sub'].lower()}.\n\n"
        f"{duration_label} of continuous, seamlessly looping ambience "
        f"({layers}) {music}.\n\n"
        f"Play it while you sleep, study, read, work or rest.\n\n"
        f"Field recordings are public domain (CC0). "
        f"Piano is composed and rendered for this channel — every piece is "
        f"different.\n\n"
        f"Headphones or speakers both work; keep the volume comfortable."
    )


def build_tags(recipe):
    return (recipe["tags"] + [c for c, _ in recipe["layers"]] + ORTAK_TAGS)[:15]
