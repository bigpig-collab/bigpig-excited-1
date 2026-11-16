"""Draw one exciting image and write it as entry.png.

A tiny rider surfs a colossal glowing jellyfish as it streaks
diagonally through deep space. The jellyfish dome is the blazing
focal point against a dark sky; its tentacles sweep back with the
motion, speed lines and stars rush past, and the rider is a small
dark silhouette on top of the dome, cape flying. Everything is
drawn from scratch with the standard library only, and the output
is fully deterministic.
"""

import binascii
import math
import os
import struct
import zlib

W = 768
H = 768

# ---------------------------------------------------------------- pixels

# rows[y] is a bytearray of W * 3 RGB bytes.
rows = []


def _lerp(a, b, t):
    return int(a + (b - a) * t + 0.5)


def _mix(c1, c2, t):
    return (_lerp(c1[0], c2[0], t), _lerp(c1[1], c2[1], t),
            _lerp(c1[2], c2[2], t))


def _fill_span(y, x0, x1, color):
    """Fill one horizontal run on row y with a solid colour."""
    if y < 0 or y >= H:
        return
    if x0 < 0:
        x0 = 0
    if x1 >= W:
        x1 = W - 1
    if x1 < x0:
        return
    row = rows[y]
    r, g, b = color
    span = bytes((r, g, b)) * (x1 - x0 + 1)
    row[x0 * 3:(x1 + 1) * 3] = span


def _fill_rect(x0, y0, x1, y1, color):
    for y in range(max(0, y0), min(H, y1 + 1)):
        _fill_span(y, x0, x1, color)


def _fill_ellipse(cx, cy, rx, ry, color):
    """Solid ellipse, scanline by scanline."""
    if rx <= 0 or ry <= 0:
        return
    for y in range(max(0, cy - ry), min(H, cy + ry + 1)):
        dy = (y - cy) / ry
        rem = 1.0 - dy * dy
        if rem < 0.0:
            continue
        dx = int(rx * math.sqrt(rem))
        _fill_span(y, cx - dx, cx + dx, color)


def _fill_disc(cx, cy, r, color):
    _fill_ellipse(cx, cy, r, r, color)


def _fill_polygon(points, color):
    """Scanline fill for a simple polygon (convex or concave)."""
    if len(points) < 3:
        return
    ys = [p[1] for p in points]
    y0 = max(0, min(ys))
    y1 = min(H - 1, max(ys))
    n = len(points)
    for y in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            x1, y1p = points[i]
            x2, y2p = points[(i + 1) % n]
            if y1p == y2p:
                continue
            if (y >= min(y1p, y2p)) and (y < max(y1p, y2p)):
                t = (y - y1p) / (y2p - y1p)
                xs.append(x1 + t * (x2 - x1))
        if len(xs) < 2:
            continue
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            _fill_span(y, int(math.ceil(xs[k])), int(math.floor(xs[k + 1])),
                       color)


