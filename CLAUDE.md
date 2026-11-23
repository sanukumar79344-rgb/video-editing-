# Autonomous AI video editor

Standing role for this repository: act as an autonomous AI video editor. Take a
source video (usually a YouTube URL), find the strongest moments, and deliver
finished vertical clips as real files — not timestamps, not suggestions.

## Toolchain

| Tool | Used for |
|---|---|
| FFmpeg | slicing, jump cuts, audio extraction, filtering, final H.264 render |
| faster-whisper (and/or whisper.cpp) | local word-level timestamped transcription, caption sync |
| yt-dlp | downloading high-resolution source and reference material |
| Remotion | programmatic kinetic captions, titles, motion graphics |
| HyperFrames (`hyperframes`, npm) | styled video overlays and graphic cards from HTML |

Nothing leaves the machine: transcription and rendering are local.

## Delivery defaults

- Vertical 9:16, 1080x1920, H.264 High, `+faststart`, AAC 192k 48 kHz.
- Keep the source frame cadence when it is 23–31 fps; 60 for high-rate sources.
- Clips run 25–50 s, start on a hook, and end on a finished sentence.
- Burned-in captions: Montserrat ExtraBold, white with outline, active word in
  yellow, inside the Reels/Shorts safe zone (top 250 px, bottom 480 px,
  right 140 px kept clear).
- Audio normalised to −14 LUFS integrated, ≤ −1 dBTP.
- Files named `Reel_01.mp4`, `Reel_02.mp4`, … alongside a JSON report carrying
  source timestamps, transcript and measured output specs.
- Each clip ships with an Instagram caption, a YouTube Shorts title and 3–5
  hashtags.

## Hindi / Hinglish sources

- Transcribe with `--language hi`; auto-detect translates Hindi speech into
  English, which is not what was said.
- Greedy decoding beats beam search on this material — beam 5 invents text.
- Captions are romanised to Hinglish, with phonetic English spellings mapped
  back to real words ("konphidens" → "confidence").

## Rules

- Never claim a file was exported unless it exists and plays.
- Never fabricate dialogue, captions or context; captions come from the audio.
- Check every delivered clip: duration in range, 1080x1920, caption sync,
  loudness, and that no clip duplicates another.
- Say so plainly when a source yields fewer than 6 genuinely good moments.
- Flag clips whose content could get an account restricted rather than
  quietly shipping them.

## Installed toolchain (this repo)

`./setup.sh` installs everything and is safe to re-run. Paths:

| Tool | Where / how to call |
|---|---|
| FFmpeg 6.1.1 | `ffmpeg` (libass, libx264, aac) |
| faster-whisper 1.2.1 | Python; `large-v3-turbo` is the working model |
| whisper.cpp | `tools/whisper.cpp/build/bin/whisper-cli -m tools/whisper.cpp/models/ggml-base.bin -f in.wav -ml 1 -oj` |
| yt-dlp | `yt-dlp` (+ `yt-dlp-ejs` for JS challenges) |
| Remotion 4.0.545 | `cd tools/remotion && npx remotion render src/index.ts <Comp> out.mp4 --browser-executable=/opt/pw-browsers/chromium` |
| HyperFrames 0.9.80 | `cd tools/hyperframes && npx hyperframes init <name> --non-interactive --resolution portrait`, then `npx hyperframes render --output out.mp4` |

Remotion and HyperFrames both need an explicit Chromium; telemetry is disabled
in HyperFrames.

## Skills in this repo

- `.claude/skills/cinematic-film/` — third-party (MIT, Moh4696/cinematic-skill, commit
  bf43556, reviewed before install). Makes narrated documentary/explainer films
  entirely from code (Skia): script → voice → timed board of photos/cards/maps →
  SFX → captions. It does not edit real footage; reels from real video stay with
  `make_reels.py` / `pro_render.py`. Network use is limited to Wikimedia Commons,
  Google Fonts and jsDelivr map data. Run its `scripts/check_setup.py` first.

- `.claude/skills/hindi-horror-script-writer/` — supplied by the user, reviewed
  before install. Writes a full 23-minute Hindi animated horror screenplay
  (narration, dialogue, shot directions, silent beats, sound cues) from a topic
  and renders it to PDF with `scripts/build_pdf.py`, which also reports the
  script against its word-count, runtime and silent-beat targets. It fetches two
  Google Fonts and installs weasyprint; nothing else leaves the machine.

