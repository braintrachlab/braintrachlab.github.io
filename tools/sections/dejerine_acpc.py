"""Sections of the atlas from the high-resolution data of the same subject (HCP 102109, AC-PC space, 0.7 mm):
T1w and T2w (brain), FreeSurfer wmparc (tissue classes), the whole-brain tractogram and FA (diffusion space).

Diffusion space -> AC-PC: acpc = dti_world - (91.25, 127.25, 73.25) mm   (found by registration, r = 0.975)

usage:
  python3 dejerine_acpc.py --t1 T1w_brain.nii.gz --t2 T2w_brain.nii.gz --parc wmparc.nii.gz \
      --trk wholebrain.trk --fa FA.nii.gz --out assets/atlas/planes --web coronal,axial,sagittal [--index]
  python3 dejerine_acpc.py ... --preview out_dir --at coronal:0.3,axial:0.5
"""
import sys, os, json
import numpy as np, cv2, nibabel as nib
from scipy import ndimage as ndi
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from dejerine_render import Tracts, splat, smoothstep

DTI2ACPC = np.array([-91.25, -127.25, -73.25], np.float32)
UP = 3                        # 0.7 mm voxels -> 0.23 mm pixels
STEP = 2                      # one section every 2 voxels (1.4 mm)
FIB_GAIN = 0.75
WIDTH = 640

# FreeSurfer labels
VENT = {4, 5, 14, 15, 43, 44, 72, 24, 31, 63, 30, 62, 80, 85}           # ventricles, CSF, choroid plexus, vessels
CTX_EXTRA = {3, 42, 8, 47, 17, 53, 18, 54}                               # cortex, cerebellar cortex, hippocampus, amygdala
DEEP = {10, 11, 12, 13, 26, 28, 49, 50, 51, 52, 58, 60}                  # thalamus, caudate, putamen, pallidum, accumbens, ventral DC

def classes(p):
    p = p.astype(np.int32)
    tissue = (p > 0) & ~np.isin(p, list(VENT))
    ctx = np.isin(p, list(CTX_EXTRA)) | ((p >= 1000) & (p < 3000))
    deep = np.isin(p, list(DEEP))
    wm = tissue & ~ctx & ~deep                                           # white matter, brainstem, CC, cerebellar WM
    return tissue, ctx, deep, wm

PLANES = {
    "coronal":  {"axis": 1, "cols": 0, "rows": 2, "reverse": True,  "labels": ["Front", "Back"], "from": "from the frontal pole"},
    "axial":    {"axis": 2, "cols": 0, "rows": 1, "reverse": False, "labels": ["Bottom", "Top"], "from": "from the lowest point"},
    "sagittal": {"axis": 0, "cols": 1, "rows": 2, "reverse": True,  "labels": ["Right", "Left"], "from": "from the right surface"},
}

def to_ras(img):
    img = nib.as_closest_canonical(img)
    return np.asarray(img.dataobj), img.affine

def cut(vol, P, j):
    sl = [slice(None)] * 3; sl[P["axis"]] = j
    a = vol[tuple(sl)]
    ax = [d for d in range(3) if d != P["axis"]]
    if ax.index(P["cols"]) == 0: a = a.T
    return np.ascontiguousarray(a[::-1, ::-1])

def up_mask(m, sigma=0.25):
    """binary mask -> smooth upsampled mask (no voxel steps)"""
    f = cv2.resize(m.astype(np.float32), None, fx=UP, fy=UP, interpolation=cv2.INTER_LINEAR)
    return cv2.GaussianBlur(f, (0, 0), UP * sigma)

T2_CSF, T2_VESSEL = 600.0, 300.0      # T2: above = CSF (sulci, fissures), below (outside the parcellation) = vessels

LEFT = lambda p: ((p >= 1000) & (p < 2000)) | ((p >= 3000) & (p < 4000)) | (p == 5001) | ((p > 0) & (p < 40) & (p != 16) & (p != 24))
RIGHT = lambda p: ((p >= 2000) & (p < 3000)) | ((p >= 4000) & (p < 5000)) | (p == 5002) | ((p >= 40) & (p < 80))

