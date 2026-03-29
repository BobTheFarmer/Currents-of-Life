#!/usr/bin/env python3
"""
Higher-fidelity ocean previews using:
- Standard LIC on white noise (creates actual thin flow-aligned streamlines)
- Rich current field with 20+ eddies and curl-noise turbulence
- Chlorophyll as brightness modulator, not the LIC seed
- Computed at 2x resolution and downsampled for anti-aliasing
"""
import numpy as np
from PIL import Image, ImageFilter, ImageDraw
import os
from scipy.ndimage import gaussian_filter, sobel

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
W, H = 960, 480      # output size
S = 2                # supersampling factor (compute at 2x)
WS, HS = W*S, H*S   # compute resolution: 1920x960

LON_MIN, LON_MAX = 130.0, 215.0
LAT_MAX, LAT_MIN =  60.0,  10.0

# ── Build rich current field at full resolution ───────────────────────────────
print("Building current field…")
fx = np.linspace(0, 1, WS, dtype=np.float32)
fy = np.linspace(0, 1, HS, dtype=np.float32)
fxg, fyg = np.meshgrid(fx, fy)

u = np.zeros((HS, WS), dtype=np.float32)
v = np.zeros((HS, WS), dtype=np.float32)

# Main gyres
def add_gyre(cx, cy, strength, radius, sign=1):
    dx=fxg-cx; dy=fyg-cy; r=np.sqrt(dx*dx+dy*dy)+0.001
    gs=strength*np.exp(-(r/radius)**2)
    global u, v
    u += sign*gs*dy/r
    v -= sign*gs*dx/r

add_gyre(0.62, 0.32, 0.9, 0.28, +1)   # subtropical gyre (clockwise)
add_gyre(0.52, 0.80, 0.5, 0.16, -1)   # subpolar gyre (counter-clockwise)

# Kuroshio (northward jet along left boundary)
kd=np.abs(fxg-0.14); kb=np.exp(-(kd*kd)/0.002)
v += kb*np.clip(1.0-np.abs(fyg-0.58)*2.5, 0, 1)*1.4

# Kuroshio extension (eastward meandering jet)
jlat=0.545+0.055*np.sin(fxg*14)+0.025*np.sin(fxg*23+0.8)
jb=np.exp(-((fyg-jlat)*11)**2)*np.clip((fxg-0.11)*6,0,1)
u += jb*1.1
v += 0.22*np.cos(fxg*14)*jb + 0.12*np.cos(fxg*23+0.8)*jb

# North Equatorial countercurrent (westward ~10N)
neq=np.exp(-((fyg-0.17)*10)**2)
u -= neq*0.5

# ── 24 mesoscale eddies (realistic North Pacific distribution) ────────────────
np.random.seed(99)
eddy_data = [
    # (cx, cy, strength, radius, sign)  — hand-placed for realism
    (0.14, 0.44, 0.55, 0.055, +1), (0.18, 0.54, 0.45, 0.050, -1),
    (0.24, 0.38, 0.40, 0.048, +1), (0.29, 0.48, 0.38, 0.045, -1),
    (0.35, 0.42, 0.42, 0.052, +1), (0.40, 0.52, 0.36, 0.048, -1),
    (0.46, 0.38, 0.38, 0.050, +1), (0.52, 0.46, 0.34, 0.044, -1),
    (0.58, 0.40, 0.40, 0.050, +1), (0.64, 0.50, 0.32, 0.046, -1),
    (0.70, 0.44, 0.35, 0.048, +1), (0.76, 0.52, 0.30, 0.043, -1),
    (0.82, 0.40, 0.32, 0.046, +1), (0.88, 0.48, 0.28, 0.042, -1),
    (0.20, 0.62, 0.30, 0.042, +1), (0.34, 0.68, 0.28, 0.040, -1),
    (0.48, 0.58, 0.32, 0.044, +1), (0.62, 0.64, 0.26, 0.040, -1),
    (0.76, 0.60, 0.28, 0.042, +1), (0.90, 0.56, 0.24, 0.038, -1),
    (0.25, 0.30, 0.28, 0.040, -1), (0.50, 0.30, 0.26, 0.038, +1),
    (0.72, 0.30, 0.24, 0.036, -1), (0.42, 0.73, 0.22, 0.036, +1),
]
for cx,cy,es,er,esign in eddy_data:
    dx=fxg-cx; dy=fyg-cy; r=np.sqrt(dx*dx+dy*dy)+0.001
    em=es*np.exp(-(r/er)**2)
    u+=esign*em*dy/r; v-=esign*em*dx/r

