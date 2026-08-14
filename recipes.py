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
        "id": "rain_piano",
        "layers": [("rain", 1.00)],
        "piano": True,
        "video": "rain_window",
        "title": "Rain & Soft Piano",
        "sub": "Relaxing Music for Sleep, Study & Calm",
        "tags": ["rain and piano", "piano rain sleep", "relaxing piano rain"],
    },
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
    {
        "id": "rain_thunder_piano",
        "layers": [("rain", 0.85), ("thunder", 0.45)],
        "piano": True,
        "video": "rain_storm",
        "title": "Rain, Thunder & Melancholy Piano",
        "sub": "Emotional Music for Sleep & Deep Rest",
        "tags": ["sad piano rain", "thunderstorm piano", "melancholy piano"],
    },

    # ---------------- SOMINE AILESI ----------------
    {
        "id": "fire_piano",
        "layers": [("fire", 1.00)],
        "piano": True,
        "video": "fireplace",
        "title": "Fireplace & Warm Piano",
        "sub": "Cozy Music for Winter Nights",
        "tags": ["fireplace piano", "cozy piano", "winter piano music"],
    },
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
    {
        "id": "fire_rain_piano",
        "layers": [("fire", 0.80), ("rain", 0.62)],
        "piano": True,
        "video": "fireplace_window",
        "title": "Fireplace, Rain & Gentle Piano",
        "sub": "Warm Music for Rest & Reading",
        "tags": ["cozy piano fireplace", "rain fire piano", "reading music"],
    },

    # ---------------- SU / OKYANUS ----------------
    {
        "id": "ocean_piano",
        "layers": [("ocean", 1.00)],
        "piano": True,
        "video": "ocean",
        "title": "Ocean Waves & Calm Piano",
        "sub": "Peaceful Music for Sleep & Meditation",
        "tags": ["ocean piano", "sea waves music", "beach relaxing music"],
    },
    {
        "id": "ocean_pure",
        "layers": [("ocean", 1.00)],
        "piano": False,
        "video": "ocean",
        "title": "Ocean Waves",
        "sub": "Calming Sea Sounds for Deep Sleep",
        "tags": ["ocean sounds", "waves for sleeping", "sea ambience"],
    },
    {
        "id": "stream_piano",
        "layers": [("stream", 1.00)],
        "piano": True,
        "video": "stream",
        "title": "Forest Stream & Soft Piano",
        "sub": "Gentle Music for Focus & Calm",
        "tags": ["water piano", "stream music", "nature piano"],
    },

    # ---------------- ORMAN / KUS ----------------
    {
        "id": "birds_piano",
        "layers": [("birds", 0.95)],
        "piano": True,
        "video": "forest_morning",
        "title": "Morning Birdsong & Piano",
        "sub": "Peaceful Music to Start the Day",
        "tags": ["birdsong piano", "morning music", "spring ambience"],
    },
    {
        "id": "birds_stream",
        "layers": [("birds", 0.85), ("stream", 0.75)],
        "piano": False,
        "video": "stream",
        "title": "Forest Stream & Birdsong",
        "sub": "Nature Sounds for Calm & Focus",
        "tags": ["forest sounds", "birds and water", "nature ambience"],
    },
    {
        "id": "forest_rain_piano",
        "layers": [("rain", 0.80), ("birds", 0.45)],
        "piano": True,
        "video": "forest_rain",
        "title": "Rain in the Forest & Piano",
        "sub": "Spring Rain Music for Rest",
        "tags": ["forest rain piano", "rain birds", "spring rain music"],
    },

    # ---------------- RUZGAR / KIS ----------------
    {
        "id": "snow_piano",
        "layers": [("snow", 0.95)],
        "piano": True,
        "video": "snow",
        "title": "Falling Snow & Quiet Piano",
        "sub": "Winter Music for Sleep & Reflection",
        "tags": ["snow piano", "winter ambience", "christmas calm music"],
    },
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
        if not folder.exists() or not any(folder.glob("*.wav")):
            return False
    return True


def pick(kind, approved_dir, state):
    """
    kind: "nature" (piyanosuz) veya "piano" (piyanolu)
    Kullanilabilir tarifler icinde SIRAYLA doner (tekrar etmesin).
    Doner: (recipe, yeni_state) - tarif yoksa (None, state)
    """
    want_piano = (kind == "piano")
    pool = [r for r in RECIPES
            if r["piano"] == want_piano and available(r, approved_dir)]
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
    music = ("with an original, gently played piano piece"
             if recipe["piano"] else "with no music and no talking")
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
