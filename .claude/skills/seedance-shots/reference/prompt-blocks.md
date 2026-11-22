# Fixed blocks — paste these unchanged

## Style line (every single prompt)

```
2D vector cartoon animation, Indian television animation style, clean uniform
black outlines, flat cel-shaded fills, hand-painted background, cinematic
composition, no text or watermark.
```

## Anti-drift line (every living human)

In a horror context the model will "helpfully" turn ordinary people into
ghosts, add glowing eyes, make figures translucent, or float them. Shut it
down explicitly. For any living human, add:

```
an ordinary living human being, solid and opaque, normally lit, feet flat on
the ground, no glow, no transparency, no supernatural effect
```

Only shots where the script actually calls for a supernatural entity may drop
this line. Mark those shots clearly.

## Negative line (every single prompt)

```
Avoid: ghost, spirit, translucent figure, glowing eyes, floating, levitation,
photorealism, 3D render, live action, anime, text, subtitles, watermark, logo,
gore, blood, extra fingers, deformed hands, blurry.
```

## Reference syntax (any prompt using uploaded images)

```
Reference the woman's appearance from Image 1 and the location from Image 2,
maintaining consistent features.
```

## Technical settings (state on every shot)

| | |
|---|---|
| Model | Seedance 2.0 (not Fast, not Mini, for final renders) |
| Resolution | 1080p |
| Aspect | 16:9 |
| Duration | per shot, as decided |

## Output template — use exactly this for every shot

```
━━━━━━ SHOT 047 ━━━━━━ 6s ━━━━━━ BEAT 6: THE LORE DUMP ━━━━━━

UPLOAD:  Image 1 = MEGHNA_sheet   ·   Image 2 = COURTYARD_plate
MODE:    Fresh generation          (or: EXTEND from SHOT 046)
SETTINGS: Seedance 2.0 · 1080p · 16:9 · 6s

PROMPT (copy everything below this line)
─────────────────────────────────────────
[the full self-contained prompt, under 200 words]
─────────────────────────────────────────

CONTINUITY
  Opens with:  [exact starting pose — weight, hands, head direction]
  Ends with:   [exact ending pose, which SHOT 048 must open from]
  Facing:      screen-left     Moves: screen-left
  Enters from: frame-right     Exits: does not exit
  Carried:     wet saree hem, mud on left foot, lantern in right hand

AUDIO (add in edit)
  NARRATION: "पिछले सौ सालों से यह कुआँ सूखा पड़ा था।"
  SFX: झींगुर, distant dog
```

## Re-roll request format

```
SHOT 047 failed — [what went wrong]. Rewrite only that prompt,
keeping the cast and location blocks identical.
```
