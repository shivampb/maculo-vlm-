"""Render the brand's PNG assets and the web app's icons from the SVG sources.

Usage:  python brand/export.py
Needs Microsoft Edge or Google Chrome (used headless) and Pillow. Fonts load
from Google Fonts, so run it online.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

BRAND = Path(__file__).resolve().parent
ROOT = BRAND.parent
LOGO = BRAND / "logo"
STATIC_IMG = ROOT / "static" / "img"
FONTS = (
    '<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700'
    '&display=swap" rel="stylesheet">'
)

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "google-chrome",
    "chromium",
    "microsoft-edge",
]


def find_browser() -> str:
    for b in BROWSERS:
        if os.path.exists(b) or shutil.which(b):
            return b
    sys.exit("Edge or Chrome is required to export brand assets.")


def svg(name: str) -> str:
    return (LOGO / name).read_text(encoding="utf-8")


def mark_inner(full_bleed: bool = False, scale: float = 1.0) -> str:
    """The mark's SVG, optionally as a square (for iOS/Android icons) and scaled
    inside its tile (for maskable icons, which crop the edges)."""
    s = svg("maculo-mark.svg")
    if full_bleed:
        s = s.replace('rx="16"', 'rx="0"')
    if scale != 1.0:
        start, end = s.index(">", s.index("<rect")) + 1, s.rindex("</svg>")
        off = 32 * (1 - scale)
        s = s[:start] + f'<g transform="translate({off} {off}) scale({scale})">' + s[start:end] + "</g>" + s[end:]
    return s


def page(body: str, w: int, h: int, bg: str = "transparent") -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>
html,body{{margin:0;width:{w}px;height:{h}px;overflow:hidden;background:{bg}}}
svg.fill{{display:block;width:{w}px;height:{h}px}}
</style></head><body>{body}</body></html>"""


def render(browser: str, html: str, w: int, h: int, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "page.html"
        src.write_text(html, encoding="utf-8")
        shot = Path(tmp) / "shot.png"
        subprocess.run(
            [
                browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                "--force-device-scale-factor=1", "--default-background-color=00000000",
                "--virtual-time-budget=5000", f"--window-size={w},{h}",
                f"--screenshot={shot}", src.as_uri(),
            ],
            check=True, capture_output=True, timeout=60,
        )
        Image.open(shot).convert("RGBA").crop((0, 0, w, h)).save(out, optimize=True)
    print("wrote", out.relative_to(ROOT))


def fill(svg_text: str) -> str:
    return svg_text.replace("<svg ", '<svg class="fill" ', 1)


OG = """
<div style="position:relative;width:1200px;height:630px;background:#0C1F19;font-family:Outfit;color:#fff;overflow:hidden">
  <div style="position:absolute;right:-60px;top:-60px;width:600px;height:750px;background:#91F188;border-radius:48px"></div>
  <svg viewBox="0 0 64 64" style="position:absolute;right:90px;top:110px;width:410px;height:410px">
    <path d="M13 23v-4.5a5.5 5.5 0 0 1 5.5-5.5H23M41 13h4.5a5.5 5.5 0 0 1 5.5 5.5V23M51 41v4.5a5.5 5.5 0 0 1-5.5 5.5H41M23 51h-4.5a5.5 5.5 0 0 1-5.5-5.5V41"
      fill="none" stroke="#0C1F19" stroke-opacity=".45" stroke-width="2" stroke-linecap="round"/>
    <path d="M27.2 21c4.5-2.9 10.6-2.7 14.5.6 4.1 3.4 4.6 8.2 2.6 11.6-1.5 2.6-1 5.5-2.9 8.3-2.7 4-8.9 5.2-13.6 2.9-4.8-2.3-7.9-7.2-7.3-12.4.4-4.4 2.9-8.6 6.7-11z"
      fill="#0C1F19" fill-opacity=".08" stroke="#0C1F19" stroke-width="2" stroke-linejoin="round"/>
    <circle cx="32.4" cy="31.6" r="3" fill="#99DBF5" stroke="#0C1F19" stroke-width="1.2"/>
  </svg>
  <div style="position:absolute;left:72px;top:68px;display:flex;align-items:center;gap:16px">
    <div style="width:60px;height:60px">{mark}</div>
    <span style="font:600 48px Outfit;letter-spacing:-.03em">maculo</span>
  </div>
  <div style="position:absolute;left:72px;top:220px;width:520px">
    <div style="font:600 70px/1.02 Outfit;letter-spacing:-.03em">A closer look at <span style="color:#91F188">skin spots.</span></div>
    <div style="font:300 25px/1.4 Outfit;color:#c9d6d1;margin-top:22px">Outline a spot, then compare it with the conditions you choose.</div>
  </div>
  <div style="position:absolute;left:72px;bottom:56px;font:500 17px Outfit;color:#99DBF5;letter-spacing:.08em;text-transform:uppercase">Research preview · Not a diagnosis</div>
</div>"""


def main() -> None:
    browser = find_browser()
    png = BRAND / "png"

    for size in (1024, 512, 256, 128, 64, 32, 16):
        render(browser, page(fill(mark_inner()), size, size), size, size, png / f"maculo-mark-{size}.png")
    for name, out in [("maculo-mark-mono.svg", "maculo-mark-mono-512.png"),
                      ("maculo-mark-white.svg", "maculo-mark-white-512.png"),
                      ("maculo-mark-lime.svg", "maculo-mark-lime-512.png")]:
        render(browser, page(fill(svg(name)), 512, 512), 512, 512, png / out)
    for name, out in [("maculo-logo.svg", "maculo-logo.png"),
                      ("maculo-logo-reversed.svg", "maculo-logo-reversed.png"),
                      ("maculo-logo-on-lime.svg", "maculo-logo-on-lime.png")]:
        render(browser, page(fill(svg(name)), 1000, 256), 1000, 256, png / out)

    og = BRAND / "social" / "og-image.png"
    render(browser, page(OG.replace("{mark}", fill(mark_inner()).replace('class="fill"', 'width="64" height="64"')), 1200, 630), 1200, 630, og)

    # Web app icons
    STATIC_IMG.mkdir(parents=True, exist_ok=True)
    shutil.copy(LOGO / "maculo-mark.svg", STATIC_IMG / "favicon.svg")
    shutil.copy(LOGO / "maculo-mark.svg", STATIC_IMG / "logo-mark.svg")
    shutil.copy(og, STATIC_IMG / "og-image.png")
    render(browser, page(fill(mark_inner(full_bleed=True)), 180, 180), 180, 180, STATIC_IMG / "apple-touch-icon.png")
    render(browser, page(fill(mark_inner()), 192, 192), 192, 192, STATIC_IMG / "icon-192.png")
    render(browser, page(fill(mark_inner()), 512, 512), 512, 512, STATIC_IMG / "icon-512.png")
    render(browser, page(fill(mark_inner(full_bleed=True, scale=0.78)), 512, 512), 512, 512, STATIC_IMG / "icon-maskable-512.png")

    ico = Image.open(png / "maculo-mark-256.png")
    buf = io.BytesIO()
    ico.save(buf, "ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    (ROOT / "static" / "favicon.ico").write_bytes(buf.getvalue())
    print("wrote static/favicon.ico")

    # The brand board, as one image to share
    with tempfile.TemporaryDirectory():
        board = BRAND / "index.html"
        out = BRAND / "maculo-brand-board.png"
        subprocess.run(
            [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             "--force-device-scale-factor=1", "--virtual-time-budget=6000",
             "--window-size=1200,2150", f"--screenshot={out}", board.as_uri()],
            check=True, capture_output=True, timeout=60,
        )
        print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