# ── Curl-noise turbulence (divergence-free fine-scale chaos) ─────────────────
print("Adding curl-noise turbulence…")
np.random.seed(7)
phi = np.random.randn(HS, WS).astype(np.float32)
# Multi-scale: smooth at different scales
phi_fine   = gaussian_filter(phi, sigma=6)    # ~40px features
phi_medium = gaussian_filter(phi, sigma=14)   # ~100px features
phi_coarse = gaussian_filter(phi, sigma=30)   # large meanders

# Curl: u = d(phi)/dy, v = -d(phi)/dx
def curl(p):
    # sobel gives gradient, approximate derivative
    dy_p = sobel(p, axis=0)
    dx_p = sobel(p, axis=1)
    return dy_p, -dx_p   # u=dphi/dy, v=-dphi/dx

uf, vf = curl(phi_fine)
um, vm = curl(phi_medium)
uc, vc = curl(phi_coarse)

u += uf*0.18 + um*0.12 + uc*0.06
v += vf*0.18 + vm*0.12 + vc*0.06

# Normalise velocity to unit-ish magnitude
mag = np.sqrt(u*u+v*v)
mag_p99 = np.percentile(mag, 99)+1e-6
un = (u/mag_p99).astype(np.float32)
vn = (v/mag_p99).astype(np.float32)
speed_norm = np.clip(mag/mag_p99, 0, 1).astype(np.float32)

# ── Build chlorophyll concentration (used as brightness modulator) ────────────
print("Building chlorophyll concentration…")
lons=np.linspace(LON_MIN, LON_MAX, WS, dtype=np.float32)
lats=np.linspace(LAT_MAX, LAT_MIN, HS, dtype=np.float32)
lon_g, lat_g = np.meshgrid(lons, lats)

chl = np.zeros((HS, WS), dtype=np.float32)
chl += 0.55 * np.exp(-((lat_g-50.0)**2)/9.0)   # subarctic front (narrow)

kuro_lon = 143.0+8.0*np.sin((lat_g-20.0)*0.12)
chl += 0.85 * np.exp(-((lon_g-kuro_lon)**2)/10.0 - ((lat_g-36.0)*2.5)**2/12.0)

ext_lat = 35.0+3.5*np.sin((lon_g-145.0)*0.10)+1.5*np.sin((lon_g-145.0)*0.22)
in_ext = (lon_g>145.0)&(lon_g<212.0)
chl += 0.75*np.exp(-((lat_g-ext_lat)**2)/2.0)*in_ext

east=(lon_g>196.0); chl += 0.35*np.exp(-((lat_g-47.0)**2)/25.0)*east

# Gyre suppression (smooth)
gyre_s = (np.tanh((lon_g-155)*0.35)*np.tanh((210-lon_g)*0.35)*
          np.tanh((lat_g-15)*0.45)*np.tanh((33-lat_g)*0.45))
chl *= 1.0 - np.clip(gyre_s,0,1)*0.90
mid_s = (np.tanh((lon_g-160)*0.3)*np.tanh((196-lon_g)*0.3)*
         np.tanh((lat_g-33)*0.4)*np.tanh((42-lat_g)*0.4))
chl *= 1.0 - np.clip(mid_s,0,1)*0.65

chl = np.clip(chl,0,1)
chl = np.log1p(chl*5)/np.log1p(5)  # log-compress
chl /= chl.max()+1e-6

