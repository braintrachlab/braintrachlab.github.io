"""Align an annotated copy of the plate (any size/crop) to plate-hires.png and write guides.png:
the plate with the red/green/blue lines transferred. Filled green label boxes and black arrows are ignored.
usage: register_guides.py plate-hires.png annotated.png guides.png"""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from scipy.optimize import minimize
PL, AN, OUT = sys.argv[1:4]
a = 1 - np.asarray(Image.open(PL).convert("L")).astype(float) / 255
b3 = np.asarray(Image.open(AN).convert("RGB")).astype(float) / 255
mx, mn = b3.max(-1), b3.min(-1); sat = (mx - mn) / (mx + 1e-6); bl = b3.mean(-1)
paper = np.median(bl[(sat < 0.3) & (bl > 0.7)])
b = np.clip(1 - bl / paper, 0, 1) * (sat < 0.35)
k = 8
As = ndi.zoom(ndi.gaussian_filter(a, k / 2), 1 / k); Bs = ndi.zoom(ndi.gaussian_filter(b, k / 2), 1 / k)
yy, xx = np.mgrid[0:As.shape[0], 0:As.shape[1]].astype(float)
def ncc(p):
    s, tx, ty = p
    w = ndi.map_coordinates(Bs, [(yy - ty) / s, (xx - tx) / s], order=1, cval=0); m = w > 0
    x = As[m] - As[m].mean(); y = w[m] - w[m].mean()
    return -(x * y).sum() / np.sqrt((x * x).sum() * (y * y).sum() + 1e-9)
s0 = np.sqrt((a > 0.3).sum() / max((b > 0.3).sum(), 1))
best = min(((ncc((s, tx, ty)), (s, tx, ty)) for s in np.linspace(s0 * 0.75, s0 * 1.3, 23)
            for tx in range(-80, 120, 8) for ty in range(-80, 100, 8)), key=lambda t: t[0])
r = minimize(ncc, best[1], method="Powell"); s, tx, ty = r.x; tx *= k; ty *= k
print("registration ncc", round(-r.fun, 3), "scale", round(s, 4), "shift", round(tx), round(ty))
np.save(OUT + ".reg.npy", np.array([s, tx, ty]))
H, W = b3.shape[:2]
R, G, B = b3[..., 0], b3[..., 1], b3[..., 2]
hue = np.degrees(np.arctan2(np.sqrt(3) * (G - B), 2 * R - G - B)) % 360
col = sat > 0.35
cls = {"red": col & ((hue < 25) | (hue > 335)), "green": col & (hue > 80) & (hue < 160), "blue": col & (hue > 180) & (hue < 235)}
lab, n = ndi.label(cls["green"]); boxes = np.zeros_like(cls["green"])
for i, sl in enumerate(ndi.find_objects(lab), 1):
    hh, ww = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
    if (lab[sl] == i).sum() > 0.35 * hh * ww and hh > 25: boxes[sl] = True
cls["green"] &= ~ndi.binary_dilation(boxes, iterations=4)
P = np.asarray(Image.open(PL).convert("RGB")).copy()
Hp, Wp = P.shape[:2]
yy, xx = np.mgrid[0:Hp, 0:Wp].astype(np.float32)
for k_, c in (("red", (225, 30, 40)), ("green", (40, 190, 60)), ("blue", (60, 140, 240))):
    w = ndi.map_coordinates(cls[k_].astype(np.float32), [(yy - ty) / s, (xx - tx) / s], order=1, cval=0) > 0.3
    P[w] = c
Image.fromarray(P).save(OUT, optimize=True)
