"""
Prepare a portrait photo for clean ASCII conversion.

Steps:
  1. Remove background (rembg) — isolates the subject on transparent bg
  2. Apply bilateral filter to smooth flat regions while keeping edges crisp
  3. CLAHE (adaptive contrast) to make face features pop across the ramp
  4. Composite onto pure white so background = spaces in ASCII ramp
  5. Auto-crop to subject bounding box
  6. Sharpening pass on the full image (unsharp mask) for edge clarity

This version is tuned for illustration/vector-style source images:
 - flat tones need less aggressive CLAHE (they don't need noise suppression)
 - edges are already sharp so unsharp mask is moderate
 - hair region needs contrast boost to separate strand details from shadow
 - skin-to-shadow gradient needs to be stretched so midtones don't flatten

Run once whenever the source photo changes.
    python scripts/prep_photo.py [input.png] [output.png]
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageFilter
from rembg import remove

HERE = os.path.dirname(os.path.abspath(__file__))
INP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "source-photo.png")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "source-prepped.png")

print(f"Loading: {INP}")

# ── Step 1: Remove background ────────────────────────────────────────────────
pil_src = Image.open(INP).convert("RGBA")
print(f"  Source size: {pil_src.size}")
cut = remove(pil_src)
alpha = np.array(cut.split()[-1])                   # 0 = background, 255 = subject
rgb  = np.array(cut.convert("RGB"))

# ── Step 2: Bilateral filter — smooth skin flats, preserve edges ─────────────
# d=9 is good for illustrations. sigmaColor/sigmaSpace higher than photo to avoid
# blurring the already-sharp outlines.
rgb = cv2.bilateralFilter(rgb, d=9, sigmaColor=40, sigmaSpace=40)

# ── Step 3: Convert to grayscale ─────────────────────────────────────────────
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

# ── Step 4: CLAHE — adaptive contrast boost ──────────────────────────────────
# clipLimit=3.0 is enough for flat illustration tones (4.0+ causes haloing on
# clean flat fills). tileGridSize=(8,8) works well for illustration scale.
clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
gray = clahe.apply(gray)

# Second finer CLAHE pass to bring out hair strand detail and face contour
clahe2 = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
gray = clahe2.apply(gray)

# ── Step 5: Global brightness/contrast stretch ───────────────────────────────
# alpha>1 = more contrast, beta>0 = lift shadows slightly so they map to
# darker ASCII chars rather than flattening to black.
gray = cv2.convertScaleAbs(gray, alpha=1.2, beta=6)

# ── Step 6: Composite onto white using alpha mask ────────────────────────────
# Feather the mask edge slightly to avoid hard pixel-jagged silhouette
mask = alpha.astype(np.float32) / 255.0
mask = cv2.GaussianBlur(mask, (0, 0), 0.8)          # soft feather
out  = gray.astype(np.float32) * mask + 255.0 * (1.0 - mask)
out  = np.clip(out, 0, 255).astype(np.uint8)

# ── Step 7: Auto-crop tight to subject bounding box ──────────────────────────
coords = cv2.findNonZero(alpha)
if coords is not None:
    x, y, w, h = cv2.boundingRect(coords)
    margin = int(max(w, h) * 0.05)                   # 5% margin on each side
    x = max(0, x - margin)
    y = max(0, y - margin)
    w = min(out.shape[1] - x, w + margin * 2)
    h = min(out.shape[0] - y, h + margin * 2)
    out = out[y:y+h, x:x+w]
    print(f"  Cropped to: {out.shape[1]}×{out.shape[0]}")

# ── Step 8: Full-image unsharp mask ─────────────────────────────────────────
# Applied AFTER crop so we sharpen only the subject area.
# radius=1.5, percent=120 gives crispness without over-sharpening illustrations.
pil_out = Image.fromarray(out, mode="L")
pil_out = pil_out.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=3))
out = np.array(pil_out)

# ── Step 9: Hair / top region targeted contrast ──────────────────────────────
# Illustrations often have very flat dark hair. Boost contrast in the top 40%
# of the cropped image so hair strands separate from each other in the ramp.
h_img, w_img = out.shape
hair_end = int(h_img * 0.42)

hair_band = out[0:hair_end, :]
# CLAHE on hair only — brings out strand separation
clahe_hair = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(3, 3))
hair_enhanced = clahe_hair.apply(hair_band)

# Feather blend so there's no hard line at the hair/face boundary
feather = int(hair_end * 0.20)
alpha_hair = np.ones((hair_end, w_img), dtype=np.float32)
for i in range(feather):
    t = i / feather
    alpha_hair[hair_end - 1 - i, :] = t             # fade out at bottom

out[0:hair_end, :] = np.clip(
    hair_enhanced.astype(np.float32) * alpha_hair
    + out[0:hair_end, :].astype(np.float32) * (1.0 - alpha_hair),
    0, 255
).astype(np.uint8)

# ── Write output ─────────────────────────────────────────────────────────────
Image.fromarray(out, mode="L").save(OUT)
print(f"Wrote: {OUT}  shape={out.shape}")
