"""Dejerine plate -> anatomically oriented streamlines.

Instead of following the local hatching (which produced swirls), the fibres
follow the medial axis of the white matter: a tree rooted in the centrum
semiovale whose branches run into every gyrus, down the internal capsule and
round into the temporal lobe. Each branch is filled with parallel strands that
widen and narrow with the white matter, so every gyral stalk is covered."""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra, connected_components
from skimage import morphology

SRC, OUT_SVG, OUT_PNG, DEBUG = sys.argv[1], sys.argv[2], sys.argv[3], (sys.argv[4] if len(sys.argv) > 4 else None)
exec(open(__file__.replace("dejerine2.py", "dejerine.py")).read().split("# --- white matter")[0]
     .replace("SRC, OUT_SVG, OUT_PNG = sys.argv[1], sys.argv[2], sys.argv[3]", ""))
rng = np.random.default_rng(7)

# ---------------- white matter mask (covers the thin gyral stalks too) ------
clean_ink = np.where(leaders, 0, ink)
dens = ndi.gaussian_filter(clean_ink, 4)
wm = (dens > 0.33) & section
wm = morphology.remove_small_objects(morphology.opening(wm, morphology.disk(2)), 300)
wm = morphology.remove_small_holes(wm, 400)
wm_s = ndi.gaussian_filter(wm.astype(np.float32), 2.5) > 0.5
dt = ndi.distance_transform_edt(wm_s)

# ---------------- medial axis, pruned ---------------------------------------
sk = morphology.skeletonize(wm_s)
def nbrs(mask):
    k = np.ones((3, 3)); k[1, 1] = 0
    return ndi.convolve(mask.astype(int), k, mode="constant") * mask
