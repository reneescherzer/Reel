#!/usr/bin/env python3
"""Render a 9:16 Polaroid-collage reel ("Meanwhile, back home...") for a college kid.

Each photo drops in as a taped Polaroid with a handwritten caption, holds for a
beat, then flies into its spot in a scrapbook collage. The reel ends on the
full collage with a notebook-paper note and floating hearts.

Usage:  python3 make_reel.py            -> output/reel.mp4 + output/cover.jpg
        python3 make_reel.py --preview  -> a few still frames in output/preview/
"""
import math
import random
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"

# --- Words (edit these to personalize) --------------------------------------
TITLE_LINES = ["Meanwhile,", "back home…"]
HEADER = "Meanwhile, back home…"
SUBTITLE = ["a little update for", "our favorite college girl"]
NOTE_TITLE = "We miss you!"
NOTE_LINES = ["Can't wait to see you.", "Love, everyone back home"]

# photo file, caption, crop box in source pixels (None = centered 4:5), photo aspect (w/h)
PHOTOS = [
    ("01-pup-with-toy.jpg", "Toy's ready whenever you are!", None, 4 / 5),
    ("02-cookie-dough.jpg", "Found the cookie dough stash!", None, 4 / 5),
    ("03-puppy-eyes.jpg", "The “when is she coming home?” face", None, 4 / 5),
    ("04-kitchen-duo.jpg", "Welcome-home committee, on standby", (0, 250, 1450, 2062), 4 / 5),
    ("05-on-your-bed.jpg", "Keeping your bed warm for you", (150, 0, 1362, 1515), 4 / 5),
    ("06-patio-crew.jpg", "Patio crew says hi!", None, 4 / 5),
    ("07-cheers.jpg", "Cheers to you, kiddo!", (180, 0, 1150, 970), 1.0),
]

# --- Look -------------------------------------------------------------------
W, H, FPS = 1080, 1920, 30
CREAM = (246, 237, 222)
PAPER = (252, 250, 245)
INK = (66, 44, 33)          # chocolate brown, like the pups
ROSE = (214, 98, 118)
SAGE = (134, 163, 129)
MUSTARD = (226, 172, 72)
SKY = (120, 168, 204)
TAPES = [ROSE, SAGE, MUSTARD, SKY]

PACIFICO = str(ROOT / "fonts/pacifico/Pacifico-Regular.ttf")
CAVEAT = str(ROOT / "fonts/caveat/Caveat[wght].ttf")

# --- Timeline (seconds) -----------------------------------------------------
CARDS_START = 2.5
DROP, HOLD, FLY = 0.55, 1.65, 0.55
SLOT = DROP + HOLD + FLY
CARDS_END = CARDS_START + len(PHOTOS) * SLOT
NOTE_START = CARDS_END + 1.3
TOTAL = NOTE_START + 3.9

FEATURE_POS = (540, 1045)
FEATURE_SCALE = 1.05
FEATURE_ROT = [-2.5, 2.0, -1.5, 2.5, -2.0, 1.5, -1.0]
COLLAGE_SCALE = 0.40
COLLAGE = [  # (cx, cy, rotation) for each photo, in order
    (285, 505, -5), (795, 495, 4),
    (185, 1060, 3), (540, 1075, -2), (895, 1055, 3.5),
    (290, 1625, -4), (785, 1615, 5),
]
HEADER_Y = 150
BG_DIM = 0.28  # how much the collage fades back while a photo is featured


# --- Helpers ----------------------------------------------------------------
def font(path, size, bold=False):
    f = ImageFont.truetype(path, size)
    if bold:
        f.set_variation_by_name("Bold")
    return f


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(t):
    return max(0.0, min(1.0, t))


def ease_out_cubic(t):
    return 1 - (1 - t) ** 3


def ease_in_out_cubic(t):
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_back(t, s=1.4):
    t -= 1
    return 1 + (s + 1) * t ** 3 + s * t ** 2


