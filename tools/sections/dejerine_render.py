"""Draw coronal slices of a T1 volume in the style of Dejerine's plates (Anatomie des centres nerveux,
drawings by H. Gillet, Weigert myelin stain): light cortex with stippling that thickens towards the
white matter, dark white matter made of fine streaks that follow the fibres along each gyral blade,
thin ink contours along every gyrus, sulcus and ventricle.

usage: python3 dejerine_render.py <T1.nii.gz> <out folder> --at 0.195,0.385   (fractions front->back)
       python3 dejerine_render.py <T1.nii.gz> assets/atlas/drawings --web 3      (series for the atlas)
       python3 dejerine_render.py <T1.nii.gz> <out folder> --every 3            (every 3rd slice)
"""
import sys, os, json
import numpy as np, cv2, nibabel as nib
from scipy import ndimage as ndi
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from pack_nifti import brain_mask

UP = 6                       # 1.25 mm voxels -> ~0.21 mm pixels

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

def draw(t1s, ms, seed=0):
    rng = np.random.default_rng(seed)
    # upsample smoothly (no voxel blocks)
    t = cv2.resize(t1s, None, fx=UP, fy=UP, interpolation=cv2.INTER_CUBIC)
    t = cv2.GaussianBlur(t, (0, 0), UP * 0.45)
    m = cv2.GaussianBlur(cv2.resize(ms.astype(np.float32), None, fx=UP, fy=UP, interpolation=cv2.INTER_LINEAR), (0, 0), UP * 0.5) > 0.5
    n = np.clip((t - 0.30) / 0.80, 0, 1) * m                   # grey ~0.47, white ~0.88
    wm = smoothstep(0.60, 0.80, n)
    # ---- fibre direction: radiating from the centrum semiovale along each gyral blade
    depth = ndi.distance_transform_edt(wm > 0.5).astype(np.float32)
    big = cv2.GaussianBlur(wm.astype(np.float32), (0, 0), UP * 2.2)
    gx = cv2.Sobel(big, cv2.CV_32F, 1, 0, ksize=5); gy = cv2.Sobel(big, cv2.CV_32F, 0, 1, ksize=5)
    s_ = UP * 0.8
    jxx = cv2.GaussianBlur(gx * gx, (0, 0), s_); jyy = cv2.GaussianBlur(gy * gy, (0, 0), s_); jxy = cv2.GaussianBlur(gx * gy, (0, 0), s_)
    ang = 0.5 * np.arctan2(2 * jxy, jxx - jyy)                     # major eigenvector = along the gradient
    vx, vy = np.cos(ang).astype(np.float32), np.sin(ang).astype(np.float32)
    # ---- fibrous texture
    noise = rng.random(t.shape).astype(np.float32)
    noise = cv2.GaussianBlur(noise, (0, 0), 0.45)
    tex = lic(noise, vx, vy, L=int(UP * 1.6))
    u = np.empty_like(tex); idx = np.argsort(tex, axis=None)       # rank transform -> uniform 0..1
    u.ravel()[idx] = np.linspace(0, 1, tex.size, dtype=np.float32)
    mmpx = 1.25 / UP                                                # mm per pixel
    # ---- tone of the Weigert stain (continuous, like the engraver's shading)
    core = smoothstep(0.50, 0.90, n)                                # myelin content from T1
    width = ndi.maximum_filter(depth, size=int(UP * 5)) * mmpx      # local half-width of the white matter (mm)
    thin = np.exp(-width / 3.0)                                     # gyral blades are darker than the centrum
    tone_wm = core * (0.70 + 0.26 * thin)
    dwm = ndi.distance_transform_edt(wm < 0.5).astype(np.float32) * mmpx     # mm outside the white matter
    gm = smoothstep(0.10, 0.30, n) * (wm < 0.5)
    tone_gm = (0.70 * np.exp(-dwm / 1.0) + 0.05) * gm                # radial fibres fading into the cortex
    tone = np.maximum(tone_wm, tone_gm)
    tone = cv2.GaussianBlur(tone, (0, 0), 1.0)
    # fine fibres: the streak texture modulates the tone (no hard black)
    streak = (u - 0.5) * 2                                          # -1..1
    ink = np.clip(tone * (1.0 + 0.30 * streak) - 0.03, 0, 1)
    # stipple in the cortex where the tone fades
    near = 0.70 * np.exp(-dwm / 1.0) * gm
    dots = (rng.random(t.shape) < near * 0.20).astype(np.float32)
    ink = np.maximum(ink, cv2.GaussianBlur(dots, (0, 0), 0.5) * 1.5)
    ink = np.clip(ink, 0, 1)
    # ---- contours: brain outline and the CSF of sulci and ventricles, as clean thin lines
    canvas = np.zeros(t.shape, np.uint8)
    sm = (cv2.GaussianBlur(m.astype(np.float32), (0, 0), UP * 0.3) > 0.5).astype(np.uint8)
    cs, _ = cv2.findContours(sm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    tis = ((cv2.GaussianBlur(n, (0, 0), UP * 0.18) > 0.30) & (sm > 0)).astype(np.uint8)
    tis = cv2.morphologyEx(tis, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cg, _ = cv2.findContours(tis, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    cg = [c for c in cg if cv2.arcLength(c, True) > UP * 12]
    cv2.drawContours(canvas, cg, -1, 140, 1, cv2.LINE_AA)            # outline of the gyri: border between tissue and CSF
    csf = ((cv2.GaussianBlur(n, (0, 0), UP * 0.35) < 0.16) & (cv2.erode(sm, np.ones((5, 5), np.uint8)) > 0)).astype(np.uint8)
    cs2, _ = cv2.findContours(csf, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    cs2 = [c for c in cs2 if cv2.arcLength(c, True) > UP * 9]
    cv2.drawContours(canvas, cs2, -1, 200, 1, cv2.LINE_AA)
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
    ink = np.maximum(ink, np.clip(skl, 0, 1) * 0.50)
    ink = np.maximum(ink, canvas.astype(np.float32) / 255 * 0.92)
    # the CSF itself stays paper-white
    ink *= 1 - cv2.GaussianBlur(csf.astype(np.float32), (0, 0), 1.0) * 0.9
    ink = np.maximum(ink, canvas.astype(np.float32) / 255 * 0.92)
    tisd = cv2.dilate(tis, np.ones((3, 3), np.uint8)).astype(np.float32)
    ink *= cv2.GaussianBlur(tisd, (0, 0), 0.6)               # nothing outside the brain tissue
    return np.clip(ink, 0, 1)

def plate(ink, paper=(233, 229, 204), inkc=(30, 31, 24)):
    a = ink[..., None]
    rgb = (np.array(paper)[None, None] * (1 - a) + np.array(inkc)[None, None] * a).astype(np.uint8)
    return Image.fromarray(rgb)

def web_series(t1, m, out, every=3, width=640):
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
    for k, j in enumerate(js):
        ink = draw(coronal(t1, j)[r0:r1, c0:c1], coronal(m, j)[r0:r1, c0:c1], seed=j)
        im = Image.fromarray((ink * 255).astype(np.uint8), "L")
        h = int(round(im.height * width / im.width))
        im = im.resize((width, h), Image.LANCZOS)
        name = f"s{k:03d}.webp"; im.save(os.path.join(out, name), quality=72, method=6)
        names.append(name); print(k, j, flush=True)
    vox = 1.25
    px = (c1 - c0) * vox / width
    cx = ((m.shape[0] - 1 - (xs.min() + xs.max()) / 2) - c0) * vox / px    # column of the brain centre
    meta = {"n": len(names), "files": names, "w": width, "h": h, "px_mm": px, "slice_mm": every * vox,
            "brain": {"center_px": [cx, 0.0], "top_row": (m.shape[2] - 1 - zs.max() - r0) * vox / px,
                      "length_mm": (ys.max() - ys.min() + 1) * vox},
            "style": "Dejerine (Weigert stain) drawing of the T1, tools/sections/dejerine_render.py",
            "note": "s000 = most anterior; image left = subject's right"}
    json.dump(meta, open(os.path.join(out, "drawings.json"), "w"), indent=1)

if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    t1, m, vox = load(src)
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
        ink = draw(coronal(t1, j), coronal(m, j), seed=j)
        plate(ink).save(os.path.join(out, f"plate-{k:03d}.png"))
        print(k, j, ink.shape, flush=True)
