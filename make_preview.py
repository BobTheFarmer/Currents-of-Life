#!/usr/bin/env python3
"""
Quick preview: what the compute-shader ocean will look like.
Uses LIC (Line Integral Convolution) with smooth colormapping.
"""
import numpy as np
from PIL import Image, ImageFilter, ImageDraw
import os, sys

W, H = 960, 480   # preview resolution

# ── Build synthetic current field (same as OceanBackground.cs fallback) ──────

def build_currents():
    fx = np.linspace(0, 1, W, dtype=np.float32)
    fy = np.linspace(0, 1, H, dtype=np.float32)
    fxg, fyg = np.meshgrid(fx, fy)

    # Subtropical gyre (clockwise) centred at (0.6, 0.35)
    dx = fxg - 0.60; dy = fyg - 0.35
    r  = np.sqrt(dx*dx + dy*dy) + 0.01
    gs = np.exp(-(r*r) / 0.12)
    gu = gs * dy / r
    gv = -gs * dx / r

    # Subpolar gyre (counter-clockwise) centred at (0.55, 0.78)
    dx2 = fxg - 0.55; dy2 = fyg - 0.78
    r2  = np.sqrt(dx2*dx2 + dy2*dy2) + 0.01
    gs2 = 0.5 * np.exp(-(r2*r2) / 0.06)
    gu2 = -gs2 * dy2 / r2
    gv2 = gs2 * dx2 / r2

    # Kuroshio (northward along left boundary)
    kd   = np.abs(fxg - 0.15)
    kb   = np.exp(-(kd*kd) / 0.003)
    kv   = kb * np.clip(1.0 - np.abs(fyg - 0.60)*2, 0, 1) * 1.2

    # Kuroshio extension jet
    jlat = 0.56 + 0.06 * np.sin(fxg * 12.0)
    jb   = np.exp(-((fyg - jlat)*10)**2) * np.clip((fxg - 0.12)*5, 0, 1)
    ju   = jb
    jv   = 0.25 * np.cos(fxg * 12.0) * jb

    u = gu + gu2 + ju * 0.9
    v = gv + gv2 + kv + jv
    return u.astype(np.float32), v.astype(np.float32)


def build_chlorophyll():
    fx = np.linspace(0, 1, W, dtype=np.float32)
    fy = np.linspace(0, 1, H, dtype=np.float32)
    fxg, fyg = np.meshgrid(fx, fy)

    # Boundary current band (left side)
    kuro = np.exp(-((fxg - 0.18)*6)**2)
    # Subarctic front (top 30%)
    arc  = np.exp(-((fyg - 0.82)*5)**2)
    # Extension jet (diagonal streak)
    ext_lat = 0.55 + 0.1 * np.sin(fxg * 8)
    jet  = np.exp(-((fyg - ext_lat)*14)**2) * np.clip((fxg - 0.15)*3, 0, 1)

    chl = np.clip(kuro*0.8 + arc*0.5 + jet*0.9, 0, 1)
    return chl.astype(np.float32)


# ── LIC: trace streamlines, average seed along them ──────────────────────────

def lic(u, v, seed, steps=40, step_size=0.8):
    """Line Integral Convolution — creates current-aligned filament streaks."""
    h, w = seed.shape
    result = np.zeros_like(seed)
    count  = np.zeros_like(seed)

    # Normalise velocity
    mag = np.sqrt(u*u + v*v)
    mag_max = np.percentile(mag, 99) + 1e-6
    un = u / mag_max
    vn = v / mag_max

    px = np.arange(w, dtype=np.float32)
    py = np.arange(h, dtype=np.float32)
    pxg, pyg = np.meshgrid(px, py)

    cx = pxg.copy()
    cy = pyg.copy()

    for step in range(steps):
        # Bilinear sample velocity
        xi = np.clip(cx, 0, w-1).astype(np.int32)
        yi = np.clip(cy, 0, h-1).astype(np.int32)
        xi1 = np.minimum(xi+1, w-1)
        yi1 = np.minimum(yi+1, h-1)
        tx = cx - xi; ty = cy - yi
        su = (un[yi, xi]*(1-tx)*(1-ty) + un[yi, xi1]*tx*(1-ty) +
              un[yi1,xi]*(1-tx)*ty    + un[yi1,xi1]*tx*ty)
        sv = (vn[yi, xi]*(1-tx)*(1-ty) + vn[yi, xi1]*tx*(1-ty) +
              vn[yi1,xi]*(1-tx)*ty    + vn[yi1,xi1]*tx*ty)

        # Advance position
        cx = np.clip(cx + su * step_size, 0, w-1)
        cy = np.clip(cy + sv * step_size, 0, h-1)

        # Sample seed at new position
        xi = cx.astype(np.int32)
        yi = cy.astype(np.int32)
        result += seed[np.minimum(yi, h-1), np.minimum(xi, w-1)]
        count  += 1

    return result / (count + 1e-6)


