#!/usr/bin/env python3
"""
make_reels.py — turn one long video into 6–8 ranked, fully edited 25–50 s vertical Reels / Shorts.

Workflow (three steps, so a human — or Claude — can curate the moments in between):

  1. analyze   Download + transcribe the WHOLE video, then write
                 work/transcript.txt   sentence-level transcript with timestamps (read this to pick moments)
                 work/candidates.json  top auto-scored 25–50 s windows
                 work/plan.json        draft plan: best 6–8 non-overlapping windows
  2. (edit)    Curate work/plan.json: adjust start/end, write the on-screen hook, captions, title, hashtags,
               keywords to colour, ASR spelling fixes, and asides to cut ("drop").
  3. render    Export every clip in the plan as out/Reel_01.mp4 … Reel_08.mp4 (rank order), plus
               out/reels.json and out/REELS.md (ranking, timestamps, captions, titles, hashtags).
  4. qc        Verify every file: 1080x1920 H.264/AAC, 25–50 s, decodes cleanly, loudness, captions,
               no duplicate/overlapping clips; writes contact sheets to out/qc/ for a visual check.

  `auto` runs analyze → render → qc in one go using the draft plan.

Editing applied to every clip
  * Pauses: any silence > 0.6 s between words is cut down to a natural breath (jump cut, never mid-word).
  * Framing: shot-aware 9:16 crop — each camera shot is centred on the speaker's face (fixed per shot, no
    jitter); shots with no single stable face use the full frame on a blurred fill. Never stretched.
  * Motion: gentle 1.00→1.04 push-in per segment, alternating 1.00/1.07 punch on every jump cut.
  * Captions: burned in, word-synced (faster-whisper word timestamps), 1–3 words per card, Inter ExtraBold,
    active word yellow, keywords/numbers green, inside the Reels/Shorts safe zone.
  * Hook: the plan's hook line as a boxed title card for the first ~3 s.
  * Audio: 70 Hz high-pass + light FFT denoise, 15 ms micro-fades at cuts, two-pass EBU R128 → −14 LUFS,
    ≤ −1 dBTP, 48 kHz AAC 256k.
  * Encode: H.264 High@4.2, CRF 17, yuv420p, BT.709, 30/60 fps matching the source, +faststart.

Usage
  python3 make_reels.py analyze "https://youtu.be/VIDEO" [--cookies cookies.txt] [--model medium]
  python3 make_reels.py analyze source.mp4
  python3 make_reels.py render work/plan.json
  python3 make_reels.py qc
  python3 make_reels.py auto "https://youtu.be/VIDEO"
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from make_short import (LUFS, LRA, TP, H, W, SAFE_BOTTOM, SAFE_LEFT, SAFE_RIGHT, SAFE_TOP,
                        HOOK_PATTERNS, WEAK_STARTS, SENT_END, TAIL_WEAK, energy_curve, fetch, heat_at,
                        loudnorm_measure, measure_output, probe, run)

MIN_LEN, MAX_LEN = 25.0, 50.0          # hard limits on the delivered clip
AUTO_MIN, AUTO_MAX = 27.0, 47.0        # auto-selection aims inside the limits
MIN_CLIPS, MAX_CLIPS = 6, 8
GAP_MAX = 0.6                          # pauses longer than this are cut …
PAD_IN, PAD_OUT = 0.12, 0.22           # … keeping this much breath before / after the words
ACTIVE = r"&H00D7FF&"                  # #FFD700 yellow  (ASS colours are &HBBGGRR&)
KEYCOL = r"&H5BFF3B&"                  # #3BFF5B green
STRONG = re.compile(r"^(never|always|nobody|everyone|everything|nothing|secret|truth|mistake|wrong|crazy|"
                    r"insane|biggest|worst|best|million|billion|money|free|death|die|love|hate|fear|"
                    r"impossible|shocking|real|only|first|last|stop|must|rich|poor|fail|failed|success)$")


def get_source(source, work, cookies=None):
    """Reuse a source already downloaded into `work` instead of fetching it again."""
    if not os.path.exists(source):
        have = [p for p in work.glob("source.*") if p.suffix in (".mp4", ".mkv", ".webm")]
        if have:
            meta = json.loads((work / "meta.json").read_text()) if (work / "meta.json").exists() else {}
            return have[0], meta
    return fetch(source, work, cookies)


# =========================================================================== transcription
def transcribe(video, work, model_size, language=None):
    tag = f"{model_size}_{language or 'auto'}"
    cache = work / f"words_{tag}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    from faster_whisper import WhisperModel
    import numpy as np
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         check=True, capture_output=True).stdout
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
    model = WhisperModel(model_size, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
    segs, info = model.transcribe(audio, word_timestamps=True, vad_filter=True, beam_size=5, language=language,
                                  condition_on_previous_text=False)
    print(f"language: {info.language} ({info.language_probability:.2f})", file=sys.stderr)
    words = []
    for s in segs:
        for w in s.words or []:
            t = w.word.strip()
            if t:
                words.append({"t0": round(w.start, 3), "t1": round(w.end, 3), "w": t, "p": round(w.probability, 3)})
        print(f"\r  transcribed {s.end / 60:6.1f} min", end="", file=sys.stderr)
    print(file=sys.stderr)
    (work / "language.txt").write_text(info.language)
    cache.write_text(json.dumps(words))
    return words


def sentences(words):
    """Group word indices into sentences (punctuation or ≥0.8 s pause)."""
    out, start = [], 0
    for k, w in enumerate(words):
        gap = words[k + 1]["t0"] - w["t1"] if k + 1 < len(words) else 99
        if SENT_END.search(w["w"]) or gap >= 0.8:
            out.append((start, k)); start = k + 1
    return out


def fmt_ts(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}" if h else f"{m:02d}:{s:06.3f}"


def write_transcript(words, path):
    lines = []
    for a, b in sentences(words):
        text = " ".join(w["w"] for w in words[a:b + 1])
        lines.append(f"[{words[a]['t0']:8.2f}-{words[b]['t1']:8.2f}] ({fmt_ts(words[a]['t0'])}) {text}")
    Path(path).write_text("\n".join(lines) + "\n")


# =========================================================================== segments (pause removal)
def clip_words(words, start, end):
    return [k for k, w in enumerate(words) if w["t0"] >= start - 0.05 and w["t1"] <= end + 0.05]


def build_segments(words, idx, drops=()):
    """Kept source spans for a clip: words in `idx`, split at long pauses and at plan 'drop' ranges."""
    keep = [k for k in idx if not any(d0 <= words[k]["t0"] and words[k]["t1"] <= d1 for d0, d1 in drops)]
    if not keep:
        return [], []
    segs, cur = [], [keep[0]]
    for k in keep[1:]:
        prev = cur[-1]
        dropped_between = k != prev + 1
        if dropped_between or words[k]["t0"] - words[prev]["t1"] > GAP_MAX:
            segs.append(cur); cur = [k]
        else:
            cur.append(k)
    segs.append(cur)
    spans = []
    for s_idx, s in enumerate(segs):
        first, last = words[s[0]], words[s[-1]]
        prev_end = words[s[0] - 1]["t1"] if s[0] > 0 else 0.0
        next_start = words[s[-1] + 1]["t0"] if s[-1] + 1 < len(words) else last["t1"] + 1.0
        a = max(first["t0"] - PAD_IN, prev_end + 0.02, 0.0)
        b = min(last["t1"] + PAD_OUT, next_start - 0.02)
        spans.append([round(a, 3), round(max(b, last["t1"]), 3)])
    return spans, keep


def out_duration(spans):
    return sum(b - a for a, b in spans)


def to_out_time(spans, t):
    """Map a source time inside a kept span to the output timeline."""
    off = 0.0
    for a, b in spans:
        if a - 1e-6 <= t <= b + 1e-6:
            return off + (t - a)
        if t < a:
            return off
        off += b - a
    return off


# =========================================================================== auto selection
def score_clip(words, idx, spans, energy, heatmap, global_mean, hop=0.1):
    text = " ".join(words[k]["w"] for k in idx)
    lower = text.lower()
    dur = out_duration(spans)
    t_in, t_out = spans[0][0], spans[-1][1]
    seg = energy[int(t_in / hop):int(t_out / hop)] or [-60]
    voiced = [e for e in seg if e > -45] or seg
    mean_db = sum(voiced) / len(voiced)
    dyn = max(seg) - mean_db
    loud = mean_db - global_mean
    hooks = sum(len(re.findall(p, lower)) for p in HOOK_PATTERNS)
    t0 = words[idx[0]]["t0"]
    first3 = " ".join(words[k]["w"] for k in idx if words[k]["t0"] < t0 + 3.0).lower()
    early = sum(len(re.findall(p, first3)) for p in HOOK_PATTERNS)
    first = re.sub(r"[^a-z']", "", words[idx[0]]["w"].lower())
    tail = " ".join(words[k]["w"] for k in idx if words[k]["t1"] > words[idx[-1]]["t1"] - 4).lower()
    tail_weak = len(re.findall(TAIL_WEAK, tail))
    wps = len(idx) / dur
    conf = sum(words[k]["p"] for k in idx) / len(idx)
    heat = heat_at(heatmap, t_in, t_out)
    questions = lower.count("?")
    s = (4.0 * heat
         + 0.08 * dyn + 0.12 * loud
         + 0.25 * min(hooks / (dur / 10), 6) + 0.6 * min(early, 3)
         + (-1.5 if early == 0 else 0.0)
         + (-1.2 if first in WEAK_STARTS else 0.0)
         + 0.3 * min(questions, 2)
         - 0.5 * abs(wps - 2.8)
         + 2.0 * (conf - 0.8)
         - 1.5 * min(tail_weak, 2)
         - 0.03 * abs(dur - 38))
    return s, {"text": text, "heat": round(heat, 3), "hook_hits": hooks, "early_hook_hits": early,
               "weak_start": first in WEAK_STARTS, "words_per_sec": round(wps, 2), "asr_conf": round(conf, 3),
               "dyn_db": round(dyn, 2), "loud_vs_avg_db": round(loud, 2)}


def auto_candidates(words, energy, heatmap, duration):
    sents = sentences(words)
    g = [e for e in energy if e > -45] or energy
    gmean = sum(g) / len(g)
    cands = []
    for si, (a, _) in enumerate(sents):
        for sj in range(si, len(sents)):
            b = sents[sj][1]
            raw = words[b]["t1"] - words[a]["t0"]
            if raw > AUTO_MAX + 25:
                break
            if not SENT_END.search(words[b]["w"]) and sj + 1 < len(sents):
                continue
            idx = list(range(a, b + 1))
            spans, keep = build_segments(words, idx)
            d = out_duration(spans)
            if d < AUTO_MIN or d > AUTO_MAX or spans[-1][1] > duration:
                continue
            s, det = score_clip(words, keep, spans, energy, heatmap, gmean)
            cands.append({"score": round(s, 3), "start": spans[0][0], "end": spans[-1][1],
                          "out_duration": round(d, 2), **det})
    cands.sort(key=lambda c: -c["score"])
    return cands


def pick_non_overlapping(cands, n_max=MAX_CLIPS, spread=3.0):
    picked = []
    for c in cands:
        if all(c["end"] + spread <= p["start"] or c["start"] >= p["end"] + spread for p in picked):
            picked.append(c)
        if len(picked) >= n_max:
            break
    if picked:   # quality floor: never pad the list with clearly weaker moments
        best = picked[0]["score"]
        floor = best - max(3.0, abs(best) * 0.6)
        strong = [p for p in picked if p["score"] >= floor]
        picked = strong if len(strong) >= MIN_CLIPS else picked[:max(len(strong), min(MIN_CLIPS, len(picked)))]
    return picked


def draft_plan(source, picked, language):
    clips = []
    for c in picked:
        first_sentence = re.split(r"(?<=[.?!])\s", c["text"], maxsplit=1)[0]
        hook = " ".join(first_sentence.split()[:9])
        clips.append({
            "start": c["start"], "end": c["end"], "hook": hook, "keywords": [], "fixes": {}, "drop": [],
            "score": None, "why": "", "ig_caption": "", "yt_title": first_sentence[:90], "hashtags": [],
            "auto_score": c["score"], "transcript": c["text"],
        })
    return {"source": source, "language": language, "clips": clips}


# =========================================================================== framing
def track_shots(video, spans, src_w, src_h, step=0.2):
    """Return output-timeline shots [(t0, t1, face_x | None)] for the clip.

    Shot boundaries = segment joins + hard cuts in the source (histogram jump). Each shot gets the
    median horizontal face centre if a single face is stable in it, else None (→ blurred-fill layout)."""
    import cv2
    det = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    prof = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
    cap = cv2.VideoCapture(str(video))
    samples = []                       # (out_t, new_shot, [face xs], hist)
    off = 0.0
    for si, (a, b) in enumerate(spans):
        t = a
        first = True
        while t < b:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            if ok:
                small = cv2.resize(frame, (int(640 * src_w / max(src_w, src_h)) or 1, int(640 * src_h / max(src_w, src_h)) or 1))
                g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                hist = cv2.calcHist([cv2.cvtColor(small, cv2.COLOR_BGR2HSV)], [0, 1], None, [32, 32], [0, 180, 0, 256])
                cv2.normalize(hist, hist)
                mn = g.shape[0] // 9
                faces = list(det.detectMultiScale(g, 1.1, 6, minSize=(mn, mn)))
                if not faces:
                    faces = list(prof.detectMultiScale(g, 1.1, 6, minSize=(mn, mn)))
                    faces += [(g.shape[1] - x - w, y, w, h) for x, y, w, h in
                              prof.detectMultiScale(cv2.flip(g, 1), 1.1, 6, minSize=(mn, mn))]
                big = max((f[2] * f[3] for f in faces), default=0)
                xs = [(x + w / 2) / g.shape[1] for x, y, w, h in faces if w * h >= 0.35 * big]
                samples.append((off + t - a, first, xs, hist))
            first = False
            t += step
        off += b - a
    cap.release()
    total = off
    if not samples:
        return [(0.0, total, None)]
    # split into shots
    shots, cur = [], [samples[0]]
    for s in samples[1:]:
        cut = s[1] or cv2.compareHist(cur[-1][3], s[3], cv2.HISTCMP_CORREL) < 0.55
        if cut:
            shots.append(cur); cur = [s]
        else:
            cur.append(s)
    shots.append(cur)
    crop_frac = (src_h * 9 / 16) / src_w
    out = []
    for k, sh in enumerate(shots):
        t0 = sh[0][0]
        t1 = shots[k + 1][0][0] if k + 1 < len(shots) else total
        singles = [s[2][0] for s in sh if len(s[2]) == 1]
        multi = sum(1 for s in sh if len(s[2]) > 1)
        fx = None
        if len(singles) >= max(2, 0.4 * len(sh)) and multi <= 0.3 * len(sh):
            singles.sort()
            spread = singles[int(len(singles) * 0.9)] - singles[int(len(singles) * 0.1)]
            if spread <= crop_frac * 0.5:
                fx = singles[len(singles) // 2]
        elif multi > 0.5 * len(sh):
            # Several faces: crop only if they all fit inside one 9:16 window.
            allx = sorted(x for s in sh for x in s[2])
            if allx and allx[-1] - allx[0] <= crop_frac * 0.7:
                fx = (allx[0] + allx[-1]) / 2
        out.append([t0, t1, fx])
    # merge very short shots (<0.6 s, usually detector noise) into the previous one
    merged = []
    for s in out:
        same = (s[2] is None and merged and merged[-1][2] is None) or \
               (s[2] is not None and merged and merged[-1][2] is not None and abs(s[2] - merged[-1][2]) < 0.03)
        if merged and (s[1] - s[0] < 0.6 or same):
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    # a shot without a face between two shots with the same framing: keep that framing
    for k in range(1, len(merged) - 1):
        if merged[k][2] is None and merged[k - 1][2] is not None and merged[k + 1][2] is not None \
                and abs(merged[k - 1][2] - merged[k + 1][2]) < 0.05 and merged[k][1] - merged[k][0] < 2.0:
            merged[k][2] = merged[k - 1][2]
    return [tuple(s) for s in merged]


def piecewise(t_ranges, default):
    """ffmpeg expression: value per [t0,t1) range of the output timeline."""
    expr = str(default)
    for t0, t1, v in reversed(t_ranges):
        expr = f"if(between(t,{t0:.3f},{t1:.3f}),{v},{expr})"
    return expr


# =========================================================================== captions
def ass_time(t):
    t = max(0.0, t)
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def norm_word(w):
    return re.sub(r"[^\w']", "", w.lower())


def apply_fixes(text, fixes):
    for wrong, right in (fixes or {}).items():
        text = re.sub(rf"(?i)(?<!\w){re.escape(wrong)}(?!\w)", right, text)
    return text


def wrap_hook(text, max_chars=20):
    lines, cur = [], ""
    for w in text.split():
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur); cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return r"\N".join(lines[:4])


def build_ass(words, keep, spans, clip, path, dur, font="Inter ExtraBold"):
    keywords = {norm_word(k) for k in clip.get("keywords", []) for k in k.split()}
    fixes = clip.get("fixes", {})
    cap_y = H - SAFE_BOTTOM - 170           # caption baseline, lower-middle, clear of UI
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},86,&H00FFFFFF,&H00FFFFFF,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,1,7,3,2,{SAFE_LEFT + 30},{SAFE_RIGHT + 30},{H - cap_y},1
Style: Hook,{font},74,&H00000000,&H00000000,&H0000D7FF,&H0000D7FF,-1,0,0,0,100,100,0,0,3,22,0,8,{SAFE_LEFT + 20},{SAFE_RIGHT + 20},{SAFE_TOP + 70},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ws = []
    for k in keep:
        w = words[k]
        text = apply_fixes(w["w"], fixes)
        t0, t1 = to_out_time(spans, w["t0"]), to_out_time(spans, w["t1"])
        if ws and re.match(r"^[,.%']\S*$", text) and t0 - ws[-1]["t1"] < 0.15:
            ws[-1]["w"] += text; ws[-1]["t1"] = t1          # "$200" ",000" → "$200,000"; "90" "%" → "90%"
            continue
        ws.append({"w": text, "t0": t0, "t1": t1})
    cards, cur = [], []
    for k, w in enumerate(ws):
        cur.append(w)
        gap = ws[k + 1]["t0"] - w["t1"] if k + 1 < len(ws) else 9
        chars = sum(len(x["w"]) + 1 for x in cur)
        if re.search(r"[.,?!;:…।]$", w["w"]) or gap > 0.35 or len(cur) >= 3 or chars >= 16:
            cards.append(cur); cur = []
    if cur:
        cards.append(cur)
    lines = []
    for c, card in enumerate(cards):
        card_end = cards[c + 1][0]["t0"] if c + 1 < len(cards) else min(dur, card[-1]["t1"] + 0.5)
        for k, w in enumerate(card):
            start = w["t0"] if k else card[0]["t0"]
            end = card[k + 1]["t0"] if k + 1 < len(card) else card_end
            if end - start < 0.01:
                continue
            parts = []
            for m, x in enumerate(card):
                word = re.sub(r"[{}\\]", "", x["w"]).upper()
                key = norm_word(x["w"]) in keywords or re.search(r"\d", x["w"]) or STRONG.match(norm_word(x["w"]))
                if m == k:
                    parts.append(r"{\c" + ACTIVE + r"\fscx110\fscy110}" + word + r"{\c&HFFFFFF&\fscx100\fscy100}")
                elif key:
                    parts.append(r"{\c" + KEYCOL + "}" + word + r"{\c&HFFFFFF&}")
                else:
                    parts.append(word)
            pop = r"{\fad(40,0)}" if k == 0 else ""
            lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Cap,,0,0,0,,{pop}{' '.join(parts)}")
    hook = clip.get("hook", "").strip()
    if hook:
        hook_end = min(3.2, dur)
        txt = wrap_hook(re.sub(r"[{}\\]", "", hook).upper())
        lines.insert(0, f"Dialogue: 1,{ass_time(0)},{ass_time(hook_end)},Hook,,0,0,0,,"
                        r"{\fad(0,180)\t(0,120,\fscx104\fscy104)\t(120,220,\fscx100\fscy100)}" + txt)
    Path(path).write_text(head + "\n".join(lines) + "\n")
    return len(lines)


# =========================================================================== render
def norm_audio(src_wav, dst_wav, dur):
    m = loudnorm_measure(src_wav, 0.0, dur)
    stage1 = dst_wav.with_suffix(".stage1.wav")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src_wav), "-af",
         f"loudnorm=I={LUFS}:TP={TP}:LRA={LRA}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
         f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,"
         f"aresample=48000", "-ac", "2", "-c:a", "pcm_s24le", str(stage1)])
    fades = f"afade=t=in:st=0:d=0.04,afade=t=out:st={max(0, dur - 0.3):.3f}:d=0.3"
    gain = 0.0
    for _ in range(3):
        run(["ffmpeg", "-y", "-v", "error", "-i", str(stage1), "-af",
             f"volume={gain:.2f}dB,alimiter=limit={10 ** ((TP - 0.5) / 20):.4f}:level=false:attack=1:release=50,"
             f"aresample=192000,aresample=48000,{fades}", "-c:a", "pcm_s24le", str(dst_wav)])
        lv = measure_output(dst_wav)
        if lv["integrated_lufs"] is None or abs(lv["integrated_lufs"] - LUFS) <= 0.3:
            break
        gain += LUFS - lv["integrated_lufs"]
    stage1.unlink(missing_ok=True)


def render_clip(video, src, words, clip, out, work, denoise=True):
    idx = clip_words(words, clip["start"], clip["end"])
    if not idx:
        raise SystemExit(f"{out.name}: no words between {clip['start']} and {clip['end']}")
    spans, keep = build_segments(words, idx, clip.get("drop", []))
    dur = round(out_duration(spans), 3)
    if not MIN_LEN <= dur <= MAX_LEN:
        raise SystemExit(f"{out.name}: edited length {dur:.2f}s is outside {MIN_LEN:.0f}–{MAX_LEN:.0f}s; "
                         f"adjust start/end/drop in the plan")
    base = max(0.0, spans[0][0] - 1.0)
    rel = [(a - base, b - base) for a, b in spans]
    n = len(spans)
    fps = src["fps"]
    out_fps = 60 if fps > 45 else 30
    sw, sh = src["w"], src["h"]

    # ---- audio: concat kept spans, clean, normalise
    raw_wav = work / f"{out.stem}.raw.wav"
    norm_wav = work / f"{out.stem}.norm.wav"
    af = [f"[0:a]asplit={n}" + "".join(f"[as{k}]" for k in range(n)) if n > 1 else "[0:a]anull[as0]"]
    for k, (a, b) in enumerate(rel):
        d = b - a
        af.append(f"[as{k}]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:st=0:d=0.015,afade=t=out:st={max(0, d - 0.015):.3f}:d=0.015[a{k}]")
    af.append("".join(f"[a{k}]" for k in range(n)) + f"concat=n={n}:v=0:a=1"
              + (",highpass=f=70,afftdn=nr=10:nf=-45:tn=1" if denoise else "") + "[aout]")
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{base:.3f}", "-t", f"{rel[-1][1] + 0.5:.3f}", "-i", str(video),
         "-filter_complex", ";".join(af), "-map", "[aout]", "-ac", "2", "-ar", "48000", "-c:a", "pcm_s24le", str(raw_wav)])
    norm_audio(raw_wav, norm_wav, dur)

    # ---- framing per shot
    try:
        shots = track_shots(video, spans, sw, sh)
    except Exception as e:  # noqa: BLE001
        print(f"! face tracking failed ({e}); using blurred-fill framing", file=sys.stderr)
        shots = [(0.0, dur, None)]
    portrait = sw / sh <= 9 / 16 + 0.01
    cw = min(sw, round(sh * 9 / 16 / 2) * 2)
    crop_shots = [(a, b, int(min(max(fx * sw - cw / 2, 0), sw - cw))) for a, b, fx in shots if fx is not None]
    fill_needed = not portrait and len(crop_shots) < len(shots)

    # ---- zoom: alternate 1.00 / 1.07 per segment (masks jump cuts) + slow 4 % push-in within each
    zr, off = [], 0.0
    for k, (a, b) in enumerate(spans):
        d = b - a
        z0 = 1.0 if k % 2 == 0 else 1.07
        zr.append((off, off + d, f"({z0}+0.04*(t-{off:.3f})/{d:.3f})"))
        off += d
    zexpr = piecewise(zr, 1.0)

    vf = [f"[0:v]split={n}" + "".join(f"[vs{k}]" for k in range(n)) if n > 1 else "[0:v]null[vs0]"]
    for k, (a, b) in enumerate(rel):
        vf.append(f"[vs{k}]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{k}]")
    vf.append("".join(f"[v{k}]" for k in range(n)) + f"concat=n={n}:v=1:a=0,fps={out_fps},setsar=1[cat]")
    if portrait:
        vf.append(f"[cat]scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}[comp]")
    else:
        branches = (1 if crop_shots else 0) + (1 if fill_needed else 0)
        if branches == 2:
            vf.append("[cat]split[c1][c2]")
            cin, fin = "[c1]", "[c2]"
        else:
            cin = fin = "[cat]"
        if fill_needed:
            vf.append(f"{fin}split[fa][fb];"
                      f"[fa]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=28:3,"
                      f"eq=brightness=-0.10:saturation=0.9[bg];"
                      f"[fb]scale={W}:-2:flags=lanczos[fg];"
                      f"[bg][fg]overlay=(W-w)/2:(H-h)/2-110[fill]")
        if crop_shots:
            xexpr = piecewise([(a, b, x) for a, b, x in crop_shots], crop_shots[0][2])
            vf.append(f"{cin}crop=w={cw}:h={sh}:x='{xexpr}':y=0,scale={W}:{H}:flags=lanczos,"
                      f"unsharp=5:5:0.35:5:5:0.0[crop]")
        if crop_shots and fill_needed:
            en = "+".join(f"between(t,{a:.3f},{b - 1e-3:.3f})" for a, b, _ in crop_shots)
            vf.append(f"[fill][crop]overlay=0:0:enable='{en}'[comp]")
        elif crop_shots:
            vf.append("[crop]null[comp]")
        else:
            vf.append("[fill]null[comp]")
    ass = work / f"{out.stem}.ass"
    n_events = build_ass(words, keep, spans, clip, ass, dur)
    ass_esc = str(ass).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    vf.append(f"[comp]scale=w='trunc({W}*({zexpr})/2)*2':h='trunc({H}*({zexpr})/2)*2':eval=frame:flags=bicubic,"
              f"crop={W}:{H}:(iw-{W})/2:(ih-{H})*0.4,setsar=1,ass='{ass_esc}',"
              f"fade=t=out:st={max(0, dur - 0.3):.3f}:d=0.3,format=yuv420p[vout]")
    run(["ffmpeg", "-y", "-hide_banner", "-v", "warning", "-ss", f"{base:.3f}", "-t", f"{rel[-1][1] + 0.5:.3f}",
         "-i", str(video), "-i", str(norm_wav), "-filter_complex", ";".join(vf), "-map", "[vout]", "-map", "1:a",
         "-c:v", "libx264", "-profile:v", "high", "-level", "4.2", "-preset", "slow", "-crf", "17",
         "-g", str(out_fps * 2), "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-colorspace", "bt709", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2",
         "-movflags", "+faststart", "-t", f"{dur:.3f}", str(out)])
    for p in (raw_wav, norm_wav):
        p.unlink(missing_ok=True)
    text = apply_fixes(" ".join(words[k]["w"] for k in keep), clip.get("fixes"))
    return {"spans": spans, "duration_s": dur, "cuts": n - 1, "shots": [[round(a, 2), round(b, 2), fx] for a, b, fx in shots],
            "caption_events": n_events, "transcript": text, "fps": out_fps}


# =========================================================================== report + QC
def write_reports(plan, results, out_dir, title):
    (out_dir / "reels.json").write_text(json.dumps({"source": plan["source"], "title": title, "reels": results}, indent=2,
                                                   ensure_ascii=False))
    md = [f"# Reels from: {title or plan['source']}", "", f"Source: {plan['source']}", "",
          "| Rank | File | Source timestamps | Length | Viral score |", "|---|---|---|---|---|"]
    for r in results:
        md.append(f"| {r['rank']} | {r['file']} | {r['source_start']} – {r['source_end']} | {r['duration_s']:.1f}s | "
                  f"{r.get('score') or '–'}/10 |")
    for r in results:
        md += ["", f"## {r['rank']}. {r['file']} — {r.get('yt_title', '')}", "",
               f"- **Source timestamps:** {r['source_start']} – {r['source_end']} (edited length {r['duration_s']:.1f}s, "
               f"{r['cuts']} pause cut(s))",
               f"- **Viral potential:** {r.get('score') or '–'}/10",
               f"- **Why it works:** {r.get('why', '')}",
               f"- **On-screen hook:** {r.get('hook', '')}",
               f"- **YouTube Shorts title:** {r.get('yt_title', '')}",
               f"- **Hashtags:** {' '.join(r.get('hashtags', []))}", "",
               "**Instagram caption:**", "", r.get("ig_caption", ""), "",
               "<details><summary>Transcript</summary>", "", r["transcript"], "", "</details>"]
    (out_dir / "REELS.md").write_text("\n".join(md) + "\n")


def cmd_render(args):
    plan_path = Path(args.plan)
    plan = json.loads(plan_path.read_text())
    work = Path(args.work); work.mkdir(parents=True, exist_ok=True)
    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)
    clips = plan["clips"]
    if len(clips) > MAX_CLIPS:
        raise SystemExit(f"Plan has {len(clips)} clips; the maximum is {MAX_CLIPS}.")
    if len(clips) < MIN_CLIPS:
        print(f"! Plan has only {len(clips)} clips (< {MIN_CLIPS}); rendering them anyway.", file=sys.stderr)
    video, meta = get_source(plan["source"], work, args.cookies)
    src = probe(video)
    words = transcribe(video, work, args.model, plan.get("language"))
    only = {int(x) for x in args.only.split(",")} if args.only else None
    results = []
    if only and (out_dir / "reels.json").exists():       # partial re-render: keep the other reels
        results = [r for r in json.loads((out_dir / "reels.json").read_text())["reels"] if r["rank"] not in only]
    else:
        for old in out_dir.glob("Reel_*.mp4"):
            old.unlink()
    for rank, clip in enumerate(clips, 1):
        out = out_dir / f"Reel_{rank:02d}.mp4"
        if only and rank not in only:
            continue
        print(f"\n=== {out.name}: {fmt_ts(clip['start'])} – {fmt_ts(clip['end'])}", file=sys.stderr)
        r = render_clip(video, src, words, clip, out, work, denoise=not args.no_denoise)
        results.append({"rank": rank, "file": out.name, "source_start": fmt_ts(r["spans"][0][0]),
                        "source_end": fmt_ts(r["spans"][-1][1]), "source_start_s": r["spans"][0][0],
                        "source_end_s": r["spans"][-1][1], **{k: clip.get(k) for k in
                        ("score", "why", "hook", "ig_caption", "yt_title", "hashtags", "keywords")}, **r})
    results.sort(key=lambda r: r["rank"])
    write_reports(plan, results, out_dir, meta.get("title"))
    print(f"\nWrote {len(results)} reels to {out_dir}/", file=sys.stderr)


def ffjson(path):
    return json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format",
                                      str(path)], capture_output=True, text=True, check=True).stdout)


def cmd_qc(args):
    out_dir = Path(args.out)
    rep = json.loads((out_dir / "reels.json").read_text())
    qc_dir = out_dir / "qc"; qc_dir.mkdir(exist_ok=True)
    fails, rows, hashes = [], [], {}
    reels = rep["reels"]
    for r in reels:
        f = out_dir / r["file"]
        problems = []
        if not f.exists():
            fails.append(f"{r['file']}: missing"); continue
        info = ffjson(f)
        v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
        a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
        dur = float(info["format"]["duration"])
        if not v or v["codec_name"] != "h264" or (v["width"], v["height"]) != (W, H):
            problems.append(f"video stream {v and (v['codec_name'], v['width'], v['height'])}")
        if v and v.get("pix_fmt") != "yuv420p":
            problems.append(f"pix_fmt {v.get('pix_fmt')}")
        if v and v.get("sample_aspect_ratio", "1:1") not in ("1:1", "0:1"):
            problems.append(f"SAR {v.get('sample_aspect_ratio')}")
        if not a or a["codec_name"] != "aac":
            problems.append("audio not AAC")
        if not MIN_LEN <= dur <= MAX_LEN + 0.1:
            problems.append(f"duration {dur:.2f}s")
        dec = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-f", "null", "-"], capture_output=True, text=True)
        if dec.returncode or dec.stderr.strip():
            problems.append("decode errors: " + dec.stderr.strip()[:200])
        loud = measure_output(f)
        if loud["integrated_lufs"] is None or abs(loud["integrated_lufs"] - LUFS) > 1.0:
            problems.append(f"loudness {loud['integrated_lufs']}")
        if loud["true_peak_dbfs"] is not None and loud["true_peak_dbfs"] > TP + 0.5:
            problems.append(f"true peak {loud['true_peak_dbfs']}")
        if r.get("caption_events", 0) < 5:
            problems.append("captions missing")
        first_word = to_out_time(r["spans"], r["spans"][0][0] + PAD_IN)
        if first_word > 0.5:
            problems.append(f"first word at {first_word:.2f}s")
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        if h in hashes:
            problems.append(f"identical to {hashes[h]}")
        hashes[h] = r["file"]
        # contact sheet: 6 frames across the clip
        sheet = qc_dir / f"{f.stem}.jpg"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(f), "-vf",
                        f"fps=6/{dur:.3f},scale=360:-2,tile=6x1:padding=6:color=white", "-frames:v", "1", str(sheet)],
                       check=False)
        rows.append({"file": r["file"], "duration_s": round(dur, 2), "w": v and v["width"], "h": v and v["height"],
                     "codec": v and v["codec_name"], "fps": v and v["avg_frame_rate"], "lufs": loud["integrated_lufs"],
                     "true_peak": loud["true_peak_dbfs"], "size_mb": round(f.stat().st_size / 1e6, 1),
                     "ok": not problems, "problems": problems})
        fails += [f"{r['file']}: {p}" for p in problems]
    # overlap between source ranges = duplicated content
    for x in range(len(reels)):
        for y in range(x + 1, len(reels)):
            a, b = reels[x], reels[y]
            ov = min(a["source_end_s"], b["source_end_s"]) - max(a["source_start_s"], b["source_start_s"])
            if ov > 0:
                fails.append(f"{a['file']} and {b['file']} overlap by {ov:.1f}s of source")
    if not MIN_CLIPS <= len(reels) <= MAX_CLIPS:
        fails.append(f"{len(reels)} reels (expected {MIN_CLIPS}–{MAX_CLIPS})")
    (out_dir / "qc.json").write_text(json.dumps({"reels": rows, "failures": fails}, indent=2))
    for r in rows:
        print(f"{'OK  ' if r['ok'] else 'FAIL'} {r['file']}  {r['duration_s']:5.1f}s  {r['w']}x{r['h']} {r['codec']} "
              f"{r['fps']}  {r['lufs']} LUFS  TP {r['true_peak']}  {r['size_mb']} MB  {'; '.join(r['problems'])}")
    print("\nQC " + ("PASSED" if not fails else "FAILED:\n  " + "\n  ".join(fails)))
    return not fails


def cmd_analyze(args):
    work = Path(args.work); work.mkdir(parents=True, exist_ok=True)
    video, meta = get_source(args.source, work, args.cookies)
    src = probe(video)
    if not src["has_audio"]:
        raise SystemExit("Source has no audio track.")
    words = transcribe(video, work, args.model, args.language)
    if not words:
        raise SystemExit("No speech detected.")
    write_transcript(words, work / "transcript.txt")
    energy = energy_curve(video, work)
    cands = auto_candidates(words, energy, meta.get("heatmap"), src["duration"])
    (work / "candidates.json").write_text(json.dumps(cands[:60], indent=2, ensure_ascii=False))
    picked = pick_non_overlapping(cands)
    lang = args.language or ((work / "language.txt").read_text().strip() if (work / "language.txt").exists() else None)
    plan = draft_plan(args.source, picked, lang)
    plan_path = work / "plan.json"
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
    print(f"\nSource: {meta.get('title') or args.source}  ({src['w']}x{src['h']} @ {src['fps']:.2f} fps, "
          f"{src['duration'] / 60:.1f} min, {len(words)} words)")
    print(f"Transcript: {work / 'transcript.txt'}\nDraft plan ({len(picked)} clips): {plan_path}")
    if len(picked) < MIN_CLIPS:
        print(f"! Only {len(picked)} clean 25–50 s moments found — fewer than {MIN_CLIPS}.")
    for k, c in enumerate(picked, 1):
        print(f"  {k}. {fmt_ts(c['start'])}–{fmt_ts(c['end'])} ({c['out_duration']:.1f}s) score {c['score']:.2f}: "
              f"{c['text'][:90]}…")
    return plan_path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--work", default="work")
    common.add_argument("--out", default="out")
    common.add_argument("--cookies", help="Netscape cookies.txt for yt-dlp (if YouTube demands sign-in)")
    common.add_argument("--model", default="medium", help="faster-whisper model (small/medium/large-v3)")
    a = sub.add_parser("analyze", parents=[common]); a.add_argument("source"); a.add_argument("--language")
    r = sub.add_parser("render", parents=[common]); r.add_argument("plan")
    r.add_argument("--only", help="comma-separated ranks to re-render, e.g. 2,5")
    r.add_argument("--no-denoise", action="store_true")
    sub.add_parser("qc", parents=[common])
    u = sub.add_parser("auto", parents=[common]); u.add_argument("source"); u.add_argument("--language")
    u.add_argument("--no-denoise", action="store_true")
    args = ap.parse_args()
    if args.cmd == "analyze":
        cmd_analyze(args)
    elif args.cmd == "render":
        cmd_render(args)
    elif args.cmd == "qc":
        sys.exit(0 if cmd_qc(args) else 1)
    elif args.cmd == "auto":
        args.plan, args.only = str(cmd_analyze(args)), None
        cmd_render(args)
        sys.exit(0 if cmd_qc(args) else 1)


if __name__ == "__main__":
    main()
