"""Dejerine plate -> streamlines that follow the ORIGINAL engraving.

Direction at every point comes from Gillet's own hatching (structure tensor of
the drawing). Where the hatching is too dense or too faint to read, the
direction of the white-matter band itself (its medial axis) is used instead.
Streamlines are short-to-medium strokes that stop as soon as they would bend
sharply, so no fibre can turn back, loop, or jump from one bundle into
another: every stroke stays on a direction that is drawn in the plate."""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage import morphology

HERE = __file__.rsplit("/", 1)[0]
SRC, OUT_SVG, OUT_PNG = sys.argv[1], sys.argv[2], sys.argv[3]
DEBUG = sys.argv[4] if len(sys.argv) > 4 else None
exec(open(HERE + "/dejerine.py").read().split("# --- white matter")[0]
     .replace("SRC, OUT_SVG, OUT_PNG = sys.argv[1], sys.argv[2], sys.argv[3]", ""))
rng = np.random.default_rng(11)

# ---------------- white matter mask ----------------------------------------
clean_ink = np.where(leaders, 0, ink)
dens = ndi.gaussian_filter(clean_ink, 4)
wm = (dens > 0.33) & section
wm = morphology.remove_small_objects(morphology.opening(wm, morphology.disk(2)), 300)
wm = morphology.remove_small_holes(wm, 400)
wm_s = ndi.gaussian_filter(wm.astype(np.float32), 2.5) > 0.5
dt = ndi.distance_transform_edt(wm_s)

# ---------------- 1. direction of the hatching (the data) ------------------
gimg = np.where(leaders, 1.0, g)                       # ignore label leader lines
gx, gy = ndi.sobel(gimg, 1), ndi.sobel(gimg, 0)
s = 2.5
Jxx, Jyy, Jxy = (ndi.gaussian_filter(v, s) for v in (gx * gx, gy * gy, gx * gy))
th_h = 0.5 * np.arctan2(2 * Jxy, Jxx - Jyy) + np.pi / 2
coh = np.sqrt((Jxx - Jyy) ** 2 + 4 * Jxy ** 2) / (Jxx + Jyy + 1e-6)
energy = Jxx + Jyy
energy = energy / (np.percentile(energy[wm_s], 90) + 1e-9)
w_h = np.clip(coh, 0, 1) * np.clip(energy, 0, 1)        # trust where the hatching is clear

# ---------------- 2. direction of the band (fallback) ----------------------
sk = morphology.skeletonize(wm_s)
sy, sx = np.nonzero(sk)
th_s = np.zeros_like(g)
# local orientation of the skeleton by PCA on a small window
skf = sk.astype(np.float32)
Ixx = ndi.gaussian_filter(skf * 0, 1)
yy, xx = np.mgrid[-6:7, -6:7]
win = (xx ** 2 + yy ** 2 <= 36).astype(np.float32)
cnt = ndi.convolve(skf, win)
mx = ndi.convolve(skf, win * xx) / (cnt + 1e-9)
my = ndi.convolve(skf, win * yy) / (cnt + 1e-9)
cxx = ndi.convolve(skf, win * xx * xx) / (cnt + 1e-9) - mx ** 2
cyy = ndi.convolve(skf, win * yy * yy) / (cnt + 1e-9) - my ** 2
cxy = ndi.convolve(skf, win * xx * yy) / (cnt + 1e-9) - mx * my
th_sk = 0.5 * np.arctan2(2 * cxy, cxx - cyy)
_, (iy, ix) = ndi.distance_transform_edt(~sk, return_indices=True)
th_s = th_sk[iy, ix]

# ---------------- blend in doubled-angle space, then smooth ----------------
W_SK = 0.18
c2 = w_h * np.cos(2 * th_h) + W_SK * np.cos(2 * th_s)
s2 = w_h * np.sin(2 * th_h) + W_SK * np.sin(2 * th_s)
msk = wm_s.astype(np.float32)
c2 = ndi.gaussian_filter(c2 * msk, 4) / (ndi.gaussian_filter(msk, 4) + 1e-6)
s2 = ndi.gaussian_filter(s2 * msk, 4) / (ndi.gaussian_filter(msk, 4) + 1e-6)
theta = 0.5 * np.arctan2(s2, c2)
vx, vy = np.cos(theta), np.sin(theta)

# ---------------- streamlines: no sharp turns, no U-turns -------------------
STEP = 1.2
MAX_STEPS = 70             # each way -> strokes up to ~170 px
MAX_TURN_STEP = np.radians(9)
MAX_TURN_TOTAL = np.radians(55)

