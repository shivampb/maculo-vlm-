"""HTTP API and static web app.

Flow: POST /api/v1/images once per photo (runs the SAM encoder), then
POST /api/v1/analyze for every click, which is fast.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import ROOT, Settings, get_settings
from .engine import Engine, Point, TorchEngine
from .imaging import ImageError, bbox, contours, crop_to_mask, decode_image, heatmap_png
from .labels import DEFAULT_SELECTION, LABEL_GROUPS
from .schemas import AnalyzeIn, AnalyzeOut, ImageOut, Meta, Outline, Prediction
from .store import ImageSession, ImageStore, RateLimiter

log = logging.getLogger("maculo.api")
STATIC = ROOT / "static"

CSP = (
    "default-src 'self'; "
    "img-src 'self' data: blob:; "
    "style-src 'self' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "script-src 'self'; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)


def versioned_index() -> str:
    """index.html with a content hash on each local asset link, so browsers can
    cache static files for a long time yet always fetch a changed file."""
    html = (STATIC / "index.html").read_text(encoding="utf-8")

    def stamp(m: re.Match) -> str:
        path = STATIC / m.group(1)
        if not path.is_file():
            return m.group(0)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:10]
        return f"/static/{m.group(1)}?v={digest}"

    return re.sub(r"/static/([\w/.-]+\.(?:css|js|svg|png))", stamp, html)


def interpret(preds, labels, outline, settings: Settings) -> tuple[str, list[str]]:
    """Turn raw scores into a plain confidence level and caveats for the reader."""
    top = preds[0][1]
    margin = top - (preds[1][1] if len(preds) > 1 else 0.0)
    notes: list[str] = []
    if outline.box is None:
        notes.append("No outline was found. Click directly on the spot.")
    elif outline.area > 0.6:
        notes.append(
            "The outline covers most of the photo. Click on the spot itself, or "
            "choose a smaller outline."
        )
    elif outline.score < 0.7:
        notes.append("The outline may not match the spot closely. Try another click.")
    if top < settings.low_confidence:
        notes.append(
            "No condition on your list is a strong match. The photo may show "
            "something that isn't listed."
        )
    elif margin < settings.low_margin:
        notes.append(f"“{preds[0][0]}” and “{preds[1][0]}” score almost the same.")
    if "healthy skin" not in {l.lower() for l in labels}:
        notes.append("Add “healthy skin” to the list to give the model a baseline.")
    return confidence_level(preds, settings), notes


def confidence_level(preds, settings: Settings) -> str:
    """High, moderate or low, from the top score and its lead over the runner-up."""
    top = preds[0][1]
    margin = top - (preds[1][1] if len(preds) > 1 else 0.0)
    if top < settings.low_confidence or margin < settings.low_margin:
        return "low"
    if top >= 0.7 and margin >= 0.2:
        return "high"
    return "moderate"


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = engine or TorchEngine(settings)
    store = ImageStore(settings.session_capacity, settings.session_ttl_s)
    limiter = RateLimiter(settings.uploads_per_minute)
    state = {"error": None}

    def load_models():
        try:
            engine.load()
        except Exception as e:  # surfaced through /readyz and /api/v1/meta
            state["error"] = str(e)
            log.exception("model loading failed")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if not engine.ready:
            # Load in the background so health checks answer while models load.
            threading.Thread(target=load_models, name="model-loader", daemon=True).start()
        yield

    app = FastAPI(
        title="Maculo",
        version=__version__,
        summary="Outline a skin spot and compare it with conditions you choose.",
        lifespan=lifespan,
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.enable_docs else None,
    )
    app.state.settings, app.state.engine, app.state.store = settings, engine, store

    app.add_middleware(GZipMiddleware, minimum_size=1024)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Content-Type"],
        )

    def client_ip(request: Request) -> str:
        if settings.trust_proxy and (fwd := request.headers.get("x-forwarded-for")):
            return fwd.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    @app.middleware("http")
    async def guard(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        t = time.perf_counter()
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > settings.max_upload_bytes + 64_000:
            response = JSONResponse(
                {"detail": f"The photo is larger than {settings.max_upload_mb:g} MB."},
                status_code=413,
            )
        else:
            try:
                response = await call_next(request)
            except Exception:
                log.exception("unhandled error [%s]", rid)
                response = JSONResponse(
                    {"detail": "Something went wrong on our side. Please try again."},
                    status_code=500,
                )
        path = request.url.path
        h = response.headers
        h["X-Request-ID"] = rid
        h["X-Content-Type-Options"] = "nosniff"
        h["Referrer-Policy"] = "no-referrer"
        h["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
        if not path.startswith(("/docs", "/openapi")):
            h["Content-Security-Policy"] = CSP
            h["X-Frame-Options"] = "DENY"
        if path.startswith("/api/"):
            h["Cache-Control"] = "no-store"
        elif path.startswith("/static/"):
            # Versioned links (?v=hash) never change; anything else revalidates hourly.
            versioned = "v" in request.query_params
            h["Cache-Control"] = "public, max-age=31536000, immutable" if versioned else "public, max-age=3600"
        if path.startswith("/api/"):
            log.info(
                "%s %s %d %.0fms [%s]",
                request.method, path, response.status_code,
                (time.perf_counter() - t) * 1000, rid,
            )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", [])[1:]) or "request"
        return JSONResponse(
            {"detail": f"Invalid {where}: {first.get('msg', 'bad value')}."},
            status_code=422,
        )

    def require_ready():
        if state["error"]:
            raise HTTPException(503, "The analysis models failed to load. Check the server log.")
        if not engine.ready:
            raise HTTPException(503, "The analysis models are still loading. Try again shortly.")

    # ---------- health ----------
    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    def readyz():
        if engine.ready:
            return {"status": "ready", "device": engine.device}
        status = "error" if state["error"] else "loading"
        return JSONResponse({"status": status, "error": state["error"]}, status_code=503)

    # ---------- API ----------
    @app.get("/api/v1/meta", response_model=Meta, tags=["info"])
    def meta():
        return Meta(
            name="Maculo",
            version=__version__,
            ready=engine.ready,
            device=engine.device,
            label_groups=LABEL_GROUPS,
            default_selection=DEFAULT_SELECTION,
            limits={
                "max_upload_mb": settings.max_upload_mb,
                "max_labels": settings.max_labels,
                "max_points": settings.max_points,
                "max_image_side": settings.max_image_side,
            },
        )

    @app.post("/api/v1/images", response_model=ImageOut, status_code=201, tags=["analysis"])
    def upload_image(request: Request, image: UploadFile = File(...)):
        """Upload a photo. Returns an id to use with /api/v1/analyze."""
        require_ready()
        if not limiter.allow(client_ip(request)):
            raise HTTPException(429, "Too many photos in a short time. Wait a minute and try again.")
        data = image.file.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(413, f"The photo is larger than {settings.max_upload_mb:g} MB.")
        try:
            img = decode_image(data, settings.max_image_side)
        except ImageError as e:
            raise HTTPException(400, str(e)) from None
        image_id = store.put(ImageSession(image=img, embedding=engine.embed(img)))
        return ImageOut(
            image_id=image_id,
            width=img.width,
            height=img.height,
            expires_in=settings.session_ttl_s,
        )

    @app.delete("/api/v1/images/{image_id}", status_code=204, tags=["analysis"])
    def delete_image(image_id: str):
        """Forget a photo now instead of waiting for it to expire."""
        store.delete(image_id)
        return Response(status_code=204)

    @app.post("/api/v1/analyze", response_model=AnalyzeOut, tags=["analysis"])
    def analyze(body: AnalyzeIn):
        """Outline the spot at the given points and rank the given conditions."""
        require_ready()
        labels = list(dict.fromkeys(l.strip() for l in body.labels if l.strip()))
        if len(labels) < 2:
            raise HTTPException(400, "Choose at least two conditions to compare.")
        if len(labels) > settings.max_labels:
            raise HTTPException(400, f"Choose at most {settings.max_labels} conditions.")
        if any(len(l) > settings.max_label_chars for l in labels):
            raise HTTPException(
                400, f"Keep each condition under {settings.max_label_chars} characters."
            )
        session = store.get(body.image_id)
        if session is None:
            raise HTTPException(404, "This photo has expired. Upload it again.")

        img = session.image
        W, H = img.size
        points = [Point(p.x * W, p.y * H, p.include) for p in body.points]
        box = None
        if body.box is not None:
            x0, y0, x1, y1 = (min(max(v, 0.0), 1.0) for v in body.box)
            if x1 - x0 < 0.005 or y1 - y0 < 0.005:
                raise HTTPException(400, "The box is too small. Drag a little wider around the spot.")
            box = (x0 * W, y0 * H, x1 * W, y1 * H)
        if box is None and not any(p.include for p in points):
            raise HTTPException(400, "Click the spot or drag a box around it.")

        t0 = time.perf_counter()
        seg = engine.segment(img, session.embedding, points, body.mask_mode, box)
        mask = seg.mask
        t1 = time.perf_counter()
        b = bbox(mask)
        outline = Outline(
            box=None if b is None else [b[0] / W, b[1] / H, (b[2] + 1) / W, (b[3] + 1) / H],
            polygons=contours(mask) if b else [],
            score=round(seg.score, 3),
            area=round(float(mask.mean()), 4),
            heatmap=heatmap_png(seg.confidence) if body.heatmap and seg.confidence is not None else None,
        )
        use_crop = body.crop and b is not None
        target = crop_to_mask(img, b) if use_crop else img
        preds = engine.classify(target, labels, body.top_k)
        t2 = time.perf_counter()

        level, notes = interpret(preds, labels, outline, settings)
        return AnalyzeOut(
            predictions=[Prediction(label=l, score=round(s, 4)) for l, s in preds],
            confidence=level,
            notes=notes,
            outline=outline,
            classified_region="outline" if use_crop else "full_image",
            timings_ms={
                "segment": round((t1 - t0) * 1000, 1),
                "classify": round((t2 - t1) * 1000, 1),
            },
        )

    # ---------- web app ----------
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", include_in_schema=False)
    def home():
        # Re-stamped on every load (a few small files to hash), so edits to the
        # web app reach browsers on a normal refresh without restarting the server.
        return HTMLResponse(versioned_index(), headers={"Cache-Control": "no-cache"})

    for name, media in [
        ("favicon.ico", "image/x-icon"),
        ("manifest.webmanifest", "application/manifest+json"),
        ("robots.txt", "text/plain"),
    ]:
        def serve(path=STATIC / name, media=media):
            return FileResponse(path, media_type=media)

        app.add_api_route(f"/{name}", serve, include_in_schema=False)

    return app
