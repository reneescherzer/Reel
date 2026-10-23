#!/usr/bin/env python3
"""Carousel versions of the "Meanwhile, back home..." reel.

- output/carousel-reel.mp4: a 9:16 video where the Polaroids slide past like a
  swipeable carousel (neighbors peeking in at the edges, page dots below),
  ending on the "We miss you!" note.
- output/carousel/NN-*.jpg: the same story as 4:5 slides for an Instagram
  carousel post (cover, one slide per photo, the note last).

Usage:  python3 make_carousel.py            -> both of the above
        python3 make_carousel.py --preview  -> a few still frames in output/preview/
"""
import math
import sys

from PIL import Image, ImageDraw

import make_reel as R
from make_reel import (
    INK, OUT, PHOTOS, ROSE, clamp, ease_in_out_cubic, ease_out_cubic, font,
    heart_sprite, lerp, paste_clipped, place, text_sprite,
)

ENTER_START, ENTER = 2.3, 0.7
ITEM_HOLD, ITEM_MOVE = 2.0, 0.6
N_ITEMS = len(PHOTOS) + 1  # the photos, then the note
NOTE_ARRIVE = ENTER_START + ENTER + (N_ITEMS - 1) * (ITEM_HOLD + ITEM_MOVE)
TOTAL = NOTE_ARRIVE + 3.6

CENTER_Y = 1020
SPACING = 640        # center-to-neighbor distance
FAR_SPACING = 430    # extra distance for items beyond the neighbors
SIDE_SCALE = 0.72    # neighbors relative to the centered item
CARD_SCALE = 0.86
NOTE_SCALE = 1.0
TILTS = [-2.0, 1.8, -1.5, 2.2, -1.8, 1.5, -1.2, -2.5]
DOTS_Y = 1800