# ── Land mask ─────────────────────────────────────────────────────────────────
print("Loading land mask…")
cache_img=Image.open(os.path.join(SCRIPT_DIR,'chla_neo_cache.png')).convert('RGB')
CW,CH2=cache_img.size
def lon2px(lo): return int((((lo+180)%360)/360.0)*CW)
def lat2py(la): return int((90.0-la)/180.0*CH2)
x0,x1=lon2px(LON_MIN),lon2px(LON_MAX)
y0,y1=lat2py(LAT_MAX),lat2py(LAT_MIN)
left=cache_img.crop((x0,y0,CW,y1)); right=cache_img.crop((0,y0,x1,y1))
reg=Image.new('RGB',(left.width+right.width,left.height))
reg.paste(left,(0,0)); reg.paste(right,(left.width,0))
reg_s=reg.resize((WS,HS),Image.LANCZOS)
ca=np.array(reg_s).astype(np.float32)/255.0
land_s=(gaussian_filter((ca[:,:,0]>ca[:,:,2]+0.06).astype(np.float32),1.5)>0.4).astype(np.float32)

# ── LIC kernel: white noise → flow-aligned streaks ───────────────────────────
def lic_white_noise(steps, step_size):
    """True LIC: advect white noise along streamlines → thin crisp flow lines"""
    np.random.seed(13)
    noise = np.random.rand(HS, WS).astype(np.float32)
    # Slightly smooth noise to reduce pixel-level aliasing
    noise = gaussian_filter(noise, sigma=0.5)

    def trace(direction):
        cx=np.tile(np.arange(WS,dtype=np.float32),(HS,1))
        cy=np.tile(np.arange(HS,dtype=np.float32),(WS,1)).T
        acc=np.zeros((HS,WS),dtype=np.float32)
        for _ in range(steps):
            xi=np.clip(cx,0,WS-1).astype(np.int32); yi=np.clip(cy,0,HS-1).astype(np.int32)
            xi1=np.minimum(xi+1,WS-1); yi1=np.minimum(yi+1,HS-1)
            tx=cx-xi; ty=cy-yi
            su=(un[yi,xi]*(1-tx)*(1-ty)+un[yi,xi1]*tx*(1-ty)+un[yi1,xi]*(1-tx)*ty+un[yi1,xi1]*tx*ty)
            sv=(vn[yi,xi]*(1-tx)*(1-ty)+vn[yi,xi1]*tx*(1-ty)+vn[yi1,xi]*(1-tx)*ty+vn[yi1,xi1]*tx*ty)
            cx=np.clip(cx+direction*su*step_size,0,WS-1)
            cy=np.clip(cy+direction*sv*step_size,0,HS-1)
            acc+=noise[np.minimum(cy.astype(np.int32),HS-1),np.minimum(cx.astype(np.int32),WS-1)]
        return acc/steps

    fwd=trace(1); bwd=trace(-1)
    return (fwd+bwd)/2

# ── Colormap ──────────────────────────────────────────────────────────────────
def colormap(t):
    pts=np.array([[0.00,0.005,0.015,0.040],
                  [0.15,0.008,0.050,0.130],
                  [0.38,0.015,0.180,0.290],
                  [0.60,0.040,0.460,0.570],
                  [0.80,0.160,0.750,0.820],
                  [1.00,0.600,0.960,1.000]])
    return np.interp(t,pts[:,0],pts[:,1]),np.interp(t,pts[:,0],pts[:,2]),np.interp(t,pts[:,0],pts[:,3])

fxl=np.linspace(-1,1,WS,dtype=np.float32); fyl=np.linspace(-1,1,HS,dtype=np.float32)
fxg2,fyg2=np.meshgrid(fxl,fyl); vig_s=np.clip(1.0-(fxg2**2+fyg2**2)*0.25,0.45,1.0)

LAND_C=np.array([0.26,0.28,0.20]); COAST_C=np.array([0.18,0.20,0.14])

def draw_boat(draw,cx,cy,s=3):
    hull=(217,204,165);deck=(127,89,51);cabin=(234,224,199);dark=(45,35,25);shadow=(76,61,40)
    rows=[(7,8),(7,8),(6,9),(6,9),(5,10),(5,10),(5,10),(4,11),(4,11),(4,11),(4,11),(4,11),
          (4,11),(4,11),(4,11),(4,11),(5,10),(5,10),(5,10),(5,10),(5,10),(6,9),(6,9),(7,8),(7,8),(7,8),(7,7),(7,7)]
    for ry,(xl,xr) in enumerate(rows):
        for x in range(xl,xr+1):
            ie=(x==xl or x==xr);ic=(10<=ry<=18 and 5<=x<=10);id_=(4<=ry<=22)
            c=dark if ie else (shadow if ic and (x in (5,10) or ry in (10,18)) else cabin if ic else deck if id_ else hull)
            px=cx+(x-7)*s;py=cy+(len(rows)-1-ry-5)*s;draw.rectangle([px,py,px+s-1,py+s-1],fill=c)

