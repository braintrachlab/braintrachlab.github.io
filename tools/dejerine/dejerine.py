"""Déjerine coronal section (drawing by H. Gillet) -> animated line drawing.
Outputs an SVG: section outline + grey/white boundary + traced fibre streamlines,
and a faint copy of the original engraving (without labels) underneath."""
import sys, base64, io
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage import measure, morphology

SRC, OUT_SVG, OUT_PNG = sys.argv[1], sys.argv[2], sys.argv[3]
im = Image.open(SRC).convert("L")
W, H = im.size
g = np.asarray(im).astype(np.float32) / 255.0
ink = 1 - g

# --- section mask: drop labels and dashed leader lines ---------------------
# remove the long thin horizontal/vertical leader lines first
lines_bin = ink > 0.35
hl = ndi.binary_opening(ndi.binary_closing(lines_bin, structure=np.ones((1, 9))), structure=np.ones((1, 45)))
vl = ndi.binary_opening(ndi.binary_closing(lines_bin, structure=np.ones((9, 1))), structure=np.ones((45, 1)))
roi = np.zeros_like(lines_bin); roi[0:985, 92:765] = True
cand_l = hl | vl
# a leader line is thin and sits in a pale area; the dense hatching of the white matter is not
lab_l, nl_ = ndi.label(cand_l)
thin = []
for i, sl in enumerate(ndi.find_objects(lab_l), 1):
    hh, ww = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
    area = (lab_l[sl] == i).sum()
    if area / max(hh, ww) < 3.5:
        thin.append(i)
leaders = np.isin(lab_l, thin)
leaders = ndi.binary_dilation(leaders, iterations=1)
dens0 = ndi.gaussian_filter(np.where(leaders, 0, ink), 4)
m = (dens0 > 0.05) & roi
m = morphology.opening(m, morphology.disk(7))
lab, n = ndi.label(m)
sizes = np.bincount(lab.ravel()); sizes[0] = 0
section = np.isin(lab, np.where(sizes > 4000)[0])
section = ndi.binary_fill_holes(ndi.binary_closing(section, iterations=3))
section = ndi.binary_dilation(section, iterations=3)
# keep the ventricle/hole regions that are white inside the section out of the "tissue"
tissue = section & (ndi.gaussian_filter(ink, 3) > 0.06)

# --- white matter: the dark hatched regions -------------------------------
dens = ndi.gaussian_filter(ink, 5)
wm = (dens > 0.42) & section
wm = morphology.remove_small_objects(morphology.opening(wm, morphology.disk(3)), 400)
wm_soft = ndi.gaussian_filter(wm.astype(np.float32), 2)

def contours(mask, sigma, step, minlen):
    out = []
    for c in measure.find_contours(ndi.gaussian_filter(mask.astype(np.float32), sigma), 0.5):
        if len(c) < minlen:
            continue
        c = c[:, ::-1]
        c = ndi.gaussian_filter1d(c, 2, axis=0, mode="nearest")[::step]
        out.append(c)
    return out

outline = contours(section, 2.0, 3, 80)
gw = contours(wm, 2.5, 3, 60)

# --- fibre orientation from the hatching ----------------------------------
gx, gy = ndi.sobel(g, 1), ndi.sobel(g, 0)
s = 3.0
Jxx, Jyy, Jxy = (ndi.gaussian_filter(v, s) for v in (gx * gx, gy * gy, gx * gy))
theta = 0.5 * np.arctan2(2 * Jxy, Jxx - Jyy) + np.pi / 2
coh = np.sqrt((Jxx - Jyy) ** 2 + 4 * Jxy ** 2) / (Jxx + Jyy + 1e-6)
c2 = ndi.gaussian_filter(np.cos(2 * theta) * coh, 4)
s2 = ndi.gaussian_filter(np.sin(2 * theta) * coh, 4)
theta = 0.5 * np.arctan2(s2, c2)
vx, vy = np.cos(theta), np.sin(theta)

