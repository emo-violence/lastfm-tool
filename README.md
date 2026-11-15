# lastfm-tools

Two small personal Python scripts for turning a Last.fm listening history into something useful.

- `lastfm_to_spotify.py` builds a private Spotify playlist of every track with more than 15 scrobbles.
- `lastfm_to_csv.py` exports tracks to a CSV with scrobbles, artist, album, track, genre, BPM and length.

BPM data from [GetSongBPM](https://getsongbpm.com).

## Setup

You need Python 3 and:

```
pip install requests spotipy tqdm
```

API keys:

- **Last.fm:** a key from https://www.last.fm/api (used by both scripts)
- **Spotify:** an app from the Spotify developer dashboard using the Web API, with the redirect URI set to exactly `http://127.0.0.1:8888/callback` (playlist script only)
- **GetSongBPM:** an optional free key from https://getsongbpm.com/api (CSV script only)

Set them as environment variables. In PowerShell, in the same window you will run the scripts from:

```powershell
$env:LASTFM_API_KEY = "..."
$env:LASTFM_USER = "..."
$env:SPOTIPY_CLIENT_ID = "..."
$env:SPOTIPY_CLIENT_SECRET = "..."
$env:GETSONGBPM_API_KEY = "..."   # optional
```

## Usage

### Playlist

```
python lastfm_to_spotify.py
```

A browser tab opens once for Spotify login. The script pulls your top tracks from Last.fm (most played first, stopping at the threshold), matches each one on Spotify, creates a private playlist and adds the matches. Tracks it could not match are listed in `misses.txt`.

To change the threshold, edit `MIN_SCROBBLES` at the top of the script.

### CSV

```
python lastfm_to_csv.py
```

Writes `scrobbles.csv`. Without a GetSongBPM key the BPM column is left blank. `MIN_SCROBBLES` at the top of the script controls which tracks are included (0 means all of them).

Where each column comes from:

| Column | Source |
| --- | --- |
| scrobbles, artist, track | Last.fm top tracks |
| album, length | Last.fm `track.getInfo` (blank if Last.fm has no data) |
| genre | Top two Last.fm tags for the track, falling back to the artist's tags |
| bpm | GetSongBPM, first search match |

Genre comes from user-submitted tags, so it can be noisy. BPM uses the first match for each lookup, so a few values will be wrong or missing.

## Resuming

Both scripts cache their lookups (`matches.json`, `lastfm_meta.json`, `bpm.json`) and save as they go. If a run is interrupted, running it again skips everything already looked up.

## Rate limits

Spotify's development mode has strict rate limits. If you hit one, the playlist script prints how long it is waiting, and the wait can run to many hours. Your progress is saved in `matches.json`, so you can stop it and rerun later.

## Do not commit these files

Add them to `.gitignore` before pushing anything:

```
.spotify_token
matches.json
lastfm_meta.json
bpm.json
misses.txt
scrobbles.csv
```

`.spotify_token` holds your Spotify login token, and the others are personal listening data. Never put API keys or secrets in the repo; they should only live in environment variables.
