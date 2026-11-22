# NAGYAKSHI — VOICEOVER PACK

Clean read-aloud text. Stage directions, SFX aur visual cues **hata diye gaye hain** —
sirf wahi hai jo bola jaayega.

## Files
| File | Kya hai | Approx time |
|---|---|---|
| `01-hook.txt` | Cold open | 0:50 |
| `02-bhanwargarh.txt` | Part 1 | 2:40 |
| `03-baawdi.txt` | Part 2 | 3:00 |
| `04-rukma.txt` | Part 3 | 2:30 |
| `05-diya.txt` | Part 4 | 3:00 |
| `06-sauda.txt` | Part 5 | 2:00 |
| `07-climax.txt` | Twist ending | 1:00 |
| `nagyakshi-full.txt` | Sab ek saath | ~15:00 |
| `nagyakshi.ssml` | SSML version (pauses + emphasis built-in) | ~15:00 |

## Pause markers
- `...` = chhota pause (0.5 sec)
- `[PAUSE]` = 1.5 sec
- `[SILENCE]` = 2 sec dead air — climax ka sabse important moment, mat hatao

## Voice settings

**Narrator (Vikrant) — mard, 28 saal, thaka hua, fusfusahat:**
- Speed: 0.88x (dheema)
- Pitch: -2 semitone
- Style: whisper/sad

**Nagyakshi — aurat, gehri, goonjti:**
- Speed: 0.80x
- Pitch: -4 semitone
- Effect: reverb 40% + 2nd layer pitch -8st at 25% volume (ye "kai aawazein ek saath" wala effect deta hai)

**Sumer Kaka — budha, shaant:** Speed 0.85x, pitch -5st
**Rukma — ladki, pehle meethi, baad mein thandi:** Speed 1.0x → 0.85x reveal ke baad
**Thakur Jaspal — dabang, chillata hua:** Speed 1.1x, pitch -1st, loud

## Free TTS options (best → worst Hindi quality)

1. **ElevenLabs** (elevenlabs.io) — sabse natural Hindi. Free tier: 10,000 chars/month.
   Full script ~11,000 chars hai, to 2 free accounts ya ek month wait.
   Model: `eleven_multilingual_v2`. Voice: "Monika Sogam" ya "Devi" (Hindi).
2. **edge-tts** (free, unlimited, no account) — terminal mein:
   `pip install edge-tts`
   `edge-tts --voice hi-IN-MadhurNeural --rate=-12% -f 01-hook.txt --write-media hook.mp3`
   Voices: `hi-IN-MadhurNeural` (mard), `hi-IN-SwaraNeural` (aurat)
3. **Google Cloud TTS** — `hi-IN-Neural2-B` (mard). Free 1M chars/month.
4. **Narakeet** (narakeet.com) — Hindi, pay per minute, acchi quality.

## Khud record karna best hai
Horror mein insaan ki saans, kaanpti aawaz, aur galat jagah ruk jaana —
ye TTS kabhi nahi de paata. Phone ke mic mein, rajai ke andar baith kar record kar
(echo nahi aayega), phir Audacity mein:
Noise Reduction → Compressor → Reverb 15% → Bass +3dB.

## ffmpeg se jodna (ye container mein already installed hai)
```
ffmpeg -f concat -safe 0 -i list.txt -c copy nagyakshi-full.mp3
```
Jahan `list.txt` mein har line: `file '01-hook.mp3'`
