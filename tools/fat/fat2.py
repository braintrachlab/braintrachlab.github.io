"""FAT plates, version 2.

Streamlines are traced on the original figure (with fascicles), exactly as in
fat.py, then registered onto the clean figure (same brains without fascicles,
with the species silhouettes). The plate is the clean brain, so the surface
under the fascicles is real and nothing is hidden before the fibres appear.

usage: fat2.py figure_with_fat.png clean_brains.png outdir"""
import sys, os
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from scipy.optimize import minimize
from skimage import morphology

SRC, CLEAN, OUTDIR = sys.argv[1], sys.argv[2], sys.argv[3]
here = os.path.dirname(os.path.abspath(__file__))
core = open(os.path.join(here, "fat.py")).read().split("# split into the three species")[0]
sys.argv = [sys.argv[0], SRC, OUTDIR]
exec(core)            # -> brain, orange, green, streamlines(), PAL, rng, X0, Y0, W, H

# ---------------- clean figure ----------------------------------------------
c = np.asarray(Image.open(CLEAN).convert("RGB")).astype(np.float32) / 255.0
cl = c.mean(-1)
Hc, Wc = cl.shape
cdark = cl < 0.3
lab, n = ndi.label(cdark)
sz = np.bincount(lab.ravel()); sz[0] = 0
sil_ids = [i for i in range(1, n + 1) if sz[i] > 3000]           # the three silhouettes
silh = np.isin(lab, sil_ids)
cbase = (cl < 0.985) & ~cdark
cbase = morphology.opening(cbase, morphology.disk(2))
lab2, n2 = ndi.label(cbase)
sz2 = np.bincount(lab2.ravel()); sz2[0] = 0
cbrain = np.isin(lab2, np.where(sz2 > 20000)[0])
cbrain = ndi.binary_fill_holes(morphology.closing(cbrain, morphology.disk(3)))

def groups(mask, dil):
    lab, n = ndi.label(ndi.binary_dilation(mask, iterations=dil))
    sz = np.bincount(lab.ravel()); sz[0] = 0
    ids = sorted(np.argsort(sz)[::-1][:3], key=lambda i: ndi.center_of_mass(lab == i)[1])
    return [(lab == i) & mask for i in ids]

old_groups = groups(brain, 25)
new_groups = groups(cbrain, 25)
sil_lab, _ = ndi.label(silh)
sil_cent = [(i, ndi.center_of_mass(sil_lab == i)) for i in range(1, sil_lab.max() + 1)]

def register(mo, mn):
    """old (x,y) -> new (x,y): uniform scale + translation, fitted on the brain masks"""
    yo, xo = np.nonzero(mo); yn, xn = np.nonzero(mn)
    s0 = np.sqrt(len(xn) / len(xo))
    t0 = [xn.mean() - s0 * xo.mean(), yn.mean() - s0 * yo.mean()]
    dtn = ndi.distance_transform_edt(~mn)
    dto = ndi.distance_transform_edt(~mo)
    eo = np.argwhere(mo & ~ndi.binary_erosion(mo, iterations=1))[::3][:, ::-1].astype(float)
    en = np.argwhere(mn & ~ndi.binary_erosion(mn, iterations=1))[::3][:, ::-1].astype(float)
    def cost(p):
        s, tx, ty = p
        q = eo * s + [tx, ty]
        xi = np.clip(q[:, 0].astype(int), 0, Wc - 1); yi = np.clip(q[:, 1].astype(int), 0, Hc - 1)
        r = (en - [tx, ty]) / s
        xr = np.clip(r[:, 0].astype(int), 0, W - 1); yr = np.clip(r[:, 1].astype(int), 0, H - 1)
        return np.mean(np.minimum(dtn[yi, xi], 30)) + np.mean(np.minimum(dto[yr, xr], 30))
    res = minimize(cost, [s0, *t0], method="Powell", options={"xtol": 1e-3, "ftol": 1e-4, "maxiter": 4000})
    return res.x, res.fun

def boxes(darkmask, brain_groups):
    """frame of each inset: union of the long straight dark segments next to each brain"""
    st = ndi.binary_opening(darkmask, structure=np.ones((1, 41))) | ndi.binary_opening(darkmask, structure=np.ones((41, 1)))
    ys, xs = np.nonzero(st)
    cents = [ndi.center_of_mass(g)[1] for g in brain_groups]
    out = []
    for k, g in enumerate(brain_groups):
        gx = np.nonzero(g)[1]
        sel = (xs > gx.min() - 60) & (xs < gx.max() + 60)
        out.append((xs[sel].min(), ys[sel].min(), xs[sel].max(), ys[sel].max()))
    return out
old_boxes = None


