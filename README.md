# Reel: "Meanwhile, back home…"

A 9:16 Polaroid-collage reel (1080×1920, 30 fps, ~27 s) for our college girl.
Each photo drops in as a taped Polaroid with a handwritten caption, then flies
into a scrapbook collage that ends with a notebook-paper "We miss you!" note.

- `output/reel.mp4`: the finished reel (silent audio track, so add a song in Instagram/TikTok)
- `output/cover.jpg`: the final collage frame, handy as a cover or a still to text
- `photos/`: the 7 source photos, in reel order
- `fonts/`: Pacifico and Caveat (SIL Open Font License, from Google Fonts)

## Re-render

Requires Python 3 with Pillow, and ffmpeg.

```sh
python3 make_reel.py            # writes output/reel.mp4 and output/cover.jpg
python3 make_reel.py --preview  # writes a few still frames to output/preview/
```

To change the wording, edit `TITLE_LINES`, `SUBTITLE`, `NOTE_TITLE`, `NOTE_LINES`
and the captions in `PHOTOS` at the top of `make_reel.py`. Colors (e.g. her
school colors) are the constants under `# --- Look`.
