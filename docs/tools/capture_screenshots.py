#!/usr/bin/env python3
"""Capture the screenshots referenced in docs/GUIDE_*.md.

Usage:
    python3 docs/tools/capture_screenshots.py

Assumes the Assembler server is running at http://localhost:5001 and
writes PNGs into docs/img/. Re-run after every visible UI change to
keep the illustrated guides accurate.
"""
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent.parent
IMG_DIR = ROOT / "docs" / "img"
IMG_DIR.mkdir(parents=True, exist_ok=True)

SERVER = os.environ.get("VHS_SERVER_URL", "http://localhost:5001")
LONG_TEXT = (
    "Call me Ishmael. Some years ago, never mind how long precisely, "
    "having little or no money in my purse, and nothing particular to "
    "interest me on shore, I thought I would sail about a little and "
    "see the watery part of the world."
)


def wait_for_render(page, timeout_ms: int = 8000):
    """Wait until the preview container has an SVG and the status shows
    'ready' (not 'Updating…')."""
    page.wait_for_selector(".preview-svg-wrapper svg", timeout=timeout_ms)
    # Short settle so the status text switches from "Updating…" to "Ready".
    page.wait_for_timeout(200)


def capture_assembler_gui(page):
    """Annotated sidebar screenshots for GUIDE_ASSEMBLER_GUI."""
    # Tall viewport so Page Setup + Typography + Styling all fit.
    page.set_viewport_size({"width": 1480, "height": 1400})
    page.goto(SERVER + "/", wait_until="networkidle")
    page.wait_for_timeout(400)

    # Apply the casual-a4 preset via the sidebar dropdown — that loads
    # a rich, realistic parameter set in one line.
    page.select_option("#presetSelect", "casual-a4")
    page.wait_for_timeout(200)
    page.fill("#textInput", LONG_TEXT)
    # Disable live preview while we fill fields so there's no race.
    page.evaluate("() => { document.getElementById('livePreview').checked = false; }")
    page.evaluate("() => { document.getElementById('autoKern').checked = true; }")
    page.click("#generateBtn")
    wait_for_render(page)

    # Force sidebar scroll to the top so the Preset section is visible.
    page.evaluate("() => { document.querySelector('aside').scrollTop = 0; }")
    page.wait_for_timeout(100)
    page.screenshot(path=str(IMG_DIR / "gui-overview.png"), full_page=False)

    # Sidebar-only close-up (whole scrollable content).
    sidebar = page.locator("aside")
    if sidebar.count():
        sidebar.screenshot(path=str(IMG_DIR / "gui-sidebar.png"))

    # Coverage panel: text with characters that trigger substitutions + drops.
    page.fill("#textInput", "Hello — it's a \u201Cquoted\u201D test\u2026")
    page.click("#generateBtn")
    wait_for_render(page)
    page.wait_for_timeout(300)
    page.screenshot(path=str(IMG_DIR / "gui-coverage.png"), full_page=False)


def capture_collector(page):
    """Screenshot the GlyphCollector at several key states."""
    page.set_viewport_size({"width": 1440, "height": 900})

    # The Collector ships with a Tailwind CDN <script>. In offline
    # environments that script can't load, which leaves the whole page
    # unstyled. For the screenshot pass we route the CDN request to a
    # stub and inject a hand-rolled fallback stylesheet that covers
    # the utility classes actually used by the Collector markup.
    shim_css = (Path(__file__).parent / "collector-shim.css").read_text()

    def intercept_tailwind(route):
        # Replace the Tailwind JS CDN with a no-op so it fails fast.
        route.fulfill(status=200, content_type="application/javascript",
                      body="/* Tailwind CDN stubbed for offline screenshots */")
    page.route("**/cdn.tailwindcss.com/**", intercept_tailwind)
    page.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(
        status=200, content_type="text/css", body=""))
    page.route("**/fonts.gstatic.com/**", lambda r: r.fulfill(
        status=200, content_type="font/woff2", body=b""))

    page.goto(SERVER + "/collector", wait_until="domcontentloaded")
    page.add_style_tag(content=shim_css)
    page.wait_for_timeout(400)

    # Viewport-sized (not full_page) — the canvas grid extends way below
    # the fold and isn't useful in a screenshot.
    page.screenshot(path=str(IMG_DIR / "collector-empty.png"), full_page=False)

    page.fill("#charInput", "a")
    page.fill("#queueInput", "abcdefghijklmnopqrstuvwxyz")
    page.wait_for_timeout(300)
    page.screenshot(path=str(IMG_DIR / "collector-queue-ready.png"), full_page=False)

    # Open the coverage dashboard panel.
    page.click("button[title='Font coverage dashboard']")
    page.wait_for_timeout(600)
    page.screenshot(path=str(IMG_DIR / "collector-coverage.png"), full_page=False)


def capture_assembler_cli(renderer_path):
    """Convert a representative CLI-rendered SVG into a PNG thumbnail."""
    import subprocess
    # 1. Produce a fresh SVG via the CLI, using the casual-a4 preset.
    samples = [
        ("letter-a4", "cli-letter-a4.svg", LONG_TEXT),
        ("casual-a4", "cli-casual-a4.svg", LONG_TEXT),
        ("notebook-page", "cli-notebook.svg", LONG_TEXT),
    ]
    for preset, fname, text in samples:
        svg_path = IMG_DIR / fname
        png_path = svg_path.with_suffix(".png")
        subprocess.run([
            sys.executable, "assembler/assembler.py",
            "--preset", preset,
            "--font", "font1",
            "--seed", "42",
            "--stroke-width", "0.4",
            text,
            str(svg_path),
        ], cwd=str(ROOT), check=True, capture_output=True)
        # Convert to PNG at 150 dpi for the docs.
        import cairosvg
        cairosvg.svg2png(url=str(svg_path), write_to=str(png_path),
                         dpi=150, background_color="white")
        svg_path.unlink(missing_ok=True)  # only keep the PNG in img/

    # Render + capture a --report text snippet as a PNG image of text
    proc = subprocess.run([
        sys.executable, "assembler/assembler.py",
        "--preset", "letter-a4", "--font", "font1",
        "--report", "--seed", "42",
        LONG_TEXT,
        "/tmp/dummy.svg",
    ], cwd=str(ROOT), capture_output=True, text=True)
    (IMG_DIR / "cli-report.txt").write_text(proc.stdout)


def main():
    renderer_path = ROOT / "assembler" / "assembler.py"
    capture_assembler_cli(renderer_path)
    with sync_playwright() as p:
        # Use the system-installed chromium if present; fall back to
        # Playwright's bundled browser otherwise.
        launch_kwargs = {}
        for candidate in (
            "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ):
            if Path(candidate).exists():
                launch_kwargs["executable_path"] = candidate
                break
        browser = p.chromium.launch(**launch_kwargs)
        ctx = browser.new_context()
        page = ctx.new_page()
        capture_assembler_gui(page)
        capture_collector(page)
        browser.close()
    print(f"Screenshots written to {IMG_DIR}")


if __name__ == "__main__":
    main()
