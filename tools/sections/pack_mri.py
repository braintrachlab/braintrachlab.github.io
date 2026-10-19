"""Pack the coronal MRI slices (FSLeyes screenshots, front -> back) into one texture for the atlas intro.
The browser draws them as Dejerine-style sections (assets/js/atlas.js, 'mri' intro).

usage: python3 pack_mri.py <folder with screenshots> <output folder (assets/atlas/mri)>
"""
import sys, os, json
import numpy as np, cv2
from scipy import ndimage as ndi
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from dejerine_slices import order, build_volume

SLICE_MM = 1.25           # distance between two screenshots (one voxel of the 1.25 mm volume)
PX_MM = 0.379             # size of a pixel of the half-resolution panel crop
OUT_MM = 0.9              # pixel size stored in the texture

def mask3d(vol, thr=0.33, rad=4.5):
    sp = (SLICE_MM, PX_MM, PX_MM)
    s = ndi.gaussian_filter(vol, (0.6, 1.5, 1.5))
    tissue = s > thr
    er = ndi.distance_transform_edt(tissue, sampling=sp) > rad
    lab, n = ndi.label(er); sz = np.bincount(lab.ravel()); sz[0] = 0
    core = lab == np.argmax(sz)
    m = (ndi.distance_transform_edt(~core, sampling=sp) <= rad + 0.8) & tissue
    for k in range(m.shape[0]): m[k] = ndi.binary_fill_holes(m[k])
    return m

if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    vol, pos = build_volume(order(src))
    m = mask3d(vol)
    keep = [i for i in range(len(vol)) if m[i].sum() > 300]
    vol, m = vol[keep], m[keep]
    zs, ys, xs = np.where(m)
    y0, y1, x0, x1 = ys.min() - 6, ys.max() + 7, xs.min() - 6, xs.max() + 7
    f = PX_MM / OUT_MM
    tiles = []
    for k in range(len(vol)):
        s = cv2.GaussianBlur(vol[k], (0, 0), 1.2)
        n = np.clip((s - 0.15) / 0.55, 0, 1)
        mk = cv2.GaussianBlur(m[k].astype(np.float32), (0, 0), 1.0)
        v = np.where(mk > 0.5, 0.02 + 0.98 * n, 0.0)[y0:y1, x0:x1]
        tiles.append(cv2.resize(v, None, fx=f, fy=f, interpolation=cv2.INTER_AREA))
    h, w = tiles[0].shape
    cols = int(np.ceil(np.sqrt(len(tiles) * h / w)))
    rows = int(np.ceil(len(tiles) / cols))
    atlas = np.zeros((rows * h, cols * w), np.uint8)
    for k, t in enumerate(tiles):
        r, c = divmod(k, cols)
        atlas[r * h:(r + 1) * h, c * w:(c + 1) * w] = (t * 255).round().astype(np.uint8)
    Image.fromarray(atlas).save(os.path.join(out, "slices.png"), optimize=True)
    # brain extent in mm, for the placement next to the tractography
    cy, cx = (ys.min() + ys.max()) / 2 - y0, (xs.min() + xs.max()) / 2 - x0
    meta = {"n": len(tiles), "cols": cols, "rows": rows, "w": w, "h": h, "px_mm": OUT_MM, "slice_mm": SLICE_MM,
            "brain": {"width_mm": float((xs.max() - xs.min()) * PX_MM), "height_mm": float((ys.max() - ys.min()) * PX_MM),
                      "length_mm": float((zs.max() - zs.min() + 1) * SLICE_MM),
                      "center_px": [float(cx * f), float(cy * f)]},
            "note": "slice 0 = most anterior; image left = subject's right (radiological, as in FSLeyes)"}
    json.dump(meta, open(os.path.join(out, "slices.json"), "w"), indent=1)
    print(meta, atlas.shape, os.path.getsize(os.path.join(out, "slices.png")) // 1024, "KB")
