#!/usr/bin/env python3
"""
make_short.py — turn a long video into a single 15-second vertical Short/Reel.

Pipeline
  1. Fetch    : download source via yt-dlp (or use a local file), keeping source fps.
  2. Transcribe: faster-whisper with word-level timestamps.
  3. Select   : score every sentence-aligned 14–16 s window for hook strength
                (YouTube "Most replayed" heatmap if available, vocal energy peaks,
                hook language, standalone-sentence start, speech density) and pick
                the best. Cut points snap to silences between words.
  4. Render   : 9:16 1080x1920, face-aware crop (or blurred-fill for wide shots),
                smooth punch-in on the hook peak, burned-in word-highlight captions
                in the safe zone, two-pass loudnorm to -14 LUFS / -1 dBTP,
                0.2 s audio+video fades, H.264 High + AAC, +faststart.
  5. Report   : writes <out>.json with exact source timestamps and metrics.

Usage
  python3 make_short.py "https://www.youtube.com/watch?v=CswOUBuokjo" -o out/short.mp4
  python3 make_short.py source.mp4 -o out/short.mp4            # local file
  python3 make_short.py URL --cookies cookies.txt                # if YouTube asks for sign-in
  python3 make_short.py URL --start 123.4                        # force a start time
"""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

TARGET = 15.0          # seconds
TOL = 1.0              # ± tolerance allowed by the spec
W, H = 1080, 1920
FADE = 0.2
LUFS, TP, LRA = -14.0, -1.0, 11.0

# Reels/Shorts UI-safe zone on a 1080x1920 canvas (conservative union of both apps):
# top 250 px (header), bottom 480 px (caption/handle/music), right 140 px (buttons).
SAFE_TOP, SAFE_BOTTOM, SAFE_LEFT, SAFE_RIGHT = 250, 480, 90, 140


def run(cmd, **kw):
    print("+", " ".join(str(c) for c in cmd), file=sys.stderr)
    return subprocess.run(cmd, check=True, **kw)


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
        check=True, capture_output=True, text=True).stdout
    info = json.loads(out)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    num, den = map(int, v.get("avg_frame_rate", "30/1").split("/"))
    fps = num / den if den else 30.0
    return {"w": int(v["width"]), "h": int(v["height"]), "fps": fps,
            "duration": float(info["format"]["duration"]),
            "has_audio": any(s["codec_type"] == "audio" for s in info["streams"])}


# --------------------------------------------------------------------------- 1. fetch
def fetch(src, work, cookies=None):
    if os.path.exists(src):
        return Path(src), {}
    meta_path = work / "meta.json"
    base = ["yt-dlp", "--no-playlist", "--js-runtimes", "node"]
    if cookies:
        base += ["--cookies", cookies]
    out_tmpl = str(work / "source.%(ext)s")
    run(base + ["-f", "bv*[height<=2160][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=2160]+ba/b",
                "--merge-output-format", "mp4", "--write-info-json", "-o", out_tmpl, src])
    info_json = next(work.glob("source*.info.json"))
    meta = json.loads(info_json.read_text())
    small = {k: meta.get(k) for k in ("id", "title", "duration", "fps", "width", "height", "heatmap", "channel")}
    meta_path.write_text(json.dumps(small, indent=2))
    return next(p for p in work.glob("source.*") if p.suffix in (".mp4", ".mkv", ".webm")), small


# --------------------------------------------------------------------------- 2. transcribe
def transcribe(video, work, model_size):
    cache = work / f"words_{model_size}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")   # plain HTTPS download; works behind strict proxies
    from faster_whisper import WhisperModel
    import numpy as np
    # Decode with ffmpeg ourselves (avoids PyAV version mismatches), 16 kHz mono float32.
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         check=True, capture_output=True).stdout
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segs, _ = model.transcribe(audio, word_timestamps=True, vad_filter=True, beam_size=5)
    words = []
    for s in segs:
        for w in s.words or []:
            words.append({"t0": round(w.start, 3), "t1": round(w.end, 3), "w": w.word.strip(), "p": round(w.probability, 3)})
    cache.write_text(json.dumps(words))
    return words


# --------------------------------------------------------------------------- 3. select
def energy_curve(video, work, hop=0.1):
    """Short-term RMS loudness (dB) every `hop` seconds, via ffmpeg astats."""
    cache = work / "energy.json"
    if cache.exists():
        return json.loads(cache.read_text())
    sr = 8000
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-ac", "1", "-ar", str(sr),
                          "-f", "s16le", "-"], check=True, capture_output=True).stdout
    import array
    a = array.array("h", raw)
    n = int(sr * hop)
    curve = []
    for i in range(0, len(a) - n, n):
        chunk = a[i:i + n]
        rms = math.sqrt(sum(x * x for x in chunk) / n) or 1e-9
        curve.append(20 * math.log10(rms / 32768))
    cache.write_text(json.dumps(curve))
    return curve


