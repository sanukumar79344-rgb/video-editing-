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

# make_reels.py — long video → 6–8 ranked 25–50 s Reels / Shorts

```bash
# 1. download + transcribe the whole video, draft the best 6–8 moments
python3 make_reels.py analyze "https://youtu.be/VIDEO" [--cookies cookies.txt] [--model medium|large-v3]
python3 make_reels.py analyze source.mp4            # or a file you downloaded yourself
#    → work/transcript.txt (timestamped), work/candidates.json, work/plan.json (draft)
# 2. curate work/plan.json (see below)
# 3. export out/Reel_01.mp4 … Reel_08.mp4 (rank order) + out/REELS.md + out/reels.json
python3 make_reels.py render work/plan.json         # --only 2,5 re-renders just those reels
# 4. quality control: specs, 25–50 s, clean decode, loudness, captions, no overlap; contact sheets in out/qc/
python3 make_reels.py qc
# or all at once with the auto-drafted plan:
python3 make_reels.py auto "https://youtu.be/VIDEO"
```

`plan.json` — one entry per reel, **listed best first** (max 8):

```json
{"source": "https://youtu.be/VIDEO", "language": "en", "clips": [
  {"start": 312.4, "end": 355.0,                 // source seconds; snapped to whole words
   "drop": [[330.1, 333.8]],                     // optional asides to cut (sentence-aligned)
   "hook": "On-screen hook for the first 3 s",
   "keywords": ["habit", "million"],             // coloured green in the captions (numbers are automatic)
   "fixes": {"Jon": "John"},                     // ASR spelling corrections
   "score": 9, "why": "…", "ig_caption": "…", "yt_title": "…", "hashtags": ["#a", "#b"]}]}
```

| Step | Detail |
|---|---|
| Selection | Every sentence-aligned window whose *edited* length is 27–47 s is scored (Most-replayed heatmap, hook language in the first 3 s, vocal emphasis, questions, pacing, weak openers/segue endings, ASR confidence); best non-overlapping 6–8 kept, with a quality floor so weak moments aren't padded in. |
| Pauses | Silences > 0.6 s are cut to a natural breath; cuts only between words, 15 ms audio micro-fades. |
| Framing | Shot-aware: each camera shot is cropped 9:16 around the speaker's face (fixed per shot, no jitter); shots without one stable face use the full frame on a blurred fill. Never stretched. |
| Motion | 1.00→1.04 push-in per segment, alternating 1.00/1.07 punch-in on each jump cut. |
| Captions | Burned in, word-synced, 1–3 words/card, Inter ExtraBold, active word yellow, keywords & numbers green, safe zone; boxed hook card for the first 3 s. Hindi/Devanagari renders via Noto fallback (`apt install fonts-noto-core`). |
| Audio | 70 Hz high-pass + light FFT denoise (`--no-denoise` to skip), −14 LUFS / ≤ −1 dBTP, AAC 256k 48 kHz. |
| Encode | 1080×1920 H.264 High@4.2 CRF 17, yuv420p, BT.709, 30/60 fps, `+faststart`. |
