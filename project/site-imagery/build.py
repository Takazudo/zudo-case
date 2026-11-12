#!/usr/bin/env python3
"""Generate the ZUDO CASE logo SVG and the editable sharing-card SVG.

Outputs (paths relative to the repository root):
  public/img/zudo-case-logo.svg       homepage illustration (CSS-mask friendly, transparent)
  project/site-imagery/ogp-card.svg   complete 1200x630 sharing card, text outlined to paths

Render the PNG afterwards with `node project/site-imagery/render.mjs`.
The illustration is decorative branding, not a drawing of any approved case design.
"""
import argparse
import hashlib
import pathlib

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = pathlib.Path(__file__).resolve().parents[2]

# ---- Card content and style (edit here) ----
TITLE = "ZUDO CASE"
SUBTITLE = "Modular synthesizer cases"
DOMAIN = "zudo-case.zudolab.dev"
BG = "#242629"      # Graphite background
FG = "#D3D5D9"      # Graphite foreground
ACCENT = "#E9AA79"  # restrained copper accent
FONT_DIR = pathlib.Path("/usr/share/fonts/opentype/inter")
TITLE_FONT = "InterDisplay-Bold.otf"
SUBTITLE_FONT = "Inter-Medium.otf"
DOMAIN_FONT = "Inter-Medium.otf"
W, H = 1200, 630

# ---- Illustration geometry (logo viewBox 1200 x 630, same aspect as the home logo box) ----
LW, LH = 1200, 630
FRAME = dict(x=150, y=45, w=900, h=540, rx=40, stroke=30)
RAIL_H = 28
ROWS = [  # (top rail y, bottom rail y, bare-rail span x0..x1, modules [(x, w, kind)])
    (82, 280, (616, 1020), [(190, 140, "osc"), (342, 90, "jacks"), (444, 160, "filter")]),
    (322, 520, (180, 688), [(700, 100, "jacks2"), (812, 198, "seq")]),
]
SLOT_PITCH, SLOT_W, SLOT_H = 52, 22, 9
LINE = 11        # module outline / knob stroke
KNOB_R, JACK_R = 22, 9


def rounded_rect(x, y, w, h, r):
    return (f"M{x + r},{y}H{x + w - r}A{r},{r} 0 0 1 {x + w},{y + r}V{y + h - r}"
            f"A{r},{r} 0 0 1 {x + w - r},{y + h}H{x + r}A{r},{r} 0 0 1 {x},{y + h - r}"
            f"V{y + r}A{r},{r} 0 0 1 {x + r},{y}Z")


def rail(x0, x1, y):
    """Bare rail segment with mounting slots cut out (evenodd)."""
    d = [rounded_rect(x0, y, x1 - x0, RAIL_H, 6)]
    cy = y + RAIL_H / 2 - SLOT_H / 2
    sx = x0 + 26
    while sx + SLOT_W <= x1 - 20:
        d.append(rounded_rect(sx, cy, SLOT_W, SLOT_H, SLOT_H / 2))
        sx += SLOT_PITCH
    return f'<path fill-rule="evenodd" d="{"".join(d)}"/>'


def module(x, w, top, bottom, kind):
    y0, y1 = top + 4, bottom + RAIL_H - 4
    h = y1 - y0
    cx = x + w / 2
    out = [f'<path d="{rounded_rect(x + LINE / 2, y0 + LINE / 2, w - LINE, h - LINE, 8)}" '
           f'fill="none" stroke="currentColor" stroke-width="{LINE}"/>']
    for sy in (y0 + 20, y1 - 20):  # panel screws
        out.append(f'<circle cx="{cx}" cy="{sy}" r="5.5"/>')
    knobs, jacks = [], []
    mid = (y0 + y1) / 2
    if kind == "osc":
        knobs = [(x + w * 0.28, mid - 52), (x + w * 0.72, mid - 52), (cx, mid + 14)]
        jacks = [(x + w * 0.3, mid + 72), (x + w * 0.7, mid + 72)]
    elif kind == "jacks":
        jacks = [(cx, mid - 64), (cx, mid - 22), (cx, mid + 20), (cx, mid + 62)]
    elif kind == "filter":
        knobs = [(x + w * 0.5, mid - 50)]
        knobs_small = [(x + w * 0.28, mid + 16), (x + w * 0.72, mid + 16)]
        knobs += knobs_small
        jacks = [(x + w * 0.22, mid + 62), (x + w * 0.5, mid + 62), (x + w * 0.78, mid + 62)]
    elif kind == "jacks2":
        knobs = [(cx, mid - 50)]
        jacks = [(cx, mid + 12), (cx, mid + 58)]
    elif kind == "seq":
        for i in range(3):
            knobs.append((x + 44 + i * ((w - 88) / 2), mid - 40))
        for i in range(4):
            jacks.append((x + 34 + i * ((w - 68) / 3), mid + 48))
    for kx, ky in knobs:
        out.append(f'<circle cx="{kx:.1f}" cy="{ky:.1f}" r="{KNOB_R}" fill="none" '
                   f'stroke="currentColor" stroke-width="{LINE}"/>')
    for jx, jy in jacks:
        out.append(f'<circle cx="{jx:.1f}" cy="{jy:.1f}" r="{JACK_R}" fill="none" '
                   f'stroke="currentColor" stroke-width="{LINE * 0.7:.1f}"/>')
    return out