HOOK_PATTERNS = [
    r"\b(never|always|nobody|everyone|secret|truth|actually|real reason|mistake|wrong|crazy|insane|biggest|worst|best)\b",
    r"\b(here'?s (the|what|why)|the (thing|key|trick) is|what (nobody|no one)|turns out|the reason)\b",
    r"\b(you|your)\b",
    r"\b\d+(\.\d+)?\s?(%|percent|million|billion|thousand|x|times|years|days)\b",
    r"[?!]",
]
WEAK_STARTS = {"and", "but", "so", "because", "or", "which", "that", "then", "also", "um", "uh", "like"}
SENT_END = re.compile(r"[.?!…]$")
TAIL_WEAK = (r"\b(so,? anyway|anyway|let'?s (talk|move|get|look)|moving on|next up|before we|"
             r"(don'?t forget to )?(like|subscribe)|thanks for watching|see you|um+|uh+)\b")


def heat_at(heatmap, t0, t1):
    if not heatmap:
        return 0.0
    vals = [h["value"] for h in heatmap if h["end_time"] > t0 and h["start_time"] < t1]
    return max(vals) if vals else 0.0


def candidate_windows(words):
    """Yield (start_word_idx, end_word_idx, t_in, t_out) with clean cut points.

    A window always starts at a sentence start and ends at a sentence end / breath. Its length may be
    brought into the 14–16 s range by including the natural silence (room tone) around it — never by
    cutting into a neighbouring word."""
    n = len(words)
    for i in range(n):
        # Cut in only at a sentence start (previous word ended a sentence or a ≥0.35 s pause).
        if i > 0 and not (SENT_END.search(words[i - 1]["w"]) or words[i]["t0"] - words[i - 1]["t1"] >= 0.35):
            continue
        gap_before = words[i]["t0"] - (words[i - 1]["t1"] if i else 0.0)
        room_before = min(1.0, max(0.0, gap_before - 0.08))
        for j in range(i, n):
            core = words[j]["t1"] - words[i]["t0"]
            if core > TARGET + TOL - 0.1:
                break
            gap_after = (words[j + 1]["t0"] if j + 1 < n else words[j]["t1"] + 1.5) - words[j]["t1"]
            # Cut out only at a sentence end or a clear breath (no mid-word / mid-phrase cuts).
            if not (SENT_END.search(words[j]["w"]) or gap_after >= 0.3):
                continue
            room_after = min(1.2, max(0.0, gap_after - 0.08))
            if core + room_before + room_after < TARGET - TOL:
                continue
            pre = min(0.12, room_before)
            post = min(0.2, room_after)
            short = TARGET - (core + pre + post)
            if short > 0:                       # pad with silence: tail first (lets the line land), then head
                add = min(short, room_after - post); post += add; short -= add
                add = min(short, room_before - pre); pre += add
            t_in = max(0.0, words[i]["t0"] - pre)
            t_out = words[j]["t1"] + post
            yield i, j, round(t_in, 3), round(t_out, 3)


