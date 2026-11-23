#!/usr/bin/env python3
"""
anim.py — a small hand-drawn-looking animation engine, everything drawn in code with Skia.

Nothing is traced, sampled or downloaded: a scene is built from shapes (sky, moon, hills,
bamboo, huts, a stepwell, figures, fog) that are parameterised and animated, so the art is
original and no footage or image rights are involved.

A film is a list of Scenes. A Scene owns layers; each layer has a parallax depth, so a camera
pan moves the far hills less than the near grass and the frame feels three-dimensional.

    from anim import *
    sc = Scene(8.0, Sky(), Hills(depth=0.25), Bamboo(depth=0.6), Ground())
    sc.cam(0, x=0, zoom=1.0).cam(8, x=300, zoom=1.08)
    render([sc], "out.mp4", fps=30)
"""
import math
import random
import subprocess
import sys
from dataclasses import dataclass, field

import skia

W, H = 1920, 1080

# ---------------------------------------------------------------- palette
NIGHT_TOP = (8, 12, 32)
NIGHT_BOT = (34, 48, 86)
DUSK_TOP = (26, 26, 54)
DUSK_BOT = (120, 78, 72)
MOON = (236, 243, 255)
LAMP = (255, 176, 74)
FAR = (26, 36, 68)
MID = (17, 25, 50)
NEAR = (9, 14, 30)
INK = (6, 9, 20)


def rgb(c, a=255):
    return skia.Color(c[0], c[1], c[2], a)


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))


def fill(c, a=255, blur=0.0):
    p = skia.Paint(Color=rgb(c, a), AntiAlias=True)
    if blur:
        p.setImageFilter(skia.ImageFilters.Blur(blur, blur))
    return p


def noise(seed):
    return random.Random(seed)


# ---------------------------------------------------------------- camera
@dataclass
class Key:
    t: float
    x: float = 0.0
    y: float = 0.0
    zoom: float = 1.0


class Camera:
    def __init__(self):
        self.keys = [Key(0)]

    def add(self, t, x=0.0, y=0.0, zoom=1.0):
        self.keys.append(Key(t, x, y, zoom))
        self.keys.sort(key=lambda k: k.t)
        return self

    def at(self, t):
        ks = self.keys
        if t <= ks[0].t:
            return ks[0]
        if t >= ks[-1].t:
            return ks[-1]
        for a, b in zip(ks, ks[1:]):
            if a.t <= t <= b.t:
                u = (t - a.t) / max(1e-6, b.t - a.t)
                u = u * u * (3 - 2 * u)                       # ease in and out
                return Key(t, lerp(a.x, b.x, u), lerp(a.y, b.y, u), lerp(a.zoom, b.zoom, u))
        return ks[-1]


# ---------------------------------------------------------------- layers
class Layer:
    depth = 0.5          # 0 = infinitely far (never moves), 1 = at the camera

    def __init__(self, depth=None, seed=0):
        if depth is not None:
            self.depth = depth
        self.seed = seed

    def draw(self, c, t, sc):
        ...


class Sky(Layer):
    depth = 0.0

    def __init__(self, top=NIGHT_TOP, bot=NIGHT_BOT, stars=170, seed=1):
        super().__init__(0.0, seed)
        self.top, self.bot, self.n = top, bot, stars

    def draw(self, c, t, sc):
        p = skia.Paint(Shader=skia.GradientShader.MakeLinear(
            [(0, -300), (0, H * 0.78)], [rgb(self.top), rgb(self.bot)]))
        c.drawRect(skia.Rect.MakeXYWH(-W, -H, 3 * W, 3 * H), p)
        r = noise(self.seed)
        for i in range(self.n):
            x, y = r.uniform(-W * 0.4, W * 1.4), r.uniform(-H * 0.2, H * 0.62)
            base = r.uniform(0.25, 1.0)
            tw = 0.75 + 0.25 * math.sin(t * r.uniform(0.6, 2.2) + i)
            c.drawCircle(x, y, r.uniform(0.9, 2.4), fill(MOON, int(190 * base * tw)))


class Moon(Layer):
    depth = 0.04

    def __init__(self, x=1430, y=210, r=92, seed=2):
        super().__init__(0.04, seed)
        self.x, self.y, self.r = x, y, r

    def draw(self, c, t, sc):
        for i, (rr, a) in enumerate(((5.2, 16), (3.4, 22), (2.1, 34), (1.35, 58))):
            c.drawCircle(self.x, self.y, self.r * rr, fill(MOON, a, blur=self.r * 0.8))
        c.drawCircle(self.x, self.y, self.r, fill(MOON, 252))
        r = noise(self.seed)
        for _ in range(7):                                    # craters, barely there
            a = r.uniform(0, 6.28); d = r.uniform(0, self.r * 0.62)
            c.drawCircle(self.x + math.cos(a) * d, self.y + math.sin(a) * d,
                         r.uniform(self.r * 0.07, self.r * 0.17), fill((206, 214, 232), 120))


