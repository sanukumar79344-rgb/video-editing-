# Shorts / Reels clip: India's Got Latent S2 EP9

Source: <https://www.youtube.com/watch?v=CswOUBuokjo> ("INDIA'S GOT LATENT S2 EP9 ft.
Raftaar, Balraj Ghai, Sahil Kale", 50:29, 25 fps, up to 2160p).

## Chosen segment

**43:22.0 → 43:37.0 (2602.0 s → 2617.0 s), 15.0 s.** This window is provisional.
`make_short.py` moves both cut points to the nearest real pauses in the speech,
keeps the clip at 15 ± 1 s, and writes the exact timestamps it used to `short.json`.

Why this moment: the contestant's **legal-notice story**. Everyone on the show got
a legal notice. He was stressed his family would find out ("घर पे अगर पता चला तो…"),
then he is reassured "कुछ नहीं पता चलेगा", and the punchline about a language they
don't understand ("…हिंदी नहीं आती") gets laughter at ~43:35. A notice
going home is easy to follow without having seen the episode, and the setup and
punchline fit in 15 s. It sits in the densest laughter/applause stretch of the
episode (42:30–44:00). I found that stretch by scoring YouTube's Hindi
auto-captions for `[हंसी]` (laughter) and applause tags in 30-second windows.
These captions drop some lines, so check the wording against the real audio
(`short.json` holds the Whisper transcript of the final cut).

Runner-up: 36:50–37:15 ("समाज बहुत घटिया है भाई"). It needs more context to land.

## Pipeline (`make_short.py`)

| Requirement | How it's done |
|---|---|
| Clean cut-in/out, 15 ± 1 s | faster-whisper word timestamps; cuts snapped to word gaps (≥0.35 s pauses preferred), then to whole frames |
| 9:16, 1080×1920 | Face-centred crop (OpenCV), Lanczos scaled; 4K source gives a true downscale |
| Frame rate | Matches source (25 fps; YouTube serves this video only at 25) |
| MP4 / H.264 / AAC | libx264 High@4.2, CRF 17, yuv420p, BT.709 tags, AAC-LC 192k 48 kHz, `+faststart` |
| Burned-in captions | Word-synced ASS: Noto Sans Devanagari Bold 84 px, white with 7 px black outline, active word yellow, pop-in per phrase |
| Safe zone | Captions centred at y=1180 with 130 px side margins. They stay clear of the top ~14%, the bottom ~25% and the right-side action rail |
| Punch-in | Smoothstep 1.00→1.12 zoom over 0.35 s, ~1 s before the loudest moment (the laugh), held to the end; `--hook` overrides |
| Loudness | Two-pass `loudnorm` to −14 LUFS integrated, −1 dBTP |
| Fades | 0.2 s video fade + 0.2 s audio fade at both ends |

## Run

```bash
pip install -r requirements.txt          # + ffmpeg, and fonts-noto-core for Devanagari
./fetch_source.sh                        # downloads 2592–2627 s at 4K
python3 make_short.py --source source_section.mkv --source-offset 2592 \
    --start 2602 --end 2617 --out short.mp4
# -> short.mp4 + short.json (exact original-video timestamps, transcript, crop, hook time)
```

Useful flags: `--hook <orig-seconds>`, `--crop-x 0..1`, `--zoom 1.12`,
`--model large-v3` (default), `--words-json` (skip Whisper), `--no-snap`.
In a network that blocks `cas-server.xethub.hf.co`, set `HF_HUB_DISABLE_XET=1` so the Whisper model can download.
