from conftest import jpeg_bytes

LABELS = ["acne", "eczema", "healthy skin"]


def analyze(client, image_id, **kw):
    body = {"image_id": image_id, "points": [{"x": 0.5, "y": 0.5}], "labels": LABELS}
    body.update(kw)
    return client.post("/api/v1/analyze", json=body)


def test_health_and_meta(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json()["status"] == "ready"
    meta = client.get("/api/v1/meta").json()
    assert meta["name"] == "Maculo"
    assert "healthy skin" in meta["default_selection"]
    assert meta["label_groups"]


def test_home_has_security_headers(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Maculo" in r.text
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"


def test_upload_returns_size(client):
    r = client.post("/api/v1/images", files={"image": ("a.jpg", jpeg_bytes(300, 100), "image/jpeg")})
    assert r.status_code == 201
    d = r.json()
    assert (d["width"], d["height"]) == (300, 100)
    assert r.headers["cache-control"] == "no-store"


def test_upload_downscales_large_images(client):
    r = client.post("/api/v1/images", files={"image": ("a.jpg", jpeg_bytes(2048, 1024), "image/jpeg")})
    assert (r.json()["width"], r.json()["height"]) == (1024, 512)


def test_upload_rejects_non_images(client):
    r = client.post("/api/v1/images", files={"image": ("a.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 400
    assert "could not be read" in r.json()["detail"]


def test_upload_rejects_too_large(client):
    big = b"\xff" * (1024 * 1024 + 10)
    r = client.post("/api/v1/images", files={"image": ("a.jpg", big, "image/jpeg")})
    assert r.status_code == 413


def test_upload_rate_limit(client):
    codes = [
        client.post("/api/v1/images", files={"image": ("a.jpg", jpeg_bytes(), "image/jpeg")}).status_code
        for _ in range(6)
    ]
    assert codes[:5] == [201] * 5 and codes[5] == 429


def test_analyze_reuses_embedding(client, engine, image_id):
    for x in (0.2, 0.5, 0.8):
        r = analyze(client, image_id, points=[{"x": x, "y": 0.5}])
        assert r.status_code == 200, r.text
    assert engine.embed_calls == 1


def test_analyze_result_shape(client, image_id):
    d = analyze(client, image_id).json()
    assert [p["label"] for p in d["predictions"]] == LABELS
    o = d["outline"]
    assert 0 <= o["box"][0] < o["box"][2] <= 1
    assert o["polygons"] and len(o["polygons"][0]) >= 3
    assert 0 < o["area"] < 1
    assert d["classified_region"] == "outline"
    assert d["confidence"] in {"high", "moderate", "low"}


def test_crop_classifies_outline_only(client, engine, image_id):
    analyze(client, image_id, crop=True)
    assert engine.last_classified[0] < 200
    analyze(client, image_id, crop=False)
    assert engine.last_classified == (200, 120)


def test_analyze_validates_input(client, image_id):
    assert analyze(client, image_id, labels=["acne"]).status_code == 422
    assert analyze(client, image_id, labels=["acne", " ", "acne"]).status_code == 400
    assert analyze(client, image_id, labels=["acne", "x" * 200]).status_code == 400
    assert analyze(client, image_id, points=[{"x": 1.5, "y": 0.5}]).status_code == 422
    assert analyze(client, image_id, points=[{"x": 0.5, "y": 0.5, "include": False}]).status_code == 400
    assert analyze(client, image_id, points=[]).status_code == 400
    assert analyze(client, image_id, points=[], box=[0.5, 0.5, 0.501, 0.6]).status_code == 400
    assert analyze(client, image_id, points=[], box=[0.1, 0.2]).status_code == 422
    assert analyze(client, image_id, mask_mode="huge").status_code == 422


def test_missing_healthy_baseline_is_noted(client, image_id):
    d = analyze(client, image_id, labels=["acne", "eczema"]).json()
    assert any("healthy skin" in n for n in d["notes"])


def test_unknown_and_deleted_images(client, image_id):
    assert analyze(client, "doesnotexist").status_code == 404
    assert client.delete(f"/api/v1/images/{image_id}").status_code == 204
    assert analyze(client, image_id).status_code == 404


def test_not_ready_returns_503(settings, engine):
    from fastapi.testclient import TestClient

    from maculo.api import create_app

    engine.ready = False
    engine.load = lambda: None  # stays "loading"
    with TestClient(create_app(settings, engine)) as c:
        assert c.get("/readyz").status_code == 503
        r = c.post("/api/v1/images", files={"image": ("a.jpg", jpeg_bytes(), "image/jpeg")})
        assert r.status_code == 503


def test_box_prompt(client, engine, image_id):
    r = analyze(client, image_id, points=[], box=[0.25, 0.25, 0.75, 0.75])
    assert r.status_code == 200, r.text
    assert engine.last_box == (50.0, 30.0, 150.0, 90.0)
    box = r.json()["outline"]["box"]
    assert abs(box[0] - 0.25) < 0.01 and abs(box[2] - 0.75) < 0.01


def test_static_assets_are_versioned(client):
    html = client.get("/").text
    assert "/static/css/app.css?v=" in html and "/static/js/app.js?v=" in html
    r = client.get("/static/css/app.css?v=abc")
    assert "immutable" in r.headers["cache-control"]


def test_heatmap_is_optional_png(client, image_id):
    d = analyze(client, image_id).json()
    assert d["outline"]["heatmap"].startswith("data:image/png;base64,")
    d = analyze(client, image_id, heatmap=False).json()
    assert d["outline"]["heatmap"] is None