class Hills(Layer):
    def __init__(self, depth=0.18, base=0.62, height=150, color=FAR, seed=3, rough=3):
        super().__init__(depth, seed)
        self.base, self.height, self.color, self.rough = base, height, color, rough

    def draw(self, c, t, sc):
        r = noise(self.seed)
        path = skia.Path()
        y0 = H * self.base
        path.moveTo(-W, H * 2)
        path.lineTo(-W, y0)
        amps = [(r.uniform(0.3, 1.0) * self.height, r.uniform(0.6, 2.4), r.uniform(0, 6.3))
                for _ in range(self.rough)]
        x = -W
        while x <= W * 2:
            y = y0
            for a, f, ph in amps:
                y -= a * math.sin(x / W * f * 3.1 + ph)
            path.lineTo(x, y)
            x += 24
        path.lineTo(W * 2, H * 2)
        path.close()
        c.drawPath(path, fill(self.color))


class Treeline(Layer):
    """A band of round-canopy trees along a horizon."""

    def __init__(self, depth=0.35, y=0.63, n=16, scale=1.0, color=MID, seed=4, sway=0.5):
        super().__init__(depth, seed)
        self.y, self.n, self.scale, self.color, self.sway = y, n, scale, color, sway

    def draw(self, c, t, sc):
        r = noise(self.seed)
        for i in range(self.n):
            x = lerp(-W * 0.3, W * 1.3, i / max(1, self.n - 1)) + r.uniform(-60, 60)
            h = r.uniform(110, 230) * self.scale
            w = h * r.uniform(0.55, 0.95)
            base = H * self.y + r.uniform(-14, 14)
            s = math.sin(t * r.uniform(0.5, 1.1) + i) * self.sway * 6
            c.drawRect(skia.Rect.MakeXYWH(x - w * 0.055, base - h * 0.55, w * 0.11, h * 0.6), fill(self.color))
            path = skia.Path()
            path.moveTo(x - w / 2, base - h * 0.45)
            path.cubicTo(x - w * 0.62, base - h * 1.12, x + w * 0.62 + s, base - h * 1.12,
                         x + w / 2, base - h * 0.45)
            path.cubicTo(x + w * 0.3, base - h * 0.2, x - w * 0.3, base - h * 0.2,
                         x - w / 2, base - h * 0.45)
            path.close()
            c.drawPath(path, fill(self.color))


class Bamboo(Layer):
    """Tall tapering stalks with leaf clusters — the signature of this village."""

    def __init__(self, depth=0.62, n=13, y=0.96, color=NEAR, seed=5, lean=1.0, x0=-0.1, x1=1.1):
        super().__init__(depth, seed)
        self.n, self.y, self.color, self.lean, self.x0, self.x1 = n, y, color, lean, x0, x1

    def draw(self, c, t, sc):
        r = noise(self.seed)
        for i in range(self.n):
            x = lerp(W * self.x0, W * self.x1, i / max(1, self.n - 1)) + r.uniform(-40, 40)
            h = r.uniform(H * 0.55, H * 1.05)
            base = H * self.y
            sway = math.sin(t * r.uniform(0.35, 0.8) + i * 1.3) * 26 * self.lean
            top = (x + sway, base - h)
            wd = r.uniform(7, 13)
            path = skia.Path()
            path.moveTo(x - wd, base)
            path.quadTo(x - wd * 0.5 + sway * 0.4, base - h * 0.55, top[0] - wd * 0.25, top[1])
            path.lineTo(top[0] + wd * 0.25, top[1])
            path.quadTo(x + wd * 0.5 + sway * 0.4, base - h * 0.55, x + wd, base)
            path.close()
            c.drawPath(path, fill(self.color))
            nodes = 7
            for k in range(nodes):
                u = 0.28 + 0.1 * k
                lx = lerp(x, top[0], u); ly = lerp(base, top[1], u)
                c.drawLine(lx - wd * 0.8, ly, lx + wd * 0.8, ly,
                           skia.Paint(Color=rgb(mix(self.color, (0, 0, 0), 0.5)), AntiAlias=True,
                                      StrokeWidth=wd * 0.5))
                for s_ in (-1, 1):
                    for j in range(2):
                        ln = r.uniform(70, 140) * (0.75 + 0.25 * u)
                        droop = r.uniform(0.25, 0.75)
                        tipx = lx + s_ * ln
                        tipy = ly + ln * droop * 0.55 - ln * 0.25
                        leaf = skia.Path()
                        leaf.moveTo(lx, ly)
                        leaf.quadTo(lx + s_ * ln * 0.45, ly - ln * 0.22, tipx, tipy)
                        leaf.quadTo(lx + s_ * ln * 0.4, ly + ln * 0.12, lx, ly)
                        leaf.close()
                        c.drawPath(leaf, fill(self.color))
                        ly += r.uniform(6, 16)