# ---------------------------------------------------------------- cortical surfaces (pial / white, each hemisphere)
class Surface:
    def __init__(self, path):
        g = nib.load(path); self.v = g.darrays[0].data.astype(np.float64); self.f = g.darrays[1].data.astype(np.int64)
        self.fv = self.v[self.f]                                     # (n, 3 vertices, xyz)
        self.lo = self.fv.min(1); self.hi = self.fv.max(1)

    def cut(self, axis, w0):
        """segments where the plane coord[axis] = w0 crosses the triangles: (n, 2, 3) world points"""
        i = np.where((self.lo[:, axis] <= w0) & (self.hi[:, axis] > w0))[0]
        T = self.fv[i]; d = T[:, :, axis] - w0                       # signed distance of the 3 vertices
        pts = []
        for a, b in ((0, 1), (1, 2), (2, 0)):
            da, db = d[:, a], d[:, b]
            cross = (da > 0) != (db > 0)
            t = np.where(cross, da / np.where(cross, da - db, 1), 0)
            p = T[:, a] + (T[:, b] - T[:, a]) * t[:, None]
            pts.append((cross, p))
        seg = []
        for k in range(len(i)):
            q = [p[k] for c, p in pts if c[k]]
            if len(q) == 2: seg.append(q)
        return np.array(seg).reshape(-1, 2, 3)

def fill_segments(shape, segs_px):
    """inside of the closed contours given as segments (pixel x, y): even-odd scanline fill at pixel centres"""
    h, w = shape
    acc = np.zeros((h, w + 1), np.int32)
    if len(segs_px):
        x0, y0, x1, y1 = segs_px[:, 0, 0], segs_px[:, 0, 1], segs_px[:, 1, 0], segs_px[:, 1, 1]
        ya, yb = np.minimum(y0, y1), np.maximum(y0, y1)
        r0 = np.ceil(ya - 0.5).astype(int); r1 = np.ceil(yb - 0.5).astype(int)    # rows whose centre lies in [ya, yb)
        n = np.clip(r1 - r0, 0, None)
        idx = np.repeat(np.arange(len(n)), n)
        rows = np.repeat(r0, n) + (np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n))
        yc = rows + 0.5
        t = (yc - y0[idx]) / (y1[idx] - y0[idx])
        xc = x0[idx] + (x1[idx] - x0[idx]) * t
        col = np.clip(np.ceil(xc - 0.5).astype(int), 0, w)
        ok = (rows >= 0) & (rows < h)
        np.add.at(acc, (rows[ok], col[ok]), 1)
    return (np.cumsum(acc, 1)[:, :w] % 2) == 1

def surface_section(SURF, axis, w0, to_px, shape):
    """masks and contour segments of the two hemispheres on this section (upsampled pixel grid)"""
    out = {}
    for key, surf in SURF.items():
        seg = surf.cut(axis, w0)
        sp = to_px(seg.reshape(-1, 3)).reshape(-1, 2, 2) if len(seg) else np.zeros((0, 2, 2))
        out[key] = (fill_segments(shape, sp), sp)
    return out

def fine_tissue(tissue, t2s, ps):
    """brain border at the upsampled resolution: the parcellation says what is brain, the T2 where the CSF is.
    Sulci and fissures stay open; the two hemispheres never fuse."""
    t2u = cv2.resize(t2s, None, fx=UP, fy=UP, interpolation=cv2.INTER_CUBIC)
    core = cv2.resize(tissue.astype(np.float32), None, fx=UP, fy=UP, interpolation=cv2.INTER_LINEAR) > 0.5
    ring = cv2.resize(ndi.binary_dilation(tissue, iterations=1).astype(np.float32), None, fx=UP, fy=UP, interpolation=cv2.INTER_LINEAR) > 0.5
    tis = (core & (t2u < T2_CSF)) | (ring & (t2u >= T2_VESSEL) & (t2u < T2_CSF * 0.92))
    # hemispheres: a thin gap where left and right tissue meet (not through the corpus callosum or the midline)
    L = cv2.resize(LEFT(ps).astype(np.float32), None, fx=UP, fy=UP, interpolation=cv2.INTER_LINEAR)
    R = cv2.resize(RIGHT(ps).astype(np.float32), None, fx=UP, fy=UP, interpolation=cv2.INTER_LINEAR)
    seam = (L > 0.2) & (R > 0.2)
    tis &= ~cv2.dilate(seam.astype(np.uint8), np.ones((2, 2), np.uint8)).astype(bool)
    tis = cv2.morphologyEx(tis.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))).astype(bool)
    tis = cv2.medianBlur(tis.astype(np.uint8) * 255, 3) > 127           # clean edges without rounding the gyri
    return tis

