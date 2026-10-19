"""Draw coronal slices of a T1 volume in the style of Dejerine's plates (Anatomie des centres nerveux,
drawings by H. Gillet, Weigert myelin stain): light cortex with stippling that thickens towards the
white matter, dark white matter made of fine streaks that follow the fibres along each gyral blade,
thin ink contours along every gyrus, sulcus and ventricle.

usage: python3 dejerine_render.py <T1.nii.gz> <out folder> --at 0.195,0.385   (fractions front->back)
       python3 dejerine_render.py <T1.nii.gz> assets/atlas/drawings --web 3      (series for the atlas)
       add  --trk whole_brain.trk  to draw the white matter from the real streamlines of the same brain
       python3 dejerine_render.py <T1.nii.gz> <out folder> --every 3            (every 3rd slice)
"""
import sys, os, json
import numpy as np, cv2, nibabel as nib
from scipy import ndimage as ndi
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from pack_nifti import brain_mask

UP = 6                       # 1.25 mm voxels -> ~0.21 mm pixels
CTX_BASE, CTX_DEEP = 0.09, 0.50   # grey tone of the cortex (outer, extra in the deep layers)
FIB_GAIN = 0.75              # ink left by each streamline (higher = darker white matter)

class Tracts:
    """streamline segments of a whole-brain tractogram (same grid as the T1), for drawing the sections"""
    def __init__(self, trk, keep=1.0, seed=0):
        t = nib.streamlines.load(trk)
        sl = t.streamlines
        pts = sl.get_data().astype(np.float32)
        off, ln = sl._offsets, sl._lengths
        if keep < 1:
            sel = np.random.default_rng(seed).random(len(ln)) < keep
        else:
            sel = np.ones(len(ln), bool)
        last = np.zeros(len(pts), bool); last[(off + ln - 1)] = True     # no segment between two streamlines
        own = np.repeat(sel, ln)
        ok = ~last[:-1] & own[:-1]
        self.a = pts[:-1][ok]; self.b = pts[1:][ok]
        self.ymin = np.minimum(self.a[:, 1], self.b[:, 1]); self.ymax = np.maximum(self.a[:, 1], self.b[:, 1])

    def slab(self, y0, half=0.65):
        """segments clipped to the slab |y - y0| < half (world mm)"""
        i = np.where((self.ymin < y0 + half) & (self.ymax > y0 - half))[0]
        a, b = self.a[i], self.b[i]
        dy = b[:, 1] - a[:, 1]
        with np.errstate(divide="ignore", invalid="ignore"):
            t0 = np.where(np.abs(dy) > 1e-6, (y0 - half - a[:, 1]) / dy, -np.inf)
            t1 = np.where(np.abs(dy) > 1e-6, (y0 + half - a[:, 1]) / dy, np.inf)
        lo = np.clip(np.minimum(t0, t1), 0, 1); hi = np.clip(np.maximum(t0, t1), 0, 1)
        d = b - a
        return a + d * lo[:, None], a + d * hi[:, None]

def splat(shape, pa, pb, step=0.35):
    """accumulate line segments (pixel coords, columns/rows) into a density image"""
    h, w = shape
    L = np.hypot(pb[:, 0] - pa[:, 0], pb[:, 1] - pa[:, 1])
    n = np.maximum(1, np.ceil(L / step)).astype(int)
    idx = np.repeat(np.arange(len(L)), n)
    k = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
    f = (k + 0.5) / np.repeat(n, n)
    x = pa[idx, 0] + (pb[idx, 0] - pa[idx, 0]) * f
    y = pa[idx, 1] + (pb[idx, 1] - pa[idx, 1]) * f
    wgt = np.repeat(np.where(L < 1.0, 1.6, L / n) if False else np.maximum(L, 1.6) / n, n)  # a crossing fibre leaves a dot
    acc = np.zeros(shape, np.float32)
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int); fx = x - x0; fy = y - y0
    for dx, dy, ww in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)), (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
        xx, yy = x0 + dx, y0 + dy
        ok = (xx >= 0) & (yy >= 0) & (xx < w) & (yy < h)
        np.add.at(acc, (yy[ok], xx[ok]), (wgt * ww)[ok])
    return acc

def fibres(tr, j, X, Z, c0=0, r0=0, shape=None, half=0.65):
    """density image (upsampled section pixels) of the streamline segments within the slab of coronal slice j"""
    y0 = 1.25 * j + 1.297                                      # world y of the T1 slice (affine of the T1)
    pa, pb = tr.slab(y0, half)
    def px(p):
        i = p[:, 0] / 1.25 - 1; k = p[:, 2] / 1.25 - 1          # voxel indices (affine of the tractogram)
        c = (X - 1 - i) - c0; r = (Z - 1 - k) - r0
        return np.stack([(c + 0.5) * UP - 0.5, (r + 0.5) * UP - 0.5], 1)
    return splat(shape, px(pa), px(pb))

def load(src):
    img = nib.as_closest_canonical(nib.load(src))
    vox = img.header.get_zooms()[:3]
    t1 = np.clip(np.asarray(img.dataobj, dtype=np.float32), 0, None)
    t1 /= np.percentile(t1[t1 > np.percentile(t1, 50)], 85)
    return t1, brain_mask(t1, vox), vox

def coronal(vol, j):
    return np.ascontiguousarray(vol[:, j, :][::-1, ::-1].T)     # rows top->bottom, columns subject right->left

def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)

