"""Image decoding and mask geometry. Pure functions, no model code."""

from __future__ import annotations

import base64
import io

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}

# Refuse decompression bombs well before they reach the models.
Image.MAX_IMAGE_PIXELS = 60_000_000


class ImageError(ValueError):
    """The upload is not an image we can use. The message is safe to show users."""


def decode_image(data: bytes, max_side: int) -> Image.Image:
    """Decode, validate, orient and downscale an uploaded image to RGB."""
    if not data:
        raise ImageError("The file is empty.")
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        img.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError):
        raise ImageError("That file could not be read as an image.") from None
    if fmt not in ALLOWED_FORMATS:
        raise ImageError("Use a JPG, PNG or WEBP photo.")
    img = ImageOps.exif_transpose(img).convert("RGB")
    if min(img.size) < 32:
        raise ImageError("The photo is too small. Use one at least 32 pixels wide.")
    img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return img


def bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    """Inclusive pixel bounds (x0, y0, x1, y1) of a boolean mask, or None if empty."""
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def crop_to_mask(
    img: Image.Image,
    box: tuple[int, int, int, int],
    pad: float = 0.15,
    min_side: float = 0.2,
) -> Image.Image:
    """Crop around a lesion box with some surrounding skin for context.

    The crop is never smaller than `min_side` of the photo's shorter edge, so a
    tiny spot isn't blown up into a blurry patch the model can't read.
    """
    W, H = img.size
    x0, y0, x1, y1 = box
    p = pad * max(x1 - x0, y1 - y0, 16)
    side = max(x1 - x0 + 2 * p, y1 - y0 + 2 * p, min_side * min(W, H))
    cx, cy = (x0 + x1 + 1) / 2, (y0 + y1 + 1) / 2
    half_w = max(x1 - x0 + 1 + 2 * p, side) / 2
    half_h = max(y1 - y0 + 1 + 2 * p, side) / 2
    left = int(max(0, min(cx - half_w, W - 2 * half_w)))
    top = int(max(0, min(cy - half_h, H - 2 * half_h)))
    return img.crop((left, top, min(W, int(left + 2 * half_w)), min(H, int(top + 2 * half_h))))


def heatmap_png(confidence: np.ndarray, max_side: int = 384) -> str:
    """Encode a 0..1 confidence map as a small grayscale PNG data URL.

    The browser colors it and scales it up smoothly, so a low resolution is enough.
    """
    img = Image.fromarray((np.clip(confidence, 0, 1) * 255).astype(np.uint8), "L")
    img.thumbnail((max_side, max_side), Image.Resampling.BILINEAR)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def contours(mask: np.ndarray, min_frac: float = 0.0002) -> list[list[list[float]]]:
    """Outline a mask as polygons in pixel coordinates (outer rings and holes).

    Drawn with the even-odd fill rule, holes render as holes. Specks smaller
    than `min_frac` of the image are dropped so the outline stays clean.
    """
    min_area = max(12.0, min_frac * mask.size)
    m = mask.astype(np.uint8)
    found, _ = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    polys = []
    for c in found:
        if cv2.contourArea(c) < min_area:
            continue
        c = cv2.approxPolyDP(c, 0.8, True)
        if len(c) >= 3:
            polys.append([[float(x), float(y)] for x, y in c[:, 0, :]])
    return polys
