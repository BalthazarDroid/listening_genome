"""Generate the Listening Genome brand icon (HA `brand/` folder).

Draws a short double-helix segment with Pillow at 8x supersampling, then downsamples.
Colours are the app's four OKLCH bases (frontend/src/helpers/genome_color.ts:
BASE_HUES = 220, 310, 40, 130 at L=0.74, C=0.115), converted here with the same maths.

    python hacs/scripts/make_icon.py            # writes brand/*.png
    python hacs/scripts/make_icon.py --preview OUT.png   # also writes the comparison sheet

Needs Pillow; uses `pyoxipng` for lossless optimisation when installed.
"""

from __future__ import annotations

import argparse
import io
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

BASE_HUES = [220, 310, 40, 130]  # blue, magenta, orange, green
BASE_L = 0.74
BASE_C = 0.115

BRAND_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "listening_genome" / "brand"


def oklch(l: float, c: float, h_deg: float) -> tuple[int, int, int]:  # noqa: E741 - L of OKLCH, as genome_color.ts names it
    """OKLCH -> 8-bit sRGB, clipped per channel (same as genome_color.ts)."""
    h = math.radians(h_deg)
    a, b = c * math.cos(h), c * math.sin(h)
    lc = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3
    mc = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3
    sc = (l - 0.0894841775 * a - 1.291485548 * b) ** 3
    lin = (
        4.0767416621 * lc - 3.3077115913 * mc + 0.2309699292 * sc,
        -1.2684380046 * lc + 2.6097574011 * mc - 0.3413193965 * sc,
        -0.0041960863 * lc - 0.7034186147 * mc + 1.707614701 * sc,
    )

    def enc(v: float) -> int:
        v = max(0.0, min(1.0, v))
        v = 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
        return round(v * 255)

    return tuple(enc(v) for v in lin)  # type: ignore[return-value]


BASES = [oklch(BASE_L, BASE_C, h) for h in BASE_HUES]
# Deeper tones of the same hues/chroma, for strokes that must hold up on white.
DEEP = [oklch(0.60, BASE_C, h) for h in BASE_HUES]
DUST = oklch(0.88, 0.006, 240)  # genome_color.ts DUST: the uncoloured structure
DUST_BACK = oklch(0.58, 0.006, 240)  # the same DUST, dimmed, for the strand behind the rungs
TILE = oklch(0.20, 0.012, 270)  # the app's near-black card, faintly cool
RIM = oklch(0.34, 0.02, 270)  # faint edge so the tile separates from a #1c1c1c page

SS = 8  # supersampling factor


def hexc(rgb) -> str:
    return "#{:02x}{:02x}{:02x}".format(*tuple(rgb[:3]))


def _cap_line(d: ImageDraw.ImageDraw, p0, p1, w, fill):
    d.line([p0, p1], fill=fill, width=int(w))
    r = w / 2
    for x, y in (p0, p1):
        d.ellipse([x - r, y - r, x + r, y + r], fill=fill)


