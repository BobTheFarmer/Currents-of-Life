#!/usr/bin/env python3
"""
preprocess_ocean_data.py
========================
Ingests NASA ocean data and exports two textures Unity loads at runtime:

  chlorophyll.png  — grayscale seed field (log-scaled chlorophyll-a concentration)
  currents_uv.png  — RG-encoded u/v surface current vectors (0.5 = zero flow)
  ocean_config.json — region metadata

Data sources:
  Chlorophyll: NASA NEO / MODIS Aqua  (https://neo.gsfc.nasa.gov/)
  Currents:    Analytically modelled North-Pacific gyres + Kuroshio
               (OSCAR NetCDF requires auth; synthetic field used instead,
                tuned to match published OSCAR patterns for this region)

Run from the project root:
    python3 preprocess_ocean_data.py

Requires:  pip install numpy Pillow requests
Optional:  pip install scipy        (for filament-preserving sharpening)
"""

import os, json, math, struct, time
import numpy as np

try:
    from PIL import Image
except ImportError:
    raise SystemExit("Install Pillow:  pip install Pillow")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request

try:
    from scipy.ndimage import gaussian_filter, sobel
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

# ── Config ────────────────────────────────────────────────────────────────────

GRID_W, GRID_H = 512, 256

# North Pacific: Kuroshio + gyre system (lat/lon)
LAT_MIN, LAT_MAX =  10.0,  60.0
LON_MIN, LON_MAX = 130.0, 215.0   # 215 = -145°W (wraps dateline)

# Output goes directly into Unity StreamingAssets
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
OUT_DIR     = os.path.join(SCRIPT_DIR, "Assets", "StreamingAssets", "OceanData")

CACHE_FILE  = os.path.join(SCRIPT_DIR, "chla_neo_cache.png")

# NASA NEO monthly global chlorophyll PNG (public, no auth)
# Resolution: 3600 × 1800  (0.1° / pixel equirectangular)
NEO_URL = (
    "https://neo.gsfc.nasa.gov/servlet/RenderData"
    "?si=875430&cs=rgb&format=PNG&width=3600&height=1800"
)

# ── Download helper ───────────────────────────────────────────────────────────

def download_file(url, dest, timeout=60):
    headers = {"User-Agent": "OceanDataPreprocessor/1.0 (Unity game research project)"}
    if HAS_REQUESTS:
        r = requests.get(url, headers=headers, timeout=timeout, stream=True)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(65536):
                f.write(chunk)
    else:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as f:
            f.write(resp.read())

# ── Chlorophyll processing ────────────────────────────────────────────────────

def load_or_download_chla():
    if os.path.exists(CACHE_FILE):
        print(f"  Using cached {os.path.basename(CACHE_FILE)}")
        return Image.open(CACHE_FILE).convert("RGB")

    print(f"  Downloading from NASA NEO (this takes ~30s)…")
    try:
        download_file(NEO_URL, CACHE_FILE)
        return Image.open(CACHE_FILE).convert("RGB")
    except Exception as e:
        print(f"  WARNING: Download failed ({e})")
        return None


def extract_region(img, lat_min, lat_max, lon_min, lon_max, w, h):
    """Crop an equirectangular global image to a lat/lon box.

    NASA NEO images use -180..+180 longitude (not 0..360).
    Pixel 0 = 180°W, pixel W = 180°E.
    """
    W, H = img.size

    def lon_to_px(lon):
        # Normalise to -180..+180, then to pixel
        lon_norm = ((lon + 180.0) % 360.0) - 180.0
        return int((lon_norm + 180.0) / 360.0 * W)

    y0 = int((90.0 - lat_max) / 180.0 * H)
    y1 = int((90.0 - lat_min) / 180.0 * H)

    x0 = lon_to_px(lon_min)   # 130°E → pixel ~3100
    x1 = lon_to_px(lon_max)   # 215°E = 145°W → pixel ~350  (wraps dateline)

    if x1 > x0:
        region = img.crop((x0, y0, x1, y1))
    else:
        # Wraps the dateline: take [x0..W] ++ [0..x1]
        left  = img.crop((x0, y0, W,  y1))
        right = img.crop((0,  y0, x1, y1))
        region = Image.new("RGB", (left.width + right.width, left.height))
        region.paste(left,  (0, 0))
        region.paste(right, (left.width, 0))
        print(f"  (wraps dateline: left={left.width}px + right={right.width}px)")

    return region.resize((w, h), Image.LANCZOS)


