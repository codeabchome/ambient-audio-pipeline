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
