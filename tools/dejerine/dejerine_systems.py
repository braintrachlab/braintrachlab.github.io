"""Dejerine plate (high resolution) -> streamlines coloured by fibre system.

Inputs (same plate, pixel-aligned):
  plate.png   the original engraving
  guides.png  the same engraving with hand-drawn guide lines:
              red = commissural (corpus callosum), green = association (U-fibres),
              blue = projection.

The DIRECTION of every streamline is read from Gillet's hatching, never from the
guide lines. The guides only decide which system a streamline belongs to: each
stroke is coloured by the nearest guide that runs parallel to it. Strokes stop
before bending more than ~7 degrees per step or ~55 degrees overall, so no
pathway is invented. The yellow of the paper is discarded.

usage: dejerine_systems.py plate.png guides.png out_dir"""
import sys, os
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage import morphology

PLATE, GUIDES, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
DEBUG = len(sys.argv) > 4
WORK = 0.62                                   # working scale of the 300 dpi render

def load(p):
    im = Image.open(p).convert("RGB")
    im = im.resize((int(im.width * WORK), int(im.height * WORK)), Image.LANCZOS)
    return np.asarray(im).astype(np.float32) / 255.0

a = load(PLATE); b = load(GUIDES)
H, W = a.shape[:2]

# ---------------- ink, without the yellow paper ---------------------------
lum = 0.3 * a[..., 0] + 0.59 * a[..., 1] + 0.11 * a[..., 2]
paper_mask = (a.min(-1) < 0.97) & (lum > np.percentile(lum[a.min(-1) < 0.97], 60))
paper = np.median(lum[paper_mask])
ink = np.clip(1.0 - lum / paper, 0, 1)
ink = np.clip(ink / np.percentile(ink[ink > 0.05], 99), 0, 1)
g = 1.0 - ink                                   # neutral grey engraving

# ---------------- guide lines ---------------------------------------------
mx, mn = b.max(-1), b.min(-1)
sat = (mx - mn) / (mx + 1e-6)
R, G, B = b[..., 0], b[..., 1], b[..., 2]
hue = np.degrees(np.arctan2(np.sqrt(3) * (G - B), 2 * R - G - B)) % 360
col = sat > 0.4
guides = {"commissural": col & ((hue < 20) | (hue > 340)),
          "association": col & (hue > 90) & (hue < 160),
          "projection": col & (hue > 185) & (hue < 230)}
guides = {k: morphology.remove_small_objects(v, 20) for k, v in guides.items()}
anyguide = ndi.binary_dilation(guides["commissural"] | guides["association"] | guides["projection"], iterations=2)
# the engraving under the guide lines is taken from the clean plate, so nothing to fix there

# ---------------- section, labels and leader lines -------------------------
dark = ink > 0.35
hl = ndi.binary_opening(ndi.binary_closing(dark, structure=np.ones((1, 9))), structure=np.ones((1, 55)))
vl = ndi.binary_opening(ndi.binary_closing(dark, structure=np.ones((9, 1))), structure=np.ones((55, 1)))
labl, nl = ndi.label(hl | vl)
thin = [i for i, sl in enumerate(ndi.find_objects(labl), 1)
        if (labl[sl] == i).sum() / max(sl[0].stop - sl[0].start, sl[1].stop - sl[1].start) < 4.0]
leaders = ndi.binary_dilation(np.isin(labl, thin), iterations=1)
clean_ink = np.where(leaders, 0, ink)
dens0 = ndi.gaussian_filter(clean_ink, 6)
m = morphology.opening(dens0 > 0.05, morphology.disk(10))
lab, n = ndi.label(m)
sz = np.bincount(lab.ravel()); sz[0] = 0
section = np.isin(lab, np.where(sz > 0.02 * sz.max())[0])
section = ndi.binary_dilation(ndi.binary_fill_holes(ndi.binary_closing(section, iterations=4)), iterations=3)

dens = ndi.gaussian_filter(clean_ink, 5)
wm = (dens > 0.33) & section
wm = morphology.remove_small_objects(morphology.opening(wm, morphology.disk(2)), 500)
wm = morphology.remove_small_holes(wm, 600)
wm_s = ndi.gaussian_filter(wm.astype(np.float32), 3) > 0.5
dt = ndi.distance_transform_edt(wm_s)
print("size", W, H, "white matter px", int(wm_s.sum()))