def score_window(words, i, j, t_in, t_out, energy, heatmap, hop=0.1):
    text = " ".join(w["w"] for w in words[i:j + 1])
    lower = text.lower()
    seg = energy[int(t_in / hop):int(t_out / hop)] or [-60]
    voiced = [e for e in seg if e > -45] or seg
    mean_db = sum(voiced) / len(voiced)
    peak_db = max(seg)
    dyn = peak_db - mean_db                      # emotional emphasis / laugh / raised voice
    g_voiced = [e for e in energy if e > -45] or energy
    global_mean = sum(g_voiced) / len(g_voiced)
    loud = mean_db - global_mean                 # more animated than the rest of the video
    hook = sum(len(re.findall(p, lower)) for p in HOOK_PATTERNS)
    # The first ~3 s must carry the hook on their own.
    first3 = " ".join(w["w"] for w in words[i:j + 1] if w["t0"] < t_in + 3.0).lower()
    early_hook = sum(len(re.findall(p, first3)) for p in HOOK_PATTERNS)
    first = re.sub(r"[^a-z']", "", words[i]["w"].lower())
    weak_start = first in WEAK_STARTS
    wps = (j - i + 1) / (t_out - t_in)           # speech density
    conf = sum(w["p"] for w in words[i:j + 1]) / (j - i + 1)
    ends_clean = bool(SENT_END.search(words[j]["w"]))
    # The last ~3.5 s should land the payoff, not drift into a segue or filler.
    tail = " ".join(w["w"] for w in words[i:j + 1] if w["t1"] > t_out - 3.5).lower()
    tail_weak = len(re.findall(TAIL_WEAK, tail))
    heat = heat_at(heatmap, t_in, t_out)
    s = (3.0 * heat
         + 0.08 * dyn + 0.10 * loud
         + 0.35 * min(hook, 6) + 0.6 * min(early_hook, 3)
         + (-1.5 if early_hook == 0 else 0.0)    # no hook in the first 3 s → viewers swipe
         + (0.0 if not weak_start else -1.2)
         + (0.5 if ends_clean else 0.0)
         - 0.6 * abs(wps - 2.7)                  # natural, punchy pace
         + 1.0 * (conf - 0.8)
         - 1.5 * min(tail_weak, 2)
         - 0.4 * abs((t_out - t_in) - TARGET))
    return s, {"text": text, "heat": round(heat, 3), "dyn_db": round(dyn, 2), "loud_vs_avg_db": round(loud, 2),
               "hook_hits": hook, "early_hook_hits": early_hook, "weak_start": weak_start,
               "words_per_sec": round(wps, 2), "weak_tail_hits": tail_weak, "asr_conf": round(conf, 3), "ends_on_sentence": ends_clean}


def select(words, energy, heatmap, duration, force_start=None):
    best = None
    for i, j, t_in, t_out in candidate_windows(words):
        if t_out > duration:
            continue
        if force_start is not None and abs(t_in - force_start) > 1.5:
            continue
        s, d = score_window(words, i, j, t_in, t_out, energy, heatmap)
        if best is None or s > best[0]:
            best = (s, i, j, t_in, t_out, d)
    if best is None:
        raise SystemExit("No clean 14–16 s sentence-aligned window found.")
    return best


def hook_peak(words, i, j, energy, t_in, t_out, hop=0.1):
    """Time (relative to clip) of the loudest stressed word — where the punch-in lands."""
    best_t, best_e = None, -1e9
    for w in words[i:j + 1]:
        if w["t0"] < t_in + 1.0:      # let the opening breathe; punch in on the payoff
            continue
        e = max(energy[int(w["t0"] / hop):int(w["t1"] / hop) + 1] or [-90])
        bonus = 3.0 if re.search(HOOK_PATTERNS[0], w["w"].lower()) else 0.0
        if e + bonus > best_e:
            best_e, best_t = e + bonus, w["t0"]
    return (best_t if best_t is not None else t_in + 0.4 * (t_out - t_in)) - t_in


