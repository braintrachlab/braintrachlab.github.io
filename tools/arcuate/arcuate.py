"""Arcuate fasciculus (long, anterior and posterior segments) -> animated streamlines.

The direction of every stroke is read from the rendered fibres of the source
image (structure tensor inside each coloured segment, ignoring the outline of the
segments). Strokes stop before bending more than ~7 degrees per step or ~50
degrees in total, so no pathway is invented. The drawing unfurls along the tract,
from the temporal terminations round the arch to the frontal lobe.

usage: arcuate.py source.png out_dir"""
import sys, os
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from skimage import morphology

SRC, OUT = sys.argv[1], sys.argv[2]
DEBUG = len(sys.argv) > 3
im = Image.open(SRC).convert("RGBA")
rgba = np.asarray(im).astype(np.float32) / 255.0
a = rgba[..., :3] * rgba[..., 3:] + (1 - rgba[..., 3:])       # on white
H, W = a.shape[:2]
R, G, B = a[..., 0], a[..., 1], a[..., 2]
lum = 0.3 * R + 0.59 * G + 0.11 * B
mx, mn = a.max(-1), a.min(-1)
sat = (mx - mn) / (mx + 1e-6)
hue = np.degrees(np.arctan2(np.sqrt(3) * (G - B), 2 * R - G - B)) % 360

tract = (sat > 0.18) | (lum < 0.75)
tract = morphology.remove_small_objects(morphology.closing(tract, morphology.disk(2)), 500)
tract = ndi.binary_fill_holes(tract)
# colour of each tract pixel, from the nearest well-saturated pixel (shadows have little colour)
good = tract & (sat > 0.3)
_, (iy, ix) = ndi.distance_transform_edt(~good, return_indices=True)
h = hue[iy, ix]
red = tract & ((h < 22) | (h > 330))
yellow = tract & (h >= 38) & (h < 72)
green = tract & (h >= 72) & (h < 180)
segs = {}
for name, m in (("long", red), ("posterior", yellow), ("anterior", green)):
    m = morphology.remove_small_objects(morphology.opening(m, morphology.disk(1)), 150)
    segs[name] = m
print({k: int(v.sum()) for k, v in segs.items()})

# ---------------- direction field ------------------------------------------
gx, gy = ndi.sobel(lum, 1), ndi.sobel(lum, 0)
edge = ndi.binary_dilation(tract, iterations=4) & ~ndi.binary_erosion(tract, iterations=4)
for m in segs.values():
    edge |= (ndi.binary_dilation(m, iterations=3) & ~ndi.binary_erosion(m, iterations=3)) & tract
gx[edge] = 0; gy[edge] = 0
Jxx, Jyy, Jxy = (ndi.gaussian_filter(v, 3.0) for v in (gx * gx, gy * gy, gx * gy))
th = 0.5 * np.arctan2(2 * Jxy, Jxx - Jyy) + np.pi / 2
coh = np.sqrt((Jxx - Jyy) ** 2 + 4 * Jxy ** 2) / (Jxx + Jyy + 1e-6)
fm = (tract & ~edge).astype(np.float32)
c2 = ndi.gaussian_filter(np.cos(2 * th) * coh * fm, 6) / (ndi.gaussian_filter(fm, 6) + 1e-6)
s2 = ndi.gaussian_filter(np.sin(2 * th) * coh * fm, 6) / (ndi.gaussian_filter(fm, 6) + 1e-6)
theta = 0.5 * np.arctan2(s2, c2)
conf = np.hypot(c2, s2)
CONF_MIN = 0.3 * np.median(conf[tract])
vx, vy = np.cos(theta), np.sin(theta)
shade = ndi.gaussian_filter(lum, 1.5)

# geodesic distance along the tract from its temporal end (lowest point) -> drawing order
ys, xs = np.nonzero(tract)
step = 3
sub = tract[::step, ::step]
idx = -np.ones(sub.shape, int); pts = np.argwhere(sub); idx[sub] = np.arange(len(pts))
rows, cols, wts = [], [], []
for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
    b = pts + [dy, dx]
    ok = (b[:, 0] < sub.shape[0]) & (b[:, 1] >= 0) & (b[:, 1] < sub.shape[1])
    aa, bb = pts[ok], b[ok]
    hit = sub[bb[:, 0], bb[:, 1]]
    rows += list(idx[aa[hit, 0], aa[hit, 1]]); cols += list(idx[bb[hit, 0], bb[hit, 1]]); wts += [np.hypot(dy, dx)] * int(hit.sum())
Gr = coo_matrix((wts, (rows, cols)), shape=(len(pts), len(pts))).tocsr(); Gr = Gr.maximum(Gr.T)
src = np.argmax(pts[:, 0] * 10 - np.abs(pts[:, 1] - np.percentile(pts[:, 1], 80)))   # bottom of the temporal fan
dist = dijkstra(Gr, indices=src)
geo = np.full(sub.shape, np.nan); geo[sub] = dist
geo = np.nan_to_num(geo, nan=np.nanmax(dist))
geo = ndi.zoom(geo, step, order=1)[:H, :W]
geo = np.pad(geo, ((0, max(0, H - geo.shape[0])), (0, max(0, W - geo.shape[1]))), mode="edge")
gmax = np.percentile(dist[np.isfinite(dist)], 99)

