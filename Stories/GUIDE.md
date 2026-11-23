# Making a YouTube story video

Everything needed is on this machine. Nothing is paid for, nothing is uploaded,
and no footage belonging to anyone else is used.

## What makes the video

| Piece | Where it comes from |
|---|---|
| Script | written here, from your idea or a researched subject |
| Hook | the first two lines of the script (see `hooks.md`) |
| Voiceover | Piper, local, four voices, unlimited (`tools/voices/`) |
| Pictures | Wikimedia Commons (licence-checked), your own files, or drawn in code |
| Motion | one camera gliding over a board — cards, photos, maps, numbers |
| Sound effects | synthesised from the cue list, nothing to license |
| Music | **you supply it** — put a royalty-free track in `Assets/` |
| Captions | burned in, plus an `.srt` to upload |

## The five commands

```bash
python3 make_story.py new   Stories/my-film --title "Title"   # folder + fonts
python3 make_story.py voice Stories/my-film --voice ryan      # narration + timings
python3 make_story.py look  Stories/my-film --at 2,10,20      # stills to judge
python3 make_story.py draft Stories/my-film --seconds 30      # first 30 s, 720p
python3 make_story.py final Stories/my-film                   # full 1080p + captions
```

`--vertical` on `final` renders 1080x1920 for Shorts and Reels instead.
`--music Assets/track.mp3` ducks a track under the voice.

Voices: `ryan` (en, deep male), `amy` (en, warm female), `pratham` (hi, male),
`priyamvada` (hi, female). `--pace 0.9` reads faster, `1.05` slower.

## The order of work, and why

1. **Script first.** `Stories/<name>/script.json` holds takes (sections) of lines.
   Each line carries `text` (on screen), `spoken` (numbers written as words, so
   the voice reads them properly) and `hero` (the one thing the camera is on).
2. **Voice second, picture third.** The film is timed to the narration, so the
   voice has to exist before the scene is laid out. Change the script, re-run
   `voice`, and every visual re-times itself — nothing is pinned to fixed seconds.
3. **Stills before renders.** A full render takes minutes; a still takes under a
   second. Judge the layout from stills.
4. **Draft before final.** 30 seconds at 720p shows pacing problems early.

## Rules that keep the channel safe

- No one else's footage, music or voice without permission.
- Archive images are fetched with their licence and credit recorded in
  `credits.md`; that file goes in the video description.
- Anything drawn in code that looks like a real document is labelled a
  recreation, and quotes only words really written.
- A story presented as true has to be true. Keep a note of sources per fact.

## Length

- 60–90 s: about 150–230 spoken words.
- 8–10 min (a full story video): about 1,200–1,600 words, 5–8 sections.
- Shorts: 35–50 s, one idea, hook in the first line.
