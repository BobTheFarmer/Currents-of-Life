#!/usr/bin/env python3
"""
Generates 4 ocean background preview options.
"""
import numpy as np
from PIL import Image, ImageFilter, ImageDraw
import os

W, H = 960, 480

# ── Shared current + chlorophyll fields ───────────────────────────────────────

def build_currents():
    fx = np.linspace(0, 1, W, dtype=np.float32)
    fy = np.linspace(0, 1, H, dtype=np.float32)
    fxg, fyg = np.meshgrid(fx, fy)

    # Subtropical gyre (clockwise) at (0.6, 0.35)
    dx = fxg-0.60; dy = fyg-0.35; r = np.sqrt(dx*dx+dy*dy)+0.01
    gs = np.exp(-(r*r)/0.12); gu = gs*dy/r; gv = -gs*dx/r

    # Subpolar gyre (counter-clockwise) at (0.55, 0.78)
    dx2=fxg-0.55; dy2=fyg-0.78; r2=np.sqrt(dx2*dx2+dy2*dy2)+0.01
    gs2=0.5*np.exp(-(r2*r2)/0.06); gu2=-gs2*dy2/r2; gv2=gs2*dx2/r2

    # Kuroshio northward
    kd=np.abs(fxg-0.15); kb=np.exp(-(kd*kd)/0.003)
    kv=kb*np.clip(1.0-np.abs(fyg-0.60)*2,0,1)*1.2

    # Kuroshio extension jet
    jlat=0.56+0.06*np.sin(fxg*12); jb=np.exp(-((fyg-jlat)*10)**2)*np.clip((fxg-0.12)*5,0,1)
    ju=jb; jv=0.25*np.cos(fxg*12)*jb

    # Mesoscale eddies
    eddies = [(0.30,0.45, 0.45,0.07,+1),(0.65,0.38, 0.38,0.055,-1),
              (0.78,0.60, 0.30,0.05,+1),(0.42,0.70, 0.35,0.06,-1)]
    eu = np.zeros_like(fxg); ev = np.zeros_like(fxg)
    for ex,ey,es,er,esign in eddies:
        ddx=fxg-ex; ddy=fyg-ey; rr=np.sqrt(ddx*ddx+ddy*ddy)+0.01
        em=es*np.exp(-(rr**2)/(2*er**2))
        eu += esign*em*ddy/rr; ev += esign*-em*ddx/rr

    u = gu+gu2+ju*0.9+eu; v = gv+gv2+kv+jv+ev
    return u.astype(np.float32), v.astype(np.float32)


def build_chlorophyll():
    fx = np.linspace(0, 1, W, dtype=np.float32)
    fy = np.linspace(0, 1, H, dtype=np.float32)
    fxg, fyg = np.meshgrid(fx, fy)

    kuro = np.exp(-((fxg-0.18)*6)**2)
    arc  = np.exp(-((fyg-0.82)*5)**2)
    ext_lat = 0.55+0.1*np.sin(fxg*8)
    jet  = np.exp(-((fyg-ext_lat)*14)**2)*np.clip((fxg-0.15)*3,0,1)
    # Add eddies pulling chlorophyll into spirals
    eddy_chl = (np.exp(-((fxg-0.30)**2+(fyg-0.45)**2)/0.008)*0.4 +
                np.exp(-((fxg-0.65)**2+(fyg-0.38)**2)/0.006)*0.3 +
                np.exp(-((fxg-0.78)**2+(fyg-0.60)**2)/0.005)*0.25)

    chl = np.clip(kuro*0.8+arc*0.5+jet*0.9+eddy_chl, 0, 1)
    return chl.astype(np.float32)