rng = np.random.default_rng(2)
field = wm_soft > 0.3
CELL = 5
occ = np.zeros((H // CELL + 1, W // CELL + 1), np.uint8)
STEP = 1.2

def trace(x0, y0, sgn):
    x, y = float(x0), float(y0)
    px, py = sgn * vx[y0, x0], sgn * vy[y0, x0]
    pts = []
    for _ in range(140):
        xi, yi = int(x), int(y)
        ux, uy = vx[yi, xi], vy[yi, xi]
        if ux * px + uy * py < 0: ux, uy = -ux, -uy
        if ux * px + uy * py < 0.8: break
        mx, my = x + ux * STEP / 2, y + uy * STEP / 2
        if not (0 <= int(my) < H and 0 <= int(mx) < W): break
        wx, wy = vx[int(my), int(mx)], vy[int(my), int(mx)]
        if wx * ux + wy * uy < 0: wx, wy = -wx, -wy
        x, y = x + wx * STEP, y + wy * STEP
        xi, yi = int(x), int(y)
        if not (0 <= xi < W and 0 <= yi < H) or not field[yi, xi]: break
        pts.append((x, y)); px, py = wx, wy
    return pts

lines = []
cand = np.argwhere(field); rng.shuffle(cand)
for (y0, x0) in cand:
    if occ[y0 // CELL, x0 // CELL] >= 2:
        continue
    L = trace(x0, y0, -1)[::-1] + [(float(x0), float(y0))] + trace(x0, y0, 1)
    if len(L) < 18:
        continue
    for (x, y) in L[::4]:
        occ[int(y) // CELL, int(x) // CELL] += 1
    p = np.array(L[::4])
    shade = float(np.mean([dens[int(y), int(x)] for x, y in p]))
    lines.append((p, shade))
print("fibres", len(lines), "outline", len(outline), "gw", len(gw))

# --- timing: fibres spread out from the centrum semiovale -----------------
cy_, cx_ = ndi.center_of_mass(wm)
hub = np.array([cx_ * 0.9 + 330 * 0.1, cy_])
maxr = max(np.hypot(*(hub - [0, 0])), np.hypot(*(hub - [W, H])))

def fmt(p): return "M" + " ".join(f"{x:.0f} {y:.0f}" for x, y in p)
INK, SLATE = "#23395d", "#3d5476"
parts = []
for i, c in enumerate([]):
    parts.append((0.0, f'<path d="{fmt(c)}" stroke="{INK}" stroke-opacity="0.75" stroke-width="1.3" data-delay="{0.1 * i:.2f}" data-dur="3.6"/>'))
for i, c in enumerate([]):
    parts.append((0.6, f'<path d="{fmt(c)}" stroke="{SLATE}" stroke-opacity="0.45" stroke-width="0.9" data-delay="{0.6 + 0.05 * i:.2f}" data-dur="3.0"/>'))
shs = np.array([s for _, s in lines]); lo, hi = np.percentile(shs, 5), np.percentile(shs, 95)
for p, sh in lines:
    t = np.clip((sh - lo) / (hi - lo), 0, 1)
    # darker hatching -> deeper ink
    r, gg, b = (np.array([150, 170, 200]) * (1 - t) + np.array([28, 44, 72]) * t).astype(int)
    # orient each fibre from the hub outward, so it "grows" away from the centre
    if np.hypot(*(p[0] - hub)) > np.hypot(*(p[-1] - hub)):
        p = p[::-1]
    r0 = np.hypot(*(p[0] - hub)) / maxr
    d = 1.6 + r0 * 4.8 + rng.uniform(0, 0.8)
    parts.append((d, f'<path d="{fmt(p)}" stroke="rgb({r},{gg},{b})" stroke-opacity="{0.55 + 0.4 * t:.2f}" stroke-width="{0.5 + 0.5 * rng.random():.2f}" data-delay="{d:.2f}" data-dur="{2.0 + rng.uniform(0, 1.0):.2f}"/>'))
parts.sort(key=lambda t: t[0])

# --- the original engraving, cleaned of labels, as a faint underlay -------
# full original plate (labels included) as sepia ink on transparent background
alpha = np.clip(ink * 1.15, 0, 1)
la = np.zeros((H, W, 2), np.uint8)
la[..., 0] = 70
la[..., 1] = (np.round(alpha * 31) * 255 / 31).astype(np.uint8)  # quantised alpha compresses well
Image.fromarray(la, "LA").save(OUT_PNG, optimize=True)

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {W} {H}" '
       f'fill="none" stroke-linecap="round" stroke-linejoin="round">\n'
       + f'<image class="plate" href="assets/img/dejerine-1895.png" x="0" y="0" width="{W}" height="{H}"/>\n'
       + "\n".join(p for _, p in parts) + "\n</svg>\n")
open(OUT_SVG, "w").write(svg)
print("svg KB", len(svg) // 1024)
