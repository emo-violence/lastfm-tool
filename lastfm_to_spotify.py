"""
Builds a Spotify playlist from every Last.fm track with > MIN_SCROBBLES plays.

pip install requests spotipy
Env vars: LASTFM_API_KEY, LASTFM_USER, SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET
Spotify app redirect URI must be exactly: http://127.0.0.1:8888/callback
"""
import json
import os
import time
import requests
from spotipy.oauth2 import SpotifyOAuth
from tqdm import tqdm

MIN_SCROBBLES = 15
PLAYLIST_NAME = f"last.fm: more than {MIN_SCROBBLES} scrobbles"

LASTFM_KEY = os.environ["LASTFM_API_KEY"]
LASTFM_USER = os.environ["LASTFM_USER"]


def lastfm_tracks():
    """yield (artist, title, playcount), most played first, stop at threshold"""
    page = 1
    while True:
        r = requests.get("https://ws.audioscrobbler.com/2.0/", params={
            "method": "user.gettoptracks", "user": LASTFM_USER,
            "api_key": LASTFM_KEY, "format": "json",
            "period": "overall", "limit": 200, "page": page,
        })
        r.raise_for_status()
        data = r.json()["toptracks"]
        for t in data["track"]:
            plays = int(t["playcount"])
            if plays <= MIN_SCROBBLES:
                return
            yield t["artist"]["name"], t["name"], plays
        if page >= int(data["@attr"]["totalPages"]):
            return
        page += 1


auth = SpotifyOAuth(
    redirect_uri="http://127.0.0.1:8888/callback",
    scope="playlist-modify-private playlist-modify-public",
    cache_path=".spotify_token",
)
HEADERS = {"Authorization": f"Bearer {auth.get_access_token(as_dict=False)}"}


def sp(method, path, **kw):
    """spotify request with 429 retry"""
    while True:
        r = requests.request(method, f"https://api.spotify.com/v1{path}",
                             headers=HEADERS, **kw)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 5)) + 1
            tqdm.write(f"rate limited by spotify, waiting {wait}s ({wait / 60:.1f} min)")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json() if r.content else {}


def find_uri(artist, title):
    # strict field search first, loose fallback second (limit max is 10 now)
    for q in (f'track:"{title}" artist:"{artist}"', f"{title} {artist}"):
        items = sp("GET", "/search", params={"q": q, "type": "track", "limit": 10}
                   )["tracks"]["items"]
        if items:
            return items[0]["uri"]
    return None


print("fetching last.fm tracks...")
tracks = list(lastfm_tracks())
print(f"{len(tracks)} tracks over {MIN_SCROBBLES} scrobbles, matching on spotify...")

CACHE_FILE = "matches.json"  # saved after every track, so restarts resume
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, encoding="utf-8") as f:
        cache = json.load(f)
    print(f"resuming, {len(cache)} tracks already matched")
else:
    cache = {}

uris, misses = [], []
for artist, title, plays in tqdm(tracks, unit="track"):
    key = f"{artist} - {title}"
    if key not in cache:
        cache[key] = find_uri(artist, title)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f)
        time.sleep(0.1)
    uri = cache[key]
    if uri and uri not in uris:
        uris.append(uri)
    elif not uri:
        misses.append(f"{key} ({plays})")

print(f"matched {len(uris)}, missed {len(misses)}")
with open("misses.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(misses))

playlist = sp("POST", "/me/playlists",
              json={"name": PLAYLIST_NAME, "public": False})
for i in range(0, len(uris), 100):
    sp("POST", f"/playlists/{playlist['id']}/items",
       json={"uris": uris[i:i + 100]})

print("done:", playlist["external_urls"]["spotify"])