class Huts(Layer):
    """Thatched houses with windows that flicker like oil light."""

    def __init__(self, depth=0.45, y=0.74, n=4, scale=1.0, color=MID, seed=6, lit=True, x0=0.05, x1=0.95):
        super().__init__(depth, seed)
        self.y, self.n, self.scale, self.color, self.lit, self.x0, self.x1 = y, n, scale, color, lit, x0, x1

    def draw(self, c, t, sc):
        r = noise(self.seed)
        for i in range(self.n):
            x = lerp(W * self.x0, W * self.x1, i / max(1, self.n - 1)) + r.uniform(-50, 50)
            bw = r.uniform(210, 320) * self.scale
            bh = bw * r.uniform(0.5, 0.7)
            base = H * self.y + r.uniform(-16, 16)
            body = skia.Rect.MakeXYWH(x - bw / 2, base - bh, bw, bh)
            c.drawRect(body, fill(self.color))
            roof = skia.Path()
            roof.moveTo(x - bw * 0.62, base - bh)
            roof.quadTo(x, base - bh - bw * 0.52, x + bw * 0.62, base - bh)
            roof.close()
            c.drawPath(roof, fill(mix(self.color, INK, 0.35)))
            if self.lit:
                fl = 0.72 + 0.28 * math.sin(t * r.uniform(5, 11) + i * 2.1) * math.sin(t * 2.7 + i)
                ww, wh = bw * 0.17, bh * 0.3
                wx, wy = x - ww / 2 + r.uniform(-bw * 0.18, bw * 0.18), base - bh * 0.66
                c.drawRect(skia.Rect.MakeXYWH(wx - ww, wy - wh, ww * 3, wh * 3),
                           fill(LAMP, int(60 * fl), blur=34))
                c.drawRect(skia.Rect.MakeXYWH(wx, wy, ww, wh), fill(LAMP, int(236 * fl)))


class Ground(Layer):
    def __init__(self, depth=0.8, y=0.84, color=NEAR, seed=7, grass=True):
        super().__init__(depth, seed)
        self.y, self.color, self.grass = y, color, grass

    def draw(self, c, t, sc):
        p = skia.Paint(Shader=skia.GradientShader.MakeLinear(
            [(0, H * self.y), (0, H * 1.3)], [rgb(mix(self.color, (0, 0, 0), 0.1)), rgb(INK)]))
        c.drawRect(skia.Rect.MakeXYWH(-W, H * self.y, 3 * W, H), p)
        if self.grass:
            r = noise(self.seed)
            for _ in range(240):
                x = r.uniform(-W * 0.3, W * 1.3); y = H * self.y + r.uniform(0, H * 0.2)
                h = r.uniform(8, 30) * (1 + (y - H * self.y) / (H * 0.2))
                s = math.sin(t * r.uniform(0.6, 1.6) + x * 0.01) * 5
                bl = skia.Path(); bl.moveTo(x, y); bl.quadTo(x + s, y - h * 0.6, x + s * 1.8, y - h)
                c.drawPath(bl, skia.Paint(Color=rgb(INK, 190), AntiAlias=True,
                                          Style=skia.Paint.kStroke_Style, StrokeWidth=r.uniform(1.5, 3)))


class Stepwell(Layer):
    """Receding arches down into the dark — the baawdi."""

    def __init__(self, depth=0.55, cx=0.5, cy=0.52, w=0.52, rows=6, color=MID, seed=8):
        super().__init__(depth, seed)
        self.cx, self.cy, self.w, self.rows, self.color = cx, cy, w, rows, color

    def draw(self, c, t, sc):
        """Seen from the rim: ground at the top, then storeys of arcade dropping away into the dark."""
        cx, cy, ww = W * self.cx, H * self.cy, W * self.w
        deep = H * 0.52
        # ground the well sits in, so it reads as a hole and not a building
        c.drawRect(skia.Rect.MakeXYWH(-W, cy - H, 3 * W, H), fill(mix(self.color, INK, 0.55)))
        mouth_b = ww * 0.42                                   # the pit narrows as it goes down
        # far wall: storeys of arcade, each darker
        for i in range(self.rows):
            u = i / (self.rows - 1)
            y = cy + deep * (u ** 1.25)
            hw = lerp(ww, mouth_b, u ** 1.1) / 2
            bh = deep / self.rows * (1.15 - u * 0.45)
            col = mix(self.color, (0, 0, 0), 0.12 + u * 0.82)
            c.drawRect(skia.Rect.MakeXYWH(cx - hw, y, hw * 2, bh), fill(col))
            c.drawLine(cx - hw, y, cx + hw, y,
                       skia.Paint(Color=rgb(mix(col, MOON, 0.3 * (1 - u))), AntiAlias=True, StrokeWidth=4))
            n = max(2, 6 - i)
            span = hw * 1.7
            aw = span / (n * 1.6)
            for j in range(n):
                ax = cx - span / 2 + span * (j + 0.5) / n
                arch = skia.Path()
                arch.moveTo(ax - aw / 2, y + bh)
                arch.lineTo(ax - aw / 2, y + bh * 0.45)
                arch.quadTo(ax, y + bh * 0.02, ax + aw / 2, y + bh * 0.45)
                arch.lineTo(ax + aw / 2, y + bh)
                arch.close()
                c.drawPath(arch, fill((0, 0, 0), int(200 + 55 * u)))
        # side walls closing in, left and right
        for s_ in (-1, 1):
            wall = skia.Path()
            wall.moveTo(cx + s_ * ww / 2, cy)
            wall.lineTo(cx + s_ * W, cy)
            wall.lineTo(cx + s_ * W, cy + deep + H * 0.4)
            wall.lineTo(cx + s_ * mouth_b / 2, cy + deep + H * 0.4)
            wall.lineTo(cx + s_ * mouth_b / 2, cy + deep)
            wall.close()
            c.drawPath(wall, fill(mix(self.color, INK, 0.62)))
            c.drawLine(cx + s_ * ww / 2, cy, cx + s_ * mouth_b / 2, cy + deep,
                       skia.Paint(Color=rgb(mix(self.color, MOON, 0.18)), AntiAlias=True, StrokeWidth=5))
        # the shaft itself
        c.drawRect(skia.Rect.MakeXYWH(cx - mouth_b / 2, cy + deep, mouth_b, H * 0.4), fill((0, 0, 0), 252))
        # stone rim at the near edge
        c.drawRect(skia.Rect.MakeXYWH(cx - ww / 2 - 30, cy - 26, ww + 60, 30),
                   fill(mix(self.color, MOON, 0.12)))


