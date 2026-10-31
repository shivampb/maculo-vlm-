<p align="center"><img src="brand/png/maculo-logo.png" alt="Maculo" width="320"></p>

<p align="center"><b>A closer look at skin spots.</b><br>
Outline a spot in a photo, then compare it with the conditions you choose.</p>

> **Research preview, not a medical device.** Maculo can't diagnose, detect or rule
> out any condition. Scores only rank the conditions on your list. The matching
> model is licensed for **non-commercial research only** (CC BY-NC-ND 4.0).

---

## What it does

1. **Outline.** Click a spot, or drag a box around a small one. The Segment Anything
   model (SAM) draws its outline. Use **+ Add area** / **− Remove area** to refine it.
2. **Compare.** A vision-language model trained on skin images scores the outlined
   area against each condition you've selected (55 presets in 7 groups, plus your own).
3. **Read honestly.** You get the closest matches, a plain confidence level, and notes
   when the result is weak, the outline looks off, or there's no "healthy skin" baseline.

Photos are kept in memory only (never written to disk) and forgotten after 15
minutes, or straight away when you start over.

## Quick start (Windows)

If the `venv` folder and `models/sam` are already set up, **double-click `start.bat`**.
Your browser opens at <http://127.0.0.1:8000>. The first start takes up to a minute
while the models load. Close the window to stop Maculo.

## Setup from scratch

You need Python 3.10–3.12. An NVIDIA GPU is optional; it works on CPU, just slower.

```bash
python -m venv venv
```

```bash
venv\Scripts\activate
```

Install PyTorch. With an NVIDIA GPU:

```bash
pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
```

Or CPU only:

```bash
pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu
```

Then the rest:

```bash
pip install -r requirements.txt
```

### Models

- **SAM** must be in `models/sam/` (`config.json`, `model.safetensors`,
  `preprocessor_config.json`, `processor_config.json`). Any Hugging Face
  `SamModel` checkpoint works, e.g. `facebook/sam-vit-base`.
- **The matching model** (`Xieji-Li/MAGEN-O-MAKE`) downloads from Hugging Face on
  the first run and is cached after that.

### Run

```bash
python -m maculo
```

Open <http://127.0.0.1:8000>. Interactive API docs are at <http://127.0.0.1:8000/docs>.

## Settings

Copy `.env.example` to `.env` and change what you need. The useful ones:

| Setting | Default | What it does |
|---|---|---|
| `MACULO_HOST` | `127.0.0.1` | Use `0.0.0.0` to open Maculo to other devices on your network |
| `MACULO_PORT` | `8000` | Port |
| `MACULO_DEVICE` | `auto` | `cuda`, `cpu`, or pick automatically |
| `MACULO_MAX_UPLOAD_MB` | `15` | Largest photo accepted |
| `MACULO_UPLOADS_PER_MINUTE` | `30` | Per-visitor upload limit |
| `MACULO_SESSION_TTL_S` | `900` | How long an idle photo is kept in memory |
| `MACULO_ENABLE_DOCS` | `true` | Show `/docs` |

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/images` | Upload a photo (multipart `image`). Runs the slow SAM encoder once. Returns `image_id`. |
| `POST` | `/api/v1/analyze` | JSON: `image_id`, `points` and/or `box`, `labels`, `mask_mode`, `crop`, `top_k`. Fast; call it on every click. |
| `DELETE` | `/api/v1/images/{id}` | Forget a photo now. |
| `GET` | `/api/v1/meta` | Version, readiness, condition presets, limits. |
| `GET` | `/healthz`, `/readyz` | Liveness, and whether the models have loaded. |

Coordinates are fractions of the image (0 to 1). Full schemas are at `/docs`.

## Project layout

```
maculo/          the app: config, models (engine.py), API (api.py), image helpers
static/          the web app (HTML, CSS, JS, icons). No build step
brand/           brand kit: logos, colors, type, board, guidelines (BRAND.md)
tests/           pytest suite. Uses a fake engine, so it runs in seconds without models
start.bat        double-click launcher for Windows
```

## Tests

```bash
pip install -r requirements-dev.txt
```

```bash
python -m pytest
```

## Going online later

Maculo runs as one process per GPU (each process loads its own models). To put it
on the internet, run it behind a reverse proxy with HTTPS (Caddy or nginx), set
`MACULO_HOST=0.0.0.0` and `MACULO_TRUST_PROXY=true`, and keep the non-commercial
model license in mind.

## Brand

See [`brand/BRAND.md`](brand/BRAND.md) and open `brand/index.html` for the board.
After editing a logo SVG, run `python brand/export.py` to regenerate every PNG and icon.
