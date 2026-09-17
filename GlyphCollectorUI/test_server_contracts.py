import re
from pathlib import Path

HTML = Path(__file__).with_name("GlyphCollectorUI.html").read_text(encoding="utf-8")


def test_server_save_uses_configured_preview_server_url():
    """Cross-origin collector saves must target the configured Assembler URL."""
    assert "fetch('/api/save-glyph'" not in HTML
    assert "function serverSaveUrl()" in HTML
    assert re.search(r"const\s+saveUrl\s*=\s*serverSaveUrl\(\)", HTML)
    assert re.search(r"fetch\(\s*saveUrl\s*\+\s*['\"]/api/save-glyph['\"]", HTML)


def test_existing_glyph_indicator_does_not_interpolate_char_into_inner_html():
    """Stored glyph metadata is user data and must not be injected as HTML."""
    function = re.search(
        r"function\s+updateExistingIndicator\s*\([^)]*\)\s*\{(?P<body>.*?)\n\s*function\s+loadExistingGlyph",
        HTML,
        re.S,
    )
    assert function, "updateExistingIndicator() must exist"
    body = function.group("body")
    assert "${data.char}" not in body
    assert "createElement('button')" in body or 'createElement("button")' in body
    assert ".textContent" in body
