import numpy as np
import pytest
from PIL import Image

from conftest import jpeg_bytes
from maculo.engine import pick_mask
from maculo.imaging import ImageError, bbox, contours, crop_to_mask, decode_image
from maculo.store import ImageSession, ImageStore, RateLimiter


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_decode_rejects_tiny_and_gif():
    with pytest.raises(ImageError):
        decode_image(jpeg_bytes(10, 10), 1024)
    import io

    buf = io.BytesIO()
    Image.new("RGB", (64, 64)).save(buf, "GIF")
    with pytest.raises(ImageError, match="JPG, PNG or WEBP"):
        decode_image(buf.getvalue(), 1024)


def test_bbox_contours_and_crop():
    m = np.zeros((50, 80), bool)
    m[10:20, 30:60] = True
    assert bbox(m) == (30, 10, 59, 19)
    assert bbox(np.zeros((5, 5), bool)) is None
    polys = contours(m)
    assert len(polys) == 1
    xs = [p[0] for p in polys[0]]
    assert min(xs) == 30 and max(xs) == 59
    crop = crop_to_mask(Image.new("RGB", (80, 50)), bbox(m))
    assert crop.size[0] < 80


def test_pick_mask_modes():
    masks = np.zeros((3, 4, 4), bool)
    masks[0, :2, :2] = True  # area 4
    masks[1, :, :] = True  # area 16
    masks[2, :1, :1] = True  # area 1
    scores = np.array([0.9, 0.5, 0.7])
    assert pick_mask(masks, scores, "best") == 0
    assert pick_mask(masks, scores, "large") == 1
    assert pick_mask(masks, scores, "small") == 2


def test_store_expiry_and_capacity():
    clock = Clock()
    store = ImageStore(capacity=2, ttl_s=10, clock=clock)
    img = Image.new("RGB", (4, 4))
    a = store.put(ImageSession(img, None))
    b = store.put(ImageSession(img, None))
    c = store.put(ImageSession(img, None))
    assert store.get(a) is None and store.get(b) and store.get(c)
    clock.t = 11
    assert store.get(b) is None and len(store) == 0


def test_rate_limiter_window():
    clock = Clock()
    rl = RateLimiter(2, clock=clock)
    assert rl.allow("ip") and rl.allow("ip") and not rl.allow("ip")
    assert rl.allow("other")
    clock.t = 61
    assert rl.allow("ip")


def test_crop_keeps_context_for_tiny_spots():
    img = Image.new("RGB", (1000, 800))
    crop = crop_to_mask(img, (500, 400, 505, 405))
    assert min(crop.size) >= 160  # 20% of the 800 px short edge
    edge = crop_to_mask(img, (0, 0, 4, 4))
    assert edge.size[0] >= 160 and edge.size[1] >= 160  # shifted inside the photo, not cut off