rng = np.random.default_rng(3)
STEP, MAX_STEPS = 1.3, 160
TURN, TOTAL = np.cos(np.radians(7)), np.cos(np.radians(50))

def trace(mask, x0, y0, sgn):
    x, y = float(x0), float(y0)
    px, py = sgn * vx[y0, x0], sgn * vy[y0, x0]; d0 = (px, py)
    pts, weak = [], 0
    for _ in range(MAX_STEPS):
        ux, uy = vx[int(y), int(x)], vy[int(y), int(x)]
        if conf[int(y), int(x)] < CONF_MIN:
            ux, uy = px, py; weak += 1
            if weak > 10: break
        else:
            weak = 0
        if ux * px + uy * py < 0: ux, uy = -ux, -uy
        if ux * px + uy * py < TURN or ux * d0[0] + uy * d0[1] < TOTAL: break
        x2, y2 = x + ux * STEP, y + uy * STEP
        if not (0 <= int(x2) < W and 0 <= int(y2) < H) or not mask[int(y2), int(x2)]: break
        x, y = x2, y2; pts.append((x, y)); px, py = ux, uy
    return pts

# website palette: muted brick red, ochre, sage green
PAL = {"long": ((128, 40, 38), (206, 104, 92)),
       "posterior": ((150, 112, 30), (222, 186, 98)),
       "anterior": ((40, 92, 58), (128, 176, 118))}
SCALE = 0.62
w, h = int(W * SCALE), int(H * SCALE)
parts = []
for name, m in segs.items():
    mm = morphology.erosion(m, morphology.disk(1))
    cell = 5
    occ = np.zeros((H // cell + 1, W // cell + 1), np.uint8)
    cand = np.argwhere(mm); rng.shuffle(cand)
    lines = []
    for (y0, x0) in cand:
        if occ[y0 // cell, x0 // cell] >= 2: continue
        L = trace(mm, x0, y0, -1)[::-1] + [(float(x0), float(y0))] + trace(mm, x0, y0, 1)
        if len(L) < 10: continue
        for (x, y) in L[::3]: occ[int(y) // cell, int(x) // cell] += 1
        p = np.array(L[::5])
        g0 = geo[int(p[0, 1]), int(p[0, 0])]; g1 = geo[int(p[-1, 1]), int(p[-1, 0])]
        if g0 > g1: p = p[::-1]; g0 = g1
        lines.append((p, float(np.mean(shade[p[:, 1].astype(int), p[:, 0].astype(int)])), g0))
    dk, lt = (np.array(c) for c in PAL[name])
    shs = np.array([l[1] for l in lines]); lo, hi = np.percentile(shs, 5), np.percentile(shs, 95)
    for p, sh, g0 in lines:
        t = np.clip((sh - lo) / (hi - lo + 1e-6), 0, 1)
        r, g_, b = (dk * (1 - t) + lt * t).astype(int)
        q = p * SCALE
        d = 0.5 + min(g0 / gmax, 1.0) * 4.8 + rng.uniform(0, 0.5)
        path = "M" + " ".join(f"{x:.0f} {y:.0f}" for x, y in q)
        parts.append((d, f'<path d="{path}" stroke="rgb({r},{g_},{b})" stroke-opacity="{0.9 - 0.2 * t:.2f}" '
                         f'stroke-width="{0.45 + 0.45 * rng.random():.2f}" data-delay="{d:.2f}" data-dur="{1.4 + rng.uniform(0, 0.8):.2f}"/>'))
    print(name, len(lines))
parts.sort(key=lambda t: t[0])

# soft colour wash, shown after the strokes
tint = np.zeros((H, W, 4), np.uint8)
for name, m in segs.items():
    v = ndi.gaussian_filter(m.astype(np.float32), 1.5)
    sel = v > 0.02
    tint[sel, :3] = PAL[name][1]
    tint[..., 3] = np.maximum(tint[..., 3], (v * 255).astype(np.uint8))
Image.fromarray(tint, "RGBA").resize((w, h), Image.LANCZOS).save(os.path.join(OUT, "arcuate-tint.png"), optimize=True)
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" fill="none" stroke-linecap="round" stroke-linejoin="round">\n'
       f'<image class="plate-tint" href="assets/img/arcuate-tint.png" x="0" y="0" width="{w}" height="{h}" style="--tint-delay:4.5s"/>\n'
       + "\n".join(p for _, p in parts) + "\n</svg>\n")
open(os.path.join(OUT, "arcuate.svg"), "w").write(svg)
print("svg KB", len(svg) // 1024, w, h)

if DEBUG:
    vis = np.full((H, W, 3), 255, np.uint8)
    vis[segs["long"]] = [220, 40, 40]; vis[segs["posterior"]] = [230, 200, 0]; vis[segs["anterior"]] = [0, 160, 60]
    gg = (np.clip(geo / gmax, 0, 1) * 255).astype(np.uint8)
    dbg = np.concatenate([vis, np.stack([gg] * 3, -1) * tract[..., None]], 1)
    Image.fromarray(dbg).resize((W, H // 2)).save(os.path.join(OUT, "_arc_debug.png"))
