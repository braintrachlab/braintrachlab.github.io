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
# tracts dissected in subject 102109 (diffusion space, 1.25 mm): converted to the AC-PC space of the sections
# and placed like the sections (assets/atlas/planes/sections.json). To add one: drop the .trk in tools/atlas
# and add a line here, then a card in content/tracts.txt.
TRACTS_102109 = [("fornix", "fornix.trk", 500)]
DTI2ACPC = np.array([-91.25, -127.25, -73.25])
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
# placement of subject 102109 in the atlas frame: the same translation the atlas page uses for the sections
sec = json.load(open(os.path.join(OUT, "planes", "sections.json")))
bb = np.array(sec["brain_box"]); c = coords_all - center
T = np.array([-(bb[0, 0] + bb[1, 0]) / 2, (c[:, 1].min() + c[:, 1].max()) / 2 - (bb[0, 1] + bb[1, 1]) / 2, c[:, 2].max() + 5 - bb[1, 2]])
for tid, fn, nmax in TRACTS_102109:
    sl = list(nib.streamlines.load(os.path.join(HERE, fn)).streamlines)
    if len(sl) > nmax: sl = [sl[i] for i in sorted(rng.choice(len(sl), nmax, replace=False))]
    lines = [r + DTI2ACPC + T + center for r in (resample(np.asarray(s, float), STEP) for s in sl) if r is not None]
    meta.append({"id": tid, "lines": len(lines), "points": int(sum(len(l) for l in lines)), "subject": "102109"})
    for l in lines:
        counts.append(len(l)); coords.append(l)
coords_all = np.concatenate(coords)
q = np.round((coords_all - center) * 10).astype(np.int16)
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, "atlas.bin"), "wb").write(np.array(counts, np.uint16).tobytes() + q.tobytes())
json.dump({"tracts": meta, "scale": 0.1, "center_rasmm": [round(float(c), 3) for c in center], "radius": float(np.linalg.norm(coords_all - center, axis=1).max())},
          open(os.path.join(OUT, "atlas.json"), "w"), indent=1)
print(meta, "total points", len(q), "bytes", os.path.getsize(os.path.join(OUT, "atlas.bin")))