def _thick_line(x0, y0, x1, y1, width, color):
    """A line drawn as a chain of discs (fast enough at this scale)."""
    dx = x1 - x0
    dy = y1 - y0
    dist = math.hypot(dx, dy)
    steps = max(1, int(dist / 3.0))
    r = max(1, width // 2)
    for i in range(steps + 1):
        t = i / steps
        _fill_disc(int(x0 + dx * t), int(y0 + dy * t), r, color)


# ---------------------------------------------------------------- text

# A small 5x7 bitmap font, defined by hand. '#' is ink, '.' is empty.
FONT = {
    'D': ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    'O': (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    'N': ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "'": ("..#..", "..#..", ".#...", ".....", ".....", ".....", "....."),
    'T': ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    ' ': (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    'B': ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    'L': ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    'I': (".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."),
    'K': ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    '.': (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
}


def _draw_text(text, x, y, scale, color, shadow=None):
    """Draw text with the bitmap font; returns the width in pixels."""
    cx = x
    for ch in text:
        glyph = FONT.get(ch, FONT[' '])
        for gy, line in enumerate(glyph):
            for gx, bit in enumerate(line):
                if bit != '#':
                    continue
                px = cx + gx * scale
                py = y + gy * scale
                if shadow is not None:
                    _fill_rect(px + 2, py + 2, px + scale + 1,
                               py + scale + 1, shadow)
                _fill_rect(px, py, px + scale - 1, py + scale - 1, color)
        cx += 5 * scale + scale + 2
    return cx - x - (scale + 2)


# ---------------------------------------------------------------- scene

def _background():
    top = (7, 10, 36)
    mid = (16, 14, 58)
    bot = (43, 12, 74)
    for y in range(H):
        if y < H // 2:
            c = _mix(top, mid, y / (H // 2))
        else:
            c = _mix(mid, bot, (y - H // 2) / (H // 2))
        rows.append(bytearray(bytes(c) * W))


def _stars():
    # Fixed-seed linear congruential generator: deterministic.
    state = 123456789
    for _ in range(170):
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        x = state % W
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        y = state % 560
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        kind = state % 10
        if kind < 7:
            _fill_disc(x, y, 1, (235, 240, 255))
        elif kind < 9:
            _fill_disc(x, y, 2, (200, 225, 255))
            _fill_span(y, x - 4, x + 4, (180, 210, 255))
            for yy in range(y - 4, y + 5):
                if 0 <= yy < H:
                    rows[yy][x * 3:(x + 1) * 3] = bytes((180, 210, 255))
        else:
            _fill_disc(x, y, 2, (255, 226, 140))


def _speed_lines():
    # Diagonal streaks rushing from top-right to bottom-left.
    lines = [
        (640, 90, 760, 30, 3, (120, 240, 255)),
        (560, 130, 700, 70, 2, (255, 120, 220)),
        (690, 210, 768, 170, 3, (255, 230, 120)),
        (60, 640, 190, 580, 3, (120, 240, 255)),
        (120, 700, 260, 640, 2, (255, 120, 220)),
        (30, 540, 150, 490, 2, (255, 230, 120)),
        (620, 560, 740, 500, 2, (140, 250, 255)),
        (90, 180, 210, 120, 2, (200, 220, 255)),
        (700, 420, 768, 385, 3, (255, 150, 200)),
        (40, 330, 150, 285, 2, (255, 220, 110)),
    ]
    for x0, y0, x1, y1, w, c in lines:
        _thick_line(x0, y0, x1, y1, w, c)


def _glow():
    # Soft halo behind the dome: many concentric ellipses stepping
    # from the background colour out to a bright violet-blue.
    cx, cy = 384, 330
    bg = (16, 14, 58)
    glow = (52, 66, 168)
    steps = 26
    for i in range(steps, 0, -1):
        t = i / steps
        rx = int(170 + 200 * t)
        ry = int(130 + 170 * t)
        _fill_ellipse(cx, cy, rx, ry, _mix(glow, bg, t * t))


def _dome():
    cx, cy, rx, ry = 384, 310, 290, 205
    # Horizontal colour bands: bright cyan crown, aqua middle,
    # magenta-violet skirt.
    for y in range(max(0, cy - ry), min(H, cy + ry + 1)):
        dy = (y - cy) / ry
        rem = 1.0 - dy * dy
        if rem < 0.0:
            continue
        dx = int(rx * math.sqrt(rem))
        t = (y - (cy - ry)) / (2 * ry)  # 0 at crown, 1 at skirt
        if t < 0.35:
            c = _mix((190, 250, 255), (34, 211, 238), t / 0.35)
        elif t < 0.75:
            c = _mix((34, 211, 238), (217, 70, 239), (t - 0.35) / 0.40)
        else:
            c = _mix((217, 70, 239), (147, 51, 234), (t - 0.75) / 0.25)
        _fill_span(y, cx - dx, cx + dx, c)
    # Bright rim following the curve of the crown, not a flat stripe.
    a = math.pi * 1.12
    while a < math.pi * 1.88:
        px = int(cx + rx * math.cos(a))
        py = int(cy + ry * math.sin(a))
        _fill_disc(px, py, 7, (225, 252, 255))
        a += 0.028
    # Inner glow spots on the dome.
    for sx, sy, sr, c in [
            (300, 240, 30, (255, 255, 255)),
            (430, 195, 20, (190, 245, 255)),
            (470, 285, 14, (255, 190, 240)),
            (250, 325, 12, (160, 230, 255)),
            (510, 365, 18, (255, 210, 120)),
            (350, 395, 24, (255, 150, 220)),
    ]:
        _fill_ellipse(sx, sy, sr, int(sr * 0.7), c)
    # Frilly skirt edge along the bottom of the dome.
    for i in range(11):
        fx = cx - rx + 30 + i * 52
        _fill_disc(fx, cy + ry - 18, 20, (217, 70, 239))
        _fill_disc(fx, cy + ry - 18, 12, (240, 120, 250))


def _tentacles():
    # Nine tentacles sweeping down and to the left, tapering as they go.
    palette = [(34, 211, 238), (217, 70, 239), (255, 190, 60),
               (120, 240, 255), (255, 90, 180)]
    for i in range(9):
        base_x = 384 - 220 + i * 55
        start_y = 500
        length = 150 + ((i * 37) % 90)
        phase = i * 0.9
        col = palette[i % len(palette)]
        dim = _mix(col, (16, 14, 58), 0.55)
        # Faint wide underlay first, then the bright core.
        for wide, c in ((True, dim), (False, col)):
            y = start_y
            while y < start_y + length and y < H - 8:
                prog = (y - start_y) / length
                sway = 42.0 * math.sin((y - start_y) / 65.0 + phase)
                drift = -0.38 * (y - start_y)
                x = int(base_x + sway + drift)
                thick = (13 if wide else 7) * (1.0 - 0.65 * prog)
                _fill_disc(x, y, max(2, int(thick)), c)
                y += 4
        # Glowing orb at the tip.
        tip_y = start_y + length
        tip_x = int(base_x + 42.0 * math.sin(length / 65.0 + phase)
                    - 0.38 * length)
        _fill_disc(tip_x, tip_y, 9, (255, 245, 180))
        _fill_disc(tip_x, tip_y, 5, (255, 255, 255))


def _rider():
    # A tiny dark silhouette surfing down the dome's upper-right
    # slope on a small board, cape streaming behind up to the left.
    # The scale joke: this little rider is steering something
    # colossal, and the slope gives the whole image its diagonal.
    ink = (10, 8, 24)
    # Board, tilted along the dome's curve (surface falls to the right).
    _fill_polygon([(522, 128), (598, 166), (592, 174), (516, 136)],
                  (255, 170, 40))
    # Legs and torso, leaning into the slope.
    _fill_polygon([(546, 150), (570, 158), (564, 124), (550, 122)], ink)
    _fill_polygon([(548, 124), (568, 130), (572, 100), (552, 94)], ink)
    _fill_disc(562, 86, 10, ink)  # head
    # Helmet glint.
    _fill_disc(566, 82, 3, (255, 220, 120))
    # Arm reaching forward, down the slope.
    _fill_polygon([(566, 104), (596, 124), (592, 132), (564, 112)], ink)
    # Cape streaming back, up to the left.
    _fill_polygon([(552, 98), (496, 52), (506, 88), (550, 110)],
                  (255, 70, 60))
    _fill_polygon([(552, 102), (512, 66), (520, 94), (550, 112)],
                  (255, 140, 50))


def _bubbles():
    for bx, by, br, c in [
            (150, 470, 10, (150, 235, 255)),
            (620, 480, 8, (255, 170, 230)),
            (110, 560, 6, (200, 240, 255)),
            (660, 580, 12, (255, 220, 130)),
            (200, 620, 7, (170, 240, 255)),
            (580, 640, 6, (255, 150, 200)),
    ]:
        _fill_disc(bx, by, br, c)
        _fill_disc(bx - 3, by - 3, max(2, br // 3), (255, 255, 255))


# ---------------------------------------------------------------- png

def _png_chunk(kind, data):
    chunk = struct.pack(">I", len(data)) + kind + data
    chunk += struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
    return chunk


def _encode_png():
    raw = bytearray()
    for row in rows:
        raw.append(0)  # filter: none
        raw.extend(row)
    compressed = zlib.compress(bytes(raw), 6)
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    out = bytearray(b"\x89PNG\r\n\x1a\n")
    out += _png_chunk(b"IHDR", ihdr)
    out += _png_chunk(b"IDAT", compressed)
    out += _png_chunk(b"IEND", b"")
    return bytes(out)


def main():
    _background()
    _stars()
    _glow()
    _speed_lines()
    _dome()
    _tentacles()
    _rider()
    _bubbles()
    _draw_text("DON'T BLINK.", 196, 26, 5, (255, 225, 77),
               shadow=(20, 8, 40))
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(_encode_png())


if __name__ == "__main__":
    main()
