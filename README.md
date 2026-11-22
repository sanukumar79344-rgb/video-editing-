# make_short.py — long video → one 15 s vertical Short / Reel

```bash
pip install -r requirements.txt          # also needs ffmpeg with libass
python3 make_short.py "https://www.youtube.com/watch?v=CswOUBuokjo" -o out/short.mp4
# YouTube asking "Sign in to confirm you're not a bot"? export cookies.txt from your browser:
python3 make_short.py URL --cookies cookies.txt -o out/short.mp4
# or point it at a file you already downloaded:
python3 make_short.py source.mp4 -o out/short.mp4
```

Writes `out/short.mp4` plus `out/short.json` with the exact source start/end timestamps,
the transcript of the clip, why it was chosen, and measured output loudness/specs.

## What it does
| Step | Detail |
|---|---|
| Selection | Scores every 14–16 s window that **starts at a sentence start and ends at a sentence end/breath** (never mid-word). Signals: YouTube "Most replayed" heatmap (when available), vocal emphasis vs. the rest of the video, hook language in the first 3 s, payoff (not a segue) in the last 3.5 s, weak openers ("and/so/but"), pacing, ASR confidence. Silence/room tone around the lines is used to reach 15 s. |
| Framing | 1080×1920 9:16. Face-centred crop when a single speaker is stable; otherwise the full frame on a blurred fill so nothing important is cropped out. |
| Punch-in | Eased 1.00→1.12 zoom over 0.35 s on the most emphasised word after the first second. |
| Captions | Burned-in, auto-synced (faster-whisper word timestamps), Inter ExtraBold, white with a 7 px black outline, active word in yellow, 1–3 words per card, kept inside the Reels/Shorts safe zone (top 250 px, bottom 480 px, right 140 px clear). |
| Audio | Two-pass EBU R128 loudnorm → measured residual-gain pass + limiter → **−14 LUFS integrated, ≤ −1 dBTP**, 48 kHz stereo AAC 192k. |
| Fades | 0.2 s video and audio fade in/out. |
| Encode | H.264 High@4.2, yuv420p, BT.709, CRF 18, 30 or 60 fps matching the source, `+faststart` MP4. |

Use `--start SECONDS` to force a region, `--model medium` for better transcription.

---

# make_clips.py — long video → several 25-50 s Reels / Shorts

```bash
python3 make_clips.py "https://youtu.be/VIDEOID" -n 3 -o out/
python3 make_clips.py URL --cookies cookies.txt -n 5      # YouTube sign-in check
python3 make_clips.py source.mp4 --min 30 --max 45        # local file, tighter range
python3 make_clips.py URL --dry-run                       # timestamps only, no render
```

Writes `out/clip01.mp4 … clipNN.mp4` plus `out/clips.json` with each clip's exact
source in/out timestamps, transcript, a suggested title, why it was chosen, and
the measured output specs.

## How it differs from `make_short.py`
| | `make_short.py` | `make_clips.py` |
|---|---|---|
| Output | one 15 s clip | `-n` clips, 25-50 s each (`--min`/`--max`) |
| Selection | best single window | greedy best non-overlapping windows, ≥2 s apart |
| Scoring | hook, heat, energy, pacing | the same, plus a dead-air penalty and a question→answer arc bonus, and no hard 15 s length target |
| Motion | one punch-in | slow 1.00→1.05 Ken-Burns drift plus up to 3 gentle punch-ins on the biggest emphasis beats |

Everything else is shared with `make_short.py`: face-tracked 9:16 crop (blurred
fill for wide shots), word-highlight captions in the safe zone, −14 LUFS /
−1 dBTP audio, 0.2 s fades, H.264 High CRF 18 `+faststart`.

## Notes
* **Loudness**: the limiter runs at 192 kHz so inter-sample peaks are caught, and
  the delivered MP4 is re-checked after encoding — AAC was measured overshooting
  a 48 kHz-limited master by up to +2.9 dB.
* **OpenCV must stay below 5.0** (`requirements.txt` pins it). OpenCV 5 removed
  `CascadeClassifier`, which silently disables face-tracked cropping.
* **YouTube** needs `--cookies cookies.txt` whenever it asks you to sign in, and
  the sandbox must allow `*.googlevideo.com` (YouTube rotates the host per video).

## Making YouTube links work

A YouTube URL needs two things in a sandboxed environment. A local file path
needs neither — `python3 make_clips.py video.mp4 -n 3` works as-is.

**1. Sign-in cookies.** YouTube answers most datacentre requests with
"Sign in to confirm you're not a bot". Export cookies from a browser that is
logged in to YouTube:

* Install a `cookies.txt` extension (Chrome: "Get cookies.txt LOCALLY";
  Firefox: "cookies.txt"). Both export the Netscape format yt-dlp expects.
* Open <https://www.youtube.com> while signed in, click the extension, and
  export **only youtube.com** cookies.
* Save the file as `cookies.txt` in this repo. It is already in `.gitignore`,
  so it will not be committed — treat it like a password, since it grants
  access to the signed-in account.
* Run with `--cookies cookies.txt`. Re-export when downloads start failing
  again; these cookies expire.

**2. Network access for the video CDN.** YouTube streams each video from a
rotating `rr<N>---sn-<id>.googlevideo.com` host, so naming hosts one by one
does not work. In the cloud environment menu in the session title bar, choose
**Edit**, then either set Network access to unrestricted, or add
`*.googlevideo.com` under **Allowed domains** (leave "Allow package managers"
ticked). Keep `www.youtube.com` and `youtubei.googleapis.com` allowed too.
See <https://code.claude.com/docs/en/cloud-environments#network-access>.