def chla_from_nasa_colormap(rgb_region):
    """
    NASA NEO uses a blue→green→yellow→red colormap for chlorophyll.
    Invert this to a scalar concentration value.
    """
    arr = np.array(rgb_region).astype(np.float32) / 255.0
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    # Land = near-black; missing/deep ocean = dark navy
    land_mask    = (r < 0.08) & (g < 0.08) & (b < 0.08)
    missing_mask = (r < 0.07) & (g < 0.07) & (b < 0.15)

    # Warm colours (red, orange, yellow, green) → high chlorophyll
    # Cool colours (dark blue) → low chlorophyll
    warmth = np.clip(r * 0.55 + g * 0.35 - b * 0.25 + 0.25, 0, 1)
    warmth[land_mask | missing_mask] = 0.0

    # Log-compress (chlorophyll spans several orders of magnitude)
    chl = np.log1p(warmth * 12.0) / np.log1p(12.0)

    # Filament-preserving sharpening: unsharp mask
    if HAS_SCIPY:
        blurred   = gaussian_filter(chl, sigma=1.5)
        chl       = np.clip(chl + 0.6 * (chl - blurred), 0, 1)
        # Edge enhancement: keep fine structure
        edges     = np.hypot(sobel(chl, axis=0), sobel(chl, axis=1))
        edges     = np.clip(edges * 2.0, 0, 1)
        chl       = np.clip(chl + edges * 0.25, 0, 1)

    return chl.astype(np.float32)


def build_synthetic_chlorophyll():
    """
    Physically-motivated synthetic chlorophyll field for the North Pacific.
    Approximates: Kuroshio upwelling, gyres, subarctic front, ENSO-like patterns.
    """
    lons = np.linspace(LON_MIN, LON_MAX, GRID_W)
    lats = np.linspace(LAT_MAX, LAT_MIN, GRID_H)   # top = high lat
    lon_g, lat_g = np.meshgrid(lons, lats)

    chl = np.zeros((GRID_H, GRID_W), dtype=np.float32)

    # Subarctic/subpolar high-chl band (45-55°N)
    chl += 0.7 * np.exp(-((lat_g - 50.0) ** 2) / 40.0)

    # Kuroshio front (boundary current leaves coast ~35°N, 140-160°E)
    kuro_lon = 148.0 + 12.0 * np.sin((lat_g - 20.0) * 0.15)
    kuro_dist = (lon_g - kuro_lon) ** 2 + ((lat_g - 35.0) * 2) ** 2
    chl += 0.9 * np.exp(-kuro_dist / 80.0)

    # Kuroshio Extension filament (eastward jet 35°N, meanders)
    ext_lat = 35.0 + 4.0 * np.sin((lon_g - 145.0) * 0.12)
    ext_dist = (lat_g - ext_lat) ** 2
    ext_lon_mask = (lon_g > 145.0) & (lon_g < 210.0)
    chl += 0.6 * np.exp(-ext_dist / 6.0) * ext_lon_mask

    # Eastern boundary upwelling (California Current-like, ~130°E side)
    east_mask = lon_g > 195.0
    chl += 0.5 * np.exp(-((lat_g - 40.0) ** 2) / 120.0) * east_mask

    # Subtropical gyre interior (low nutrient → low chl) — suppress
    gyre_mask = ((lat_g > 18) & (lat_g < 33) &
                 (lon_g > 155) & (lon_g < 205))
    chl *= np.where(gyre_mask, 0.15, 1.0)

    # Add fine-scale filament noise (elongated in flow direction)
    np.random.seed(7)
    noise_h = np.random.rand(GRID_H, GRID_W).astype(np.float32)
    noise_h = np.roll(noise_h, 3, axis=1)   # stretch horizontally
    if HAS_SCIPY:
        noise_h = gaussian_filter(noise_h, sigma=[1.5, 4.0])
    chl += noise_h * 0.12

    # Normalize
    chl = np.clip(chl, 0, 1)
    chl = chl / (chl.max() + 1e-6)
    return chl