class Figure(Layer):
    """A walking silhouette. kind: walk, stand, cycle, shadow."""

    def __init__(self, depth=0.75, x=0.5, y=0.86, h=0.2, kind="walk", color=INK,
                 face=1, speed=1.0, seed=9, alpha=255):
        super().__init__(depth, seed)
        self.x, self.y, self.h, self.kind, self.color = x, y, h, kind, color
        self.face, self.speed, self.alpha = face, speed, alpha

    def draw(self, c, t, sc):
        x, y, h = W * self.x, H * self.y, H * self.h
        a = self.alpha
        col = self.color
        if self.kind == "shadow":
            drift = math.sin(t * 0.8) * h * 0.02
            hem = h * 0.06
            body = skia.Path()
            body.moveTo(x - h * 0.26, y)                                  # left hem
            body.cubicTo(x - h * 0.3, y - h * 0.5, x - h * 0.2 + drift, y - h * 0.82,
                         x - h * 0.13 + drift, y - h * 0.98)              # up to the shoulder
            body.quadTo(x - h * 0.12 + drift, y - h * 1.2, x + drift, y - h * 1.26)   # hood crown
            body.quadTo(x + h * 0.12 + drift, y - h * 1.2, x + h * 0.13 + drift, y - h * 0.98)
            body.cubicTo(x + h * 0.2 + drift, y - h * 0.82, x + h * 0.3, y - h * 0.5,
                         x + h * 0.26, y)
            r = noise(self.seed)
            xx = x + h * 0.26                                              # torn hem
            while xx > x - h * 0.26:
                xx -= h * 0.052
                body.lineTo(xx + h * 0.026, y - hem * r.uniform(0.2, 1.0) + math.sin(t * 2 + xx) * 3)
                body.lineTo(xx, y)
            body.close()
            c.drawPath(body, fill(col, a))
            c.drawPath(body, fill(col, int(a * 0.5), blur=14))
            hood = skia.Path()                                             # the dark inside the hood
            hood.moveTo(x - h * 0.075 + drift, y - h * 1.14)
            hood.quadTo(x + drift, y - h * 1.21, x + h * 0.075 + drift, y - h * 1.14)
            hood.quadTo(x + drift, y - h * 1.0, x - h * 0.075 + drift, y - h * 1.14)
            hood.close()
            c.drawPath(hood, fill((0, 0, 0), min(255, a)))
            glow = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(t * 2.3))
            for s_ in (-1, 1):                                             # two pale eyes
                ex, ey = x + s_ * h * 0.032 + drift, y - h * 1.1
                c.drawCircle(ex, ey, h * 0.019, fill((206, 222, 255), int(a * glow)))
                c.drawCircle(ex, ey, h * 0.05, fill((150, 180, 255), int(a * 0.30 * glow), blur=10))
            return
        ph = t * 6.5 * self.speed
        bob = abs(math.sin(ph)) * h * 0.018
        hip = y - h * 0.46 - bob
        sh = y - h * 0.80 - bob
        line = lambda x1, y1, x2, y2, wd: c.drawLine(
            x1, y1, x2, y2, skia.Paint(Color=rgb(col, a), AntiAlias=True,
                                       Style=skia.Paint.kStroke_Style, StrokeWidth=wd,
                                       StrokeCap=skia.Paint.kRound_Cap))
        if self.kind == "cycle":
            wr = h * 0.2
            wy = y - wr
            for s in (-1, 1):
                c.drawCircle(x + s * h * 0.34, wy, wr,
                             skia.Paint(Color=rgb(col, a), AntiAlias=True,
                                        Style=skia.Paint.kStroke_Style, StrokeWidth=h * 0.035))
                for k in range(6):
                    ang = ph * 0.8 + k * 1.05
                    c.drawLine(x + s * h * 0.34, wy,
                               x + s * h * 0.34 + math.cos(ang) * wr, wy + math.sin(ang) * wr,
                               skia.Paint(Color=rgb(col, int(a * 0.8)), AntiAlias=True, StrokeWidth=h * 0.012))
            line(x - h * 0.34, wy, x + h * 0.06, y - h * 0.5, h * 0.03)
            line(x + h * 0.06, y - h * 0.5, x + h * 0.34, wy, h * 0.03)
            line(x - h * 0.1, y - h * 0.5, x + h * 0.2, y - h * 0.62, h * 0.03)
            body_top = y - h * 0.95
            line(x - h * 0.02, y - h * 0.52, x + h * 0.08, body_top, h * 0.085)
            c.drawCircle(x + h * 0.1, body_top - h * 0.1, h * 0.1, fill(col, a))
            line(x + h * 0.08, y - h * 0.86, x + h * 0.26, y - h * 0.62, h * 0.05)
            for s in (1, -1):
                kx = x + h * 0.04 + math.cos(ph * 0.8 + (0 if s > 0 else 3.14)) * h * 0.1
                ky = y - h * 0.44 + math.sin(ph * 0.8 + (0 if s > 0 else 3.14)) * h * 0.1
                line(x - h * 0.0, y - h * 0.52, kx, ky, h * 0.055)
            return
        swing = math.sin(ph) * (0.22 if self.kind == "walk" else 0.02)
        torso = skia.Path()                                     # tapered torso with shoulders
        torso.moveTo(x - h * 0.075, hip)
        torso.cubicTo(x - h * 0.085, hip - h * 0.2, x - h * 0.105, sh + h * 0.06, x - h * 0.1, sh)
        torso.lineTo(x + h * 0.1, sh)
        torso.cubicTo(x + h * 0.105, sh + h * 0.06, x + h * 0.085, hip - h * 0.2, x + h * 0.075, hip)
        torso.close()
        c.drawPath(torso, fill(col, a))
        line(x, sh, x, sh - h * 0.05, h * 0.045)                # neck
        c.drawCircle(x, sh - h * 0.115, h * 0.082, fill(col, a))
        for s, ds in ((1, swing), (-1, -swing)):
            line(x, hip, x + self.face * ds * h * 0.42, y, h * 0.062)     # legs
            line(x, sh - h * 0.02, x + self.face * -ds * h * 0.3, hip + h * 0.12, h * 0.05)   # arms


