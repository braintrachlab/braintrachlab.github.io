"""Pack the coronal slices of a T1 volume (NIfTI) into one texture for the atlas opening.
The browser draws them as Dejerine-style sections (assets/js/atlas.js, 'mri' opening).

usage: python3 pack_nifti.py <T1.nii.gz> <output folder (assets/atlas/mri)> [--mask brainmask.nii.gz]
"""
import sys, os, json
import numpy as np, cv2, nibabel as nib
from scipy import ndimage as ndi
from PIL import Image

UP = 1.5                                     # in-plane upsampling of the stored slices

def brain_mask(t1, vox):
    s = ndi.gaussian_filter(t1, 0.7)
    tissue = (s > 0.45) & (s < 1.25)           # t1 normalised: white matter = 1, grey ~0.68; excludes fat
    er = ndi.distance_transform_edt(tissue, sampling=vox) > 4.5
    lab, n = ndi.label(er); sz = np.bincount(lab.ravel()); sz[0] = 0
    core = lab == np.argmax(sz)
    m = (ndi.distance_transform_edt(~core, sampling=vox) <= 5.2) & (s > 0.40)
    m = ndi.binary_closing(m, iterations=2)
    for j in range(m.shape[1]): m[:, j, :] = ndi.binary_fill_holes(m[:, j, :])
    return m

if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    img = nib.as_closest_canonical(nib.load(src))           # RAS: x right, y anterior, z superior
    vox = img.header.get_zooms()[:3]
    t1 = np.asarray(img.dataobj, dtype=np.float32)
    t1 = np.clip(t1, 0, None)
    # white matter = 1 (upper part of the brain-tissue intensities)
    wm = np.percentile(t1[t1 > np.percentile(t1, 50)], 85)
    t1 /= wm
    if "--mask" in sys.argv:
        m = np.asarray(nib.as_closest_canonical(nib.load(sys.argv[sys.argv.index("--mask") + 1])).dataobj) > 0
    else:
        m = brain_mask(t1, vox)
    np.save(os.path.join(out, "_mask_debug.npy"), m) if "--debug" in sys.argv else None
    xs, ys, zs = np.where(m)
    x0, x1 = max(xs.min() - 3, 0), min(xs.max() + 4, m.shape[0])
    z0, z1 = max(zs.min() - 3, 0), min(zs.max() + 4, m.shape[2])
    print("mask bbox x", xs.min(), xs.max(), "y", ys.min(), ys.max(), "z", zs.min(), zs.max(), "of", m.shape, flush=True)
    slices = list(range(ys.max(), ys.min() - 1, -1))        # front -> back
    tiles = []
    for j in slices:
        a = t1[x0:x1, j, z0:z1]                              # (x, z)
        mk = m[x0:x1, j, z0:z1].astype(np.float32)
        a = np.ascontiguousarray(a[::-1, ::-1].T)                                  # rows: top -> bottom; columns: subject right -> left
        mk = np.ascontiguousarray(mk[::-1, ::-1].T)
        a = cv2.resize(a, None, fx=UP, fy=UP, interpolation=cv2.INTER_CUBIC)
        mk = cv2.resize(mk, None, fx=UP, fy=UP, interpolation=cv2.INTER_LINEAR)
        n = np.clip((a - 0.30) / 0.80, 0, 1)                 # grey matter ~0.47, white matter ~0.88
        tiles.append(np.where(mk > 0.5, 0.02 + 0.98 * n, 0.0))
    h, w = tiles[0].shape
    cols = int(np.ceil(np.sqrt(len(tiles) * h / w)))
    rows = int(np.ceil(len(tiles) / cols))
    atlas = np.zeros((rows * h, cols * w), np.uint8)
    for k, t in enumerate(tiles):
        r, c = divmod(k, cols)
        atlas[r * h:(r + 1) * h, c * w:(c + 1) * w] = (t * 255).round().astype(np.uint8)
    os.makedirs(out, exist_ok=True)
    Image.fromarray(atlas).save(os.path.join(out, "slices.png"), optimize=True)
    px = vox[0] / UP
    cx = ((x1 - 1) - (xs.min() + xs.max()) / 2) * UP        # column of the brain's centre (x)
    meta = {"n": len(tiles), "cols": cols, "rows": rows, "w": w, "h": h, "px_mm": float(px), "slice_mm": float(vox[1]),
            "brain": {"width_mm": float((xs.max() - xs.min() + 1) * vox[0]), "height_mm": float((zs.max() - zs.min() + 1) * vox[2]),
                      "length_mm": float(len(slices) * vox[1]), "center_px": [float(cx), 0.0],
                      "top_row": float(((z1 - 1) - zs.max()) * UP)},
            "source": os.path.basename(src).split("_", 1)[-1],
            "note": "slice 0 = most anterior; image left = subject's right (radiological)"}
    json.dump(meta, open(os.path.join(out, "slices.json"), "w"), indent=1)
    print(meta, atlas.shape, os.path.getsize(os.path.join(out, "slices.png")) // 1024, "KB")