def heart_sprite(size, color, alpha=255):
    """Antialiased heart, drawn at 4x then downsampled."""
    k = 4
    S = size * k
    im = Image.new("RGBA", (S, S), color + (0,))
    pts = []
    for i in range(200):
        t = 2 * math.pi * i / 200
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((S / 2 + x * S / 36, S * 0.45 - y * S / 36))
    ImageDraw.Draw(im).polygon(pts, fill=color + (alpha,))
    return im.resize((size, size), Image.LANCZOS)


def paw_sprite(size, color, alpha=255):
    k = 4
    S = size * k
    im = Image.new("RGBA", (S, S), color + (0,))
    d = ImageDraw.Draw(im)
    c = color + (alpha,)
    d.ellipse([S * 0.24, S * 0.46, S * 0.76, S * 0.92], fill=c)
    for cx, cy in [(0.16, 0.38), (0.36, 0.18), (0.64, 0.18), (0.84, 0.38)]:
        r = S * 0.11
        d.ellipse([S * cx - r, S * cy - r * 1.25, S * cx + r, S * cy + r * 1.25], fill=c)
    return im.resize((size, size), Image.LANCZOS)


def star_sprite(size, color, alpha=255):
    k = 4
    S = size * k
    im = Image.new("RGBA", (S, S), color + (0,))
    pts = []
    for i in range(10):
        r = S * (0.48 if i % 2 == 0 else 0.2)
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((S / 2 + r * math.cos(a), S / 2 + r * math.sin(a)))
    ImageDraw.Draw(im).polygon(pts, fill=color + (alpha,))
    return im.resize((size, size), Image.LANCZOS)


def grain(size, strength, seed):
    rnd = random.Random(seed)
    n = Image.effect_noise(size, 40).point(lambda v: 128 + (v - 128) * strength / 40)
    return n.convert("L")


def tinted_texture(size, color, strength, seed):
    base = Image.new("RGB", size, color)
    n = grain(size, strength, seed)
    return Image.composite(base.point(lambda v: min(255, v + 6)), base.point(lambda v: max(0, v - 6)), n)


def tape_strip(color, w=240, h=66, seed=0):
    """Washi tape with torn ends and a stripe pattern."""
    rnd = random.Random(seed)
    k = 3
    im = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    pts = [(0, 0)]
    for x in range(0, w * k + 1, 6 * k):
        pts.append((x, rnd.uniform(0, 4 * k)))
    pts.append((w * k, 0))
    right = [(w * k - rnd.uniform(0, 5 * k), y) for y in range(0, h * k + 1, 6 * k)]
    bottom = [(x, h * k - rnd.uniform(0, 4 * k)) for x in range(w * k, -1, -6 * k)]
    left = [(rnd.uniform(0, 5 * k), y) for y in range(h * k, -1, -6 * k)]
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).polygon(pts + right + bottom + left, fill=255)
    fill = Image.new("RGBA", im.size, color + (205,))
    stripes = ImageDraw.Draw(fill)
    light = tuple(min(255, c + 45) for c in color) + (205,)
    for x in range(-h * k, w * k, 22 * k):
        stripes.polygon([(x, h * k), (x + 9 * k, h * k), (x + 9 * k + h * k, 0), (x + h * k, 0)], fill=light)
    im.paste(fill, (0, 0), mask)
    return im.resize((w, h), Image.LANCZOS)


def draw_centered(draw, cx, y, text, fnt, fill):
    w = draw.textlength(text, font=fnt)
    draw.text((cx - w / 2, y), text, font=fnt, fill=fill)


def fit_caption(draw, text, max_w):
    """Largest Caveat size that fits on one line, else two lines."""
    for size in range(76, 59, -2):
        f = font(CAVEAT, size, bold=True)
        if draw.textlength(text, font=f) <= max_w:
            return f, [text]
    words = text.split()
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        cost = abs(len(a) - len(b))
        if best is None or cost < best[0]:
            best = (cost, [a, b])
    lines = best[1]
    for size in range(66, 40, -2):
        f = font(CAVEAT, size, bold=True)
        if max(draw.textlength(l, font=f) for l in lines) <= max_w:
            return f, lines
    return f, lines


# --- Cards ------------------------------------------------------------------
PAD = 80