def _butt_line(d: ImageDraw.ImageDraw, p0, p1, w, fill):
    """A bar that stops exactly at its end points (no caps), so a rung ends on the strand."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    if L < 1:
        return
    nx, ny = -(y1 - y0) / L * w / 2, (x1 - x0) / L * w / 2
    d.polygon(
        [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], fill=fill
    )


def _dim(rgb, f):
    return (*tuple(int(v * f) for v in rgb[:3]), 255)


def helix(
    size: int,
    *,
    horizontal: bool,
    twists: float,
    strand_w: float,
    rung_w: float,
    rungs: int,
    strand_cols,
    rung_cols,
    amp: float = 0.36,
    length: float = 0.86,
    back_dim: float = 0.55,
    rung_shrink: float = 0.0,
    dots: bool = False,
    tile: tuple | None = None,
    glow: bool = False,
    phase0: float = math.pi / 2,
    rung_positions: list | None = None,
    tile_radius: float = 0.22,
    rim: tuple | None = None,
    core: bool = False,
    back_col: tuple | None = None,
    round_rungs: bool = True,
) -> Image.Image:
    """Render a helix segment on a transparent canvas; all measures are fractions of size."""
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))  # helix structure only
    d = ImageDraw.Draw(img)
    glow_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)

    c = S / 2
    L = S * length
    A = S * amp

    def pt(t, strand):
        ph = 2 * math.pi * twists * t + phase0 + strand * math.pi
        along = c - L / 2 + L * t
        across = c + A * math.sin(ph)
        z = math.cos(ph)
        return ((along, across) if horizontal else (across, along)), z

    items = []  # (z, kind, payload)
    N = 400
    for s in (0, 1):
        for i in range(N):
            t0, t1 = i / N, (i + 1) / N
            (p0, z0), (p1, z1) = pt(t0, s), pt(t1, s)
            items.append(((z0 + z1) / 2, "seg", (p0, p1, s, (t0 + t1) / 2)))
    rung_ts = rung_positions or [(k + 0.5) / rungs for k in range(rungs)]
    for k, t in enumerate(rung_ts):
        (a, _), (b, _) = pt(t, 0), pt(t, 1)
        items.append((0.0, "rung", (a, b, k)))
    items.sort(key=lambda it: it[0])

    for z, kind, pl in items:
        if kind == "seg":
            p0, p1, s, _tm = pl
            col = strand_cols[s]
            if back_col is not None:
                # flat two-tone depth: same width, dimmer colour for the half behind the rungs
                w = strand_w * S
                fill = (*tuple((col if z >= 0 else back_col)[:3]), 255)
            else:
                f = 1.0 if z >= 0 else back_dim + (1 - back_dim) * (1 + z)
                w = strand_w * S * (0.8 + 0.2 * (z + 1) / 2)
                fill = _dim(col, f) if f < 1 else (*tuple(col[:3]), 255)
            _cap_line(d, p0, p1, w, fill)
        else:
            a, b, k = pl
            col = (*tuple(rung_cols[k % len(rung_cols)][:3]), 255)
            (ax, ay), (bx, by) = a, b
            if rung_shrink:
                mx, my = (ax + bx) / 2, (ay + by) / 2
                ax, ay = mx + (ax - mx) * (1 - rung_shrink), my + (ay - my) * (1 - rung_shrink)
                bx, by = mx + (bx - mx) * (1 - rung_shrink), my + (by - my) * (1 - rung_shrink)
            if math.hypot(bx - ax, by - ay) < 1:
                continue
            if dots:
                n = max(2, round(math.hypot(bx - ax, by - ay) / (rung_w * S * 1.45)))
                r = rung_w * S / 2
                for j in range(n + 1):
                    x = ax + (bx - ax) * j / n
                    y = ay + (by - ay) * j / n
                    d.ellipse([x - r, y - r, x + r, y + r], fill=col)
            else:
                line = _cap_line if round_rungs else _butt_line
                line(d, (ax, ay), (bx, by), rung_w * S, col)
                if core:  # a hot centre line, like the lit particle rungs in the app
                    hot = (*tuple(int(v + (255 - v) * 0.55) for v in col[:3]), 255)
                    line(d, (ax, ay), (bx, by), rung_w * S * 0.34, hot)
            if glow:
                line = _cap_line if round_rungs else _butt_line
                line(gd, (ax, ay), (bx, by), rung_w * S * 1.7, (*col[:3], 110))

    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    if tile is not None:
        ImageDraw.Draw(out).rounded_rectangle(
            [0, 0, S - 1, S - 1],
            radius=int(S * tile_radius),
            fill=(*tuple(tile), 255),
            outline=((*tuple(rim), 255)) if rim else None,
            width=int(S * 0.014) if rim else 0,
        )
    if glow:
        g = glow_layer.filter(ImageFilter.GaussianBlur(S * 0.025))
        if tile is not None:  # keep the glow inside the tile
            m = Image.new("L", (S, S), 0)
            ImageDraw.Draw(m).rounded_rectangle(
                [0, 0, S - 1, S - 1], radius=int(S * tile_radius), fill=255
            )
            g.putalpha(Image.composite(g.getchannel("A"), Image.new("L", (S, S), 0), m))
        out.alpha_composite(g)
    out.alpha_composite(img)
    img = out
    return img.resize((size, size), Image.LANCZOS)


def trim_square(img: Image.Image, size: int, pad: float = 0.0) -> Image.Image:
    """Crop to artwork bbox, centre on a square, rescale to `size`."""
    bbox = img.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    crop = img.crop(bbox)
    side = max(crop.size)
    side = int(side * (1 + 2 * pad))
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.alpha_composite(crop, ((side - crop.width) // 2, (side - crop.height) // 2))
    return sq.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- candidates
def cand_waveform(size):
    """A: horizontal helix; vertical rungs read as an audio waveform."""
    return helix(
        size,
        horizontal=True,
        twists=1.5,
        strand_w=0.075,
        rung_w=0.085,
        rungs=6,
        strand_cols=[DEEP[0], DEEP[1]],
        rung_cols=[BASES[2], BASES[3], BASES[0], BASES[1]],
        amp=0.30,
        length=0.84,
        rung_shrink=0.0,
    )


def cand_particles(size):
    """B: vertical helix with dotted particle rungs, like the live molecule."""
    return helix(
        size,
        horizontal=False,
        twists=1.25,
        strand_w=0.06,
        rung_w=0.07,
        rungs=5,
        strand_cols=[DEEP[0], DEEP[1]],
        rung_cols=[BASES[1], BASES[2], BASES[3], BASES[0]],
        amp=0.30,
        length=0.86,
        dots=True,
    )


def cand_tile(size):
    """C: the app's dark card as a rounded tile, glowing helix inside."""
    return helix(
        size,
        horizontal=False,
        twists=1.5,
        strand_w=0.055,
        rung_w=0.07,
        rungs=6,
        strand_cols=[BASES[0], BASES[1]],
        rung_cols=[BASES[2], BASES[3], BASES[0], BASES[1]],
        amp=0.25,
        length=0.70,
        tile=TILE,
        glow=True,
        back_dim=0.45,
    )


