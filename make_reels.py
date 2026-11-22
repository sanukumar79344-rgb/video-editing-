#!/usr/bin/env python3
"""
make_reels.py — long video / livestream VOD -> 6-8 vertical Reels of 25-50 s each.

Built for multi-hour sources (e.g. a 10 h livestream VOD) where transcribing everything
is not affordable, and for Hindi/Hinglish speech.

Pipeline
  1. Audio      : download bestaudio only (yt-dlp) — a few hundred MB instead of tens of GB.
  2. Scan       : RMS energy curve over the whole source; shortlist the most animated regions
                  (laughs, shouting, sustained excitement) + YouTube "most replayed" heat when present.
  3. Transcribe : faster-whisper word timestamps on the shortlist only.
  4. Select     : score sentence-aligned 25-50 s windows; greedy non-overlapping pick, spread
                  across the timeline, promos/ads excluded. Max 8.
  5. Cut        : download only those sections in full quality (--download-sections).
  6. Caption    : re-transcribe each section locally (exact sync, no drift), romanize Devanagari
                  to Hinglish, build word-highlight ASS.
  7. Render     : 1080x1920 H.264, face/blur/split layout, punch-in, loudnorm, fades.
  8. Report     : reels.json with timestamps, scores, transcripts, measured output specs.

Usage
  python3 make_reels.py URL --cookies cookies.txt -o out
  python3 make_reels.py URL --cookies cookies.txt --max-clips 8 --scan-model small --caption-model medium
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

from make_short import (W, H, FADE, SAFE_TOP, SAFE_BOTTOM, SAFE_LEFT, SAFE_RIGHT,
                        run, probe, ass_time, build_ass, normalize_audio, measure_output,
                        fmt_ts, face_crop_x, render as render_clip)

MIN_LEN, MAX_LEN = 25.0, 50.0
SWEET = 36.0                 # preferred clip length
MIN_GAP = 180.0              # seconds between two chosen clips
HOP = 0.1                    # energy curve resolution


# --------------------------------------------------------------------------- devanagari -> hinglish
_CONS = {
    'क': 'k', 'ख': 'kh', 'ग': 'g', 'घ': 'gh', 'ङ': 'n',
    'च': 'ch', 'छ': 'chh', 'ज': 'j', 'झ': 'jh', 'ञ': 'n',
    'ट': 't', 'ठ': 'th', 'ड': 'd', 'ढ': 'dh', 'ण': 'n',
    'त': 't', 'थ': 'th', 'द': 'd', 'ध': 'dh', 'न': 'n',
    'प': 'p', 'फ': 'ph', 'ब': 'b', 'भ': 'bh', 'म': 'm',
    'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'v', 'श': 'sh',
    'ष': 'sh', 'स': 's', 'ह': 'h', 'ळ': 'l',
    'क़': 'q', 'ख़': 'kh', 'ग़': 'g', 'ज़': 'z', 'ड़': 'r', 'ढ़': 'rh', 'फ़': 'f',
}
# Hinglish convention: single Latin vowels, no length marks ("bhai", not "bhaaee").
_VOW = {'अ': 'a', 'आ': 'a', 'इ': 'i', 'ई': 'i', 'उ': 'u', 'ऊ': 'u', 'ऋ': 'ri',
        'ए': 'e', 'ऐ': 'ai', 'ओ': 'o', 'औ': 'au', 'ऑ': 'o', 'ॲ': 'a'}
_MATRA = {'ा': 'a', 'ि': 'i', 'ी': 'i', 'ु': 'u', 'ू': 'u', 'ृ': 'ri',
          'े': 'e', 'ै': 'ai', 'ो': 'o', 'ौ': 'au', 'ॉ': 'o', 'ॅ': 'a'}
_DIGIT = {'०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
          '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'}
_VIRAMA, _ANUSVARA, _CHANDRA, _VISARGA, _NUKTA = '्', 'ं', 'ँ', 'ः', '़'


def romanize(text):
    """Devanagari -> readable lowercase Hinglish (schwa-deleted). Latin text passes through."""
    if not re.search(r'[ऀ-ॿ]', text):
        return text
    if ' ' in text.strip():              # schwa rules are per word, so romanize word by word
        return ' '.join(romanize(t) for t in text.split(' '))
    out = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ''
        if ch + nxt in _CONS:                      # nukta pairs
            out.append([_CONS[ch + nxt], 'c']); i += 2; continue
        if ch in _CONS:
            out.append([_CONS[ch], 'c']); i += 1
            if i < n and text[i] == _NUKTA:
                i += 1
            if i < n and text[i] == _VIRAMA:
                i += 1                              # no inherent vowel
            elif i < n and text[i] in _MATRA:
                out.append([_MATRA[text[i]], 'v']); i += 1
            else:
                out.append(['a', 'schwa'])          # inherent vowel, may be deleted later
            continue
        if ch in _VOW:
            out.append([_VOW[ch], 'v']); i += 1; continue
        if ch in _MATRA:
            out.append([_MATRA[ch], 'v']); i += 1; continue
        if ch == _ANUSVARA:
            out.append(['n', 'c']); i += 1; continue
        if ch == _CHANDRA:
            out.append(['n', 'c']); i += 1; continue
        if ch == _VISARGA:
            out.append(['h', 'c']); i += 1; continue
        if ch in _DIGIT:
            out.append([_DIGIT[ch], 'o']); i += 1; continue
        if ch in ('।', '॥'):
            out.append(['.', 'o']); i += 1; continue
        if ch in (_VIRAMA, _NUKTA, '‍', '‌'):
            i += 1; continue
        out.append([ch, 'o']); i += 1               # spaces, latin, punctuation
    # Schwa deletion, the two cases that matter for readable Hinglish:
    #   final inherent 'a'            kasama  -> kasam
    #   medial one before C + a real vowel   lagataa -> lagta  (kept in kasam: next vowel is a schwa)
    for k, item in enumerate(out):
        if item[1] != 'schwa':
            continue
        is_final = (k + 1 >= len(out)) or (out[k + 1][1] == 'o' and not out[k + 1][0].isalnum())
        if is_final and k >= 2:
            item[0] = ''
        elif k >= 2 and k + 2 < len(out) and out[k + 1][1] == 'c' and out[k + 2][1] == 'v':
            item[0] = ''
    txt = ''.join(x[0] for x in out)
    for a, b in (('chchh', 'cch'), ('shch', 'sch'), ('nn', 'n')):
        txt = txt.replace(a, b)
    return txt


# --------------------------------------------------------------------------- 1. audio
def fetch_audio(src, work, cookies=None):
    """bestaudio to work/audio.m4a + metadata (incl. heatmap when YouTube exposes it)."""
    audio = work / "audio.m4a"
    meta_file = work / "meta.json"
    if audio.exists() and meta_file.exists():
        return audio, json.loads(meta_file.read_text())
    if os.path.exists(src):
        run(["ffmpeg", "-y", "-v", "error", "-i", src, "-vn", "-c:a", "aac", "-b:a", "128k", str(audio)])
        meta_file.write_text("{}")
        return audio, {}
    base = ["yt-dlp", "--no-playlist", "--js-runtimes", "node"]
    if cookies:
        base += ["--cookies", cookies]
    run(base + ["-f", "bestaudio[ext=m4a]/bestaudio", "--write-info-json",
                "-o", str(work / "audio.%(ext)s"), src])
    got = next(p for p in work.glob("audio.*") if p.suffix in (".m4a", ".webm", ".opus", ".mp4"))
    if got != audio:
        run(["ffmpeg", "-y", "-v", "error", "-i", str(got), "-c:a", "aac", "-b:a", "128k", str(audio)])
    info = json.loads(next(work.glob("audio*.info.json")).read_text())
    meta = {k: info.get(k) for k in ("id", "title", "channel", "duration", "heatmap", "chapters",
                                     "width", "height", "fps", "was_live")}
    meta_file.write_text(json.dumps(meta, indent=2))
    return audio, meta


# --------------------------------------------------------------------------- 2. scan
def energy_curve(audio, work, hop=HOP):
    """RMS dB every `hop` s for the whole source (numpy, streams via ffmpeg)."""
    import numpy as np
    cache = work / "energy.npy"
    if cache.exists():
        return np.load(cache)
    sr = 8000
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(audio), "-ac", "1", "-ar", str(sr),
                          "-f", "s16le", "-"], check=True, capture_output=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    n = int(sr * hop)
    a = a[:len(a) // n * n].reshape(-1, n)
    rms = np.sqrt((a * a).mean(axis=1) + 1e-12)
    curve = 20 * np.log10(rms)
    np.save(cache, curve)
    return curve


def heat_lookup(heatmap):
    if not heatmap:
        return lambda t0, t1: 0.0
    pts = sorted(((h["start_time"], h["end_time"], h["value"]) for h in heatmap), key=lambda x: x[0])

    def at(t0, t1):
        vals = [v for s, e, v in pts if e > t0 and s < t1]
        return max(vals) if vals else 0.0
    return at


def shortlist(energy, heat_at, duration, regions=40, region_len=90.0, hop=HOP):
    """Most animated regions of the source: loud-and-dynamic speech, spread over the timeline."""
    import numpy as np
    voiced = energy[energy > -45]
    base = float(np.median(voiced)) if len(voiced) else -40.0
    win = int(region_len / hop)
    step = int(15.0 / hop)
    scored = []
    for s in range(0, max(1, len(energy) - win), step):
        seg = energy[s:s + win]
        v = seg[seg > -45]
        if len(v) < win * 0.25:                      # mostly silence/music -> skip
            continue
        t0, t1 = s * hop, (s + win) * hop
        loud = float(v.mean()) - base
        dyn = float(np.percentile(seg, 99) - np.percentile(v, 40))
        excite = float((v > base + 6).mean())        # share of time clearly above baseline
        scored.append((1.0 * loud + 0.35 * dyn + 6.0 * excite + 8.0 * heat_at(t0, t1), t0, t1))
    scored.sort(reverse=True)
    picked = []
    for sc, t0, t1 in scored:
        if any(not (t1 <= p[0] or t0 >= p[1]) for p in picked):
            continue
        picked.append((t0, min(t1, duration)))
        if len(picked) >= regions:
            break
    return sorted(picked)


# --------------------------------------------------------------------------- 3. transcribe
def load_model(size):
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    from faster_whisper import WhisperModel
    return WhisperModel(size, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)


def decode_pcm(audio, t0=None, dur=None):
    import numpy as np
    cmd = ["ffmpeg", "-v", "error"]
    if t0 is not None:
        cmd += ["-ss", f"{t0:.3f}"]
    if dur is not None:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-i", str(audio), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
    pcm = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0


def words_from(model, pcm, offset=0.0, language="hi"):
    segs, _ = model.transcribe(pcm, language=language, word_timestamps=True,
                               vad_filter=True, beam_size=5,
                               condition_on_previous_text=False)
    out = []
    for s in segs:
        for w in s.words or []:
            txt = romanize(w.word.strip())
            if txt:
                out.append({"t0": round(w.start + offset, 3), "t1": round(w.end + offset, 3),
                            "w": txt, "p": round(w.probability, 3)})
    return out


def transcribe_regions(audio, regions, model_size, work, language="hi"):
    cache = work / f"scan_words_{model_size}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    model = load_model(model_size)
    words = []
    for k, (t0, t1) in enumerate(regions, 1):
        print(f"[scan] region {k}/{len(regions)}  {fmt_ts(t0)}-{fmt_ts(t1)}", file=sys.stderr)
        words += words_from(model, decode_pcm(audio, t0, t1 - t0), offset=t0, language=language)
        cache.write_text(json.dumps(words))
    return words


# --------------------------------------------------------------------------- 4. select
HOOK = [
    r"\b(bhai|bhaiya|yaar|arre|arrey|oye|abe|dekho|dekh|suno|sun)\b",
    r"\b(kya|kyun|kaise|kab|kaun|kitna|matlab)\b",
    r"\b(pagal|paagal|insane|crazy|bakwaas|jhoot|sach|sachme|kasam|mazaak|mazak)\b",
    r"\b(pehli baar|kabhi nahi|kabhi nahin|sabse|zyada|bilkul|ekdum|seedha)\b",
    r"\b(never|always|nobody|everyone|secret|truth|actually|real|insane|biggest|worst|best|first time)\b",
    r"\b(gta|rockstar|lucia|jason|vice city|graphics|mission|trailer)\b",
    r"[?!]",
]
LAUGH = r"\b(haha+|hahaha+|lol|lmao|bhai haha|hasi|hans)\b"
PROMO = (r"\b(subscribe|superchat|super chat|membership|member|giveaway|sponsor|sponsored|link|"
         r"description|discount|code|promo|wlues|makhaane|makhana|channel|follow|insta|instagram|"
         r"stream|live aa|donate|paisa bhejo)\b")
WEAK_STARTS = {"and", "but", "so", "or", "then", "also", "um", "uh", "like", "aur", "toh", "to",
               "lekin", "phir", "matlab", "ki", "ke", "ka", "hai", "haan", "ha", "nahi", "woh", "wo", "ye"}
SENT_END = re.compile(r"[.?!…]$")


def windows(words):
    """Sentence-aligned (start-of-sentence -> end-of-sentence/breath) windows of MIN_LEN..MAX_LEN."""
    n = len(words)
    for i in range(n):
        if i > 0:
            gap = words[i]["t0"] - words[i - 1]["t1"]
            if not (SENT_END.search(words[i - 1]["w"]) or gap >= 0.45):
                continue
        for j in range(i, n):
            if j > i and words[j]["t0"] - words[j - 1]["t1"] > 8.0:
                break               # a hole: shortlist regions are not contiguous, never span one
            core = words[j]["t1"] - words[i]["t0"]
            if core > MAX_LEN - 0.3:
                break
            if core < MIN_LEN - 0.6:
                continue
            gap_after = (words[j + 1]["t0"] if j + 1 < n else words[j]["t1"] + 1.5) - words[j]["t1"]
            if not (SENT_END.search(words[j]["w"]) or gap_after >= 0.35):
                continue
            pre = min(0.15, max(0.0, (words[i]["t0"] - (words[i - 1]["t1"] if i else 0.0)) - 0.08))
            post = min(0.35, max(0.0, gap_after - 0.08))
            t_in, t_out = round(words[i]["t0"] - pre, 3), round(words[j]["t1"] + post, 3)
            if MIN_LEN <= t_out - t_in <= MAX_LEN:
                yield i, j, t_in, t_out


def score(words, i, j, t_in, t_out, energy, heat_at, base_db, hop=HOP):
    import numpy as np
    text = " ".join(w["w"] for w in words[i:j + 1])
    low = text.lower()
    seg = energy[int(t_in / hop):int(t_out / hop)]
    if not len(seg):
        return -99, {}
    v = seg[seg > -45]
    mean_db = float(v.mean()) if len(v) else -60.0
    dyn = float(np.percentile(seg, 99) - (np.percentile(v, 40) if len(v) else -60))
    loud = mean_db - base_db
    hook = sum(len(re.findall(p, low)) for p in HOOK)
    first3 = " ".join(w["w"] for w in words[i:j + 1] if w["t0"] < t_in + 3.0).lower()
    early = sum(len(re.findall(p, first3)) for p in HOOK)
    laugh = len(re.findall(LAUGH, low))
    promo = len(re.findall(PROMO, low))
    first = re.sub(r"[^a-z']", "", words[i]["w"].lower())
    weak_start = first in WEAK_STARTS
    wps = (j - i + 1) / (t_out - t_in)
    conf = sum(w["p"] for w in words[i:j + 1]) / (j - i + 1)
    ends_clean = bool(SENT_END.search(words[j]["w"]))
    heat = heat_at(t_in, t_out)
    s = (3.0 * heat
         + 0.10 * dyn + 0.14 * loud
         + 0.30 * min(hook, 8) + 0.55 * min(early, 3) + 0.30 * min(laugh, 4)
         + (-1.6 if early == 0 else 0.0)
         + (-1.3 if weak_start else 0.0)
         + (0.6 if ends_clean else 0.0)
         - 2.2 * min(promo, 3)
         - 0.55 * abs(wps - 2.9)
         + 1.5 * (conf - 0.75)
         - 0.05 * abs((t_out - t_in) - SWEET))
    return s, {"text": text, "heat": round(heat, 3), "dyn_db": round(dyn, 2),
               "loud_vs_base_db": round(loud, 2), "hook_hits": hook, "early_hook_hits": early,
               "laugh_hits": laugh, "promo_hits": promo, "weak_start": weak_start,
               "words_per_sec": round(wps, 2), "asr_conf": round(conf, 3),
               "ends_on_sentence": ends_clean}


def select(words, energy, heat_at, max_clips, min_gap=MIN_GAP):
    import numpy as np
    voiced = energy[energy > -45]
    base_db = float(np.median(voiced)) if len(voiced) else -40.0
    cands = []
    for i, j, t_in, t_out in windows(words):
        s, d = score(words, i, j, t_in, t_out, energy, heat_at, base_db)
        if d:
            cands.append((s, i, j, t_in, t_out, d))
    cands.sort(key=lambda x: -x[0])
    picked = []
    for c in cands:
        if c[5]["promo_hits"] >= 2:
            continue
        if any(not (c[4] + min_gap <= p[3] or c[3] >= p[4] + min_gap) for p in picked):
            continue
        picked.append(c)
        if len(picked) >= max_clips:
            break
    return picked, len(cands)


# --------------------------------------------------------------------------- 5. cut
def download_section(src, t0, t1, out, cookies=None, pad=4.0):
    """Download just [t0-pad, t1+pad] in full quality. Returns (file, offset_of_t0_in_file)."""
    a, b = max(0.0, t0 - pad), t1 + pad
    base = ["yt-dlp", "--no-playlist", "--js-runtimes", "node", "--force-keyframes-at-cuts",
            "--download-sections", f"*{a:.3f}-{b:.3f}"]
    if cookies:
        base += ["--cookies", cookies]
    run(base + ["-f", "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=1080]+ba/b",
                "--merge-output-format", "mp4", "-o", str(out), src])
    return out, t0 - a


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("-o", "--outdir", default="out")
    ap.add_argument("--work", default="work")
    ap.add_argument("--cookies")
    ap.add_argument("--max-clips", type=int, default=8)
    ap.add_argument("--regions", type=int, default=40, help="how many 90 s regions to transcribe in the scan")
    ap.add_argument("--scan-model", default="small")
    ap.add_argument("--caption-model", default="medium")
    ap.add_argument("--language", default="hi")
    ap.add_argument("--select-only", action="store_true", help="stop after choosing moments")
    args = ap.parse_args()

    work = Path(args.work); work.mkdir(parents=True, exist_ok=True)
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    audio, meta = fetch_audio(args.source, work, args.cookies)
    duration = meta.get("duration") or probe(audio)["duration"]
    energy = energy_curve(audio, work)
    heat_at = heat_lookup(meta.get("heatmap"))
    regions = shortlist(energy, heat_at, duration, regions=args.regions)
    print(f"[scan] {len(regions)} regions, {sum(b - a for a, b in regions) / 60:.0f} min of audio to transcribe",
          file=sys.stderr)
    words = transcribe_regions(audio, regions, args.scan_model, work, args.language)
    print(f"[scan] {len(words)} words", file=sys.stderr)
    picked, n_cands = select(words, energy, heat_at, args.max_clips)
    print(f"[select] {len(picked)} clips from {n_cands} candidate windows", file=sys.stderr)
    plan = [{"rank": k, "start_s": c[3], "end_s": c[4], "duration_s": round(c[4] - c[3], 2),
             "start": fmt_ts(c[3]), "end": fmt_ts(c[4]), "score": round(c[0], 3), **c[5]}
            for k, c in enumerate(picked, 1)]
    (work / "plan.json").write_text(json.dumps(plan, indent=2))
    print(json.dumps(plan, indent=2))
    if args.select_only:
        return

    cap_model = load_model(args.caption_model)
    report = []
    for k, c in enumerate(picked, 1):
        t_in, t_out = c[3], c[4]
        name = f"Reel_{k:02d}"
        sect = work / f"{name}_src.mp4"
        off_file = work / f"{name}_offset.json"
        if sect.exists() and off_file.exists():
            off = json.loads(off_file.read_text())["offset"]
        else:
            _, off = download_section(args.source, t_in, t_out, sect, args.cookies)
            off_file.write_text(json.dumps({"offset": off}))
        src = probe(sect)
        dur = t_out - t_in
        # exact, drift-free captions: transcribe the cut itself
        cw = words_from(cap_model, decode_pcm(sect, off, dur), offset=off, language=args.language)
        if not cw:
            print(f"! {name}: no speech found in the cut, skipping", file=sys.stderr)
            continue
        ass = work / f"{name}.ass"
        build_ass(cw, 0, len(cw) - 1, off, off + dur, ass)
        face_x = face_crop_x(sect, off, off + dur, src["w"], src["h"])
        peak = min(dur * 0.5, 1.2)
        out = outdir / f"{name}.mp4"
        render_clip(sect, src, off, off + dur, peak, ass, out, face_x)
        res = probe(out)
        report.append({"file": str(out), "rank": k,
                       "source_start": fmt_ts(t_in), "source_end": fmt_ts(t_out),
                       "source_start_s": t_in, "source_end_s": t_out,
                       "duration_s": round(res["duration"], 2),
                       "width": res["w"], "height": res["h"], "fps": round(res["fps"], 2),
                       "crop": "face-tracked 9:16" if face_x is not None else "centre/blur-fill",
                       "transcript": " ".join(w["w"] for w in cw),
                       "selection": c[5], "score": round(c[0], 3), **measure_output(out)})
        (outdir / "reels.json").write_text(json.dumps(report, indent=2))
        print(f"[done] {out}", file=sys.stderr)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
