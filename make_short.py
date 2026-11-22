#!/usr/bin/env python3
"""Turn a 15-second window of a 16:9 source video into a 9:16 Reels/Shorts clip.

Pipeline
  1. Transcribe a padded window around the requested cut with faster-whisper
     (word timestamps) and snap the cut-in / cut-out to silent gaps between
     words, keeping the length at 15 s +/- 1 s.
  2. Find the speaker's face (OpenCV) and crop a 9:16 column around it.
  3. Ease in a ~12% punch-in just before the hook (the loudest moment of the
     clip, usually the laugh after the punchline) or at --hook.
  4. Burn in word-synced captions (bold white, black outline, the active word in
     yellow) inside the Reels/Shorts centre-safe zone.
  5. Two-pass EBU R128 loudness normalisation to -14 LUFS / -1 dBTP.
  6. 0.2 s audio and video fades at both ends.
  7. Encode 1080x1920 H.264 High / AAC-LC 48 kHz MP4 at the source frame rate,
     with +faststart.

Usage
  python3 make_short.py --source source.mp4 --start 2602.0 --end 2617.0 \
      --out short.mp4 [--source-offset 2597] [--lang hi] [--hook 2614.5]

--start/--end are times in the ORIGINAL YouTube video. If the source file is a
section that was cut out of it (see fetch_source.sh), pass --source-offset with
the original-video time at which that file begins.
"""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

OUT_W, OUT_H = 1080, 1920
TARGET_LEN, LEN_TOL = 15.0, 1.0
FADE = 0.2
# Safe zone for Reels/Shorts UI: avoid the top ~14%, the bottom ~25% (caption,
# handle, audio row) and ~120 px on the right (like/comment/share rail).
CAPTION_Y = 1180          # vertical centre of the caption block
CAPTION_MARGIN_LR = 130


def run(cmd, capture=False):
    print("+", " ".join(str(c) for c in cmd), file=sys.stderr)
    r = subprocess.run(cmd, check=True, text=True,
                       stdout=subprocess.PIPE if capture else None,
                       stderr=subprocess.PIPE if capture else None)
    return r


def probe(path):
    out = run(["ffprobe", "-v", "error", "-show_streams", "-show_format",
               "-of", "json", path], capture=True).stdout
    info = json.loads(out)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    num, den = (int(x) for x in v["avg_frame_rate"].split("/"))
    return {"w": int(v["width"]), "h": int(v["height"]), "fps": num / den,
            "fps_str": v["avg_frame_rate"],
            "duration": float(info["format"]["duration"])}


# --------------------------------------------------------------------------- #
# 1. transcription + clean cut points
# --------------------------------------------------------------------------- #
def transcribe(src, t0, t1, lang, model_name, tmp):
    import numpy as np
    raw = os.path.join(tmp, "window.f32")
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}",
         "-i", src, "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", raw])
    audio = np.fromfile(raw, dtype=np.float32)   # decoded by ffmpeg, not PyAV
    from faster_whisper import WhisperModel
    model = WhisperModel(model_name, device="auto", compute_type="auto")
    segs, _ = model.transcribe(audio, language=lang, word_timestamps=True,
                               vad_filter=False, beam_size=5,
                               condition_on_previous_text=False)
    words = []
    for s in segs:
        for w in s.words or []:
            text = w.word.strip()
            if text:
                words.append({"start": t0 + w.start, "end": t0 + w.end, "text": text})
    return words


def snap_cuts(words, start, end, lo, hi):
    """Choose cut points inside silent gaps, closest to the requested ones."""
    if not words:
        return start, end
    # candidate cut time -> length of the silent gap it sits in
    gaps = {lo: 0.5, hi: 0.5}
    for a, b in zip(words, words[1:]):
        g = b["start"] - a["end"]
        if g >= 0.12:
            gaps[(a["end"] + b["start"]) / 2] = g
    gaps[max(lo, words[0]["start"] - 0.15)] = 0.5
    gaps[min(hi, words[-1]["end"] + 0.15)] = 0.5

    def inside_word(t):
        return any(w["start"] + 0.02 < t < w["end"] - 0.02 for w in words)

    def pause_penalty(g):
        # cutting at a real pause (phrase boundary) beats a short breath
        return 0.0 if g >= 0.35 else 1.0 - g / 0.35

    cands = sorted(c for c in gaps if lo <= c <= hi and not inside_word(c))
    best = None
    for a in cands:
        for b in cands:
            d = b - a
            if abs(d - TARGET_LEN) > LEN_TOL:
                continue
            cost = (abs(a - start) + abs(b - end) + 0.5 * abs(d - TARGET_LEN)
                    + 1.5 * pause_penalty(gaps[a]) + 0.75 * pause_penalty(gaps[b]))
            if best is None or cost < best[0]:
                best = (cost, a, b)
    if best is None:
        print("! no clean word-gap pair within 15+/-1 s; using requested times",
              file=sys.stderr)
        return start, end
    return best[1], best[2]


