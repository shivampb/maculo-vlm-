<p align="center"><img src="brand/png/maculo-readme-banner.png" alt="Maculo: a closer look at skin spots" width="100%"></p>

<p align="center">Outline a spot in a photo, then compare it with the conditions you choose.</p>

> **Research preview, not a medical device.** Maculo can't diagnose, detect or rule
> out any condition. Scores only rank the conditions on your list. The matching
> model is licensed for **non-commercial research only** (CC BY-NC-ND 4.0).

---

## What it does

1. **Outline.** Click a spot, or drag a box around a small one. The Segment Anything
   model (SAM) draws its outline. Use **+ Add area** / **− Remove area** to refine it.
2. **Compare.** A vision-language model trained on skin images scores the outlined
   area against each condition you've selected (54 presets in 7 groups, plus your own).
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
  `SamModel` checkpoint works, e.g. `facebook/sam-vit-base`:

  ```bash
  huggingface-cli download facebook/sam-vit-base --local-dir models/sam
  ```

- **The matching model** (`Xieji-Li/MAGEN-O-MAKE`) downloads from Hugging Face on
  the first run (about 570 MB) and is cached after that.

You only need the internet for that first download. After it, Maculo loads both
models from disk. To make sure it never goes online, set `HF_HUB_OFFLINE=1`.

### Run

```bash
python -m maculo
```

Open <http://127.0.0.1:8000>. Interactive API docs are at <http://127.0.0.1:8000/docs>.

If you start it from a terminal where the venv isn't activated, Maculo restarts itself
with `venv\Scripts\python.exe` so the pinned packages are used. Set
`MACULO_NO_RELAUNCH=1` to turn that off.

## Troubleshooting

**The page says "The analysis models failed to load", or `/readyz` stays at 503.**
Look at the server window for `model loading failed` and the error under it.

| Error | Cause and fix |
|---|---|
| `No module named 'open_clip'` or a `transformers` import error such as `cannot import name 'VideoInput'` | The server is running on the wrong Python, usually the global one. Start with `start.bat` or `venv\Scripts\python.exe -m maculo`, then check with `where python` that the venv comes first. |
| `SAM model not found in ...` | `models/sam/` is empty. See [Models](#models). |
| It takes minutes and then times out | The first run is downloading the matching model, so check your connection. Re-running resumes the download. |

**Check that the GPU is used.** This should print `2.6.0+cu124 True`:

```bash
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

If it shows `+cpu` or `False`, reinstall PyTorch with the `cu124` command above and add
`--force-reinstall`. When the models are ready, the log says `models loaded on cuda in ...`.

**`venv\Scripts\activate` runs the wrong Python.** This happens if the `venv` folder was
copied or moved from somewhere else, because the activate scripts keep the old path.
Recreate it with `python -m venv venv --clear` and reinstall as in
[Setup from scratch](#setup-from-scratch).

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
