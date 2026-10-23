# Reel: "Meanwhile, back home…"

A 9:16 Polaroid-collage reel (1080×1920, 30 fps, ~27 s) for our college girl.
Each photo drops in as a taped Polaroid with a handwritten caption, then flies
into a scrapbook collage that ends with a notebook-paper "We miss you!" note.

- `output/reel.mp4`: the finished reel (silent audio track, so add a song in Instagram/TikTok)
- `output/cover.jpg`: the final collage frame, handy as a cover or a still to text
- `output/carousel-reel.mp4`: carousel version (~25 s), where the Polaroids slide past like
  swiping an Instagram carousel, with page dots, ending on the note
- `output/carousel/`: the same story as nine 4:5 slides (1080×1350) for an Instagram carousel post
- `photos/`: the 7 source photos, in reel order
- `fonts/`: Pacifico and Caveat (SIL Open Font License, from Google Fonts)

## Re-render

Requires Python 3 with Pillow, and ffmpeg.

```sh
python3 make_reel.py            # writes output/reel.mp4 and output/cover.jpg
python3 make_reel.py --preview  # writes a few still frames to output/preview/
python3 make_carousel.py        # writes output/carousel-reel.mp4 and output/carousel/*.jpg
```

To change the wording, edit `TITLE_LINES`, `SUBTITLE`, `NOTE_TITLE`, `NOTE_LINES`
and the captions in `PHOTOS` at the top of `make_reel.py` (both versions use them). Colors (e.g. her
school colors) are the constants under `# --- Look`.