def lic(u, v, seed, steps=50, step_size=1.0, bidirectional=True):
    h, w = seed.shape
    mag = np.sqrt(u*u+v*v); mag_max = np.percentile(mag,99)+1e-6
    un = u/mag_max; vn = v/mag_max

    def trace(un, vn, fwd):
        cx = np.tile(np.arange(w,dtype=np.float32), (h,1))
        cy = np.tile(np.arange(h,dtype=np.float32), (w,1)).T
        acc = np.zeros((h,w), dtype=np.float32)
        sign = 1.0 if fwd else -1.0
        for _ in range(steps):
            xi=np.clip(cx,0,w-1).astype(np.int32); yi=np.clip(cy,0,h-1).astype(np.int32)
            xi1=np.minimum(xi+1,w-1); yi1=np.minimum(yi+1,h-1)
            tx=cx-xi; ty=cy-yi
            su=(un[yi,xi]*(1-tx)*(1-ty)+un[yi,xi1]*tx*(1-ty)+
                un[yi1,xi]*(1-tx)*ty   +un[yi1,xi1]*tx*ty)
            sv=(vn[yi,xi]*(1-tx)*(1-ty)+vn[yi,xi1]*tx*(1-ty)+
                vn[yi1,xi]*(1-tx)*ty   +vn[yi1,xi1]*tx*ty)
            cx=np.clip(cx+sign*su*step_size,0,w-1)
            cy=np.clip(cy+sign*sv*step_size,0,h-1)
            xi2=cx.astype(np.int32); yi2=cy.astype(np.int32)
            acc += seed[np.minimum(yi2,h-1),np.minimum(xi2,w-1)]
        return acc/steps

    fwd = trace(un,vn,True)
    if bidirectional:
        bwd = trace(un,vn,False)
        return (fwd+bwd)/2
    return fwd


def vignette(strength=0.4):
    fx=np.linspace(-1,1,W,dtype=np.float32)
    fy=np.linspace(-1,1,H,dtype=np.float32)
    fxg,fyg=np.meshgrid(fx,fy)
    return np.clip(1.0-(fxg**2+fyg**2)*strength, 0.3, 1.0)


def draw_boat(draw, cx, cy, scale=3):
    hull=(217,204,165); deck=(127,89,51); cabin=(234,224,199)
    dark=(45,35,25); shadow=(76,61,40)
    rows=[(7,8),(7,8),(6,9),(6,9),(5,10),(5,10),(5,10),(4,11),
          (4,11),(4,11),(4,11),(4,11),(4,11),(4,11),(4,11),(4,11),
          (5,10),(5,10),(5,10),(5,10),(5,10),(6,9),(6,9),(7,8),
          (7,8),(7,8),(7,7),(7,7)]
    rh=len(rows)
    for ry,(xl,xr) in enumerate(rows):
        for x in range(xl,xr+1):
            ie=(x==xl or x==xr)
            ic=(10<=ry<=18 and 5<=x<=10)
            id_=(4<=ry<=22)
            c=dark if ie else (shadow if ic and (x==5 or x==10 or ry==10 or ry==18) else cabin if ic else deck if id_ else hull)
            px=cx+(x-7)*scale; py=cy+(rh-1-ry-5)*scale
            draw.rectangle([px,py,px+scale-1,py+scale-1], fill=c)


