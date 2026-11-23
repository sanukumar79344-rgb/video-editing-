#!/usr/bin/env python3
"""
Build a clean PDF from a Hindi horror script written in the skill's element format,
and print a validation report against the measured spec.

Usage:
    python3 build_pdf.py <input.txt> <output.pdf>

Handles the Devanagari font and weasyprint automatically.
"""

import sys, os, re, html, subprocess, urllib.request

FONT_DIR = os.path.expanduser("~/.cache/hh-script-fonts")
FONTS = {
    "NotoSansDevanagari.ttf":
        "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansdevanagari/NotoSansDevanagari%5Bwdth%2Cwght%5D.ttf",
    "Inter.ttf":
        "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf",
}


def ensure_deps():
    os.makedirs(FONT_DIR, exist_ok=True)
    for name, url in FONTS.items():
        path = os.path.join(FONT_DIR, name)
        if not os.path.exists(path) or os.path.getsize(path) < 10000:
            try:
                urllib.request.urlretrieve(url, path)
            except Exception as e:
                print(f"  ! could not fetch {name}: {e}")
    try:
        import weasyprint  # noqa
    except ImportError:
        print("  installing weasyprint ...")
        subprocess.run([sys.executable, "-m", "pip", "install", "weasyprint",
                        "--break-system-packages", "-q"], check=False)


# ---------------------------------------------------------------- parsing

RE_TITLE = re.compile(r"^#\s+(.*)")
RE_BEAT = re.compile(r"^\[BEAT\s*(.*?)\]\s*$", re.I)
RE_VISUAL = re.compile(r"^\[VISUAL\]\s*(.*)", re.I)
RE_SFX = re.compile(r"^\[SFX\]\s*(.*)", re.I)
RE_SILENT = re.compile(r"^\[SILENT\s*(\d+)\s*s?\]\s*(.*)", re.I)
RE_LINE = re.compile(r"^([A-Za-z\u0900-\u097F][^:]{0,40}):\s*(.*)")

CTA_WORDS = ["subscribe", "सब्सक्राइब", "लाइक", "कमेंट", "शेयर",
             "like karo", "comment karo", "share karo"]


def parse(text):
    blocks, spoken, silent_s, sfx_n, silent_n = [], [], 0, 0, 0
    title = "Untitled"
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if m := RE_TITLE.match(line):
            title = m.group(1).strip(); continue
        if m := RE_BEAT.match(line):
            blocks.append(("beat", m.group(1).strip(), "")); continue
        if m := RE_VISUAL.match(line):
            blocks.append(("visual", "", m.group(1).strip())); continue
        if m := RE_SFX.match(line):
            sfx_n += 1
            blocks.append(("sfx", "", m.group(1).strip())); continue
        if m := RE_SILENT.match(line):
            silent_n += 1; silent_s += int(m.group(1))
            blocks.append(("silent", f"{m.group(1)}s", m.group(2).strip())); continue
        if m := RE_LINE.match(line):
            who, said = m.group(1).strip(), m.group(2).strip()
            kind = "narr" if who.upper() in ("NARRATOR", "NARRATION", "सूत्रधार") else "dial"
            spoken.append(said)
            blocks.append((kind, who, said)); continue
        spoken.append(line)
        blocks.append(("plain", "", line.strip()))
    return title, blocks, spoken, silent_s, sfx_n, silent_n


def report(spoken, silent_s, sfx_n, silent_n):
    joined = " ".join(spoken)
    words = len(joined.split())
    q = joined.count("?")
    speak_min = words / 130.0
    total_min = speak_min + silent_s / 60.0
    ctas = [w for w in CTA_WORDS if w.lower() in joined.lower()]
    pct_silent = 100 * (silent_s / 60.0) / total_min if total_min else 0

    def flag(ok):
        return "OK  " if ok else "FIX "

    print("\n" + "=" * 62)
    print("  VALIDATION REPORT")
    print("=" * 62)
    print(f"  {flag(2700 <= words <= 3000)}Spoken words        {words:>6}      target 2,800–2,900")
    print(f"  {flag(21 <= total_min <= 25)}Est. runtime        {int(total_min)}:{int((total_min%1)*60):02d}       target 23:00")
    print(f"      Spoken time         {int(speak_min)}:{int((speak_min%1)*60):02d}       at 130 WPM")
    print(f"  {flag(10 <= pct_silent <= 19)}Wordless screen     {silent_s:>4}s ({pct_silent:.0f}%)  target ~14%")
    print(f"  {flag(12 <= silent_n <= 16)}Silent beats        {silent_n:>6}      target 12–16")
    print(f"  {flag(20 <= sfx_n <= 24)}Sound cues          {sfx_n:>6}      target 20–24")
    print(f"  {flag(28 <= q <= 45)}Question marks      {q:>6}      target ~35")
    print(f"  {flag(not ctas)}CTAs in voice track {len(ctas):>6}      target 0"
          + (f"   -> {ctas}" if ctas else ""))
    print("=" * 62)
    if all([2700 <= words <= 3000, 10 <= pct_silent <= 19, not ctas]):
        print("  Script meets spec.\n")
    else:
        print("  Revise the flagged items before delivering.\n")
    return words, total_min