go = np.hypot(ndi.sobel(ndi.gaussian_filter(lum, 1.5), 1), ndi.sobel(ndi.gaussian_filter(lum, 1.5), 0))
gn = np.hypot(ndi.sobel(ndi.gaussian_filter(cl, 1.5), 1), ndi.sobel(ndi.gaussian_filter(cl, 1.5), 0))
fib_w = ~ndi.binary_dilation(orange | green, iterations=4)

def register_inset(box, s0, t0):
    # sample the upper-left part of the frame (the lateral brain covers the lower right)
    bx1, by1, bx2, by2 = box
    ys, xs = np.mgrid[by1 + 4:by1 + int(0.62 * (by2 - by1)):2, bx1 + 4:bx1 + int(0.62 * (bx2 - bx1)):2]
    ys, xs = ys.ravel(), xs.ravel()
    keep = fib_w[ys, xs] & brain[ys, xs]
    ys, xs = ys[keep], xs[keep]
    a = go[ys, xs]; a = (a - a.mean()) / (a.std() + 1e-9)
    best = (-9, None)
    for ds in np.linspace(0.94, 1.06, 13):
        sc = s0 * ds
        for dx in range(-60, 61, 3):
            for dy in range(-60, 61, 3):
                qx = (xs * sc + t0[0] + dx).astype(int); qy = (ys * sc + t0[1] + dy).astype(int)
                ok = (qx >= 0) & (qx < Wc) & (qy >= 0) & (qy < Hc)
                b = gn[qy[ok], qx[ok]]
                if b.std() < 1e-6: continue
                r = float(np.mean(a[ok] * (b - b.mean()) / b.std()))
                if r > best[0]: best = (r, (sc, t0[0] + dx, t0[1] + dy))
    sc, tx, ty = best[1]
    # refine at 1 px
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            qx = (xs * sc + tx + dx).astype(int); qy = (ys * sc + ty + dy).astype(int)
            ok = (qx >= 0) & (qx < Wc) & (qy >= 0) & (qy < Hc)
            b = gn[qy[ok], qx[ok]]; r = float(np.mean(a[ok] * (b - b.mean()) / (b.std() + 1e-9)))
            if r > best[0]: best = (r, (sc, tx + dx, ty + dy))
    return best