# silver (cell-body) stain, tones per structure after BigBrain (full16 400 um, co-registered to this T2):
# grey matter dark, white matter pale (0 = black, 1 = paper)
SILVER = {"wm": 0.86, "ctx": 0.24, "cbctx": 0.17, "put": 0.19, "caud": 0.21, "acc": 0.22, "pall": 0.33, "thal": 0.42,
          "hipp": 0.27, "amyg": 0.22, "vdc": 0.50}
SILVER_LABELS = {"put": [12, 51], "caud": [11, 50], "acc": [26, 58], "pall": [13, 52], "thal": [10, 49], "hipp": [17, 53],
                 "amyg": [18, 54], "vdc": [28, 60], "cbctx": [8, 47]}

def silver(t1s, ps, tis, rng, ctx_m=None, wm_m=None):
    """silver-stain tone of one section (upsampled grid): continuous tone from the T1, structure tones from the parcellation"""
    t = cv2.GaussianBlur(cv2.resize(t1s, None, fx=UP, fy=UP, interpolation=cv2.INTER_CUBIC), (0, 0), UP * 0.35)
    v = t[tis]; lo, hi = (np.percentile(v, 2), np.percentile(v, 99)) if v.size else (0, 1)
    tn = np.clip((t - lo) / (hi - lo + 1e-6), 0, 1)
    tone = 0.18 + 0.72 * smoothstep(0.30, 0.80, tn)                   # T1: grey matter dark, white matter pale
    up = lambda m: cv2.GaussianBlur(cv2.resize(m.astype(np.float32), None, fx=UP, fy=UP, interpolation=cv2.INTER_LINEAR), (0, 0), UP * 0.6)
    ctx = up(((ps >= 1000) & (ps < 3000)) | np.isin(ps, [3, 42])) if ctx_m is None else cv2.GaussianBlur(ctx_m.astype(np.float32), (0, 0), 0.6)
    wmm = up(((ps >= 3000) & (ps < 5003)) | np.isin(ps, [2, 41, 7, 46, 16, 251, 252, 253, 254, 255, 85])) if wm_m is None else cv2.GaussianBlur(wm_m.astype(np.float32), (0, 0), 0.6)
    # cortex: uniformly dark, a thin pale molecular layer at the surface, slightly lighter towards the white matter
    dsurf = ndi.distance_transform_edt(tis).astype(np.float32) * (0.7 / UP)
    dwm = ndi.distance_transform_edt(wmm < 0.5).astype(np.float32) * (0.7 / UP)
    lam = SILVER["ctx"] + 0.30 * (1 - smoothstep(0.15, 0.45, dsurf)) + 0.10 * (1 - smoothstep(0.0, 0.6, dwm))
    tone = tone * (1 - 0.8 * ctx) + lam * 0.8 * ctx
    tone = tone * (1 - 0.6 * wmm) + (SILVER["wm"] - 0.10 + 0.14 * tn) * 0.6 * wmm
    for k, labs in SILVER_LABELS.items():
        mk = cv2.GaussianBlur(up(np.isin(ps, labs)), (0, 0), UP * 0.9) * 0.9     # nuclei: smooth outlines
        tone = tone * (1 - mk) + (SILVER[k] + 0.22 * (tn - 0.5)) * mk     # keep the texture of the T1 inside the nuclei
    grain = cv2.GaussianBlur(rng.normal(0, 1, t.shape).astype(np.float32), (0, 0), 0.7)
    tone += 0.035 * grain                                              # fine grain of the stained section
    return np.clip(tone, 0, 1)

NONCEREBRAL = [7, 8, 46, 47, 16, 28, 60, 10, 49, 11, 50, 12, 51, 13, 52, 26, 58, 17, 53, 18, 54, 251, 252, 253, 254, 255, 85]
VENT_FINE = [4, 5, 14, 15, 43, 44, 72, 24, 31, 63]