# ---------------------------------------------------------------- render

CSS = """
@font-face{font-family:'D';src:url('FONTDIR/NotoSansDevanagari.ttf');}
@font-face{font-family:'I';src:url('FONTDIR/Inter.ttf');}
@page{size:A4;margin:18mm 18mm 16mm 18mm;
 @bottom-center{content:counter(page);font-family:'I';font-size:7.5pt;color:#aaa;}}
body{font-family:'I','D';font-size:10pt;line-height:1.6;color:#1a1a1a;}
h1{font-size:19pt;letter-spacing:-.02em;margin:0 0 2mm 0;}
.sub{font-family:'I';font-size:8pt;color:#888;letter-spacing:.05em;
     text-transform:uppercase;border-bottom:1.5pt solid #111;padding-bottom:3mm;margin-bottom:7mm;}
.beat{background:#111;color:#fff;font-family:'I';font-size:8pt;font-weight:700;
      letter-spacing:.1em;text-transform:uppercase;padding:2mm 3mm;margin:8mm 0 4mm 0;
      page-break-after:avoid;}
.visual{border-left:2.5pt solid #4a6fa5;background:#f5f8fc;padding:2mm 3mm;margin:2.5mm 0;
        font-size:8.6pt;color:#2c3e50;font-style:italic;page-break-inside:avoid;}
.visual b,.sfx b,.silent b{font-style:normal;font-family:'I';font-size:7pt;letter-spacing:.12em;
        text-transform:uppercase;display:block;margin-bottom:.8mm;}
.visual b{color:#4a6fa5;} .sfx b{color:#9a6700;} .silent b{color:#7a3ea5;}
.sfx{border-left:2.5pt solid #9a6700;background:#fffcf3;padding:1.6mm 3mm;margin:2mm 0;
     font-size:8.6pt;color:#6b4c00;page-break-inside:avoid;}
.silent{border-left:2.5pt solid #7a3ea5;background:#faf6fd;padding:2mm 3mm;margin:2.5mm 0;
        font-size:8.6pt;color:#4a2a66;page-break-inside:avoid;}
.narr{margin:3mm 0;padding-left:0;}
.narr .who{font-family:'I';font-size:7pt;letter-spacing:.12em;color:#888;
           text-transform:uppercase;display:block;margin-bottom:.6mm;}
.dial{margin:3mm 0 3mm 12mm;}
.dial .who{font-family:'I';font-size:7.6pt;font-weight:700;color:#000;
           letter-spacing:.04em;display:block;margin-bottom:.6mm;}
.dial .said{border-left:1pt solid #ddd;padding-left:3mm;}
.plain{margin:2.5mm 0;}
.dv{font-family:'D','I';}
"""


def render(title, blocks, words, total_min, out):
    parts = [f"<h1>{html.escape(title)}</h1>",
             f"<div class='sub'>Target {int(total_min)}:{int((total_min%1)*60):02d} &nbsp;·&nbsp; "
             f"{words:,} spoken words &nbsp;·&nbsp; 130 WPM &nbsp;·&nbsp; Hindi animated horror</div>"]
    for kind, who, txt in blocks:
        t = html.escape(txt); w = html.escape(who)
        if kind == "beat":
            parts.append(f"<div class='beat'>{w}</div>")
        elif kind == "visual":
            parts.append(f"<div class='visual'><b>Visual</b>{t}</div>")
        elif kind == "sfx":
            parts.append(f"<div class='sfx dv'><b>SFX</b>{t}</div>")
        elif kind == "silent":
            parts.append(f"<div class='silent'><b>Silent — {w}</b>{t}</div>")
        elif kind == "narr":
            parts.append(f"<div class='narr'><span class='who'>Narrator</span>"
                         f"<span class='dv'>{t}</span></div>")
        elif kind == "dial":
            parts.append(f"<div class='dial'><span class='who dv'>{w}</span>"
                         f"<div class='said dv'>{t}</div></div>")
        else:
            parts.append(f"<div class='plain dv'>{t}</div>")

    doc = ("<!DOCTYPE html><html><head><meta charset='utf-8'><style>"
           + CSS.replace("FONTDIR", FONT_DIR) + "</style></head><body>"
           + "".join(parts) + "</body></html>")

    from weasyprint import HTML
    HTML(string=doc, base_url=FONT_DIR).write_pdf(out)
    print(f"  PDF written: {out}")


def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    src, out = sys.argv[1], sys.argv[2]
    ensure_deps()
    text = open(src, encoding="utf-8").read()
    title, blocks, spoken, silent_s, sfx_n, silent_n = parse(text)
    words, total_min = report(spoken, silent_s, sfx_n, silent_n)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    render(title, blocks, words, total_min, out)


if __name__ == "__main__":
    main()