def cand_tile_dust(size):
    """C2: tile, neutral DUST backbone, rung lengths vary like a waveform."""
    return helix(
        size,
        horizontal=False,
        twists=1.25,
        strand_w=0.064,
        rung_w=0.052,
        rungs=8,
        strand_cols=[DUST, DUST],
        rung_cols=[BASES[1], BASES[2], BASES[3], BASES[0]],
        amp=0.27,
        length=0.76,
        tile=TILE,
        glow=True,
        phase0=0.0,
        rim=RIM,
        core=True,
        back_col=DUST_BACK,
        round_rungs=False,
    )


def cand_wave2(size):
    """A2: transparent horizontal helix, many rungs so their lengths form a waveform."""
    return helix(
        size,
        horizontal=True,
        twists=1.25,
        strand_w=0.07,
        rung_w=0.075,
        rungs=8,
        strand_cols=[DEEP[0], DEEP[1]],
        rung_cols=[BASES[2], BASES[3], BASES[0], BASES[1]],
        amp=0.36,
        length=0.90,
        phase0=0.0,
    )


FINAL = cand_tile_dust


def optimise(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    data = buf.getvalue()
    try:
        import oxipng

        data = oxipng.optimize_from_memory(data, level=6, strip=oxipng.StripChunks.safe())
    except Exception:
        pass
    return data


def render_final(size: int) -> Image.Image:
    art = FINAL(size * 2)
    return trim_square(art, size, pad=0.02)


def sheet(out: Path, cands) -> None:
    from PIL import ImageFont

    bgs = [(255, 255, 255), (28, 28, 28)]
    sizes = [256, 64, 32, 16]
    row_h = 280
    W = 20 + (256 + 64 + 32 + 16 + 4 * 30) * 2 + 20
    H = 20 + row_h * len(cands) + 20
    sh = Image.new("RGB", (W, H), (128, 128, 128))
    dr = ImageDraw.Draw(sh)
    font = ImageFont.load_default()
    for r, (name, fn) in enumerate(cands):
        art = trim_square(fn(1024), 512, pad=0.02)
        y = 20 + r * row_h
        x = 20
        for bg in bgs:
            dr.rectangle([x - 10, y - 10, x + (256 + 64 + 32 + 16 + 4 * 30) - 20, y + 266], fill=bg)
            for s in sizes:
                im = art.resize((s, s), Image.LANCZOS)
                sh.paste(im, (x, y + (256 - s) // 2 if s != 256 else y), im)
                x += s + 30
        dr.text((22, y + 258), name, fill=(0, 0, 0), font=font)
    sh.save(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", type=Path)
    ap.add_argument("--candidates", type=Path)
    args = ap.parse_args()
    if args.candidates:
        sheet(
            args.candidates,
            [
                ("A waveform", cand_waveform),
                ("B particles", cand_particles),
                ("C tile", cand_tile),
                ("C2 tile dust", cand_tile_dust),
                ("A2 wave", cand_wave2),
            ],
        )
        return
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    for name, s in (("icon.png", 256), ("icon@2x.png", 512)):
        data = optimise(render_final(s))
        (BRAND_DIR / name).write_bytes(data)
        print(name, s, len(data))
    print(
        "colours:",
        {h: hexc(c) for h, c in zip(BASE_HUES, BASES, strict=False)},
        "deep:",
        [hexc(c) for c in DEEP],
    )
    if args.preview:
        final_preview(args.preview)


def final_preview(out: Path) -> None:
    """Final icon on light and dark at 256/64/32/16 (+16 px blown up 4x), rejects below."""
    from PIL import ImageFont

    font = ImageFont.load_default()
    icon2x = Image.open(BRAND_DIR / "icon@2x.png").convert("RGBA")
    icon = Image.open(BRAND_DIR / "icon.png").convert("RGBA")
    bgs = [((255, 255, 255), (0, 0, 0)), ((28, 28, 28), (220, 220, 220))]
    W, rowh = 2 * 620, 300
    sh = Image.new("RGB", (W, rowh + 170), (128, 128, 128))
    dr = ImageDraw.Draw(sh)
    for i, (bg, fg) in enumerate(bgs):
        x0 = i * 620
        dr.rectangle([x0, 0, x0 + 619, rowh - 1], fill=bg)
        x = x0 + 16
        y = 16
        for sz in (256, 64, 32, 16):
            im = icon if sz == 256 else icon2x.resize((sz, sz), Image.LANCZOS)
            sh.paste(im, (x, y + (256 - sz) // 2), im)
            dr.text((x, y + 262), f"{sz}", fill=fg, font=font)
            x += sz + 24
        # 16 px rendering, magnified so its pixels can be judged
        small = icon2x.resize((16, 16), Image.LANCZOS)
        tile = Image.new("RGBA", (16, 16), (*bg, 255))
        tile.alpha_composite(small)
        big = tile.resize((96, 96), Image.NEAREST)
        sh.paste(big, (x, y + 80))
        dr.text((x, y + 182), "16 @ 6x", fill=fg, font=font)
    # rejected candidates, small
    y = rowh + 10
    dr.text(
        (16, y),
        "rejected: A2 horizontal waveform helix, B particle-dot helix",
        fill=(0, 0, 0),
        font=font,
    )
    x = 16
    for fn in (cand_wave2, cand_particles):
        art = trim_square(fn(512), 256, pad=0.02)
        for bg, _ in bgs:
            dr.rectangle([x - 6, y + 18, x + 64 + 32 + 16 + 30, y + 150], fill=bg)
            xx = x
            for sz in (64, 32, 16):
                im = art.resize((sz, sz), Image.LANCZOS)
                sh.paste(im, (xx, y + 40 + (64 - sz) // 2), im)
                xx += sz + 12
            x += 64 + 32 + 16 + 50
    sh.save(out)


if __name__ == "__main__":
    main()