class Lantern(Layer):
    """A warm light source: glow, and a small flame."""

    def __init__(self, depth=0.75, x=0.5, y=0.78, r=260, color=LAMP, seed=10, power=1.0):
        super().__init__(depth, seed)
        self.x, self.y, self.r, self.color, self.power = x, y, r, color, power

    def draw(self, c, t, sc):
        x, y = W * self.x, H * self.y
        fl = (0.8 + 0.2 * math.sin(t * 9.1) * math.sin(t * 3.3)) * self.power
        for rr, a in ((1.0, 26), (0.6, 40), (0.32, 74), (0.14, 150)):
            c.drawCircle(x, y, self.r * rr, fill(self.color, int(a * fl), blur=self.r * 0.3))
        c.drawCircle(x, y, 7 * fl + 4, fill((255, 236, 198), int(250 * fl)))


class Fog(Layer):
    def __init__(self, depth=0.9, y=0.78, bands=5, color=(150, 170, 210), alpha=26, seed=11, speed=14):
        super().__init__(depth, seed)
        self.y, self.bands, self.color, self.alpha, self.speed = y, bands, color, alpha, speed

    def draw(self, c, t, sc):
        r = noise(self.seed)
        for i in range(self.bands):
            yy = H * self.y + i * 34 + math.sin(t * 0.4 + i) * 10
            hh = r.uniform(50, 120)
            off = (t * self.speed * r.uniform(0.4, 1.3) + i * 400) % (W * 2) - W * 0.5
            c.drawOval(skia.Rect.MakeXYWH(off - W * 0.5, yy, W * 1.6, hh),
                       fill(self.color, self.alpha, blur=60))


class Rain(Layer):
    def __init__(self, depth=1.0, n=220, color=(170, 190, 230), seed=12, speed=1500, alpha=90):
        super().__init__(depth, seed)
        self.n, self.color, self.speed, self.alpha = n, color, speed, alpha

    def draw(self, c, t, sc):
        r = noise(self.seed)
        p = skia.Paint(Color=rgb(self.color, self.alpha), AntiAlias=True,
                       Style=skia.Paint.kStroke_Style, StrokeWidth=2)
        for _ in range(self.n):
            x0 = r.uniform(-W * 0.3, W * 1.3); ph = r.uniform(0, 1)
            y = ((t + ph) * self.speed * r.uniform(0.8, 1.2)) % (H * 1.4) - H * 0.2
            ln = r.uniform(18, 46)
            c.drawLine(x0, y, x0 - 10, y + ln, p)


