"""Builds assets/atlas/atlas.bin + atlas.json from the .trk files in tools/atlas.
Each tract: a random subset of streamlines (max N), resampled every STEP mm, stored as int16 (0.1 mm).
usage: python3 tools/atlas/build_atlas.py"""
import os, json, glob, warnings
import numpy as np, nibabel as nib
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "assets", "atlas")
# id, file, max streamlines
TRACTS = [("cc", "CC.trk", 1700), ("atr", "anterior_thalamic_radiations.trk", 400),
          ("fat", "FAT.trk", 600), ("ifof", "IFOF.trk", 900), ("uf", "UF.trk", 600)]
STEP = 1.6
rng = np.random.default_rng(1)
def resample(s, step):
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(s, axis=0), axis=1))]
    if d[-1] < 2 * step: return None
    t = np.arange(0, d[-1], step)
    return np.stack([np.interp(t, d, s[:, i]) for i in range(3)], 1)
allp, meta, counts, coords = [], [], [], []
for tid, fn, nmax in TRACTS:
    sl = list(nib.streamlines.load(os.path.join(HERE, fn)).streamlines)
    if len(sl) > nmax: sl = [sl[i] for i in sorted(rng.choice(len(sl), nmax, replace=False))]
    lines = [r for r in (resample(np.asarray(s, float), STEP) for s in sl) if r is not None]
    meta.append({"id": tid, "lines": len(lines), "points": int(sum(len(l) for l in lines))})
    for l in lines:
        counts.append(len(l)); coords.append(l)
coords_all = np.concatenate(coords)
center = (coords_all.min(0) + coords_all.max(0)) / 2
q = np.round((coords_all - center) * 10).astype(np.int16)
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, "atlas.bin"), "wb").write(np.array(counts, np.uint16).tobytes() + q.tobytes())
json.dump({"tracts": meta, "scale": 0.1, "radius": float(np.linalg.norm(coords_all - center, axis=1).max())},
          open(os.path.join(OUT, "atlas.json"), "w"), indent=1)
print(meta, "total points", len(q), "bytes", os.path.getsize(os.path.join(OUT, "atlas.bin")))
