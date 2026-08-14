#!/usr/bin/env python3
"""
Frekans plani: 1 Hz'den 2000 Hz'e kadar sirayla ilerler.

Durum state.json icinde tutulur ve her calismadan sonra depoya geri yazilir,
boylece sistem kaldigi yerden devam eder.

ONEMLI TEKNIK NOT:
  20 Hz'in altindaki sesler insan kulagi tarafindan TON olarak duyulmaz.
  Bu yuzden 1-20 Hz araligi "binaural vurus" olarak uretilir:
  hos bir tasiyici (or. 200 Hz) uzerine o kadar fark konur, beyin farki algilar.
  Sektordeki kanallar da bunu boyle yapar (or. 7.83 Hz Schumann).
"""

import json
from pathlib import Path

STATE = Path("state.json")
MIN_HZ, MAX_HZ = 1, 2000

# 20 Hz alti -> binaural vurus modu, bu tasiyici uzerinde calar
BEAT_CARRIER = 200.0


# ---------------------------------------------------------------- isimler

# Bilinen frekanslarin yerlesik adlari (sektorde bu isimlerle aranir)
KNOWN = {
    174: ("Foundation", "Pain Relief & Deep Security"),
    285: ("Tissue Renewal", "Cellular Repair & Regeneration"),
    396: ("Release the Fear", "Letting Go of Guilt & Fear"),
    417: ("Undoing Situations", "Clearing Negative Energy"),
    432: ("Natural Tuning", "Deep Harmony with Nature"),
    528: ("The Miracle Tone", "DNA Repair & Transformation"),
    639: ("Harmonious Connection", "Relationships & Compassion"),
    741: ("Sonic Clarity", "Detox & Self Expression"),
    852: ("Return to Spirit", "Intuition & Inner Order"),
    963: ("Gateway to the Divine", "Pineal Activation & Oneness"),
    111: ("Cell Regeneration", "Angelic Renewal"),
    136.1: ("Cosmic OM", "The Earth Year Tone"),
    440: ("Standard Pitch", "Concert Tuning Reference"),
    1111: ("Angelic Portal", "Spiritual Awakening"),
    1500: ("Cosmic Stream", "Higher Field Attunement"),
}

# 20 Hz alti - beyin dalgasi bantlari
BRAINWAVE = [
    (0, 4,   "Delta Waves",  "Deep Dreamless Sleep"),
    (4, 8,   "Theta Waves",  "Deep Meditation & Dream State"),
    (8, 13,  "Alpha Waves",  "Calm Focus & Light Relaxation"),
    (13, 21, "Beta Waves",   "Alert Concentration"),
]

SPECIAL_LOW = {
    7.83: ("Schumann Resonance", "The Earth's Heartbeat"),
    10:   ("Alpha Gateway", "Calm Alert Awareness"),
    3:    ("Delta Descent", "Deep Restorative Sleep"),
    6:    ("Theta Drift", "Dreamlike Inner Stillness"),
}

# Prosedurel isim havuzu (bilinmeyen frekanslar icin)
ADJ = ["Silent", "Deep", "Golden", "Quiet", "Inner", "Still", "Hidden",
       "Distant", "Soft", "Sacred", "Endless", "Gentle", "Crystal",
       "Ancient", "Weightless", "Boundless", "Luminous", "Tranquil"]
NOUN = ["Current", "Horizon", "Field", "Drift", "Bloom", "Tide", "Chamber",
        "Threshold", "Passage", "Expanse", "Stillness", "Ascent", "Depth",
        "Resonance", "Sanctuary", "Harbour", "Clearing", "Veil"]
BENEFIT = [
    "Deep Sleep & Nervous System Reset",
    "Stress Relief & Emotional Release",
    "Meditation & Inner Stillness",
    "Anxiety Relief & Calm Focus",
    "Healing Sleep & Body Restoration",
    "Letting Go & Deep Relaxation",
    "Mind Clearing & Quiet Focus",
    "Restful Sleep & Inner Balance",
]


