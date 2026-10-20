"""Draw coronal slices of a T1 volume in the style of Dejerine's plates (Anatomie des centres nerveux,
drawings by H. Gillet, Weigert myelin stain): light cortex with stippling that thickens towards the
white matter, dark white matter made of fine streaks that follow the fibres along each gyral blade,
thin ink contours along every gyrus, sulcus and ventricle.

usage: python3 dejerine_render.py <T1.nii.gz> <out folder> --at 0.195,0.385   (fractions front->back)
       python3 dejerine_render.py <T1.nii.gz> assets/atlas/sections --web coronal,axial,sagittal --index coronal,axial,sagittal --trk wb.trk --fa FA.nii.gz
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
        self.lo = np.minimum(self.a, self.b); self.hi = np.maximum(self.a, self.b)

    def slab(self, w0, half=0.65, axis=1):
        """segments clipped to the slab |coord[axis] - w0| < half (world mm)"""
        i = np.where((self.lo[:, axis] < w0 + half) & (self.hi[:, axis] > w0 - half))[0]
        a, b = self.a[i], self.b[i]
        dy = b[:, axis] - a[:, axis]
        with np.errstate(divide="ignore", invalid="ignore"):
            t0 = np.where(np.abs(dy) > 1e-6, (w0 - half - a[:, axis]) / dy, -np.inf)
            t1 = np.where(np.abs(dy) > 1e-6, (w0 + half - a[:, axis]) / dy, np.inf)
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
    wgt = np.repeat(np.maximum(L, 1.0) / n, n)          # a crossing fibre leaves a dot as dark and as wide as a line
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

def draw(t1s, ms, seed=0, fib=None, return_alpha=False, with_base=False):
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
    base_ink = np.clip(np.maximum(wash, ctx), 0, 1)
    ink = np.clip(np.maximum(base_ink, fibink), 0, 1)
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
    hull = cv2.convexHull(np.concatenate(cg)) if cg else None
    cs2 = [c for c in cs2 if cv2.arcLength(c, True) > UP * 9 and hull is not None and
           np.min(dsurf[np.clip(c[:, 0, 1], 0, tis.shape[0] - 1), np.clip(c[:, 0, 0], 0, tis.shape[1] - 1)]) > 0 and
           cv2.pointPolygonTest(hull, tuple(map(float, c[0, 0])), True) > UP * 4]
    cv2.drawContours(canvas, cs2, -1, 170, 1, cv2.LINE_AA)            # ventricles only
    tisd = cv2.dilate(tis, np.ones((3, 3), np.uint8)).astype(np.float32)
    alpha = cv2.GaussianBlur(tisd, (0, 0), 0.6)                  # tissue: grey and white matter only
    csfb = cv2.GaussianBlur(csf.astype(np.float32), (0, 0), 1.0)
    def finish(x):
        x = np.maximum(x, canvas.astype(np.float32) / 255 * 0.92)
        x = x * (1 - csfb * 0.9)                                  # the CSF itself stays paper-white
        x = np.maximum(x, canvas.astype(np.float32) / 255 * 0.92)
        return np.clip(x * alpha, 0, 1)
    out = [finish(ink)]
    if with_base: out.append(finish(base_ink))
    if return_alpha: out.append(np.clip(alpha, 0, 1))
    return out[0] if len(out) == 1 else tuple(out)

def plate(ink, paper=(247, 247, 245), inkc=(30, 31, 24), alpha=None):
    a = ink[..., None]
    rgb = (np.array(paper)[None, None] * (1 - a) + np.array(inkc)[None, None] * a).astype(np.uint8)
    return Image.fromarray(rgb)

TR = None
FA = None
MAPS_ONLY = "--maps-only" in sys.argv          # only re-make the T1 and FA images

# plane: normal axis, in-plane axes (columns, rows; both drawn reversed), order of the slider, labels
PLANES = {
    "coronal":  {"axis": 1, "cols": 0, "rows": 2, "reverse": True,  "labels": ["Front", "Back"]},
    "axial":    {"axis": 2, "cols": 0, "rows": 1, "reverse": False, "labels": ["Bottom", "Top"]},
    "sagittal": {"axis": 0, "cols": 1, "rows": 2, "reverse": True,  "labels": ["Right", "Left"]},
}

def cut(vol, P, j):
    """2D section: rows = reversed 'rows' axis (top/anterior first), columns = reversed 'cols' axis"""
    sl = [slice(None)] * 3; sl[P["axis"]] = j
    a = vol[tuple(sl)]                                         # remaining axes in increasing order
    ax = [d for d in range(3) if d != P["axis"]]
    if ax.index(P["cols"]) == 0: a = a.T                       # -> (rows axis, cols axis)
    return np.ascontiguousarray(a[::-1, ::-1])

def fibres_plane(tr, P, j, shape_vox, c0, r0, shape, aff, half=0.65):
    w0 = aff[P["axis"], P["axis"]] * j + aff[P["axis"], 3]
    pa, pb = tr.slab(w0, half, P["axis"])
    def px(p):
        ic = (p[:, P["cols"]] - aff[P["cols"], 3]) / aff[P["cols"], P["cols"]]
        ir = (p[:, P["rows"]] - aff[P["rows"], 3]) / aff[P["rows"], P["rows"]]
        c = (shape_vox[P["cols"]] - 1 - ic) - c0; r = (shape_vox[P["rows"]] - 1 - ir) - r0
        return np.stack([(c + 0.5) * UP - 0.5, (r + 0.5) * UP - 0.5], 1)
    return splat(shape, px(pa), px(pb))

def web_plane(name, t1, m, aff, out, width=640):
    P = PLANES[name]; od = os.path.join(out, name)
    for sub in ("", "t1", "fa", "base"): os.makedirs(os.path.join(od, sub), exist_ok=True)
    sh = m.shape
    other = tuple(d for d in range(3) if d != P["axis"])
    idx = np.where(m.any(other))[0]
    js = list(range(idx.max(), idx.min() - 1, -1)) if P["reverse"] else list(range(idx.min(), idx.max() + 1))
    cc = np.where(m.any(tuple(d for d in range(3) if d != P["cols"])))[0]
    rr = np.where(m.any(tuple(d for d in range(3) if d != P["rows"])))[0]
    c0, c1 = max(sh[P["cols"]] - 1 - cc.max() - 3, 0), min(sh[P["cols"]] - 1 - cc.min() + 4, sh[P["cols"]])
    r0, r1 = max(sh[P["rows"]] - 1 - rr.max() - 3, 0), min(sh[P["rows"]] - 1 - rr.min() + 4, sh[P["rows"]])
    sw = width // 2
    for k, j in enumerate(js):
        sec = cut(t1, P, j)[r0:r1, c0:c1]; msk = cut(m, P, j)[r0:r1, c0:c1]
        fname = f"s{k:03d}.webp"
        if not MAPS_ONLY:
            fib = fibres_plane(TR, P, j, sh, c0, r0, (sec.shape[0] * UP, sec.shape[1] * UP), aff) if TR else None
            ink, base, alpha = draw(sec, msk, seed=j, fib=fib, return_alpha=True, with_base=True)
            h = int(round(ink.shape[0] * width / ink.shape[1]))
            for sub, x, q in (("", ink, 74), ("base", base, 74)):
                la = np.stack([(x * 255).astype(np.uint8), (alpha * 255).astype(np.uint8)], -1)
                Image.fromarray(la, "LA").resize((width, h), Image.LANCZOS).save(os.path.join(od, sub, fname), quality=q, method=6)
        hs = int(round(sec.shape[0] * sw / sec.shape[1]))
        mk = cv2.resize(cv2.GaussianBlur(msk.astype(np.float32), (0, 0), 0.8), (sw, hs), interpolation=cv2.INTER_CUBIC)
        mk = smoothstep(0.35, 0.65, mk)
        for sub, img, lo, hi in (("t1", sec, 0.15, 1.15), ("fa", cut(FA, P, j)[r0:r1, c0:c1] if FA is not None else None, 0.0, 0.85)):
            if img is None: continue
            v = cv2.resize(np.clip((img - lo) / (hi - lo), 0, 1), (sw, hs), interpolation=cv2.INTER_CUBIC)
            la = np.stack([(np.clip(v, 0, 1) * 255).astype(np.uint8), (np.clip(mk, 0, 1) * 255).astype(np.uint8)], -1)
            Image.fromarray(la, "LA").save(os.path.join(od, sub, fname), quality=82, method=6)
        print(name, k, j, flush=True)
    vx = [aff[d, d] for d in range(3)]
    def world(d, i): return float(aff[d, d] * i + aff[d, 3])
    O = [0.0, 0.0, 0.0]; U = [0.0, 0.0, 0.0]; V = [0.0, 0.0, 0.0]
    O[P["cols"]] = world(P["cols"], sh[P["cols"]] - 1 - c0 + 0.5); U[P["cols"]] = -(c1 - c0) * vx[P["cols"]]
    O[P["rows"]] = world(P["rows"], sh[P["rows"]] - 1 - r0 + 0.5); V[P["rows"]] = -(r1 - r0) * vx[P["rows"]]
    meta = {"n": len(js), "axis": P["axis"], "labels": P["labels"], "w": width, "aspect": (r1 - r0) / (c1 - c0),
            "pos": [world(P["axis"], j) for j in js], "O": O, "U": U, "V": V,
            "modes": {"dejerine": "", "base": "base/", "t1": "t1/", "fa": "fa/" if FA is not None else None}}
    json.dump(meta, open(os.path.join(od, "plane.json"), "w"), indent=1)

def web_index(m, aff, out, planes):
    xs, ys, zs = [np.where(m.any(tuple(d for d in range(3) if d != a)))[0] for a in range(3)]
    def w(d, i): return float(aff[d, d] * i + aff[d, 3])
    meta = {"planes": planes, "space": "HCP 102109 DTI (1.25 mm)",
            "brain_box": [[w(0, xs.min()), w(1, ys.min()), w(2, zs.min())], [w(0, xs.max()), w(1, ys.max()), w(2, zs.max())]],
            "style": "Dejerine (Weigert stain) drawings from the T1 and the whole-brain tractogram: tools/sections/dejerine_render.py",
            "note": "world = RAS mm of the DTI space; atlas tracts in the same space align exactly"}
    json.dump(meta, open(os.path.join(out, "sections.json"), "w"), indent=1)

if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    t1, m, vox = load(src)
    KEEP = float(sys.argv[sys.argv.index("--keep") + 1]) if "--keep" in sys.argv else 0.15
    TR = Tracts(sys.argv[sys.argv.index("--trk") + 1], keep=KEEP) if "--trk" in sys.argv else None
    if "--fa" in sys.argv:
        FA = np.clip(np.asarray(nib.as_closest_canonical(nib.load(sys.argv[sys.argv.index("--fa") + 1])).dataobj, dtype=np.float32), 0, 1)
    if "--web" in sys.argv:
        aff = nib.as_closest_canonical(nib.load(src)).affine
        planes = sys.argv[sys.argv.index("--web") + 1].split(",")
        for pl in planes: web_plane(pl, t1, m, aff, out)
        if "--index" in sys.argv: web_index(m, aff, out, sys.argv[sys.argv.index("--index") + 1].split(","))
        sys.exit()
    ys = np.where(m.any((0, 2)))[0]
    front, back = ys.max(), ys.min()
    if "--at" in sys.argv:
        fr = [float(x) for x in sys.argv[sys.argv.index("--at") + 1].split(",")]
        js = [int(round(front - f * (front - back))) for f in fr]
    else:
        e = int(sys.argv[sys.argv.index("--every") + 1]); js = list(range(front, back - 1, -e))
    for k, j in enumerate(js):
        sec = coronal(t1, j)
        aff = nib.as_closest_canonical(nib.load(src)).affine
        fib = fibres_plane(TR, PLANES["coronal"], j, m.shape, 0, 0, (sec.shape[0] * UP, sec.shape[1] * UP), aff) if TR else None
        ink, al = draw(sec, coronal(m, j), seed=j, fib=fib, return_alpha=True)
        plate(ink, alpha=al).save(os.path.join(out, f"plate-{k:03d}.png"))
        print(k, j, ink.shape, flush=True)
