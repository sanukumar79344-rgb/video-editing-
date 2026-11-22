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