def trace(x0, y0, sgn):
    x, y = float(x0), float(y0)
    px, py = sgn * vx[y0, x0], sgn * vy[y0, x0]
    d0x, d0y = px, py
    pts = []
    for _ in range(MAX_STEPS):
        xi, yi = int(x), int(y)
        ux, uy = vx[yi, xi], vy[yi, xi]
        if ux * px + uy * py < 0: ux, uy = -ux, -uy
        if ux * px + uy * py < np.cos(MAX_TURN_STEP): break
        if ux * d0x + uy * d0y < np.cos(MAX_TURN_TOTAL): break   # never bend far from the start
        x2, y2 = x + ux * STEP, y + uy * STEP
        xi, yi = int(x2), int(y2)
        if not (0 <= xi < W and 0 <= yi < H) or not wm_s[yi, xi]: break
        x, y = x2, y2
        pts.append((x, y)); px, py = ux, uy
    return pts

CELL = 4
occ = np.zeros((H // CELL + 1, W // CELL + 1), np.uint8)
cand = np.argwhere(wm_s); rng.shuffle(cand)
# seed thin gyri first so that they are always reached
cand = cand[np.argsort(dt[cand[:, 0], cand[:, 1]] > 6, kind="stable")]
lines = []
for (y0, x0) in cand:
    if occ[y0 // CELL, x0 // CELL] >= 2:
        continue
    L = trace(x0, y0, -1)[::-1] + [(float(x0), float(y0))] + trace(x0, y0, 1)
    if len(L) < 9:
        continue
    for (x, y) in L[::3]:
        occ[int(y) // CELL, int(x) // CELL] += 1
    p = np.array(L[::3])
    shade = float(np.mean(dens[p[:, 1].astype(int), p[:, 0].astype(int)]))
    lines.append((p, shade))
print("streamlines", len(lines))

# ---------------- SVG ------------------------------------------------------
cy_, cx_ = ndi.center_of_mass(wm_s & (dt > np.percentile(dt[wm_s], 90)))
hub = np.array([cx_, cy_])
maxr = np.hypot(W, H) * 0.6
def fmt(p): return "M" + " ".join(f"{x:.0f} {y:.0f}" for x, y in p)
shs = np.array([s for _, s in lines]); lo, hi = np.percentile(shs, 5), np.percentile(shs, 95)
parts = []
for p, sh in lines:
    t = 0.3 + 0.7 * np.clip((sh - lo) / (hi - lo + 1e-6), 0, 1)
    r, gg, b = (np.array([130, 152, 188]) * (1 - t) + np.array([24, 38, 66]) * t).astype(int)
    if np.hypot(*(p[0] - hub)) > np.hypot(*(p[-1] - hub)):
        p = p[::-1]                                   # grow away from the centre
    d = 1.4 + np.hypot(*(p[0] - hub)) / maxr * 4.2 + rng.uniform(0, 0.7)
    parts.append((d, f'<path d="{fmt(p)}" stroke="rgb({r},{gg},{b})" stroke-opacity="{0.45 + 0.45 * t:.2f}" '
                     f'stroke-width="{0.35 + 0.45 * rng.random():.2f}" data-delay="{d:.2f}" data-dur="{1.6 + rng.uniform(0, 1.0):.2f}"/>'))
parts.sort(key=lambda t: t[0])

alpha = np.clip(ink * 1.15, 0, 1)
la = np.zeros((H, W, 2), np.uint8); la[..., 0] = 70
la[..., 1] = (np.round(alpha * 31) * 255 / 31).astype(np.uint8)
Image.fromarray(la, "LA").save(OUT_PNG, optimize=True)
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" fill="none" stroke-linecap="round" stroke-linejoin="round">\n'
       f'<image class="plate" href="assets/img/dejerine-1895.png" x="0" y="0" width="{W}" height="{H}"/>\n'
       + "\n".join(p for _, p in parts) + "\n</svg>\n")
open(OUT_SVG, "w").write(svg)
print("svg KB", len(svg) // 1024)

if DEBUG:   # direction field drawn as short ticks over the plate
    from PIL import ImageDraw
    im = Image.fromarray((g * 255).astype(np.uint8)).convert("RGB").resize((W * 2, H * 2))
    dr = ImageDraw.Draw(im)
    for y in range(4, H, 9):
        for x in range(4, W, 9):
            if wm_s[y, x]:
                c = (220, 40, 40) if w_h[y, x] > 0.25 else (40, 140, 40)
                dx, dy = vx[y, x] * 4, vy[y, x] * 4
                dr.line([(2 * (x - dx), 2 * (y - dy)), (2 * (x + dx), 2 * (y + dy))], fill=c, width=2)
    im.save(DEBUG)
