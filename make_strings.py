#!/usr/bin/env python3
"""
Generates strings_3_balanced.png and strings_4_tight.png with:
- Reduced blown-out highlights (log-compressed chlorophyll, no spike eddies)
- Real land mask extracted from NASA cache
- Japan / Korean peninsula shown in correct earthy colors
"""
import numpy as np
from PIL import Image, ImageFilter, ImageDraw
import os
from scipy.ndimage import gaussian_filter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Region config (must match preprocess_ocean_data.py) ──────────────────────
LON_MIN, LON_MAX = 130.0, 215.0
LAT_MIN, LAT_MAX =  10.0,  60.0
W, H = 960, 480   # preview size

# ── Build improved chlorophyll (no star eddies, log-compressed) ───────────────
print("Building improved chlorophyll…")

lons = np.linspace(LON_MIN, LON_MAX, W, dtype=np.float32)
lats = np.linspace(LAT_MAX, LAT_MIN, H, dtype=np.float32)
lon_g, lat_g = np.meshgrid(lons, lats)

chl = np.zeros((H, W), dtype=np.float32)

# Subarctic front (45-58°N) — broad but not overwhelming
chl += 0.55 * np.exp(-((lat_g - 52.0)**2) / 40.0)

# Kuroshio — smooth Gaussian streak, not a star
kuro_lon = 143.0 + 8.0*np.sin((lat_g - 20.0)*0.12)
chl += 0.70 * np.exp(-((lon_g - kuro_lon)**2 + ((lat_g - 36.0)*2.2)**2) / 70.0)

# Kuroshio Extension filament (eastward jet with meanders)
ext_lat = 35.0 + 3.5*np.sin((lon_g - 145.0)*0.10)
in_ext = (lon_g > 145.0) & (lon_g < 210.0)
chl += 0.55 * np.exp(-((lat_g - ext_lat)**2)/7.0) * in_ext

# Oyashio cold current (east side, 40-55°N near coast)
east = lon_g > 195.0
chl += 0.40 * np.exp(-((lat_g - 47.0)**2)/80.0) * east

# Mesoscale eddies — smooth Gaussians only, NO spiral arms
for elon, elat, es, er in [(152,42,0.30,8),(165,36,0.25,6),(180,33,0.22,7),(192,40,0.28,6),(170,48,0.20,5)]:
    chl += es * np.exp(-((lon_g-elon)**2+(lat_g-elat)**2)/(2*er**2))

# Suppress subtropical gyre interior with smooth sigmoid (no hard rectangle)
gyre_cx, gyre_cy = (155+205)/2, (15+32)/2
gyre_mask_soft = (np.tanh((lon_g - 155.0)*0.4) * np.tanh((205.0 - lon_g)*0.4) *
                  np.tanh((lat_g - 15.0)*0.5) * np.tanh((32.0 - lat_g)*0.5))
gyre_mask_soft = np.clip(gyre_mask_soft, 0, 1)
chl *= (1.0 - gyre_mask_soft * 0.85)

# Anisotropic noise (E-W elongated like real filaments)
np.random.seed(42)
noise = gaussian_filter(np.random.rand(H, W).astype(np.float32), sigma=[1.2, 5.0])
chl += noise * 0.08

# Log-compress to reduce blown-out peaks (most important fix)
chl = np.clip(chl, 0, None)
chl = np.log1p(chl * 4.0) / np.log1p(4.0)   # soft ceiling

# Unsharp mask for filament sharpening
blurred = gaussian_filter(chl, sigma=2.0)
chl = np.clip(chl + 0.5*(chl - blurred), 0, 1)
chl /= chl.max() + 1e-6

print(f"  min={chl.min():.3f}  mean={chl.mean():.3f}  max={chl.max():.3f}")

# ── Extract land mask from NASA cache ────────────────────────────────────────
print("Extracting land mask from NASA cache…")
cache_path = os.path.join(SCRIPT_DIR, "chla_neo_cache.png")
cache_img  = Image.open(cache_path).convert("RGB")
CW, CH = cache_img.size   # 3600x1800

def lon_to_px(lon, W_img):
    lon_norm = ((lon + 180.0) % 360.0) - 180.0
    return int((lon_norm + 180.0) / 360.0 * W_img)

def lat_to_py(lat, H_img):
    return int((90.0 - lat) / 180.0 * H_img)

x0 = lon_to_px(LON_MIN, CW)   # 130°E → ~3100
x1 = lon_to_px(LON_MAX, CW)   # 215°E = 145°W → ~350  (wraps)
y0 = lat_to_py(LAT_MAX, CH)   # 60°N
y1 = lat_to_py(LAT_MIN, CH)   # 10°N

