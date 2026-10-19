"""Turn FSLeyes screenshots of coronal MRI slices into drawings in the style of Dejerine's
coronal sections (Weigert myelin stain: white matter dark and hatched, grey matter light).

usage: python3 dejerine_slices.py <folder with screenshots> <output folder> [--every N] [--only i,j]
"""
import sys, re, glob, os
import numpy as np, cv2
from PIL import Image
from scipy import ndimage as ndi

COR = (1340, 320, 2300, 1500)        # coronal panel (x0, y0, x1, y1) in the screenshots
SAG = (180, 320, 1340, 1500)         # sagittal panel (crosshair = position of the cut)

def order(folder):
    fs = glob.glob(os.path.join(folder, "*.png"))
    def key(f):
        m = re.search(r"(\d+)\.(\d+)\.(\d+)( (\d+))?\.png$", f)
        return (int(m[1]), int(m[2]), int(m[3]), int(m[5] or 0))
    return sorted(fs, key=key)

def green(im):
    return (im[..., 1] > 120) & (im[..., 0] < 110) & (im[..., 2] < 110)

def cut_position(im):
    """x of the vertical crosshair on the sagittal panel (anterior is on the right)."""
    x0, y0, x1, y1 = SAG
    g = green(im[y0:y1, x0:x1])
    cols = g.sum(0)
    return x0 + int(np.argmax(cols)) if cols.max() > 200 else None

def coronal(im):
    x0, y0, x1, y1 = COR
    c = im[y0:y1, x0:x1].copy()
    g = cv2.dilate(green(c).astype(np.uint8), np.ones((5, 5), np.uint8))
    gray = cv2.cvtColor(c, cv2.COLOR_RGB2GRAY)
    gray = cv2.inpaint(gray, g, 5, cv2.INPAINT_TELEA)
    return gray.astype(np.float32) / 255.0

def brain_mask(t1):
    s = cv2.GaussianBlur(t1, (0, 0), 3)
    tissue = s > 0.20
    h, w = t1.shape
    er = cv2.erode(tissue.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))
    n, lab, st, cen = cv2.connectedComponentsWithStats(er)
    if n < 2:
        return np.zeros_like(tissue)
    # the brain: large component closest to the upper centre of the panel
    best, bs = 0, -1e9
    for j in range(1, n):
        cx, cy = cen[j]; a = st[j, 4]
        score = a / 1000 - abs(cx - w * 0.5) / 20 - abs(cy - h * 0.42) / 25
        if score > bs: bs, best = score, j
    m = (lab == best).astype(np.uint8)
    m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))) & tissue.astype(np.uint8)
    m = ndi.binary_fill_holes(m)
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    return m.astype(bool)

def engrave(t1, mask, seed=0, lims=None):
    rng = np.random.default_rng(seed)
    h, w = t1.shape
    s = cv2.GaussianBlur(t1, (0, 0), 1.1)                      # remove the voxel blocks
    lo, hi = lims if lims else (np.percentile(s[mask], 8), np.percentile(s[mask], 99.5))
    n = np.clip((s - lo) / (hi - lo), 0, 1)
    # Weigert look: myelin (bright on T1) becomes dark ink, cortex stays light
    wm = np.clip((n - 0.55) / 0.30, 0, 1) ** 1.2
    gm = np.clip((n - 0.18) / 0.4, 0, 1)
    dens = 0.10 * gm + 0.78 * wm
    dens *= mask
    # hatching: fine parallel strokes whose thickness follows the ink density
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    warp = cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), 7) * 9
    ph = ((xx * 0.42 + yy * 0.91 + warp) / 2.6) % 1.0
    line = np.abs(ph - 0.5) * 2                                 # 0 at the centre of a stroke
    ink = np.clip((dens * 1.15 - line) / 0.18 + 0.5, 0, 1) * (dens > 0.03)
    ink = np.maximum(ink, np.clip(dens - 0.62, 0, 1) * 2.2)     # deep white matter almost solid
    # fine stipple in the cortex
    st = (rng.random((h, w)) < gm * 0.05 * mask) * 0.6
    ink = np.maximum(ink, st)
    # contours: pial surface and grey/white boundary
    edge = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    gw = (cv2.GaussianBlur(wm, (0, 0), 1.2) > 0.35).astype(np.uint8)
    gwe = (cv2.morphologyEx(gw, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0) & mask
    ink = np.maximum(ink, edge * 0.95)
    ink = np.maximum(ink, gwe * 0.55)
    ink = cv2.GaussianBlur(ink.astype(np.float32), (0, 0), 0.7)
    return np.clip(ink, 0, 1)

def to_rgba(ink, size):
    ys, xs = np.where(ink > 0.02)
    a = (ink * 255).astype(np.uint8)
    rgba = np.zeros(ink.shape + (4,), np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2], rgba[..., 3] = 52, 41, 32, a
    im = Image.fromarray(rgba)
    return im.resize(size, Image.LANCZOS)

def build_volume(fs, scale=0.5):
    vols, pos = [], []
    for f in fs:
        im = np.array(Image.open(f).convert("RGB"))
        pos.append(cut_position(im))
        t1 = coronal(im)
        vols.append(cv2.resize(t1, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA))
    return np.stack(vols), pos

def brain_mask_3d(vol):
    from scipy.ndimage import binary_erosion, binary_dilation, label, binary_fill_holes, gaussian_filter
    s = gaussian_filter(vol, (0.7, 1.5, 1.5))
    tissue = s > 0.22
    ball = np.zeros((5, 13, 13), bool)                 # ~5 mm: breaks the bridges to scalp and skull
    zz, yy, xx = np.mgrid[-2:3, -6:7, -6:7]
    ball[(zz / 2.5) ** 2 + (yy / 6.5) ** 2 + (xx / 6.5) ** 2 <= 1] = True
    er = binary_erosion(tissue, ball)
    lab, n = label(er)
    sizes = np.bincount(lab.ravel()); sizes[0] = 0
    core = lab == np.argmax(sizes)
    m = binary_dilation(core, ball) & tissue
    for k in range(m.shape[0]):
        m[k] = binary_fill_holes(m[k])
        m[k] = cv2.morphologyEx(m[k].astype(np.uint8), cv2.MORPH_OPEN,
                                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))).astype(bool)
    return m

if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    every = int(sys.argv[sys.argv.index("--every") + 1]) if "--every" in sys.argv else 1
    os.makedirs(out, exist_ok=True)
    fs = order(src)
    vol, pos = build_volume(fs)
    print("volume", vol.shape, flush=True)
    mask = brain_mask_3d(vol)
    np.save(os.path.join(out, "mask.npy"), mask)
    v = vol[mask]
    lims = (float(np.percentile(v, 5)), float(np.percentile(v, 99.7)))
    meta = []
    keep = [i for i in range(0, len(fs), every) if mask[i].sum() > 400]
    for k, i in enumerate(keep):
        ink = engrave(vol[i], mask[i], seed=i, lims=lims)
        name = f"slice-{k:03d}.webp"
        to_rgba(ink, (vol.shape[2], vol.shape[1])).save(os.path.join(out, name), quality=78, method=6)
        meta.append((i, pos[i], name))
    with open(os.path.join(out, "slices.txt"), "w") as f:
        for i, p_, name in meta: f.write(f"{i}\t{p_}\t{name}\n")
    print(len(meta), "slices", flush=True)