# --------------------------------------------------------------------------- #
# 2. face-centred 9:16 crop
# --------------------------------------------------------------------------- #
def face_center_x(src, a, b, w):
    try:
        import cv2
        import numpy as np
    except ImportError:
        return 0.5
    if not hasattr(cv2, "CascadeClassifier"):
        print("! OpenCV build has no Haar cascades (need opencv<5); centre crop", file=sys.stderr)
        return 0.5
    casc = cv2.CascadeClassifier(cv2.data.haarcascades +
                                 "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(src)
    xs = []
    for i in range(16):
        cap.set(cv2.CAP_PROP_POS_MSEC, (a + (b - a) * (i + 0.5) / 16) * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        scale = 640 / frame.shape[1]
        small = cv2.resize(frame, None, fx=scale, fy=scale)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        faces = casc.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
        if len(faces):
            fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
            xs.append((fx + fw / 2) / small.shape[1])
    cap.release()
    if not xs:
        print("! no face found; using centre crop", file=sys.stderr)
        return 0.5
    return float(np.median(xs))


# --------------------------------------------------------------------------- #
# 3. hook = loudest second (laugh / applause right after the punchline)
# --------------------------------------------------------------------------- #
def loudest_moment(src, a, b, tmp):
    import numpy as np
    raw = os.path.join(tmp, "mono.f32")
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}",
         "-i", src, "-vn", "-ac", "1", "-ar", "8000", "-f", "f32le", raw])
    x = np.fromfile(raw, dtype=np.float32)
    if len(x) < 8000:
        return None
    win = 8000
    e = np.convolve(x * x, np.ones(win) / win, mode="valid")
    # ignore the first 40% so the punch-in lands in the payoff half
    skip = int(len(e) * 0.4)
    i = skip + int(np.argmax(e[skip:]))
    return i / 8000.0          # seconds from clip start


# --------------------------------------------------------------------------- #
# 4. captions (ASS)
# --------------------------------------------------------------------------- #
def ass_time(t):
    t = max(0.0, t)
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def ass_escape(s):
    return s.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def build_ass(words, a, b, font, path):
    words = [dict(w, start=w["start"] - a, end=w["end"] - a) for w in words
             if w["end"] > a and w["start"] < b]
    dur = b - a
    chunks, cur = [], []
    for w in words:
        if cur and (len(cur) >= 3 or w["start"] - cur[-1]["end"] > 0.35 or
                    sum(len(x["text"]) for x in cur) + len(w["text"]) > 18 or
                    re.search(r"[.?!,।]$", cur[-1]["text"])):
            chunks.append(cur)
            cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)

    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {OUT_W}
