"""FAT figure (macaque, chimpanzee, human) -> three animated plates.

For each species: a pale plate of the brain surface (labels, boxes and
silhouettes removed) and streamlines traced from the rendered FAT fibres,
orange for the prefrontal FAT and green for the precentral FAT. Streamline
directions come from the original rendering; strokes stop before bending
more than a few degrees per step, so no pathway is invented."""
import sys, os
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage import morphology

SRC, OUTDIR = sys.argv[1], sys.argv[2]
DEBUG = len(sys.argv) > 3
os.makedirs(OUTDIR, exist_ok=True)
X0, Y0 = 100, 598
im = Image.open(SRC).convert("RGB").crop((X0, Y0, 2856, 1182))
a = np.asarray(im).astype(np.float32) / 255.0
H, W = a.shape[:2]
R, G, B = a[..., 0], a[..., 1], a[..., 2]
lum = 0.3 * R + 0.59 * G + 0.11 * B
mx, mn = a.max(-1), a.min(-1)
sat = (mx - mn) / (mx + 1e-6)
hue = np.degrees(np.arctan2(np.sqrt(3) * (G - B), 2 * R - G - B)) % 360
col = (sat > 0.22) & (mx > 0.12)
dark = (lum < 0.45) & ~col

# brain surfaces: large light-grey regions (labels, box lines, silhouettes excluded)
base = (lum < 0.975) & ~dark
base = morphology.opening(base, morphology.disk(2))
lab, n = ndi.label(base)
sz = np.bincount(lab.ravel()); sz[0] = 0
brain = np.isin(lab, np.where(sz > 20000)[0])
brain = ndi.binary_fill_holes(morphology.closing(brain, morphology.disk(3)))

# fibre masks: coloured pixels on the brain (the coloured labels lie on white and are dropped)
near = ndi.binary_dilation(brain, iterations=2)
def colour_mask(m):
    lab, n = ndi.label(m)
    keep = [i for i, sl in enumerate(ndi.find_objects(lab), 1)
            if (lab[sl] == i).sum() > 60 and (near[sl][lab[sl] == i]).mean() > 0.9]
    out = np.isin(lab, keep)
    return morphology.closing(out, morphology.disk(1)) & brain
orange = colour_mask(col & (hue > 8) & (hue < 58))
green = colour_mask(col & (hue > 65) & (hue < 175))
fibre = orange | green

# plate: brain shading, with fibres and box lines filled in from the surrounding surface
valid = brain & ~fibre & ~dark & ~ndi.binary_dilation(col, iterations=1)
_, (iy, ix) = ndi.distance_transform_edt(~valid, return_indices=True)
surf = lum[iy, ix]
surf = np.where(valid, lum, ndi.gaussian_filter(surf, 2))
alpha = np.clip((1.0 - surf) * 2.3, 0, 1) * ndi.gaussian_filter(brain.astype(np.float32), 1.0)

# direction field from the rendered fibres
gx, gy = ndi.sobel(lum, 1), ndi.sobel(lum, 0)
# ignore the contrast of the bundle outline: only the streaks inside a bundle give the direction
edge = ndi.binary_dilation(fibre, iterations=5) & ~ndi.binary_erosion(fibre, iterations=5)
for c in (orange, green):
    edge |= ndi.binary_dilation(c, iterations=4) & ~ndi.binary_erosion(c, iterations=4) & fibre
gx[edge] = 0; gy[edge] = 0
Jxx, Jyy, Jxy = (ndi.gaussian_filter(v, 3.5) for v in (gx * gx, gy * gy, gx * gy))
th = 0.5 * np.arctan2(2 * Jxy, Jxx - Jyy) + np.pi / 2
coh = np.sqrt((Jxx - Jyy) ** 2 + 4 * Jxy ** 2) / (Jxx + Jyy + 1e-6)
fm = (fibre & ~edge).astype(np.float32)
c2 = ndi.gaussian_filter(np.cos(2 * th) * coh * fm, 7) / (ndi.gaussian_filter(fm, 7) + 1e-6)
s2 = ndi.gaussian_filter(np.sin(2 * th) * coh * fm, 7) / (ndi.gaussian_filter(fm, 7) + 1e-6)
theta = 0.5 * np.arctan2(s2, c2)
conf = np.hypot(c2, s2)
CONF_MIN = 0.3 * np.median(conf[fibre])
print('conf median', float(np.median(conf[fibre])))
vx, vy = np.cos(theta), np.sin(theta)
shade_img = ndi.gaussian_filter(lum, 1.5)

rng = np.random.default_rng(5)
STEP, MAX_STEPS = 1.2, 150
TURN, TOTAL = np.cos(np.radians(7)), np.cos(np.radians(45))

def trace(mask, x0, y0, sgn):
    x, y = float(x0), float(y0)
    px, py = sgn * vx[y0, x0], sgn * vy[y0, x0]; d0 = (px, py)
    pts = []
    weak = 0
    for _ in range(MAX_STEPS):
        ux, uy = vx[int(y), int(x)], vy[int(y), int(x)]
        if conf[int(y), int(x)] < CONF_MIN:      # direction unreadable: go straight on, briefly
            ux, uy = px, py; weak += 1
            if weak > 12: break
        else:
            weak = 0
        if ux * px + uy * py < 0: ux, uy = -ux, -uy
        if ux * px + uy * py < TURN or ux * d0[0] + uy * d0[1] < TOTAL: break
        x2, y2 = x + ux * STEP, y + uy * STEP
        if not (0 <= int(x2) < W and 0 <= int(y2) < H) or not mask[int(y2), int(x2)]: break
        x, y = x2, y2; pts.append((x, y)); px, py = ux, uy
    return pts