# ── Current field ─────────────────────────────────────────────────────────────

def build_current_field():
    """
    Analytically construct a surface current field for the North Pacific.
    Based on published OSCAR climatology patterns.
    Returns u, v in [-1, 1] (normalised).
    """
    lons = np.linspace(LON_MIN, LON_MAX, GRID_W)
    lats = np.linspace(LAT_MAX, LAT_MIN, GRID_H)
    lon_g, lat_g = np.meshgrid(lons, lats)

    u = np.zeros((GRID_H, GRID_W), dtype=np.float32)
    v = np.zeros((GRID_H, GRID_W), dtype=np.float32)

    # ── North Pacific Subtropical Gyre (clockwise) ───────────────────────────
    gcx, gcy = 175.0, 28.0
    dx, dy = lon_g - gcx, lat_g - gcy
    r = np.sqrt(dx ** 2 + dy ** 2)
    gyre_str = 0.7 * np.exp(-(r / 35.0) ** 2)
    u += gyre_str * dy / (r + 4.0)
    v -= gyre_str * dx / (r + 4.0)

    # ── Subpolar Gyre (counter-clockwise, ~50°N) ─────────────────────────────
    gcx2, gcy2 = 180.0, 52.0
    dx2, dy2 = lon_g - gcx2, lat_g - gcy2
    r2 = np.sqrt(dx2 ** 2 + dy2 ** 2)
    gyre2_str = 0.4 * np.exp(-(r2 / 20.0) ** 2)
    u -= gyre2_str * dy2 / (r2 + 4.0)
    v += gyre2_str * dx2 / (r2 + 4.0)

    # ── Kuroshio Current (northward along Japanese coast) ────────────────────
    kuro_lon = 141.0
    kuro_width = 4.0
    in_kuro = (lat_g > 18) & (lat_g < 43)
    kuro_lon_mask = np.exp(-((lon_g - kuro_lon) ** 2) / (2 * kuro_width ** 2))
    v += 1.2 * kuro_lon_mask * in_kuro

    # ── Kuroshio Extension (eastward jet, meanders) ──────────────────────────
    ext_lat    = 35.5 + 3.5 * np.sin((lon_g - 145.0) * 0.13)
    ext_width  = 2.5
    in_ext     = lon_g > 143.0
    ext_mask   = np.exp(-((lat_g - ext_lat) ** 2) / (2 * ext_width ** 2)) * in_ext
    u += 1.1 * ext_mask
    v += 0.3 * np.cos((lon_g - 145.0) * 0.13) * ext_mask  # meander crossflow

    # ── North Equatorial Current (westward, 8-20°N) ──────────────────────────
    neq_lat, neq_w = 14.0, 4.0
    neq_mask = np.exp(-((lat_g - neq_lat) ** 2) / (2 * neq_w ** 2))
    u -= 0.6 * neq_mask

    # ── Mesoscale eddies (adds realistic variability) ─────────────────────────
    eddies = [
        # lat,   lon,   strength, radius, sign(+1=anticyclone, -1=cyclone)
        (42.0, 152.0,   0.45,    7.0,   +1),
        (36.0, 163.0,   0.38,    6.0,   -1),
        (33.0, 178.0,   0.40,    7.0,   +1),
        (40.0, 190.0,   0.35,    6.0,   -1),
        (48.0, 168.0,   0.30,    5.5,   +1),
        (28.0, 158.0,   0.28,    5.0,   -1),
        (37.0, 148.0,   0.42,    6.5,   +1),
    ]
    for (elat, elon, estr, erad, esign) in eddies:
        dx = lon_g - elon
        dy = lat_g - elat
        r  = np.sqrt(dx ** 2 + dy ** 2)
        em = estr * np.exp(-(r ** 2) / (2 * erad ** 2))
        u += esign *  em * dy / (r + 2.0)
        v += esign * -em * dx / (r + 2.0)

    # Normalise to [-1, 1]
    mag    = np.sqrt(u ** 2 + v ** 2)
    scale  = np.percentile(mag, 98) + 1e-6
    u      = np.clip(u / scale, -1, 1)
    v      = np.clip(v / scale, -1, 1)

    return u, v