PlayResY: {OUT_H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,7,3,5,{CAPTION_MARGIN_LR},{CAPTION_MARGIN_LR},0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for ci, ch in enumerate(chunks):
        ch_end = min(ch[-1]["end"] + 0.25,
                     chunks[ci + 1][0]["start"] if ci + 1 < len(chunks) else dur)
        for wi, w in enumerate(ch):
            s = w["start"] if wi else max(0.0, w["start"] - 0.05)
            e = ch[wi + 1]["start"] if wi + 1 < len(ch) else ch_end
            if e <= s:
                continue
            parts = []
            for k, x in enumerate(ch):
                t = ass_escape(x["text"]).upper() if x["text"].isascii() else ass_escape(x["text"])
                parts.append("{\\c&H0000E5FF&}" + t + "{\\c&H00FFFFFF&}" if k == wi else t)
            pop = "{\\fscx88\\fscy88\\t(0,90,\\fscx100\\fscy100)}" if wi == 0 else ""
            text = f"{{\\an5\\pos({OUT_W // 2},{CAPTION_Y})}}{pop}" + " ".join(parts)
            lines.append(f"Dialogue: 0,{ass_time(s)},{ass_time(min(e, dur))},Cap,,0,0,0,,{text}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + "\n".join(lines) + "\n")
    return len(lines)


# --------------------------------------------------------------------------- #
# 5. loudness
# --------------------------------------------------------------------------- #
def loudnorm_measure(src, a, dur):
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-ss", f"{a:.3f}", "-t", f"{dur:.3f}",
             "-i", src, "-vn", "-af",
             "loudnorm=I=-14:TP=-1.0:LRA=11:print_format=json", "-f", "null", "-"],
            capture=True)
    j = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
    return j


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", required=True)
    p.add_argument("--start", type=float, required=True, help="original-video seconds")
    p.add_argument("--end", type=float, required=True, help="original-video seconds")
    p.add_argument("--source-offset", type=float, default=0.0,
                   help="original-video time at which --source begins")
    p.add_argument("--out", default="short.mp4")
    p.add_argument("--lang", default="hi")
    p.add_argument("--model", default="large-v3")
    p.add_argument("--font", default="Noto Sans Devanagari",
                   help="bold font with Devanagari + Latin (apt: fonts-noto-core)")
    p.add_argument("--hook", type=float, help="original-video time of the punch-in")
    p.add_argument("--zoom", type=float, default=1.12)
    p.add_argument("--crop-x", type=float, help="0..1 horizontal crop centre (default: face)")
    p.add_argument("--words-json", help="skip Whisper; use [{start,end,text}] in original-video seconds")
    p.add_argument("--no-snap", action="store_true")
    p.add_argument("--keep-temp", action="store_true")
    args = p.parse_args()

    off = args.source_offset
    src = args.source
    info = probe(src)
    tmp = tempfile.mkdtemp(prefix="short_")
    try:
        # --- words & cut points (all in source-file seconds) ---
        s_req, e_req = args.start - off, args.end - off
        lo = max(0.0, s_req - 2.0)
        hi = min(info["duration"], e_req + 2.0)
        if args.words_json:
            words = [dict(w, start=w["start"] - off, end=w["end"] - off)
                     for w in json.load(open(args.words_json, encoding="utf-8"))]
        else:
            words = transcribe(src, lo, hi, args.lang, args.model, tmp)
        a, b = (s_req, e_req) if args.no_snap else snap_cuts(words, s_req, e_req, lo, hi)
        # snap to whole frames
        fps = info["fps"]
        a = round(a * fps) / fps
        nframes = int(round((b - a) * fps))
        dur = nframes / fps
        b = a + dur
        print(f"cut: {a + off:.3f} -> {b + off:.3f}  ({dur:.3f} s, {nframes} frames)",
              file=sys.stderr)

        # --- crop ---
        cx = args.crop_x if args.crop_x is not None else face_center_x(src, a, b, info["w"])
        crop_w = int(info["h"] * 9 / 16) // 2 * 2
        crop_w = min(crop_w, info["w"] // 2 * 2)
        crop_x = int(min(max(cx * info["w"] - crop_w / 2, 0), info["w"] - crop_w))

        # --- hook / punch-in ---
        if args.hook is not None:
            hook = args.hook - off - a
        else:
            peak = loudest_moment(src, a, b, tmp)
            hook = (peak - 1.0) if peak is not None else dur * 0.6
        hook = min(max(hook, 0.5), dur - 1.5)
        ramp = 0.35
        z = (f"if(lt(it,{hook:.3f}),1,"
             f"1+{args.zoom - 1:.4f}*(3*pow(min((it-{hook:.3f})/{ramp},1),2)"
             f"-2*pow(min((it-{hook:.3f})/{ramp},1),3)))")

        # --- captions ---
        ass = os.path.join(tmp, "captions.ass")
        n_events = build_ass(words, a, b, args.font, ass)
        if not n_events:
            print("! no words transcribed in the cut; captions will be empty", file=sys.stderr)

        # --- loudness pass 1 ---
        m = loudnorm_measure(src, a, dur)
        af = (f"loudnorm=I=-14:TP=-1.0:LRA=11:measured_I={m['input_i']}:"
              f"measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
              f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:"
              f"linear=true,aresample=48000,"
              f"afade=t=in:st=0:d={FADE},afade=t=out:st={dur - FADE:.3f}:d={FADE},"
              f"apad,atrim=0:{dur:.3f}")

        ass_esc = ass.replace("\\", "/").replace(":", "\\:")
        vf = (f"crop={crop_w}:{info['h']}:{crop_x}:0,"
              f"scale={OUT_W * 2}:{OUT_H * 2}:flags=lanczos,setsar=1,"
              f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
              f"d=1:s={OUT_W}x{OUT_H}:fps={info['fps_str']},"
              f"ass='{ass_esc}':shaping=complex,"
              f"fade=t=in:st=0:d={FADE},fade=t=out:st={dur - FADE:.3f}:d={FADE},"
              f"format=yuv420p")

        run(["ffmpeg", "-y", "-hide_banner", "-ss", f"{a:.3f}", "-t", f"{dur:.3f}",
             "-i", src, "-map", "0:v:0", "-map", "0:a:0", "-vf", vf, "-af", af,
             "-r", info["fps_str"], "-frames:v", str(nframes),
             "-c:v", "libx264", "-profile:v", "high", "-level:v", "4.2",
             "-preset", "slow", "-crf", "17", "-maxrate", "16M", "-bufsize", "32M",
             "-g", str(int(round(fps * 2))), "-pix_fmt", "yuv420p",
             "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
             "-movflags", "+faststart", "-shortest", args.out])

        report = {
            "source_video_start_s": round(a + off, 3),
            "source_video_end_s": round(b + off, 3),
            "source_video_start": fmt_ts(a + off),
            "source_video_end": fmt_ts(b + off),
            "duration_s": round(dur, 3),
            "frames": nframes,
            "fps": info["fps_str"],
            "crop": {"x": crop_x, "w": crop_w, "h": info["h"], "face_center": round(cx, 3)},
            "punch_in_at_clip_s": round(hook, 3),
            "caption_events": n_events,
            "transcript": " ".join(w["text"] for w in words
                                   if w["end"] > a and w["start"] < b),
        }
        with open(os.path.splitext(args.out)[0] + ".json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        if args.keep_temp:
            shutil.copy(ass, os.path.splitext(args.out)[0] + ".ass")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        if not args.keep_temp:
            shutil.rmtree(tmp, ignore_errors=True)


def fmt_ts(t):
    h = int(t // 3600)
    m = int(t // 60 % 60)
    s = t - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


if __name__ == "__main__":
    main()