# --------------------------------------------------------------------------- 4. render
def face_crop_x(video, t_in, t_out, src_w, src_h):
    """Median horizontal face center across the clip, or None if no stable face."""
    try:
        import cv2
        cv2.CascadeClassifier  # removed in OpenCV 5 — pin opencv-python-headless<5
    except (ImportError, AttributeError):
        print("! OpenCV face detector unavailable; using centre/blur-fill framing", file=sys.stderr)
        return None
    cap = cv2.VideoCapture(str(video))
    det = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    xs = []
    t = t_in
    while t < t_out:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        t += 1.0
        if not ok:
            continue
        if frame.shape[1] > 960:        # detect on a small copy: 4K frames are far too slow
            frame = cv2.resize(frame, (960, round(960 * frame.shape[0] / frame.shape[1])))
        g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        fh, fw = g.shape[:2]
        faces = det.detectMultiScale(g, 1.1, 5, minSize=(fh // 16, fh // 16))
        if len(faces):
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            xs.append((x + w / 2) / fw)
    cap.release()
    if len(xs) < 4:
        return None
    xs.sort()
    spread = xs[int(len(xs) * 0.9)] - xs[int(len(xs) * 0.1)]
    crop_frac = (src_h * 9 / 16) / src_w
    if spread > crop_frac * 0.6:      # subject jumps around (two-shot etc.) → don't hard-crop
        return None
    return xs[len(xs) // 2]


def ass_time(t):
    t = max(0.0, t)
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_ass(words, i, j, t_in, t_out, path):
    """Word-by-word highlighted captions, 1–3 words per card, inside the safe zone."""
    margin_v = SAFE_BOTTOM + 120          # sits in the clean band under the video, clear of both UIs
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Montserrat ExtraBold,76,&H00FFFFFF,&H00FFFFFF,&H00000000,&HB0000000,-1,0,0,0,100,100,1,0,1,6,4,2,{SAFE_LEFT + 30},{SAFE_RIGHT + 30},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ws = [dict(w, t0=w["t0"] - t_in, t1=w["t1"] - t_in) for w in words[i:j + 1]]
    clip_len = t_out - t_in
    # Group into cards: break on punctuation, pauses, or 3 words / 16 chars.
    cards, cur = [], []
    for k, w in enumerate(ws):
        cur.append(w)
        nxt_gap = ws[k + 1]["t0"] - w["t1"] if k + 1 < len(ws) else 9
        chars = sum(len(x["w"]) + 1 for x in cur)
        if re.search(r"[.,?!;:…]$", w["w"]) or nxt_gap > 0.35 or len(cur) >= 3 or chars >= 16:
            cards.append(cur); cur = []
    if cur:
        cards.append(cur)
    lines = []
    for c, card in enumerate(cards):
        card_end = cards[c + 1][0]["t0"] if c + 1 < len(cards) else min(clip_len, card[-1]["t1"] + 0.4)
        for k, w in enumerate(card):
            start = w["t0"] if k else card[0]["t0"]
            end = card[k + 1]["t0"] if k + 1 < len(card) else card_end
            parts = []
            for m, x in enumerate(card):
                word = re.sub(r"[{}\\]", "", x["w"]).upper()
                if m == k:   # active word: yellow, slight pop
                    parts.append(r"{\c&H00D7FF&\fscx108\fscy108}" + word + r"{\c&HFFFFFF&\fscx100\fscy100}")
                else:
                    parts.append(word)
            pop = r"{\fad(40,0)}" if k == 0 else ""
            lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Cap,,0,0,0,,{pop}{' '.join(parts)}")
    Path(path).write_text(head + "\n".join(lines) + "\n")


def loudnorm_measure(video, t_in, dur):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-ss", f"{t_in:.3f}", "-t", f"{dur:.3f}", "-i", str(video),
                        "-af", f"loudnorm=I={LUFS}:TP={TP}:LRA={LRA}:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, check=True)
    js = p.stderr[p.stderr.rfind("{"):p.stderr.rfind("}") + 1]
    return json.loads(js)


def normalize_audio(video, t_in, dur, wav):
    """Two-pass EBU R128 to -14 LUFS, then a measured residual-gain pass with a true-peak limiter,
    so the delivered file lands on target (single-pass linear loudnorm often undershoots)."""
    m = loudnorm_measure(video, t_in, dur)
    stage1 = wav.with_suffix(".stage1.wav")
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t_in:.3f}", "-t", f"{dur:.3f}", "-i", str(video), "-af",
         f"loudnorm=I={LUFS}:TP={TP}:LRA={LRA}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
         f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,"
         f"aresample=48000", "-ac", "2", "-c:a", "pcm_s24le", str(stage1)])
    fades = f"afade=t=in:st=0:d={FADE},afade=t=out:st={dur - FADE:.3f}:d={FADE}"
    gain = 0.0
    for _ in range(3):
        run(["ffmpeg", "-y", "-v", "error", "-i", str(stage1), "-af",
             f"volume={gain:.2f}dB,alimiter=limit={10 ** ((TP - 0.5) / 20):.4f}:level=false:attack=1:release=50,"
             f"aresample=192000,aresample=48000,{fades}", "-c:a", "pcm_s24le", str(wav)])
        lv = measure_output(wav)
        if lv["integrated_lufs"] is None or abs(lv["integrated_lufs"] - LUFS) <= 0.3:
            break
        gain += LUFS - lv["integrated_lufs"]
    stage1.unlink(missing_ok=True)
    return wav


