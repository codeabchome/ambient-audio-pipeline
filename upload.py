#!/usr/bin/env python3
"""
YouTube'a video yukler.
Kimlik bilgileri GitHub Secrets'tan ortam degiskeni olarak gelir -
kodun icinde ASLA anahtar bulunmaz.

Gerekli secrets:
  YT_CLIENT_ID
  YT_CLIENT_SECRET
  YT_REFRESH_TOKEN
"""

import json
import os
import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

TOKEN_URI = "https://oauth2.googleapis.com/token"


def get_service():
    cid = os.environ.get("YT_CLIENT_ID")
    csec = os.environ.get("YT_CLIENT_SECRET")
    rtok = os.environ.get("YT_REFRESH_TOKEN")
    missing = [k for k, v in
               {"YT_CLIENT_ID": cid, "YT_CLIENT_SECRET": csec,
                "YT_REFRESH_TOKEN": rtok}.items() if not v]
    if missing:
        print("Eksik secret:", ", ".join(missing), file=sys.stderr)
        raise SystemExit(1)

    creds = Credentials(
        token=None,
        refresh_token=rtok,
        client_id=cid,
        client_secret=csec,
        token_uri=TOKEN_URI,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload(meta_path="out/meta.json", privacy="private"):
    meta = json.loads(Path(meta_path).read_text())
    video = meta["video"]

    body = {
        "snippet": {
            "title": meta["title"][:100],
            "description": meta["description"][:4900],
            "tags": meta["tags"],
            "categoryId": "10",          # Music
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy,     # private | unlisted | public
            "selfDeclaredMadeForKids": False,
        },
    }

    yt = get_service()
    media = MediaFileUpload(video, chunksize=8 * 1024 * 1024, resumable=True,
                            mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    print(f"Yukleniyor: {meta['title']}")
    resp = None
    while resp is None:
        try:
            status, resp = req.next_chunk()
            if status:
                print(f"  %{int(status.progress() * 100)}")
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504):
                print("  gecici hata, tekrar deneniyor...")
                continue
            raise

    vid = resp["id"]
    print(f"TAMAM  https://youtu.be/{vid}")

    # kapak gorseli (varsa)
    thumb = meta.get("thumbnail")
    if thumb and Path(thumb).exists():
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumb)).execute()
            print("Kapak gorseli yuklendi")
        except HttpError as e:
            print("Kapak yuklenemedi (dogrulanmamis kanal olabilir):", e)

    return vid


if __name__ == "__main__":
    privacy = os.environ.get("PRIVACY", "private")
    upload(sys.argv[1] if len(sys.argv) > 1 else "out/meta.json", privacy)