def lic(noise, vx, vy, L=14):
    """line integral convolution of a noise image along an orientation field (sign-free)."""
    h, w = noise.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    acc = noise.copy(); wsum = np.ones_like(noise)
    for sgn in (1, -1):
        px, py = xx.copy(), yy.copy()
        dx0, dy0 = vx * sgn, vy * sgn
        for k in range(1, L + 1):
            dx = ndi.map_coordinates(vx, [py, px], order=1, mode="nearest")
            dy = ndi.map_coordinates(vy, [py, px], order=1, mode="nearest")
            flip = np.where(dx * dx0 + dy * dy0 < 0, -1.0, 1.0)      # keep going the same way
            dx, dy = dx * flip, dy * flip
            px += dx; py += dy; dx0, dy0 = dx, dy
            wk = np.exp(-(k / L) ** 2 * 2)
            acc += wk * ndi.map_coordinates(noise, [py, px], order=1, mode="nearest"); wsum += wk
    return acc / wsum

def draw(t1s, ms, seed=0, fib=None, return_alpha=False):
    """fib: density of the real streamline segments crossing this section (upsampled pixel grid)"""
    rng = np.random.default_rng(seed)
    # upsample smoothly (no voxel blocks)
    t = cv2.resize(t1s, None, fx=UP, fy=UP, interpolation=cv2.INTER_CUBIC)
    t = cv2.GaussianBlur(t, (0, 0), UP * 0.45)
    m = cv2.GaussianBlur(cv2.resize(ms.astype(np.float32), None, fx=UP, fy=UP, interpolation=cv2.INTER_LINEAR), (0, 0), UP * 0.5) > 0.5
    n = np.clip((t - 0.30) / 0.80, 0, 1) * m                   # grey ~0.47, white ~0.88
    wm = smoothstep(0.60, 0.80, n)
    mmpx = 1.25 / UP                                                # mm per pixel
    core = smoothstep(0.50, 0.90, n)                                # myelin content from T1
    dwm = ndi.distance_transform_edt(wm < 0.5).astype(np.float32) * mmpx     # mm outside the white matter
    gm = smoothstep(0.30, 0.42, n) * (wm < 0.5)
    # ---- the fibres: real streamlines of this brain crossing the section (lines in plane, dots across it)
    if fib is not None:
        fl = cv2.GaussianBlur(fib, (0, 0), 0.30)
        fibink = 0.88 * (1.0 - np.exp(-fl * FIB_GAIN))            # each line stays a line: little build-up
    else:
        fibink = np.zeros_like(n)
    # light wash of the stain under the fibres (white matter and deep nuclei), and the cortex band
    # cortex as in the plates: a grey stippled band, darker in the deep layers (radial fibres),
    # paler towards the surface (molecular layer)
    gm2 = smoothstep(0.30, 0.42, n) * (wm < 0.5)
    deep = np.exp(-dwm / 0.8)
    tone = (CTX_BASE + CTX_DEEP * deep) * gm2
    tone = cv2.GaussianBlur(tone, (0, 0), 1.2)
    dots = (rng.random(n.shape) < 0.10 * deep * gm2).astype(np.float32)
    dots = np.clip(cv2.GaussianBlur(dots, (0, 0), 0.4) * 3.0, 0, 1)
    ctx = np.clip(np.maximum(tone, dots * 0.7), 0, 1) * gm2
    wash = 0.08 * core
    ink = np.clip(np.maximum(np.maximum(wash, ctx), fibink), 0, 1)
    tone_gm = (0.70 * np.exp(-dwm / 1.0) + 0.05) * gm
    # stipple in the cortex where the tone fades
    ink = np.clip(ink, 0, 1)
    # ---- contours: brain outline and the CSF of sulci and ventricles, as clean thin lines
    canvas = np.zeros(t.shape, np.uint8)
    sm = (cv2.GaussianBlur(m.astype(np.float32), (0, 0), UP * 0.3) > 0.5).astype(np.uint8)
    cs, _ = cv2.findContours(sm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    tis = ((cv2.GaussianBlur(n, (0, 0), UP * 0.18) > 0.33) & (sm > 0)).astype(np.uint8)
    tis = cv2.morphologyEx(tis, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cg, _ = cv2.findContours(tis, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    cg = [c for c in cg if cv2.arcLength(c, True) > UP * 12]
    cv2.drawContours(canvas, cg, -1, 140, 1, cv2.LINE_AA)            # outline of the gyri: border between tissue and CSF
    csf = ((cv2.GaussianBlur(n, (0, 0), UP * 0.35) < 0.16) & (cv2.erode(sm, np.ones((5, 5), np.uint8)) > 0)).astype(np.uint8)
    cs2, _ = cv2.findContours(csf, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    dsurf = ndi.distance_transform_edt(tis > 0) * (1.25 / UP)
    cs2 = [c for c in cs2 if cv2.arcLength(c, True) > UP * 9 and
           np.min(dsurf[np.clip(c[:, 0, 1], 0, tis.shape[0] - 1), np.clip(c[:, 0, 0], 0, tis.shape[1] - 1)]) > 0 and
           cv2.pointPolygonTest(cv2.convexHull(np.concatenate(cg)) if cg else c, tuple(map(float, c[0, 0])), True) > UP * 4]
    cv2.drawContours(canvas, cs2, -1, 170, 1, cv2.LINE_AA)            # ventricles only
    # sulci: midline of the cortex between two white matter blades (skeleton of brain minus white matter)
    from skimage.morphology import skeletonize, remove_small_objects
    ctx = (cv2.erode(sm, np.ones((3, 3), np.uint8)) > 0) & (wm < 0.5)
    sk = skeletonize(ctx)
    dsk = ndi.distance_transform_edt(wm < 0.5) * mmpx                     # distance from the white matter
    dout = ndi.distance_transform_edt(sm > 0) * mmpx                      # distance from the brain surface
    sk &= (dsk > 1.3) & (dsk < 5.0) & (dout > 0.6)
    nb = cv2.GaussianBlur(n, (0, 0), UP * 0.25)
    lab, nl = ndi.label(sk, structure=np.ones((3, 3)))
    keep = np.zeros(nl + 1, bool)
    if nl:
        mean_n = ndi.mean(nb, lab, index=np.arange(1, nl + 1))
        size = ndi.sum(sk, lab, index=np.arange(1, nl + 1))
        touch = ndi.minimum(dout, lab, index=np.arange(1, nl + 1))
        keep[1:] = (size > UP * 4) & (mean_n < 0.50) & (touch < 3.0)     # darker (CSF) and open to the surface
    sk = keep[lab]
    skl = cv2.GaussianBlur(sk.astype(np.float32), (0, 0), 0.6) * 1.8
    ink = np.maximum(ink, canvas.astype(np.float32) / 255 * 0.92)
    # the CSF itself stays paper-white
    ink *= 1 - cv2.GaussianBlur(csf.astype(np.float32), (0, 0), 1.0) * 0.9
    ink = np.maximum(ink, canvas.astype(np.float32) / 255 * 0.92)
    tisd = cv2.dilate(tis, np.ones((3, 3), np.uint8)).astype(np.float32)
    alpha = cv2.GaussianBlur(tisd, (0, 0), 0.6)                  # tissue: grey and white matter only
    ink *= alpha
    if return_alpha: return np.clip(ink, 0, 1), np.clip(alpha, 0, 1)
    return np.clip(ink, 0, 1)

def plate(ink, paper=(247, 247, 245), inkc=(30, 31, 24), alpha=None):
    a = ink[..., None]
    rgb = (np.array(paper)[None, None] * (1 - a) + np.array(inkc)[None, None] * a).astype(np.uint8)
    return Image.fromarray(rgb)

TR = None
FA = None
MAPS_ONLY = "--maps-only" in sys.argv          # only re-make the T1 and FA images

def web_series(t1, m, out, every=1, width=640):
    """all coronal slices (front -> back, every N), same crop, ink as grayscale WebP + slices.json for atlas.js"""
    os.makedirs(out, exist_ok=True)
    ys = np.where(m.any((0, 2)))[0]
    js = list(range(ys.max(), ys.min() - 1, -every))
    xs = np.where(m.any((1, 2)))[0]; zs = np.where(m.any((0, 1)))[0]
    # crop in the coronal image (columns = x reversed, rows = z reversed), with a margin of 3 voxels
    c0, c1 = m.shape[0] - 1 - xs.max() - 3, m.shape[0] - 1 - xs.min() + 4
    r0, r1 = m.shape[2] - 1 - zs.max() - 3, m.shape[2] - 1 - zs.min() + 4
    c0, r0 = max(c0, 0), max(r0, 0)
    names = []
    for sub in ("t1", "fa"): os.makedirs(os.path.join(out, sub), exist_ok=True)
    sw = width // 2                                          # T1 and FA: their own resolution is ~1.25 mm
    for k, j in enumerate(js):
        sec = coronal(t1, j)[r0:r1, c0:c1]; msk = coronal(m, j)[r0:r1, c0:c1]
        fib = fibres(TR, j, m.shape[0], m.shape[2], c0, r0, (sec.shape[0] * UP, sec.shape[1] * UP)) if TR else None
        if MAPS_ONLY: ink = alpha = np.zeros((sec.shape[0] * UP, sec.shape[1] * UP), np.float32)
        else: ink, alpha = draw(sec, msk, seed=j, fib=fib, return_alpha=True)
        h = int(round(ink.shape[0] * width / ink.shape[1]))
        la = np.stack([(ink * 255).astype(np.uint8), (alpha * 255).astype(np.uint8)], -1)
        im = Image.fromarray(la, "LA").resize((width, h), Image.LANCZOS)
        name = f"s{k:03d}.webp"
        if not MAPS_ONLY: im.save(os.path.join(out, name), quality=76, method=6)
        # T1 and FA of the same slice, brain only (transparent outside the brain)
        hs = int(round(sec.shape[0] * sw / sec.shape[1]))
        mk = cv2.resize(cv2.GaussianBlur(msk.astype(np.float32), (0, 0), 0.8), (sw, hs), interpolation=cv2.INTER_CUBIC)
        mk = smoothstep(0.35, 0.65, mk)                     # smooth outline instead of voxel steps
        for sub, img, lo, hi in (("t1", sec, 0.15, 1.15), ("fa", coronal(FA, j)[r0:r1, c0:c1] if FA is not None else None, 0.0, 0.85)):
            if img is None: continue
            v = cv2.resize(np.clip((img - lo) / (hi - lo), 0, 1), (sw, hs), interpolation=cv2.INTER_CUBIC)
            la = np.stack([(np.clip(v, 0, 1) * 255).astype(np.uint8), (np.clip(mk, 0, 1) * 255).astype(np.uint8)], -1)
            Image.fromarray(la, "LA").save(os.path.join(out, sub, name), quality=82, method=6)
        names.append(name); print(k, j, flush=True)
    vox = 1.25
    px = (c1 - c0) * vox / width
    cx = ((m.shape[0] - 1 - (xs.min() + xs.max()) / 2) - c0) * vox / px    # column of the brain centre
    meta = {"n": len(names), "files": names, "w": width, "h": h, "px_mm": px, "slice_mm": every * vox,
            "brain": {"center_px": [cx, 0.0], "top_row": (m.shape[2] - 1 - zs.max() - r0) * vox / px,
                      "length_mm": (ys.max() - ys.min() + 1) * vox},
            "style": "Dejerine (Weigert stain) drawing of the T1, tools/sections/dejerine_render.py",
            "modes": {"dejerine": "", "t1": "t1/", "fa": "fa/" if FA is not None else None},
            "note": "s000 = most anterior; image left = subject's right"}
    json.dump(meta, open(os.path.join(out, "drawings.json"), "w"), indent=1)

if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    t1, m, vox = load(src)
    KEEP = float(sys.argv[sys.argv.index("--keep") + 1]) if "--keep" in sys.argv else 0.15
    TR = Tracts(sys.argv[sys.argv.index("--trk") + 1], keep=KEEP) if "--trk" in sys.argv else None
    if "--fa" in sys.argv:
        FA = np.clip(np.asarray(nib.as_closest_canonical(nib.load(sys.argv[sys.argv.index("--fa") + 1])).dataobj, dtype=np.float32), 0, 1)
    if "--web" in sys.argv:
        web_series(t1, m, out, every=int(sys.argv[sys.argv.index("--web") + 1])); sys.exit()
    ys = np.where(m.any((0, 2)))[0]
    front, back = ys.max(), ys.min()
    if "--at" in sys.argv:
        fr = [float(x) for x in sys.argv[sys.argv.index("--at") + 1].split(",")]
        js = [int(round(front - f * (front - back))) for f in fr]
    else:
        e = int(sys.argv[sys.argv.index("--every") + 1]); js = list(range(front, back - 1, -e))
    for k, j in enumerate(js):
        sec = coronal(t1, j)
        fib = fibres(TR, j, m.shape[0], m.shape[2], 0, 0, (sec.shape[0] * UP, sec.shape[1] * UP)) if TR else None
        ink, al = draw(sec, coronal(m, j), seed=j, fib=fib, return_alpha=True)
        plate(ink, alpha=al).save(os.path.join(out, f"plate-{k:03d}.png"))
        print(k, j, ink.shape, flush=True)
