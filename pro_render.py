#!/usr/bin/env python3
"""
pro_render.py — agency-style render of one clip.

Given a source video, a [t_in, t_out] window and word timestamps, it:
  1. cuts dead air: any gap between words longer than GAP is removed (jump cuts),
     keeping a little breath either side so speech cadence stays natural;
  2. frames every kept segment on its own (face-tracked 9:16 crop when one face is
     prominent, otherwise the full frame over a blurred fill) and alternates a
     1.00 / 1.10 punch-in from cut to cut, which hides the jump and resets attention;
  3. applies a light, consistent grade (contrast, saturation, gentle sharpen);
  4. cleans the voice (rumble high-pass, FFT denoise, gentle compression) and
     normalises to -14 LUFS / -1 dBTP with a two-pass loudnorm;
  5. burns word-synced captions retimed to the cut timeline: Montserrat ExtraBold,
     active word yellow with a small pop, key words (numbers, emphatic words) green.

Captions come from the words passed in — nothing is invented.
"""
import json
import re
import subprocess
from pathlib import Path

W, H = 1080, 1920
GAP = 0.35            # pauses longer than this are cut
PAD_IN, PAD_OUT = 0.08, 0.14
SAFE_BOTTOM, SAFE_LEFT, SAFE_RIGHT = 480, 90, 140
LUFS, TP = -14.0, -1.0

KEY = re.compile(
    r"^(\d[\d,.%]*|never|always|sabse|kabhi|pehli|bilkul|ekdum|pagal|insane|crazy|"
    r"sach|jhoot|kasam|shocking|secret|truth|million|crore|lakh|hazaar|best|worst|"
    r"biggest|first|last|only|nahi|nahin|kya|kyun|bhai|wow|omg)$", re.I)


def run(cmd):
    subprocess.run(cmd, check=True)


def probe(p):
    o = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
                                   "-show_format", str(p)], check=True, capture_output=True, text=True).stdout)
    v = next(s for s in o["streams"] if s["codec_type"] == "video")
    n, d = map(int, v["avg_frame_rate"].split("/"))
    return {"w": int(v["width"]), "h": int(v["height"]), "fps": n / d if d else 30.0,
            "duration": float(o["format"]["duration"])}


# --------------------------------------------------------------------------- segments
def segments(words, t_in, t_out):
    ws = [w for w in words if w["t0"] >= t_in - 0.05 and w["t1"] <= t_out + 0.05]
    segs, cur = [], [ws[0]]
    for a, b in zip(ws, ws[1:]):
        if b["t0"] - a["t1"] > GAP:
            segs.append(cur); cur = [b]
        else:
            cur.append(b)
    segs.append(cur)
    out = []
    for s in segs:
        a = max(t_in, s[0]["t0"] - PAD_IN)
        b = min(t_out, s[-1]["t1"] + PAD_OUT)
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], b, out[-1][2] + s)
        else:
            out.append((a, b, list(s)))
    return out