def carousel_pos(t):
    """Fractional index of the item sitting in the center at time t."""
    if t < ENTER_START:
        return None
    if t < ENTER_START + ENTER:
        return lerp(-1.6, 0.0, ease_out_cubic((t - ENTER_START) / ENTER))
    lt = t - ENTER_START - ENTER
    step = ITEM_HOLD + ITEM_MOVE
    k = int(lt // step)
    if k >= N_ITEMS - 1:
        return float(N_ITEMS - 1)
    r = lt - k * step
    if r < ITEM_HOLD:
        return float(k)
    return k + ease_in_out_cubic((r - ITEM_HOLD) / ITEM_MOVE)


def arrival(i):
    return ENTER_START + ENTER + i * (ITEM_HOLD + ITEM_MOVE)


def circle_sprite(r, color, alpha=255):
    k = 4
    im = Image.new("RGBA", (2 * r * k, 2 * r * k), color + (0,))
    ImageDraw.Draw(im).ellipse([0, 0, 2 * r * k - 1, 2 * r * k - 1], fill=color + (alpha,))
    return im.resize((2 * r, 2 * r), Image.LANCZOS)


class CarouselReel(R.Reel):
    def __init__(self):
        super().__init__()
        self.items = self.cards + [self.note]
        self.base_scale = [CARD_SCALE] * len(self.cards) + [NOTE_SCALE]
        self.dot = circle_sprite(9, INK, 70)
        self.dot_on = circle_sprite(12, ROSE)

    def frame(self, t):
        canvas = self.bg.copy()
        self.draw_titles(canvas, t)
        pos = carousel_pos(t)
        if pos is None:
            return canvas.convert("RGB")

        if t >= NOTE_ARRIVE - 0.3:
            self.hearts.draw(canvas, t - NOTE_ARRIVE + 0.1)

        # far items first so the centered one lands on top
        for i in sorted(range(N_ITEMS), key=lambda i: -abs(i - pos)):
            d = i - pos
            ad = abs(d)
            if ad > 2.2:
                continue
            x = 540 + math.copysign(min(ad, 1) * SPACING + max(ad - 1, 0) * FAR_SPACING, d)
            grow = 1 + 0.025 * clamp((t - arrival(i)) / ITEM_HOLD) if t >= arrival(i) else 1
            s = self.base_scale[i] * lerp(1, SIDE_SCALE, min(ad, 1)) * grow
            place(canvas, self.items[i], x, CENTER_Y + 25 * min(ad, 1), s, TILTS[i])

        self.draw_dots(canvas, pos, t)
        return canvas.convert("RGB")

    def draw_dots(self, canvas, pos, t):
        a = clamp((t - ENTER_START) / 0.4)
        gap = 40
        x0 = 540 - gap * (N_ITEMS - 1) / 2
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        for i in range(N_ITEMS):
            paste_clipped(layer, self.dot, round(x0 + i * gap - 9), DOTS_Y - 9)
        hx = x0 + clamp(pos / (N_ITEMS - 1)) * (N_ITEMS - 1) * gap
        paste_clipped(layer, self.dot_on, round(hx - 12), DOTS_Y - 12)
        if a < 1:
            layer.putalpha(layer.getchannel("A").point(lambda v: round(v * a)))
        canvas.alpha_composite(layer)


# --- Instagram carousel slides (4:5) ----------------------------------------
SW, SH = 1080, 1350


def swipe_hint():
    """"swipe" plus a drawn arrow (the handwriting font has no arrow glyph)."""
    word = text_sprite(["swipe"], font(R.CAVEAT, 60, bold=True), INK)
    k = 3
    aw, ah = 110, word.height
    arrow = Image.new("RGBA", (aw * k, ah * k), INK + (0,))
    d = ImageDraw.Draw(arrow)
    y = ah * k * 0.55
    d.line([(6 * k, y), (aw * k - 14 * k, y)], fill=INK + (255,), width=5 * k)
    d.line([(aw * k - 36 * k, y - 20 * k), (aw * k - 12 * k, y), (aw * k - 36 * k, y + 20 * k)],
           fill=INK + (255,), width=5 * k, joint="curve")
    arrow = arrow.resize((aw, ah), Image.LANCZOS)
    im = Image.new("RGBA", (word.width + aw, ah), INK + (0,))
    im.alpha_composite(word, (0, 0))
    im.alpha_composite(arrow, (word.width - 20, 0))
    return im


def make_slides(reel):
    out = OUT / "carousel"
    out.mkdir(exist_ok=True)
    for old in out.glob("*.jpg"):
        old.unlink()
    bg = R.make_background(SW, SH)
    n = 0

    def save(img, name):
        nonlocal n
        n += 1
        img.convert("RGB").save(out / f"{n:02d}-{name}.jpg", quality=93)

    # cover: title over a fan of three Polaroids
    cover = bg.copy()
    for i, x, rot in [(0, 290, 9), (3, 790, -8), (2, 540, -1)]:
        place(cover, reel.cards[i], x, 990, 0.42, rot)
    place(cover, reel.cap, 540, 120, 0.8, -6)
    place(cover, reel.title, 540, 350, 0.82, -3)
    place(cover, reel.sub, 540, 605, 0.95, -1.5)
    place(cover, R.Sprite(swipe_hint()), 880, 1308, 1.0, -3)
    save(cover, "cover")

    # one slide per photo
    for i, card in enumerate(reel.cards):
        slide = bg.copy()
        place(slide, reel.header, 540, 105, 0.95, -1.5)
        place(slide, card, 540, 755, 0.84, TILTS[i])
        save(slide, R.PHOTOS[i][0].split(".")[0].split("-", 1)[1])

    # the note, with a scatter of hearts
    slide = bg.copy()
    for x, y, size, col in [(160, 260, 70, ROSE), (900, 300, 56, R.MUSTARD), (220, 1120, 54, R.MUSTARD),
                            (880, 1090, 76, ROSE), (540, 210, 44, (238, 140, 160)), (110, 700, 40, ROSE),
                            (980, 720, 46, (238, 140, 160))]:
        h = heart_sprite(size, col)
        paste_clipped(slide, h, x - size // 2, y - size // 2)
    place(slide, reel.note, 540, 690, 1.05, -2.5)
    save(slide, "we-miss-you")
    print(f"Wrote {n} slides to {out}", file=sys.stderr)


def main():
    OUT.mkdir(exist_ok=True)
    reel = CarouselReel()
    if "--preview" in sys.argv:
        prev = OUT / "preview"
        prev.mkdir(exist_ok=True)
        for t in [2.6, arrival(0) + 1, arrival(0) + ITEM_HOLD + 0.3, arrival(3) + 1, arrival(6) + 1,
                  NOTE_ARRIVE - 0.3, TOTAL - 0.05]:
            reel.frame(t).save(prev / f"c{t:05.2f}.jpg", quality=88)
        make_slides(reel)
        print(f"Wrote previews to {prev}", file=sys.stderr)
        return
    make_slides(reel)
    R.encode(reel, TOTAL, OUT / "carousel-reel.mp4")


if __name__ == "__main__":
    main()