def name_for(hz):
    """Frekansa uygun isim + fayda tanimlayicisi."""
    key = int(hz) if float(hz).is_integer() else hz

    if key in KNOWN:
        return KNOWN[key]
    if key in SPECIAL_LOW:
        return SPECIAL_LOW[key]

    if hz < 21:
        for lo, hi, nm, ben in BRAINWAVE:
            if lo <= hz < hi:
                return (nm, ben)

    # prosedurel ama deterministik: ayni frekans hep ayni ismi alir
    a = ADJ[int(hz * 7) % len(ADJ)]
    n = NOUN[int(hz * 13) % len(NOUN)]
    b = BENEFIT[int(hz * 3) % len(BENEFIT)]
    return (f"{a} {n}", b)


# ---------------------------------------------------------------- durum

def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            pass
    return {"next_hz": MIN_HZ, "done": []}


def save_state(st):
    STATE.write_text(json.dumps(st, indent=2))


def next_frequency(advance=True):
    """
    Siradaki frekansi ver ve sayaci ilerlet.
    2000'e ulasinca basa doner (o noktada ~400 gunluk arsiv olur).
    """
    st = load_state()
    hz = st.get("next_hz", MIN_HZ)
    if hz > MAX_HZ:
        hz = MIN_HZ
    if advance:
        st["next_hz"] = hz + 1 if hz < MAX_HZ else MIN_HZ
        save_state(st)
    return hz


def plan_for(hz):
    """
    Frekansi calinabilir hale getir.
    < 21 Hz  -> binaural vurus (tasiyici 200 Hz uzerinde)
    >= 21 Hz -> tasiyici tonun kendisi
    """
    hz = float(hz)
    if hz < 21:
        return {
            "mode": "beat",
            "label_hz": hz,
            "carrier": BEAT_CARRIER,
            "beat": hz,
        }
    # duyulabilir ama yormayan bolge icin vurus sec
    beat = 4.0 + (hz % 7)          # 4-11 Hz arasi, theta/alfa
    return {
        "mode": "tone",
        "label_hz": hz,
        "carrier": hz,
        "beat": round(beat, 2),
    }


def format_hz(hz):
    return f"{int(hz)}" if float(hz).is_integer() else f"{hz:g}"


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    st = load_state()
    start = st.get("next_hz", 1)
    for i in range(n):
        hz = start + i
        if hz > MAX_HZ:
            break
        nm, ben = name_for(hz)
        p = plan_for(hz)
        print(f"{format_hz(hz):>5} Hz | {p['mode']:5} | {nm} — {ben}")


# ---------------------------------------------------------------- doga adlari

NATURE_NAMES = {
    "rain":    ("Gentle Rain", "Rain Sounds for Sleep & Study"),
    "ocean":   ("Ocean Waves", "Calming Sea Sounds"),
    "stream":  ("Forest Stream", "Flowing Water Sounds"),
    "forest":  ("Forest Ambience", "Birdsong & Woodland Calm"),
    "wind":    ("Soft Wind", "Gentle Wind Ambience"),
    "fire":    ("Crackling Fireplace", "Cozy Fire Sounds"),
    "night":   ("Summer Night", "Crickets & Night Ambience"),
    "thunder": ("Rain & Distant Thunder", "Stormy Night Ambience"),
}


def nature_name(category, recording=""):
    """Kategori + kayit adina gore baslik ciftini sec."""
    base = NATURE_NAMES.get(category, (category.title(), "Nature Ambience"))
    r = recording.lower()
    if category == "rain":
        if "thunder" in r or "storm" in r:
            return NATURE_NAMES["thunder"]
        if "tent" in r:
            return ("Rain on a Tent", "Cozy Rain Sounds")
        if "forest" in r or "bird" in r:
            return ("Rain in the Forest", "Rain & Birdsong")
        if "frog" in r or "night" in r:
            return ("Rainy Night", "Night Rain Ambience")
    return base


# ------------------------------------------------------- populer frekanslar