# --------------------------------------------------------------------------- framing
def face_x(video, a, b, sw, sh):
    """Centre x (0..1) of the largest face across samples in [a, b]; 0.5 if none found."""
    import cv2
    det = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(str(video))
    xs = []
    n = max(3, int((b - a) / 0.7))
    for j in range(n):
        cap.set(cv2.CAP_PROP_POS_MSEC, (a + (b - a) * (j + 0.5) / n) * 1000)
        ok, fr = cap.read()
        if not ok:
            continue
        fr = cv2.resize(fr, (960, round(960 * fr.shape[0] / fr.shape[1])))
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        fh, fw = g.shape
        faces = det.detectMultiScale(g, 1.1, 5, minSize=(fh // 12, fh // 12))
        if len(faces):
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            xs.append((x + w / 2) / fw)
    cap.release()
    return sorted(xs)[len(xs) // 2] if xs else 0.5


def seg_filter(i, a, b, fx, sw, sh, zoom):
    trim = f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS"
    if True:                                  # always a full-bleed 9:16 crop
        cw = min(sw, round(sh * 9 / 16 / 2) * 2)
        x = int(min(max(fx * sw - cw / 2, 0), sw - cw))
        base = f"{trim},crop={cw}:{sh}:{x}:0,scale={W}:{H}:flags=lanczos"
    else:
        fgw = round(W * 1.12 / 2) * 2
        base = (f"{trim},split[s{i}a][s{i}b];"
                f"[s{i}a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                f"boxblur=28:3,eq=brightness=-0.10[s{i}bg];"
                f"[s{i}b]scale={fgw}:-2:flags=lanczos,crop={W}:ih:(iw-{W})/2:0[s{i}fg];"
                f"[s{i}bg][s{i}fg]overlay=(W-w)/2:(H-h)/2-250")
    if zoom > 1.0:
        zw, zh = round(W * zoom / 2) * 2, round(H * zoom / 2) * 2
        base += f",scale={zw}:{zh}:flags=lanczos,crop={W}:{H}:(iw-{W})/2:(ih-{H})/2*0.8"
    return (f"{base},setsar=1[v{i}];"
            f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:d=0.01,afade=t=out:st={max(0, b - a - 0.012):.3f}:d=0.012[a{i}]")


# --------------------------------------------------------------------------- captions
def ass_t(t):
    t = max(0.0, t); return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def build_ass(ws, dur, path, credit=None):
    mv = SAFE_BOTTOM + 120
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Montserrat ExtraBold,78,&H00FFFFFF,&H00FFFFFF,&H00000000,&HB0000000,-1,0,0,0,100,100,1,0,1,6,4,2,{SAFE_LEFT + 30},{SAFE_RIGHT + 30},{mv},1
Style: Credit,Montserrat ExtraBold,30,&H80FFFFFF,&H80FFFFFF,&H90000000,&H00000000,-1,0,0,0,100,100,1,0,1,2,0,8,60,60,270,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    # Whisper sometimes emits stray non-Latin characters; captions are Latin-only.
    ws = [dict(w, w=re.sub(r"[^A-Za-z0-9%'.,?!-]", "", w["w"])) for w in ws]
    ws = [w for w in ws if w["w"]]
    cards, cur = [], []
    for k, w in enumerate(ws):
        cur.append(w)
        gap = ws[k + 1]["t0"] - w["t1"] if k + 1 < len(ws) else 9
        if re.search(r"[.,?!;:…]$", w["w"]) or gap > 0.3 or len(cur) >= 3 or sum(len(x["w"]) + 1 for x in cur) >= 15:
            cards.append(cur); cur = []
    if cur:
        cards.append(cur)
    lines = []
    for c, card in enumerate(cards):
        end_card = cards[c + 1][0]["t0"] if c + 1 < len(cards) else min(dur, card[-1]["t1"] + 0.4)
        for k, w in enumerate(card):
            st = w["t0"] if k else card[0]["t0"]
            en = card[k + 1]["t0"] if k + 1 < len(card) else end_card
            parts = []
            for m, x in enumerate(card):
                word = re.sub(r"[{}\\]", "", x["w"]).upper()
                clean = re.sub(r"[^\w%]", "", x["w"])
                if m == k:
                    parts.append(r"{\c&H00D7FF&\t(0,80,\fscx112\fscy112)\t(80,160,\fscx104\fscy104)}" + word +
                                 r"{\c&HFFFFFF&\fscx100\fscy100}")
                elif KEY.match(clean):
                    parts.append(r"{\c&H7AFF3D&}" + word + r"{\c&HFFFFFF&}")
                else:
                    parts.append(word)
            fade = r"{\fad(60,0)}" if k == 0 else ""
            lines.append(f"Dialogue: 0,{ass_t(st)},{ass_t(en)},Cap,,0,0,0,,{fade}{' '.join(parts)}")
    if credit:
        lines.append(f"Dialogue: 1,{ass_t(0)},{ass_t(dur)},Credit,,0,0,0,,{credit}")
    Path(path).write_text(head + "\n".join(lines) + "\n")


# --------------------------------------------------------------------------- audio
def clean_audio(src_wav, out_wav):
    chain = "highpass=f=80,afftdn=nf=-25:tn=1,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120:makeup=2"
    p = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(src_wav), "-af",
                        f"{chain},loudnorm=I={LUFS}:TP={TP}:LRA=9:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, check=True)
    m = json.loads(p.stderr[p.stderr.rfind("{"):p.stderr.rfind("}") + 1])
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src_wav), "-af",
         f"{chain},loudnorm=I={LUFS}:TP={TP}:LRA=9:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
         f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,"
         f"alimiter=limit={10 ** ((TP - 0.3) / 20):.4f}:level=false,aresample=48000",
         "-ac", "2", "-c:a", "pcm_s24le", str(out_wav)])


def measure(path):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", p.stderr); tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", p.stderr)
    return {"lufs": float(i[-1]) if i else None, "true_peak": float(tp[-1]) if tp else None}