# ── Colormap: deep navy → teal → bright cyan ─────────────────────────────────

def colormap(t):
    """Map [0,1] → ocean colour (numpy array, shape (N,3), float32 [0,1])."""
    t = np.clip(t, 0, 1)
    # control points: (t, R, G, B)
    pts = np.array([
        [0.00, 0.04, 0.10, 0.22],   # deep navy
        [0.20, 0.05, 0.18, 0.38],   # dark teal-blue
        [0.45, 0.06, 0.38, 0.55],   # mid teal
        [0.70, 0.10, 0.65, 0.72],   # bright teal
        [0.88, 0.35, 0.88, 0.90],   # light cyan
        [1.00, 0.80, 0.97, 1.00],   # near-white
    ], dtype=np.float32)

    r = np.interp(t, pts[:,0], pts[:,1])
    g = np.interp(t, pts[:,0], pts[:,2])
    b = np.interp(t, pts[:,0], pts[:,3])
    return r, g, b


# ── Boat sprite ───────────────────────────────────────────────────────────────

def draw_boat(draw, cx, cy, scale=3):
    hull   = (217, 204, 165)
    deck   = (127,  89,  51)
    cabin  = (234, 224, 199)
    dark   = ( 45,  35,  25)
    shadow = ( 76,  61,  40)

    rows = [
        (7,8),(7,8),(6,9),(6,9),
        (5,10),(5,10),(5,10),(4,11),
        (4,11),(4,11),(4,11),(4,11),
        (4,11),(4,11),(4,11),(4,11),
        (5,10),(5,10),(5,10),(5,10),
        (5,10),(6,9),(6,9),(7,8),
        (7,8),(7,8),(7,7),(7,7),
    ]
    h = len(rows)
    for row_y, (xl, xr) in enumerate(rows):
        for x in range(xl, xr+1):
            is_edge  = (x == xl or x == xr)
            is_cabin = (10 <= row_y <= 18 and 5 <= x <= 10)
            is_deck  = (4  <= row_y <= 22)
            if is_edge:   c = dark
            elif is_cabin:
                c = shadow if (x==5 or x==10 or row_y==10 or row_y==18) else cabin
            elif is_deck: c = deck
            else:         c = hull

            px = cx + (x - 7) * scale
            py = cy + (h - 1 - row_y - 5) * scale
            draw.rectangle([px, py, px+scale-1, py+scale-1], fill=c)


# ── Main ──────────────────────────────────────────────────────────────────────

print("Building current field…")
u, v = build_currents()

print("Building chlorophyll…")
chl = build_chlorophyll()

print("Running LIC (40 steps)…")
lic_val = lic(u, v, chl, steps=40, step_size=1.2)

# Smooth slightly
from PIL import ImageFilter
lic_img = Image.fromarray((lic_val * 255).clip(0,255).astype(np.uint8))
lic_img = lic_img.filter(ImageFilter.GaussianBlur(radius=1.0))
lic_smooth = np.array(lic_img).astype(np.float32) / 255.0

# Apply soft contrast boost (no hard threshold)
contrast = 2.8
display = np.clip((lic_smooth - 0.05) * contrast, 0, 1)
# Gamma
display = display ** 0.7

print(f"  display  min={display.min():.3f}  mean={display.mean():.3f}  max={display.max():.3f}")

# Colormap
r, g, b = colormap(display)

# Vignette
fx = np.linspace(-1, 1, W, dtype=np.float32)
fy = np.linspace(-1, 1, H, dtype=np.float32)
fxg, fyg = np.meshgrid(fx, fy)
vignette = np.clip(1.0 - (fxg**2 + fyg**2) * 0.35, 0.5, 1.0)
r *= vignette; g *= vignette; b *= vignette

rgb = np.stack([
    (r * 255).clip(0,255).astype(np.uint8),
    (g * 255).clip(0,255).astype(np.uint8),
    (b * 255).clip(0,255).astype(np.uint8),
], axis=2)

img = Image.fromarray(rgb, mode="RGB")

# Draw boat
draw = ImageDraw.Draw(img)
draw_boat(draw, W//2, H//2, scale=3)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview_ocean.png")
img.save(out)
print(f"Saved {out}")