def draw(t1s, labs, fib, seed=0, t2s=None, ps=None, surf=None):
    """Dejerine (Weigert) drawing of one section. Returns ink (with fibres), ink (without), tissue alpha.
    surf: cut of the pial/white surfaces of both hemispheres (exact cortical border, hemispheres never fuse)"""
    rng = np.random.default_rng(seed)
    tissue, ctx, deep, wm = labs
    C = up_mask(ctx, 0.25); Dp = up_mask(deep, 0.25); W = up_mask(wm, 0.25)
    if surf is not None:
        upl = lambda m: cv2.resize(m.astype(np.float32), None, fx=UP, fy=UP, interpolation=cv2.INTER_LINEAR) > 0.5
        pial = surf["Lp"][0] | surf["Rp"][0]; white = surf["Lw"][0] | surf["Rw"][0]
        other = (cv2.GaussianBlur(cv2.resize(np.isin(ps, [7, 8, 46, 47, 16, 28, 60]).astype(np.float32), None, fx=UP, fy=UP, interpolation=cv2.INTER_LINEAR), (0, 0), UP * 0.6) > 0.5)   # cerebellum, brainstem, ventral DC
        upls = lambda m: cv2.GaussianBlur(cv2.resize(m.astype(np.float32), None, fx=UP, fy=UP, interpolation=cv2.INTER_LINEAR), (0, 0), UP * 0.7) > 0.5
        vent = upls(np.isin(ps, VENT_FINE))                              # ventricles: smooth outline
        tis = (pial | other) & ~vent
        tis = cv2.morphologyEx(tis.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)).astype(bool)
        cortex = pial & ~white & ~upl(np.isin(ps, NONCEREBRAL))
        C = np.maximum(cv2.GaussianBlur(cortex.astype(np.float32), (0, 0), 0.6), up_mask(np.isin(ps, [8, 47, 17, 53, 18, 54]), 0.25))
        W = np.where(white | other, np.maximum(W, (white & ~upl(np.isin(ps, NONCEREBRAL))).astype(np.float32)), 0)
    else:
        tis = fine_tissue(tissue, t2s, ps) if t2s is not None else (smoothstep(0.42, 0.58, up_mask(tissue)) > 0.5)
    alpha = cv2.GaussianBlur(tis.astype(np.float32), (0, 0), 0.5)
    wmb = (W > 0.5) & tis
    # sulci: where the cortex of two gyri touch, the line equidistant from their white matter blades
    # (skeleton of the space outside the white matter, inside the tissue): a fine line, and a cut between the gyri
    from skimage.morphology import skeletonize
    dw = ndi.distance_transform_edt(~wmb) * (0.7 / UP)
    sk = (skeletonize(~wmb) if surf is None else np.zeros_like(wmb)) & tis & (dw > 0.9) & (dw < 4.0) & (cv2.dilate((C > 0.4).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0)
    lab, nl = ndi.label(sk, structure=np.ones((3, 3)))
    if nl:
        size = ndi.sum(sk, lab, index=np.arange(1, nl + 1))
        sk = np.concatenate([[False], size > UP * 4])[lab]
    sulc = cv2.GaussianBlur(sk.astype(np.float32), (0, 0), 0.55)
    tis = tis & ~(sk & (dw > 1.2))                                     # the two banks do not fuse
    alpha = cv2.GaussianBlur(tis.astype(np.float32), (0, 0), 0.5)
    mmpx = 0.7 / UP
    dwm = ndi.distance_transform_edt(~wmb).astype(np.float32) * mmpx       # mm from the white matter
    # myelin from the T1 (smooth), for a light wash under the fibres
    t = cv2.GaussianBlur(cv2.resize(t1s, None, fx=UP, fy=UP, interpolation=cv2.INTER_CUBIC), (0, 0), UP * 0.5)
    vals = t[tis]; lo, hi = (np.percentile(vals, 5), np.percentile(vals, 98)) if vals.size else (0, 1)
    n = np.clip((t - lo) / (hi - lo + 1e-6), 0, 1)
    # cortex: pale at the surface, darker in the deep layers, fine stipple near the white matter
    cm = np.clip(C, 0, 1) * tis
    deepl = np.exp(-dwm / 0.9)
    tone_c = (0.08 + 0.42 * deepl) * cm
    tone_c = cv2.GaussianBlur(tone_c, (0, 0), 1.0)
    dots = (rng.random(t.shape) < 0.09 * deepl * cm).astype(np.float32)
    dots = np.clip(cv2.GaussianBlur(dots, (0, 0), 0.4) * 3.0, 0, 1)
    ctxink = np.maximum(tone_c, dots * 0.65)
    # deep grey nuclei: light grey with a sparse stipple
    dm = np.clip(Dp, 0, 1) * tis
    dd = (rng.random(t.shape) < 0.035 * dm).astype(np.float32)
    deepink = np.maximum(0.10 * dm, np.clip(cv2.GaussianBlur(dd, (0, 0), 0.4) * 2.4, 0, 1) * 0.5)
    # white matter: a light wash, the fibres are the real streamlines
    wash = 0.09 * np.clip(W, 0, 1) * (0.6 + 0.4 * n)
    base = np.maximum(np.maximum(ctxink, deepink), wash)
    # version shown with a selected tract: plain grey tones, no stipple (it would look like the tract's fibres)
    plain = np.maximum(np.maximum(cv2.GaussianBlur(tone_c, (0, 0), 1.5) * 0.85, 0.10 * dm), wash)
    if fib is not None:
        fl = cv2.GaussianBlur(fib, (0, 0), 0.30)
        fibink = 0.88 * (1.0 - np.exp(-fl * FIB_GAIN)) * tis
        fibink *= 1.0 - 0.6 * np.clip(Dp, 0, 1)              # deep grey nuclei: only the stronger bundles show
    else:
        fibink = np.zeros_like(base)
    full = np.maximum(base, fibink)
    # thin contour of the brain and of the ventricles (border of the tissue)
    canvas = np.zeros(t.shape, np.uint8)
    cs, _ = cv2.findContours(tis.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    cs = [c for c in cs if cv2.arcLength(c, True) > UP * 10]
    cv2.drawContours(canvas, cs, -1, 150, 1, cv2.LINE_AA)
    if surf is not None:                                               # the pial contour of each hemisphere, as drawn lines
        canvas = np.zeros(t.shape, np.uint8)
        for key in ("Lp", "Rp"):
            sp = surf[key][1]
            if len(sp):
                pts = np.round(sp * 16).astype(np.int32)                 # sub-pixel precision (shift 4)
                cv2.polylines(canvas, list(pts.reshape(-1, 2, 1, 2)), False, 165, 1, cv2.LINE_AA, shift=4)
        vcs, _ = cv2.findContours(upls(np.isin(ps, VENT_FINE)).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(canvas, [c for c in vcs if cv2.arcLength(c, True) > UP * 6], -1, 150, 1, cv2.LINE_AA)
    line = np.maximum(canvas.astype(np.float32) / 255, np.clip(sulc * 2.2, 0, 1) * 0.75)
    global LAST_SILVER
    LAST_SILVER = (silver(t1s, ps, tis, rng, cortex, white & ~upl(np.isin(ps, NONCEREBRAL))) if surf is not None else silver(t1s, ps, tis, rng)) if ps is not None else None
    out = []
    for x in (full, plain):
        x = np.maximum(x, line * 0.85) * alpha
        out.append(np.clip(x, 0, 1))
    return out[0], out[1], alpha

def main():
    A = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None
    t1, aff = to_ras(nib.load(A("--t1"))); t1 = t1.astype(np.float32)
    t2, _ = to_ras(nib.load(A("--t2"))); t2 = t2.astype(np.float32)
    parc, _ = to_ras(nib.load(A("--parc")))
    tissue, ctx, deep, wm = classes(parc)
    vx = abs(aff[0, 0])
    # FA (diffusion space) resampled on the AC-PC grid
    FA = None
    if A("--fa"):
        fi = nib.as_closest_canonical(nib.load(A("--fa"))); fa = np.asarray(fi.dataobj, np.float32)
        ii, jj, kk = np.mgrid[0:t1.shape[0], 0:t1.shape[1], 0:t1.shape[2]].astype(np.float32)
        acpc = np.stack([ii, jj, kk, np.ones_like(ii)]).reshape(4, -1)
        w = (aff @ acpc)[:3] - DTI2ACPC[:, None]                   # -> diffusion world
        c = (np.linalg.inv(fi.affine) @ np.vstack([w, np.ones((1, w.shape[1]))]))[:3]
        FA = ndi.map_coordinates(fa, c, order=1, cval=0).reshape(t1.shape)
        del ii, jj, kk, acpc, w, c
    SURF = {}
    for key, flag in (("Lp", "--lpial"), ("Lw", "--lwhite"), ("Rp", "--rpial"), ("Rw", "--rwhite")):
        if A(flag): SURF[key] = Surface(A(flag))
    TR = None
    if A("--trk"):
        TR = Tracts(A("--trk"), keep=float(A("--keep") or 0.15))
        TR.a += DTI2ACPC; TR.b += DTI2ACPC; TR.lo += DTI2ACPC; TR.hi += DTI2ACPC
    sh = t1.shape
    world = lambda d, i: float(aff[d, d] * i + aff[d, 3])
    norm = lambda v, lo, hi: np.clip((v - lo) / (hi - lo), 0, 1)
    t1lo, t1hi = np.percentile(t1[tissue], [1, 99.5]); t2lo, t2hi = np.percentile(t2[tissue], [1, 99.5])

    def section(P, j, c0, c1, r0, r1, want_fib=True):
        sec = cut(t1, P, j)[r0:r1, c0:c1]
        labs = [cut(m, P, j)[r0:r1, c0:c1] for m in (tissue, ctx, deep, wm)]
        extra = (cut(t2, P, j)[r0:r1, c0:c1], cut(parc, P, j)[r0:r1, c0:c1])
        fib = None
        w0 = world(P["axis"], j)
        def px(p):
            ic = (p[:, P["cols"]] - aff[P["cols"], 3]) / aff[P["cols"], P["cols"]]
            ir = (p[:, P["rows"]] - aff[P["rows"], 3]) / aff[P["rows"], P["rows"]]
            c = (sh[P["cols"]] - 1 - ic) - c0; r = (sh[P["rows"]] - 1 - ir) - r0
            return np.stack([(c + 0.5) * UP - 0.5, (r + 0.5) * UP - 0.5], 1)
        shape = (sec.shape[0] * UP, sec.shape[1] * UP)
        if TR is not None and want_fib:
            pa, pb = TR.slab(w0, vx / 2 + 0.3, P["axis"])
            fib = splat(shape, px(pa), px(pb))
        surf = surface_section(SURF, P["axis"], w0, px, shape) if SURF else None
        return sec, labs, fib, extra + (surf,)

    def crop(P):
        cc = np.where(tissue.any(tuple(d for d in range(3) if d != P["cols"])))[0]
        rr = np.where(tissue.any(tuple(d for d in range(3) if d != P["rows"])))[0]
        c0, c1 = max(sh[P["cols"]] - 1 - cc.max() - 4, 0), min(sh[P["cols"]] - 1 - cc.min() + 5, sh[P["cols"]])
        r0, r1 = max(sh[P["rows"]] - 1 - rr.max() - 4, 0), min(sh[P["rows"]] - 1 - rr.min() + 5, sh[P["rows"]])
        return c0, c1, r0, r1

    if A("--preview"):
        od = A("--preview"); os.makedirs(od, exist_ok=True)
        for spec in A("--at").split(","):
            pl, f = spec.split(":"); P = PLANES[pl]; f = float(f)
            idx = np.where(tissue.any(tuple(d for d in range(3) if d != P["axis"])))[0]
            j = int(round(idx.max() - f * (idx.max() - idx.min()))) if P["reverse"] else int(round(idx.min() + f * (idx.max() - idx.min())))
            c0, c1, r0, r1 = crop(P)
            sec, labs, fib, (t2s, ps, sf) = section(P, j, c0, c1, r0, r1)
            full, base, alpha = draw(sec, labs, fib, seed=j, t2s=t2s, ps=ps, surf=sf)
            sv = LAST_SILVER * alpha + (1 - alpha) * 0.97
            Image.fromarray((np.clip(sv, 0, 1) * 255).astype(np.uint8)).save(os.path.join(od, f"{pl}_{f}_silver.png"))
            for nm, x in (("full", full), ("base", base)):
                rgb = (247 * (1 - x[..., None]) + 60 * x[..., None]).astype(np.uint8).repeat(3, -1)
                Image.fromarray(rgb).save(os.path.join(od, f"{pl}_{f}_{nm}.png"))
            print(pl, j, full.shape, flush=True)
        return

    out = A("--out")
    planes = A("--web").split(",")
    for name in planes:
        P = PLANES[name]; od = os.path.join(out, name)
        for sub in ("", "base", "t1", "t2", "fa", "silver"): os.makedirs(os.path.join(od, sub), exist_ok=True)
        idx = np.where(tissue.any(tuple(d for d in range(3) if d != P["axis"])))[0]
        js = list(range(idx.max(), idx.min() - 1, -STEP)) if P["reverse"] else list(range(idx.min(), idx.max() + 1, STEP))
        c0, c1, r0, r1 = crop(P)
        for k, j in enumerate(js):
            sec, labs, fib, (t2s, ps, sf) = section(P, j, c0, c1, r0, r1)
            full, base, alpha = draw(sec, labs, fib, seed=j, t2s=t2s, ps=ps, surf=sf)
            h = int(round(full.shape[0] * WIDTH / full.shape[1]))
            fname = f"s{k:03d}.webp"
            for sub, x in (("", full), ("base", base), ("silver", LAST_SILVER)):
                la = np.stack([(x * 255).astype(np.uint8), (alpha * 255).astype(np.uint8)], -1)
                Image.fromarray(la, "LA").resize((WIDTH, h), Image.LANCZOS).save(os.path.join(od, sub, fname), quality=74, method=4)
            # T1, T2, FA: brain only (the parcellation), at their own resolution
            sw = WIDTH // 2; hs = int(round(sec.shape[0] * sw / sec.shape[1]))
            mk = cv2.resize(alpha, (sw, hs), interpolation=cv2.INTER_AREA)       # same border as the drawing
            for sub, vol, lo, hi in (("t1", t1, t1lo, t1hi), ("t2", t2, t2lo, t2hi), ("fa", FA, 0.0, 0.85)):
                if vol is None: continue
                v = cv2.resize(norm(cut(vol, P, j)[r0:r1, c0:c1], lo, hi), (sw, hs), interpolation=cv2.INTER_AREA)
                la = np.stack([(v * 255).astype(np.uint8), (np.clip(mk, 0, 1) * 255).astype(np.uint8)], -1)
                Image.fromarray(la, "LA").save(os.path.join(od, sub, fname), quality=82, method=4)
            print(name, k, j, flush=True)
        O = [0.0] * 3; U = [0.0] * 3; V = [0.0] * 3
        O[P["cols"]] = world(P["cols"], sh[P["cols"]] - 1 - c0 + 0.5); U[P["cols"]] = -(c1 - c0) * vx
        O[P["rows"]] = world(P["rows"], sh[P["rows"]] - 1 - r0 + 0.5); V[P["rows"]] = -(r1 - r0) * vx
        meta = {"n": len(js), "axis": P["axis"], "labels": P["labels"], "from": P["from"], "step_mm": STEP * vx,
                "pos": [world(P["axis"], j) for j in js], "O": O, "U": U, "V": V,
                "modes": {"dejerine": "", "base": "base/", "t1": "t1/", "t2": "t2/", "silver": "silver/", "fa": "fa/" if FA is not None else None}}
        json.dump(meta, open(os.path.join(od, "plane.json"), "w"), indent=1)
    if "--index" in sys.argv:
        xs, ys, zs = [np.where(tissue.any(tuple(d for d in range(3) if d != a)))[0] for a in range(3)]
        meta = {"planes": list(PLANES), "space": "HCP 102109 ACPC",
                "brain_box": [[world(0, xs.min()), world(1, ys.min()), world(2, zs.min())], [world(0, xs.max()), world(1, ys.max()), world(2, zs.max())]],
                "dti_to_acpc_mm": DTI2ACPC.tolist(),
                "style": "Dejerine (Weigert stain) drawings from T1w, wmparc and the whole-brain tractogram: tools/sections/dejerine_acpc.py",
                "note": "world = AC-PC RAS mm of subject 102109; atlas tracts in the same space align exactly"}
        json.dump(meta, open(os.path.join(out, "sections.json"), "w"), indent=1)

if __name__ == "__main__":
    main()