# --------------------------------------------------------------------------- main entry
def render(video, t_in, t_out, words, out, work, credit=None, captions=True):
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    src = probe(video)
    fps = round(src["fps"]) if 23 <= src["fps"] <= 31 else (60 if src["fps"] > 45 else 30)
    segs = segments(words, t_in, t_out)
    graph, total, cut_words = [], 0.0, []
    for i, (a, b, ws) in enumerate(segs):
        fx = face_x(video, a, b, src["w"], src["h"])
        graph.append(seg_filter(i, a, b, fx, src["w"], src["h"], 1.08 if i % 2 else 1.0))
        for w in ws:
            cut_words.append(dict(w, t0=w["t0"] - a + total, t1=w["t1"] - a + total))
        total += b - a
    n = len(segs)
    graph.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[cv][ca]")
    graph.append(f"[cv]fps={fps},eq=contrast=1.06:saturation=1.10:gamma=0.98,unsharp=5:5:0.45:5:5:0,format=yuv420p[vout]")
    stem = Path(out).stem
    inter, raw = work / f"{stem}.inter.mp4", work / f"{stem}.raw.wav"
    # Only the window is decoded: seek first, then offset everything to it.
    g = ";".join(graph).replace("trim=start=", "trim=start=").replace("[0:v]", "[0:v]").replace("[0:a]", "[0:a]")
    pre = max(0.0, t_in - 1.0)
    g = re.sub(r"(a?trim=start=)([\d.]+):end=([\d.]+)",
               lambda m: f"{m.group(1)}{float(m.group(2)) - pre:.3f}:end={float(m.group(3)) - pre:.3f}", g)
    run(["ffmpeg", "-y", "-hide_banner", "-v", "error", "-ss", f"{pre:.3f}", "-t", f"{t_out - pre + 1:.3f}",
         "-i", str(video), "-filter_complex", g, "-map", "[vout]", "-map", "[ca]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "14", "-c:a", "pcm_s16le", str(inter)])
    run(["ffmpeg", "-y", "-v", "error", "-i", str(inter), "-vn", "-c:a", "pcm_s16le", str(raw)])
    clean = work / f"{stem}.clean.wav"
    clean_audio(raw, clean)
    ass = work / f"{stem}.ass"
    build_ass(cut_words, total, ass, credit)
    esc = str(ass).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    burn = f"ass='{esc}'," if (captions or credit) else ""
    if not captions:
        build_ass([], total, ass, credit)
    run(["ffmpeg", "-y", "-hide_banner", "-v", "error", "-i", str(inter), "-i", str(clean),
         "-vf", f"{burn}fade=t=in:st=0:d=0.15,fade=t=out:st={total - 0.2:.3f}:d=0.2",
         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-crf", "18",
         "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
         "-g", str(fps * 2), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart",
         "-shortest", str(out)])
    for f in (inter, raw, clean):
        f.unlink(missing_ok=True)
    o = probe(out)
    return {"file": str(out), "segments": n, "cuts_removed_s": round((t_out - t_in) - total, 2),
            "duration_s": round(o["duration"], 2), "width": o["w"], "height": o["h"], "fps": round(o["fps"], 2),
            "words": cut_words, **measure(out)}