for _ in range(3):  # remove short spurs that point sideways into the cortex
    n = nbrs(sk)
    ends = np.argwhere((n == 1) & sk)
    junc = (n >= 3) & sk
    for (y, x) in ends:
        path = [(y, x)]
        py, px = y, x
        prev = None
        while True:
            nb = [(py + dy, px + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                  if (dy or dx) and 0 <= py + dy < H and 0 <= px + dx < W and sk[py + dy, px + dx] and (py + dy, px + dx) != prev
                  and (py + dy, px + dx) not in path]
            if len(nb) != 1 or junc[nb[0]]:
                break
            prev = (py, px); py, px = nb[0]; path.append((py, px))
            if len(path) > 200:
                break
        if junc[min(max(py, 0), H - 1), min(max(px, 0), W - 1)] or len(nb) > 1:
            if len(path) < max(14, 2.4 * dt[py, px]):
                for q in path:
                    sk[q] = False
    sk = morphology.skeletonize(sk)

# ---------------- skeleton graph and trees ----------------------------------
idx = -np.ones((H, W), int)
pts = np.argwhere(sk); idx[sk] = np.arange(len(pts))
rows, cols, w = [], [], []
for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
    a = pts; b = pts + [dy, dx]
    ok = (b[:, 0] < H) & (b[:, 1] >= 0) & (b[:, 1] < W)
    a, b = a[ok], b[ok]
    hit = sk[b[:, 0], b[:, 1]]
    rows += list(idx[a[hit, 0], a[hit, 1]]); cols += list(idx[b[hit, 0], b[hit, 1]])
    w += [np.hypot(dy, dx)] * int(hit.sum())
G = coo_matrix((w, (rows, cols)), shape=(len(pts), len(pts))).tocsr(); G = G.maximum(G.T)
ncomp, lab = connected_components(G, directed=False)

deg = np.asarray((G > 0).sum(1)).ravel()
paths = []   # each: array of (x, y) from root to tip
for c in range(ncomp):
    members = np.where(lab == c)[0]
    if len(members) < 25:
        continue
    # root: the thickest point of the component (centrum semiovale for the main one)
    root = members[np.argmax(dt[pts[members, 0], pts[members, 1]])]
    dist, pred = dijkstra(G, indices=root, return_predecessors=True)
    tips = [i for i in members if deg[i] == 1]
    for t in tips:
        seq = [t]
        while seq[-1] != root and pred[seq[-1]] >= 0:
            seq.append(pred[seq[-1]])
        seq = seq[::-1]
        if len(seq) < 6:
            continue
        p = pts[seq][:, ::-1].astype(float)  # (x, y)
        paths.append((p, dist[t], seq))

# lower-left: internal capsule / cerebral peduncle. The hatching there is
# a broad diagonal sheet, so it is drawn as a guided projection bundle.
def in_box(x, y):
    return (x < 320) & (y > 565) & (y < 880)
paths = [(p, t, sq) for p, t, sq in paths if not in_box(p[-1][0], p[-1][1])]
mult = np.zeros(len(pts), int)
for _, _, sq in paths:
    mult[sq] += 1
GUIDE = np.array([(395, 470), (372, 560), (338, 640), (285, 710), (220, 775), (160, 835), (120, 870)], float)

def smooth(p, s):
    return ndi.gaussian_filter1d(p, s, axis=0, mode="nearest")

def extend_to_border(p):
    """continue past the skeleton tip into the gyral crown, until the white matter ends"""
    d = p[-1] - p[-6]; d /= (np.linalg.norm(d) + 1e-9)
    ext = []
    q = p[-1].copy()
    for _ in range(60):
        q = q + d * 1.5
        xi, yi = int(q[0]), int(q[1])
        if not (0 <= xi < W and 0 <= yi < H) or not wm_s[yi, xi]:
            break
        ext.append(q.copy())
    return np.vstack([p] + ([np.array(ext)] if ext else []))

def resample(p, step):
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    t = np.arange(0, seg[-1], step)
    return np.stack([np.interp(t, seg, p[:, 0]), np.interp(t, seg, p[:, 1])], 1)

strands = []  # (points, shade, start distance along the tree)
def add_runs(q, a_dist):
    inside = wm_s[np.clip(q[:, 1].astype(int), 0, H - 1), np.clip(q[:, 0].astype(int), 0, W - 1)]
    runs, cur = [], []
    for pt, ok in zip(q, inside):
        if ok: cur.append(pt)
        elif cur: runs.append(cur); cur = []
    if cur: runs.append(cur)
    n = 0
    for r_ in runs:
        r_ = np.array(r_)
        if len(r_) < 4: continue
        shade = float(np.mean(dens[np.clip(r_[:, 1].astype(int), 0, H - 1), np.clip(r_[:, 0].astype(int), 0, W - 1)]))
        strands.append((r_, shade, a_dist)); n += 1
    return n

REPORT = []
for p, total, seq in paths:
    own = np.where(mult[seq] <= 1)[0]
    own_frac = (own[0] / len(seq)) if len(own) else 0.0      # where this branch leaves the shared trunk
    p = resample(smooth(p, 7 if len(p) > 60 else (4 if len(p) > 30 else 2)), 2.0)
    if len(p) < 3:
        REPORT.append((tuple(p[-1].astype(int)), 0)); continue
    p = resample(extend_to_border(p) if len(p) >= 6 else p, 2.0)
    d = np.gradient(p, axis=0); d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    xi = np.clip(p[:, 0].astype(int), 0, W - 1); yi = np.clip(p[:, 1].astype(int), 0, H - 1)
    half = ndi.gaussian_filter1d(np.maximum(dt[yi, xi], 2.0), 3) * 1.08
    # where the branch bends sharply, keep the strands close to the axis (no kinks or loops)
    dd = np.gradient(d, axis=0)
    curv = ndi.gaussian_filter1d(np.abs(d[:, 0] * dd[:, 1] - d[:, 1] * dd[:, 0]) / 2.0, 3)
    half = half * np.clip(1.0 / (1.0 + 1.0 * curv * half), 0.65, 1.0)
    L = len(p)
    o0 = int(own_frac * L)
    n_str = int(np.clip(np.mean(half[o0:] if o0 < L - 2 else half) * 5.0, 14, 110))
    added = 0
    for k in range(n_str):
        s0 = rng.uniform(-1, 1)
        wob = s0 + 0.05 * np.sin(np.linspace(0, rng.uniform(2, 7), L) + rng.uniform(0, 6))
        q = p + nrm * (wob * half)[:, None]
        # most strands start where the branch leaves the trunk; some reach back into it
        if rng.random() < 0.45:
            a = int(rng.uniform(0, max(o0, 1)))
        else:
            a = int(o0 + rng.uniform(-0.1, 0.4) * max(L - o0, 1))
        a = int(np.clip(a, 0, max(L - 4, 0)))
        b = L - int(rng.uniform(0, 0.12) * L * (rng.random() < 0.35))
        added += add_runs(q[a:b], a * 2.0)
    REPORT.append((tuple(p[-1].astype(int)), added))

# guided projection bundle
gp = None
def catmull(P, n=160):
    P = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out = []
    for i in range(len(P) - 3):
        p0, p1, p2, p3 = P[i:i + 4]
        for t in np.linspace(0, 1, n // (len(P) - 3), endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2]); return np.array(out)
gp = resample(catmull(GUIDE), 2.0)
gd = np.gradient(gp, axis=0); gd /= np.linalg.norm(gd, axis=1, keepdims=True)
gn = np.stack([-gd[:, 1], gd[:, 0]], 1)
Lg = len(gp)
fan = np.linspace(0, 1, Lg)
for k in range(260):
    off = rng.uniform(-1, 1)
    width = 18 + 70 * fan ** 0.9          # narrow at the top, a wide sheet at the bottom
    q = gp + gn * ((off + 0.05 * np.sin(np.linspace(0, 5, Lg) + k)) * width)[:, None]
    a = int(rng.uniform(0, 0.6) * Lg)
    q = q[a:]
    add_runs(np.array([pt for r_ in runs for pt in r_]) if False else q, (a + 60) * 2.0)

print("paths", len(paths), "strands", len(strands)); print(sorted(REPORT, key=lambda r: r[1])[:14])

# ---------------- SVG -------------------------------------------------------
def fmt(p): return "M" + " ".join(f"{x:.0f} {y:.0f}" for x, y in p[::2])
shs = np.array([s for _, s, _ in strands]); lo, hi = np.percentile(shs, 5), np.percentile(shs, 95)
maxd = max(a for _, _, a in strands) + 1
parts = []
for q, sh, a in strands:
    t = 0.35 + 0.65 * np.clip((sh - lo) / (hi - lo + 1e-6), 0, 1)
    r, gg, b = (np.array([120, 144, 182]) * (1 - t) + np.array([24, 38, 66]) * t).astype(int)
    d = 1.4 + (a / maxd) * 3.6 + rng.uniform(0, 0.8)
    parts.append((d, f'<path d="{fmt(q)}" stroke="rgb({r},{gg},{b})" stroke-opacity="{0.4 + 0.5 * t:.2f}" '
                     f'stroke-width="{0.3 + 0.45 * rng.random():.2f}" data-delay="{d:.2f}" data-dur="{2.2 + rng.uniform(0, 1.2):.2f}"/>'))
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

if DEBUG:
    rgb = np.stack([g * 255] * 3, -1).astype(np.uint8)
    rgb[wm_s] = (rgb[wm_s] * 0.6 + np.array([120, 160, 230]) * 0.4).astype(np.uint8)
    rgb[ndi.binary_dilation(sk)] = [220, 30, 30]
    Image.fromarray(rgb).save(DEBUG)