def render(video, src, t_in, t_out, peak_rel, ass_path, out, face_x):
    dur = t_out - t_in
    fps = src["fps"]
    # Keep the source cadence when it is already Reels/Shorts-friendly (24/25/30), so no frame
    # is duplicated; only odd or high rates are normalised.
    out_fps = 60 if fps > 45 else (round(fps) if 23 <= fps <= 31 else 30)
    # Punch-in: ease from 1.00 → 1.12 over 0.35 s starting just before the peak, hold to the end.
    z0, z1, a, b = 1.0, 1.12, max(0.0, peak_rel - 0.15), max(0.0, peak_rel - 0.15) + 0.35
    zexpr = (f"if(lt(t,{a:.3f}),{z0},if(lt(t,{b:.3f}),{z0}+({z1}-{z0})*(1-cos(PI*(t-{a:.3f})/{b - a:.3f}))/2,{z1}))")
    sw, sh = src["w"], src["h"]
    if face_x is not None or sw / sh <= 9 / 16 + 0.01:
        # Hard 9:16 crop centred on the speaker.
        cw = min(sw, round(sh * 9 / 16 / 2) * 2)
        cx = 0.5 if face_x is None else face_x
        x = int(min(max(cx * sw - cw / 2, 0), sw - cw))
        base = f"[0:v]crop={cw}:{sh}:{x}:0,scale={W}:{H}:flags=lanczos,setsar=1[base]"
    else:
        # Wide shot: sharp full frame on a blurred, darkened 9:16 fill (keeps everything in the safe zone).
        base = (f"[0:v]split[a][b];"
                f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:3,eq=brightness=-0.08[bg];"
                f"[b]scale={round(W * 1.12 / 2) * 2}:-2:flags=lanczos,crop={W}:ih:(iw-{W})/2:0[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2-250,setsar=1[base]")
    zoom = (f"[base]scale=w='trunc({W}*({zexpr})/2)*2':h='trunc({H}*({zexpr})/2)*2':eval=frame:flags=bicubic,"
            f"crop={W}:{H}:(iw-{W})/2:(ih-{H})/2*0.85")
    ass_esc = str(ass_path).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    vf = (f"{base};{zoom},fps={out_fps},ass='{ass_esc}',"
          f"fade=t=in:st=0:d={FADE},fade=t=out:st={dur - FADE:.3f}:d={FADE},format=yuv420p[v]")
    wav = normalize_audio(video, t_in, dur, Path(out).with_suffix(".norm.wav"))
    run(["ffmpeg", "-y", "-hide_banner", "-v", "warning", "-ss", f"{t_in:.3f}", "-t", f"{dur:.3f}", "-i", str(video),
         "-i", str(wav), "-filter_complex", vf, "-map", "[v]", "-map", "1:a",
         "-c:v", "libx264", "-profile:v", "high", "-level", "4.2", "-preset", "slow", "-crf", "18",
         "-g", str(out_fps * 2), "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-colorspace", "bt709", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
         "-movflags", "+faststart", "-t", f"{dur:.3f}", str(out)])
    wav.unlink(missing_ok=True)
    return out_fps


def measure_output(out):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(out), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", p.stderr)
    tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", p.stderr)
    return {"integrated_lufs": float(i[-1]) if i else None, "true_peak_dbfs": float(tp[-1]) if tp else None}


def fmt_ts(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="YouTube URL or local video file")
    ap.add_argument("-o", "--out", default="out/short.mp4")
    ap.add_argument("--work", default="work")
    ap.add_argument("--cookies", help="Netscape cookies.txt for yt-dlp (needed if YouTube demands sign-in)")
    ap.add_argument("--model", default="small", help="faster-whisper model size (tiny/base/small/medium/large-v3)")
    ap.add_argument("--start", type=float, help="force the clip to start near this time (s)")
    args = ap.parse_args()

    work = Path(args.work); work.mkdir(parents=True, exist_ok=True)
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)

    video, meta = fetch(args.source, work, args.cookies)
    src = probe(video)
    if not src["has_audio"]:
        raise SystemExit("Source has no audio track.")
    words = transcribe(video, work, args.model)
    if not words:
        raise SystemExit("No speech detected; nothing to caption.")
    energy = energy_curve(video, work)
    score, i, j, t_in, t_out, detail = select(words, energy, meta.get("heatmap"), src["duration"], args.start)
    peak = hook_peak(words, i, j, energy, t_in, t_out)
    face_x = face_crop_x(video, t_in, t_out, src["w"], src["h"])
    ass = work / "captions.ass"
    build_ass(words, i, j, t_in, t_out, ass)
    out_fps = render(video, src, t_in, t_out, peak, ass, out, face_x)
    res = probe(out)
    loud = measure_output(out)
    report = {
        "source": args.source, "title": meta.get("title"),
        "source_start": fmt_ts(t_in), "source_end": fmt_ts(t_out),
        "source_start_s": t_in, "source_end_s": t_out, "duration_s": round(t_out - t_in, 3),
        "punch_in_at_clip_s": round(peak, 2), "crop": "face-tracked 9:16" if face_x is not None else "centre/blur-fill",
        "transcript": detail["text"], "selection_metrics": detail, "score": round(score, 3),
        "output": {"file": str(out), "width": res["w"], "height": res["h"], "fps": round(res["fps"], 3),
                   "duration_s": round(res["duration"], 3), "source_fps": round(src["fps"], 3), **loud},
    }
    out.with_suffix(".json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
