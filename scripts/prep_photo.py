"""
Prepare a portrait photo for clean ASCII conversion:
  1. remove the background (rembg) so the subject is isolated
  2. boost LOCAL contrast (CLAHE) so a flatly-lit face gains highlights and
     shadows -- this is what turns a dark blob into a recognizable face
  3. composite the subject onto pure white so the background reads as blank
     (white -> spaces in the ascii ramp)

Output: source-prepped.png (grayscale), consumed by make_ascii_svg.py.
Run once whenever the source photo changes; the ascii SVG itself is static.

    python scripts/prep_photo.py <input.jpg> [output.png]
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image
from rembg import remove

HERE = os.path.dirname(os.path.abspath(__file__))
INP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "source-photo.jpg")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "source-prepped.png")

# 1. cut out the subject
cut = remove(Image.open(INP).convert("RGBA"))
rgb = np.array(cut.convert("RGB"))
alpha = np.array(cut.split()[-1])                 # 0 = background

# 1b. bilateral filter to sharpen edges while keeping skin smooth
rgb = cv2.bilateralFilter(rgb, d=9, sigmaColor=50, sigmaSpace=50)

# 2. local-contrast the luminance (CLAHE) — stronger clip for more face detail
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(6, 6))
gray = clahe.apply(gray)

# apply a second mild CLAHE pass at finer tile to pull out micro-detail (glasses, eyes)
clahe2 = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
gray = clahe2.apply(gray)

# global scale: slightly boost contrast, minimal lift so darks stay dark
gray = cv2.convertScaleAbs(gray, alpha=1.15, beta=8)

# 3. paste onto white using the alpha mask (feathered a hair to avoid a halo)
mask = (alpha.astype(np.float32) / 255.0)
mask = cv2.GaussianBlur(mask, (0, 0), 1.0)
out = gray.astype(np.float32) * mask + 255.0 * (1.0 - mask)
out = np.clip(out, 0, 255).astype(np.uint8)

# 4. Auto-crop to bounding box of the subject to center them properly
coords = cv2.findNonZero(alpha)
if coords is not None:
    x, y, w, h = cv2.boundingRect(coords)
    # Add a small margin
    margin = int(max(w, h) * 0.05)
    x = max(0, x - margin)
    y = max(0, y - margin)
    w = min(out.shape[1] - x, w + margin * 2)
    h = min(out.shape[0] - y, h + margin * 2)
    out = out[y:y+h, x:x+w]

# 5. ── Glasses / eye zone targeted enhancement ─────────────────────────────
# The glasses frames and eyes need extra separation. Apply aggressive
# sharpening + micro-tile CLAHE only to the y = 30%–53% vertical band,
# then feather-blend it back so no hard seam appears at the boundaries.
h_img, w_img = out.shape
ey0 = int(h_img * 0.30)   # top of glasses band
ey1 = int(h_img * 0.53)   # bottom of glasses band (covers frames + eyes)

band = out[ey0:ey1, :].astype(np.float32)

# a) Aggressive unsharp mask: makes glass frames snap to black, pupils pop
blur_band = cv2.GaussianBlur(band, (0, 0), 1.2)
sharp_band = np.clip(band * 3.0 - blur_band * 2.0, 0, 255).astype(np.uint8)

# b) Micro-tile CLAHE on the sharpened band (2×2 tiles catch tiny frame edges)
clahe_eye = cv2.createCLAHE(clipLimit=7.0, tileGridSize=(2, 2))
enhanced_band = clahe_eye.apply(sharp_band)

# c) Second very-fine CLAHE pass to deepen the lens-vs-frame contrast further
clahe_eye2 = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(2, 2))
enhanced_band = clahe_eye2.apply(enhanced_band)

# d) Feather blend at top+bottom 18% of the band to avoid a hard edge seam
feather = int((ey1 - ey0) * 0.18)
alpha_mask = np.ones((ey1 - ey0, w_img), dtype=np.float32)
for i in range(feather):
    t = i / feather                          # 0.0 → 1.0
    alpha_mask[i, :]              = t        # fade in at top
    alpha_mask[ey1 - ey0 - 1 - i, :] = t   # fade in at bottom

out[ey0:ey1, :] = np.clip(
    enhanced_band.astype(np.float32) * alpha_mask
    + out[ey0:ey1, :].astype(np.float32) * (1.0 - alpha_mask),
    0, 255
).astype(np.uint8)
# ─────────────────────────────────────────────────────────────────────────────

Image.fromarray(out, mode="L").save(OUT)
print("wrote", OUT, out.shape)