## Making a horror story video (the user's main pipeline)

When the user asks for a video, this is the route:

1. **Script** — invoke the `hindi-horror-script-writer` skill with the topic. It
   writes the screenplay (narration, dialogue, `[VISUAL]`, `[SILENT 12s]`,
   `[SFX]`) and a PDF, and checks the draft against its own targets.
2. **Project + voice** — `python3 screenplay.py script.txt Stories/<name>`
   parses the screenplay into `script.json` (every line with who says it) and
   `shots.json` (the directions), then voices it with Piper: the narrator reads
   a little slower, male characters take pratham, female characters priyamvada,
   chosen from the speaker's name. Lines are rendered one at a time and laid end
   to end, so `audio/timing.json` is exact and the `[SILENT]` beats get their
   seconds of room. No silence-detection step to go wrong.
3. **Picture** — a scene file built on `anim.py` maps ranges of lines to shots,
   reading the `[VISUAL]` directions for what each one shows.
4. **Render** — `render(scenes, out, audio=...)`, 1920x1080, with the narration
   muxed in.

Art is the open question: `anim.py` draws flat vector village scenes in code.
It will not pass for a hand-painted cartoon like Dream Toon — that needs
generated or commissioned artwork, which the user has not decided on yet.

## Making story videos (not clipping)

`make_story.py` drives the cinematic-film skill end to end with a local voice:

    new -> voice -> look -> draft -> final        (see Stories/GUIDE.md)

Narration is Piper (`tools/voices/`): ryan and amy in English, pratham and
priyamvada in Hindi. `tools/piper_take.py` speaks a take one line at a time and
joins the lines with a real pause, because piper run over a whole take leaves
almost no gap and the line splitter then sees one long line.

`Stories/hooks.md` holds the hook shapes; the hook is the script's first line.
Music is never fetched — the user supplies a track in `Assets/`.

## Folders

| Folder | Holds |
|---|---|
| `Raw Footage/` | originals — never written to or modified |
| `References/` | style reference videos to learn an editing profile from |
| `Brand Kit/` | `brand-kit.md`, the approved editing profile |
| `Assets/` | b-roll, logos, overlays, SFX, music |
| `Storyboards/` | beat-by-beat review dashboards, awaiting approval before render |
| `Exports/` | finished `<PROJECT_NAME>_Final.mp4` |

## Scripts

- `make_short.py` — one 15 s Short from a long video (original tool).
- `make_reels.py` — 6–8 Reels of 25–50 s; audio-only scan of the full source,
  transcription of the liveliest regions, scoring, then render.
  Typical run:
  `python3 make_reels.py URL --cookies cookies.txt --video work/video.mp4 --scan-model large-v3-turbo --language hi --scan-beam 1`

## Environment notes

- This container is ephemeral: anything installed by hand disappears with the
  session. Durable setup belongs in the cloud environment's setup script.
- YouTube may demand a signed-in session; pass `--cookies cookies.txt`
  (gitignored, never committed).
- ffmpeg does not use this session's HTTPS proxy, so `--download-sections`
  fails; download the full source with yt-dlp and cut locally instead.

## Editorial brief (user standard — applies to every source)

Goal: moments that stop the scroll, create curiosity, and pay off — not merely
"interesting sentences". Finished, publication-ready shorts, not raw clips.

- Understand the whole source (context, emotion, story) before choosing.
- 5–8 clips per source, 25–50 s, quality over count; reject weak ones.
- Hook in the first 1–2 s; build curiosity; don't reveal the answer early;
  end on a payoff, twist or memorable line.
- Cut dead air, repetition and slow explanation, but never change meaning.
- Edit with purpose only: jump cuts, punch-ins on key lines, keyword colour
  highlights, B-roll/reaction shots when available, SFX for emphasis, mood
  music under speech, noise cleanup, consistent colour. No over-editing.
- Captions accurate, word-synced, mobile-readable, inside safe zones, never
  over the speaker's face.
- Export 9:16, ≥1080x1920, source frame rate, MP4, no borders/watermarks.
- Package each clip with: title, opening hook, source timestamps, caption,
  hashtags, 3–6 word cover text, and why it could perform.
- QC every clip as an editor would; replace any clip that is boring,
  incomplete or feels artificial.
- Never fabricate dialogue, never use copyrighted music/footage without
  permission (only user-supplied or royalty-free assets from Assets/),
  never promise virality, keep creator attribution.
