#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import time
import wave
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

FPS = 24
DURATION = 60.0
PC_SIZE = (1280, 720)
MOBILE_SIZE = (720, 1280)

FONT_REG_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]
FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
]

PALETTE = {
    "deep": (10, 70, 54),
    "green": (32, 150, 79),
    "lime": (142, 208, 70),
    "cream": (255, 248, 222),
    "yellow": (255, 215, 55),
    "orange": (245, 120, 46),
    "red": (227, 65, 48),
    "blue": (50, 126, 210),
    "pink": (237, 99, 151),
    "brown": (120, 73, 38),
    "white": (255, 255, 255),
    "black": (24, 28, 30),
}

UTTERANCES = [
    (0.55, 2.70, "クワガタ たんけんたい！"),
    (2.90, 5.75, "もりへ、さがしに いこう！"),
    (6.65, 9.20, "クワガタ、どこかな？"),
    (9.45, 11.65, "あっ、みつけた！"),
    (12.10, 15.10, "ほんものの クワガタが、うごいてる！"),
    (15.25, 18.15, "きの うえを、のぼっているよ。"),
    (18.30, 21.70, "おおきな あご、かっこいい！"),
    (23.10, 26.10, "これは、ノコギリクワガタ。"),
    (26.30, 29.75, "ぎざぎざの おおあごが、めじるし！"),
    (29.95, 33.25, "からだは、あかちゃいろの ことも あるよ。"),
    (34.05, 37.25, "にほんの、いろいろな もりに いるよ。"),
    (37.45, 40.55, "コナラや クヌギの じゅえきが、だいすき！"),
    (40.70, 43.65, "あるいている すがたも、みてみよう。"),
    (44.10, 46.75, "ここで クイズ！"),
    (46.95, 50.45, "ぎざぎざの おおあごは、どっち？"),
    (52.70, 55.85, "せいかいは、ビー！ ノコギリクワガタ！"),
    (56.75, 59.70, "つぎは、ミヤマや ヒラタも みてみよう！"),
]

SFX_EVENTS = [
    (0.20, "sparkle"), (0.55, "pop"), (2.85, "whoosh"),
    (6.45, "whoosh"), (9.35, "pop"), (11.90, "whoosh"),
    (18.10, "ding"), (22.85, "whoosh"), (26.20, "rattle"),
    (33.90, "whoosh"), (40.50, "whoosh"), (43.95, "quiz"),
    (50.70, "tick"), (51.45, "tick"), (52.20, "tick"),
    (52.65, "answer"), (56.55, "whoosh"), (59.45, "sparkle"),
]


def pick_font(candidates: list[str]) -> str:
    for path in candidates:
        if Path(path).exists():
            return path
    return "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


FONT_REG = pick_font(FONT_REG_CANDIDATES)
FONT_BOLD = pick_font(FONT_BOLD_CANDIDATES)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, max(8, int(size)))


def run(cmd: list[str], *, capture: bool = False, check: bool = True) -> str:
    print("RUN:", " ".join(str(x) for x in cmd), flush=True)
    cp = subprocess.run(cmd, text=True, capture_output=capture, check=check)
    return cp.stdout if capture else ""


def probe_duration(path: Path) -> float:
    out = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ], capture=True)
    return float(out.strip())