def illustration_body():
    f = FRAME
    parts = [f'<path d="{rounded_rect(f["x"], f["y"], f["w"], f["h"], f["rx"])}" fill="none" '
             f'stroke="currentColor" stroke-width="{f["stroke"]}"/>']
    for top, bottom, (x0, x1), modules in ROWS:
        parts.append(rail(x0, x1, top))
        parts.append(rail(x0, x1, bottom))
        for x, w, kind in modules:
            parts.extend(module(x, w, top, bottom, kind))
    return "\n  ".join(parts)


def logo_svg():
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {LW} {LH}" '
            f'width="{LW}" height="{LH}" fill="#000" color="#000">\n'
            f'  <title>ZUDO CASE</title>\n  {illustration_body()}\n</svg>\n')


def text_path(font_file, text, size, x, baseline, tracking=0.0):
    font = TTFont(FONT_DIR / font_file)
    gs = font.getGlyphSet()
    cmap = font.getBestCmap()
    scale = size / font["head"].unitsPerEm
    pen = SVGPathPen(gs)
    cursor = 0.0
    for ch in text:
        name = cmap[ord(ch)]
        tp = TransformPen(pen, (scale, 0, 0, -scale, x + cursor, baseline))
        gs[name].draw(tp)
        cursor += gs[name].width * scale + tracking
    return pen.getCommands(), cursor - tracking


def font_fingerprint():
    out = []
    for name in sorted({TITLE_FONT, SUBTITLE_FONT, DOMAIN_FONT}):
        data = (FONT_DIR / name).read_bytes()
        out.append(f"{name} sha256:{hashlib.sha256(data).hexdigest()[:16]}")
    return "; ".join(out)


def card_svg():
    # Illustration: logo viewBox scaled into the left area.
    ill_w = 500
    ill_h = ill_w * LH / LW
    ill_x, ill_y = 40, (H - ill_h) / 2
    tx = 566  # text column start
    title_d, title_w = text_path(TITLE_FONT, TITLE, 92, tx, 304, tracking=1.0)
    sub_d, sub_w = text_path(SUBTITLE_FONT, SUBTITLE, 34, tx + 2, 364)
    dom_d, dom_w = text_path(DOMAIN_FONT, DOMAIN, 24, tx + 2, 438, tracking=0.4)
    right = tx + max(title_w, sub_w, dom_w)
    if right > W - 80:
        raise SystemExit(f"text overflows the safe area: right edge {right:.1f}")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <!-- ZUDO CASE sharing card. Generated by project/site-imagery/build.py; text outlined from Inter
       ({font_fingerprint()}). Edit build.py, not this file. -->
  <rect width="{W}" height="{H}" fill="{BG}"/>
  <svg x="{ill_x}" y="{ill_y:.1f}" width="{ill_w}" height="{ill_h:.1f}" viewBox="0 0 {LW} {LH}" fill="{FG}" color="{FG}">
  {illustration_body()}
  </svg>
  <rect x="{tx + 2}" y="200" width="72" height="6" rx="3" fill="{ACCENT}"/>
  <path fill="{FG}" d="{title_d}"/>
  <path fill="{FG}" fill-opacity="0.78" d="{sub_d}"/>
  <path fill="{ACCENT}" d="{dom_d}"/>
</svg>
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="fail if committed SVGs differ from generated output")
    args = ap.parse_args()
    outputs = {
        ROOT / "public/img/zudo-case-logo.svg": logo_svg(),
        ROOT / "project/site-imagery/ogp-card.svg": card_svg(),
    }
    stale = []
    for path, text in outputs.items():
        if args.check:
            if not path.exists() or path.read_text() != text:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            print(f"wrote {path.relative_to(ROOT)} ({len(text.encode())} bytes)")
    if stale:
        raise SystemExit("stale: " + ", ".join(stale))


if __name__ == "__main__":
    main()
