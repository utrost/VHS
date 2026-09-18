import re
from pathlib import Path

HTML = Path(__file__).parent.joinpath("templates", "index.html").read_text(encoding="utf-8")
_style_match = re.search(r"<style>(.*?)</style>", HTML, re.S)
assert _style_match, "Assembler template must include an inline <style> block"
STYLE = _style_match.group(1)


def _tag_for_id(control_id: str) -> str:
    match = re.search(rf"<(?P<tag>input|select|textarea|button)\b(?=[^>]*\bid=\"{re.escape(control_id)}\")[^>]*>", HTML, re.S)
    assert match, f"missing control #{control_id}"
    return match.group(0)


def _media_block(max_width: int) -> str:
    marker = f"@media (max-width: {max_width}px)"
    start = STYLE.find(marker)
    assert start != -1, f"missing {marker}"
    brace = STYLE.find("{", start)
    depth = 0
    for idx in range(brace, len(STYLE)):
        if STYLE[idx] == "{":
            depth += 1
        elif STYLE[idx] == "}":
            depth -= 1
            if depth == 0:
                return STYLE[brace + 1:idx]
    raise AssertionError(f"unclosed {marker}")


def test_assembler_primary_form_controls_have_programmatic_labels():
    for control_id in [
        "textInput", "fileUpload", "fontSelect", "presetSelect", "paperSize",
        "orientation", "margin", "startX", "startY", "maxWidthMm",
        "lineHeightMm", "linesPerPage", "lineSpacing", "wrapMode",
        "spaceWidthMm", "spaceJitterMm", "kernAggressiveness", "jitter",
        "strokeWidth", "color", "lineDriftAngle", "lineDriftY",
        "glyphSlantJitter", "glyphYJitter", "pngDpi", "pngTransparent",
    ]:
        tag = _tag_for_id(control_id)
        has_label = re.search(rf"<label\b[^>]*\bfor=\"{re.escape(control_id)}\"", HTML)
        has_aria = re.search(r"\baria-label=\"[^\"]+\"|\baria-labelledby=\"[^\"]+\"", tag)
        assert has_label or has_aria, f"#{control_id} needs a programmatic label"


def test_assembler_toggles_are_keyboard_visible_labeled_checkboxes():
    assert ".toggle input { display: none; }" not in HTML
    for control_id, label_text in [
        ("smooth", "Smooth Curves"),
        ("autoKern", "Auto Kerning"),
        ("fallbacks", "Unicode Fallbacks"),
        ("livePreview", "Live Preview"),
    ]:
        tag = _tag_for_id(control_id)
        assert f'aria-label="{label_text}"' in tag or re.search(rf"<label\b[^>]*\bfor=\"{control_id}\"[^>]*>\s*{re.escape(label_text)}", HTML), control_id
    assert "toggle input:focus-visible" in STYLE


def test_assembler_mobile_layout_enables_vertical_escape_without_horizontal_overflow():
    mobile = _media_block(768)
    for required in [
        "html, body",
        "height: auto",
        "min-height: 100%",
        "overflow-x: hidden",
        "overflow-y: auto",
        ".header",
        "flex-wrap: wrap",
        ".main",
        "overflow: visible",
        ".sidebar",
        "max-height: none",
        ".preview-area",
        "min-height: 60vh",
        ".preview-toolbar",
        ".preview-toolbar > div",
    ]:
        assert required in mobile, f"mobile CSS missing {required}"


def test_assembler_mobile_touch_targets_and_wrapping_controls():
    mobile = _media_block(768)
    for selector in [".view-tab", ".btn", ".toggle", ".fitchip-btn"]:
        assert selector in mobile, f"mobile CSS must size {selector}"
    assert "min-height: 44px" in mobile
    assert "flex-wrap: wrap" in mobile


def test_text_file_upload_reuses_input_session_and_live_preview_path():
    match = re.search(r"function\s+handleFileUpload\s*\([^)]*\)\s*\{(?P<body>.*?)\n\s*// ── Generate", HTML, re.S)
    assert match, "handleFileUpload() must exist"
    body = match.group("body")
    assert "textInput.dispatchEvent(new Event('input', { bubbles: true }))" in body
    assert "textInput.dispatchEvent(new Event('change', { bubbles: true }))" in body
    assert "saveSession()" in body


def test_wysiwyg_editor_handles_are_keyboard_accessible_controls():
    assert '<button type="button" class="wys-handle move"' in HTML
    assert 'aria-label="Move text block"' in HTML
    assert 'aria-label="Resize text column"' in HTML
    assert 'aria-label="Adjust page margin"' in HTML
    assert "function attachKeyboardHandle" in HTML
    assert "addEventListener('keydown'" in HTML
    assert "ArrowLeft" in HTML and "ArrowRight" in HTML and "ArrowUp" in HTML and "ArrowDown" in HTML
    assert "o.querySelectorAll('.wys-handle').forEach(attachKeyboardHandle)" in HTML


def test_extra_frame_controls_are_keyboard_accessible_buttons():
    assert "_el('button', 'wys-handle move frame')" in HTML
    assert "_el('button', 'wys-handle ew frame')" in HTML
    assert "_el('button', 'wys-frame-del')" in HTML
    assert "hMove.setAttribute('aria-label'" in HTML
    assert "hEw.setAttribute('aria-label'" in HTML
    assert "del.setAttribute('aria-label'" in HTML
    assert "attachKeyboardFrameHandle" in HTML