def ease_out_back(x: float) -> float:
    x = max(0.0, min(1.0, x))
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ease_in_out(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def saw(x: float) -> float:
    return x - math.floor(x)


def fit_cover(img: Image.Image, size: tuple[int, int], crop=(0.5, 0.5), zoom: float = 1.0) -> Image.Image:
    tw, th = size
    src = img.convert("RGB")
    scale = max(tw / src.width, th / src.height) * zoom
    nw, nh = max(1, int(src.width * scale)), max(1, int(src.height * scale))
    src = src.resize((nw, nh), Image.Resampling.LANCZOS)
    cx = int((nw - tw) * crop[0])
    cy = int((nh - th) * crop[1])
    cx = max(0, min(max(0, nw - tw), cx))
    cy = max(0, min(max(0, nh - th), cy))
    return src.crop((cx, cy, cx + tw, cy + th)).convert("RGBA")


def fit_contain(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    src = img.convert("RGBA")
    src.thumbnail(size, Image.Resampling.LANCZOS)
    return src


def rounded_crop(img: Image.Image, radius: int) -> Image.Image:
    src = img.convert("RGBA")
    mask = Image.new("L", src.size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, src.width - 1, src.height - 1), radius=max(2, radius), fill=255)
    src.putalpha(mask)
    return src


def paste_card(
    base: Image.Image,
    img: Image.Image,
    center: tuple[float, float],
    size: tuple[float, float],
    *,
    crop=(0.5, 0.5),
    angle: float = 0.0,
    radius: int = 26,
    border: int = 0,
    border_fill=(255, 255, 255, 255),
    shadow: bool = True,
    zoom: float = 1.0,
) -> None:
    w, h = max(2, int(size[0])), max(2, int(size[1]))
    layer = fit_cover(img, (w, h), crop=crop, zoom=zoom)
    layer = rounded_crop(layer, radius)
    if border > 0:
        canvas = Image.new("RGBA", (w + border * 2, h + border * 2), (0, 0, 0, 0))
        bd = ImageDraw.Draw(canvas)
        bd.rounded_rectangle((0, 0, canvas.width - 1, canvas.height - 1), radius=radius + border, fill=border_fill)
        canvas.alpha_composite(layer, (border, border))
        layer = canvas
    if angle:
        layer = layer.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
    x = int(center[0] - layer.width / 2)
    y = int(center[1] - layer.height / 2)
    if shadow:
        sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
        sm = layer.getchannel("A")
        sim = Image.new("RGBA", layer.size, (0, 0, 0, 110))
        sim.putalpha(sm.point(lambda p: int(p * 0.55)))
        sh.alpha_composite(sim, (x + 10, y + 14))
        sh = sh.filter(ImageFilter.GaussianBlur(max(5, int(min(w, h) * 0.035))))
        base.alpha_composite(sh)
    base.alpha_composite(layer, (x, y))


def draw_text_center(
    base: Image.Image,
    text: str,
    center: tuple[float, float],
    size: int,
    fill,
    *,
    stroke: int = 5,
    stroke_fill=(255, 255, 255),
    max_width: float | None = None,
    scale: float = 1.0,
    shadow: bool = True,
) -> None:
    fsize = max(8, int(size * scale))
    f = font(fsize, True)
    probe = ImageDraw.Draw(base)
    while max_width and fsize > 12 and probe.textbbox((0, 0), text, font=f, stroke_width=stroke)[2] > max_width:
        fsize -= 2
        f = font(fsize, True)
    bbox = probe.textbbox((0, 0), text, font=f, stroke_width=stroke)
    w = bbox[2] - bbox[0] + 34
    h = bbox[3] - bbox[1] + 34
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if shadow:
        d.text((18, 20), text, font=f, fill=(0, 0, 0, 100), stroke_width=stroke, stroke_fill=(0, 0, 0, 100))
    d.text((15, 15), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
    base.alpha_composite(layer, (int(center[0] - w / 2), int(center[1] - h / 2)))


def draw_pill(
    base: Image.Image,
    text: str,
    center: tuple[float, float],
    size: int,
    fill,
    *,
    text_fill=(255, 255, 255),
    max_width: float | None = None,
    pulse: float = 1.0,
) -> None:
    fsize = max(10, int(size * pulse))
    f = font(fsize, True)
    d = ImageDraw.Draw(base)
    bbox = d.textbbox((0, 0), text, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    if max_width and tw + 64 > max_width:
        fsize = max(10, int(fsize * max_width / (tw + 64)))
        f = font(fsize, True)
        bbox = d.textbbox((0, 0), text, font=f)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    w, h = tw + 64, th + 34
    x1, y1 = int(center[0] - w / 2), int(center[1] - h / 2)
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.rounded_rectangle((x1 + 8, y1 + 10, x1 + w + 8, y1 + h + 10), radius=h // 2, fill=(0, 0, 0, 80))
    sh = sh.filter(ImageFilter.GaussianBlur(8))
    base.alpha_composite(sh)
    d.rounded_rectangle((x1, y1, x1 + w, y1 + h), radius=h // 2, fill=fill)
    d.text((x1 + (w - tw) // 2, y1 + (h - th) // 2 - 3), text, font=f, fill=text_fill)


def draw_starburst(base: Image.Image, center, r1, r2, points, fill, *, rotation=0.0, alpha=230) -> None:
    pts = []
    for i in range(points * 2):
        radius = r1 if i % 2 == 0 else r2
        angle = rotation + math.pi * i / points
        pts.append((center[0] + math.cos(angle) * radius, center[1] + math.sin(angle) * radius))
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).polygon(pts, fill=(*fill, alpha))
    base.alpha_composite(layer)


def draw_leaf_sparkles(base: Image.Image, t: float, count: int = 18) -> None:
    w, h = base.size
    d = ImageDraw.Draw(base)
    for i in range(count):
        rng = random.Random(700 + i)
        phase = rng.random() * 8
        x = (rng.random() * w + t * (12 + rng.random() * 20)) % (w + 80) - 40
        y = h * (0.06 + rng.random() * 0.76) + math.sin(t * 1.7 + phase) * 15
        r = 4 + (i % 3) * 2
        col = [PALETTE["lime"], PALETTE["yellow"], PALETTE["cream"]][i % 3]
        d.ellipse((x - r, y - r, x + r, y + r), fill=(*col, 135))


def overlay_vignette(base: Image.Image, amount: float = 0.35) -> None:
    w, h = base.size
    yy, xx = np.mgrid[0:h, 0:w]
    nx = (xx - w / 2) / (w / 2)
    ny = (yy - h / 2) / (h / 2)
    dist = np.sqrt(nx * nx + ny * ny)
    alpha = np.clip((dist - 0.35) / 0.65, 0, 1) * 255 * amount
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    layer.putalpha(Image.fromarray(alpha.astype(np.uint8), "L"))
    black = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    black.putalpha(layer.getchannel("A"))
    base.alpha_composite(black)


def draw_safe_frame(base: Image.Image, title_bug: bool = True) -> None:
    w, h = base.size
    m = h > w
    d = ImageDraw.Draw(base)
    lw = max(2, int(min(w, h) * 0.004))
    d.rounded_rectangle((10, 10, w - 10, h - 10), radius=int(min(w, h) * 0.022), outline=(255, 255, 255, 150), width=lw)
    if title_bug:
        bw = 245 if not m else 215
        bh = 46 if not m else 48
        d.rounded_rectangle((18, 18, bw, bh + 18), radius=20, fill=(3, 48, 36, 190))
        d.text((30, 27), "クワガタ たんけんたい", font=font(19 if not m else 16, True), fill=PALETTE["white"])


class VideoReader:
    def __init__(self, path: Path):
        self.path = path
        self.cap = cv2.VideoCapture(str(path))
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open video: {path}")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 24.0
        self.count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self.duration = self.count / self.fps if self.count else probe_duration(path)
        self.current_index = -1
        self.current_frame: np.ndarray | None = None

    def frame(self, sec: float) -> Image.Image:
        if self.duration > 0:
            sec = sec % self.duration
        idx = max(0, int(sec * self.fps))
        if idx < self.current_index or idx - self.current_index > max(12, int(self.fps * 1.5)):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            self.current_index = idx - 1
        while self.current_index < idx:
            ok, frame = self.cap.read()
            if not ok:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.current_index = -1
                ok, frame = self.cap.read()
                if not ok:
                    raise RuntimeError(f"Failed to read video frame: {self.path}")
            self.current_index += 1
            self.current_frame = frame
        if self.current_frame is None:
            ok, frame = self.cap.read()
            if not ok:
                raise RuntimeError(f"Failed to read first frame: {self.path}")
            self.current_index = 0
            self.current_frame = frame
        rgb = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    def close(self) -> None:
        self.cap.release()


class RenderContext:
    def __init__(self, assets: dict[str, Image.Image], videos: dict[str, Path], size: tuple[int, int]):
        self.assets = assets
        self.size = size
        self.mobile = size[1] > size[0]
        self.readers = {key: VideoReader(path) for key, path in videos.items()}

    def close(self) -> None:
        for reader in self.readers.values():
            reader.close()

    def forest(self, sec: float, *, dark: float = 0.18, blur: float = 0.0) -> Image.Image:
        key = "forest_v" if self.mobile else "forest_h"
        frame = self.readers[key].frame(sec)
        crop = (0.50, 0.48 if self.mobile else 0.52)
        zoom = 1.02 + 0.015 * math.sin(sec * 0.35)
        im = fit_cover(frame, self.size, crop=crop, zoom=zoom)
        if blur > 0:
            im = im.filter(ImageFilter.GaussianBlur(blur))
        if dark > 0:
            im.alpha_composite(Image.new("RGBA", self.size, (0, 0, 0, int(255 * dark))))
        overlay_vignette(im, 0.28)
        return im

    def beetle_video(self, key: str, sec: float, *, dark: float = 0.08, crop=(0.5, 0.5), zoom=1.0) -> Image.Image:
        frame = self.readers[key].frame(sec)
        im = fit_cover(frame, self.size, crop=crop, zoom=zoom)
        if dark > 0:
            im.alpha_composite(Image.new("RGBA", self.size, (0, 0, 0, int(255 * dark))))
        overlay_vignette(im, 0.20)
        return im


def make_explorer_badge(photo: Image.Image, diameter: int) -> Image.Image:
    # The source image already shows a child using binoculars. A safari-style badge
    # and hat graphic make the expedition cue immediate without inventing a fake scene.
    d = diameter
    base = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    photo_square = fit_cover(photo, (d - 28, d - 28), crop=(0.44, 0.42), zoom=1.03)
    mask = Image.new("L", photo_square.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, photo_square.width - 1, photo_square.height - 1), fill=255)
    photo_square.putalpha(mask)
    draw = ImageDraw.Draw(base)
    draw.ellipse((0, 0, d - 1, d - 1), fill=(*PALETTE["yellow"], 245))
    draw.ellipse((8, 8, d - 9, d - 9), fill=(*PALETTE["green"], 255))
    base.alpha_composite(photo_square, (14, 14))
    # small expedition hat icon above the badge
    hat_w = int(d * 0.56)
    hx = d // 2
    hy = int(d * 0.13)
    draw.ellipse((hx - hat_w // 2, hy - 9, hx + hat_w // 2, hy + 18), fill=(218, 177, 85, 255), outline=(89, 76, 34, 255), width=max(2, d // 85))
    draw.rounded_rectangle((hx - int(hat_w * 0.28), hy - int(d * 0.12), hx + int(hat_w * 0.28), hy + 2), radius=max(4, d // 30), fill=(231, 194, 106, 255), outline=(89, 76, 34, 255), width=max(2, d // 85))
    draw.rectangle((hx - int(hat_w * 0.28), hy - 4, hx + int(hat_w * 0.28), hy + 3), fill=(*PALETTE["green"], 255))
    return base


def draw_explorer_callout(base: Image.Image, photo: Image.Image, t: float, *, compact: bool = False) -> None:
    w, h = base.size
    m = h > w
    diam = int(min(w, h) * (0.26 if not compact else 0.15))
    badge = make_explorer_badge(photo, diam)
    if compact:
        center = (w * (0.86 if not m else 0.80), h * (0.18 if not m else 0.14))
        p = 1.0
    else:
        center = (w * (0.79 if not m else 0.50), h * (0.53 if not m else 0.62))
        p = ease_out_back(min(1.0, max(0.0, (t - 0.35) / 0.75)))
    badge = badge.resize((max(2, int(diam * p)), max(2, int(diam * p))), Image.Resampling.LANCZOS)
    base.alpha_composite(badge, (int(center[0] - badge.width / 2), int(center[1] - badge.height / 2)))
    if not compact and p > 0.2:
        draw_pill(
            base,
            "さがしに いこう！",
            (center[0], center[1] + diam * 0.66),
            int(min(w, h) * 0.050),
            (*PALETTE["orange"], 255),
            max_width=w * (0.40 if not m else 0.82),
            pulse=1 + 0.04 * math.sin(t * 6),
        )


def map_card(map_img: Image.Image, size: tuple[int, int], t: float) -> Image.Image:
    w, h = size
    card = Image.new("RGBA", size, (255, 248, 222, 245))
    card = rounded_crop(card, int(min(w, h) * 0.08))
    gray = ImageOps.grayscale(map_img.convert("RGB"))
    mask = ImageOps.invert(gray)
    mask = mask.point(lambda p: 255 if p > 35 else 0)
    mask.thumbnail((int(w * 0.84), int(h * 0.82)), Image.Resampling.LANCZOS)
    fill = Image.new("RGBA", mask.size, (*PALETTE["green"], 255))
    fill.putalpha(mask)
    x = (w - mask.width) // 2
    y = (h - mask.height) // 2
    card.alpha_composite(fill, (x, y))
    d = ImageDraw.Draw(card)
    # broad glowing band indicating the main distribution from Hokkaido through Kyushu
    phase = 0.5 + 0.5 * math.sin(t * 3.2)
    for idx, yy in enumerate([0.20, 0.34, 0.48, 0.62, 0.76]):
        cx = w * (0.54 - idx * 0.04)
        cy = h * yy
        rr = min(w, h) * (0.035 + 0.01 * phase)
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=(*PALETTE["orange"], 210), outline=PALETTE["white"], width=max(2, int(rr * 0.22)))
    return card


def scene_title(ctx: RenderContext, t: float) -> Image.Image:
    w, h = ctx.size
    m = ctx.mobile
    im = ctx.forest(t * 0.85, dark=0.22)
    draw_leaf_sparkles(im, t, 22)
    draw_starburst(im, (w * (0.34 if not m else 0.5), h * (0.41 if not m else 0.31)), min(w, h) * 0.29, min(w, h) * 0.21, 16, PALETTE["yellow"], rotation=t * 0.18, alpha=150)
    p = ease_out_back(min(1, t / 0.8))
    draw_text_center(im, "クワガタ", (w * (0.34 if not m else 0.5), h * (0.34 if not m else 0.26)), int(min(w, h) * 0.12), PALETTE["red"], stroke=6, stroke_fill=PALETTE["white"], max_width=w * (0.60 if not m else 0.88), scale=p)
    draw_text_center(im, "たんけんたい！", (w * (0.34 if not m else 0.5), h * (0.51 if not m else 0.40)), int(min(w, h) * 0.075), PALETTE["deep"], stroke=5, stroke_fill=PALETTE["cream"], max_width=w * (0.62 if not m else 0.90), scale=p)
    draw_explorer_callout(im, ctx.assets["explorer"], t)
    draw_safe_frame(im, False)
    return im


def scene_search(ctx: RenderContext, t: float) -> Image.Image:
    w, h = ctx.size
    m = ctx.mobile
    im = ctx.forest(5.0 + t * 0.95, dark=0.08)
    d = ImageDraw.Draw(im)
    draw_leaf_sparkles(im, t + 2, 12)
    draw_text_center(im, "クワガタ どこかな？", (w * 0.5, h * (0.15 if not m else 0.10)), int(min(w, h) * 0.080), PALETTE["cream"], stroke=6, stroke_fill=PALETTE["deep"], max_width=w * 0.88, scale=1 + 0.035 * math.sin(t * 5))
    mx = w * (0.16 + 0.68 * (0.5 + 0.5 * math.sin(t * 1.25)))
    my = h * (0.58 if not m else 0.50) + math.sin(t * 2.2) * h * 0.045
    rr = min(w, h) * 0.105
    # magnifier with a real beetle photo hidden inside the lens
    lens = fit_cover(ctx.assets["noko_tree"], (int(rr * 1.65), int(rr * 1.65)), crop=(0.44, 0.50), zoom=1.2)
    mask = Image.new("L", lens.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, lens.width - 1, lens.height - 1), fill=255)
    lens.putalpha(mask)
    im.alpha_composite(lens, (int(mx - lens.width / 2), int(my - lens.height / 2)))
    d.ellipse((mx - rr, my - rr, mx + rr, my + rr), outline=PALETTE["white"], width=max(6, int(rr * 0.10)))
    d.ellipse((mx - rr + 9, my - rr + 9, mx + rr - 9, my + rr - 9), outline=PALETTE["blue"], width=max(4, int(rr * 0.055)))
    d.line((mx + rr * 0.70, my + rr * 0.70, mx + rr * 1.50, my + rr * 1.50), fill=PALETTE["red"], width=max(10, int(rr * 0.18)))
    if t > 2.8:
        p = ease_out_back(min(1, (t - 2.8) / 0.55))
        draw_starburst(im, (w * 0.5, h * (0.70 if not m else 0.76)), min(w, h) * 0.20 * p, min(w, h) * 0.14 * p, 12, PALETTE["yellow"], rotation=t, alpha=210)
        draw_text_center(im, "みつけた！", (w * 0.5, h * (0.70 if not m else 0.76)), int(min(w, h) * 0.100), PALETTE["red"], stroke=6, stroke_fill=PALETTE["white"], max_width=w * 0.88, scale=p)
    draw_safe_frame(im)
    return im


def scene_moving(ctx: RenderContext, t: float) -> Image.Image:
    w, h = ctx.size
    m = ctx.mobile
    # The stag macro footage is real video, not a still. It is labelled generically so
    # it is not misrepresented as one of the Japanese species introduced later.
    im = ctx.beetle_video("stag_macro", 1.4 + t * 1.12, dark=0.04, crop=(0.55 if not m else 0.60, 0.50), zoom=1.03)
    draw_pill(im, "ほんものの クワガタ", (w * (0.27 if not m else 0.50), h * (0.15 if not m else 0.10)), int(min(w, h) * 0.052), (*PALETTE["green"], 235), max_width=w * (0.46 if not m else 0.86), pulse=1 + 0.03 * math.sin(t * 5))
    if 3.0 < t < 6.4:
        draw_text_center(im, "うごいてる！", (w * (0.30 if not m else 0.50), h * (0.83 if not m else 0.87)), int(min(w, h) * 0.092), PALETTE["yellow"], stroke=6, stroke_fill=PALETTE["deep"], max_width=w * 0.75, scale=1 + 0.05 * math.sin(t * 7))
    elif t >= 6.4:
        draw_text_center(im, "おおきな あご！", (w * (0.30 if not m else 0.50), h * (0.83 if not m else 0.87)), int(min(w, h) * 0.086), PALETTE["orange"], stroke=6, stroke_fill=PALETTE["white"], max_width=w * 0.78, scale=1 + 0.04 * math.sin(t * 6))
    draw_safe_frame(im)
    return im


def scene_noko(ctx: RenderContext, t: float) -> Image.Image:
    w, h = ctx.size
    m = ctx.mobile
    im = ctx.forest(9.5 + t * 0.35, dark=0.30, blur=7)
    draw_leaf_sparkles(im, t + 6, 14)
    p = ease_out_back(min(1, t / 0.65))
    if not m:
        main_c, main_s = (w * 0.35, h * 0.53), (w * 0.47 * p, h * 0.69 * p)
        sub_c, sub_s = (w * 0.78, h * 0.58), (w * 0.31, h * 0.46)
    else:
        main_c, main_s = (w * 0.50, h * 0.39), (w * 0.82 * p, h * 0.43 * p)
        sub_c, sub_s = (w * 0.50, h * 0.73), (w * 0.68, h * 0.25)
    paste_card(im, ctx.assets["noko_pair"], main_c, main_s, crop=(0.52, 0.50), angle=math.sin(t * 2) * 1.2, radius=int(min(w, h) * 0.035), border=max(4, int(min(w, h) * 0.007)), border_fill=(*PALETTE["cream"], 255), zoom=1.02)
    if t > 2.8:
        q = ease_out_back(min(1, (t - 2.8) / 0.55))
        paste_card(im, ctx.assets["noko_tree"], sub_c, (sub_s[0] * q, sub_s[1] * q), crop=(0.42, 0.48), angle=-2 + math.sin(t * 3), radius=int(min(w, h) * 0.032), border=max(3, int(min(w, h) * 0.006)), border_fill=(*PALETTE["yellow"], 255), zoom=1.06)
    draw_pill(im, "ノコギリクワガタ", (w * (0.72 if not m else 0.50), h * (0.17 if not m else 0.10)), int(min(w, h) * 0.060), (*PALETTE["red"], 245), max_width=w * (0.48 if not m else 0.88), pulse=1 + 0.035 * math.sin(t * 5))
    if t > 3.3:
        draw_text_center(im, "ぎざぎざの おおあご", (w * (0.72 if not m else 0.50), h * (0.88 if not m else 0.91)), int(min(w, h) * 0.066), PALETTE["yellow"], stroke=5, stroke_fill=PALETTE["deep"], max_width=w * 0.88, scale=1 + 0.04 * math.sin(t * 6))
    draw_safe_frame(im)
    return im


def scene_habitat(ctx: RenderContext, t: float) -> Image.Image:
    w, h = ctx.size
    m = ctx.mobile
    if t < 6.4:
        im = ctx.forest(13.0 + t * 0.70, dark=0.16)
        if not m:
            c, s = (w * 0.28, h * 0.52), (w * 0.39, h * 0.68)
        else:
            c, s = (w * 0.50, h * 0.37), (w * 0.78, h * 0.46)
        map_im = map_card(ctx.assets["map"], (max(10, int(s[0])), max(10, int(s[1]))), t)
        paste_card(im, map_im, c, s, angle=math.sin(t * 2) * 1.0, radius=int(min(w, h) * 0.04), shadow=True)
        draw_text_center(im, "北海道〜九州の もり", (w * (0.70 if not m else 0.50), h * (0.30 if not m else 0.70)), int(min(w, h) * 0.072), PALETTE["cream"], stroke=6, stroke_fill=PALETTE["deep"], max_width=w * (0.50 if not m else 0.88))
        draw_pill(im, "コナラ・クヌギの じゅえき", (w * (0.70 if not m else 0.50), h * (0.55 if not m else 0.83)), int(min(w, h) * 0.050), (*PALETTE["orange"], 245), max_width=w * (0.48 if not m else 0.86), pulse=1 + 0.035 * math.sin(t * 5))
    else:
        im = ctx.beetle_video("stag_walk", 0.4 + (t - 6.4) * 0.95, dark=0.04, crop=(0.52, 0.48), zoom=1.05)
        draw_pill(im, "てくてく あるくよ", (w * 0.50, h * (0.14 if not m else 0.09)), int(min(w, h) * 0.056), (*PALETTE["blue"], 240), max_width=w * 0.84, pulse=1 + 0.04 * math.sin(t * 6))
    draw_safe_frame(im)
    return im


def scene_quiz(ctx: RenderContext, t: float) -> Image.Image:
    w, h = ctx.size
    m = ctx.mobile
    im = ctx.forest(17.5 + t * 0.20, dark=0.38, blur=7)
    d = ImageDraw.Draw(im)
    if t < 2.8:
        p = ease_out_back(min(1, t / 0.55))
        draw_starburst(im, (w * 0.50, h * (0.38 if not m else 0.27)), min(w, h) * 0.28 * p, min(w, h) * 0.19 * p, 14, PALETTE["pink"], rotation=t * 0.4, alpha=215)
        draw_text_center(im, "クイズ！", (w * 0.50, h * (0.38 if not m else 0.27)), int(min(w, h) * 0.13), PALETTE["white"], stroke=6, stroke_fill=PALETTE["red"], max_width=w * 0.82, scale=p)
        draw_pill(im, "ぎざぎざは どっち？", (w * 0.50, h * (0.72 if not m else 0.67)), int(min(w, h) * 0.060), (*PALETTE["deep"], 245), max_width=w * 0.88, pulse=1 + 0.04 * math.sin(t * 6))
    else:
        if not m:
            c1, c2, cs = (w * 0.28, h * 0.55), (w * 0.72, h * 0.55), (w * 0.35, h * 0.58)
        else:
            c1, c2, cs = (w * 0.50, h * 0.34), (w * 0.50, h * 0.73), (w * 0.78, h * 0.29)
        pulse = 1 + 0.018 * math.sin(t * 4)
        paste_card(im, ctx.assets["kokuwa"], c1, (cs[0] * pulse, cs[1] * pulse), crop=(0.52, 0.48), angle=math.sin(t * 2) * 1.1, radius=int(min(w, h) * 0.035), border=max(4, int(min(w, h) * 0.006)), border_fill=(*PALETTE["cream"], 255), zoom=1.04)
        paste_card(im, ctx.assets["noko_pair"], c2, (cs[0] * pulse, cs[1] * pulse), crop=(0.52, 0.50), angle=-math.sin(t * 2) * 1.1, radius=int(min(w, h) * 0.035), border=max(4, int(min(w, h) * 0.006)), border_fill=(*PALETTE["cream"], 255), zoom=1.03)
        draw_pill(im, "A", (c1[0] - cs[0] * 0.38, c1[1] - cs[1] * 0.39), int(min(w, h) * 0.060), (*PALETTE["blue"], 255), max_width=min(w, h) * 0.2)
        draw_pill(im, "B", (c2[0] - cs[0] * 0.38, c2[1] - cs[1] * 0.39), int(min(w, h) * 0.060), (*PALETTE["red"], 255), max_width=min(w, h) * 0.2)
        if t < 8.65:
            draw_text_center(im, "どっち？", (w * 0.50, h * (0.12 if not m else 0.075)), int(min(w, h) * 0.086), PALETTE["yellow"], stroke=5, stroke_fill=PALETTE["deep"], max_width=w * 0.84, scale=1 + 0.045 * math.sin(t * 7))
            for i in range(3):
                active = t > 6.55 + i * 0.75
                r = min(w, h) * (0.019 if not active else 0.030)
                x = w * 0.50 + (i - 1) * min(w, h) * 0.09
                y = h * (0.91 if not m else 0.95)
                d.ellipse((x - r, y - r, x + r, y + r), fill=PALETTE["red"] if active else PALETTE["white"])
        else:
            phase = ease_out_back(min(1, (t - 8.65) / 0.55))
            draw_starburst(im, c2, min(w, h) * 0.25 * phase, min(w, h) * 0.18 * phase, 16, PALETTE["yellow"], rotation=t, alpha=205)
            paste_card(im, ctx.assets["noko_pair"], c2, (cs[0] * (1 + 0.07 * phase), cs[1] * (1 + 0.07 * phase)), crop=(0.52, 0.50), angle=math.sin(t * 4) * 1.5, radius=int(min(w, h) * 0.035), border=max(5, int(min(w, h) * 0.009)), border_fill=(*PALETTE["yellow"], 255), zoom=1.03)
            draw_text_center(im, "せいかいは B！", (w * 0.50, h * (0.12 if not m else 0.075)), int(min(w, h) * 0.086), PALETTE["red"], stroke=6, stroke_fill=PALETTE["white"], max_width=w * 0.88, scale=phase)
            for i in range(24):
                rng = random.Random(1000 + i)
                x = (rng.random() * w + (t - 8.65) * (40 + rng.random() * 80)) % (w + 30) - 15
                y = rng.random() * h * 0.70 + (t - 8.65) * 60
                col = [PALETTE["red"], PALETTE["blue"], PALETTE["green"], PALETTE["yellow"], PALETTE["pink"]][i % 5]
                d.rectangle((x, y, x + 8 + (i % 3) * 3, y + 17), fill=col)
    draw_safe_frame(im)
    return im


def scene_teaser(ctx: RenderContext, t: float) -> Image.Image:
    w, h = ctx.size
    m = ctx.mobile
    im = ctx.forest(20.5 + t * 0.8, dark=0.30)
    draw_leaf_sparkles(im, t + 10, 12)
    draw_text_center(im, "つぎは だれかな？", (w * 0.50, h * (0.14 if not m else 0.08)), int(min(w, h) * 0.078), PALETTE["yellow"], stroke=5, stroke_fill=PALETTE["deep"], max_width=w * 0.88, scale=1 + 0.04 * math.sin(t * 6))
    keys = ["kokuwa", "miyama_male", "hirata_dorsal", "ookuwa"]
    labels = ["コクワ", "ミヤマ♂", "ヒラタ", "オオクワ"]
    if not m:
        centers = [(w * 0.16, h * 0.54), (w * 0.39, h * 0.54), (w * 0.63, h * 0.54), (w * 0.86, h * 0.54)]
        card_size = (w * 0.205, h * 0.48)
    else:
        centers = [(w * 0.28, h * 0.32), (w * 0.72, h * 0.32), (w * 0.28, h * 0.68), (w * 0.72, h * 0.68)]
        card_size = (w * 0.39, h * 0.28)
    for i, (key, label, c) in enumerate(zip(keys, labels, centers)):
        p = ease_out_back(min(1, max(0, (t - i * 0.17) / 0.48)))
        crop = (0.50, 0.48)
        paste_card(im, ctx.assets[key], c, (card_size[0] * p, card_size[1] * p), crop=crop, angle=math.sin(t * 2 + i) * 1.2, radius=int(min(w, h) * 0.030), border=max(3, int(min(w, h) * 0.005)), border_fill=(*PALETTE["cream"], 255), zoom=1.03)
        if p > 0.55:
            draw_pill(im, label, (c[0], c[1] + card_size[1] * 0.44), int(min(w, h) * 0.034), (*PALETTE["deep"], 235), max_width=card_size[0] * 0.95)
    draw_explorer_callout(im, ctx.assets["explorer"], t, compact=True)
    draw_safe_frame(im)
    return im


def render_frame(ctx: RenderContext, time_s: float) -> Image.Image:
    if time_s < 6.4:
        im = scene_title(ctx, time_s)
    elif time_s < 12.0:
        im = scene_search(ctx, time_s - 6.4)
    elif time_s < 23.0:
        im = scene_moving(ctx, time_s - 12.0)
    elif time_s < 34.0:
        im = scene_noko(ctx, time_s - 23.0)
    elif time_s < 44.0:
        im = scene_habitat(ctx, time_s - 34.0)
    elif time_s < 56.5:
        im = scene_quiz(ctx, time_s - 44.0)
    else:
        im = scene_teaser(ctx, time_s - 56.5)
    # quick white wipes at chapter boundaries
    for boundary in (6.4, 12.0, 23.0, 34.0, 44.0, 56.5):
        delta = abs(time_s - boundary)
        if delta < 0.12:
            alpha = int(225 * (1 - delta / 0.12))
            im.alpha_composite(Image.new("RGBA", ctx.size, (255, 255, 255, alpha)))
    return im.convert("RGB")


def load_assets(asset_dir: Path) -> tuple[dict[str, Image.Image], dict[str, Path]]:
    required_images = {
        "noko_tree": asset_dir / "noko_tree.jpg",
        "noko_pair": asset_dir / "noko_pair.jpg",
        "kokuwa": asset_dir / "kokuwa.jpg",
        "ookuwa": asset_dir / "ookuwa.jpg",
        "miyama_male": asset_dir / "miyama_male.jpg",
        "hirata_dorsal": asset_dir / "hirata_dorsal.jpg",
        "explorer": asset_dir / "explorer.jpg",
        "map": asset_dir / "japan_map.png",
    }
    required_videos = {
        "forest_h": asset_dir / "forest_h.webm",
        "forest_v": asset_dir / "forest_v.webm",
        "stag_walk": asset_dir / "stag_walk.webm",
        "stag_macro": asset_dir / "stag_macro.webm",
    }
    missing = [str(p) for p in [*required_images.values(), *required_videos.values()] if not p.exists() or p.stat().st_size < 1000]
    if missing:
        raise FileNotFoundError(f"Missing assets: {missing}")
    images = {key: Image.open(path).convert("RGB") for key, path in required_images.items()}
    return images, required_videos


def render_video(size: tuple[int, int], out_path: Path, assets: dict[str, Image.Image], videos: dict[str, Path], fps: int) -> None:
    w, h = size
    ctx = RenderContext(assets, videos, size)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
        "-profile:v", "high", "-level", "4.0", "-movflags", "+faststart", str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    total = int(round(DURATION * fps))
    try:
        for i in range(total):
            frame = render_frame(ctx, i / fps)
            if proc.stdin is None:
                raise RuntimeError("ffmpeg stdin closed")
            proc.stdin.write(np.asarray(frame, dtype=np.uint8).tobytes())
            if i % 120 == 0:
                print(f"render {out_path.name}: {i}/{total}", flush=True)
    finally:
        if proc.stdin:
            proc.stdin.close()
        rc = proc.wait()
        ctx.close()
        if rc != 0:
            raise RuntimeError(f"ffmpeg video encoder failed: {rc}")


def wait_voicevox(base_url: str, timeout: int = 420) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = requests.get(f"{base_url}/version", timeout=5)
            if response.ok:
                print("VOICEVOX ready:", response.text, flush=True)
                return
        except requests.RequestException:
            pass
        time.sleep(3)
    raise TimeoutError("VOICEVOX engine did not become ready")


def find_voicevox_style(base_url: str, speaker_name: str = "ずんだもん", style_name: str = "ノーマル") -> int:
    speakers = requests.get(f"{base_url}/speakers", timeout=30).json()
    for speaker in speakers:
        if speaker.get("name") == speaker_name:
            for style in speaker.get("styles", []):
                if style.get("name") == style_name:
                    return int(style["id"])
            if speaker.get("styles"):
                return int(speaker["styles"][0]["id"])
    raise RuntimeError(f"VOICEVOX speaker not found: {speaker_name}/{style_name}")


def atempo_chain(factor: float) -> str:
    parts: list[float] = []
    f = factor
    while f > 2.0:
        parts.append(2.0)
        f /= 2.0
    while f < 0.5:
        parts.append(0.5)
        f /= 0.5
    parts.append(f)
    return ",".join(f"atempo={p:.6f}" for p in parts)


def synthesize_voice(work: Path, base_url: str) -> list[tuple[float, float, Path, str]]:
    work.mkdir(parents=True, exist_ok=True)
    wait_voicevox(base_url)
    speaker = find_voicevox_style(base_url)
    print("VOICEVOX speaker style id:", speaker, flush=True)
    clips: list[tuple[float, float, Path, str]] = []
    for idx, (start, end, text) in enumerate(UTTERANCES):
        query = requests.post(
            f"{base_url}/audio_query",
            params={"speaker": speaker, "text": text},
            timeout=60,
        )
        query.raise_for_status()
        payload: dict[str, Any] = query.json()
        payload["speedScale"] = 1.08
        payload["pitchScale"] = 0.035
        payload["intonationScale"] = 1.18
        payload["volumeScale"] = 1.08
        payload["prePhonemeLength"] = 0.08
        payload["postPhonemeLength"] = 0.10
        raw = work / f"voice_{idx:02d}_raw.wav"
        response = requests.post(
            f"{base_url}/synthesis",
            params={"speaker": speaker},
            json=payload,
            timeout=180,
        )
        response.raise_for_status()
        raw.write_bytes(response.content)
        fitted = work / f"voice_{idx:02d}.wav"
        duration = probe_duration(raw)
        slot = max(0.25, end - start - 0.10)
        filters = ["highpass=f=90", "lowpass=f=12000"]
        if duration > slot:
            filters.insert(0, atempo_chain(duration / slot))
        filters.extend(["acompressor=threshold=-20dB:ratio=2.2:attack=10:release=80", "volume=1.15"])
        run([
            "ffmpeg", "-y", "-v", "error", "-i", str(raw),
            "-af", ",".join(filters), "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(fitted),
        ])
        clips.append((start, end, fitted, text))
    return clips


def envelope(n: int, sr: int, attack=0.01, release=0.12) -> np.ndarray:
    env = np.ones(n, dtype=np.float32)
    a = min(n, int(sr * attack))
    r = min(n, int(sr * release))
    if a > 0:
        env[:a] = np.linspace(0, 1, a, dtype=np.float32)
    if r > 0:
        env[-r:] = np.linspace(1, 0, r, dtype=np.float32)
    return env


def add_note(track: np.ndarray, start: float, duration: float, freq: float, amp: float, sr: int, harmonics=(1.0, 0.28, 0.09)) -> None:
    pos = int(start * sr)
    n = min(len(track) - pos, int(duration * sr))
    if n <= 0:
        return
    tt = np.arange(n, dtype=np.float32) / sr
    y = np.zeros(n, dtype=np.float32)
    for i, h in enumerate(harmonics, 1):
        y += h * np.sin(2 * np.pi * freq * i * tt)
    y *= envelope(n, sr, 0.006, min(0.16, duration * 0.42)) * amp
    track[pos:pos + n] += y


def synth_sfx(kind: str, sr=48000) -> np.ndarray:
    rng = np.random.default_rng(abs(hash(kind)) % (2**32))
    if kind == "whoosh":
        dur = 0.42
        n = int(sr * dur)
        tt = np.arange(n) / sr
        noise = rng.normal(0, 1, n)
        smooth = np.convolve(noise, np.ones(70) / 70, mode="same")
        y = smooth * np.sin(np.pi * tt / dur) ** 2 * 0.80
    elif kind == "pop":
        dur = 0.25
        n = int(sr * dur)
        tt = np.arange(n) / sr
        y = np.sin(2 * np.pi * (720 * tt - 380 * tt * tt / (2 * dur))) * np.exp(-13 * tt) * 0.85
    elif kind == "ding":
        dur = 0.68
        n = int(sr * dur)
        tt = np.arange(n) / sr
        y = (np.sin(2 * np.pi * 880 * tt) + 0.45 * np.sin(2 * np.pi * 1320 * tt)) * np.exp(-5.5 * tt) * 0.46
    elif kind == "sparkle":
        dur = 0.9
        n = int(sr * dur)
        y = np.zeros(n)
        for st, freq in [(0, 1175), (0.12, 1480), (0.25, 1760), (0.39, 2349)]:
            pos = int(st * sr)
            t2 = np.arange(n - pos) / sr
            y[pos:] += np.sin(2 * np.pi * freq * t2) * np.exp(-8 * t2) * 0.26
    elif kind == "rattle":
        dur = 0.50
        n = int(sr * dur)
        y = np.zeros(n)
        for st in np.arange(0, dur, 0.07):
            pos = int(st * sr)
            n2 = min(int(0.06 * sr), n - pos)
            t2 = np.arange(n2) / sr
            y[pos:pos + n2] += np.sin(2 * np.pi * (520 + st * 280) * t2) * np.exp(-35 * t2) * 0.35
    elif kind == "tick":
        dur = 0.12
        n = int(sr * dur)
        tt = np.arange(n) / sr
        y = np.sin(2 * np.pi * 1200 * tt) * np.exp(-35 * tt) * 0.32
    elif kind == "quiz":
        dur = 0.52
        n = int(sr * dur)
        tt = np.arange(n) / sr
        y = (np.sin(2 * np.pi * 440 * tt) + 0.55 * np.sin(2 * np.pi * 660 * tt)) * np.exp(-4.2 * tt) * 0.38
    elif kind == "answer":
        dur = 1.05
        n = int(sr * dur)
        y = np.zeros(n)
        for st, freq in [(0, 523), (0.13, 659), (0.26, 784), (0.39, 1047)]:
            pos = int(st * sr)
            t2 = np.arange(n - pos) / sr
            y[pos:] += np.sin(2 * np.pi * freq * t2) * np.exp(-5 * t2) * 0.30
    else:
        dur = 0.2
        n = int(sr * dur)
        y = np.zeros(n)
    return np.asarray(y, dtype=np.float32)


def make_music(path: Path, duration: float = DURATION, sr: int = 48000) -> None:
    n = int(duration * sr)
    bgm = np.zeros(n, dtype=np.float32)
    notes = [523.25, 659.25, 783.99, 659.25, 587.33, 698.46, 880.00, 783.99]
    beat = 0.50
    for i, start in enumerate(np.arange(0, duration, beat)):
        freq = notes[i % len(notes)]
        add_note(bgm, float(start), 0.29, freq, 0.060, sr)
        if i % 2 == 0:
            add_note(bgm, float(start), 0.17, freq / 2, 0.038, sr, (1, 0.15))
    for start in np.arange(0, duration, 1.0):
        add_note(bgm, float(start), 0.17, 130.81, 0.040, sr, (1, 0.10))
    sfx = np.zeros(n, dtype=np.float32)
    for start, kind in SFX_EVENTS:
        y = synth_sfx(kind, sr)
        pos = int(start * sr)
        count = min(len(y), n - pos)
        if count > 0:
            sfx[pos:pos + count] += y[:count]
    mix = np.clip(bgm + sfx, -1, 1)
    stereo = np.column_stack([mix, mix])
    pcm = (stereo * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


def mix_audio(music: Path, clips: list[tuple[float, float, Path, str]], out: Path) -> None:
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(music)]
    for _, _, clip, _ in clips:
        cmd += ["-i", str(clip)]
    filters = ["[0:a]volume=0.52[base]"]
    labels = ["[base]"]
    for idx, (start, _, _, _) in enumerate(clips, 1):
        delay = int(start * 1000)
        filters.append(f"[{idx}:a]adelay={delay}|{delay},volume=1.0[v{idx}]")
        labels.append(f"[v{idx}]")
    filters.append("".join(labels) + f"amix=inputs={len(labels)}:duration=longest:dropout_transition=0,loudnorm=I=-15.5:LRA=7:TP=-1.0[m]")
    cmd += [
        "-filter_complex", ";".join(filters), "-map", "[m]", "-t", str(DURATION),
        "-ar", "48000", "-ac", "2", "-c:a", "aac", "-b:a", "160k", str(out),
    ]
    run(cmd)


def mux(video: Path, audio: Path, out: Path) -> None:
    run([
        "ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(audio),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "copy",
        "-t", str(DURATION), "-movflags", "+faststart", str(out),
    ])


def make_srt(path: Path) -> None:
    def tc(value: float) -> str:
        ms = int(round(value * 1000))
        hh = ms // 3_600_000
        ms %= 3_600_000
        mm = ms // 60_000
        ms %= 60_000
        ss = ms // 1000
        ms %= 1000
        return f"{hh:02}:{mm:02}:{ss:02},{ms:03}"

    lines: list[str] = []
    for idx, (start, end, text) in enumerate(UTTERANCES, 1):
        lines += [str(idx), f"{tc(start)} --> {tc(end)}", text, ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def extract_frame(source: Path, sec: float, dest: Path) -> None:
    run(["ffmpeg", "-y", "-v", "error", "-ss", str(sec), "-i", str(source), "-frames:v", "1", str(dest)])


def make_contact_sheet(video: Path, out: Path, mobile: bool) -> None:
    times = [0.6, 3.2, 7.2, 10.2, 12.8, 16.2, 20.2, 23.8, 27.2, 31.0, 34.8, 38.2, 41.8, 44.8, 48.2, 51.8, 54.0, 57.5, 59.0]
    tmp = out.parent / ("contact_mobile" if mobile else "contact_pc")
    tmp.mkdir(exist_ok=True)
    thumbs: list[Image.Image] = []
    for idx, sec in enumerate(times):
        p = tmp / f"{idx:02d}.jpg"
        extract_frame(video, sec, p)
        thumbs.append(Image.open(p).convert("RGB"))
    tw, th = ((180, 320) if mobile else (320, 180))
    cols = 4 if mobile else 3
    rows = math.ceil(len(thumbs) / cols)
    sheet = Image.new("RGB", (tw * cols, th * rows), PALETTE["white"])
    d = ImageDraw.Draw(sheet)
    for idx, img in enumerate(thumbs):
        thumb = fit_cover(img, (tw, th)).convert("RGB")
        x = (idx % cols) * tw
        y = (idx // cols) * th
        sheet.paste(thumb, (x, y))
        d.text((x + 6, y + 6), f"{times[idx]:.1f}s", font=font(15, True), fill=PALETTE["red"], stroke_width=2, stroke_fill=PALETTE["white"])
    sheet.save(out, quality=91)


def verify_video(path: Path, expected_size: tuple[int, int]) -> dict[str, Any]:
    out = run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,codec_name,pix_fmt",
        "-show_entries", "format=duration,size", "-of", "json", str(path),
    ], capture=True)
    meta = json.loads(out)
    stream = meta["streams"][0]
    duration = float(meta["format"]["duration"])
    if (stream["width"], stream["height"]) != expected_size:
        raise RuntimeError(f"Unexpected dimensions: {stream}")
    if not 59.75 <= duration <= 60.25:
        raise RuntimeError(f"Unexpected duration: {duration}")
    if stream["codec_name"] != "h264":
        raise RuntimeError(f"Unexpected codec: {stream}")
    run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"])
    return meta


def write_credits(path: Path) -> None:
    path.write_text(
        "クワガタたんけんたい 修正版パイロット v2（個人視聴用）\n"
        "\n"
        "【今回の主要修正】\n"
        "・キノコ主体の背景を廃止し、実際の森林映像へ変更。\n"
        "・ミヤマクワガタは大あごのあるオス写真へ変更。\n"
        "・ヒラタクワガタは背面・上方から見える写真へ変更。\n"
        "・双眼鏡を使う子どもの探検隊バッジを追加。\n"
        "・ナレーションを子どもらしい合成音声へ変更。\n"
        "\n"
        "【映像・画像】\n"
        "森林（横）：Cosumnes River Preserve / Bob Wick, Bureau of Land Management / Wikimedia Commons.\n"
        "森林（縦）：Walking along Rokuwatari Path at the foot of Mt Nijozan Osaka Japan June2025 / Shironsilentpond / CC BY 4.0.\n"
        "動くクワガタ：Stag Beetle (Lucanus cervus) / Leonora Enking / CC BY-SA 2.0.\n"
        "動くクワガタ接写：Жук Олень / Сергій Ковальов / CC BY-SA 4.0.\n"
        "ノコギリクワガタ：Wikimedia Commons（Kinokoekuwagata、K fumishima）/ CC BY-SA 4.0.\n"
        "コクワガタ：takato marui / CC BY-SA 2.0.\n"
        "オオクワガタ：keusju / CC BY-SA 3.0・GFDL.\n"
        "ミヤマクワガタ（オス）：Lee Junyoung / iNaturalist / CC BY-NC.\n"
        "ヒラタクワガタ（背面）：曾祥宇 / Wikimedia Commons / CC BY-SA 4.0.\n"
        "探検隊の子ども：U.S. Fish and Wildlife Service / Public Domain.\n"
        "日本地図：Regions and Prefectures of Japan - blank / Bigmorr / Public Domain.\n"
        "\n"
        "【音声】\n"
        "VOICEVOX:ずんだもん（子どもらしい高めの合成音声として使用）\n"
        "音楽・効果音：本ビルドで新規合成。\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("output_revision_v2"))
    parser.add_argument("--work", type=Path, default=Path("work_revision_v2"))
    parser.add_argument("--voicevox-url", default="http://127.0.0.1:50021")
    parser.add_argument("--fps", type=int, default=FPS)
    parser.add_argument("--pc-only", action="store_true")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    args.work.mkdir(parents=True, exist_ok=True)
    assets, videos = load_assets(args.assets)

    pc_silent = args.work / "revision_pc_silent.mp4"
    render_video(PC_SIZE, pc_silent, assets, videos, args.fps)
    mobile_silent: Path | None = None
    if not args.pc_only:
        mobile_silent = args.work / "revision_mobile_silent.mp4"
        render_video(MOBILE_SIZE, mobile_silent, assets, videos, args.fps)

    music = args.work / "music_sfx.wav"
    make_music(music)
    clips = synthesize_voice(args.work / "voice", args.voicevox_url)
    mixed = args.work / "mixed_audio.m4a"
    mix_audio(music, clips, mixed)

    pc_final = args.output / "Kuwagata_Expedition_Revised_v2_PC_1280x720.mp4"
    mux(pc_silent, mixed, pc_final)
    qa: dict[str, Any] = {"pc": verify_video(pc_final, PC_SIZE)}
    make_contact_sheet(pc_final, args.output / "Kuwagata_Expedition_Revised_v2_PC_Contact.jpg", False)

    if mobile_silent is not None:
        mobile_final = args.output / "Kuwagata_Expedition_Revised_v2_Mobile_720x1280.mp4"
        mux(mobile_silent, mixed, mobile_final)
        qa["mobile"] = verify_video(mobile_final, MOBILE_SIZE)
        make_contact_sheet(mobile_final, args.output / "Kuwagata_Expedition_Revised_v2_Mobile_Contact.jpg", True)

    make_srt(args.output / "Kuwagata_Expedition_Revised_v2_JP.srt")
    write_credits(args.output / "Kuwagata_Expedition_Revised_v2_Credits.txt")
    (args.output / "Kuwagata_Expedition_Revised_v2_QA.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