def render_and_save(lic_val, chl_weight, speed_weight, contrast, threshold, fname, label):
    """Combine LIC texture with chlorophyll brightness and current speed."""
    # Blend: LIC gives flow texture, chl gives where filaments are, speed sharpens edges
    combined = lic_val * (chl_weight*chl + speed_weight*speed_norm + (1-chl_weight-speed_weight))
    # Normalize
    combined = (combined - combined.min()) / (combined.max()-combined.min()+1e-6)
    # Contrast + threshold
    d = np.clip((combined - threshold)*contrast, 0, 1)**0.62
    # Apply vignette
    d *= vig_s
    # Colormap
    r,g,b = colormap(d)
    # Land
    coast_e=np.clip(gaussian_filter(land_s,2.0)-land_s*0.99,0,1)*6; coast_e=np.clip(coast_e,0,1)
    r=r*(1-land_s)+LAND_C[0]*land_s; g=g*(1-land_s)+LAND_C[1]*land_s; b=b*(1-land_s)+LAND_C[2]*land_s
    r=np.clip(r-coast_e*0.07,0,1); g=np.clip(g-coast_e*0.07,0,1); b=np.clip(b-coast_e*0.07,0,1)
    # Assemble at supersampled resolution
    rgb_s=np.stack([(np.clip(r,0,1)*255).astype(np.uint8),
                    (np.clip(g,0,1)*255).astype(np.uint8),
                    (np.clip(b,0,1)*255).astype(np.uint8)],axis=2)
    # Downsample to output resolution (anti-aliasing)
    img=Image.fromarray(rgb_s,'RGB').resize((W,H),Image.LANCZOS)
    draw=ImageDraw.Draw(img); draw_boat(draw,W//2,H//2,s=3)
    path=os.path.join(SCRIPT_DIR,fname); img.save(path)
    print(f"  {fname}  [{label}]")

# ── Generate options ──────────────────────────────────────────────────────────
print("\nRunning LIC variants…")

# Short steps: shows flow direction texture, slight blending
print("[1/5] steps=25 short (subtle flow texture)…")
lic25 = lic_white_noise(steps=25, step_size=1.0)
render_and_save(lic25, chl_weight=0.55, speed_weight=0.20, contrast=3.0, threshold=0.20,
                fname="v2_1_subtle.png", label="25 steps — subtle flow direction")

# Medium steps: balanced filaments
print("[2/5] steps=60 medium (clear filaments)…")
lic60 = lic_white_noise(steps=60, step_size=0.9)
render_and_save(lic60, chl_weight=0.60, speed_weight=0.25, contrast=3.5, threshold=0.22,
                fname="v2_2_filaments.png", label="60 steps — clear thin filaments")

# Many steps: long streamlines
print("[3/5] steps=120 long (long sinuous streamlines)…")
lic120 = lic_white_noise(steps=120, step_size=0.8)
render_and_save(lic120, chl_weight=0.65, speed_weight=0.20, contrast=4.0, threshold=0.24,
                fname="v2_3_streamlines.png", label="120 steps — long sinuous streamlines")

# High speed emphasis: current jets prominent
print("[4/5] steps=80 speed-weighted (jets and gyres)…")
lic80 = lic_white_noise(steps=80, step_size=0.9)
render_and_save(lic80, chl_weight=0.40, speed_weight=0.45, contrast=4.2, threshold=0.22,
                fname="v2_4_jets.png", label="80 steps, speed-weighted — jets and gyres prominent")

# Maximum detail: fine step, many steps
print("[5/5] steps=200 fine step (maximum fidelity)…")
lic200 = lic_white_noise(steps=200, step_size=0.5)
render_and_save(lic200, chl_weight=0.60, speed_weight=0.30, contrast=4.5, threshold=0.26,
                fname="v2_5_max.png", label="200 steps, fine — maximum fidelity")

print("\nDone.")