# Internette en cok aranan/dinlenen frekanslar (arama hacmine gore sirali)
POPULAR = [
    528,    # Miracle Tone - acik ara en populer
    432,    # Natural Tuning
    963,    # Gateway to the Divine
    396,    # Release the Fear
    639,    # Harmonious Connection
    7.83,   # Schumann Resonance
    174,    # Foundation / Pain Relief
    852,    # Return to Spirit
    741,    # Sonic Clarity
    417,    # Undoing Situations
    285,    # Tissue Renewal
    111,    # Cell Regeneration
    1111,   # Angelic Portal
    136.1,  # Cosmic OM
    10,     # Alpha Gateway
    4,      # Theta / deep meditation
    2,      # Delta / deep sleep
]


def popular_next(advance=True):
    """Populer listeden sirayla frekans ver (ayri sayac)."""
    st = load_state()
    i = st.get("pop_i", 0) % len(POPULAR)
    if advance:
        st["pop_i"] = (i + 1) % len(POPULAR)
        save_state(st)
    return POPULAR[i]


# ---------------------------------------------------- amac odakli basliklar

# Her frekansin dogal amaci (arama kaliplari boyle)
FREQ_PURPOSE = {
    528: "healing", 432: "relax", 963: "meditation", 396: "release",
    639: "relax", 7.83: "grounding", 174: "healing", 852: "meditation",
    741: "focus", 417: "release", 285: "healing", 111: "meditation",
    1111: "meditation", 136.1: "meditation", 10: "focus", 4: "sleep", 2: "sleep",
}

# amac -> (baslik kalibi, aciklama vurgusu, ek etiketler)
PURPOSE_PACK = {
    "sleep": ("Deep Sleep Music", "fall asleep fast and stay asleep",
              ["sleep music", "deep sleep", "fall asleep fast", "insomnia relief"]),
    "focus": ("Focus & Study Music", "deep concentration and productive work",
              ["study music", "focus music", "concentration", "deep work"]),
    "meditation": ("Meditation Music", "deep meditation and inner stillness",
                   ["meditation music", "spiritual", "inner peace", "zen"]),
    "healing": ("Healing Sleep Music", "deep healing and full body restoration",
                ["healing frequency", "healing music", "body restoration"]),
    "relax": ("Relaxing Music", "release stress and deeply unwind",
              ["relaxing music", "stress relief", "calm music", "unwind"]),
    "release": ("Letting Go Music", "release fear, guilt and negative energy",
                ["let go", "release negativity", "emotional healing"]),
    "grounding": ("Grounding Meditation", "reconnect with the earth and feel present",
                  ["schumann resonance", "grounding", "earthing", "nature frequency"]),
}


def freq_title(hz, duration_label):
    """Amac odakli frekans basligi + aciklama + etiketler."""
    key = int(hz) if float(hz).is_integer() else hz
    purpose = FREQ_PURPOSE.get(key, "relax")
    pack_name, benefit, extra = PURPOSE_PACK[purpose]
    name, meaning = name_for(hz)
    hz_txt = format_hz(hz)

    title = f"{hz_txt} Hz {pack_name} | {name} | {duration_label}"

    if hz < 21:
        how = (f"A {hz_txt} Hz binaural beat on a soft carrier tone - "
               f"headphones are essential for the effect.")
    else:
        how = (f"A pure {hz_txt} Hz tone on a soft ambient bed, "
               f"with a gentle binaural beat beneath. Headphones recommended.")

    desc = (f"{hz_txt} Hz - {name}. {meaning}.\n\n"
            f"Made to help you {benefit}.\n\n{how}\n\n"
            f"{duration_label} of continuous, seamlessly looping sound. "
            f"Play it while you sleep, meditate, study or rest.\n\n"
            f"All audio is original and synthesised for this channel.\n\n"
            f"Sound is not a treatment. If something hurts or worries you, "
            f"please speak to a doctor.")

    tags = ([f"{hz_txt}hz", f"{hz_txt} hz", name.lower(),
             "binaural beats", "solfeggio"] + extra +
            ["ambient", "1 hour", "sound healing"])[:15]
    return title, desc, tags, purpose
