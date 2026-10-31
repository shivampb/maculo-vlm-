import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from maculo.api import create_app
from maculo.config import Settings
from maculo.engine import Segmentation


class FakeEngine:
    """Stands in for the real models: outlines a square around the first point
    and always ranks the labels in the order given."""

    def __init__(self):
        self.ready = True
        self.device = "cpu"
        self.embed_calls = 0
        self.last_classified = None

    def load(self):
        self.ready = True

    def embed(self, img):
        self.embed_calls += 1
        return "embedding"

    def segment(self, img, embedding, points, mode, box=None):
        assert embedding == "embedding"
        W, H = img.size
        mask = np.zeros((H, W), bool)
        self.last_box = box
        if box is not None:
            x0, y0, x1, y1 = (int(v) for v in box)
            mask[y0:y1, x0:x1] = True
            return Segmentation(mask, 0.9, mask.astype(np.float32))
        p = points[0]
        r = {"small": 5, "large": 30}.get(mode, 15)
        mask[max(int(p.y) - r, 0) : int(p.y) + r, max(int(p.x) - r, 0) : int(p.x) + r] = True
        return Segmentation(mask, 0.95, mask.astype(np.float32))

    def classify(self, img, labels, top_k):
        self.last_classified = img.size
        scores = np.linspace(1, 0.2, len(labels))
        scores = scores / scores.sum()
        return list(zip(labels, scores.tolist()))[:top_k]


def jpeg_bytes(w=200, h=120, color=(200, 150, 140)):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
def engine():
    return FakeEngine()


@pytest.fixture
def settings():
    return Settings(max_upload_mb=1, uploads_per_minute=5, session_capacity=3)


@pytest.fixture
def client(settings, engine):
    with TestClient(create_app(settings, engine)) as c:
        yield c


@pytest.fixture
def image_id(client):
    r = client.post("/api/v1/images", files={"image": ("a.jpg", jpeg_bytes(), "image/jpeg")})
    assert r.status_code == 201, r.text
    return r.json()["image_id"]
