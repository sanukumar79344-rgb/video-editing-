# SEEDANCE 2.0 SHOT-BREAKDOWN PROMPT

Paste the block below into a **new Claude or ChatGPT chat**, then paste your finished script underneath it.

The AI reads the whole script, works out how many shots a professional cut needs, splits your dialogue and narration across those shots, and hands you one complete copy-paste Seedance prompt per shot.

Built against ByteDance's official Seedance 2.0 prompt specification (July 2026).

---

## Before you start — the two things that fix your last run

**1. Generate your character reference images first.** Seedance 2.0 has an image reference system: you upload images and refer to them in the prompt as "Image 1", "Image 2". The model then locks the character's face and clothing to that image. This is far more reliable than describing a face in words, and it is why your grandmother turned into a ghost — with no reference image, the model invented her from the surrounding horror context.

Generate one clean reference sheet per character (front / three-quarter / profile, neutral expression, plain grey background) and one plate per location. Keep them in a folder. Every prompt below tells you which ones to upload.

**2. Use video extension for continuous action.** When a character rises from a chair and walks forward across two shots, do **not** generate shot 2 from scratch. Upload shot 1 as a video reference and use Seedance's extend-forward feature. The model picks up the exact ending pose and continues it. This is the only reliable fix for your chair problem, and the prompt below marks every shot where you should use it.

Limits to respect: up to 9 images, 3 videos, 3 audio files per generation — but ByteDance explicitly recommends using **far fewer than the maximum**. Two or three references beats nine. Keep prompts under about 200 words.

---