class Vignette(Layer):
    depth = 0.0

    def __init__(self, strength=190, grade=None, seed=13):
        super().__init__(0.0, seed)
        self.strength, self.grade = strength, grade

    def draw(self, c, t, sc):
        if self.grade:
            c.drawRect(skia.Rect.MakeWH(W, H), fill(self.grade[0], self.grade[1]))
        p = skia.Paint(Shader=skia.GradientShader.MakeRadial(
            (W / 2, H / 2), W * 0.72,
            [skia.Color(0, 0, 0, 0), skia.Color(0, 0, 0, self.strength)], [0.45, 1.0]))
        c.drawRect(skia.Rect.MakeWH(W, H), p)


class Flash(Layer):
    """A light going out, or a sudden white — on a timetable of (t, value) pairs."""
    depth = 0.0

    def __init__(self, keys, color=(0, 0, 0)):
        super().__init__(0.0, 0)
        self.keys, self.color = sorted(keys), color

    def draw(self, c, t, sc):
        v = 0.0
        ks = self.keys
        if t <= ks[0][0]:
            v = ks[0][1]
        elif t >= ks[-1][0]:
            v = ks[-1][1]
        else:
            for a, b in zip(ks, ks[1:]):
                if a[0] <= t <= b[0]:
                    u = (t - a[0]) / max(1e-6, b[0] - a[0])
                    v = lerp(a[1], b[1], u)
                    break
        if v > 0.002:
            c.drawRect(skia.Rect.MakeWH(W, H), fill(self.color, int(255 * min(1, v))))


class Grain(Layer):
    depth = 0.0

    def __init__(self, amount=13, seed=14):
        super().__init__(0.0, seed)
        self.amount = amount

    def draw(self, c, t, sc):
        r = noise(self.seed + int(t * 24))
        for _ in range(900):
            c.drawRect(skia.Rect.MakeXYWH(r.uniform(0, W), r.uniform(0, H), 2.4, 2.4),
                       fill((255, 255, 255), r.randint(3, self.amount)))


# ---------------------------------------------------------------- scene
@dataclass
class Scene:
    dur: float
    layers: list = field(default_factory=list)
    camera: Camera = field(default_factory=Camera)
    fade_in: float = 0.4
    fade_out: float = 0.4

    def __init__(self, dur, *layers, fade_in=0.4, fade_out=0.4):
        self.dur, self.layers = dur, list(layers)
        self.camera, self.fade_in, self.fade_out = Camera(), fade_in, fade_out

    def cam(self, t, x=0.0, y=0.0, zoom=1.0):
        self.camera.add(t, x, y, zoom)
        return self

    def add(self, *layers):
        self.layers.extend(layers)
        return self

    def draw(self, c, t):
        k = self.camera.at(t)
        c.clear(rgb(INK))
        for L in sorted(self.layers, key=lambda l: l.depth):
            c.save()
            c.translate(W / 2, H / 2)
            z = 1 + (k.zoom - 1) * (0.4 + L.depth)
            c.scale(z, z)
            c.translate(-W / 2 - k.x * L.depth, -H / 2 - k.y * L.depth)
            L.draw(c, t, self)
            c.restore()
        if self.fade_in and t < self.fade_in:
            c.drawRect(skia.Rect.MakeWH(W, H), fill((0, 0, 0), int(255 * (1 - t / self.fade_in))))
        if self.fade_out and t > self.dur - self.fade_out:
            u = (t - (self.dur - self.fade_out)) / self.fade_out
            c.drawRect(skia.Rect.MakeWH(W, H), fill((0, 0, 0), int(255 * min(1, u))))


# ---------------------------------------------------------------- render
def _frames(scenes, fps):
    for sc in scenes:
        n = max(1, round(sc.dur * fps))
        for i in range(n):
            yield sc, i / fps


def render_still(scene, t, path, size=(W, H)):
    surf = skia.Surface(W, H)
    with surf as c:
        scene.draw(c, t)
    img = surf.makeImageSnapshot()
    if size != (W, H):
        img = img.resize(*size)
    img.save(path, skia.kPNG)


def _worker(args):
    import pickle
    scenes, fps, i0, i1, out, size = args
    scenes = pickle.loads(scenes)
    surf = skia.Surface(W, H)
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
         "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
         "-pix_fmt", "yuv420p", "-vf", f"scale={size[0]}:{size[1]}:flags=lanczos", out],
        stdin=subprocess.PIPE)
    for i, (sc, t) in enumerate(_frames(scenes, fps)):
        if not (i0 <= i < i1):
            continue
        with surf as c:
            sc.draw(c, t)
        ff.stdin.write(surf.makeImageSnapshot().tobytes())
    ff.stdin.close()
    ff.wait()
    return out