# ---------------- direction from the hatching ------------------------------
gimg = np.where(leaders, 1.0, g)
gx, gy = ndi.sobel(gimg, 1), ndi.sobel(gimg, 0)
Jxx, Jyy, Jxy = (ndi.gaussian_filter(v, 3.5) for v in (gx * gx, gy * gy, gx * gy))
th_h = 0.5 * np.arctan2(2 * Jxy, Jxx - Jyy) + np.pi / 2
coh = np.sqrt((Jxx - Jyy) ** 2 + 4 * Jxy ** 2) / (Jxx + Jyy + 1e-6)
energy = (Jxx + Jyy) / (np.percentile((Jxx + Jyy)[wm_s], 90) + 1e-9)
w_h = np.clip(coh, 0, 1) * np.clip(energy, 0, 1)
# fallback where the hatching is unreadable: direction of the white-matter band
sk = morphology.skeletonize(wm_s).astype(np.float32)
yy, xx = np.mgrid[-8:9, -8:9]; win = (xx ** 2 + yy ** 2 <= 64).astype(np.float32)
cnt = ndi.convolve(sk, win)
mx_ = ndi.convolve(sk, win * xx) / (cnt + 1e-9); my_ = ndi.convolve(sk, win * yy) / (cnt + 1e-9)
cxx = ndi.convolve(sk, win * xx * xx) / (cnt + 1e-9) - mx_ ** 2
cyy = ndi.convolve(sk, win * yy * yy) / (cnt + 1e-9) - my_ ** 2
cxy = ndi.convolve(sk, win * xx * yy) / (cnt + 1e-9) - mx_ * my_
th_sk = 0.5 * np.arctan2(2 * cxy, cxx - cyy)
_, (iy, ix) = ndi.distance_transform_edt(sk == 0, return_indices=True)
th_s = th_sk[iy, ix]
c2 = w_h * np.cos(2 * th_h) + 0.15 * np.cos(2 * th_s)
s2 = w_h * np.sin(2 * th_h) + 0.15 * np.sin(2 * th_s)
msk = wm_s.astype(np.float32)
c2 = ndi.gaussian_filter(c2 * msk, 5) / (ndi.gaussian_filter(msk, 5) + 1e-6)
s2 = ndi.gaussian_filter(s2 * msk, 5) / (ndi.gaussian_filter(msk, 5) + 1e-6)
theta = 0.5 * np.arctan2(s2, c2)
vx, vy = np.cos(theta), np.sin(theta)
shade_img = ndi.gaussian_filter(dens, 1.0)

# ---------------- system field from the guides -----------------------------
SIG = 38.0 * WORK / 0.62
def guide_fields(mask):
    gm = mask.astype(np.float32)
    gxx, gyy_ = ndi.sobel(ndi.gaussian_filter(gm, 2), 1), ndi.sobel(ndi.gaussian_filter(gm, 2), 0)
    Txx, Tyy, Txy = (ndi.gaussian_filter(v, 3) for v in (gxx * gxx, gyy_ * gyy_, gxx * gyy_))
    tang = 0.5 * np.arctan2(2 * Txy, Txx - Tyy) + np.pi / 2
    d, (iy, ix) = ndi.distance_transform_edt(~mask, return_indices=True)
    return d, tang[iy, ix]
FIELDS = {k: guide_fields(v) for k, v in guides.items()}
SHELL = 9.0
_bd = wm_s & ~ndi.binary_erosion(wm_s, iterations=1)
_bx, _by = ndi.sobel(ndi.gaussian_filter(wm_s.astype(np.float32), 3), 1), ndi.sobel(ndi.gaussian_filter(wm_s.astype(np.float32), 3), 0)
border_t = np.arctan2(_by, _bx) + np.pi / 2

def classify(p):
    xi = np.clip(p[:, 0].astype(int), 0, W - 1); yi = np.clip(p[:, 1].astype(int), 0, H - 1)
    seg = np.diff(p, axis=0); ang = np.arctan2(seg[:, 1], seg[:, 0]); ang = np.r_[ang, ang[-1:]]
    scores = {}
    for k, (d, tg) in FIELDS.items():
        align = np.abs(np.cos(ang - tg[yi, xi])) ** 2
        scores[k] = float(np.mean(np.exp(-(d[yi, xi] / SIG) ** 2 / 2) * (0.25 + 0.75 * align)))
    # U-fibres run in the thin shell under the cortex, parallel to the grey/white border
    shell = float(np.mean(dt[yi, xi] < SHELL))
    btan = border_t[yi, xi]
    par = float(np.mean(np.abs(np.cos(ang - btan)) ** 2))
    scores["association"] *= (1.0 + 1.5 * shell * par)
    scores["commissural"] *= (1.0 - 0.5 * shell * par)
    scores["projection"] *= (1.0 - 0.5 * shell * par)
    best = max(scores, key=scores.get)
    return best, scores[best]

# ---------------- streamlines ----------------------------------------------
rng = np.random.default_rng(13)
STEP, MAX_STEPS = 1.3, 160
TURN, TOTAL = np.cos(np.radians(7)), np.cos(np.radians(55))
def trace(x0, y0, sgn):
    x, y = float(x0), float(y0)
    px, py = sgn * vx[y0, x0], sgn * vy[y0, x0]; d0 = (px, py)
    pts = []
    for _ in range(MAX_STEPS):
        ux, uy = vx[int(y), int(x)], vy[int(y), int(x)]
        if ux * px + uy * py < 0: ux, uy = -ux, -uy
        if ux * px + uy * py < TURN or ux * d0[0] + uy * d0[1] < TOTAL: break
        x2, y2 = x + ux * STEP, y + uy * STEP
        if not (0 <= int(x2) < W and 0 <= int(y2) < H) or not wm_s[int(y2), int(x2)]: break
        x, y = x2, y2; pts.append((x, y)); px, py = ux, uy
    return pts