old_boxes = boxes(dark, old_groups)
new_boxes = boxes((cl < 0.6) & ~ndi.binary_dilation(silh, iterations=3), new_groups)
print('boxes', old_boxes, new_boxes)
names = ["macaque", "chimpanzee", "human"]
INK = np.array([128, 138, 154])     # soft cool grey for the silhouettes
OUT_SCALE = 0.75
meta = []
LAT_MASKS = []
DBG = (c * 255).astype(np.uint8).copy()
for k, (name, mo, mn) in enumerate(zip(names, old_groups, new_groups)):
    (s, tx, ty), err = register(mo, mn)
    ob = old_boxes[k]; nb = new_boxes[k]
    r_in, (si, txi, tyi) = register_inset(ob, s, (tx, ty))
    pass  # print(name, "lateral", round(float(s), 4), "inset", round(float(si), 4), round(txi - tx, 1), round(tyi - ty, 1), "ncc", round(r_in, 3))
    # lateral brain in the clean figure: watershed between the part outside the frame
    # (lateral surface) and the top-left of the frame (medial inset), on the image gradient
    # which surface is visible at each point of the clean figure? compare the clean image with
    # the original warped by the lateral and by the inset transform (fibre pixels ignored)
    nin = np.zeros((Hc, Wc), bool); nin[nb[1]:nb[3], nb[0]:nb[2]] = True
    yy, xx = np.mgrid[0:Hc, 0:Wc].astype(np.float32)
    lumz = ndi.gaussian_filter(lum, 1.0); wfib = fib_w.astype(np.float32)
    def warp(img, sc, ox, oy):
        return ndi.map_coordinates(img, [(yy - oy) / sc, (xx - ox) / sc], order=1, cval=1.0)
    clz = ndi.gaussian_filter(cl, 1.0)
    dl = np.abs(clz - warp(lumz, s, tx, ty)) * warp(wfib, s, tx, ty)
    di = np.abs(clz - warp(lumz, si, txi, tyi)) * warp(wfib, si, txi, tyi)
    wl = ndi.gaussian_filter(warp(wfib, s, tx, ty), 6) + 1e-3
    wi = ndi.gaussian_filter(warp(wfib, si, txi, tyi), 6) + 1e-3
    dl = ndi.gaussian_filter(dl, 6) / wl; di = ndi.gaussian_filter(di, 6) / wi
    sure = (wl > 0.5) & (wi > 0.5)                       # both views show bare surface here
    lat_ev = mn & (~nin | (sure & (dl < di)))
    ins_ev = mn & nin & sure & (di <= dl)
    lat_ev = morphology.opening(lat_ev, morphology.disk(4))
    # areas covered by fibres in the original carry no evidence: give them to the surface
    # that surrounds them (closing of the lateral evidence, never across inset evidence)
    # the undecided areas are split along the edges of the clean rendering (the outline of the
    # lateral brain is a sharp edge there, since the clean figure has no fibres)
    from skimage.segmentation import watershed
    markers = np.zeros((Hc, Wc), np.int32)
    markers[morphology.erosion(lat_ev, morphology.disk(2))] = 1
    markers[morphology.erosion(ins_ev, morphology.disk(2))] = 2
    ws = watershed(ndi.gaussian_filter(gn, 1.0), markers, mask=mn)
    new_lat = ws == 1
    labl, _ = ndi.label(new_lat)
    keep = np.unique(labl[mn & ~nin & (labl > 0)])
    new_lat = ndi.binary_fill_holes(np.isin(labl, keep[keep > 0]))
    # where the two bundles are separate in the original, classify each bundle directly:
    # a bundle that reaches outside the frame lies on the lateral brain
    ins_old = np.zeros_like(brain); ins_old[ob[1]:ob[3], ob[0]:ob[2]] = True
    old_inset_fib = np.zeros_like(brain); separable = True
    for m in (orange, green):
        labf, nf = ndi.label(m & ndi.binary_dilation(mo, iterations=25))
        for i in range(1, nf + 1):
            comp = labf == i
            frac_in = (comp & ins_old).sum() / comp.sum()
            if comp.sum() > 300 and os.environ.get("FATDEBUG"): print("   comp", name, int(comp.sum()), round(float(frac_in), 2))
            if frac_in > 0.98: old_inset_fib |= comp
            elif frac_in > 0.15 and comp.sum() > 400: separable = False
    def to_new(p):
        p = np.asarray(p, float)
        q_l = p * s + [tx, ty]
        q_i = p * si + [txi, tyi]
        xo = np.clip(p[:, 0].astype(int), 0, W - 1); yo = np.clip(p[:, 1].astype(int), 0, H - 1)
        use_i = old_inset_fib[yo, xo]                  # bundles entirely inside the frame
        if r_in > 0.9:                                 # reliable image split for merged bundles
            xi = np.clip(q_l[:, 0].astype(int), 0, Wc - 1); yi = np.clip(q_l[:, 1].astype(int), 0, Hc - 1)
            use_i = use_i | (~new_lat[yi, xi] & ins_old[yo, xo])
        return np.where(use_i[:, None], q_i, q_l), use_i
    LAT_MASKS.append(new_lat)
    # silhouette: the one closest to this brain
    cy, cx = ndi.center_of_mass(mn)
    sid = min(sil_cent, key=lambda t: abs(t[1][1] - cx) + 0.3 * abs(t[1][0] - cy))[0]
    sm = sil_lab == sid
    ys, xs = np.nonzero(mn | sm)
    pad = 8
    x1, x2 = max(xs.min() - pad, 0), min(xs.max() + pad, Wc)
    y1, y2 = max(ys.min() - pad, 0), min(ys.max() + pad, Hc)
    w, h = int((x2 - x1) * OUT_SCALE), int((y2 - y1) * OUT_SCALE)

    parts = []
    region_old = ndi.binary_dilation(mo, iterations=25)
    yso = np.nonzero(mo)[0]
    ytop, ybot = yso.min(), yso.max()
    for cname, m in (("orange", orange), ("green", green)):
        mm = morphology.erosion(m & region_old, morphology.disk(2))
        if not mm.any():
            continue
        sl = streamlines(mm, 3)
        dk, lt = (np.array(v) for v in PAL[cname])
        shs = np.array([v for _, v in sl]); lo, hi = np.percentile(shs, 5), np.percentile(shs, 95)
        for p, sh in sl:
            t = np.clip((sh - lo) / (hi - lo + 1e-6), 0, 1)
            r, g_, b = (dk * (1 - t) + lt * t).astype(int)
            q = (to_new(p)[0] - [x1, y1]) * OUT_SCALE
            d = 1.2 + k * 1.1 + (ybot - p[0, 1]) / (ybot - ytop + 1) * 2.4 + rng.uniform(0, 0.5)
            path = "M" + " ".join(f"{x:.1f} {y:.1f}" for x, y in q)
            parts.append((d, f'<path d="{path}" stroke="rgb({r},{g_},{b})" stroke-opacity="{0.92 - 0.2 * t:.2f}" '
                             f'stroke-width="{0.5 + 0.45 * rng.random():.2f}" data-delay="{d:.2f}" data-dur="{1.6 + rng.uniform(0, 0.9):.2f}"/>'))
    parts.sort(key=lambda t: t[0])

    # plate: the clean brain (no fascicles), box lines removed
    sub = cl[y1:y2, x1:x2]
    bm = ndi.gaussian_filter(mn[y1:y2, x1:x2].astype(np.float32), 1.0)
    fl = (cl < 0.75) & ~ndi.binary_dilation(silh, iterations=2)
    straight = ndi.binary_opening(fl, structure=np.ones((1, 41))) | ndi.binary_opening(fl, structure=np.ones((41, 1)))
    frame = ndi.binary_dilation(straight[y1:y2, x1:x2], iterations=2)
    alpha = np.clip((1.0 - sub) * 2.3, 0, 1) * bm * ~frame
    la = np.zeros(sub.shape + (2,), np.uint8); la[..., 0] = 64
    la[..., 1] = (np.round(alpha * 31) * 255 / 31).astype(np.uint8)
    png = f"fat-{name}.png"
    Image.fromarray(la, "LA").resize((w, h), Image.LANCZOS).save(os.path.join(OUTDIR, png), optimize=True)
    # silhouette in ink, drawn behind the brain
    sa = ndi.gaussian_filter(sm[y1:y2, x1:x2].astype(np.float32), 0.7)
    rgba = np.zeros(sub.shape + (4,), np.uint8); rgba[..., :3] = INK; rgba[..., 3] = (sa * 255).astype(np.uint8)
    spng = f"fat-{name}-silhouette.png"
    Image.fromarray(rgba, "RGBA").resize((w, h), Image.LANCZOS).save(os.path.join(OUTDIR, spng), optimize=True)
    # soft colour wash under the fibres, registered too
    tint = np.zeros((h, w, 4), np.uint8)
    for cname, m in (("orange", orange), ("green", green)):
        pts_o = np.argwhere(m & region_old)[:, ::-1]
        qn = (to_new(pts_o)[0] - [x1, y1]) * OUT_SCALE
        acc = np.zeros((h, w), np.float32)
        qi = np.round(qn).astype(int); ok = (qi[:, 0] >= 0) & (qi[:, 0] < w) & (qi[:, 1] >= 0) & (qi[:, 1] < h)
        acc[qi[ok, 1], qi[ok, 0]] = 1
        val = ndi.gaussian_filter(ndi.binary_closing(acc > 0, iterations=2).astype(np.float32), 1.2)
        sel = val > 0.02
        tint[sel, :3] = PAL[cname][1]
        tint[..., 3] = np.maximum(tint[..., 3], (np.clip(val, 0, 1) * 255).astype(np.uint8))
    tpng = f"fat-{name}-tint.png"
    Image.fromarray(tint, "RGBA").save(os.path.join(OUTDIR, tpng), optimize=True)

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" fill="none" stroke-linecap="round" stroke-linejoin="round">\n'
           f'<image class="silhouette" href="assets/img/{spng}" x="0" y="0" width="{w}" height="{h}"/>\n'
           f'<image class="plate plate-cool" href="assets/img/{png}" x="0" y="0" width="{w}" height="{h}"/>\n'
           f'<image class="plate-tint" href="assets/img/{tpng}" x="0" y="0" width="{w}" height="{h}" style="--tint-delay:{2.2 + k * 1.1:.1f}s"/>\n'
           + "\n".join(p for _, p in parts) + "\n</svg>\n")
    open(os.path.join(OUTDIR, f"fat-{name}.svg"), "w").write(svg)
    if os.environ.get("FATDEBUG"):
        dbg = DBG
        print(name, 'image split used' if r_in > 0.9 else 'bundle rule only')
        e = new_lat & ~ndi.binary_erosion(new_lat, iterations=2); dbg[e] = [200, 0, 0]
        f = np.argwhere((orange | green) & region_old)[:, ::-1]
        q, ui = to_new(f); q = q.astype(int)
        ok = (q[:, 0] >= 0) & (q[:, 0] < Wc) & (q[:, 1] >= 0) & (q[:, 1] < Hc)
        col_ = np.where(ui[ok, None], np.array([[0, 120, 255]]), np.array([[255, 140, 0]]))
        dbg[q[ok, 1], q[ok, 0]] = (dbg[q[ok, 1], q[ok, 0]] * 0.45 + col_ * 0.55).astype(np.uint8)
    meta.append((name, w, h, round(float(s), 4), round(float(err), 2), len(parts)))
print(meta)


if os.environ.get("FATDEBUG"):
    Image.fromarray(DBG).save(os.path.join(OUTDIR, "_reg.png"))