def render(scenes, out, fps=30, audio=None, workers=4, size=(W, H), tmp="/tmp/anim"):
    import multiprocessing as mp
    import os
    import pathlib
    import pickle
    pathlib.Path(tmp).mkdir(parents=True, exist_ok=True)
    total = sum(max(1, round(s.dur * fps)) for s in scenes)
    blob = pickle.dumps(scenes)
    step = math.ceil(total / workers)
    jobs = [(blob, fps, i * step, min(total, (i + 1) * step), f"{tmp}/part{i:03d}.mp4", size)
            for i in range(workers) if i * step < total]
    print(f"{total} frames, {len(jobs)} workers", file=sys.stderr)
    with mp.Pool(len(jobs)) as pool:
        parts = pool.map(_worker, jobs)
    lst = f"{tmp}/list.txt"
    pathlib.Path(lst).write_text("".join(f"file '{p}'\n" for p in parts))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst]
    if audio:
        cmd += ["-i", str(audio), "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "copy", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    for p in parts:
        os.remove(p)
    print(f"wrote {out}", file=sys.stderr)
    return out


# ---------------------------------------------------------------- interiors and props
class StoneWall(Layer):
    """An interior wall of block courses with a deep arch niche — the inside of the well."""

    def __init__(self, depth=0.3, color=(48, 44, 60), seed=20, arch=True, y=0.0):
        super().__init__(depth, seed)
        self.color, self.arch, self.y = color, arch, y

    def draw(self, c, t, sc):
        r = noise(self.seed)
        c.drawRect(skia.Rect.MakeXYWH(-W, -H, 3 * W, 3 * H), fill(self.color))
        bh = 86
        y = -H * 0.2 + H * self.y
        row = 0
        while y < H * 1.2:
            off = (row % 2) * 110
            x = -W * 0.3 + off
            while x < W * 1.3:
                bw = r.uniform(170, 240)
                c.drawRect(skia.Rect.MakeXYWH(x + 4, y + 4, bw - 8, bh - 8),
                           fill(mix(self.color, (0, 0, 0), r.uniform(0.05, 0.3))))
                x += bw
            y += bh
            row += 1
        if self.arch:
            ax, aw, ah = W * 0.5, W * 0.34, H * 0.62
            p = skia.Path()
            p.moveTo(ax - aw / 2, H * 0.95)
            p.lineTo(ax - aw / 2, H * 0.95 - ah * 0.55)
            p.quadTo(ax, H * 0.95 - ah * 1.05, ax + aw / 2, H * 0.95 - ah * 0.55)
            p.lineTo(ax + aw / 2, H * 0.95)
            p.close()
            c.drawPath(p, fill((0, 0, 0), 236))


class Machine(Layer):
    """A diesel pump: body, turning flywheel, pipe, and a breath of exhaust."""

    def __init__(self, depth=0.7, x=0.5, y=0.82, s=1.0, color=(26, 26, 34), seed=21, running=True):
        super().__init__(depth, seed)
        self.x, self.y, self.s, self.color, self.running = x, y, s, color, running

    def draw(self, c, t, sc):
        x, y, s = W * self.x, H * self.y, 260 * self.s
        c.drawRect(skia.Rect.MakeXYWH(x - s * 0.5, y - s * 0.46, s, s * 0.46), fill(self.color))
        c.drawRect(skia.Rect.MakeXYWH(x - s * 0.56, y - s * 0.56, s * 1.12, s * 0.12),
                   fill(mix(self.color, MOON, 0.1)))
        ang = t * (7.0 if self.running else 0.0)
        fx, fy, fr = x + s * 0.44, y - s * 0.22, s * 0.3
        c.drawCircle(fx, fy, fr, skia.Paint(Color=rgb(mix(self.color, MOON, 0.18)), AntiAlias=True,
                                            Style=skia.Paint.kStroke_Style, StrokeWidth=s * 0.07))
        for k in range(5):
            a = ang + k * 1.256
            c.drawLine(fx, fy, fx + math.cos(a) * fr, fy + math.sin(a) * fr,
                       skia.Paint(Color=rgb(mix(self.color, MOON, 0.12)), AntiAlias=True, StrokeWidth=s * 0.03))
        c.drawCircle(fx, fy, s * 0.05, fill(mix(self.color, MOON, 0.25)))
        pipe = skia.Path()                                    # hose running off to the side
        pipe.moveTo(x - s * 0.5, y - s * 0.3)
        pipe.cubicTo(x - s * 1.2, y - s * 0.26, x - s * 1.4, y - s * 0.02, x - s * 2.1, y - s * 0.06)
        c.drawPath(pipe, skia.Paint(Color=rgb(mix(self.color, (0, 0, 0), 0.3)), AntiAlias=True,
                                    Style=skia.Paint.kStroke_Style, StrokeWidth=s * 0.09,
                                    StrokeCap=skia.Paint.kRound_Cap))
        if self.running:
            r = noise(self.seed)
            for k in range(4):
                ph = (t * 0.8 + k * 0.25) % 1.0
                c.drawCircle(x + s * 0.1 + ph * s * 0.3, y - s * 0.6 - ph * s * 0.9,
                             s * (0.06 + ph * 0.16), fill((120, 125, 140), int(70 * (1 - ph)), blur=20))


class Bundles(Layer):
    """Stacked coils of wire under a tarpaulin — what the well was really hiding."""

    def __init__(self, depth=0.72, x=0.3, y=0.86, n=7, s=1.0, color=(44, 34, 26), seed=22, tarp=True):
        super().__init__(depth, seed)
        self.x, self.y, self.n, self.s, self.color, self.tarp = x, y, n, s, color, tarp

    def draw(self, c, t, sc):
        r = noise(self.seed)
        x, y, s = W * self.x, H * self.y, 120 * self.s
        pos = []
        for i in range(self.n):
            col = i % 3
            row = i // 3
            cx = x + (col - 1) * s * 1.15 + r.uniform(-8, 8)
            cy = y - row * s * 0.78
            pos.append((cx, cy))
            c.drawOval(skia.Rect.MakeXYWH(cx - s * 0.55, cy - s * 0.42, s * 1.1, s * 0.84),
                       fill(mix(self.color, (0, 0, 0), 0.2)))
            c.drawOval(skia.Rect.MakeXYWH(cx - s * 0.26, cy - s * 0.2, s * 0.52, s * 0.4),
                       fill((0, 0, 0), 215))
            c.drawArc(skia.Rect.MakeXYWH(cx - s * 0.55, cy - s * 0.42, s * 1.1, s * 0.84),
                      200, 120, False,
                      skia.Paint(Color=rgb((188, 112, 56), 165), AntiAlias=True,
                                 Style=skia.Paint.kStroke_Style, StrokeWidth=s * 0.07))
            for k in range(4):
                c.drawOval(skia.Rect.MakeXYWH(cx - s * (0.5 - k * 0.05), cy - s * (0.37 - k * 0.04),
                                              s * (1.0 - k * 0.1), s * (0.74 - k * 0.08)),
                           skia.Paint(Color=rgb(mix(self.color, MOON, 0.16), 120), AntiAlias=True,
                                      Style=skia.Paint.kStroke_Style, StrokeWidth=2))
        if self.tarp and pos:
            xs = [p[0] for p in pos]; ys = [p[1] for p in pos]
            tp = skia.Path()
            tp.moveTo(min(xs) - s * 0.8, y + s * 0.45)
            tp.quadTo(x, min(ys) - s * 1.25, max(xs) + s * 0.8, y + s * 0.45)
            tp.close()
            c.drawPath(tp, fill((30, 34, 40), 215))
            c.drawPath(tp, skia.Paint(Color=rgb((90, 96, 110), 70), AntiAlias=True,
                                      Style=skia.Paint.kStroke_Style, StrokeWidth=3))


class Bound(Layer):
    """A person sitting against a wall, hands tied — seen by torchlight."""

    def __init__(self, depth=0.76, x=0.5, y=0.88, h=0.22, color=INK, seed=23):
        super().__init__(depth, seed)
        self.x, self.y, self.h, self.color = x, y, h, color

    def draw(self, c, t, sc):
        x, y, h = W * self.x, H * self.y, H * self.h
        br = math.sin(t * 1.6) * h * 0.012                      # breathing
        body = skia.Path()
        body.moveTo(x - h * 0.3, y)
        body.lineTo(x - h * 0.16, y - h * 0.62 + br)
        body.quadTo(x, y - h * 0.72 + br, x + h * 0.16, y - h * 0.62 + br)
        body.lineTo(x + h * 0.3, y)
        body.close()
        c.drawPath(body, fill(self.color))
        c.drawCircle(x + h * 0.02, y - h * 0.8 + br, h * 0.12, fill(self.color))
        c.drawLine(x - h * 0.3, y - h * 0.1, x + h * 0.34, y - h * 0.12,
                   skia.Paint(Color=rgb(mix(self.color, MOON, 0.3)), AntiAlias=True,
                              Style=skia.Paint.kStroke_Style, StrokeWidth=h * 0.035))
        c.drawLine(x - h * 0.26, y - h * 0.4 + br, x + h * 0.3, y - h * 0.42 + br,
                   skia.Paint(Color=rgb(mix(self.color, MOON, 0.22)), AntiAlias=True,
                              Style=skia.Paint.kStroke_Style, StrokeWidth=h * 0.03))


class Prints(Layer):
    """Boot prints pressed into wet ground, appearing one after another."""

    def __init__(self, depth=0.85, y=0.72, n=7, t0=0.0, step=0.28, color=(14, 16, 26), seed=24):
        super().__init__(depth, seed)
        self.y, self.n, self.t0, self.step, self.color = y, n, t0, step, color

    def draw(self, c, t, sc):
        r = noise(self.seed)
        for i in range(self.n):
            if t < self.t0 + i * self.step:
                break
            u = i / max(1, self.n - 1)
            x = lerp(W * 0.12, W * 0.9, u) + r.uniform(-20, 20)
            y = H * self.y + u * H * 0.16 + (0 if i % 2 else H * 0.03)
            s = 46 + u * 46
            c.save(); c.translate(x, y); c.rotate(r.uniform(-14, 14))
            c.drawRoundRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-s * 0.32, -s * 0.8, s * 0.64, s * 1.1),
                                                  s * 0.22, s * 0.3), fill(self.color, 235))
            c.drawRoundRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-s * 0.28, s * 0.42, s * 0.56, s * 0.42),
                                                  s * 0.16, s * 0.16), fill(self.color, 235))
            c.restore()
