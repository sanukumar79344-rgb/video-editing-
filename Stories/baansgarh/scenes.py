#!/usr/bin/env python3
"""Baansgarh: the picture, scene by scene, timed to the narration.

Each entry below covers a range of narration lines (1-based, inclusive) and builds the shot
for them. Durations come from audio/timing.json, so re-recording the voice re-times the film
without touching this file.

    python3 scenes.py --still 40        # one frame at 40 s
    python3 scenes.py --out out/film.mp4
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from anim import (Bamboo, Bound, Bundles, Fog, Figure, Flash, Grain, Ground, Hills, Huts,
                  Lantern, Machine, Moon, Prints, Rain, Scene, Sky, Stepwell, StoneWall,
                  Treeline, Vignette, W, H, INK, FAR, MID, NEAR, LAMP, MOON, DUSK_TOP,
                  DUSK_BOT, NIGHT_TOP, NIGHT_BOT, mix, render, render_still)

HERE = pathlib.Path(__file__).resolve().parent
SEG = json.loads((HERE / "audio" / "timing.json").read_text())["segments"]
TOTAL = json.loads((HERE / "audio" / "timing.json").read_text())["total_duration"]


def span(a, b):
    """Start and length covering narration lines a..b."""
    s = SEG[a - 1]["start"]
    e = SEG[b - 1]["end"]
    return s, e - s


# ---------------------------------------------------------------- shot builders
def village_wide(d, moon_x=1430, lit=True, fog=26):
    sc = Scene(d, Sky(), Moon(moon_x, 210, 92),
               Hills(0.12, 0.58, 150, FAR),
               Hills(0.2, 0.65, 95, mix(FAR, MID, 0.6), seed=31),
               Treeline(0.3, 0.70, 15, 1.0, MID, seed=41),
               Huts(0.44, 0.77, 5, 1.0, mix(MID, NEAR, 0.45), seed=51, lit=lit),
               Bamboo(0.6, 9, 0.99, NEAR, seed=61),
               Ground(0.8, 0.86), Fog(0.9, 0.78, 5, (150, 170, 210), fog),
               Vignette(170), Grain())
    return sc


def bamboo_path(d, walker=None, shadow=None, lantern=None, seed=7):
    sc = Scene(d, Sky(), Moon(350, 175, 74),
               Treeline(0.28, 0.67, 12, 1.25, MID, seed=seed),
               Bamboo(0.5, 7, 0.98, mix(NEAR, MID, 0.45), seed=seed + 1, x0=-0.15, x1=0.55),
               Bamboo(0.72, 6, 1.02, NEAR, seed=seed + 2, x0=0.55, x1=1.2),
               Ground(0.82, 0.88), Fog(0.92, 0.8, 6, (140, 160, 200), 30))
    if lantern:
        sc.add(Lantern(0.8, lantern[0], lantern[1], 250))
    if walker:
        sc.add(walker)
    if shadow:
        sc.add(shadow)
    sc.add(Vignette(205), Grain())
    return sc


def well_shot(d, figure=None, lantern=None, rows=6, cy=0.34, light=(58, 52, 74)):
    sc = Scene(d, Sky(DUSK_TOP, DUSK_BOT, 40), Hills(0.1, 0.30, 120, (46, 38, 58)),
               Stepwell(depth=0.5, cx=0.5, cy=cy, w=0.62, rows=rows, color=light))
    if figure:
        sc.add(figure)
    if lantern:
        sc.add(Lantern(0.82, lantern[0], lantern[1], 220))
    sc.add(Fog(0.92, 0.52, 5, (170, 160, 190), 20), Vignette(205), Grain())
    return sc


def dark_room(d, *extra, arch=True, wall=(46, 42, 58), y=0.0):
    """Inside the well: a block wall, a floor, then whatever the torch finds."""
    sc = Scene(d, StoneWall(0.3, wall, arch=arch, y=y),
               Ground(0.55, 0.86, (22, 22, 30), grass=False), *extra)
    sc.add(Fog(0.95, 0.84, 3, (120, 130, 150), 16), Vignette(225), Grain())
    return sc


# ---------------------------------------------------------------- the film
def build():
    sc = []

    # 1-4  hook: the village from far, then the rule
    s, d = span(1, 2)
    a = village_wide(d, lit=True)
    a.cam(0, 0, 0, 1.0).cam(d, -140, 20, 1.1)
    sc.append(a)

    s, d = span(3, 4)
    b = well_shot(d, lantern=(0.5, 0.26))
    b.cam(0, 0, -60, 1.14).cam(d, 0, 30, 1.0)
    sc.append(b)

    # 5-10  the village by day and dusk, the bell, the well's history
    s, d = span(5, 6)
    c = Scene(d, Sky((92, 118, 170), (196, 176, 150), 0), Moon(1600, 160, 60),
              Hills(0.12, 0.58, 150, (120, 128, 140)),
              Treeline(0.3, 0.70, 15, 1.0, (86, 96, 100), seed=41),
              Huts(0.44, 0.77, 5, 1.0, (104, 96, 86), seed=51, lit=False),
              Bamboo(0.6, 9, 0.99, (58, 68, 58), seed=61),
              Ground(0.8, 0.86, (96, 92, 78)), Fog(0.9, 0.8, 4, (220, 210, 190), 22),
              Vignette(120), Grain())
    c.cam(0, 120, 0, 1.0).cam(d, -120, 0, 1.06)
    sc.append(c)

    s, d = span(7, 8)
    e = village_wide(d, moon_x=1250, fog=40)
    e.cam(0, -100, 0, 1.04).cam(d, 60, 10, 1.12)
    sc.append(e)

    s, d = span(9, 10)
    f = well_shot(d, rows=6, cy=0.30)
    f.cam(0, 0, -40, 1.0).cam(d, 0, 60, 1.16)
    sc.append(f)

    # 11-17  the legend and the three who went
    s, d = span(11, 13)
    g = well_shot(d, cy=0.36, light=(40, 36, 54))
    g.cam(0, 0, 40, 1.12).cam(d / 2, 0, -10, 1.0).cam(d, 0, 20, 1.08)
    sc.append(g)

    for lines, fx in ((( 14, 14), 0.3), ((15, 15), 0.5), ((16, 16), 0.7)):
        s, d = span(*lines)
        h = bamboo_path(d, walker=Figure(0.74, fx, 0.9, 0.2, "walk", INK, speed=0.9, seed=int(fx * 10)),
                        lantern=(fx - 0.06, 0.8), seed=int(10 + fx * 10))
        h.cam(0, 60, 0, 1.0).cam(d, -60, 0, 1.08)
        sc.append(h)

    s, d = span(17, 17)
    i = bamboo_path(d, shadow=Figure(0.85, 0.5, 0.93, 0.4, "shadow", (4, 6, 16)), seed=19)
    i.cam(0, 0, 0, 1.0).cam(d, 0, -20, 1.14)
    sc.append(i)

    # 18-29  Kishan's night
    s, d = span(18, 19)
    j = village_wide(d, lit=False, fog=34)
    j.cam(0, 100, 0, 1.06).cam(d, -40, 0, 1.0)
    sc.append(j)

    s, d = span(20, 21)
    k = bamboo_path(d, walker=Figure(0.72, 0.42, 0.9, 0.24, "cycle", INK, speed=1.3), seed=23)
    k.cam(0, -200, 0, 1.0).cam(d, 220, 0, 1.04)
    sc.append(k)

    s, d = span(22, 23)
    m = Scene(d, Sky(), Moon(1500, 200, 80), Treeline(0.28, 0.68, 10, 1.1, MID, seed=29),
              Bamboo(0.55, 7, 0.99, NEAR, seed=31, x0=0.45, x1=1.2),
              Figure(0.7, 0.3, 0.88, 0.24, "stand", INK),
              Lantern(0.72, 0.3, 0.72, 200, power=0.7),
              Ground(0.82, 0.86), Fog(0.9, 0.8, 5, (140, 160, 200), 26),
              Vignette(200), Grain())
    m.cam(0, 0, 0, 1.0).cam(d, -80, -20, 1.12)
    sc.append(m)

    s, d = span(24, 24)                                   # the lights come on
    n = village_wide(d, lit=True, fog=30)
    n.add(Flash([(0, 0.5), (0.35, 0.0)], color=(255, 232, 190)))
    n.cam(0, 0, 0, 1.08).cam(d, 60, 0, 1.0)
    sc.append(n)

    s, d = span(25, 26)                                   # the bell, then water in a dry well
    o = well_shot(d, cy=0.32, light=(44, 40, 60))
    o.cam(0, 0, -30, 1.0).cam(d, 0, 90, 1.25)
    sc.append(o)

    s, d = span(27, 27)
    p = well_shot(d, cy=0.30, light=(40, 36, 56))
    p.cam(0, 0, 80, 1.2).cam(d, 0, 140, 1.4)
    sc.append(p)

    s, d = span(28, 28)                                   # the torch dies
    q = bamboo_path(d, walker=Figure(0.72, 0.34, 0.9, 0.22, "stand", INK),
                    lantern=(0.42, 0.72), seed=37)
    q.add(Flash([(0, 0.0), (d * 0.45, 0.0), (d * 0.5, 0.75), (d * 0.58, 0.0),
                 (d * 0.66, 0.6), (d * 0.75, 0.95)], color=(0, 0, 0)))
    q.cam(0, 0, 0, 1.0).cam(d, 40, 0, 1.1)
    sc.append(q)

    s, d = span(29, 29)                                   # the shadow is standing there
    r = bamboo_path(d, shadow=Figure(0.86, 0.52, 0.93, 0.46, "shadow", (3, 5, 14)), seed=41)
    r.cam(0, 0, 40, 1.0).cam(d, 0, -10, 1.2)
    sc.append(r)

    s, d = span(30, 30)                                   # morning: the toolbox
    t_ = Scene(d, Sky((150, 160, 180), (214, 206, 190), 0),
               Hills(0.12, 0.6, 120, (150, 150, 152)),
               Treeline(0.3, 0.70, 12, 1.0, (110, 118, 112), seed=43),
               Bamboo(0.6, 8, 0.99, (74, 84, 74), seed=47),
               Figure(0.74, 0.62, 0.9, 0.2, "cycle", (40, 42, 44), speed=0.0),
               Ground(0.8, 0.86, (120, 116, 100)), Fog(0.9, 0.82, 4, (230, 226, 216), 30),
               Vignette(120), Grain())
    t_.cam(0, -60, 0, 1.12).cam(d, 40, 0, 1.0)
    sc.append(t_)

    # 31-38  Meera
    s, d = span(31, 33)
    u = village_wide(d, lit=True, fog=24)
    u.cam(0, -120, 0, 1.08).cam(d, 120, 0, 1.0)
    sc.append(u)

    s, d = span(34, 35)
    v = Scene(d, Sky(), Moon(1300, 190, 78), Treeline(0.3, 0.70, 10, 1.0, MID, seed=53),
              Huts(0.5, 0.8, 2, 1.5, mix(MID, NEAR, 0.4), seed=57),
              Figure(0.75, 0.38, 0.9, 0.23, "stand", INK, seed=59),
              Figure(0.75, 0.56, 0.9, 0.21, "stand", mix(INK, MID, 0.25), seed=61),
              Lantern(0.78, 0.47, 0.74, 240, power=0.8),
              Ground(0.82, 0.88), Fog(0.9, 0.82, 4, (150, 160, 190), 22),
              Vignette(200), Grain())
    v.cam(0, 40, 0, 1.0).cam(d, -40, 0, 1.1)
    sc.append(v)

    s, d = span(36, 38)
    w_ = dark_room(d, Lantern(0.62, 0.58, 0.5, 420, power=0.55),
                   Figure(0.8, 0.44, 0.88, 0.26, "stand", INK), arch=False, wall=(52, 46, 54))
    w_.cam(0, 0, 0, 1.0).cam(d, 0, -30, 1.12)
    sc.append(w_)

    # 39-46  the clues
    s, d = span(39, 40)
    x = bamboo_path(d, walker=Figure(0.74, 0.44, 0.9, 0.22, "walk", INK, speed=0.85, seed=67),
                    lantern=(0.5, 0.78), seed=71)
    x.cam(0, -120, 0, 1.0).cam(d, 80, 10, 1.1)
    sc.append(x)

    s, d = span(41, 42)
    y = Scene(d, Sky((10, 14, 30), (26, 34, 60), 0),
              Ground(0.35, 0.18, (36, 34, 44), grass=False),
              Prints(0.85, 0.52, 8, t0=0.5, step=0.34),
              Lantern(0.62, 0.22, 0.42, 420, power=0.8),
              Fog(0.95, 0.72, 4, (150, 150, 170), 18), Vignette(215), Grain())
    y.cam(0, 60, -30, 1.14).cam(d, -60, 20, 1.0)
    sc.append(y)

    s, d = span(43, 45)
    z = well_shot(d, cy=0.33, lantern=(0.38, 0.3), light=(50, 46, 66))
    z.cam(0, -60, -40, 1.1).cam(d, 20, 20, 1.0)
    sc.append(z)

    s, d = span(46, 46)
    aa = well_shot(d, cy=0.30, lantern=(0.5, 0.28), light=(46, 42, 62))
    aa.cam(0, 0, 0, 1.0).cam(d, 0, 110, 1.3)
    sc.append(aa)

    # 47-58  down the steps, the truth
    s, d = span(47, 49)
    ab = well_shot(d, cy=0.22, lantern=(0.5, 0.45), rows=6, light=(56, 50, 70))
    ab.cam(0, 0, -60, 1.1).cam(d, 0, 180, 1.45)
    sc.append(ab)

    s, d = span(50, 52)
    ac = dark_room(d, Machine(0.7, 0.58, 0.84, 1.0),
                   Lantern(0.6, 0.3, 0.62, 430, power=0.85),
                   Figure(0.8, 0.2, 0.88, 0.24, "stand", INK))
    ac.cam(0, -60, 0, 1.0).cam(d, 60, 0, 1.12)
    sc.append(ac)

    s, d = span(53, 54)
    ad = dark_room(d, Bundles(0.72, 0.52, 0.9, 9, 1.7, tarp=False),
                   Machine(0.68, 0.18, 0.84, 0.8),
                   Lantern(0.6, 0.5, 0.6, 560, power=0.9), arch=False)
    ad.cam(0, 0, 20, 1.08).cam(d, 0, -20, 1.0)
    sc.append(ad)

    s, d = span(55, 56)                                   # three men, and the shadow
    ae = well_shot(d, cy=0.26, light=(44, 40, 60))
    ae.add(Figure(0.7, 0.36, 0.42, 0.16, "stand", INK, seed=73),
           Figure(0.7, 0.5, 0.42, 0.16, "stand", INK, seed=79),
           Figure(0.7, 0.64, 0.42, 0.16, "stand", INK, seed=83),
           Figure(0.88, 0.5, 0.95, 0.4, "shadow", (3, 5, 14)),
           Lantern(0.72, 0.5, 0.4, 300, power=0.8))
    ae.cam(0, 0, -40, 1.0).cam(d, 0, 30, 1.16)
    sc.append(ae)

    s, d = span(57, 58)                                   # the torch on its face: cloth
    af = dark_room(d, Figure(0.86, 0.52, 0.95, 0.42, "shadow", (6, 8, 18)),
                   Figure(0.8, 0.3, 0.9, 0.24, "stand", INK, seed=101),
                   Lantern(0.62, 0.3, 0.6, 420, power=1.0), arch=False)
    af.add(Flash([(0, 0.0), (d * 0.3, 0.0), (d * 0.42, 0.5), (d * 0.6, 0.0)], color=(255, 250, 240)))
    af.cam(0, 0, 0, 1.12).cam(d, 0, -40, 1.0)
    sc.append(af)

    s, d = span(59, 59)
    ag = dark_room(d, Figure(0.8, 0.46, 0.9, 0.3, "stand", INK),
                   Figure(0.78, 0.66, 0.9, 0.26, "stand", mix(INK, MID, 0.3), seed=103),
                   Lantern(0.62, 0.56, 0.58, 400, power=0.9), arch=False)
    ag.cam(0, 0, 0, 1.0).cam(d, 20, 0, 1.08)
    sc.append(ag)

    # 60-69  the end
    s, d = span(60, 62)
    ah = well_shot(d, cy=0.32, light=(48, 44, 64))
    ah.cam(0, 0, 60, 1.14).cam(d, 0, -20, 1.0)
    sc.append(ah)

    s, d = span(63, 64)
    ai = bamboo_path(d, walker=Figure(0.74, 0.46, 0.9, 0.22, "walk", INK, speed=1.1, seed=89),
                     lantern=(0.52, 0.78), seed=91)
    ai.cam(0, -80, 0, 1.0).cam(d, 80, 0, 1.08)
    sc.append(ai)

    s, d = span(65, 66)
    aj = dark_room(d, Bound(0.76, 0.42, 0.88, 0.24),
                   Lantern(0.6, 0.66, 0.5, 520, power=0.85),
                   Figure(0.8, 0.74, 0.9, 0.24, "stand", INK, seed=97))
    aj.cam(0, 0, 0, 1.1).cam(d, 0, 0, 1.0)
    sc.append(aj)

    s, d = span(67, 67)
    ak = village_wide(d, lit=True, fog=22)
    ak.cam(0, 80, 0, 1.06).cam(d, -80, 0, 1.0)
    sc.append(ak)

    s, d = span(68, 69)
    al = Scene(d, Sky((18, 24, 48), (96, 86, 96), 0), Moon(1430, 200, 86),
               Hills(0.12, 0.58, 150, (54, 52, 68)),
               Treeline(0.3, 0.70, 15, 1.0, (40, 42, 56), seed=41),
               Huts(0.44, 0.77, 5, 1.0, (32, 34, 46), seed=51, lit=True),
               Bamboo(0.6, 9, 0.99, (16, 18, 28), seed=61),
               Ground(0.8, 0.86), Fog(0.9, 0.78, 5, (180, 180, 200), 24),
               Vignette(160), Grain(), fade_out=1.6)
    al.cam(0, -60, 0, 1.08).cam(d, 60, -20, 1.0)
    sc.append(al)
    return sc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--still", type=float, default=None)
    ap.add_argument("--out", default=str(HERE / "out" / "film.mp4"))
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--size", default="1920x1080")
    a = ap.parse_args()
    scenes = build()
    made = sum(s.dur for s in scenes)
    print(f"{len(scenes)} scenes, {made:.1f}s of picture for {TOTAL:.1f}s of voice", file=sys.stderr)
    if a.still is not None:
        t = a.still
        for s_ in scenes:
            if t < s_.dur:
                render_still(s_, t, str(HERE / "out" / f"still_{a.still:.0f}.png"))
                print(HERE / "out" / f"still_{a.still:.0f}.png")
                return
            t -= s_.dur
        sys.exit("past the end")
    (HERE / "out").mkdir(exist_ok=True)
    w, h = (int(x) for x in a.size.split("x"))
    render(scenes, a.out, fps=a.fps, audio=HERE / "audio" / "narration.m4a",
           workers=a.workers, size=(w, h))


if __name__ == "__main__":
    main()