# ── Output helpers ─────────────────────────────────────────────────────────────

def save_grayscale(arr, path):
    img = Image.fromarray((arr * 255).clip(0, 255).astype(np.uint8), mode="L")
    img.save(path)
    print(f"  Saved  {os.path.relpath(path)}")


def save_rg_texture(u, v, path):
    """Encode u/v into RG channels. 0.5 = zero flow."""
    H, W = u.shape
    rgb  = np.zeros((H, W, 3), dtype=np.uint8)
    rgb[:, :, 0] = ((u + 1.0) * 0.5 * 255).clip(0, 255).astype(np.uint8)
    rgb[:, :, 1] = ((v + 1.0) * 0.5 * 255).clip(0, 255).astype(np.uint8)
    rgb[:, :, 2] = 128
    Image.fromarray(rgb, mode="RGB").save(path)
    print(f"  Saved  {os.path.relpath(path)}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("╔═══════════════════════════════════════╗")
    print("║  Ocean Data Preprocessor              ║")
    print("╚═══════════════════════════════════════╝")
    print()

    # ── 1. Chlorophyll ────────────────────────────────────────────────────────
    print("[1/3] Chlorophyll seed field")
    img_global = load_or_download_chla() if True else None

    if img_global is not None:
        print(f"  Extracting region ({LAT_MIN}–{LAT_MAX}°N, {LON_MIN}–{LON_MAX}°E)…")
        region = extract_region(img_global, LAT_MIN, LAT_MAX, LON_MIN, LON_MAX, GRID_W, GRID_H)
        chl    = chla_from_nasa_colormap(region)
        print(f"  Processed NASA MODIS chlorophyll  (scipy={HAS_SCIPY})")
    else:
        print("  Falling back to synthetic chlorophyll field")
        chl = build_synthetic_chlorophyll()

    save_grayscale(chl, os.path.join(OUT_DIR, "chlorophyll.png"))

    # ── 2. Currents ───────────────────────────────────────────────────────────
    print("\n[2/3] Current field (analytical OSCAR-matched model)")
    u, v = build_current_field()
    save_rg_texture(u, v, os.path.join(OUT_DIR, "currents_uv.png"))

    # ── 3. Config ─────────────────────────────────────────────────────────────
    print("\n[3/3] Writing config")
    config = {
        "lat_min": LAT_MIN, "lat_max": LAT_MAX,
        "lon_min": LON_MIN, "lon_max": LON_MAX,
        "grid_w":  GRID_W,  "grid_h":  GRID_H,
        "region":  "North Pacific — Kuroshio + subtropical gyre",
        "chl_source": "NASA NEO MODIS Aqua" if img_global else "synthetic",
        "cur_source": "analytical (OSCAR-matched)",
    }
    cfg_path = os.path.join(OUT_DIR, "ocean_config.json")
    with open(cfg_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  Saved  {os.path.relpath(cfg_path)}")

    print()
    print("Done! Hit Play in Unity — OceanBackground loads these files automatically.")
    print(f"Scipy available: {HAS_SCIPY} (install for sharper filaments)")


if __name__ == "__main__":
    main()
