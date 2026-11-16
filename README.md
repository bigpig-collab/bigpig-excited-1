# DON'T BLINK.

A tiny rider surfs a colossal glowing jellyfish as it streaks through
deep space. The jellyfish dome is the blazing centre of the picture,
its tentacles sweeping back with the motion while stars and speed
lines rush past diagonally. The joke is the scale: one small figure
with a flying red cape, steering something enormous.

The picture is drawn entirely by `main.py` — no image files, no
network, only the Python standard library. It builds the PNG bytes
itself and writes them deterministically, so every run produces the
exact same file.

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

That writes `out/entry.png` (768 by 768 pixels).