def save(arr_rgb, name, note=""):
    img = Image.fromarray(arr_rgb, "RGB")
    draw = ImageDraw.Draw(img)
    draw_boat(draw, W//2, H//2, scale=3)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    img.save(path)
    print(f"  Saved {name}  {note}")
    return img


def to_rgb(r,g,b):
    return np.stack([(np.clip(r,0,1)*255).astype(np.uint8),
                     (np.clip(g,0,1)*255).astype(np.uint8),
                     (np.clip(b,0,1)*255).astype(np.uint8)], axis=2)


# ── Build shared data ─────────────────────────────────────────────────────────

print("Building fields…")
u, v = build_currents()
chl  = build_chlorophyll()

print("Running LIC (bidirectional, 50 steps)…")
lic_raw = lic(u, v, chl, steps=50, step_size=1.1, bidirectional=True)

# Smooth slightly
lic_sm = np.array(Image.fromarray((lic_raw*255).clip(0,255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))).astype(np.float32)/255.0

vig = vignette(0.35)

mag = np.sqrt(u*u+v*v); mag_n = mag/mag.max()

print("Generating previews…")


# ── Option A: Filaments — thin bright streaks on very dark background ─────────
# High contrast, dark base, only top signals show
disp_a = np.clip((lic_sm - 0.08) * 3.5, 0, 1) ** 0.6
disp_a *= vig

pts = np.array([[0.00,0.008,0.022,0.055],[0.18,0.010,0.065,0.160],
                [0.42,0.020,0.210,0.320],[0.65,0.050,0.520,0.620],
                [0.85,0.200,0.820,0.880],[1.00,0.700,0.970,1.000]])
r=np.interp(disp_a,pts[:,0],pts[:,1]); g=np.interp(disp_a,pts[:,0],pts[:,2]); b=np.interp(disp_a,pts[:,0],pts[:,3])
save(to_rgb(r,g,b), "preview_A_filaments.png", "(high contrast filaments, very dark)")


# ── Option B: Bioluminescent — glowing electric blue/cyan on near-black ───────
# Softer base, intense glow at peaks
disp_b = np.clip((lic_sm - 0.05) * 2.8, 0, 1) ** 0.55

# Add flow speed as glow overlay
glow = np.clip(mag_n * 0.4, 0, 1) * lic_sm

pts_b = np.array([[0.00,0.000,0.002,0.012],[0.20,0.000,0.030,0.120],
                  [0.45,0.010,0.150,0.420],[0.68,0.040,0.450,0.700],
                  [0.85,0.100,0.750,0.950],[1.00,0.600,0.950,1.000]])
rb=np.interp(disp_b,pts_b[:,0],pts_b[:,1]); gb=np.interp(disp_b,pts_b[:,0],pts_b[:,2]); bb=np.interp(disp_b,pts_b[:,0],pts_b[:,3])
# Add glow as extra brightness
rb = np.clip(rb + glow*0.05, 0, 1); gb = np.clip(gb + glow*0.3, 0, 1); bb = np.clip(bb + glow*0.5, 0, 1)
rb *= vig; gb *= vig; bb *= vig
save(to_rgb(rb,gb,bb), "preview_B_bioluminescent.png", "(glowing electric blue)")


# ── Option C: Chlorophyll heatmap — oceanographic false-color ─────────────────
# Navy→blue→cyan→green→yellow→orange for chlorophyll concentration
disp_c = np.clip((lic_sm - 0.03) * 2.2, 0, 1) ** 0.75 * vig

pts_c = np.array([[0.00,0.020,0.050,0.150],  # deep navy
                  [0.15,0.030,0.130,0.380],  # cobalt
                  [0.30,0.050,0.380,0.500],  # teal
                  [0.50,0.100,0.600,0.450],  # sea green
                  [0.68,0.200,0.750,0.200],  # yellow-green
                  [0.82,0.700,0.700,0.050],  # yellow
                  [0.92,0.900,0.400,0.020],  # orange
                  [1.00,0.950,0.180,0.050]]) # red-orange
rc=np.interp(disp_c,pts_c[:,0],pts_c[:,1]); gc=np.interp(disp_c,pts_c[:,0],pts_c[:,2]); bc=np.interp(disp_c,pts_c[:,0],pts_c[:,3])
save(to_rgb(rc,gc,bc), "preview_C_heatmap.png", "(NASA false-color chlorophyll)")


# ── Option D: Deep ocean — rich teal-to-indigo with current speed overlay ─────
# Two-layer: base = chlorophyll richness (teal), overlay = current speed (indigo)
disp_d_chl = np.clip((lic_sm - 0.06) * 2.5, 0, 1) ** 0.65
disp_d_spd = np.clip(mag_n * 1.5, 0, 1) ** 0.5

# Blend: slow+rich = teal, fast+rich = bright cyan, fast+poor = indigo
rd = disp_d_spd*0.10 + disp_d_chl*0.08
gd = disp_d_chl*0.70 + disp_d_spd*0.20
bd = disp_d_spd*0.65 + disp_d_chl*0.55 + 0.06

# Base dark navy floor
rd = np.clip(rd + 0.008, 0, 1); gd = np.clip(gd + 0.025, 0, 1); bd = np.clip(bd + 0.090, 0, 1)
rd *= vig; gd *= vig; bd *= vig
save(to_rgb(rd,gd,bd), "preview_D_deep_ocean.png", "(teal/indigo, speed+chlorophyll blend)")


print("\nDone. 4 options saved:")
print("  preview_A_filaments.png    — high contrast, very dark")
print("  preview_B_bioluminescent.png — electric glowing blue")
print("  preview_C_heatmap.png      — NASA false-color")
print("  preview_D_deep_ocean.png   — teal/indigo speed blend")
