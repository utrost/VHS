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


def test_queue_start_guards_unsaved_strokes_before_retargeting_character():
    """Starting a queue must not silently relabel existing unsaved strokes."""
    assert "function hasUnsavedStrokes()" in HTML
    assert "Start queue and discard the unsaved strokes" in HTML
    start_queue = re.search(
        r"function\s+startQueue\s*\([^)]*\)\s*\{(?P<body>.*?)\n\s*function\s+advanceQueue",
        HTML,
        re.S,
    )
    assert start_queue, "startQueue() must exist"
    body = start_queue.group("body")
    guard_pos = body.find("hasUnsavedStrokes()")
    retarget_pos = body.find("charInput').value = queueChars[0]")
    assert guard_pos != -1, "startQueue must check unsaved strokes"
    assert retarget_pos != -1, "startQueue must preload the first queued character"
    assert guard_pos < retarget_pos, "unsaved-strokes guard must run before retargeting charInput"


def test_global_enter_shortcut_ignores_form_fields_before_saving():
    init = re.search(
        r"document\.addEventListener\('keydown', \(e\) => \{(?P<body>.*?)\n\s*// Auto-save when character input changes",
        HTML,
        re.S,
    )
    assert init, "init keydown handler must exist"
    body = init.group("body")
    enter_pos = body.find("e.key === 'Enter'")
    save_pos = body.find("saveAndReset()", enter_pos)
    guard_pos = body.find("isFormFieldActive()")
    assert enter_pos != -1 and save_pos != -1, "Enter shortcut must still save from drawing context"
    assert guard_pos != -1 and guard_pos < save_pos, "Enter shortcut must guard form fields before save"