def streamlines(mask, cell):
    occ = np.zeros((H // cell + 1, W // cell + 1), np.uint8)
    cand = np.argwhere(mask); rng.shuffle(cand)
    out = []
    for (y0, x0) in cand:
        if occ[y0 // cell, x0 // cell] >= 2: continue
        L = trace(mask, x0, y0, -1)[::-1] + [(float(x0), float(y0))] + trace(mask, x0, y0, 1)
        if len(L) < 10: continue
        for (x, y) in L[::3]: occ[int(y) // cell, int(x) // cell] += 1
        p = np.array(L[::3])
        if p[0, 1] < p[-1, 1]: p = p[::-1]          # grow upwards, from the frontal operculum
        out.append((p, float(np.mean(shade_img[p[:, 1].astype(int), p[:, 0].astype(int)]))))
    return out

PAL = {"orange": ((150, 72, 24), (226, 150, 78)), "green": ((36, 92, 52), (120, 172, 112))}

# split into the three species by the brain components (left to right)
lab, n = ndi.label(ndi.binary_dilation(brain, iterations=25))
sz = np.bincount(lab.ravel()); sz[0] = 0
comps = sorted(np.argsort(sz)[::-1][:3], key=lambda i: ndi.center_of_mass(lab == i)[1])
names = ["macaque", "chimpanzee", "human"]
SCALE = 0.6
meta = []
for k, (ci, name) in enumerate(zip(comps, names)):
    region = lab == ci
    ys, xs = np.nonzero(region & brain)
    pad = 6
    x1, x2 = max(xs.min() - pad, 0), min(xs.max() + pad, W)
    y1, y2 = max(ys.min() - pad, 0), min(ys.max() + pad, H)
    w, h = int((x2 - x1) * SCALE), int((y2 - y1) * SCALE)
    parts = []
    for cname, m in (("orange", orange), ("green", green)):
        mm = morphology.erosion(m & region, morphology.disk(2))
        if not mm.any(): continue
        sl = streamlines(mm, 3)
        ytop, ybot = ys.min(), ys.max()
        dk, lt = (np.array(c) for c in PAL[cname])
        shs = np.array([s for _, s in sl]) if sl else np.array([0.5])
        lo, hi = np.percentile(shs, 5), np.percentile(shs, 95)
        for p, sh in sl:
            t = np.clip((sh - lo) / (hi - lo + 1e-6), 0, 1)
            r, g_, b = (dk * (1 - t) + lt * t).astype(int)
            q = (p - [x1, y1]) * SCALE
            d = 0.6 + k * 1.1 + (ybot - p[0, 1]) / (ybot - ytop + 1) * 2.4 + rng.uniform(0, 0.5)
            path = "M" + " ".join(f"{x:.1f} {y:.1f}" for x, y in q)
            parts.append((d, f'<path d="{path}" stroke="rgb({r},{g_},{b})" stroke-opacity="{0.92 - 0.2 * t:.2f}" '
                             f'stroke-width="{0.45 + 0.45 * rng.random():.2f}" data-delay="{d:.2f}" data-dur="{1.6 + rng.uniform(0, 0.9):.2f}"/>'))
    parts.sort(key=lambda t: t[0])
    pl = alpha[y1:y2, x1:x2]
    la = np.zeros(pl.shape + (2,), np.uint8); la[..., 0] = 64
    la[..., 1] = (np.round(pl * 31) * 255 / 31).astype(np.uint8)
    tint = np.zeros(pl.shape + (4,), np.uint8)
    for cname, m in (("orange", orange), ("green", green)):
        mm = ndi.gaussian_filter((m & region)[y1:y2, x1:x2].astype(np.float32), 1.5)
        c = np.array(PAL[cname][1])
        sel = mm > 0.02
        tint[sel, :3] = c
        tint[..., 3] = np.maximum(tint[..., 3], (mm * 255).astype(np.uint8))
    tpng = f"fat-{name}-tint.png"
    Image.fromarray(tint, "RGBA").resize((w, h), Image.LANCZOS).save(os.path.join(OUTDIR, tpng), optimize=True)
    png = f"fat-{name}.png"
    Image.fromarray(la, "LA").resize((w, h), Image.LANCZOS).save(os.path.join(OUTDIR, png), optimize=True)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" fill="none" stroke-linecap="round" stroke-linejoin="round">\n'
           f'<image class="plate plate-cool" href="assets/img/{png}" x="0" y="0" width="{w}" height="{h}"/>\n'
           f'<image class="plate-tint" href="assets/img/{tpng}" x="0" y="0" width="{w}" height="{h}" style="--tint-delay:{1.6 + k * 1.1:.1f}s"/>\n'
           + "\n".join(p for _, p in parts) + "\n</svg>\n")
    open(os.path.join(OUTDIR, f"fat-{name}.svg"), "w").write(svg)
    meta.append((name, w, h, len(parts), len(svg) // 1024))
print(meta)

if DEBUG:
    vis = (a * 255).astype(np.uint8).copy()
    vis[~brain] = 255
    vis[orange] = [255, 140, 0]; vis[green] = [0, 170, 0]
    Image.fromarray(vis).resize((W // 2, H // 2)).save(os.path.join(OUTDIR, "_debug.png"))