if x1 > x0:
    region = cache_img.crop((x0, y0, x1, y1))
else:
    left  = cache_img.crop((x0, y0, CW, y1))
    right = cache_img.crop((0,  y0, x1, y1))
    region = Image.new("RGB", (left.width + right.width, left.height))
    region.paste(left, (0, 0)); region.paste(right, (left.width, 0))

region_r = region.resize((W, H), Image.LANCZOS)
carr = np.array(region_r).astype(np.float32) / 255.0
cr, cg, cb = carr[:,:,0], carr[:,:,1], carr[:,:,2]

# Land: noticeably warmer (redder) than blue channel
land_mask = (cr > cb + 0.06).astype(np.float32)
# Smooth mask slightly to avoid aliasing
land_mask = gaussian_filter(land_mask, sigma=0.8)
land_mask = (land_mask > 0.4).astype(np.float32)

print(f"  Land coverage: {100*land_mask.mean():.1f}%")

# ── Current field ─────────────────────────────────────────────────────────────
fx=np.linspace(0,1,W,dtype=np.float32); fy=np.linspace(0,1,H,dtype=np.float32)
fxg,fyg=np.meshgrid(fx,fy)

dx=fxg-0.60; dy=fyg-0.35; r=np.sqrt(dx*dx+dy*dy)+0.01
gs=np.exp(-(r*r)/0.12); gu=gs*dy/r; gv=-gs*dx/r

dx2=fxg-0.55; dy2=fyg-0.78; r2=np.sqrt(dx2*dx2+dy2*dy2)+0.01
gs2=0.5*np.exp(-(r2*r2)/0.06); gu2=-gs2*dy2/r2; gv2=gs2*dx2/r2

kd=np.abs(fxg-0.15); kb=np.exp(-(kd*kd)/0.003)
kv=kb*np.clip(1.0-np.abs(fyg-0.60)*2,0,1)*1.2

jlat=0.56+0.06*np.sin(fxg*12); jb=np.exp(-((fyg-jlat)*10)**2)*np.clip((fxg-0.12)*5,0,1)
ju=jb; jv=0.25*np.cos(fxg*12)*jb

eu=np.zeros_like(fxg); ev=np.zeros_like(fxg)
for ex,ey,es,er,esign in [(0.30,0.45,0.45,0.07,+1),(0.65,0.38,0.38,0.055,-1),(0.78,0.60,0.30,0.05,+1),(0.42,0.70,0.35,0.06,-1)]:
    ddx=fxg-ex; ddy=fyg-ey; rr=np.sqrt(ddx*ddx+ddy*ddy)+0.01
    em=es*np.exp(-(rr**2)/(2*er**2)); eu+=esign*em*ddy/rr; ev+=esign*-em*ddx/rr

u=(gu+gu2+ju*0.9+eu).astype(np.float32); v=(gv+gv2+kv+jv+ev).astype(np.float32)
mag=np.sqrt(u*u+v*v); mag_max=np.percentile(mag,99)+1e-6
un=u/mag_max; vn=v/mag_max

# ── LIC ───────────────────────────────────────────────────────────────────────
def lic_pass(seed, steps, step_size, direction=1):
    h,w=seed.shape
    cx=np.tile(np.arange(w,dtype=np.float32),(h,1))
    cy=np.tile(np.arange(h,dtype=np.float32),(w,1)).T
    acc=np.zeros((h,w),dtype=np.float32)
    for _ in range(steps):
        xi=np.clip(cx,0,w-1).astype(np.int32); yi=np.clip(cy,0,h-1).astype(np.int32)
        xi1=np.minimum(xi+1,w-1); yi1=np.minimum(yi+1,h-1)
        tx=cx-xi; ty=cy-yi
        su=(un[yi,xi]*(1-tx)*(1-ty)+un[yi,xi1]*tx*(1-ty)+un[yi1,xi]*(1-tx)*ty+un[yi1,xi1]*tx*ty)
        sv=(vn[yi,xi]*(1-tx)*(1-ty)+vn[yi,xi1]*tx*(1-ty)+vn[yi1,xi]*(1-tx)*ty+vn[yi1,xi1]*tx*ty)
        cx=np.clip(cx+direction*su*step_size,0,w-1); cy=np.clip(cy+direction*sv*step_size,0,h-1)
        acc+=seed[np.minimum(cy.astype(np.int32),h-1),np.minimum(cx.astype(np.int32),w-1)]
    return acc/steps

