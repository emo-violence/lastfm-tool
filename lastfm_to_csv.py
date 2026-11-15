"""
Export your Last.fm tracks to a CSV: scrobbles, artist, album, track, genre, bpm, length

pip install requests tqdm
Env vars: LASTFM_API_KEY, LASTFM_USER
Optional: GETSONGBPM_API_KEY (free key at getsongbpm.com/api, they require a
backlink to their site). Without it the bpm column is left blank.

Resumable: lookups are cached in lastfm_meta.json and bpm.json, so ctrl+c
and rerunning picks up where it left off.
"""
import csv
import json
import os
import time

import requests
from tqdm import tqdm

MIN_SCROBBLES = 0  # keep tracks with strictly MORE than this (0 = everything)
OUT_FILE = "scrobbles.csv"
META_FILE = "lastfm_meta.json"
BPM_FILE = "bpm.json"

LASTFM_KEY = os.environ["LASTFM_API_KEY"]
LASTFM_USER = os.environ["LASTFM_USER"]
BPM_KEY = os.environ.get("GETSONGBPM_API_KEY")

LASTFM_URL = "https://ws.audioscrobbler.com/2.0/"
BPM_URL = "https://api.getsong.co"
JUNK_TAGS = {"seen live", "favorites", "favourites", "favorite", "awesome",
             "love", "loved", "my music", "albums i own"}


def lastfm(method, **params):
    """Last.fm GET with retry on rate limits / server errors. None on API error."""
    for attempt in range(6):
        r = requests.get(LASTFM_URL, timeout=30, params={
            "method": method, "api_key": LASTFM_KEY, "format": "json", **params})
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(5 * (attempt + 1))
            continue
        data = r.json()
        if data.get("error") == 29:  # rate limit exceeded
            time.sleep(5 * (attempt + 1))
            continue
        return None if "error" in data else data
    return None


def top_tracks():
    """yield (artist, title, plays), most played first"""
    page = 1
    while True:
        data = lastfm("user.gettoptracks", user=LASTFM_USER,
                      period="overall", limit=200, page=page)["toptracks"]
        for t in data["track"]:
            plays = int(t["playcount"])
            if plays <= MIN_SCROBBLES:
                return
            yield t["artist"]["name"], t["name"], plays
        if page >= int(data["@attr"]["totalPages"]):
            return
        page += 1


def tag_names(tags):
    if isinstance(tags, dict):  # a single tag comes back as a dict
        tags = [tags]
    return [t["name"] for t in tags or []
            if t["name"].lower() not in JUNK_TAGS]


def track_meta(artist, title, meta):
    d = lastfm("track.getinfo", artist=artist, track=title, autocorrect=1)
    t = (d or {}).get("track", {})
    album = (t.get("album") or {}).get("title", "")
    length = int(t.get("duration") or 0) // 1000
    tags = tag_names((t.get("toptags") or {}).get("tag"))
    if not tags:  # fall back to the artist's tags (cached per artist)
        akey = f"artist::{artist}"
        if akey not in meta:
            a = lastfm("artist.gettoptags", artist=artist, autocorrect=1)
            meta[akey] = tag_names(((a or {}).get("toptags") or {}).get("tag"))
            time.sleep(0.25)
        tags = meta[akey]
    return {"album": album, "length": length, "genre": "; ".join(tags[:2])}


def get_bpm(artist, title):
    """first getsongbpm match's tempo, or None"""
    r = requests.get(f"{BPM_URL}/search/", timeout=30, params={
        "api_key": BPM_KEY, "type": "both",
        "lookup": f"song:{title} artist:{artist}"})
    if r.status_code != 200:
        return None
    results = r.json().get("search")
    if not isinstance(results, list) or not results:
        return None
    song = results[0]
    tempo = song.get("tempo")
    if not tempo:  # search result lacked tempo, fetch the song itself
        d = requests.get(f"{BPM_URL}/song/", timeout=30,
                         params={"api_key": BPM_KEY, "id": song["id"]}).json()
        tempo = d.get("song", {}).get("tempo")
    return int(tempo) if tempo else None


def load(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f)


def fmt_length(seconds):
    return f"{seconds // 60}:{seconds % 60:02d}" if seconds else ""


def main():
    print("fetching last.fm tracks...")
    tracks = list(top_tracks())
    print(f"{len(tracks)} tracks, looking up details...")
    if not BPM_KEY:
        print("no GETSONGBPM_API_KEY set, bpm column will be blank")

    meta, bpms = load(META_FILE), load(BPM_FILE)
    try:
        for i, (artist, title, plays) in enumerate(tqdm(tracks, unit="track"), 1):
            key = f"{artist} - {title}"
            if key not in meta:
                meta[key] = track_meta(artist, title, meta)
                time.sleep(0.25)
            if BPM_KEY and key not in bpms:
                bpms[key] = get_bpm(artist, title)
                time.sleep(0.3)
            if i % 25 == 0:
                save(META_FILE, meta)
                save(BPM_FILE, bpms)
    finally:  # also runs on ctrl+c, so progress is kept
        save(META_FILE, meta)
        save(BPM_FILE, bpms)

    # utf-8-sig so excel on windows reads accents correctly
    with open(OUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["scrobbles", "artist", "album", "track", "genre", "bpm", "length"])
        for artist, title, plays in tracks:
            key = f"{artist} - {title}"
            m = meta[key]
            w.writerow([plays, artist, m["album"], title, m["genre"],
                        bpms.get(key) or "", fmt_length(m["length"])])
    print(f"done: {len(tracks)} rows in {OUT_FILE}")


if __name__ == "__main__":
    main()