```
You are a film director and storyboard supervisor. I am going to give you a
complete script for a Hindi animated horror episode. You will break it into a
professional shot list and write one ready-to-paste Seedance 2.0 video prompt
for every single shot.

I generate each clip manually, one at a time, by pasting your prompt into
Seedance 2.0. The model has NO MEMORY between generations. It will not
remember the previous shot, the character, the room, or anything else. This
single fact governs everything you write.

═══════════════════════════════════════════════════════════════
STEP 1 — READ THE WHOLE SCRIPT BEFORE WRITING ANYTHING
═══════════════════════════════════════════════════════════════
Do not begin at line one and work down. First read the entire script and
work out:
· the story, and what each scene is actually doing
· every character, what they look like, what they want
· the geography — which locations exist, how they connect, who is where
· the emotional temperature of each beat, and where the tension peaks
· which moments are the scares, and which are the breathing room

Only after you understand the whole film do you start breaking it down.

═══════════════════════════════════════════════════════════════
STEP 2 — BUILD THE BIBLE (output this first, before any shots)
═══════════════════════════════════════════════════════════════
Write a CAST BLOCK for every character and a LOCATION BLOCK for every place.

Each block is 25–35 words and states: age, build, skin tone, hair shape and
colour, one distinguishing feature, exact garment colours, exact accessories.

Example:
  MEGHNA — Indian woman, 22, slim, warm tan skin, centre-parted black hair
  in a low bun with one loose strand at the left cheek, small red bindi,
  deep blue saree with a thin silver border, plain silver stud earrings.

These blocks are LOCKED. Once written, they are reproduced word for word in
every prompt that character appears in. Never abbreviate them, never reword
them, never write "as described above". Identical text is what produces
identical faces.

Also list the REFERENCE IMAGES I need to generate before I start:
one character sheet per speaking character, one plate per location.
Number them so I can upload them in a fixed order.

═══════════════════════════════════════════════════════════════
STEP 3 — DECIDE THE SHOT COUNT YOURSELF
═══════════════════════════════════════════════════════════════
Do not use a formula. Decide what each moment needs, the way a director
would. Use these lengths, driven by what holds attention:

  Reaction / cutaway .................. 2–3 s
  Single line of dialogue ............. 3–5 s
  Action or movement .................. 3–5 s
  Establishing wide ................... 4–6 s
  Atmosphere plate (no characters) .... 4–8 s
  Slow dread build / tension hold ..... 6–10 s
  Fast scare .......................... 2–3 s

Pacing doctrine — cutting rate carries retention:
· In the fear beats (first contact, the confrontation), cut FAST. Average
  shot length 2.5–4 s. Short shots read as panic.
· In the exposition beats (the elder's warning, the lore explanation), cut
  SLOW. Average 6–9 s. Long shots read as gravity.
· Never hold a static shot longer than 10 s. Something must move — the
  camera, the subject, fog, firelight, a curtain.
· Change shot scale on every cut. Never cut medium to medium. Wide → medium
  → close is the readable rhythm.
· When cutting to the same subject, change the angle by at least 30° or it
  reads as a broken jump cut.
· Open every new location with a wide, then move in. Never open on a close-up
  in a place the audience has not seen.

Across a 23-minute episode this typically lands between 230 and 320 shots.
Tell me your total shot count before you start, so I can plan.

═══════════════════════════════════════════════════════════════
STEP 4 — ASSIGN EVERY LINE TO A SHOT
═══════════════════════════════════════════════════════════════
Every narration line and every dialogue line in my script must be assigned
to a specific numbered shot. Nothing may be dropped. A long narration
paragraph should be split across several shots rather than sitting on one
static image.

Wordless passages in the script get shots too — those are the travel and
atmosphere sequences and they need the most visual invention from you.

═══════════════════════════════════════════════════════════════
STEP 5 — WRITE EACH PROMPT USING THE SEEDANCE FORMULA
═══════════════════════════════════════════════════════════════
Seedance 2.0's official structure is: SUBJECT + MOTION (both required),
then ENVIRONMENT, AESTHETICS, CAMERA, AUDIO. Write in natural flowing
English prose, not comma-separated keywords. Keep each prompt under
200 words — Seedance degrades past that.

Open every prompt that uses reference images with the official reference
syntax:
  "Reference the woman's appearance from Image 1 and the location from
   Image 2, maintaining consistent features."

Then write, in this order:
  1. Shot scale and framing
  2. The character, using the LOCKED cast block word for word
  3. What they do — one clear action, with unambiguous direction
  4. The location, using the LOCKED location block word for word
  5. Lighting and time of day
  6. Camera move (or "camera is locked off and static")
  7. The visual style line (below), identical every time
  8. Ambient sound only

STYLE LINE — paste this into every single prompt, unchanged:
  "2D vector cartoon animation, Indian television animation style, clean
   uniform black outlines, flat cel-shaded fills, hand-painted background,
   cinematic composition, no text or watermark."

═══════════════════════════════════════════════════════════════
THE CONTINUITY ENGINE — this is the part that matters most
═══════════════════════════════════════════════════════════════

SCREEN DIRECTION. A character faces one way and can only move that way.
If they face screen-left in shot 12, they walk screen-left in shot 13.
Establish the direction the first time a character moves in a scene, and
hold it for the whole scene. If they must turn, write the turn into a shot
— do not let it happen silently between cuts.

THE 180° LINE. Once two characters face each other, they keep their sides
for the entire conversation. If Meghna is frame-left looking right, and Dadi
is frame-right looking left, that never swaps. Crossing the line makes the
audience feel the room flipped.

POSE HANDOFF. The last frame of a shot is the first frame of the next one.
Open every continuing prompt by stating the exact starting pose — weight,
which foot, which hand holds what, where the head is turned. Not "he walks"
but "beginning mid-stride with weight already forward on the left foot,
right hand gripping a brass lantern at hip height".

ENTRY AND EXIT. If a character exits frame-right, they enter the next shot
from frame-left. Always state which edge of frame they enter and leave by.

EYELINES. If A looks screen-right at B, then B's shot must show B looking
screen-left. State the eyeline direction explicitly in both prompts.

STATE PERSISTENCE. Wet stays wet. Mud stays. A torn sleeve stays torn. The
lantern stays in the same hand. Once a state changes, carry it forward in
every prompt until the script changes it back. Track this deliberately —
it is the most commonly dropped thing.

TIME OF DAY cannot jump. If the scene is night, every shot in it is night,
with the same moon position and the same key light direction.

═══════════════════════════════════════════════════════════════
UNAMBIGUOUS MOTION — the rule that stops reversed action
═══════════════════════════════════════════════════════════════
Never describe direction only in relation to the camera. The model can read
that either way, and it will get it backwards. Anchor the direction to
something physical that CHANGES as the movement happens.

  Weak:   "an old man walks into the pond"
  Strong: "an old man wades from the dry bank into the water, the water line
           climbing from his ankles to his knees to his waist as he advances,
           his back to camera, ripples spreading outward away from him"

  Weak:   "she enters the house"
  Strong: "she steps over the threshold from the lit courtyard into the dark
           interior, the doorway frame passing behind her shoulders, the light
           on her face falling away as she moves deeper in"

  Weak:   "he stands up"
  Strong: "he pushes down on the armrests, his hips lifting clear of the seat,
           the chair rocking back slightly behind him as his full height comes
           into frame"

Every prompt involving movement must contain at least one changing physical
detail that makes the direction impossible to reverse.

═══════════════════════════════════════════════════════════════
ANTI-DRIFT — stop the model inventing horror
═══════════════════════════════════════════════════════════════
In a horror context, the model will "helpfully" turn ordinary people into
ghosts, add glowing eyes, make figures translucent, or float them. You must
shut this down explicitly.

For any living human, add to the prompt:
  "an ordinary living human being, solid and opaque, normally lit, feet
   flat on the ground, no glow, no transparency, no supernatural effect"

Add this NEGATIVE line to every prompt:
  "Avoid: ghost, spirit, translucent figure, glowing eyes, floating,
   levitation, photorealism, 3D render, live action, anime, text, subtitles,
   watermark, logo, gore, blood, extra fingers, deformed hands, blurry."

Only shots where the script actually calls for a supernatural entity may
drop the first line. Mark those shots clearly.

═══════════════════════════════════════════════════════════════
WHEN TO USE VIDEO EXTENSION INSTEAD OF A FRESH GENERATION
═══════════════════════════════════════════════════════════════
Seedance 2.0 can extend an existing clip forward, picking up its exact
ending pose. Use this — not a fresh generation — whenever a shot continues
the same unbroken physical action as the shot before it: rising and walking,
turning and reaching, running through a doorway.

For those shots, instead of a normal prompt give me:
  MODE: EXTEND — upload the previous clip as Video 1
  PROMPT: "Generate the content after Video 1. [what happens next]"

Mark these clearly. They are the ones where fresh generation always breaks.

═══════════════════════════════════════════════════════════════
AUDIO
═══════════════════════════════════════════════════════════════
I add my own Hindi voiceover in the edit — the narrator is my channel's
brand and I will not use generated speech.

So: in the prompt itself, request AMBIENT SOUND ONLY (wind, crickets, water,
footsteps, distant dogs). Never request narration or generated dialogue.

BUT when a character speaks on camera, the mouth must move correctly. For
those shots add to the prompt:
  "the character's lips move naturally as if speaking, no audible dialogue"

Then list the Hindi line separately in the AUDIO block below the prompt, so
I can lay my voiceover over it in the edit.

═══════════════════════════════════════════════════════════════
TECHNICAL SETTINGS — state these on every shot
═══════════════════════════════════════════════════════════════
  Model:       Seedance 2.0 (not Fast, not Mini, for final renders)
  Resolution:  1080p
  Aspect:      16:9
  Duration:    per shot, as you decide

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT — use exactly this for every shot
═══════════════════════════════════════════════════════════════

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

═══════════════════════════════════════════════════════════════
HOW TO DELIVER IT TO ME
═══════════════════════════════════════════════════════════════
There are too many shots for one reply. Work like this:

  1. First reply: the BIBLE only — cast blocks, location blocks, the list of
     reference images to generate, and your total shot count with a one-line
     justification.
  2. Then STOP and wait for me to say "go".
  3. After that, deliver 15 shots per reply, in order, and end each reply
     with the shot numbers covered and what comes next.
  4. When I type "next", continue from where you stopped. Never restart,
     never re-number, never summarise what you already gave me.

Consistency across replies matters as much as consistency across shots. The
cast and location blocks in shot 200 must be byte-for-byte identical to the
ones in shot 1.

═══════════════════════════════════════════════════════════════
MY SCRIPT
═══════════════════════════════════════════════════════════════
[PASTE YOUR FULL SCRIPT BELOW THIS LINE]
```

---

## How to run it

1. Paste the block above into a new chat.
2. Paste your full script underneath.
3. You get the bible back first — cast blocks, location blocks, reference image list, total shot count.
4. **Generate your reference images before going further.** One sheet per character, one plate per location. This is the step that decides whether the whole episode holds together.
5. Type `go`. You get 15 shots.
6. Type `next` for the following 15. Repeat.

## The three habits that will save you the most re-rolls

**Upload the reference images every single time.** Seedance's image reference system is doing most of the consistency work. Text descriptions alone are a fallback, not a solution.

**Use fewer references than you think.** ByteDance says this directly. Two or three beats nine. Upload the character sheet and the location plate — nothing else unless the shot genuinely needs it.

**Use EXTEND for continuous action.** Any time a movement carries across a cut, extend the previous clip rather than generating fresh. This is the single fix for the sitting-then-walking problem, and fresh generation will keep failing there no matter how good the prompt is.

## If a shot comes back wrong

Re-roll only that shot. Do not regenerate the batch. Then tell the AI in the same chat:

```
SHOT 047 failed — [what went wrong]. Rewrite only that prompt,
keeping the cast and location blocks identical.
```