def lic_bidir(steps, step_size):
    return (lic_pass(chl,steps,step_size,1) + lic_pass(chl,steps,step_size,-1)) / 2

# ── Colormap ──────────────────────────────────────────────────────────────────
def colormap_ocean(t):
    pts=np.array([[0.00,0.008,0.022,0.055],[0.18,0.010,0.065,0.160],
                  [0.42,0.020,0.210,0.320],[0.65,0.050,0.520,0.620],
                  [0.85,0.200,0.820,0.880],[1.00,0.700,0.970,1.000]])
    return np.interp(t,pts[:,0],pts[:,1]), np.interp(t,pts[:,0],pts[:,2]), np.interp(t,pts[:,0],pts[:,3])

# Land colors: earthy green-gray (like a real map)
LAND_COLOR  = np.array([0.28, 0.30, 0.22], dtype=np.float32)  # dark olive
COAST_COLOR = np.array([0.22, 0.24, 0.18], dtype=np.float32)  # darker coast edge

def vignette():
    fxl=np.linspace(-1,1,W,dtype=np.float32); fyl=np.linspace(-1,1,H,dtype=np.float32)
    fxg2,fyg2=np.meshgrid(fxl,fyl)
    return np.clip(1.0-(fxg2**2+fyg2**2)*0.30, 0.4, 1.0)

vig = vignette()

def draw_boat(draw, cx, cy, s=3):
    hull=(217,204,165); deck=(127,89,51); cabin=(234,224,199); dark=(45,35,25); shadow=(76,61,40)
    rows=[(7,8),(7,8),(6,9),(6,9),(5,10),(5,10),(5,10),(4,11),(4,11),(4,11),(4,11),(4,11),
          (4,11),(4,11),(4,11),(4,11),(5,10),(5,10),(5,10),(5,10),(5,10),(6,9),(6,9),(7,8),
          (7,8),(7,8),(7,7),(7,7)]
    for ry,(xl,xr) in enumerate(rows):
        for x in range(xl,xr+1):
            ie=(x==xl or x==xr); ic=(10<=ry<=18 and 5<=x<=10); id_=(4<=ry<=22)
            c=dark if ie else (shadow if ic and (x in (5,10) or ry in (10,18)) else cabin if ic else deck if id_ else hull)
            px=cx+(x-7)*s; py=cy+(len(rows)-1-ry-5)*s
            draw.rectangle([px,py,px+s-1,py+s-1],fill=c)

def make_image(raw, contrast, threshold, blur_post, label):
    d = np.clip((raw - threshold) * contrast, 0, 1) ** 0.65
    if blur_post > 0:
        d = np.array(Image.fromarray((d*255).clip(0,255).astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(blur_post))).astype(np.float32)/255.0
    d *= vig

    r,g,b = colormap_ocean(d)

    # Apply land mask
    lm = land_mask
    coast_edge = gaussian_filter(lm, sigma=1.2) - lm*0.999  # thin edge halo
    coast_edge = np.clip(coast_edge * 6, 0, 1)

    r = r*(1-lm) + LAND_COLOR[0]*lm + COAST_COLOR[0]*coast_edge
    g = g*(1-lm) + LAND_COLOR[1]*lm + COAST_COLOR[1]*coast_edge
    b = b*(1-lm) + LAND_COLOR[2]*lm + COAST_COLOR[2]*coast_edge

    rgb = np.stack([(np.clip(r,0,1)*255).astype(np.uint8),
                    (np.clip(g,0,1)*255).astype(np.uint8),
                    (np.clip(b,0,1)*255).astype(np.uint8)], axis=2)
    img = Image.fromarray(rgb, "RGB")
    draw = ImageDraw.Draw(img)
    draw_boat(draw, W//2, H//2, s=3)
    return img

# ── Render 4 options ──────────────────────────────────────────────────────────
configs = [
    (18,  2.0, 0.03, 1.2, "strings_2_medium.png"),
    (40,  2.8, 0.04, 0.6, "strings_3_balanced.png"),
    (80,  3.8, 0.05, 0.3, "strings_4_tight.png"),
    (120, 5.0, 0.07, 0.0, "strings_5_sharp.png"),
]

for steps, contrast, threshold, blur, fname in configs:
    print(f"LIC steps={steps}…")
    raw = lic_bidir(steps, step_size=max(0.5, 1.5 - steps*0.008))
    img = make_image(raw, contrast, threshold, blur, fname)
    img.save(os.path.join(SCRIPT_DIR, fname))
    print(f"  Saved {fname}")

print("\nDone.")