CELL = 4
occ = np.zeros((H // CELL + 1, W // CELL + 1), np.uint8)
cand = np.argwhere(wm_s); rng.shuffle(cand)
cand = cand[np.argsort(dt[cand[:, 0], cand[:, 1]] > 8, kind="stable")]      # thin gyri first
lines = []
for (y0, x0) in cand:
    if occ[y0 // CELL, x0 // CELL] >= 2: continue
    L = trace(x0, y0, -1)[::-1] + [(float(x0), float(y0))] + trace(x0, y0, 1)
    if len(L) < 12: continue
    for (x, y) in L[::3]: occ[int(y) // CELL, int(x) // CELL] += 1
    p = np.array(L[::5])
    sys_, sc = classify(p)
    lines.append((p, float(np.mean(shade_img[p[:, 1].astype(int), p[:, 0].astype(int)])), sys_, sc))
print("streamlines", len(lines), {k: sum(1 for l in lines if l[2] == k) for k in FIELDS})

# ---------------- output ---------------------------------------------------
PAL = {"commissural": ((112, 30, 42), (196, 112, 116)),     # garnet
       "association": ((34, 84, 56), (132, 178, 128)),     # sage
       "projection": ((26, 44, 78), (124, 150, 190))}      # ink blue
NEUTRAL = ((70, 78, 92), (170, 176, 186))
OUT_SCALE = 0.75
w, h = int(W * OUT_SCALE), int(H * OUT_SCALE)
cy_, cx_ = ndi.center_of_mass(wm_s & (dt > np.percentile(dt[wm_s], 90)))
hub = np.array([cx_, cy_]); maxr = np.hypot(W, H) * 0.6
shs = np.array([l[1] for l in lines]); lo, hi = np.percentile(shs, 3), np.percentile(shs, 97)
parts = []
for p, sh, sys_, sc in lines:
    t = 1.0 - np.clip((sh - lo) / (hi - lo + 1e-6), 0, 1)       # dense hatching -> dark
    dk, lt = (np.array(c) for c in (PAL[sys_] if sc > 0.08 else NEUTRAL))
    r, g_, b_ = (lt * t + dk * (1 - t)).astype(int)
    if np.hypot(*(p[0] - hub)) > np.hypot(*(p[-1] - hub)): p = p[::-1]
    d = 1.2 + np.hypot(*(p[0] - hub)) / maxr * 4.4 + rng.uniform(0, 0.7)
    q = p * OUT_SCALE
    path = "M" + " ".join(f"{x:.0f} {y:.0f}" for x, y in q)
    parts.append((d, f'<path d="{path}" stroke="rgb({r},{g_},{b_})" stroke-opacity="{0.92 - 0.2 * t:.2f}" '
                     f'stroke-width="{0.35 + 0.35 * rng.random():.2f}" data-delay="{d:.2f}" data-dur="{1.6 + rng.uniform(0, 1.0):.2f}"/>'))
parts.sort(key=lambda t: t[0])

# plate: neutral grey engraving, transparent paper
alpha = np.clip(ink * 1.1, 0, 1)
page = ndi.binary_erosion(a.min(-1) < 0.985, iterations=int(18 * WORK / 0.62))   # inside the scanned sheet
alpha *= page
alpha[alpha < 0.08] = 0                                                         # paper grain
drawn = ndi.binary_dilation(ink > 0.45, iterations=int(22 * WORK / 0.62))       # near the drawing only
alpha *= ndi.gaussian_filter(drawn.astype(np.float32), 4)
la = np.zeros((H, W, 2), np.uint8); la[..., 0] = 60
la[..., 1] = (np.round(alpha * 31) * 255 / 31).astype(np.uint8)
Image.fromarray(la, "LA").resize((w, h), Image.LANCZOS).save(os.path.join(OUT, "dejerine-1895.png"), optimize=True)
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" fill="none" stroke-linecap="round" stroke-linejoin="round">\n'
       f'<image class="plate plate-neutral" href="assets/img/dejerine-1895.png" x="0" y="0" width="{w}" height="{h}"/>\n'
       + "\n".join(p for _, p in parts) + "\n</svg>\n")
open(os.path.join(OUT, "dejerine-lines.svg"), "w").write(svg)
print("svg", w, h, len(svg) // 1024, "KB")

if DEBUG:
    vis = np.stack([g * 255] * 3, -1).astype(np.uint8)
    vis[wm_s] = (vis[wm_s] * 0.7 + np.array([200, 210, 230]) * 0.3).astype(np.uint8)
    for k, c in (("commissural", (220, 30, 40)), ("association", (30, 170, 60)), ("projection", (40, 120, 230))):
        vis[ndi.binary_dilation(guides[k], iterations=1)] = c
    Image.fromarray(vis).resize((W // 2, H // 2)).save(os.path.join(OUT, "_dj_debug.png"))