class Sprite:
    """An RGBA image kept at a few pre-shrunk sizes for clean downscaling."""

    def __init__(self, im):
        self.mips = []
        s = 1.0
        while True:
            size = (max(1, round(im.width * s)), max(1, round(im.height * s)))
            mip = im if s == 1.0 else im.resize(size, Image.LANCZOS)
            self.mips.append((s, mip.convert("RGBa")))
            if s < 0.3:
                break
            s *= 0.7

    def pick(self, scale):
        chosen = self.mips[0]
        for s, mip in self.mips:
            if s >= scale * 0.98:
                chosen = (s, mip)
        return chosen


def make_card(idx, fname, caption, crop, aspect):
    src = ImageOps.exif_transpose(Image.open(ROOT / "photos" / fname)).convert("RGB")
    pw = 800
    ph = round(pw / aspect)
    if crop:
        src = src.crop(crop)
    photo = ImageOps.fit(src, (pw, ph), Image.LANCZOS, centering=(0.5, 0.5))

    m, bottom = 40, 190
    cw, ch = pw + 2 * m, ph + m + bottom
    card = tinted_texture((cw, ch), PAPER, 10, seed=idx).convert("RGBA")
    card.paste(photo, (m, m))
    d = ImageDraw.Draw(card)
    d.rectangle([m - 1, m - 1, m + pw, m + ph], outline=(0, 0, 0, 40))

    f, lines = fit_caption(d, caption, pw - 20)
    asc, desc = f.getmetrics()
    lh = asc + desc - 10
    y = m + ph + (bottom - lh * len(lines)) / 2 - 6
    for line in lines:
        draw_centered(d, cw / 2, y, line, f, INK)
        y += lh

    full = Image.new("RGBA", (cw + 2 * PAD, ch + 2 * PAD), (0, 0, 0, 0))
    shadow = Image.new("L", full.size, 0)
    ImageDraw.Draw(shadow).rectangle([PAD + 6, PAD + 18, PAD + cw + 6, PAD + ch + 18], fill=95)
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    full.putalpha(shadow)
    full.alpha_composite(card, (PAD, PAD))

    rnd = random.Random(idx * 7 + 3)
    tape = tape_strip(TAPES[idx % len(TAPES)], seed=idx).rotate(rnd.uniform(-7, 7), Image.BICUBIC, expand=True)
    full.alpha_composite(tape, (round(PAD + cw / 2 - tape.width / 2 + rnd.uniform(-60, 60)), PAD - tape.height // 2 + 4))
    return Sprite(full)


def place(canvas, sprite, cx, cy, scale, angle, alpha=1.0):
    """Draw sprite centered at (cx, cy) with sub-pixel position, scale and rotation."""
    ms, src = sprite.pick(scale)
    k = scale / ms
    w, h = src.size
    th = math.radians(angle)
    c, s = math.cos(th), math.sin(th)
    ex = k * (abs(w / 2 * c) + abs(h / 2 * s))
    ey = k * (abs(w / 2 * s) + abs(h / 2 * c))
    x0, y0 = math.floor(cx - ex) - 1, math.floor(cy - ey) - 1
    x1, y1 = math.ceil(cx + ex) + 1, math.ceil(cy + ey) + 1
    # inverse mapping: output pixel -> source pixel
    dx0, dy0 = x0 - cx, y0 - cy
    coeffs = (
        c / k, -s / k, (c * dx0 - s * dy0) / k + w / 2,
        s / k, c / k, (s * dx0 + c * dy0) / k + h / 2,
    )
    out = src.transform((x1 - x0, y1 - y0), Image.AFFINE, coeffs, resample=Image.BICUBIC).convert("RGBA")
    if alpha < 1.0:
        out.putalpha(out.getchannel("A").point(lambda v: round(v * alpha)))
    paste_clipped(canvas, out, x0, y0)


def paste_clipped(canvas, im, x, y):
    l, t = max(0, x), max(0, y)
    r, b = min(canvas.width, x + im.width), min(canvas.height, y + im.height)
    if r <= l or b <= t:
        return
    canvas.alpha_composite(im.crop((l - x, t - y, r - x, b - y)), (l, t))


# --- Static layers ----------------------------------------------------------
def make_background(w=W, h=H):
    bg = tinted_texture((w, h), CREAM, 14, seed=99).convert("RGBA")
    rnd = random.Random(5)
    makers = [heart_sprite, star_sprite, paw_sprite]
    for _ in range(46):
        size = rnd.randint(22, 46)
        color = rnd.choice([ROSE, SAGE, MUSTARD, SKY, INK])
        sp = rnd.choice(makers)(size, color, alpha=rnd.randint(45, 80))
        sp = sp.rotate(rnd.uniform(-25, 25), Image.BICUBIC, expand=True)
        bg.alpha_composite(sp, (rnd.randint(0, w - size), rnd.randint(0, h - size)))
    return bg


def text_sprite(lines, fnt, fill, spacing=0, extra=None):
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    asc, desc = fnt.getmetrics()
    lh = asc + desc + spacing
    tw = max(probe.textlength(l, font=fnt) for l in lines)
    im = Image.new("RGBA", (round(tw) + 40, lh * len(lines) + 40), fill + (0,))
    d = ImageDraw.Draw(im)
    for i, line in enumerate(lines):
        draw_centered(d, im.width / 2, 20 + i * lh, line, fnt, fill)
    return im


def make_title():
    title = text_sprite(TITLE_LINES, font(PACIFICO, 150), INK, spacing=-60)
    sub = text_sprite(SUBTITLE, font(CAVEAT, 72, bold=True), ROSE, spacing=-14)
    header = text_sprite([HEADER], font(PACIFICO, 70), INK)
    return Sprite(title), Sprite(sub), Sprite(header)


def make_cap(size=190):
    """Little graduation-cap doodle."""
    k = 3
    S = size * k
    im = Image.new("RGBA", (S, S), INK + (0,))
    d = ImageDraw.Draw(im)
    cx, cy = S / 2, S * 0.42
    d.polygon([(cx - S * 0.25, cy + S * 0.05), (cx + S * 0.25, cy + S * 0.05),
               (cx + S * 0.22, cy + S * 0.3), (cx - S * 0.22, cy + S * 0.3)], fill=INK)
    d.polygon([(cx, cy - S * 0.22), (cx + S * 0.48, cy), (cx, cy + S * 0.2), (cx - S * 0.48, cy)], fill=INK)
    d.line([(cx, cy), (cx + S * 0.36, cy + S * 0.06), (cx + S * 0.36, cy + S * 0.36)], fill=MUSTARD, width=5 * k)
    d.ellipse([cx + S * 0.31, cy + S * 0.34, cx + S * 0.41, cy + S * 0.48], fill=MUSTARD)
    return Sprite(im.resize((size, size), Image.LANCZOS))


def make_note():
    """Notebook-paper sign-off note."""
    nw, nh = 840, 560
    paper = tinted_texture((nw, nh), (253, 252, 248), 8, seed=11).convert("RGBA")
    d = ImageDraw.Draw(paper)
    for y in range(110, nh, 62):
        d.line([(0, y), (nw, y)], fill=(150, 185, 220, 255), width=3)
    d.line([(96, 0), (96, nh)], fill=(226, 120, 130, 255), width=3)
    for y in (90, nh // 2, nh - 90):
        d.ellipse([28, y - 18, 64, y + 18], fill=CREAM + (255,))

    title_f = font(PACIFICO, 104)
    body_f = font(CAVEAT, 66, bold=True)
    cx = 96 + (nw - 96) / 2
    tw = d.textlength(NOTE_TITLE, font=title_f)
    d.text((cx - tw / 2 - 34, 40), NOTE_TITLE, font=title_f, fill=ROSE)
    paper.alpha_composite(heart_sprite(74, ROSE), (round(cx + tw / 2 - 20), 112))
    draw_centered(d, cx, 266, NOTE_LINES[0], body_f, INK)
    lw = d.textlength(NOTE_LINES[1], font=body_f)
    draw_centered(d, cx - 30, 390, NOTE_LINES[1], body_f, INK)
    paper.alpha_composite(paw_sprite(58, INK), (round(cx - 30 + lw / 2 + 14), 410))

    full = Image.new("RGBA", (nw + 2 * PAD, nh + 2 * PAD), (0, 0, 0, 0))
    shadow = Image.new("L", full.size, 0)
    ImageDraw.Draw(shadow).rectangle([PAD + 6, PAD + 18, PAD + nw + 6, PAD + nh + 18], fill=100)
    full.putalpha(shadow.filter(ImageFilter.GaussianBlur(18)))
    full.alpha_composite(paper, (PAD, PAD))
    for i, (x, rot) in enumerate([(PAD + 40, -28), (PAD + nw - 40, 24)]):
        tape = tape_strip(TAPES[i * 2], w=190, h=60, seed=40 + i).rotate(rot, Image.BICUBIC, expand=True)
        full.alpha_composite(tape, (round(x - tape.width / 2), PAD - tape.height // 2 + 8))
    return Sprite(full)


# --- Animation --------------------------------------------------------------
def card_state(i, t):
    """(cx, cy, scale, angle, alpha) for card i at time t, or None before it appears."""
    t0 = CARDS_START + i * SLOT
    if t < t0:
        return None
    fx, fy = FEATURE_POS
    fr = FEATURE_ROT[i]
    tx, ty, tr = COLLAGE[i]
    lt = t - t0
    if lt < DROP:
        p = lt / DROP
        e = ease_out_back(p, 1.2)
        side = 1 if i % 2 == 0 else -1
        return (fx + side * 40 * (1 - e), lerp(fy - 320, fy, e), FEATURE_SCALE * lerp(1.2, 1.0, e),
                lerp(fr + 9 * side, fr, e), clamp(p / 0.35))
    lt -= DROP
    hold_scale = FEATURE_SCALE * (1.0 + 0.035 * clamp(lt / HOLD))
    hold_rot = fr + 0.6 * clamp(lt / HOLD)
    if lt < HOLD:
        return (fx, fy, hold_scale, hold_rot, 1.0)
    lt -= HOLD
    e = ease_in_out_cubic(clamp(lt / FLY))
    return (lerp(fx, tx, e), lerp(fy, ty, e), lerp(hold_scale, COLLAGE_SCALE, e), lerp(hold_rot, tr, e), 1.0)


class Hearts:
    def __init__(self):
        rnd = random.Random(21)
        self.items = []
        for _ in range(16):
            size = rnd.randint(34, 70)
            color = rnd.choice([ROSE, ROSE, (238, 140, 160), MUSTARD])
            self.items.append(dict(
                sprite=heart_sprite(size, color), x=rnd.uniform(40, W - 40), delay=rnd.uniform(0, 2.2),
                speed=rnd.uniform(380, 620), wob=rnd.uniform(18, 40), ph=rnd.uniform(0, 6.28),
            ))

    def draw(self, canvas, t):
        for h in self.items:
            lt = t - h["delay"]
            if lt < 0:
                continue
            y = H + 60 - lt * h["speed"]
            x = h["x"] + math.sin(lt * 2.4 + h["ph"]) * h["wob"]
            sp = h["sprite"]
            a = clamp((y + 100) / 700)
            if a <= 0:
                continue
            if a < 1:
                sp = sp.copy()
                sp.putalpha(sp.getchannel("A").point(lambda v: round(v * a)))
            paste_clipped(canvas, sp, round(x - sp.width / 2), round(y - sp.height / 2))


class Reel:
    def __init__(self):
        print("Building layers…", file=sys.stderr)
        self.bg = make_background()
        self.cards = [make_card(i, *p) for i, p in enumerate(PHOTOS)]
        self.title, self.sub, self.header = make_title()
        self.cap = make_cap()
        self.note = make_note()
        self.hearts = Hearts()
        self.settled_count = -1
        self.settled = None

    def settled_layer(self, n):
        if n != self.settled_count:
            layer = self.bg.copy()
            for i in range(n):
                x, y, r = COLLAGE[i]
                place(layer, self.cards[i], x, y, COLLAGE_SCALE, r)
            self.settled, self.settled_count = layer, n
        return self.settled

    def frame(self, t):
        n_settled = sum(1 for i in range(len(PHOTOS)) if t >= CARDS_START + (i + 1) * SLOT)
        base = self.settled_layer(n_settled)

        # fade the collage back while photos are featured; reveal it at the end
        if t < CARDS_START:
            dim = 0.0
        elif t < CARDS_END:
            dim = BG_DIM * clamp((t - CARDS_START) / 0.4)
        elif t < NOTE_START:
            dim = BG_DIM * (1 - ease_out_cubic(clamp((t - CARDS_END) / 0.5)))
        else:
            dim = 0.18 * clamp((t - NOTE_START) / 0.4)
        canvas = Image.blend(base, self.bg, dim) if dim > 0 else base.copy()

        self.draw_titles(canvas, t)

        for i in range(len(PHOTOS)):
            if i < n_settled:
                continue
            st = card_state(i, t)
            if st:
                cx, cy, s, a, al = st
                place(canvas, self.cards[i], cx, cy, s, a, al)
                break

        if t >= NOTE_START:
            p = clamp((t - NOTE_START) / 0.6)
            e = ease_out_back(p, 1.6)
            self.hearts.draw(canvas, t - NOTE_START - 0.2)
            place(canvas, self.note, 540, 1010, lerp(0.55, 1.0, e), lerp(-10, -2.5, e), clamp(p / 0.3))
        return canvas.convert("RGB")

    def draw_titles(self, canvas, t):
        pop = lambda t0: ease_out_back(clamp((t - t0) / 0.5), 1.6)
        out = ease_in_out_cubic(clamp((t - 1.95) / 0.4))
        if out < 1:
            fade = 1 - out
            shrink = lerp(1.0, 0.85, out)
            ty = 870 - 60 * out
            place(canvas, self.cap, 540, ty - 300, (0.2 + 0.8 * pop(0.0)) * shrink,
                  lerp(-12, 0, pop(0.0)), clamp(t / 0.25) * fade)
            place(canvas, self.title, 540, ty, lerp(0.6, 1.0, pop(0.15)) * shrink, -3,
                  clamp((t - 0.15) / 0.25) * fade)
            place(canvas, self.sub, 540, ty + 330, lerp(0.6, 1.0, pop(0.45)) * shrink,
                  -1.5, clamp((t - 0.45) / 0.25) * fade)
        e = ease_out_cubic(clamp((t - 2.2) / 0.45))
        if e > 0:
            place(canvas, self.header, 540, lerp(HEADER_Y - 30, HEADER_Y, e), lerp(1.12, 1.0, e), -1.5, e)


def main():
    OUT.mkdir(exist_ok=True)
    reel = Reel()
    if "--preview" in sys.argv:
        prev = OUT / "preview"
        prev.mkdir(exist_ok=True)
        for t in [1.6, 2.2, 2.5] + [CARDS_START + i * SLOT + DROP + 1.0 for i in range(len(PHOTOS))] + [CARDS_END - 0.3, NOTE_START - 0.2, TOTAL - 0.05]:
            reel.frame(t).save(prev / f"t{t:05.2f}.jpg", quality=88)
        print(f"Wrote previews to {prev}", file=sys.stderr)
        return

    encode(reel, TOTAL, OUT / "reel.mp4", cover=OUT / "cover.jpg")


def encode(reel, total, out, cover=None):
    """Pipe reel.frame(t) for every frame into an H.264 MP4 with a silent audio track."""
    frames = round(total * FPS)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-map", "0:v", "-map", "1:a", "-shortest",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
        "-profile:v", "high", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "128k", str(out),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(frames):
        t = f / FPS
        img = reel.frame(t)
        proc.stdin.write(img.tobytes())
        if cover and f == frames - 1:
            img.save(cover, quality=92)
        if f % FPS == 0:
            print(f"  {t:4.0f}s / {total:.0f}s", file=sys.stderr)
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("ffmpeg failed")
    print(f"Wrote {out} ({frames} frames, {total:.1f}s)", file=sys.stderr)


if __name__ == "__main__":
    main()
