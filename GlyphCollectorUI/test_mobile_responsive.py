import re
from pathlib import Path

HTML = Path(__file__).with_name("GlyphCollectorUI.html").read_text(encoding="utf-8")
_style_match = re.search(r"<style>(.*?)</style>", HTML, re.S)
assert _style_match, "GlyphCollectorUI.html must include an inline <style> block"
STYLE = _style_match.group(1)


def _css_block(selector: str) -> str:
    """Return declarations for a simple CSS selector block."""
    pattern = re.compile(r"%s\s*\{(?P<body>[^{}]*)\}" % re.escape(selector), re.S)
    match = pattern.search(STYLE)
    assert match, f"missing CSS rule for {selector}"
    return match.group("body")


def _media_block(max_width: int) -> str:
    marker = f"@media (max-width: {max_width}px)"
    start = STYLE.find(marker)
    assert start != -1, f"missing {marker} responsive breakpoint"
    brace = STYLE.find("{", start)
    assert brace != -1, f"{marker} has no opening brace"
    depth = 0
    for idx in range(brace, len(STYLE)):
        if STYLE[idx] == "{":
            depth += 1
        elif STYLE[idx] == "}":
            depth -= 1
            if depth == 0:
                return STYLE[brace + 1:idx]
    raise AssertionError(f"{marker} block is not closed")


def test_viewport_is_mobile_width_without_forced_zoom_lock():
    meta = re.search(r'<meta\s+name="viewport"\s+content="([^"]+)"', HTML)
    assert meta, "missing viewport meta tag"
    content = meta.group(1)
    assert "width=device-width" in content
    assert "initial-scale=1.0" in content
    assert "user-scalable=no" not in content, "stylus users must be allowed to pinch-zoom"
    assert "maximum-scale" not in content, "do not cap mobile zoom"


def test_touch_action_none_is_limited_to_canvas_slots():
    selectors = re.findall(r"([^{}]+)\{[^{}]*touch-action\s*:\s*none\s*;", STYLE)
    normalized = [selector.strip() for selector in selectors]
    assert normalized == [".canvas-slot"], f"touch-action:none must only apply to canvas slots, got {normalized}"


def test_mobile_breakpoint_is_valid_and_enables_page_scroll():
    mobile = _media_block(900)
    assert "single-column" in mobile or "flex-direction: column" in mobile
    for required in [
        "html, body",
        "height: auto",
        "overflow-y: auto",
        "overflow-x: hidden",
        "-webkit-overflow-scrolling: touch",
        "main",
        "overflow-y: visible",
        "#canvasContainer",
        "flex-direction: column",
    ]:
        assert required in mobile, f"mobile CSS missing {required}"


def test_mobile_toolbar_wraps_and_queue_collapses():
    mobile = _media_block(900)
    for required in [
        "header > div",
        "flex-wrap: wrap",
        "header > div:nth-of-type(2)",
        "overflow-x: auto",
        "#queueStartBtn",
        "#queueStatus",
        "width: 100%",
    ]:
        assert required in mobile, f"mobile toolbar contract missing {required}"


def test_mobile_panels_are_bottom_sheets():
    mobile = _media_block(900)
    for panel in ["#settingsPanel", "#coveragePanel", "#previewPanel"]:
        assert panel in mobile, f"{panel} must be included in mobile bottom-sheet CSS"
    for required in [
        "position: fixed",
        "bottom: 0",
        "left: 0",
        "right: 0",
        "width: 100%",
        "max-height: 70vh",
        "overflow-y: auto",
        "border-radius: 1rem 1rem 0 0",
    ]:
        assert required in mobile, f"bottom-sheet CSS missing {required}"


def test_mobile_canvas_slots_fit_small_screens_with_safe_touch_target():
    mobile = _media_block(900)
    for required in [
        ".canvas-slot",
        "width: min(",
        "calc(100vw - 2rem)",
        "height: auto",
        "max-width: 420px",
    ]:
        assert required in mobile, f"canvas sizing contract missing {required}"
    assert re.search(r"canvas\.style\.maxWidth\s*=\s*['\"]100%['\"]", HTML), "generated canvases must cap CSS width at 100%"
    assert re.search(r"canvas\.style\.height\s*=\s*`\$\{CANVAS_HEIGHT \* DISPLAY_SCALE\}px`", HTML), "canvas CSS height should preserve configured aspect until mobile CSS scales it"
